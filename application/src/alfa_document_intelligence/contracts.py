"""Cross-record invariants for document records; JSON Schema remains the structural contract."""
from __future__ import annotations

from datetime import date
import re
from typing import Any

from .document_family_catalog import catalog_from_snapshots, validate_family_snapshot

_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
_CANDIDATE_STATUSES = {"observed", "uncertain", "unreadable", "absent", "not_applicable", "rejected"}
_DOCUMENT_FAMILIES = {"invoice", "fiscal_receipt", "parking_receipt", "hotel_document", "expense_report", "pos_slip", "other", "unknown"}
_CUSTOM_FAMILY_ID = re.compile(r"^custom_[a-z][a-z0-9_]{1,24}$")
_CUSTOM_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CUSTOM_AMOUNT = re.compile(r"^-?(?:0|[1-9][0-9]*)\.[0-9]{2}$")
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



def _validate_custom_value(
    value: Any, field_type: str, path: str, issues: list[str]
) -> None:
    if value is None:
        return
    if field_type in {"text", "identifier"}:
        if not isinstance(value, str):
            issues.append(f"{path}: custom {field_type} value must be text")
        return
    if field_type == "date":
        if not isinstance(value, str) or not _CUSTOM_ISO_DATE.fullmatch(value):
            issues.append(f"{path}: custom date value must be a valid ISO date")
            return
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            issues.append(f"{path}: custom date value must be a valid ISO date")
            return
        if parsed.isoformat() != value:
            issues.append(f"{path}: custom date value must be a valid ISO date")
        return
    if field_type == "amount" and (not isinstance(value, str) or not _CUSTOM_AMOUNT.fullmatch(value)):
        issues.append(f"{path}: custom amount value must be a canonical decimal string with two fractional digits")


def validate_document_record(record: dict[str, Any]) -> list[str]:
    """Return deterministic invariant violations without mutating the supplied record."""
    issues: list[str] = []
    if not isinstance(record, dict):
        return ["record: expected object"]
    schema_version = record.get("schema_version")
    if schema_version not in ("0.1.0", "0.2.0", "0.3.0"):
        issues.append("schema_version: expected 0.1.0, 0.2.0, or 0.3.0")

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
    is_custom_family = isinstance(family, str) and bool(_CUSTOM_FAMILY_ID.fullmatch(family))
    if "document_family" in record and family not in _DOCUMENT_FAMILIES and not is_custom_family:
        issues.append("document_family: unsupported family")
    definitions = record.get("document_family_definitions", [])
    if not isinstance(definitions, list) or len(definitions) > 25:
        issues.append("document_family_definitions: expected at most 25 snapshots")
        definitions = []
    family_snapshots: dict[str, dict[str, Any]] = {}
    snapshot_field_names: set[str] = set()
    snapshot_field_types: dict[str, set[tuple[str, str]]] = {}
    snapshot_family_ids: set[str] = set()
    for index, snapshot in enumerate(definitions):
        snapshot_issues = validate_family_snapshot(snapshot)
        issues.extend(snapshot_issues)
        if isinstance(snapshot, dict) and isinstance(snapshot.get("family"), dict):
            snapshot_id = snapshot["family"].get("id")
            if isinstance(snapshot_id, str):
                if snapshot_id in family_snapshots:
                    issues.append("document_family_definitions: duplicate family snapshot")
                family_snapshots[snapshot_id] = snapshot
                snapshot_family_ids.add(snapshot_id)
                if not snapshot_issues:
                    for field in snapshot["family"].get("fields", []):
                        field_name = f"{snapshot_id}_{field['id']}"
                        snapshot_field_names.add(field_name)
                        snapshot_field_types.setdefault(field_name, set()).add(
                            (snapshot_id, field.get("type", "text"))
                        )
    if family_snapshots:
        try:
            catalog_from_snapshots(family_snapshots.values())
        except ValueError:
            issues.append("document_family_definitions: snapshots are mutually ambiguous")
    snapshot_versions = {
        snapshot.get("catalog_version")
        for snapshot in definitions
        if isinstance(snapshot, dict) and snapshot.get("catalog_version") in ("1", "2")
    }
    if len(snapshot_versions) > 1:
        issues.append("document_family_definitions: snapshots use mixed catalog versions")
    custom_candidate_ids: set[str] = set()
    fields_for_family = record.get("fields")
    if isinstance(fields_for_family, dict):
        proposal = fields_for_family.get("document_family_candidates")
        alternatives = proposal.get("alternatives") if isinstance(proposal, dict) else None
        selected = proposal.get("value") if isinstance(proposal, dict) else None
        if isinstance(selected, str) and _CUSTOM_FAMILY_ID.fullmatch(selected):
            custom_candidate_ids.add(selected)
        if isinstance(alternatives, list):
            custom_candidate_ids.update({
                alternative.get("value") for alternative in alternatives
                if isinstance(alternative, dict)
                and isinstance(alternative.get("value"), str)
                and _CUSTOM_FAMILY_ID.fullmatch(alternative["value"])
            })
    if is_custom_family:
        custom_candidate_ids.add(family)
    if schema_version == "0.1.0" and (custom_candidate_ids or "document_family_definitions" in record):
        issues.append("document_family_definitions: custom families require schema 0.2.0")
    if schema_version == "0.2.0" and not definitions:
        issues.append("document_family_definitions: schema 0.2.0 requires a snapshot")
    if schema_version == "0.3.0" and custom_candidate_ids and not definitions:
        issues.append("document_family_definitions: custom family candidates require a snapshot")
    for custom_id in custom_candidate_ids:
        if custom_id not in family_snapshots:
            issues.append("document_family_definitions: custom family candidate requires its snapshot")
    if any(custom_id not in _DOCUMENT_FAMILIES and custom_id not in family_snapshots for custom_id in custom_candidate_ids):
        issues.append("document_family_definitions: custom family does not match a valid snapshot")
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

    expense_lines = record.get("expense_lines")
    if schema_version == "0.3.0":
        semantic_stage = processing.get("semantic_extraction") if isinstance(processing, dict) else None
        if family == "expense_report" and isinstance(semantic_stage, dict) and semantic_stage.get("status") == "completed" and "expense_lines" not in record:
            issues.append("expense_lines: completed expense-report analysis requires line proposals")
        if expense_lines is not None:
            from .expense_line_extraction import validate_expense_lines
            issues.extend(validate_expense_lines(expense_lines, source_hash or "", page_numbers))
    elif expense_lines is not None:
        issues.append("expense_lines: requires document schema 0.3.0")

    fields = record.get("fields")
    if not isinstance(fields, dict):
        issues.append("fields: expected object")
        fields = {}
    for field_name, candidate in fields.items():
        if isinstance(field_name, str) and field_name.startswith("custom_"):
            matching_families = {
                family_id for family_id in snapshot_family_ids
                if field_name.startswith(f"{family_id}_")
            }
            if not matching_families:
                issues.append(
                    f"fields.{field_name}: custom field requires a matching family snapshot"
                )
            elif field_name not in snapshot_field_names:
                issues.append(
                    f"fields.{field_name}: custom field is not declared by its family snapshot"
                )
            elif len(snapshot_field_types.get(field_name, set())) > 1:
                issues.append(
                    f"fields.{field_name}: custom field identifier is ambiguous across family snapshots"
                )
        if not isinstance(candidate, dict):
            issues.append(f"fields.{field_name}: expected candidate object")
            continue
        status = candidate.get("status")
        if status not in _CANDIDATE_STATUSES:
            issues.append(f"fields.{field_name}.status: unsupported status")
        value = candidate.get("value")
        custom_field_definitions = snapshot_field_types.get(field_name) if isinstance(field_name, str) else None
        custom_field_type = next(iter(custom_field_definitions))[1] if custom_field_definitions and len(custom_field_definitions) == 1 else None
        if custom_field_type is not None:
            _validate_custom_value(value, custom_field_type, f"fields.{field_name}.value", issues)
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
            if custom_field_type is not None:
                _validate_custom_value(
                    alt_value, custom_field_type, f"{path}.value", issues
                )
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
