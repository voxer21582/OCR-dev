"""In-memory association of one expense note with independent supporting documents."""
from __future__ import annotations

from collections import defaultdict
import hashlib
import re
from typing import Any, Iterable, Mapping

from .contracts import validate_document_record
from .review_ledger import verify_review_ledger

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class ExpenseReportBundleError(ValueError):
    """An expense report bundle would break source or relationship integrity."""


def _validate_id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ExpenseReportBundleError(f"{label} must be an opaque non-empty identifier")
    return value


def _get_valid_document(document_id: str, documents: Mapping[str, dict[str, Any]]) -> dict[str, Any]:
    record = documents.get(document_id)
    if not isinstance(record, dict):
        raise ExpenseReportBundleError(f"document {document_id!r} is missing")
    if record.get("document_id") != document_id:
        raise ExpenseReportBundleError(f"document key does not match record ID for {document_id!r}")
    issues = validate_document_record(record)
    if issues:
        raise ExpenseReportBundleError(f"document {document_id!r} violates its contract: " + "; ".join(issues))
    try:
        verify_review_ledger(record)
    except ValueError as exc:
        raise ExpenseReportBundleError(f"document {document_id!r} has an invalid review ledger") from exc
    return record


def build_expense_report_bundle(
    expense_report_id: str,
    note_document_id: str,
    attachment_document_ids: Iterable[str],
    documents: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    """Build an in-memory parent bundle; source document records remain independent.

    The expense note must have family 'expense_report'. Supporting document IDs
    retain caller order. Exact-content duplicates are reported, never removed.
    An empty attachment list is allowed but raises a review finding.
    """
    bundle_id = _validate_id(expense_report_id, "expense_report_id")
    note_id = _validate_id(note_document_id, "note_document_id")
    if isinstance(attachment_document_ids, (str, bytes)):
        raise ExpenseReportBundleError("attachments must be an ordered collection of document IDs")
    try:
        attachment_ids = tuple(_validate_id(item, "attachment document ID") for item in attachment_document_ids)
    except TypeError as exc:
        raise ExpenseReportBundleError("attachments must be an ordered collection of document IDs") from exc
    if note_id in attachment_ids:
        raise ExpenseReportBundleError("expense note cannot also be attached as supporting evidence")
    if len(attachment_ids) != len(set(attachment_ids)):
        raise ExpenseReportBundleError("attachment document IDs must be unique within a bundle")

    note = _get_valid_document(note_id, documents)
    if note.get("document_family") != "expense_report":
        raise ExpenseReportBundleError("note document must have expense_report family")

    members: list[tuple[str, dict[str, Any]]] = [(note_id, note)]
    for document_id in attachment_ids:
        record = _get_valid_document(document_id, documents)
        if record.get("document_family") == "expense_report":
            raise ExpenseReportBundleError("supporting attachments cannot be another expense report")
        members.append((document_id, record))

    duplicates: dict[str, list[str]] = defaultdict(list)
    for document_id, record in members:
        duplicates[record["source"]["sha256"]].append(document_id)
    duplicate_groups = [
        {"source_sha256": digest, "document_ids": ids}
        for digest, ids in sorted(duplicates.items())
        if len(ids) > 1
    ]

    attachments = [
        {
            "position": index,
            "document_id": document_id,
            "source_sha256": record["source"]["sha256"],
            "document_family": record["document_family"],
            "role": "supporting_document",
        }
        for index, (document_id, record) in enumerate(members[1:], start=1)
    ]
    findings: list[dict[str, Any]] = []
    if not attachments:
        findings.append({
            "code": "no_supporting_documents",
            "severity": "review",
            "outcome": "indeterminate",
            "document_ids": [],
        })
    for group in duplicate_groups:
        findings.append({
            "code": "duplicate_source_in_bundle",
            "severity": "warning",
            "outcome": "indeterminate",
            "document_ids": list(group["document_ids"]),
            "source_sha256": group["source_sha256"],
        })

    return {
        "bundle_schema_version": "0.1.0",
        "expense_report_id": bundle_id,
        "note_document_id": note_id,
        "note_source_sha256": note["source"]["sha256"],
        "attachments": attachments,
        "duplicate_content_groups": duplicate_groups,
        "findings": findings,
        "review_status": "not_started",
    }


def validate_expense_report_bundle(
    bundle: dict[str, Any],
    documents: Mapping[str, dict[str, Any]],
) -> None:
    """Raise when a bundle's references/findings no longer match source records."""
    if not isinstance(bundle, dict):
        raise ExpenseReportBundleError("bundle must be an object")
    attachment_ids = []
    for attachment in bundle.get("attachments", []):
        if not isinstance(attachment, dict):
            raise ExpenseReportBundleError("bundle attachment must be an object")
        attachment_ids.append(attachment.get("document_id"))
    expected = build_expense_report_bundle(
        bundle.get("expense_report_id"),
        bundle.get("note_document_id"),
        attachment_ids,
        documents,
    )
    if bundle != expected:
        raise ExpenseReportBundleError("bundle content does not match linked source records")


from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .ingestion import MaterializedBatch, MaterializedDocument

_MEDIA_TYPES = {
    "pdf": "application/pdf",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "tiff": "image/tiff",
    "webp": "image/webp",
}
_DOCUMENT_FAMILIES = {
    "invoice", "fiscal_receipt", "parking_receipt", "hotel_document",
    "expense_report", "pos_slip", "other", "unknown",
}


@dataclass(frozen=True)
class ExpenseReportIntakeSession:
    """Volatile session objects for one note and its selected attachments."""

    bundle: dict[str, Any]
    documents: dict[str, dict[str, Any]]
    source_bytes: dict[str, bytes]


def _page_inventory(materialized: "MaterializedDocument") -> list[dict[str, Any]]:
    item = materialized.inventory
    if item.page_count is None:
        return []
    pages = []
    for number in range(1, item.page_count + 1):
        page: dict[str, Any] = {"page_number": number}
        if number == 1 and item.width_px is not None and item.height_px is not None:
            page["width_px"] = item.width_px
            page["height_px"] = item.height_px
            if item.width_px == item.height_px:
                page["orientation"] = "square"
            else:
                page["orientation"] = "landscape" if item.width_px > item.height_px else "portrait"
        else:
            page["orientation"] = "unknown"
        pages.append(page)
    return pages


def _document_record_from_materialized(
    materialized: "MaterializedDocument",
    *,
    document_id: str,
    session_id: str,
    document_family: str,
    received_at: str,
) -> dict[str, Any]:
    _validate_id(document_id, "document_id")
    if document_family not in _DOCUMENT_FAMILIES:
        raise ExpenseReportBundleError("unsupported document family")
    media_type = _MEDIA_TYPES.get(materialized.inventory.media_kind)
    if media_type is None:
        raise ExpenseReportBundleError("unsupported materialized document media kind")
    try:
        timestamp = datetime.fromisoformat(received_at.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ExpenseReportBundleError("received_at must be an ISO date-time") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ExpenseReportBundleError("received_at must include a timezone")

    item = materialized.inventory
    source: dict[str, Any] = {
        "sha256": item.sha256,
        "media_type": media_type,
        "byte_length": item.byte_length,
        "original_filename": item.name,
        "received_at": received_at,
        "storage_ref": f"memory://{session_id}/{document_id}",
    }
    if item.page_count is not None:
        source["page_count"] = item.page_count
    record: dict[str, Any] = {
        "schema_version": "0.1.0",
        "document_id": document_id,
        "source": source,
        "document_family": document_family,
        "language": "unknown",
        "fiscal_document_state": {"status": "unknown", "evidence": []},
        "pages": _page_inventory(materialized),
        "processing": {
            "ingestion": {"status": "completed"},
            "ocr": {"status": "not_started"},
            "semantic_extraction": {"status": "not_started"},
            "document_validation": {"status": "not_started"},
            "administrative_verification": {"status": "not_started"},
        },
        "fields": {},
        "validation_findings": [],
        "review": {"status": "not_started", "events": []},
        "administrative_verification": {"status": "not_started"},
    }
    issues = validate_document_record(record)
    if issues:
        raise ExpenseReportBundleError("materialized document record violates its contract: " + "; ".join(issues))
    verify_review_ledger(record)
    return record


def create_expense_report_intake_session(
    batch: "MaterializedBatch",
    *,
    expense_report_id: str,
    note_document_id: str,
    document_ids: Iterable[str],
    session_id: str,
    received_at: str,
) -> ExpenseReportIntakeSession:
    """Turn materialized files into source-bound records and one volatile bundle.

    The caller explicitly identifies which uploaded document is the expense
    note. All remaining documents become ordered attachments; no OCR
    classification or employee identity is inferred.
    """
    _validate_id(session_id, "session_id")
    _validate_id(expense_report_id, "expense_report_id")
    _validate_id(note_document_id, "note_document_id")
    if isinstance(document_ids, (str, bytes)):
        raise ExpenseReportBundleError("document_ids must be an ordered collection")
    try:
        ids = tuple(_validate_id(item, "document_id") for item in document_ids)
    except TypeError as exc:
        raise ExpenseReportBundleError("document_ids must be an ordered collection") from exc
    payloads = tuple(
        document
        for upload in batch.uploads
        for document in upload.documents
    )
    if len(ids) != len(payloads):
        raise ExpenseReportBundleError("one document ID is required for each materialized source")
    if len(set(ids)) != len(ids):
        raise ExpenseReportBundleError("document IDs must be unique within a session")
    if note_document_id not in ids:
        raise ExpenseReportBundleError("selected expense note is not part of this upload session")

    documents: dict[str, dict[str, Any]] = {}
    source_bytes: dict[str, bytes] = {}
    for document_id, payload in zip(ids, payloads, strict=True):
        family = "expense_report" if document_id == note_document_id else "unknown"
        documents[document_id] = _document_record_from_materialized(
            payload,
            document_id=document_id,
            session_id=session_id,
            document_family=family,
            received_at=received_at,
        )
        if hashlib.sha256(payload.data).hexdigest() != documents[document_id]["source"]["sha256"]:
            raise ExpenseReportBundleError("materialized bytes do not match source hash")
        source_bytes[document_id] = payload.data

    attachment_ids = [item for item in ids if item != note_document_id]
    bundle = build_expense_report_bundle(
        expense_report_id,
        note_document_id,
        attachment_ids,
        documents,
    )
    return ExpenseReportIntakeSession(bundle, documents, source_bytes)
