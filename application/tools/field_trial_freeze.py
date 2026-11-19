"""In-memory primitives for binding a field-trial sheet to exact input bytes.

No files are opened, output or persisted by this module. Callers must obtain
file streams safely, keep the snapshot private and pass the returned verified
bytes directly to ingestion. These primitives do not themselves approve a
sample, safely persist a protected snapshot, prevent replay, or perform OCR.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import BinaryIO, Mapping

from tools.field_trial_sheet import SHEET, MATCHES, _rows_from_bytes, convert_reference
from tools.field_trial_score import _object

_MAX_DOCUMENT_BYTES = 25 * 1024 * 1024
_CHUNK = 1024 * 1024


@dataclass(frozen=True, repr=False)
class Snapshot:
    _sheet_digest: bytes
    _matches_digest: bytes
    _documents: Mapping[str, bytes]
    _row_locations_digest: bytes | None = None


def _consume(stream: BinaryIO, *, keep: bool):
    try:
        if stream.tell() != 0:
            raise ValueError('stream not at start')
    except (AttributeError, OSError, TypeError) as exc:
        raise ValueError('stream position unavailable') from exc
    digest = hashlib.sha256()
    size = 0
    chunks = []
    while True:
        block = stream.read(min(_CHUNK, _MAX_DOCUMENT_BYTES + 1 - size))
        if not isinstance(block, bytes):
            raise ValueError('invalid stream')
        if not block:
            break
        size += len(block)
        if size > _MAX_DOCUMENT_BYTES:
            raise ValueError('document too large')
        digest.update(block)
        if keep:
            chunks.append(block)
    if not size:
        raise ValueError('empty document')
    return digest.digest(), b''.join(chunks) if keep else None


def capture(sheet_bytes: bytes, matches_bytes: bytes, documents: Mapping[str, BinaryIO], *, row_locations=None) -> Snapshot:
    reference = convert_reference(_rows_from_bytes(sheet_bytes, SHEET), _rows_from_bytes(matches_bytes, MATCHES))
    if row_locations is not None:
        _validate_row_locations(sheet_bytes, matches_bytes, row_locations)
    ids = {item['id'] for item in reference['documents']}
    if not isinstance(documents, Mapping) or set(documents) != ids:
        raise ValueError('document set mismatch')
    digests = {}
    for key in sorted(ids):
        digest, _ = _consume(documents[key], keep=False)
        if digest in digests.values():
            raise ValueError('duplicate content')
        digests[key] = digest
    return Snapshot(hashlib.sha256(sheet_bytes).digest(), hashlib.sha256(matches_bytes).digest(), MappingProxyType(digests),
                    hashlib.sha256(row_locations).digest() if row_locations is not None else None)


def _validate_row_locations(sheet_bytes, matches_bytes, row_locations):
    rows = _rows_from_bytes(sheet_bytes, SHEET)
    matches = _rows_from_bytes(matches_bytes, MATCHES)
    locations = _rows_from_bytes(row_locations, ('codice_riga', 'codice_nota', 'pagina', 'posizione'))
    notes = {row['codice'].strip() for row in rows if row['ruolo'].strip().lower() == 'nota'}
    expected = {row['codice_riga'].strip() for row in matches}
    seen, positions = set(), set()
    for row in locations:
        code, note = row['codice_riga'].strip(), row['codice_nota'].strip()
        page, position = row['pagina'].strip(), row['posizione'].strip()
        if (code not in expected or code in seen or note not in notes
                or not re.fullmatch(r'[1-9][0-9]{0,2}', page)
                or not re.fullmatch(r'[1-9][0-9]{0,3}', position)):
            raise ValueError('invalid row locations')
        key = (note, int(page), int(position))
        if key in positions:
            raise ValueError('duplicate row location')
        seen.add(code)
        positions.add(key)
    if seen != expected:
        raise ValueError('missing row locations')


def verify_sheets(snapshot: Snapshot, sheet_bytes: bytes, matches_bytes: bytes, *, row_locations=None) -> None:
    if not (hmac.compare_digest(snapshot._sheet_digest, hashlib.sha256(sheet_bytes).digest())
            and hmac.compare_digest(snapshot._matches_digest, hashlib.sha256(matches_bytes).digest())):
        raise ValueError('sheet changed')
    if snapshot._row_locations_digest is not None:
        if not isinstance(row_locations, bytes) or not hmac.compare_digest(snapshot._row_locations_digest, hashlib.sha256(row_locations).digest()):
            raise ValueError('row locations changed')
    elif row_locations is not None:
        raise ValueError('row locations not bound')


def read_verified(snapshot: Snapshot, document_id: str, stream: BinaryIO,
                  sheet_bytes: bytes, matches_bytes: bytes, *, row_locations=None) -> bytes:
    verify_sheets(snapshot, sheet_bytes, matches_bytes, row_locations=row_locations)
    expected = snapshot._documents.get(document_id)
    if expected is None:
        raise ValueError('unknown document')
    digest, data = _consume(stream, keep=True)
    if not hmac.compare_digest(expected, digest):
        raise ValueError('document changed')
    return data


_MAX_SEALED_BYTES = 64 * 1024


def seal(snapshot: Snapshot, *, protector=None) -> bytes:
    """Protect private snapshot metadata; caller must safely persist ciphertext."""
    if protector is None:
        from alfa_document_intelligence.local_document_store import WindowsDpapiProtector
        protector = WindowsDpapiProtector()
    try:
        payload = {
            'version': 1,
            'sheet': snapshot._sheet_digest.hex(),
            'matches': snapshot._matches_digest.hex(),
            'documents': {key: value.hex() for key, value in snapshot._documents.items()},
        }
        if snapshot._row_locations_digest is not None:
            payload['version'] = 2
            payload['row_locations'] = snapshot._row_locations_digest.hex()
        plain = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('ascii')
        protected = protector.protect(plain)
        if not isinstance(protected, bytes) or not protected or len(protected) > _MAX_SEALED_BYTES:
            raise ValueError('invalid protector output')
        return protected
    except Exception:
        raise ValueError('snapshot protection failed') from None


def unseal(protected: bytes, *, protector=None) -> Snapshot:
    """Authenticate protected metadata and reject unsupported or malformed records."""
    if protector is None:
        from alfa_document_intelligence.local_document_store import WindowsDpapiProtector
        protector = WindowsDpapiProtector()
    try:
        if not isinstance(protected, bytes) or not protected or len(protected) > _MAX_SEALED_BYTES:
            raise ValueError('invalid snapshot')
        plain = protector.unprotect(protected)
        if not isinstance(plain, bytes) or len(plain) > _MAX_SEALED_BYTES:
            raise ValueError('invalid snapshot')
        payload = json.loads(plain.decode('ascii'), object_pairs_hook=_object)
        if (not isinstance(payload, dict) or type(payload.get('version')) is not int
                or not ((payload['version'] == 1 and set(payload) == {'version', 'sheet', 'matches', 'documents'})
                        or (payload['version'] == 2 and set(payload) == {'version', 'sheet', 'matches', 'documents', 'row_locations'}))):
            raise ValueError('invalid snapshot')
        docs = payload['documents']
        if not isinstance(docs, dict) or not 30 <= len(docs) <= 50:
            raise ValueError('invalid snapshot')
        def digest(value):
            if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
                raise ValueError('invalid snapshot')
            return bytes.fromhex(value)
        decoded = {}
        for key, value in docs.items():
            if not isinstance(key, str) or not re.fullmatch(r'[0-9a-f]{32}', key):
                raise ValueError('invalid snapshot')
            decoded[key] = digest(value)
        if len(set(decoded.values())) != len(decoded):
            raise ValueError('invalid snapshot')
        return Snapshot(digest(payload['sheet']), digest(payload['matches']), MappingProxyType(decoded),
                        digest(payload['row_locations']) if payload['version'] == 2 else None)
    except Exception:
        raise ValueError('snapshot authentication failed') from None
