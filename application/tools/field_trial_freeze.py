"""In-memory primitives for binding a field-trial sheet to exact input bytes.

No files are opened, output or persisted by this module. Callers must obtain
file streams safely, keep the snapshot private and pass the returned verified
bytes directly to ingestion. These primitives do not themselves approve a
sample, protect a snapshot across restarts, or perform OCR.
"""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from types import MappingProxyType
from typing import BinaryIO, Mapping

from tools.field_trial_sheet import SHEET, MATCHES, _rows_from_bytes, convert_reference

_MAX_DOCUMENT_BYTES = 25 * 1024 * 1024
_CHUNK = 1024 * 1024


@dataclass(frozen=True, repr=False)
class Snapshot:
    _sheet_digest: bytes
    _matches_digest: bytes
    _documents: Mapping[str, bytes]


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


def capture(sheet_bytes: bytes, matches_bytes: bytes, documents: Mapping[str, BinaryIO]) -> Snapshot:
    reference = convert_reference(_rows_from_bytes(sheet_bytes, SHEET), _rows_from_bytes(matches_bytes, MATCHES))
    ids = {item['id'] for item in reference['documents']}
    if not isinstance(documents, Mapping) or set(documents) != ids:
        raise ValueError('document set mismatch')
    digests = {}
    for key in sorted(ids):
        digest, _ = _consume(documents[key], keep=False)
        if digest in digests.values():
            raise ValueError('duplicate content')
        digests[key] = digest
    return Snapshot(hashlib.sha256(sheet_bytes).digest(), hashlib.sha256(matches_bytes).digest(), MappingProxyType(digests))


def verify_sheets(snapshot: Snapshot, sheet_bytes: bytes, matches_bytes: bytes) -> None:
    if not (hmac.compare_digest(snapshot._sheet_digest, hashlib.sha256(sheet_bytes).digest())
            and hmac.compare_digest(snapshot._matches_digest, hashlib.sha256(matches_bytes).digest())):
        raise ValueError('sheet changed')


def read_verified(snapshot: Snapshot, document_id: str, stream: BinaryIO,
                  sheet_bytes: bytes, matches_bytes: bytes) -> bytes:
    verify_sheets(snapshot, sheet_bytes, matches_bytes)
    expected = snapshot._documents.get(document_id)
    if expected is None:
        raise ValueError('unknown document')
    digest, data = _consume(stream, keep=True)
    if not hmac.compare_digest(expected, digest):
        raise ValueError('document changed')
    return data
