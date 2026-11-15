"""Read the text layer embedded in a PDF page as OCR-shaped tokens (REQ-027).

A PDF produced by software already carries its text; reading it is exact and
much faster than raster OCR. The result is recorded under its own producer
name, so provenance never claims an OCR engine read it. Call only inside the
bounded worker: pypdfium2 is a native decoder.

The text layer is used only when it can be trusted to stand for the page:
the page is not rotated, the text is visible, it has at least
``MIN_USEFUL_CHARS`` characters, and no image covers half the page (a scan
with a short text footer or a hidden OCR layer is read by the engine instead).
"""
from __future__ import annotations

from importlib import metadata

from .ocr_adapter import OCRToken

PDF_TEXT_PRODUCER_NAME = "pdf-text-layer"
MIN_USEFUL_CHARS = 20
MAX_IMAGE_COVERAGE = 0.5


def producer_version() -> str:
    try:
        return metadata.version("pypdfium2")
    except metadata.PackageNotFoundError:
        return "unavailable"


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, value))


class PdfTextLayerReader:
    """Opens a PDF once and reads the usable text layer of its pages."""

    def __init__(self, source_bytes: bytes, *, min_chars: int = MIN_USEFUL_CHARS):
        self._min_chars = min_chars
        self._document = None
        try:
            import pypdfium2

            self._pdfium = pypdfium2
            self._document = pypdfium2.PdfDocument(source_bytes)
        except Exception:
            self._document = None

    def close(self) -> None:
        if self._document is not None:
            self._document.close()
            self._document = None

    def __enter__(self) -> "PdfTextLayerReader":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def tokens(self, page_number: int) -> list[OCRToken] | None:
        """The page's visible words with boxes normalized to the crop box, or ``None``."""
        if self._document is None or not 1 <= page_number <= len(self._document):
            return None
        try:
            return self._read(page_number)
        except Exception:
            return None  # any reading problem: the engine reads the page instead

    def _read(self, page_number: int) -> list[OCRToken] | None:
        raw = self._pdfium.raw
        page = self._document[page_number - 1]
        try:
            if page.get_rotation() % 360 != 0:
                return None
            left, bottom, right, top = page.get_cropbox()
            width, height = right - left, top - bottom
            if width <= 0 or height <= 0:
                return None
            for image in page.get_objects(filter=[raw.FPDF_PAGEOBJ_IMAGE]):
                il, ib, ir, it = image.get_pos()
                covered = max(0.0, min(ir, right) - max(il, left)) * max(0.0, min(it, top) - max(ib, bottom))
                if covered >= MAX_IMAGE_COVERAGE * width * height:
                    return None
            textpage = page.get_textpage()
            try:
                words = self._words(textpage, raw)
            finally:
                textpage.close()
        finally:
            page.close()
        if words is None:
            return None
        tokens: list[OCRToken] = []
        for index, (word, wl, wb, wr, wt) in enumerate(words, 1):
            x0, x1 = _clamp((wl - left) / width), _clamp((wr - left) / width)
            y0, y1 = _clamp((top - wt) / height), _clamp((top - wb) / height)
            if x1 <= x0 or y1 <= y0:
                continue
            tokens.append(OCRToken(
                token_id=f"p{page_number}-text-{index}",
                text=word,
                polygon=((x0, y0), (x1, y0), (x1, y1), (x0, y1)),
                confidence=None,
            ))
        return tokens or None

    def _words(self, textpage, raw) -> list[tuple[str, float, float, float, float]] | None:
        count = textpage.count_chars()
        if count <= 0:
            return None
        text = textpage.get_text_range(0, count)
        words: list[tuple[str, float, float, float, float]] = []
        current: list[str] = []
        box: list[float] | None = None
        visible = 0
        for index in range(min(count, len(text))):
            char = text[index]
            invisible = False
            if not char.isspace():
                textobj = textpage.get_textobj(index)
                invisible = textobj is not None and (
                    raw.FPDFTextObj_GetTextRenderMode(textobj.raw) == raw.FPDF_TEXTRENDERMODE_INVISIBLE
                )
            if char.isspace() or invisible:
                if current:
                    words.append(("".join(current), *box))
                current, box = [], None
                continue
            visible += 1
            cl, cb, cr, ct = textpage.get_charbox(index)
            current.append(char)
            box = [cl, cb, cr, ct] if box is None else [
                min(box[0], cl), min(box[1], cb), max(box[2], cr), max(box[3], ct),
            ]
        if current:
            words.append(("".join(current), *box))
        return words if visible >= self._min_chars else None


def extract_text_tokens(source_bytes: bytes, page_number: int, *, min_chars: int = MIN_USEFUL_CHARS) -> list[OCRToken] | None:
    """One-page convenience wrapper around :class:`PdfTextLayerReader`."""
    with PdfTextLayerReader(source_bytes, min_chars=min_chars) as reader:
        return reader.tokens(page_number)
