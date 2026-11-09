"""Pure, bounded framing for the internal OCR protocol."""
import base64
import binascii
from dataclasses import dataclass
import json
import math
import os
import re
from collections.abc import Mapping


class OCRJobProtocolError(ValueError):
    """Invalid protocol input."""


def _fail():
    raise OCRJobProtocolError('Invalid OCR protocol input')


_MAX = 2147483647
_INT = 2**63 - 1
_KINDS = frozenset(('start', 'status', 'result', 'complete', 'error'))
_PHASES = frozenset(('queued', 'starting_engine', 'processing', 'cancelling', 'succeeded', 'failed', 'cancelled'))
_KEYS = {
    'start': frozenset(('v', 'kind', 'generation_id', 'documents', 'decode_limits', 'catalog_json', 'catalog_version', 'catalog_sha256')),
    'status': frozenset(('v', 'kind', 'job_id', 'generation_id', 'phase', 'completed_documents', 'total_documents', 'current_page', 'total_pages', 'error_code')),
    'result': frozenset(('v', 'kind', 'job_id', 'document_id', 'record')),
    'complete': frozenset(('v', 'kind', 'job_id', 'document_count', 'result_sha256')),
    'error': frozenset(('v', 'kind', 'job_id', 'error_code')),
}


def _integer(value, low, high):
    return type(value) is int and low <= value <= high


@dataclass(frozen=True)
class OCRProcessLimits:
    job_timeout_seconds: float
    cleanup_grace_seconds: float
    child_memory_limit_bytes: int
    max_input_frame_bytes: int
    max_status_frame_bytes: int
    max_result_frame_bytes: int
    max_aggregate_result_bytes: int
    max_page_output_bytes: int
    max_ipc_messages: int

    def __post_init__(self):
        if os.name not in ('nt', 'posix'):
            _fail()
        for value, ceiling in ((self.job_timeout_seconds, 3600), (self.cleanup_grace_seconds, 30)):
            if type(value) not in (int, float) or not 0 < value <= ceiling or not math.isfinite(value):
                _fail()
        if not _integer(self.child_memory_limit_bytes, 134217728, _MAX):
            _fail()
        for value in (self.max_input_frame_bytes, self.max_status_frame_bytes, self.max_result_frame_bytes, self.max_aggregate_result_bytes, self.max_page_output_bytes):
            if not _integer(value, 1, _MAX): _fail()
        if not _integer(self.max_ipc_messages, 1, 1000000): _fail()


def _text(value, cap):
    if type(value) is not str or not 0 < len(value) <= cap: _fail()


def _digest(value):
    if type(value) is not str or re.fullmatch(r'[0-9a-f]{64}', value) is None: _fail()


def _code(value):
    if type(value) is not str or re.fullmatch(r'[A-Za-z0-9_]{1,64}', value) is None: _fail()


def _string_size(value, cap):
    """Count JSON-escaped UTF-8 bytes without allocating an encoded copy."""
    size = 2
    for character in value:
        code = ord(character)
        if 0xD800 <= code <= 0xDFFF: _fail()
        if code < 0x20:
            size += 2 if code in (8, 9, 10, 12, 13) else 6
        elif character in ('"', '\\'):
            size += 2
        elif code < 0x80: size += 1
        elif code < 0x800: size += 2
        elif code < 0x10000: size += 3
        else: size += 4
        if size > cap: _fail()
    return size


def _encoded_size(root, cap):
    size = 0
    stack = [root]
    while stack:
        item = stack.pop()
        if type(item) is dict:
            size += 2 + max(0, len(item) - 1) + len(item)
            for key, value in item.items():
                size += _string_size(key, cap)
                stack.append(value)
        elif type(item) is list:
            size += 2 + max(0, len(item) - 1)
            stack.extend(item)
        elif type(item) is str:
            size += _string_size(item, cap)
        elif item is None: size += 4
        elif type(item) is bool: size += 4 if item else 5
        else: size += len(json.dumps(item, allow_nan=False))
        if size > cap: _fail()

def _tree(root, cap):
    stack = [(root, 0, False)]
    active = set()
    entries = 0
    while stack:
        item, depth, leaving = stack.pop()
        if leaving:
            active.remove(id(item)); continue
        if depth > 32: _fail()
        if type(item) in (dict, list):
            if id(item) in active: _fail()
            active.add(id(item)); stack.append((item, depth, True))
            entries += len(item)
            if entries > 100000: _fail()
            if type(item) is dict:
                for key, value in item.items():
                    if type(key) is not str or len(key) > 256: _fail()
                    _string_size(key, cap)
                    stack.append((value, depth + 1, False))
            else:
                stack.extend((value, depth + 1, False) for value in item)
        elif type(item) is str:
            if len(item) > cap: _fail()
            _string_size(item, cap)
        elif type(item) is int:
            if not -_INT <= item <= _INT: _fail()
        elif type(item) is float:
            if not math.isfinite(item): _fail()
        elif item is not None and type(item) is not bool:
            _fail()


def _schema(msg, cap, expected=None):
    if type(msg) is not dict: _fail()
    kind = msg.get('kind')
    if type(kind) is not str or kind not in _KINDS or (expected is not None and kind != expected): _fail()
    if set(msg) != _KEYS[kind] or type(msg['v']) is not int or msg['v'] != 1: _fail()
    for key, limit in (('job_id', 64), ('generation_id', 64), ('document_id', 128)):
        if key in msg: _text(msg[key], limit)
    if kind == 'start':
        limits = msg['decode_limits']
        names = {'max_pages', 'max_dimension_px', 'max_page_pixels', 'max_total_pixels', 'pdf_render_dpi', 'max_source_bytes'}
        if type(limits) is not dict or set(limits) != names or any(not _integer(x, 1, _INT) for x in limits.values()): _fail()
        docs = msg['documents']
        if type(docs) is not list or not docs: _fail()
        ids = set()
        source_cap = min(cap, limits['max_source_bytes'], 25 * 1024 * 1024)
        for doc in docs:
            if type(doc) is not dict or set(doc) != {'document_id', 'record', 'source_bytes_b64'}: _fail()
            identifier = doc['document_id']; _text(identifier, 128)
            if identifier in ids: _fail()
            ids.add(identifier)
            if type(doc['record']) is not dict or doc['record'].get('document_id') != identifier: _fail()
            encoded = doc['source_bytes_b64']
            if type(encoded) is not str or not encoded or len(encoded) > 4 * ((source_cap + 2) // 3): _fail()
            raw = encoded.encode('ascii')
            decoded = base64.b64decode(raw, validate=True)
            if not decoded or len(decoded) > source_cap or base64.b64encode(decoded) != raw: _fail()
        catalog = (msg['catalog_json'], msg['catalog_version'], msg['catalog_sha256'])
        if any(x is not None for x in catalog):
            if any(x is None for x in catalog) or type(catalog[0]) is not str or len(catalog[0]) > 65536 or sum(1 if ord(c) < 128 else 2 if ord(c) < 2048 else 3 if ord(c) < 65536 else 4 for c in catalog[0]) > 65536: _fail()
            _text(catalog[1], cap); _digest(catalog[2])
    elif kind == 'status':
        phase = msg['phase']
        if type(phase) is not str or phase not in _PHASES: _fail()
        for key in ('completed_documents', 'total_documents', 'current_page', 'total_pages'):
            if not _integer(msg[key], 0, _INT): _fail()
        if msg['completed_documents'] > msg['total_documents'] or msg['current_page'] > msg['total_pages']: _fail()
        if msg['error_code'] is not None: _code(msg['error_code'])
    elif kind == 'result':
        if type(msg['record']) is not dict: _fail()
    elif kind == 'complete':
        if not _integer(msg['document_count'], 1, _INT): _fail()
        _digest(msg['result_sha256'])
    else:
        _code(msg['error_code'])


def _cap(value):
    if not _integer(value, 1, _MAX): _fail()


def encode_frame(message, *, max_bytes):
    try:
        _cap(max_bytes)
        if not isinstance(message, Mapping): _fail()
        if type(message) is not dict:
            bounded = {}
            key_bytes = 0
            for key in message:
                if len(bounded) >= min(100000, max_bytes): _fail()
                if type(key) is not str or len(key) > 256 or key in bounded: _fail()
                key_bytes += _string_size(key, max_bytes) + 2
                if key_bytes > max_bytes: _fail()
                bounded[key] = message[key]
            message = bounded
        _tree(message, max_bytes); _encoded_size(message, max_bytes)
        _schema(message, max_bytes)
        chunks = []; size = 0
        for part in json.JSONEncoder(sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).iterencode(message):
            chunk = part.encode('utf-8'); size += len(chunk)
            if size > max_bytes: _fail()
            chunks.append(chunk)
        return b''.join(chunks)
    except (TypeError, ValueError, UnicodeError, RecursionError, OverflowError, binascii.Error):
        _fail()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result: _fail()
        result[key] = value
    return result


def decode_frame(frame, *, max_bytes, expected_kind):
    try:
        _cap(max_bytes)
        if type(expected_kind) is not str or expected_kind not in _KINDS: _fail()
        if type(frame) is not bytes or not frame or len(frame) > max_bytes: _fail()
        value = json.loads(frame.decode('utf-8'), object_pairs_hook=_pairs, parse_constant=lambda _: _fail())
        _tree(value, max_bytes); _schema(value, max_bytes, expected_kind)
        return value
    except (TypeError, ValueError, UnicodeError, RecursionError, OverflowError, binascii.Error):
        _fail()
