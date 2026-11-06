"""Deterministic structural validation for taxonomy-bound field candidates."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from .extraction_contracts import (
    CandidateState,
    ExtractionContractError,
    FieldCandidate,
    validate_field_candidate,
)
from .ocr_contracts import PageOCRResult
from .taxonomy_binding import TaxonomyBindingError, validate_taxonomy_binding


_ERROR_CODE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_STATE_FINDING = {
    CandidateState.MISSING: "field_missing",
    CandidateState.UNCERTAIN: "field_uncertain",
    CandidateState.UNREADABLE: "field_unreadable",
    CandidateState.REJECTED: "field_rejected",
}


class ValidationContractError(ValueError):
    """Stable error code that excludes catalog contents and candidate text."""

    def __init__(self, code: str) -> None:
        if type(code) is not str or not _ERROR_CODE.fullmatch(code):
            raise ValueError("validation_error_code_invalid")
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class FieldValidationEntry:
    """Candidate states for one eligible field, preserving duplicate records."""

    field_id: str
    states: tuple[CandidateState, ...]


@dataclass(frozen=True)
class ValidationFinding:
    """A content-free finding identified by stable code and taxonomy field."""

    code: str
    type_id: str
    field_id: str


@dataclass(frozen=True)
class ValidationReport:
    """Immutable structural report tied to one exact taxonomy snapshot."""

    taxonomy_schema_version: str
    taxonomy_version: int
    taxonomy_sha256: str
    type_id: str
    field_entries: tuple[FieldValidationEntry, ...]
    findings: tuple[ValidationFinding, ...]


def validate_document_fields(
    binding: dict[str, Any],
    type_id: str,
    candidates: tuple[FieldCandidate, ...],
    page_results: tuple[PageOCRResult, ...],
) -> ValidationReport:
    """Report structural presence and ambiguity without interpreting candidate values."""
    try:
        catalog, digest = validate_taxonomy_binding(binding)
    except (TaxonomyBindingError, TypeError, ValueError) as error:
        raise ValidationContractError("validation_taxonomy_binding_invalid") from error

    if type(type_id) is not str:
        raise ValidationContractError("validation_type_not_eligible")
    document_type = next((item for item in catalog["types"] if item["id"] == type_id), None)
    if (document_type is None or document_type["enabled"] is not True
            or document_type["extraction_mode"] != "built_in"
            or document_type["role"] in {"unknown", "custom_manual"}):
        raise ValidationContractError("validation_type_not_eligible")
    eligible_fields = {
        field["id"]: field for field in document_type["fields"]
        if field["extraction_mode"] == "built_in"
    }

    if type(candidates) is not tuple or any(type(item) is not FieldCandidate for item in candidates):
        raise ValidationContractError("validation_candidates_invalid")
    if type(page_results) is not tuple or any(type(item) is not PageOCRResult for item in page_results):
        raise ValidationContractError("validation_page_results_invalid")

    grouped: dict[str, list[CandidateState]] = {field_id: [] for field_id in eligible_fields}
    try:
        for item in candidates:
            if item.type_id != type_id or item.field_id not in eligible_fields:
                raise ExtractionContractError("extraction_field_not_eligible")
            validate_field_candidate(item, binding, page_results)
            grouped[item.field_id].append(item.state)
    except (ExtractionContractError, TaxonomyBindingError, TypeError, ValueError) as error:
        raise ValidationContractError("validation_candidate_invalid") from error

    entries: list[FieldValidationEntry] = []
    findings: list[ValidationFinding] = []
    for field_id in sorted(eligible_fields):
        field = eligible_fields[field_id]
        states = tuple(sorted(grouped[field_id], key=lambda state: state.value))
        entries.append(FieldValidationEntry(field_id, states))
        state_codes = {_STATE_FINDING[state] for state in states if state in _STATE_FINDING}
        findings.extend(ValidationFinding(code, type_id, field_id) for code in state_codes)
        if len(states) > 1:
            findings.append(ValidationFinding("field_candidate_conflict", type_id, field_id))
        if field["required"] is True and (len(states) != 1 or states[0] is not CandidateState.PROPOSED):
            findings.append(ValidationFinding("required_field_missing", type_id, field_id))

    return ValidationReport(
        binding["catalog_schema_version"], binding["catalog_version"], digest, type_id,
        tuple(entries), tuple(sorted(findings, key=lambda item: (item.field_id, item.code))),
    )


__all__ = [
    "FieldValidationEntry", "ValidationContractError", "ValidationFinding", "ValidationReport",
    "validate_document_fields",
]
