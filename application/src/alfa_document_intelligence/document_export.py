"""Local serialization helpers for validated document intelligence records.

These functions serialize metadata only. They never read or include source-file
bytes and never write files or transmit exported content.
"""
from __future__ import annotations

import csv
import io
import json
import re
from typing import Any

from .contracts import validate_document_record
from .review_ledger import reviewed_overlay

CSV_EXPORT_VERSION = "ocr2-document-csv-v1"
_CSV_DOCUMENT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_CSV_FIELD_NAME = re.compile(r"[a-z][a-z0-9_]{1,63}\Z")
CSV_COLUMNS = (
    "export_format_version",
    "document_id",
    "schema_version",
    "document_family",
    "source_sha256",
    "source_filename_json",
    "field_name",
    "candidate_json",
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


def export_document_csv(record: dict[str, Any]) -> str:
    """Return a tabular, non-round-trip projection of a valid record.

    Each row represents one field candidate. Candidate values, alternatives,
    and evidence are encoded as JSON in a cell, preserving their structure and
    ensuring a free-text literal is not placed at the start of a CSV cell.
    The JSON export should be used when a complete record is required.
    """
    document = _validated_record(record)
    fields = document["fields"]
    if not isinstance(document["document_id"], str) or not _CSV_DOCUMENT_ID.fullmatch(document["document_id"]):
        raise ExportValidationError(["document_id: invalid CSV identifier"])
    if any(not isinstance(name, str) or not _CSV_FIELD_NAME.fullmatch(name) for name in fields):
        raise ExportValidationError(["fields: invalid CSV field identifier"])
    field_names = sorted(fields)
    if not field_names:
        field_names = [""]

    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS, lineterminator="\r\n")
    writer.writeheader()
    for field_name in field_names:
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
                "candidate_json": _json_text(fields[field_name]) if field_name else "",
            }
        )
    return output.getvalue()


def export_reviewed_document_csv(record: dict[str, Any]) -> str:
    """Project extracted and effective reviewed candidates without claiming approval.

    The review ledger is verified. JSON remains the complete audit representation.
    """
    document = _validated_record(record)
    overlay = reviewed_overlay(document)
    document_id = document["document_id"]
    if not isinstance(document_id, str) or not _CSV_DOCUMENT_ID.fullmatch(document_id):
        raise ExportValidationError(["document_id: invalid CSV identifier"])
    extracted = overlay["extracted_fields"]
    reviewed = overlay["reviewed_fields"]
    names = set(extracted) | set(reviewed)
    if any(not isinstance(name, str) or not _CSV_FIELD_NAME.fullmatch(name) for name in names):
        raise ExportValidationError(["fields: invalid CSV field identifier"])
    columns = (
        "export_format_version", "document_id", "source_sha256", "review_status",
        "extracted_document_family", "reviewed_document_family",
        "extracted_fiscal_json", "reviewed_fiscal_json", "field_name",
        "extracted_candidate_json", "reviewed_candidate_json",
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\r\n")
    writer.writeheader()
    for name in sorted(names) or [""]:
        writer.writerow({
            "export_format_version": "ocr2-reviewed-csv-v1",
            "document_id": document_id,
            "source_sha256": document["source"]["sha256"],
            "review_status": overlay["review_status"],
            "extracted_document_family": overlay["extracted_document_family"],
            "reviewed_document_family": overlay["reviewed_document_family"],
            "extracted_fiscal_json": _json_text(overlay["extracted_fiscal_document_state"]),
            "reviewed_fiscal_json": _json_text(overlay["reviewed_fiscal_document_state"]),
            "field_name": name,
            "extracted_candidate_json": _json_text(extracted.get(name)),
            "reviewed_candidate_json": _json_text(reviewed.get(name)),
        })
    return output.getvalue()
