"""Bounded, standard-library inspection of raster dimensions before decoding."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ImageInfo:
    width_px: int
    height_px: int
    page_count: int = 1


class ImageHeaderError(ValueError):
    """Raster metadata was missing, malformed, animated, or outside configured bounds."""


def _check_dimensions(width: int, height: int, max_dimension: int, max_pixels: int) -> None:
    if width <= 0 or height <= 0:
        raise ImageHeaderError("image dimensions must be positive")
    if width > max_dimension or height > max_dimension:
        raise ImageHeaderError("image dimension exceeds configured limit")
    if width * height > max_pixels:
        raise ImageHeaderError("image pixel count exceeds configured limit")


def _png(header: bytes, max_header_bytes: int) -> ImageInfo:
    if len(header) < 33 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ImageHeaderError("truncated PNG header")
    if int.from_bytes(header[8:12], "big") != 13 or header[12:16] != b"IHDR":
        raise ImageHeaderError("invalid PNG IHDR")
    width, height = int.from_bytes(header[16:20], "big"), int.from_bytes(header[20:24], "big")
    offset = 8
    while True:
        if offset + 8 > len(header):
            raise ImageHeaderError("PNG metadata exceeds configured header limit")
        length = int.from_bytes(header[offset:offset + 4], "big")
        chunk = header[offset + 4:offset + 8]
        if chunk == b"acTL":
            raise ImageHeaderError("animated PNG is not supported")
        if chunk == b"IDAT":
            break
        next_offset = offset + 12 + length
        if next_offset > len(header):
            if next_offset > max_header_bytes:
                raise ImageHeaderError("PNG metadata exceeds configured header limit")
            raise ImageHeaderError("truncated PNG metadata")
        offset = next_offset
    return ImageInfo(width, height)


def _jpeg(header: bytes, max_header_bytes: int) -> ImageInfo:
    if len(header) < 4 or header[:2] != b"\xff\xd8":
        raise ImageHeaderError("invalid JPEG signature")
    sof_markers = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
    offset = 2
    while offset < len(header):
        if header[offset] != 0xFF:
            raise ImageHeaderError("invalid JPEG marker sequence")
        while offset < len(header) and header[offset] == 0xFF:
            offset += 1
        if offset >= len(header):
            break
        marker = header[offset]
        offset += 1
        if marker in {0xD8, 0x01, *range(0xD0, 0xD8)}:
            continue
        if marker in {0xD9, 0xDA}:
            raise ImageHeaderError("JPEG dimensions are missing before image data")
        if offset + 2 > len(header):
            raise ImageHeaderError("JPEG metadata exceeds configured header limit")
        length = int.from_bytes(header[offset:offset + 2], "big")
        if length < 2:
            raise ImageHeaderError("invalid JPEG segment length")
        end = offset + length
        if end > len(header):
            if end > max_header_bytes:
                raise ImageHeaderError("JPEG metadata exceeds configured header limit")
            raise ImageHeaderError("truncated JPEG segment")
        if marker in sof_markers:
            if length < 8:
                raise ImageHeaderError("invalid JPEG frame header")
            height = int.from_bytes(header[offset + 3:offset + 5], "big")
            width = int.from_bytes(header[offset + 5:offset + 7], "big")
            return ImageInfo(width, height)
        offset = end
    raise ImageHeaderError("JPEG dimensions were not found within configured header limit")


def _tiff(header: bytes, max_pages: int) -> tuple[ImageInfo, tuple[tuple[int, int], ...]]:
    if len(header) < 8:
        raise ImageHeaderError("truncated TIFF header")
    if header[:2] == b"II":
        endian = "little"
    elif header[:2] == b"MM":
        endian = "big"
    else:
        raise ImageHeaderError("invalid TIFF byte order")
    if int.from_bytes(header[2:4], endian) != 42:
        raise ImageHeaderError("unsupported TIFF magic")
    offset = int.from_bytes(header[4:8], endian)
    seen: set[int] = set()
    pages: list[tuple[int, int]] = []
    while offset:
        if offset in seen:
            raise ImageHeaderError("cyclic TIFF page directory")
        seen.add(offset)
        if len(pages) >= max_pages:
            raise ImageHeaderError("TIFF page count exceeds configured limit")
        if offset + 2 > len(header):
            raise ImageHeaderError("TIFF metadata exceeds configured header limit")
        count = int.from_bytes(header[offset:offset + 2], endian)
        end = offset + 2 + count * 12 + 4
        if end > len(header):
            raise ImageHeaderError("TIFF metadata exceeds configured header limit")
        width = height = None
        for index in range(count):
            entry = offset + 2 + index * 12
            tag = int.from_bytes(header[entry:entry + 2], endian)
            field_type = int.from_bytes(header[entry + 2:entry + 4], endian)
            value_count = int.from_bytes(header[entry + 4:entry + 8], endian)
            if tag not in {256, 257}:
                continue
            if value_count != 1 or field_type not in {3, 4}:
                raise ImageHeaderError("unsupported TIFF dimension encoding")
            raw = header[entry + 8:entry + 12]
            if field_type == 4:
                value = int.from_bytes(raw, endian)
            else:
                value = int.from_bytes(raw[:2], endian)
            if tag == 256:
                width = value
            else:
                height = value
        if width is None or height is None:
            raise ImageHeaderError("TIFF page dimensions are missing")
        pages.append((width, height))
        offset = int.from_bytes(header[end - 4:end], endian)
    if not pages:
        raise ImageHeaderError("TIFF contains no pages")
    return ImageInfo(pages[0][0], pages[0][1], len(pages)), tuple(pages)


def _webp(header: bytes) -> ImageInfo:
    if len(header) < 20 or header[:4] != b"RIFF" or header[8:12] != b"WEBP":
        raise ImageHeaderError("invalid WebP signature")
    chunk_type = header[12:16]
    chunk_length = int.from_bytes(header[16:20], "little")
    if chunk_type == b"VP8X":
        if chunk_length < 10 or len(header) < 30:
            raise ImageHeaderError("truncated WebP extended header")
        if header[20] & 0x02:
            raise ImageHeaderError("animated WebP is not supported")
        width = 1 + int.from_bytes(header[24:27], "little")
        height = 1 + int.from_bytes(header[27:30], "little")
        return ImageInfo(width, height)
    if chunk_type == b"VP8 ":
        if chunk_length < 10 or len(header) < 30 or header[23:26] != b"\x9d\x01\x2a":
            raise ImageHeaderError("invalid WebP lossy frame header")
        width = int.from_bytes(header[26:28], "little") & 0x3FFF
        height = int.from_bytes(header[28:30], "little") & 0x3FFF
        return ImageInfo(width, height)
    if chunk_type == b"VP8L":
        if chunk_length < 5 or len(header) < 25 or header[20] != 0x2F:
            raise ImageHeaderError("invalid WebP lossless frame header")
        b1, b2, b3, b4 = header[21:25]
        width = 1 + b1 + ((b2 & 0x3F) << 8)
        height = 1 + ((b2 >> 6) | (b3 << 2) | ((b4 & 0x0F) << 10))
        return ImageInfo(width, height)
    raise ImageHeaderError("unsupported WebP frame encoding")


def inspect_image_header(
    header: bytes,
    media_kind: str,
    *,
    max_header_bytes: int,
    max_dimension: int,
    max_pixels: int,
    max_tiff_pages: int,
) -> ImageInfo:
    """Read dimensions from a bounded header without decoding pixel data."""
    if len(header) > max_header_bytes:
        raise ImageHeaderError("image header exceeds configured byte limit")
    pages: tuple[tuple[int, int], ...] | None = None
    if media_kind == "png":
        info = _png(header, max_header_bytes)
    elif media_kind == "jpeg":
        info = _jpeg(header, max_header_bytes)
    elif media_kind == "tiff":
        info, pages = _tiff(header, max_tiff_pages)
    elif media_kind == "webp":
        info = _webp(header)
    else:
        raise ImageHeaderError("unsupported raster media kind")
    for width, height in pages or ((info.width_px, info.height_px),):
        _check_dimensions(width, height, max_dimension, max_pixels)
    return info
