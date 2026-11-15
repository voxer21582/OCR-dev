"""Local serialization helpers for validated document intelligence records.

These functions serialize metadata only. They never read or include source-file
bytes and never write files or transmit exported content.
"""
from __future__ import annotations

import csv
import io
import json
from typing import Any

from .field_status import failed_rules_by_field, goal_status
from .contracts import validate_document_record
from .review_ledger import ReviewRejected, verify_review_ledger

CSV_EXPORT_VERSION = "ocr2-document-csv-v3"
CSV_COLUMNS = (
    "export_format_version",
    "document_id",
    "schema_version",
    "document_family",
    "source_sha256",
    "source_filename_json",
    "field_name",
    "goal_status",
    "goal_status_reason",
    "candidate_json",
    "review_events_json",
)
_REQUIRED_RECORD_PROPERTIES = (
    "schema_version",
    "document_id",
    "source",
    "document_family",
    "language",
    "fiscal_document_state",
    "pages",
    "processing",
    "fields",
    "validation_findings",
    "review",
    "administrative_verification",
)


class ExportValidationError(ValueError):
    """The record does not satisfy the document contract and cannot be exported."""

    def __init__(self, issues: list[str]) -> None:
        self.issues = tuple(issues)
        super().__init__("document record is invalid: " + "; ".join(issues))


def _validated_record(record: dict[str, Any]) -> dict[str, Any]:
    issues = validate_document_record(record)
    if isinstance(record, dict):
        missing = [key for key in _REQUIRED_RECORD_PROPERTIES if key not in record]
        if missing:
            issues.append("record: missing required properties: " + ", ".join(missing))
    if not issues:
        try:
            verify_review_ledger(record)
        except ReviewRejected:
            issues.append("review: invalid or tampered ledger")
    if issues:
        raise ExportValidationError(issues)
    return record


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def export_document_json(record: dict[str, Any]) -> str:
    """Return a complete, deterministic JSON serialization of one valid record.

    The record remains in its schema-defined shape so it can be validated and
    consumed by existing contract-aware tools. The caller controls where it is
    saved; callers must treat the result as sensitive local document data.
    """
    return json.dumps(
        _validated_record(record), ensure_ascii=True, sort_keys=True, indent=2
    ) + "\n"


def _goal_columns(candidate: Any, failed: frozenset[str]) -> dict[str, str]:
    if candidate is None:
        return {"goal_status": "", "goal_status_reason": ""}
    status, reason = goal_status(candidate, failed_rule_ids=failed)
    return {"goal_status": status, "goal_status_reason": reason}


def export_document_csv(record: dict[str, Any]) -> str:
    """Return a tabular, non-round-trip projection of a valid record.

    Each row represents one field candidate. Candidate values, alternatives,
    and evidence are encoded as JSON in a cell, preserving their structure and
    ensuring a free-text literal is not placed at the start of a CSV cell.
    The JSON export should be used when a complete record is required.
    """
    document = _validated_record(record)
    fields = document["fields"]
    failed_rules = failed_rules_by_field(document)
    field_names = sorted(fields)
    if not field_names:
        field_names = [""]

    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS, lineterminator="\r\n")
    writer.writeheader()
    for row_index, field_name in enumerate(field_names):
        writer.writerow(
            {
                "export_format_version": CSV_EXPORT_VERSION,
                "document_id": document["document_id"],
                "schema_version": document["schema_version"],
                "document_family": document["document_family"],
                "source_sha256": document["source"]["sha256"],
                "source_filename_json": _json_text(
                    document["source"].get("original_filename")
                ),
                "field_name": field_name,
                # Fixed vocabulary and reasons that start with a letter: no
                # cell can begin with a spreadsheet formula character.
                **_goal_columns(fields.get(field_name), failed_rules.get(field_name, frozenset())),
                "candidate_json": _json_text(fields[field_name]) if field_name else "",
                "review_events_json": _json_text(document["review"]["events"]) if row_index == 0 else "",
            }
        )
    return output.getvalue()
