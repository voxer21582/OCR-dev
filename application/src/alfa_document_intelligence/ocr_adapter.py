"""Engine-neutral OCR adapter contract; contains no OCR engine or decoder."""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Literal, Protocol, Sequence

_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
_OCR_ERROR_CODE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
MAX_OCR_PAGES_PER_DOCUMENT = 100
MAX_OCR_TOKENS_PER_PAGE = 10_000
MAX_OCR_TOKENS_PER_DOCUMENT = 100_000
MAX_OCR_TOKEN_ID_CHARS = 256
MAX_OCR_TOKEN_TEXT_CHARS = 4_096
MAX_OCR_POLYGON_VERTICES = 256
Point = tuple[float, float]
Polygon = tuple[Point, ...]


@dataclass(frozen=True)
class RasterPage:
    """A decoded page containing tightly packed RGB8 pixels."""
    page_number: int
    width_px: int
    height_px: int
    image_bytes: bytes


@dataclass(frozen=True)
class OCRToken:
    """One OCR observation. Text remains untrusted and is not a semantic field."""
    token_id: str
    text: str
    polygon: Polygon
    confidence: float | None = None


@dataclass(frozen=True)
class OCRPageResult:
    source_sha256: str
    page_number: int
    engine_name: str
    engine_version: str
    language: str
    tokens: tuple[OCRToken, ...]
    status: Literal["complete", "partial", "failed"] = "complete"
    error_code: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, str) or self.status not in ("complete", "partial", "failed"):
            raise OCRContractError("status must be complete, partial, or failed")
        if self.error_code is not None and (
            not isinstance(self.error_code, str)
            or not _OCR_ERROR_CODE.fullmatch(self.error_code)
        ):
            raise OCRContractError("error_code must be a stable non-sensitive code")
        if self.status == "complete" and self.error_code is not None:
            raise OCRContractError("complete result cannot have an error_code")
        if self.status != "complete" and self.error_code is None:
            raise OCRContractError("partial or failed result requires an error_code")
        if self.status == "failed" and self.tokens:
            raise OCRContractError("failed result cannot contain OCR observations")


class OCREngineAdapter(Protocol):
    """Adapter contract. Implementations must run locally in an approved environment."""
    name: str
    version: str

    def recognize(self, page: RasterPage, languages: tuple[str, ...]) -> Sequence[OCRToken]:
        """Recognize visible text on one already-decoded page."""
        ...


class OCRContractError(ValueError):
    """An adapter returned observations outside the versioned OCR contract."""


def _validate_page(page: RasterPage) -> None:
    if not isinstance(page.page_number, int) or isinstance(page.page_number, bool) or page.page_number < 1:
        raise OCRContractError("page_number must be a positive integer")
    if not isinstance(page.width_px, int) or isinstance(page.width_px, bool) or page.width_px < 1:
        raise OCRContractError("width_px must be a positive integer")
    if not isinstance(page.height_px, int) or isinstance(page.height_px, bool) or page.height_px < 1:
        raise OCRContractError("height_px must be a positive integer")
    if not isinstance(page.image_bytes, bytes) or not page.image_bytes:
        raise OCRContractError("image_bytes must be non-empty decoded page bytes")


def _validate_token(token: OCRToken, seen_ids: set[str]) -> None:
    if not isinstance(token, OCRToken):
        raise OCRContractError("adapter output must contain OCRToken values")
    if not isinstance(token.token_id, str) or not token.token_id.strip():
        raise OCRContractError("token_id is required")
    if token.token_id in seen_ids:
        raise OCRContractError("token_id must be unique within a page")
    seen_ids.add(token.token_id)
    if not isinstance(token.text, str) or not token.text.strip():
        raise OCRContractError("token text must be non-empty")
    if not isinstance(token.polygon, tuple) or len(token.polygon) < 3:
        raise OCRContractError("token polygon must have at least three normalized points")
    for point in token.polygon:
        if not isinstance(point, tuple) or len(point) != 2:
            raise OCRContractError("each polygon point must be an x,y tuple")
        x, y = point
        if (not isinstance(x, (int, float)) or isinstance(x, bool)
                or not isinstance(y, (int, float)) or isinstance(y, bool)
                or not math.isfinite(x) or not math.isfinite(y)
                or not 0 <= x <= 1 or not 0 <= y <= 1):
            raise OCRContractError("polygon coordinates must be finite and normalized to [0, 1]")
    if token.confidence is not None:
        confidence = token.confidence
        if (not isinstance(confidence, (int, float)) or isinstance(confidence, bool)
                or not math.isfinite(confidence) or not 0 <= confidence <= 1):
            raise OCRContractError("confidence must be finite and in [0, 1]")


def run_ocr(
    adapter: OCREngineAdapter,
    pages: Sequence[RasterPage],
    *,
    source_sha256: str,
    languages: tuple[str, ...] = ("it", "en"),
) -> tuple[OCRPageResult, ...]:
    """Run an injected local adapter and bind each token set to its source/page.

    Call only after bounded ingestion and local decoding have succeeded. This
    function does not provide those limits or decode the source.
    """
    if not isinstance(source_sha256, str) or not _SHA256.fullmatch(source_sha256):
        raise OCRContractError("source_sha256 must be 64 hexadecimal characters")
    if not isinstance(languages, tuple) or not languages or any(lang not in {"it", "en"} for lang in languages):
        raise OCRContractError("languages must be a non-empty tuple containing only it/en")
    if len(set(languages)) != len(languages):
        raise OCRContractError("languages must not contain duplicates")
    if not isinstance(adapter.name, str) or not adapter.name.strip():
        raise OCRContractError("adapter name is required")
    if not isinstance(adapter.version, str) or not adapter.version.strip():
        raise OCRContractError("adapter version is required")
    if not pages:
        raise OCRContractError("at least one page is required")

    results: list[OCRPageResult] = []
    seen_pages: set[int] = set()
    for page in pages:
        _validate_page(page)
        if page.page_number in seen_pages:
            raise OCRContractError("page_number must be unique in a document")
        seen_pages.add(page.page_number)
        tokens = adapter.recognize(page, languages)
        if isinstance(tokens, (str, bytes)) or not isinstance(tokens, Sequence):
            raise OCRContractError("adapter must return a sequence of OCRToken values")
        seen_ids: set[str] = set()
        for token in tokens:
            _validate_token(token, seen_ids)
        results.append(OCRPageResult(
            source_sha256=source_sha256,
            page_number=page.page_number,
            engine_name=adapter.name,
            engine_version=adapter.version,
            language="+".join(languages),
            tokens=tuple(tokens),
        ))
    return tuple(results)
