"""Taxonomy-bound structured candidates without extraction or review behavior."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Any

from .ocr_contracts import PageOCRResult, PageProvenance, TextRegion
from .taxonomy_binding import TaxonomyBindingError, validate_taxonomy_binding


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{1,63}$")


class ExtractionContractError(ValueError):
    """Stable error code without source content, paths, or exception details."""

    def __init__(self, code: str) -> None:
        if type(code) is not str or not _IDENTIFIER.fullmatch(code):
            raise ValueError("extraction_error_code_invalid")
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class SourceRegionReference:
    """A region on a source page with no corresponding readable OCR observation."""

    provenance: PageProvenance
    region: TextRegion

    def __post_init__(self) -> None:
        if type(self.provenance) is not PageProvenance or type(self.region) is not TextRegion:
            raise ExtractionContractError("extraction_source_reference_invalid")


@dataclass(frozen=True)
class OCRObservationReference:
    """Stable index and geometry for one observation within a page result."""

    provenance: PageProvenance
    observation_index: int
    region: TextRegion

    def __post_init__(self) -> None:
        if (type(self.provenance) is not PageProvenance
                or type(self.observation_index) is not int or self.observation_index < 0
                or type(self.region) is not TextRegion):
            raise ExtractionContractError("extraction_observation_reference_invalid")


class CandidateState(str, Enum):
    PROPOSED = "proposed"
    UNCERTAIN = "uncertain"
    MISSING = "missing"
    UNREADABLE = "unreadable"
    REJECTED = "rejected"


@dataclass(frozen=True)
class CandidateAlternative:
    """One literal interpretation; normalized text is opaque and optional."""

    literal_segments: tuple[str, ...]
    normalized_value: str | None
    evidence: tuple[OCRObservationReference, ...]

    def __post_init__(self) -> None:
        if (type(self.literal_segments) is not tuple or not self.literal_segments
                or any(type(text) is not str or not text.strip() for text in self.literal_segments)
                or type(self.evidence) is not tuple or len(self.evidence) != len(self.literal_segments)
                or any(type(reference) is not OCRObservationReference for reference in self.evidence)):
            raise ExtractionContractError("extraction_candidate_alternative_invalid")
        if self.normalized_value is not None and (
            type(self.normalized_value) is not str or not self.normalized_value.strip()
        ):
            raise ExtractionContractError("extraction_normalized_value_invalid")


@dataclass(frozen=True)
class FieldCandidate:
    """A proposed, uncertain, absent, unreadable, or rejected taxonomy field value."""

    taxonomy_schema_version: str
    taxonomy_version: int
    taxonomy_sha256: str
    type_id: str
    field_id: str
    state: CandidateState
    alternatives: tuple[CandidateAlternative, ...]
    unreadable_region: SourceRegionReference | None = None

    def __post_init__(self) -> None:
        if (type(self.taxonomy_schema_version) is not str or not self.taxonomy_schema_version.strip()
                or type(self.taxonomy_version) is not int or self.taxonomy_version < 1
                or type(self.taxonomy_sha256) is not str or not _SHA256.fullmatch(self.taxonomy_sha256)
                or type(self.type_id) is not str or not _IDENTIFIER.fullmatch(self.type_id)
                or type(self.field_id) is not str or not _IDENTIFIER.fullmatch(self.field_id)
                or type(self.state) is not CandidateState
                or type(self.alternatives) is not tuple
                or any(type(item) is not CandidateAlternative for item in self.alternatives)
                or (self.unreadable_region is not None
                    and type(self.unreadable_region) is not SourceRegionReference)):
            raise ExtractionContractError("extraction_candidate_invalid")

        count = len(self.alternatives)
        if self.state is CandidateState.PROPOSED and (count != 1 or self.unreadable_region is not None):
            raise ExtractionContractError("extraction_candidate_state_invalid")
        if self.state is CandidateState.UNCERTAIN and (count < 1 or self.unreadable_region is not None):
            raise ExtractionContractError("extraction_candidate_state_invalid")
        if self.state is CandidateState.MISSING and (count != 0 or self.unreadable_region is not None):
            raise ExtractionContractError("extraction_candidate_state_invalid")
        if self.state is CandidateState.UNREADABLE and (count != 0 or self.unreadable_region is None):
            raise ExtractionContractError("extraction_candidate_state_invalid")
        if self.state is CandidateState.REJECTED and (count < 1 or self.unreadable_region is not None):
            raise ExtractionContractError("extraction_candidate_state_invalid")


def validate_field_candidate(
    candidate: FieldCandidate,
    binding: dict[str, Any],
    page_results: tuple[PageOCRResult, ...],
) -> FieldCandidate:
    """Validate candidate identity and exact page-observation references."""
    if type(candidate) is not FieldCandidate:
        raise ExtractionContractError("extraction_candidate_invalid")
    try:
        catalog, digest = validate_taxonomy_binding(binding)
    except (TaxonomyBindingError, TypeError, ValueError) as error:
        raise ExtractionContractError("extraction_taxonomy_binding_invalid") from error

    if (candidate.taxonomy_schema_version != binding["catalog_schema_version"]
            or candidate.taxonomy_version != binding["catalog_version"]
            or candidate.taxonomy_sha256 != digest):
        raise ExtractionContractError("extraction_taxonomy_mismatch")

    document_type = next((item for item in catalog["types"] if item["id"] == candidate.type_id), None)
    field = next((item for item in document_type["fields"] if item["id"] == candidate.field_id), None) \
        if document_type is not None else None
    if (document_type is None or document_type["enabled"] is not True
            or document_type["extraction_mode"] != "built_in" or field is None
            or field["extraction_mode"] != "built_in"):
        raise ExtractionContractError("extraction_field_not_eligible")

    if type(page_results) is not tuple or any(type(result) is not PageOCRResult for result in page_results):
        raise ExtractionContractError("extraction_page_results_invalid")
    pages: dict[PageProvenance, PageOCRResult] = {}
    for result in page_results:
        if result.provenance in pages:
            raise ExtractionContractError("extraction_page_ambiguous")
        pages[result.provenance] = result

    for alternative in candidate.alternatives:
        for literal, reference in zip(alternative.literal_segments, alternative.evidence, strict=True):
            result = pages.get(reference.provenance)
            if result is None:
                raise ExtractionContractError("extraction_provenance_mismatch")
            if reference.observation_index >= len(result.observations):
                raise ExtractionContractError("extraction_observation_reference_invalid")
            observation = result.observations[reference.observation_index]
            if observation.region != reference.region or observation.text != literal:
                raise ExtractionContractError("extraction_evidence_mismatch")

    if candidate.unreadable_region is not None:
        if candidate.unreadable_region.provenance not in pages:
            raise ExtractionContractError("extraction_provenance_mismatch")
    return candidate


__all__ = [
    "CandidateAlternative", "CandidateState", "ExtractionContractError", "FieldCandidate",
    "OCRObservationReference", "SourceRegionReference", "validate_field_candidate",
]
