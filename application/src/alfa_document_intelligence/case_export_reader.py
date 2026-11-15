"""Read back an exported expense case and refuse inconsistent files (REQ-089).

Without the archive, the export can be checked for accidental or careless
edits: each line's evidence digest is recomputed from its fields, every review
event's own digest is checked, line statuses must match the recorded decisions,
and every suggestion, decision, duplicate group and unused attachment must
refer to an attachment bound in the export.

Limit: the digests are not keyed. Someone who edits the file on purpose and
recomputes them, or edits fields no digest covers (findings, suggestion
reasons, source hashes), is not detected. Proving the export against the
originals needs the archive (``validate_reconciliation``).
"""
from __future__ import annotations

from copy import deepcopy
import json
from typing import Any

from .expense_reconciliation import (
    _LINE_FIELDS,
    ReconciliationError,
    _canonical_digest,
    _valid_hash,
    _valid_id,
    _validate_review_event,
)
from .exporters.case_json import CASE_EXPORT_KEYS, CASE_EXPORT_SCHEMA_VERSION

_MAX_EXPORT_BYTES = 64 * 1024 * 1024
_STATUSES = {
    "unreviewed", "confirmed", "rejected", "ambiguous", "missing_support",
    "possible_duplicate", "excluded_with_reason",
}


class CaseExportError(ValueError):
    """The text is not an unaltered OCR2 case export."""


def _binding(value: Any, label: str) -> tuple[str, str]:
    if not isinstance(value, dict) or set(value) != {"document_id", "source_sha256"}:
        raise CaseExportError(f"{label} binding is invalid")
    return _valid_id(value["document_id"], label), _valid_hash(value["source_sha256"], label)


def read_case_export(text: str) -> dict[str, Any]:
    """Validate an exported case and return it unchanged, as a new dictionary.

    Machine suggestions stay in ``lines[*].suggestions``, human decisions in
    ``review_events`` and source evidence in the digests and bindings.
    """
    if not isinstance(text, str) or len(text.encode("utf-8")) > _MAX_EXPORT_BYTES:
        raise CaseExportError("the export must be text of reasonable size")
    try:
        payload = json.loads(text)
        return _validated(payload)
    except CaseExportError:
        raise
    except (ValueError, ReconciliationError, KeyError, TypeError) as exc:
        raise CaseExportError("the export is not a valid or unaltered OCR2 case export") from exc


def _validated(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != {"export_schema_version", "case_id", *CASE_EXPORT_KEYS}:
        raise CaseExportError("the export fields are not the expected ones")
    if payload["export_schema_version"] != CASE_EXPORT_SCHEMA_VERSION:
        raise CaseExportError("unsupported case export version")
    _valid_id(payload["case_id"], "case ID")
    case_revision = _valid_hash(payload["case_revision"], "case revision")
    statement_id, _ = _binding(payload["statement"], "statement")
    attachments = payload["attachments"]
    if not isinstance(attachments, list):
        raise CaseExportError("attachments must be a list")
    bound = dict(_binding(item, "attachment") for item in attachments)
    if len(bound) != len(attachments):
        raise CaseExportError("attachments must be unique")

    lines = payload["lines"]
    if not isinstance(lines, list) or not lines:
        raise CaseExportError("lines must be a non-empty list")
    by_id: dict[str, dict] = {}
    for line in lines:
        line_id = _valid_id(line["line_id"], "line ID")
        fields = line["fields"]
        if line_id in by_id or not isinstance(fields, dict) or not set(fields) <= set(_LINE_FIELDS):
            raise CaseExportError("line identity or fields are invalid")
        if _canonical_digest({"line_id": line_id, "fields": fields}) != _valid_hash(line["evidence_sha256"], "line evidence"):
            raise CaseExportError("a line was changed after export")
        if line["status"] not in _STATUSES or not isinstance(line["findings"], list):
            raise CaseExportError("line status is invalid")
        for suggestion in line["suggestions"]:
            if bound.get(suggestion["document_id"]) != suggestion["source_sha256"]:
                raise CaseExportError("a suggestion refers to an attachment that is not in the export")
            if not isinstance(suggestion["reasons"], list) or not isinstance(suggestion["supporting_fields"], dict):
                raise CaseExportError("suggestion details are invalid")
        by_id[line_id] = line

    events = payload["review_events"]
    if not isinstance(events, list):
        raise CaseExportError("review events must be a list")
    latest: dict[str, dict] = {}
    seen: set[str] = set()
    for sequence, event in enumerate(events, start=1):
        _validate_review_event(event, sequence)
        if event["event_id"] in seen:
            raise CaseExportError("review event IDs must be unique")
        seen.add(event["event_id"])
        if event["case_revision"] == case_revision:
            line = by_id.get(event["line_id"])
            if line is None or line["evidence_sha256"] != event["line_evidence_sha256"]:
                raise CaseExportError("a decision refers to a line that is not in the export")
            for source in event["candidate_sources"]:
                if bound.get(source["document_id"]) != source["source_sha256"]:
                    raise CaseExportError("a decision refers to an attachment that is not in the export")
            latest[event["line_id"]] = event
    for line_id, line in by_id.items():
        event = latest.get(line_id)
        if line["status"] != (event["action"] if event else "unreviewed") or \
                line["current_review_event_id"] != (event["event_id"] if event else None):
            raise CaseExportError("a line status does not match its recorded decisions")

    known = set(bound) | {statement_id}
    if not set(payload["unused_document_ids"]) <= known:
        raise CaseExportError("unused attachments are not in the export")
    for group in payload["duplicate_source_groups"]:
        if not set(group["document_ids"]) <= known:
            raise CaseExportError("a duplicate group refers to an unknown attachment")
    for group in payload["possible_duplicate_claim_groups"]:
        if not set(group["line_ids"]) <= set(by_id):
            raise CaseExportError("a duplicate claim group refers to an unknown line")
    return deepcopy(payload)
