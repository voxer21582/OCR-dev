"""Bounded in-memory raster and PDF decoding for OCR.

This module is optional-runtime code: Pillow and pypdfium2 are loaded lazily.
It writes no files and returns tightly packed RGB8 bytes, one page at a time.
The caller remains responsible for bounded intake, source hashing, and any
separately required scanner policy.
"""
from __future__ import annotations

from dataclasses import dataclass
import io
import hashlib
import math
from typing import Any, Iterator

from .ocr_adapter import RasterPage


@dataclass(frozen=True)
class DecodeLimits:
    max_pages: int = 100
    max_dimension_px: int = 12_000
    max_page_pixels: int = 50_000_000
    max_total_pixels: int = 200_000_000
    pdf_render_dpi: int = 200
    max_source_bytes: int = 25 * 1024 * 1024

    def __post_init__(self) -> None:
        for name in ("max_pages", "max_dimension_px", "max_page_pixels", "max_total_pixels", "pdf_render_dpi", "max_source_bytes"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.pdf_render_dpi > 600:
            raise ValueError("pdf_render_dpi must be at most 600")


@dataclass(frozen=True)
class DecodedPage:
    raster: RasterPage
    page_count: int


class DocumentDecodeError(ValueError):
    """The source could not be decoded within the requested resource limits."""


def _check_dimensions(width: int, height: int, limits: DecodeLimits) -> int:
    if (not isinstance(width, int) or isinstance(width, bool) or width <= 0
            or not isinstance(height, int) or isinstance(height, bool) or height <= 0):
        raise DocumentDecodeError("decoded page has invalid dimensions")
    pixels = width * height
    if width > limits.max_dimension_px or height > limits.max_dimension_px:
        raise DocumentDecodeError("decoded page exceeds the dimension limit")
    if pixels > limits.max_page_pixels:
        raise DocumentDecodeError("decoded page exceeds the pixel limit")
    return pixels


def iter_decoded_pages(
    source_bytes: bytes,
    media_kind: str,
    *,
    source_sha256: str,
    limits: DecodeLimits = DecodeLimits(),
) -> Iterator[DecodedPage]:
    """Yield decoded RGB8 pages after source hash and resource-limit checks.

    PDF rasterization uses pypdfium2. Raster decoding uses Pillow. No OCR model
    is constructed, and no source or rendered page is written to disk.
    """
    if not isinstance(source_bytes, bytes) or not source_bytes:
        raise DocumentDecodeError("source bytes must be non-empty")
    if len(source_bytes) > limits.max_source_bytes:
        raise DocumentDecodeError("source bytes exceed the configured size limit")
    if not isinstance(source_sha256, str) or len(source_sha256) != 64:
        raise DocumentDecodeError("source SHA-256 is required")
    if hashlib.sha256(source_bytes).hexdigest() != source_sha256.lower():
        raise DocumentDecodeError("source bytes do not match the supplied SHA-256")
    if type(media_kind) is not str or media_kind not in {"pdf", "png", "jpeg", "tiff", "webp"}:
        raise DocumentDecodeError("unsupported media kind")

    if media_kind == "pdf":
        yield from _iter_pdf(source_bytes, source_sha256.lower(), limits)
    else:
        yield from _iter_raster(source_bytes, media_kind, source_sha256.lower(), limits)


def _iter_raster(
    data: bytes, media_kind: str, source_sha256: str, limits: DecodeLimits
) -> Iterator[DecodedPage]:
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise DocumentDecodeError("Pillow is required for raster decoding") from exc
    expected_formats = {"png": "PNG", "jpeg": "JPEG", "tiff": "TIFF", "webp": "WEBP"}
    try:
        with Image.open(io.BytesIO(data)) as source:
            if source.format != expected_formats[media_kind]:
                raise DocumentDecodeError("decoded image format does not match inventory")
            count = getattr(source, "n_frames", 1)
            if not isinstance(count, int) or count < 1 or count > limits.max_pages:
                raise DocumentDecodeError("image page count exceeds the configured limit")
            if media_kind in {"png", "webp"} and count != 1:
                raise DocumentDecodeError("animated PNG/WebP is not supported")
            total_pixels = 0
            for index in range(count):
                oriented = None
                rgb = None
                try:
                    source.seek(index)
                    _check_dimensions(*source.size, limits)
                    source.load()
                    oriented = ImageOps.exif_transpose(source)
                    rgb = oriented.convert("RGB")
                    width, height = rgb.size
                    pixels = _check_dimensions(width, height, limits)
                    total_pixels += pixels
                    if total_pixels > limits.max_total_pixels:
                        raise DocumentDecodeError("document exceeds the total pixel limit")
                    raw = rgb.tobytes()
                    if len(raw) != pixels * 3:
                        raise DocumentDecodeError("decoded raster byte count is inconsistent")
                    yield DecodedPage(RasterPage(index + 1, width, height, raw), count)
                finally:
                    if rgb is not None:
                        rgb.close()
                    if oriented is not None and oriented is not source:
                        oriented.close()
    except DocumentDecodeError:
        raise
    except Exception as exc:
        raise DocumentDecodeError("raster decoding failed") from exc


def _iter_pdf(
    data: bytes, source_sha256: str, limits: DecodeLimits
) -> Iterator[DecodedPage]:
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise DocumentDecodeError("pypdfium2 is required for PDF decoding") from exc

    document: Any = None
    try:
        document = pdfium.PdfDocument(data)
        try:
            security_revision = pdfium.raw.FPDF_GetSecurityHandlerRevision(document.raw)
        except Exception as exc:
            raise DocumentDecodeError("PDF encryption status could not be verified") from exc
        if not isinstance(security_revision, int) or isinstance(security_revision, bool) or security_revision < -1:
            raise DocumentDecodeError("PDF encryption status is invalid")
        if security_revision != -1:
            raise DocumentDecodeError("encrypted PDF is not supported")

        count = len(document)
        if not isinstance(count, int) or count < 1 or count > limits.max_pages:
            raise DocumentDecodeError("PDF page count exceeds the configured limit")
        total_pixels = 0
        for index in range(count):
            page = document[index]
            bitmap = None
            image = None
            rgb = None
            try:
                width_points, height_points = page.get_size()
                if (not math.isfinite(width_points) or not math.isfinite(height_points)
                        or width_points <= 0 or height_points <= 0):
                    raise DocumentDecodeError("PDF page has invalid dimensions")
                base_scale = limits.pdf_render_dpi / 72.0
                cap_scale = min(
                    limits.max_dimension_px / max(width_points, height_points),
                    math.sqrt(limits.max_page_pixels / (width_points * height_points)),
                    math.sqrt(max(1, limits.max_total_pixels - total_pixels) / (width_points * height_points)),
                )
                scale = min(base_scale, cap_scale) * 0.99
                if not math.isfinite(scale) or scale <= 0:
                    raise DocumentDecodeError("PDF page cannot be rendered within limits")
                bitmap = page.render(scale=scale)
                image = bitmap.to_pil()
                rgb = image.convert("RGB")
                width, height = rgb.size
                pixels = _check_dimensions(width, height, limits)
                total_pixels += pixels
                if total_pixels > limits.max_total_pixels:
                    raise DocumentDecodeError("document exceeds the total pixel limit")
                raw = rgb.tobytes()
                if len(raw) != pixels * 3:
                    raise DocumentDecodeError("decoded PDF byte count is inconsistent")
                yield DecodedPage(RasterPage(index + 1, width, height, raw), count)
            finally:
                if rgb is not None:
                    rgb.close()
                if image is not None:
                    image.close()
                if bitmap is not None and hasattr(bitmap, "close"):
                    bitmap.close()
                if hasattr(page, "close"):
                    page.close()
    except DocumentDecodeError:
        raise
    except Exception as exc:
        password_error = getattr(getattr(pdfium, "raw", None), "FPDF_ERR_PASSWORD", None)
        if password_error is not None and getattr(exc, "err_code", None) == password_error:
            raise DocumentDecodeError("password-protected PDF is not supported") from exc
        raise DocumentDecodeError("PDF decoding failed") from exc
    finally:
        if document is not None and hasattr(document, "close"):
            document.close()
