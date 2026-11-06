"""Engine-neutral OCR page contracts; this module does not execute OCR."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
import re
from typing import Protocol


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ERROR_CODE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_MAX_IDENTITY_TEXT = 256
_MAX_REGION_VERTICES = 256


class OCRContractError(ValueError):
    """Contract failure with a stable code that never embeds document details."""

    def __init__(self, code: str) -> None:
        if type(code) is not str or not _ERROR_CODE.fullmatch(code):
            raise ValueError("ocr_contract_error_code_invalid")
        self.code = code
        super().__init__(code)


def _identity_text(value: object) -> bool:
    return (
        type(value) is str
        and bool(value.strip())
        and len(value) <= _MAX_IDENTITY_TEXT
        and all(ord(character) >= 32 and ord(character) != 127 for character in value)
    )


def _error_code(value: object) -> bool:
    return type(value) is str and _ERROR_CODE.fullmatch(value) is not None


def _finite_number(value: object) -> bool:
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, ValueError):
        return False


def _cross(first: tuple[float, float], second: tuple[float, float], third: tuple[float, float]) -> float:
    return ((second[0] - first[0]) * (third[1] - first[1])
            - (second[1] - first[1]) * (third[0] - first[0]))


def _on_segment(
    start: tuple[float, float], point: tuple[float, float], end: tuple[float, float]
) -> bool:
    return (min(start[0], end[0]) <= point[0] <= max(start[0], end[0])
            and min(start[1], end[1]) <= point[1] <= max(start[1], end[1]))


def _segments_intersect(
    first_start: tuple[float, float],
    first_end: tuple[float, float],
    second_start: tuple[float, float],
    second_end: tuple[float, float],
) -> bool:
    first_orientation = _cross(first_start, first_end, second_start)
    second_orientation = _cross(first_start, first_end, second_end)
    third_orientation = _cross(second_start, second_end, first_start)
    fourth_orientation = _cross(second_start, second_end, first_end)

    if (((first_orientation > 0 and second_orientation < 0)
         or (first_orientation < 0 and second_orientation > 0))
            and ((third_orientation > 0 and fourth_orientation < 0)
                 or (third_orientation < 0 and fourth_orientation > 0))):
        return True
    return (
        (first_orientation == 0 and _on_segment(first_start, second_start, first_end))
        or (second_orientation == 0 and _on_segment(first_start, second_end, first_end))
        or (third_orientation == 0 and _on_segment(second_start, first_start, second_end))
        or (fourth_orientation == 0 and _on_segment(second_start, first_end, second_end))
    )


@dataclass(frozen=True)
class EngineIdentity:
    """Declared engine, optional model, and runtime identities for one result."""

    engine_id: str
    engine_version: str
    model_id: str | None
    model_version: str | None
    runtime_id: str
    runtime_version: str

    def __post_init__(self) -> None:
        required = (self.engine_id, self.engine_version, self.runtime_id, self.runtime_version)
        if not all(_identity_text(value) for value in required):
            raise OCRContractError("ocr_engine_identity_invalid")
        if (self.model_id is None) != (self.model_version is None):
            raise OCRContractError("ocr_engine_identity_invalid")
        if self.model_id is not None and not all(
            _identity_text(value) for value in (self.model_id, self.model_version)
        ):
            raise OCRContractError("ocr_engine_identity_invalid")


@dataclass(frozen=True)
class PageProvenance:
    """Identity of an original document page, independent of rendered bytes."""

    source_sha256: str
    page_number: int

    def __post_init__(self) -> None:
        if type(self.source_sha256) is not str or not _SHA256.fullmatch(self.source_sha256):
            raise OCRContractError("ocr_source_hash_invalid")
        if type(self.page_number) is not int or self.page_number < 1:
            raise OCRContractError("ocr_page_number_invalid")


@dataclass(frozen=True)
class PageInput:
    """Already-rendered page bytes plus the caller-supplied source identity."""

    provenance: PageProvenance
    media_type: str
    image_bytes: bytes

    def __post_init__(self) -> None:
        if type(self.provenance) is not PageProvenance:
            raise OCRContractError("ocr_page_input_invalid")
        if not _identity_text(self.media_type) or type(self.image_bytes) is not bytes or not self.image_bytes:
            raise OCRContractError("ocr_page_input_invalid")


@dataclass(frozen=True)
class TextRegion:
    """Polygon in normalized page coordinates, where both axes span 0 through 1."""

    polygon: tuple[tuple[float, float], ...]

    def __post_init__(self) -> None:
        points = self.polygon
        if type(points) is not tuple or not 3 <= len(points) <= _MAX_REGION_VERTICES:
            raise OCRContractError("ocr_region_invalid")

        normalized: list[tuple[float, float]] = []
        for point in points:
            if type(point) is not tuple or len(point) != 2:
                raise OCRContractError("ocr_region_invalid")
            x, y = point
            if any(not _finite_number(value) for value in point):
                raise OCRContractError("ocr_region_invalid")
            if not 0 <= x <= 1 or not 0 <= y <= 1:
                raise OCRContractError("ocr_region_invalid")
            normalized.append((float(x), float(y)))

        if len(set(normalized)) < 3:
            raise OCRContractError("ocr_region_invalid")
        for first_index, first_start in enumerate(normalized):
            first_end = normalized[(first_index + 1) % len(normalized)]
            for second_index in range(first_index + 1, len(normalized)):
                second_end_index = (second_index + 1) % len(normalized)
                if second_index == (first_index + 1) % len(normalized) or second_end_index == first_index:
                    continue
                if _segments_intersect(
                    first_start,
                    first_end,
                    normalized[second_index],
                    normalized[second_end_index],
                ):
                    raise OCRContractError("ocr_region_invalid")
        area_twice = sum(
            normalized[index][0] * normalized[(index + 1) % len(normalized)][1]
            - normalized[(index + 1) % len(normalized)][0] * normalized[index][1]
            for index in range(len(normalized))
        )
        if not math.isfinite(area_twice) or area_twice == 0:
            raise OCRContractError("ocr_region_invalid")
        object.__setattr__(self, "polygon", tuple(normalized))


@dataclass(frozen=True)
class TextObservation:
    """Literal recognized text and optional confidence, without a confirmation state."""

    text: str
    region: TextRegion
    confidence: float | None = None

    def __post_init__(self) -> None:
        if type(self.text) is not str or not self.text.strip():
            raise OCRContractError("ocr_observation_invalid")
        if type(self.region) is not TextRegion:
            raise OCRContractError("ocr_observation_invalid")
        if self.confidence is not None:
            if (not _finite_number(self.confidence)
                    or not 0 <= self.confidence <= 1):
                raise OCRContractError("ocr_confidence_invalid")
            object.__setattr__(self, "confidence", float(self.confidence))


class PageResultStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass(frozen=True)
class PageOCRResult:
    """Page observations tied to their source, location, and declared runtime."""

    provenance: PageProvenance
    engine: EngineIdentity
    observations: tuple[TextObservation, ...]
    status: PageResultStatus = PageResultStatus.COMPLETE
    error_code: str | None = None

    def __post_init__(self) -> None:
        if type(self.provenance) is not PageProvenance or type(self.engine) is not EngineIdentity:
            raise OCRContractError("ocr_result_invalid")
        if type(self.observations) is not tuple or any(
            type(observation) is not TextObservation for observation in self.observations
        ):
            raise OCRContractError("ocr_result_invalid")
        if type(self.status) is not PageResultStatus:
            raise OCRContractError("ocr_result_invalid")
        if self.error_code is not None and not _error_code(self.error_code):
            raise OCRContractError("ocr_error_code_invalid")
        if self.status is PageResultStatus.FAILED:
            if self.observations or self.error_code is None:
                raise OCRContractError("ocr_failed_result_invalid")
        elif self.status is PageResultStatus.COMPLETE and self.error_code is not None:
            raise OCRContractError("ocr_result_invalid")


class OCREngine(Protocol):
    """Typing boundary only; implementations and runtime policy are supplied later."""

    @property
    def identity(self) -> EngineIdentity:
        """Return the exact declared identity for results produced by this engine."""

    def recognize_page(self, page: PageInput) -> PageOCRResult:
        """Recognize one already-rendered page; no implementation is provided here."""


def validate_page_result(
    page: PageInput,
    result: PageOCRResult,
    *,
    expected_engine: EngineIdentity,
) -> PageOCRResult:
    """Reject results detached from their input page or registered engine identity."""
    if (type(page) is not PageInput or type(result) is not PageOCRResult
            or type(expected_engine) is not EngineIdentity):
        raise OCRContractError("ocr_result_invalid")
    if result.provenance != page.provenance:
        raise OCRContractError("ocr_provenance_mismatch")
    if result.engine != expected_engine:
        raise OCRContractError("ocr_engine_identity_mismatch")
    return result


__all__ = [
    "EngineIdentity", "OCRContractError", "OCREngine", "PageInput", "PageOCRResult",
    "PageProvenance", "PageResultStatus", "TextObservation", "TextRegion", "validate_page_result",
]
