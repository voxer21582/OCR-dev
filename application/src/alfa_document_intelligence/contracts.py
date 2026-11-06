"""Cross-record invariants for document records; JSON Schema remains the structural contract."""
from __future__ import annotations

import re
from typing import Any

_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
_CANDIDATE_STATUSES = {"observed", "uncertain", "unreadable", "absent", "not_applicable", "rejected"}
_DOCUMENT_FAMILIES = {"invoice", "fiscal_receipt", "parking_receipt", "hotel_document", "expense_report", "pos_slip", "other", "unknown"}
_STAGE_NAMES = {"ingestion", "ocr", "semantic_extraction", "document_validation", "administrative_verification"}

def _validate_evidence_items(
    evidence: list[Any],
    path: str,
    source_hash: str | None,
    page_numbers: set[int],
    issues: list[str],
) -> None:
    for evidence_i, item in enumerate(evidence):
        evidence_path = f"{path}[{evidence_i}]"
        if not isinstance(item, dict):
            issues.append(f"{evidence_path}: expected object")
            continue
        if source_hash is None or item.get("source_sha256") != source_hash:
            issues.append(f"{evidence_path}.source_sha256: must bind to this document")
        page_number = item.get("page_number")
        if not isinstance(page_number, int) or isinstance(page_number, bool) or page_number not in page_numbers:
            issues.append(f"{evidence_path}.page_number: must reference an inventoried page")
        if not any(key in item for key in ("region", "text_span", "token_ids")):
            issues.append(f"{evidence_path}: requires region, text_span, or token_ids")



def validate_document_record(record: dict[str, Any]) -> list[str]:
    """Return deterministic invariant violations without mutating the supplied record."""
    issues: list[str] = []
    if not isinstance(record, dict):
        return ["record: expected object"]
    if record.get("schema_version") != "0.1.0":
        issues.append("schema_version: expected 0.1.0")

    source = record.get("source")
    source_hash = source.get("sha256") if isinstance(source, dict) else None
    if not isinstance(source_hash, str) or not _SHA256.fullmatch(source_hash):
        issues.append("source.sha256: expected 64 hexadecimal characters")
        source_hash = None

    pages = record.get("pages")
    page_numbers: set[int] = set()
    if not isinstance(pages, list):
        issues.append("pages: expected array")
        pages = []
    for i, page in enumerate(pages):
        number = page.get("page_number") if isinstance(page, dict) else None
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            issues.append(f"pages[{i}].page_number: expected positive integer")
        elif number in page_numbers:
            issues.append(f"pages[{i}].page_number: duplicate page number")
        else:
            page_numbers.add(number)

    processing = record.get("processing")
    if not isinstance(processing, dict) or set(processing) != _STAGE_NAMES:
        issues.append("processing: expected exactly the five independent stages")

    family = record.get("document_family")
    if "document_family" in record and family not in _DOCUMENT_FAMILIES:
        issues.append("document_family: unsupported family")
    fiscal = record.get("fiscal_document_state")
    if not isinstance(fiscal, dict):
        issues.append("fiscal_document_state: expected object")
    else:
        fiscal_status = fiscal.get("status")
        fiscal_evidence = fiscal.get("evidence")
        if not isinstance(fiscal_evidence, list):
            issues.append("fiscal_document_state.evidence: expected array")
            fiscal_evidence = []
        if fiscal_status in {"fiscal_document", "payment_evidence", "not_fiscal", "uncertain"} and not fiscal_evidence:
            issues.append(f"fiscal_document_state.evidence: required for {fiscal_status} classification")
        for evidence_i, item in enumerate(fiscal_evidence):
            path = f"fiscal_document_state.evidence[{evidence_i}]"
            if not isinstance(item, dict):
                issues.append(f"{path}: expected object")
                continue
            if source_hash is None or item.get("source_sha256") != source_hash:
                issues.append(f"{path}.source_sha256: must bind to this document")
            page_number = item.get("page_number")
            if not isinstance(page_number, int) or isinstance(page_number, bool) or page_number not in page_numbers:
                issues.append(f"{path}.page_number: must reference an inventoried page")
            if not any(key in item for key in ("region", "text_span", "token_ids")):
                issues.append(f"{path}: requires region, text_span, or token_ids")
    if family == "pos_slip" and isinstance(fiscal, dict) and fiscal.get("status") == "fiscal_document":
        issues.append("fiscal_document_state: a POS slip alone cannot establish fiscal-document status")

    fields = record.get("fields")
    if not isinstance(fields, dict):
        issues.append("fields: expected object")
        fields = {}
    for field_name, candidate in fields.items():
        if not isinstance(candidate, dict):
            issues.append(f"fields.{field_name}: expected candidate object")
            continue
        status = candidate.get("status")
        if status not in _CANDIDATE_STATUSES:
            issues.append(f"fields.{field_name}.status: unsupported status")
        value = candidate.get("value")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            issues.append(f"fields.{field_name}.value: JSON numbers are forbidden; use decimal strings")
        evidence = candidate.get("evidence")
        if not isinstance(evidence, list):
            issues.append(f"fields.{field_name}.evidence: expected array")
            evidence = []
        alternatives = candidate.get("alternatives")
        if not isinstance(alternatives, list):
            issues.append(f"fields.{field_name}.alternatives: expected array")
            alternatives = []
        if status in {"observed", "uncertain", "unreadable", "rejected"} and not evidence:
            issues.append(f"fields.{field_name}.evidence: required for {status} candidate")
        if status == "observed" and value is None:
            issues.append(f"fields.{field_name}.value: observed candidate requires a value")
        if status in {"unreadable", "absent", "not_applicable"} and value is not None:
            issues.append(f"fields.{field_name}.value: {status} candidate must have null value")
        if status == "uncertain" and value is None and not alternatives:
            issues.append(f"fields.{field_name}.alternatives: required when uncertain value is null")
        normalization = candidate.get("normalization")
        if isinstance(normalization, dict) and normalization.get("normalized_value") != value:
            issues.append(f"fields.{field_name}.normalization: normalized_value must equal candidate value")
        _validate_evidence_items(evidence, f"fields.{field_name}.evidence", source_hash, page_numbers, issues)
        for alt_i, alternative in enumerate(alternatives):
            path = f"fields.{field_name}.alternatives[{alt_i}]"
            if not isinstance(alternative, dict):
                issues.append(f"{path}: expected object")
                continue
            alt_status = alternative.get("status")
            if alt_status not in {"observed", "uncertain", "unreadable", "rejected"}:
                issues.append(f"{path}.status: unsupported alternative status")
            alt_value = alternative.get("value")
            if isinstance(alt_value, (int, float)) and not isinstance(alt_value, bool):
                issues.append(f"{path}.value: JSON numbers are forbidden; use decimal strings")
            if alt_status == "observed" and alt_value is None:
                issues.append(f"{path}.value: observed alternative requires a value")
            if alt_status == "unreadable" and alt_value is not None:
                issues.append(f"{path}.value: unreadable alternative must have null value")
            alt_evidence = alternative.get("evidence")
            if not isinstance(alt_evidence, list) or not alt_evidence:
                issues.append(f"{path}.evidence: at least one evidence reference is required")
                alt_evidence = alt_evidence if isinstance(alt_evidence, list) else []
            _validate_evidence_items(
                alt_evidence, f"{path}.evidence", source_hash, page_numbers, issues
            )
            alt_normalization = alternative.get("normalization")
            if isinstance(alt_normalization, dict) and alt_normalization.get("normalized_value") != alt_value:
                issues.append(f"{path}.normalization: normalized_value must equal alternative value")

    return issues