"""Append-only human review transitions separate from extraction and administration."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import json
import re
import uuid
from typing import Any

from .contracts import validate_document_record
from .document_family_catalog import validate_family_snapshot

_REVIEW_STATUSES = {"not_started", "queued", "in_progress", "completed", "blocked"}
_ACTIONS = {"queued", "opened", "field_corrected", "alternative_selected", "fiscal_state_corrected", "flagged", "completed", "returned"}
_EDIT_ACTIONS = {"field_corrected", "alternative_selected"}
_DOCUMENT_FAMILY_VALUES = {"invoice", "fiscal_receipt", "parking_receipt", "hotel_document", "pos_slip", "other", "unknown"}
_FIELD = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_COMMON_KEYS = {"event_id", "actor_id", "action", "timestamp", "previous_event_hash", "event_hash"}
_ALLOWED_KEYS = _COMMON_KEYS | {
    "field_name", "reason_code", "candidate", "fiscal_state", "document_family_snapshot"
}
_STAGE_NAMES = ("ingestion", "ocr", "semantic_extraction", "document_validation", "administrative_verification")


class ReviewRejected(ValueError):
    """A proposed review event violates identity, evidence, integrity, or state rules."""


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ReviewRejected("review timestamp must be an ISO date-time")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReviewRejected("review timestamp must be an ISO date-time") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReviewRejected("review timestamp must include a timezone")
    return parsed


def _event_hash(unsigned: dict[str, Any]) -> str:
    encoded = json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _next_status(status: str, action: str) -> str:
    transitions = {
        ("not_started", "queued"): "queued",
        ("queued", "opened"): "in_progress",
        ("blocked", "opened"): "in_progress",
        ("in_progress", "field_corrected"): "in_progress",
        ("in_progress", "alternative_selected"): "in_progress",
        ("in_progress", "fiscal_state_corrected"): "in_progress",
        ("in_progress", "flagged"): "blocked",
        ("in_progress", "completed"): "completed",
        ("in_progress", "returned"): "queued",
    }
    result = transitions.get((status, action))
    if result is None:
        raise ReviewRejected("review action is not allowed from the current status")
    return result


def _validate_candidate(record: dict[str, Any], field_name: str, candidate: Any) -> None:
    if not isinstance(field_name, str) or not _FIELD.fullmatch(field_name):
        raise ReviewRejected("review field_name is invalid")
    if not isinstance(candidate, dict):
        raise ReviewRejected("review candidate must be an object")
    allowed = {"value", "status", "alternatives", "evidence", "confidence", "normalization"}
    required = {"value", "status", "alternatives", "evidence"}
    if set(candidate) - allowed or not required <= set(candidate):
        raise ReviewRejected("review candidate does not match the field-candidate contract")
    if not isinstance(candidate.get("status"), str) or candidate["status"] not in {"observed", "uncertain", "unreadable", "absent", "not_applicable", "rejected"}:
        raise ReviewRejected("review candidate status is invalid")
    if candidate.get("status") == "observed" and candidate.get("value") is None:
        raise ReviewRejected("observed review candidate requires a value")
    if candidate.get("status") == "uncertain" and candidate.get("value") is None and not candidate.get("alternatives"):
        raise ReviewRejected("uncertain null review candidate requires alternatives")
    if candidate.get("status") in {"absent", "not_applicable", "unreadable"} and candidate.get("value") is not None:
        raise ReviewRejected("review candidate status requires a null value")
    if not isinstance(candidate.get("alternatives"), list) or not isinstance(candidate.get("evidence"), list):
        raise ReviewRejected("review candidate alternatives and evidence must be arrays")
    if candidate.get("normalization") is not None:
        if not isinstance(candidate["normalization"], dict) or candidate["normalization"].get("normalized_value") != candidate.get("value"):
            raise ReviewRejected("review normalization must match the candidate value")

    source = record.get("source")
    pages = record.get("pages")
    probe = {
        "schema_version": "0.1.0",
        "source": source,
        "fiscal_document_state": record.get("fiscal_document_state"),
        "pages": pages,
        "processing": {name: {"status": "not_started"} for name in _STAGE_NAMES},
        "fields": {field_name: candidate},
    }
    issues = validate_document_record(probe)
    if issues:
        raise ReviewRejected("review candidate violates source-evidence contract: " + "; ".join(issues))


def _validate_fiscal_state(record: dict[str, Any], fiscal_state: Any) -> None:
    if not isinstance(fiscal_state, dict) or set(fiscal_state) != {"status", "evidence"}:
        raise ReviewRejected("review fiscal_state must contain status and evidence only")
    if fiscal_state.get("status") not in {"fiscal_document", "payment_evidence", "not_fiscal", "uncertain", "unknown"}:
        raise ReviewRejected("review fiscal_state status is invalid")
    if not isinstance(fiscal_state.get("evidence"), list):
        raise ReviewRejected("review fiscal_state evidence must be an array")
    probe = deepcopy(record)
    probe["fiscal_document_state"] = deepcopy(fiscal_state)
    issues = validate_document_record(probe)
    if issues:
        raise ReviewRejected("review fiscal-state candidate violates source-evidence contract: " + "; ".join(issues))



def _effective_family(record: dict[str, Any], prior_events: list[dict[str, Any]]) -> str:
    family = record.get("document_family", "unknown")
    for prior in prior_events:
        if (
            prior.get("action") in _EDIT_ACTIONS
            and prior.get("field_name") == "document_family"
            and isinstance(prior.get("candidate"), dict)
        ):
            family = prior["candidate"].get("value", family)
    return family


def _effective_fiscal_state(record: dict[str, Any], prior_events: list[dict[str, Any]]) -> dict[str, Any]:
    state = deepcopy(record.get("fiscal_document_state", {}))
    for prior in prior_events:
        if prior.get("action") == "fiscal_state_corrected":
            state = deepcopy(prior.get("fiscal_state", state))
    return state


def _validate_document_family_candidate(
    record: dict[str, Any], candidate: Any, prior_events: list[dict[str, Any]]
) -> dict[str, Any] | None:
    if record.get("document_family") == "expense_report":
        raise ReviewRejected("expense note family cannot be corrected as a supporting document family")
    if not isinstance(candidate, dict) or candidate.get("status") != "observed":
        raise ReviewRejected("document family selection must be an observed candidate")
    value = candidate.get("value")
    if not isinstance(value, str):
        raise ReviewRejected("document family selection value must be text")
    selected_snapshot = None
    if value not in _DOCUMENT_FAMILY_VALUES:
        snapshots = record.get("document_family_definitions")
        if not isinstance(snapshots, list) or not snapshots:
            raise ReviewRejected("custom document family selection requires an embedded snapshot")
        for snapshot in snapshots:
            if validate_family_snapshot(snapshot):
                raise ReviewRejected("custom document family selection has an invalid embedded snapshot")
        selected_snapshot = next(
            (snapshot for snapshot in snapshots if snapshot["family"].get("id") == value), None
        )
        if selected_snapshot is None:
            raise ReviewRejected("custom document family selection requires a matching embedded snapshot")
    proposal = record.get("fields", {}).get("document_family_candidates")
    alternatives = proposal.get("alternatives") if isinstance(proposal, dict) else None
    if not isinstance(alternatives, list):
        raise ReviewRejected("document family selection requires extracted family alternatives")
    supported = any(
        isinstance(item, dict)
        and item.get("value") == value
        and item.get("status") == "observed"
        and item.get("evidence") == candidate.get("evidence")
        for item in alternatives
    )
    if not supported:
        raise ReviewRejected("document family selection must match an evidence-bound alternative")
    if (
        value == "pos_slip"
        and _effective_fiscal_state(record, prior_events).get("status") == "fiscal_document"
    ):
        raise ReviewRejected("a document with fiscal-document status cannot be reclassified as a POS slip")
    return deepcopy(selected_snapshot)


def _validate_event_shape(
    record: dict[str, Any], event: dict[str, Any], prior_events: list[dict[str, Any]]
) -> datetime:
    if not isinstance(event, dict) or set(event) - _ALLOWED_KEYS or not _COMMON_KEYS <= set(event):
        raise ReviewRejected("review event fields are invalid")
    for key in ("event_id", "actor_id"):
        if not isinstance(event.get(key), str) or not event[key].strip():
            raise ReviewRejected(f"review {key} is required")
    if not isinstance(event["action"], str) or event["action"] not in _ACTIONS:
        raise ReviewRejected("review action is unsupported")
    if "document_family_snapshot" in event and (
        event["action"] not in _EDIT_ACTIONS or event.get("field_name") != "document_family"
    ):
        raise ReviewRejected("document family snapshot is allowed only for family selection")
    timestamp = _timestamp(event.get("timestamp"))
    if event.get("action") in _EDIT_ACTIONS:
        if not isinstance(event.get("reason_code"), str) or not event["reason_code"].strip():
            raise ReviewRejected("field review actions require reason_code")
        _validate_candidate(record, event.get("field_name"), event.get("candidate"))
        if event["action"] == "alternative_selected" and event["candidate"].get("status") != "observed":
            raise ReviewRejected("selected alternative must become an observed candidate")
        if event.get("field_name") == "document_family":
            family_snapshot = _validate_document_family_candidate(record, event.get("candidate"), prior_events)
            if family_snapshot is not None and event.get("document_family_snapshot") != family_snapshot:
                raise ReviewRejected("custom document family event does not bind its embedded snapshot")
            if family_snapshot is None and "document_family_snapshot" in event:
                raise ReviewRejected("built-in document family event cannot include a custom snapshot")
    elif event["action"] == "fiscal_state_corrected":
        if not isinstance(event.get("reason_code"), str) or not event["reason_code"].strip():
            raise ReviewRejected("fiscal-state review action requires reason_code")
        _validate_fiscal_state(record, event.get("fiscal_state"))
        if (
            event.get("fiscal_state", {}).get("status") == "fiscal_document"
            and _effective_family(record, prior_events) == "pos_slip"
        ):
            raise ReviewRejected("a reviewed POS slip cannot be classified as a fiscal document")
        if any(key in event for key in ("field_name", "candidate")):
            raise ReviewRejected("fiscal-state review action cannot replace a field candidate")
    elif event["action"] == "flagged":
        if not isinstance(event.get("reason_code"), str) or not event["reason_code"].strip():
            raise ReviewRejected("flagged review action requires reason_code")
        if any(key in event for key in ("candidate", "fiscal_state")):
            raise ReviewRejected("flagged review action cannot replace document evidence")
        if "field_name" in event and (not isinstance(event["field_name"], str) or not _FIELD.fullmatch(event["field_name"])):
            raise ReviewRejected("review field_name is invalid")
    elif any(key in event for key in ("field_name", "reason_code", "candidate", "fiscal_state")):
        raise ReviewRejected("workflow-only review action cannot include field data")
    previous_hash = event.get("previous_event_hash")
    if previous_hash is not None and (not isinstance(previous_hash, str) or not re.fullmatch(r"[a-f0-9]{64}", previous_hash)):
        raise ReviewRejected("previous review hash is invalid")
    if not isinstance(event.get("event_hash"), str) or not re.fullmatch(r"[a-f0-9]{64}", event["event_hash"]):
        raise ReviewRejected("review event hash is invalid")
    return timestamp


def verify_review_ledger(record: dict[str, Any]) -> str | None:
    """Verify ordered transitions and hash links; return the current head hash."""
    if not isinstance(record, dict) or not isinstance(record.get("review"), dict):
        raise ReviewRejected("document review record is missing")
    review = record["review"]
    final_status = review.get("status")
    events = review.get("events")
    if not isinstance(final_status, str) or final_status not in _REVIEW_STATUSES or not isinstance(events, list):
        raise ReviewRejected("document review status or events are invalid")
    status = "not_started"
    last_hash = None
    last_timestamp = None
    event_ids: set[str] = set()
    prior_events: list[dict[str, Any]] = []
    for event in events:
        timestamp = _validate_event_shape(record, event, prior_events)
        if event["event_id"] in event_ids:
            raise ReviewRejected("review event_id is duplicated")
        event_ids.add(event["event_id"])
        if last_timestamp is not None and timestamp < last_timestamp:
            raise ReviewRejected("review timestamps must be ordered")
        if event["previous_event_hash"] != last_hash:
            raise ReviewRejected("review hash chain is broken")
        unsigned = {key: value for key, value in event.items() if key != "event_hash"}
        computed = _event_hash(unsigned)
        if event["event_hash"] != computed:
            raise ReviewRejected("review event hash mismatch")
        status = _next_status(status, event["action"])
        last_hash, last_timestamp = event["event_hash"], timestamp
        prior_events.append(event)
    if status != final_status:
        raise ReviewRejected("review status does not match its event history")
    return last_hash


def reviewed_overlay(record: dict[str, Any]) -> dict[str, Any]:
    """Return separate extracted and effective reviewed views without mutating the record."""
    verify_review_ledger(record)
    extracted_fields = deepcopy(record["fields"])
    reviewed_fields = deepcopy(extracted_fields)
    reviewed_fiscal_state = deepcopy(record["fiscal_document_state"])
    extracted_family = record.get("document_family", "unknown")
    reviewed_family = extracted_family
    for event in record["review"]["events"]:
        if event["action"] in _EDIT_ACTIONS:
            reviewed_fields[event["field_name"]] = deepcopy(event["candidate"])
            if event.get("field_name") == "document_family":
                reviewed_family = event["candidate"]["value"]
        elif event["action"] == "fiscal_state_corrected":
            reviewed_fiscal_state = deepcopy(event["fiscal_state"])
    return {
        "extracted_fields": extracted_fields,
        "reviewed_fields": reviewed_fields,
        "extracted_document_family": extracted_family,
        "reviewed_document_family": reviewed_family,
        "extracted_fiscal_document_state": deepcopy(record["fiscal_document_state"]),
        "reviewed_fiscal_document_state": reviewed_fiscal_state,
        "review_status": record["review"]["status"],
    }


def append_review_event(
    record: dict[str, Any],
    *,
    actor_id: str,
    action: str,
    timestamp: str,
    field_name: str | None = None,
    reason_code: str | None = None,
    candidate: dict[str, Any] | None = None,
    fiscal_state: dict[str, Any] | None = None,
    event_id: str | None = None,
) -> dict[str, Any]:
    """Return a new document with a verified review event; extraction is never rewritten."""
    previous_hash = verify_review_ledger(record)
    review = record["review"]
    next_status = _next_status(review["status"], action)
    if not isinstance(actor_id, str) or not actor_id.strip():
        raise ReviewRejected("review actor_id is required")
    parsed_timestamp = _timestamp(timestamp)
    if review["events"]:
        last_timestamp = _timestamp(review["events"][-1]["timestamp"])
        if parsed_timestamp < last_timestamp:
            raise ReviewRejected("review timestamps must be ordered")

    event: dict[str, Any] = {
        "event_id": event_id or str(uuid.uuid4()),
        "actor_id": actor_id,
        "action": action,
        "timestamp": timestamp,
        "previous_event_hash": previous_hash,
    }
    if action in _EDIT_ACTIONS | {"flagged", "fiscal_state_corrected"}:
        if field_name is not None:
            event["field_name"] = field_name
        if reason_code is not None:
            event["reason_code"] = reason_code
    if action in _EDIT_ACTIONS and candidate is not None:
        event["candidate"] = deepcopy(candidate)
        if field_name == "document_family":
            family_snapshot = _validate_document_family_candidate(record, candidate, review["events"])
            if family_snapshot is not None:
                event["document_family_snapshot"] = family_snapshot
    if action == "fiscal_state_corrected" and fiscal_state is not None:
        event["fiscal_state"] = deepcopy(fiscal_state)
    event["event_hash"] = _event_hash(event)

    updated = deepcopy(record)
    updated["review"]["events"].append(event)
    updated["review"]["status"] = next_status
    verify_review_ledger(updated)
    return updated
