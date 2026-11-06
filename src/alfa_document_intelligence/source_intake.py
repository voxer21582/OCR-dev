"""Bounded, signature-only identity for an in-memory document source.

This module does not open files, parse document structure, or run OCR.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import re
from typing import BinaryIO


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PDF_HEADER = re.compile(rb"%PDF-(?:1\.[0-7]|2\.0)")
_PDF_HEADER_MAX_START = 1023
_PDF_HEADER_LENGTH = len(b"%PDF-2.0")
_PDF_HEADER_WINDOW = _PDF_HEADER_MAX_START + _PDF_HEADER_LENGTH
_READ_CHUNK_BYTES = 64 * 1024
_ERROR_CODES = frozenset(
    {
        "source_descriptor_invalid",
        "source_format_unsupported",
        "source_limit_invalid",
        "source_payload_empty",
        "source_payload_invalid",
        "source_stream_invalid",
        "source_stream_read_failed",
        "source_too_large",
    }
)


class SourceInspectionError(ValueError):
    """Input failure carrying a stable code without document details."""

    def __init__(self, code: str) -> None:
        if type(code) is not str or code not in _ERROR_CODES:
            raise ValueError("source_error_code_invalid")
        self.code = code
        super().__init__(code)


class SourceFormat(str, Enum):
    """A format candidate identified by its leading signature only."""

    PDF = "pdf"
    PNG = "png"
    JPEG = "jpeg"
    WEBP = "webp"
    TIFF = "tiff"


@dataclass(frozen=True)
class SourceDescriptor:
    """Minimal immutable identity; it deliberately retains no source bytes."""

    sha256: str
    byte_count: int
    format_id: SourceFormat

    def __post_init__(self) -> None:
        if (
            type(self.sha256) is not str
            or _SHA256.fullmatch(self.sha256) is None
            or type(self.byte_count) is not int
            or self.byte_count < 1
            or type(self.format_id) is not SourceFormat
        ):
            raise SourceInspectionError("source_descriptor_invalid")


def _detect_format(payload: bytes) -> SourceFormat:
    # Include the complete header when it begins at the last permitted offset.
    if _PDF_HEADER.search(payload[:_PDF_HEADER_WINDOW]) is not None:
        return SourceFormat.PDF
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return SourceFormat.PNG
    if payload.startswith(b"\xff\xd8\xff"):
        return SourceFormat.JPEG
    if len(payload) >= 12 and payload[:4] == b"RIFF" and payload[8:12] == b"WEBP":
        return SourceFormat.WEBP
    if payload.startswith((b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+")):
        return SourceFormat.TIFF
    raise SourceInspectionError("source_format_unsupported")


def inspect_source(payload: bytes, *, max_bytes: int) -> SourceDescriptor:
    """Classify a signature and hash exact bytes under a required size limit.

    The caller has already materialized ``payload``; this limit does not bound
    upstream reads or allocations. Recognition does not validate, decode, or
    count pages.
    """
    if type(max_bytes) is not int or max_bytes < 1:
        raise SourceInspectionError("source_limit_invalid")
    if type(payload) is not bytes:
        raise SourceInspectionError("source_payload_invalid")
    if not payload:
        raise SourceInspectionError("source_payload_empty")
    if len(payload) > max_bytes:
        raise SourceInspectionError("source_too_large")

    format_id = _detect_format(payload)
    return SourceDescriptor(
        sha256=hashlib.sha256(payload).hexdigest(),
        byte_count=len(payload),
        format_id=format_id,
    )


def inspect_stream(stream: BinaryIO, *, max_bytes: int) -> SourceDescriptor:
    """Hash and classify a caller-owned binary stream using bounded reads.

    The caller opens, positions, and closes the stream. Reads are limited to
    64 KiB and stop after at most one byte beyond ``max_bytes``. The stream is
    consumed but is neither closed nor rewound. Its read method must honor the
    requested size; returned chunks are also checked against that bound.
    """
    if type(max_bytes) is not int or max_bytes < 1:
        raise SourceInspectionError("source_limit_invalid")
    read = getattr(stream, "read", None)
    if not callable(read):
        raise SourceInspectionError("source_stream_invalid")

    digest = hashlib.sha256()
    header = bytearray()
    byte_count = 0
    while True:
        read_size = min(_READ_CHUNK_BYTES, max_bytes + 1 - byte_count)
        try:
            chunk = read(read_size)
        except (OSError, ValueError):
            raise SourceInspectionError("source_stream_read_failed") from None
        if type(chunk) is not bytes or len(chunk) > read_size:
            raise SourceInspectionError("source_stream_invalid")
        if not chunk:
            break

        byte_count += len(chunk)
        if byte_count > max_bytes:
            raise SourceInspectionError("source_too_large")
        digest.update(chunk)
        if len(header) < _PDF_HEADER_WINDOW:
            header.extend(chunk[:_PDF_HEADER_WINDOW - len(header)])

    if byte_count == 0:
        raise SourceInspectionError("source_payload_empty")
    format_id = _detect_format(bytes(header))
    return SourceDescriptor(
        sha256=digest.hexdigest(),
        byte_count=byte_count,
        format_id=format_id,
    )


__all__ = [
    "SourceDescriptor",
    "SourceFormat",
    "SourceInspectionError",
    "inspect_source",
    "inspect_stream",
]
