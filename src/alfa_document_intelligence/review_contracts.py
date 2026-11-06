"""In-memory, append-only human review records for OCR2 field candidates."""
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import json
import re
from typing import Any

from .extraction_contracts import (
    ExtractionContractError,
    FieldCandidate,
    validate_field_candidate,
)
from .ocr_contracts import PageOCRResult
from .taxonomy_binding import TaxonomyBindingError, validate_taxonomy_binding


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_STALE_EVIDENCE_ERRORS = frozenset({
    "extraction_provenance_mismatch",
    "extraction_observation_reference_invalid",
    "extraction_evidence_mismatch",
})


class ReviewContractError(ValueError):
    """Stable failure code without candidate text, paths, or identity details."""

    def __init__(self, code: str) -> None:
        if type(code) is not str or not _IDENTIFIER.fullmatch(code):
            raise ValueError("review_error_code_invalid")
        self.code = code
        super().__init__(code)


class ReviewAction(str, Enum):
    CONFIRM = "confirm"
    CORRECT = "correct"
    REJECT = "reject"
    DEFER = "defer"


class ReviewStatus(str, Enum):
    UNREVIEWED = "unreviewed"
    CURRENT = "current"
    STALE = "stale"


@dataclass(frozen=True)
class ReviewEvent:
    """One immutable human action bound to the candidate and taxonomy snapshot."""

    subject_id: str
    revision: int
    candidate_sha256: str
    taxonomy_schema_version: str
    taxonomy_version: int
    taxonomy_sha256: str
    action: ReviewAction
    reviewer_id: str
    reason_code: str
    occurred_at_utc: datetime
    selected_alternative_index: int | None = None
    corrected_value: str | None = None

    def __post_init__(self) -> None:
        if (type(self.subject_id) is not str or not _IDENTIFIER.fullmatch(self.subject_id)
                or type(self.revision) is not int or self.revision < 1
                or type(self.candidate_sha256) is not str or not _SHA256.fullmatch(self.candidate_sha256)
                or type(self.taxonomy_schema_version) is not str or not self.taxonomy_schema_version.strip()
                or type(self.taxonomy_version) is not int or self.taxonomy_version < 1
                or type(self.taxonomy_sha256) is not str or not _SHA256.fullmatch(self.taxonomy_sha256)
                or type(self.action) is not ReviewAction
                or type(self.reviewer_id) is not str or not _IDENTIFIER.fullmatch(self.reviewer_id)
                or type(self.reason_code) is not str or not _IDENTIFIER.fullmatch(self.reason_code)
                or type(self.occurred_at_utc) is not datetime
                or self.occurred_at_utc.tzinfo is None
                or self.occurred_at_utc.utcoffset() != timedelta(0)):
            raise ReviewContractError("review_event_invalid")
        if self.selected_alternative_index is not None and (
            type(self.selected_alternative_index) is not int or self.selected_alternative_index < 0
        ):
            raise ReviewContractError("review_event_invalid")
        if self.corrected_value is not None and (
            type(self.corrected_value) is not str or not self.corrected_value.strip()
        ):
            raise ReviewContractError("review_event_invalid")

        if self.action is ReviewAction.CORRECT:
            if self.corrected_value is None or self.selected_alternative_index is not None:
                raise ReviewContractError("review_event_invalid")
        elif self.action is ReviewAction.CONFIRM:
            if self.corrected_value is not None:
                raise ReviewContractError("review_event_invalid")
        elif self.selected_alternative_index is not None or self.corrected_value is not None:
            raise ReviewContractError("review_event_invalid")


@dataclass(frozen=True)
class ReviewLedger:
    """Immutable history and original candidate snapshot for one subject."""

    subject_id: str
    candidate_sha256: str
    taxonomy_schema_version: str
    taxonomy_version: int
    taxonomy_sha256: str
    source_candidate: FieldCandidate
    events: tuple[ReviewEvent, ...] = ()

    def __post_init__(self) -> None:
        if (type(self.subject_id) is not str or not _IDENTIFIER.fullmatch(self.subject_id)
                or type(self.candidate_sha256) is not str or not _SHA256.fullmatch(self.candidate_sha256)
                or type(self.taxonomy_schema_version) is not str or not self.taxonomy_schema_version.strip()
                or type(self.taxonomy_version) is not int or self.taxonomy_version < 1
                or type(self.taxonomy_sha256) is not str or not _SHA256.fullmatch(self.taxonomy_sha256)
                or type(self.source_candidate) is not FieldCandidate
                or type(self.events) is not tuple
                or any(type(event) is not ReviewEvent for event in self.events)):
            raise ReviewContractError("review_ledger_invalid")
        if (self.source_candidate.taxonomy_schema_version != self.taxonomy_schema_version
                or self.source_candidate.taxonomy_version != self.taxonomy_version
                or self.source_candidate.taxonomy_sha256 != self.taxonomy_sha256
                or _candidate_sha256(self.source_candidate) != self.candidate_sha256):
            raise ReviewContractError("review_ledger_invalid")
        for expected_revision, event in enumerate(self.events, start=1):
            if (event.revision != expected_revision or event.subject_id != self.subject_id
                    or event.candidate_sha256 != self.candidate_sha256
                    or event.taxonomy_schema_version != self.taxonomy_schema_version
                    or event.taxonomy_version != self.taxonomy_version
                    or event.taxonomy_sha256 != self.taxonomy_sha256):
                raise ReviewContractError("review_ledger_invalid")


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _json_value(getattr(value, field.name)) for field in fields(value)}
    if type(value) is tuple:
        return [_json_value(item) for item in value]
    if value is None or type(value) in (str, int, float, bool):
        return value
    raise TypeError("review_candidate_serialization_invalid")


def _candidate_sha256(candidate: FieldCandidate) -> str:
    try:
        canonical = json.dumps(
            _json_value(candidate), ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        )
        encoded = canonical.encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as error:
        raise ReviewContractError("review_candidate_invalid") from error
    return hashlib.sha256(encoded).hexdigest()


def _candidate_identity(
    candidate: FieldCandidate,
    binding: dict[str, Any],
    page_results: tuple[PageOCRResult, ...],
) -> tuple[str, int, str, str]:
    if type(candidate) is not FieldCandidate:
        raise ReviewContractError("review_candidate_invalid")
    try:
        catalog, digest = validate_taxonomy_binding(binding)
        validate_field_candidate(candidate, binding, page_results)
    except (ExtractionContractError, TaxonomyBindingError, TypeError, ValueError) as error:
        raise ReviewContractError("review_candidate_invalid") from error
    return catalog["schema_version"], catalog["version"], digest, _candidate_sha256(candidate)


def start_review_ledger(
    subject_id: str,
    candidate: FieldCandidate,
    binding: dict[str, Any],
    page_results: tuple[PageOCRResult, ...],
) -> ReviewLedger:
    """Start an empty ledger after validating the exact candidate evidence."""
    if type(subject_id) is not str or not _IDENTIFIER.fullmatch(subject_id):
        raise ReviewContractError("review_subject_invalid")
    schema_version, version, taxonomy_digest, candidate_digest = _candidate_identity(
        candidate, binding, page_results,
    )
    return ReviewLedger(
        subject_id, candidate_digest, schema_version, version, taxonomy_digest, candidate,
    )


def append_review_event(
    ledger: ReviewLedger,
    candidate: FieldCandidate,
    binding: dict[str, Any],
    page_results: tuple[PageOCRResult, ...],
    *,
    expected_revision: int,
    action: ReviewAction,
    reviewer_id: str,
    reason_code: str,
    occurred_at_utc: datetime,
    selected_alternative_index: int | None = None,
    corrected_value: str | None = None,
) -> ReviewLedger:
    """Append a new event if the caller's revision and candidate snapshot are current."""
    if type(ledger) is not ReviewLedger:
        raise ReviewContractError("review_ledger_invalid")
    if type(expected_revision) is not int or expected_revision != len(ledger.events):
        raise ReviewContractError("review_revision_conflict")
    schema_version, version, taxonomy_digest, candidate_digest = _candidate_identity(
        candidate, binding, page_results,
    )
    if (schema_version != ledger.taxonomy_schema_version or version != ledger.taxonomy_version
            or taxonomy_digest != ledger.taxonomy_sha256):
        raise ReviewContractError("review_taxonomy_stale")
    if candidate_digest != ledger.candidate_sha256:
        raise ReviewContractError("review_candidate_stale")

    if type(action) is not ReviewAction:
        raise ReviewContractError("review_event_invalid")
    if action is ReviewAction.CONFIRM:
        alternative_count = len(candidate.alternatives)
        if (alternative_count == 0 and selected_alternative_index is not None
                or alternative_count > 0 and (
                    type(selected_alternative_index) is not int
                    or not 0 <= selected_alternative_index < alternative_count
                )):
            raise ReviewContractError("review_selection_invalid")
    elif selected_alternative_index is not None:
        raise ReviewContractError("review_event_invalid")

    event = ReviewEvent(
        subject_id=ledger.subject_id,
        revision=len(ledger.events) + 1,
        candidate_sha256=candidate_digest,
        taxonomy_schema_version=schema_version,
        taxonomy_version=version,
        taxonomy_sha256=taxonomy_digest,
        action=action,
        reviewer_id=reviewer_id,
        reason_code=reason_code,
        occurred_at_utc=occurred_at_utc,
        selected_alternative_index=selected_alternative_index,
        corrected_value=corrected_value,
    )
    return ReviewLedger(
        ledger.subject_id, candidate_digest, schema_version, version, taxonomy_digest,
        ledger.source_candidate, ledger.events + (event,),
    )


def review_status(
    ledger: ReviewLedger,
    candidate: FieldCandidate,
    binding: dict[str, Any],
    page_results: tuple[PageOCRResult, ...],
) -> ReviewStatus:
    """Return stale when the current candidate or exact taxonomy has changed."""
    if type(ledger) is not ReviewLedger:
        raise ReviewContractError("review_ledger_invalid")
    try:
        catalog, digest = validate_taxonomy_binding(binding)
    except (TaxonomyBindingError, TypeError, ValueError) as error:
        raise ReviewContractError("review_taxonomy_invalid") from error
    if (catalog["schema_version"] != ledger.taxonomy_schema_version
            or catalog["version"] != ledger.taxonomy_version or digest != ledger.taxonomy_sha256):
        return ReviewStatus.STALE

    try:
        schema_version, version, taxonomy_digest, candidate_digest = _candidate_identity(
            candidate, binding, page_results,
        )
    except ReviewContractError as error:
        cause = error.__cause__
        if (type(cause) is ExtractionContractError
                and cause.code in _STALE_EVIDENCE_ERRORS):
            return ReviewStatus.STALE
        raise
    if (schema_version != ledger.taxonomy_schema_version or version != ledger.taxonomy_version
            or taxonomy_digest != ledger.taxonomy_sha256 or candidate_digest != ledger.candidate_sha256):
        return ReviewStatus.STALE
    return ReviewStatus.CURRENT if ledger.events else ReviewStatus.UNREVIEWED


def derived_result_is_current(
    ledger: ReviewLedger,
    candidate: FieldCandidate,
    binding: dict[str, Any],
    page_results: tuple[PageOCRResult, ...],
    *,
    candidate_sha256: str,
    taxonomy_sha256: str,
    review_revision: int,
) -> bool:
    """Check whether a cached result matches candidate, taxonomy, and review revision."""
    if (type(candidate_sha256) is not str or not _SHA256.fullmatch(candidate_sha256)
            or type(taxonomy_sha256) is not str or not _SHA256.fullmatch(taxonomy_sha256)
            or type(review_revision) is not int or review_revision < 0):
        raise ReviewContractError("review_result_identity_invalid")
    if review_status(ledger, candidate, binding, page_results) is ReviewStatus.STALE:
        return False
    return (
        candidate_sha256 == ledger.candidate_sha256
        and taxonomy_sha256 == ledger.taxonomy_sha256
        and review_revision == len(ledger.events)
    )


__all__ = [
    "ReviewAction", "ReviewContractError", "ReviewEvent", "ReviewLedger", "ReviewStatus",
    "append_review_event", "derived_result_is_current", "review_status", "start_review_ledger",
]
