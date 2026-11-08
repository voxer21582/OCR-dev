"""Small, bounded helpers for human-selected source-page evidence."""
from __future__ import annotations

import math
import re
import struct
import zlib
from typing import Any


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MAX_DIMENSION = 12_000
_MAX_PIXELS = 50_000_000
_DEFAULT_MAX_PNG_BYTES = 64 * 1024 * 1024


def _png_chunk(kind: bytes, content: bytes) -> bytes:
    return (
        struct.pack(">I", len(content)) + kind + content
        + struct.pack(">I", zlib.crc32(kind + content) & 0xFFFFFFFF)
    )


def encode_rgb8_png(
    width: int,
    height: int,
    rgb: bytes,
    *,
    max_output_bytes: int = _DEFAULT_MAX_PNG_BYTES,
) -> bytes:
    """Encode one bounded RGB8 page to PNG without writing intermediate files."""
    if (
        not isinstance(width, int) or isinstance(width, bool) or width < 1 or width > _MAX_DIMENSION
        or not isinstance(height, int) or isinstance(height, bool) or height < 1 or height > _MAX_DIMENSION
        or width * height > _MAX_PIXELS
    ):
        raise ValueError("raster dimensions are outside the preview limits")
    if not isinstance(rgb, bytes) or len(rgb) != width * height * 3:
        raise ValueError("RGB8 bytes do not match raster dimensions")
    if not isinstance(max_output_bytes, int) or isinstance(max_output_bytes, bool) or max_output_bytes < 64:
        raise ValueError("PNG output limit must be an integer of at least 64 bytes")

    output = bytearray(b"\x89PNG\r\n\x1a\n")

    def append_chunk(kind: bytes, content: bytes) -> None:
        chunk = _png_chunk(kind, content)
        if len(output) + len(chunk) > max_output_bytes:
            raise ValueError("PNG preview exceeds the response-size limit")
        output.extend(chunk)

    append_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    compressor = zlib.compressobj(level=6)
    row_bytes = width * 3
    for row in range(height):
        start = row * row_bytes
        compressed = compressor.compress(b"\x00" + rgb[start:start + row_bytes])
        if compressed:
            append_chunk(b"IDAT", compressed)
    compressed = compressor.flush()
    if compressed:
        append_chunk(b"IDAT", compressed)
    append_chunk(b"IEND", b"")
    return bytes(output)


def normalized_rectangle(x0: str, y0: str, x1: str, y1: str) -> dict[str, Any]:
    """Parse a strict normalized rectangle and return a four-point page polygon."""
    try:
        coords = tuple(float(value) for value in (x0, y0, x1, y1))
    except (TypeError, ValueError) as exc:
        raise ValueError("coordinates must be finite normalized numbers") from exc
    if any(not math.isfinite(value) or value < 0 or value > 1 for value in coords):
        raise ValueError("coordinates must be finite normalized numbers from 0 to 1")
    left, top, right, bottom = coords
    if left >= right or top >= bottom:
        raise ValueError("region must have positive width and height")
    return {
        "coordinate_space": "normalized_page",
        "polygon": [[left, top], [right, top], [right, bottom], [left, bottom]],
    }


def build_human_region_evidence(
    source_sha256: str,
    page_number: int,
    x0: str,
    y0: str,
    x1: str,
    y1: str,
) -> dict[str, Any]:
    """Build geometry-only human evidence; the typed value is never an OCR literal."""
    if not isinstance(source_sha256, str) or not _SHA256.fullmatch(source_sha256):
        raise ValueError("source SHA-256 is invalid")
    if not isinstance(page_number, int) or isinstance(page_number, bool) or page_number < 1:
        raise ValueError("page number must be a positive integer")
    return {
        "source_sha256": source_sha256,
        "page_number": page_number,
        "region": normalized_rectangle(x0, y0, x1, y1),
        "producer": {"stage": "human_review", "name": "local-reviewer", "version": "1"},
    }
