"""Read the text layer embedded in a PDF page as OCR-shaped tokens (REQ-027).

A PDF produced by software already carries its text; reading it is exact and
much faster than raster OCR. The result is recorded under its own producer
name, so provenance never claims an OCR engine read it. Call only inside the
bounded worker: pypdfium2 is a native decoder.
"""
from __future__ import annotations

from importlib import metadata

from .ocr_adapter import OCRToken

PDF_TEXT_PRODUCER_NAME = "pdf-text-layer"
MIN_USEFUL_CHARS = 20


def producer_version() -> str:
    try:
        return metadata.version("pypdfium2")
    except metadata.PackageNotFoundError:
        return "unavailable"


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, value))


def extract_text_tokens(source_bytes: bytes, page_number: int, *, min_chars: int = MIN_USEFUL_CHARS) -> list[OCRToken] | None:
    """Return the page's words with normalized boxes, or ``None`` when the text is not usable.

    ``None`` means: no text layer, fewer than ``min_chars`` non-blank characters,
    or a page that cannot be read; the caller then runs OCR instead.
    """
    try:
        import pypdfium2
    except ImportError:
        return None
    try:
        document = pypdfium2.PdfDocument(source_bytes)
    except Exception:
        return None
    try:
        if not 1 <= page_number <= len(document):
            return None
        page = document[page_number - 1]
        width, height = page.get_size()
        textpage = page.get_textpage()
        try:
            count = textpage.count_chars()
            if count <= 0 or width <= 0 or height <= 0:
                return None
            text = textpage.get_text_range(0, count)
            if sum(1 for char in text if not char.isspace()) < min_chars:
                return None
            words: list[tuple[str, float, float, float, float]] = []
            current: list[str] = []
            box: list[float] | None = None
            for index in range(min(count, len(text))):
                char = text[index]
                if char.isspace():
                    if current:
                        words.append(("".join(current), *box))
                    current, box = [], None
                    continue
                left, bottom, right, top = textpage.get_charbox(index)
                current.append(char)
                box = [left, bottom, right, top] if box is None else [
                    min(box[0], left), min(box[1], bottom), max(box[2], right), max(box[3], top),
                ]
            if current:
                words.append(("".join(current), *box))
        finally:
            textpage.close()
            page.close()
    finally:
        document.close()

    tokens: list[OCRToken] = []
    for index, (word, left, bottom, right, top) in enumerate(words, 1):
        x0, x1 = _clamp(left / width), _clamp(right / width)
        y0, y1 = _clamp(1.0 - top / height), _clamp(1.0 - bottom / height)
        if x1 <= x0 or y1 <= y0:
            continue
        tokens.append(OCRToken(
            token_id=f"p{page_number}-text-{index}",
            text=word,
            polygon=((x0, y0), (x1, y0), (x1, y1), (x0, y1)),
            confidence=None,
        ))
    return tokens or None
