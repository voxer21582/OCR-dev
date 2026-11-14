"""Deterministic, evidence-bound suggestions for expense statement lines.

This module ranks candidate supporting records. It does not confirm matches or
approve fiscal, reimbursement, accounting, or payment outcomes.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from typing import Any, Mapping

from .contracts import validate_document_record


class ReconciliationError(ValueError):
    """The reconciliation payload does not satisfy its source-bound contract."""


_HASH = re.compile(r"^[a-fA-F0-9]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_ACTIONS = {
    "confirmed", "rejected", "ambiguous", "missing_support",
    "possible_duplicate", "excluded_with_reason",
}
_LINE_FIELDS = ("amount", "currency", "date", "merchant", "description")


def _canonical_digest(value: Any) -> str:
    try:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ReconciliationError("payload is not canonical JSON data") from exc
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _revision_digest(
    case_id: str, statement: dict[str, str], attachments: list[dict[str, str]],
    lines: list[dict[str, str]], source_set_revision: str,
) -> str:
    return _canonical_digest({
        "case_id": case_id,
        "statement": statement,
        "attachments": attachments,
        "lines": lines,
        "source_set_revision": source_set_revision,
    })


def case_source_set_revision(
    statement_id: str, statement_hash: str, chunks: list[dict], inclusion_events: list[dict],
) -> str:
    """Digest immutable upload and inclusion history without binding review events."""
    statement = {
        "document_id": _valid_id(statement_id, "statement document ID"),
        "source_sha256": _valid_hash(statement_hash, "statement source hash"),
    }
    if not isinstance(chunks, list) or not isinstance(inclusion_events, list):
        raise ReconciliationError("source-set history is invalid")
    normalized_chunks = []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            raise ReconciliationError("source-set chunk is invalid")
        chunk_id = _valid_id(chunk.get("chunk_id"), "source-set chunk ID")
        chunk_hash = _valid_hash(chunk.get("chunk_digest"), "source-set chunk digest")
        document_ids = chunk.get("document_ids")
        if not isinstance(document_ids, list):
            raise ReconciliationError("source-set chunk documents are invalid")
        normalized_chunks.append({
            "chunk_id": chunk_id,
            "chunk_digest": chunk_hash,
            "document_ids": [_valid_id(value, "source-set document ID") for value in document_ids],
        })
    normalized_events = []
    for sequence, event in enumerate(inclusion_events, start=1):
        if not isinstance(event, dict) or event.get("sequence") != sequence:
            raise ReconciliationError("source-set inclusion history is invalid")
        digest = _valid_hash(event.get("event_sha256"), "source-set inclusion event digest")
        body = {key: value for key, value in event.items() if key not in {"sequence", "event_sha256"}}
        if _canonical_digest(body) != digest:
            raise ReconciliationError("source-set inclusion event digest is invalid")
        normalized_events.append({"sequence": sequence, "event_sha256": digest})
    return _canonical_digest({
        "statement": statement,
        "chunks": normalized_chunks,
        "inclusion_events": normalized_events,
    })


def _validate_review_event(event: Any, expected_sequence: int | None = None) -> None:
    if not isinstance(event, dict):
        raise ReconciliationError("review event is invalid")
    _valid_id(event.get("event_id"), "review event ID")
    _valid_hash(event.get("case_revision"), "review case revision")
    _valid_id(event.get("line_id"), "review line ID")
    _valid_hash(event.get("line_evidence_sha256"), "review line evidence digest")
    if expected_sequence is not None and event.get("sequence") != expected_sequence:
        raise ReconciliationError("review event sequence is invalid")
    action = event.get("action")
    if action not in _ACTIONS:
        raise ReconciliationError("review event action is invalid")
    sources = event.get("candidate_sources")
    if not isinstance(sources, list):
        raise ReconciliationError("review event candidate sources are invalid")
    source_ids = set()
    for source in sources:
        if not isinstance(source, dict) or set(source) != {"document_id", "source_sha256"}:
            raise ReconciliationError("review event source binding is invalid")
        document_id = _valid_id(source.get("document_id"), "review candidate document ID")
        _valid_hash(source.get("source_sha256"), "review candidate source hash")
        if document_id in source_ids:
            raise ReconciliationError("review event sources must be unique")
        source_ids.add(document_id)
    if action == "confirmed" and not sources:
        raise ReconciliationError("confirmation requires a selected supporting source")
    note = event.get("reviewer_note")
    if note is not None and (not isinstance(note, str) or len(note) > 2000):
        raise ReconciliationError("reviewer note is invalid")
    if action == "excluded_with_reason" and not (isinstance(note, str) and note.strip()):
        raise ReconciliationError("exclusion requires a reviewer reason")
    digest = event.get("event_sha256")
    body = {key: value for key, value in event.items() if key not in {"sequence", "event_sha256"}}
    if not isinstance(digest, str) or _canonical_digest(body) != digest:
        raise ReconciliationError("review event digest is invalid")


def _valid_id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ReconciliationError(f"{label} must be an opaque identifier")
    return value


def _valid_hash(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _HASH.fullmatch(value):
        raise ReconciliationError(f"{label} must be a SHA-256 digest")
    return value.lower()


def _validate_document(document_id: str, record: Any) -> str:
    if not isinstance(record, dict) or record.get("document_id") != document_id:
        raise ReconciliationError("document key does not match its record ID")
    contract_issues = validate_document_record(record)
    if contract_issues:
        raise ReconciliationError("document record violates the evidence contract")
    digest = _valid_hash((record.get("source") or {}).get("sha256"), "document source hash")
    pages = record.get("pages")
    if not isinstance(pages, list):
        raise ReconciliationError("document pages must be an array")
    page_numbers = set()
    for page in pages:
        if not isinstance(page, dict) or not isinstance(page.get("page_number"), int) or page["page_number"] < 1:
            raise ReconciliationError("document page inventory is invalid")
        page_numbers.add(page["page_number"])
    fields = record.get("fields")
    if not isinstance(fields, dict):
        raise ReconciliationError("document fields must be an object")
    for name, candidate in fields.items():
        _validate_candidate(candidate, label=f"document field {name}", expected_hash=digest, page_numbers=page_numbers)
    return digest


def _validate_candidate(candidate: Any, *, label: str, expected_hash: str, page_numbers: set[int]) -> None:
    if not isinstance(candidate, dict):
        raise ReconciliationError(f"{label} candidate must be an object")
    status = candidate.get("status")
    if status not in {"observed", "uncertain", "unreadable", "absent", "not_applicable", "rejected"}:
        raise ReconciliationError(f"{label} candidate status is invalid")
    if status == "observed" and not isinstance(candidate.get("value"), str):
        raise ReconciliationError(f"observed {label} candidate must have a string value")
    if status in {"absent", "not_applicable", "unreadable"} and candidate.get("value") is not None:
        raise ReconciliationError(f"{label} candidate status requires a null value")
    evidence = candidate.get("evidence", [])
    if not isinstance(evidence, list):
        raise ReconciliationError(f"{label} evidence must be an array")
    if status in {"observed", "uncertain", "unreadable", "rejected"} and not evidence:
        raise ReconciliationError(f"{label} candidate lacks source evidence")
    for item in evidence:
        if not isinstance(item, dict):
            raise ReconciliationError(f"{label} evidence item is invalid")
        if _valid_hash(item.get("source_sha256"), f"{label} evidence hash") != expected_hash:
            raise ReconciliationError(f"{label} evidence hash does not match its source")
        page = item.get("page_number")
        if not isinstance(page, int) or page < 1 or page not in page_numbers:
            raise ReconciliationError(f"{label} evidence page is invalid")
    alternatives = candidate.get("alternatives", [])
    if not isinstance(alternatives, list):
        raise ReconciliationError(f"{label} alternatives must be an array")
    if status == "uncertain" and candidate.get("value") is None and not alternatives:
        raise ReconciliationError(f"uncertain {label} candidate requires alternatives")
    for alternative in alternatives:
        if not isinstance(alternative, dict) or alternative.get("status") not in {"observed", "uncertain", "unreadable", "rejected"}:
            raise ReconciliationError(f"{label} alternative is invalid")
        alternative_evidence = alternative.get("evidence")
        if not isinstance(alternative_evidence, list) or not alternative_evidence:
            raise ReconciliationError(f"{label} alternative lacks evidence")
        for item in alternative_evidence:
            if not isinstance(item, dict) or _valid_hash(item.get("source_sha256"), f"{label} alternative hash") != expected_hash:
                raise ReconciliationError(f"{label} alternative source binding is invalid")
            page = item.get("page_number")
            if not isinstance(page, int) or page < 1 or page not in page_numbers:
                raise ReconciliationError(f"{label} alternative evidence page is invalid")
    normalization = candidate.get("normalization")
    if normalization is not None and (
        not isinstance(normalization, dict) or normalization.get("normalized_value") != candidate.get("value")
    ):
        raise ReconciliationError(f"{label} normalization is inconsistent")


def _candidate_value(candidate: dict[str, Any]) -> Any:
    if candidate.get("status") != "observed":
        return None
    normalization = candidate.get("normalization")
    if isinstance(normalization, dict) and isinstance(normalization.get("normalized_value"), str):
        return normalization["normalized_value"]
    return candidate.get("value")


def _candidate_possible_values(candidate: dict[str, Any], normalize) -> list[tuple[Any, dict[str, Any], bool]]:
    """Return normalized observations and alternatives, marking non-final values uncertain."""
    if not isinstance(candidate, dict):
        return []
    if candidate.get("status") == "observed":
        value = normalize(_candidate_value(candidate))
        return [(value, candidate, False)] if value is not None else []
    if candidate.get("status") != "uncertain":
        return []
    result = []
    value = normalize(candidate.get("value"))
    if value is not None:
        result.append((value, candidate, True))
    for alternative in candidate.get("alternatives", []):
        if not isinstance(alternative, dict) or alternative.get("status") not in {"observed", "uncertain"}:
            continue
        value = normalize(alternative.get("value"))
        if value is not None:
            result.append((value, candidate, True))
    return result


def _amount(value: Any) -> Decimal | None:
    if not isinstance(value, str):
        return None
    try:
        amount = Decimal(value)
    except InvalidOperation:
        return None
    return amount if amount.is_finite() else None


def _currency(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip().upper()
    return value if re.fullmatch(r"[A-Z]{3}", value) else None


def _date(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value.strip()).isoformat()
    except ValueError:
        return None


def _merchant(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(re.findall(r"[\w]+", value.casefold(), flags=re.UNICODE))
    return normalized or None


def _field_match(record: dict[str, Any], name: str, normalize) -> Any:
    candidate = record.get("fields", {}).get(name)
    return normalize(_candidate_value(candidate)) if isinstance(candidate, dict) else None


def _first_observed_field(record: dict[str, Any], names: tuple[str, ...], normalize):
    fields = record.get("fields", {})
    for name in names:
        candidate = fields.get(name)
        if isinstance(candidate, dict):
            value = normalize(_candidate_value(candidate))
            if value is not None:
                return name, candidate, value
    return None, None, None


def _validate_statement_line(line: Any, statement_hash: str, page_numbers: set[int]) -> dict[str, Any]:
    if not isinstance(line, dict):
        raise ReconciliationError("statement line must be an object")
    line_id = _valid_id(line.get("line_id"), "statement line ID")
    for field in _LINE_FIELDS:
        if field in line:
            _validate_candidate(line[field], label=f"line {field}", expected_hash=statement_hash, page_numbers=page_numbers)
    if not any(
        isinstance(line.get(field), dict) and line[field].get("evidence")
        for field in _LINE_FIELDS
    ):
        raise ReconciliationError("statement line requires source evidence")
    evidence_digest = _canonical_digest({"line_id": line_id, "fields": {key: line.get(key) for key in _LINE_FIELDS if key in line}})
    return {"line_id": line_id, "evidence_sha256": evidence_digest}


def build_reconciliation(
    case_id: str,
    statement_id: str,
    statement_hash: str,
    statement_lines: list[dict],
    attachments: list[dict],
    documents: Mapping[str, dict],
    *,
    source_set_revision: str,
) -> dict:
    """Build deterministic ranked candidate suggestions with source bindings."""
    case_id = _valid_id(case_id, "case ID")
    statement_id = _valid_id(statement_id, "statement document ID")
    statement_hash = _valid_hash(statement_hash, "statement source hash")
    source_set_revision = _valid_hash(source_set_revision, "source-set revision")
    if not isinstance(statement_lines, list) or not statement_lines:
        raise ReconciliationError("statement lines must be a non-empty array")
    if not isinstance(attachments, list) or not isinstance(documents, Mapping):
        raise ReconciliationError("attachments and documents have invalid types")
    statement = documents.get(statement_id)
    if _validate_document(statement_id, statement) != statement_hash:
        raise ReconciliationError("statement hash does not match its source document")
    statement_pages = {page["page_number"] for page in statement["pages"]}

    line_bindings: list[dict[str, str]] = []
    seen_line_ids: set[str] = set()
    for line in statement_lines:
        binding = _validate_statement_line(line, statement_hash, statement_pages)
        if binding["line_id"] in seen_line_ids:
            raise ReconciliationError("statement line IDs must be unique")
        seen_line_ids.add(binding["line_id"])
        line_bindings.append(binding)

    attachment_bindings = []
    selected: list[tuple[dict[str, Any], dict[str, Any]]] = []
    seen_attachment_ids: set[str] = set()
    for item in attachments:
        if not isinstance(item, dict) or item.get("included") is not True:
            raise ReconciliationError("attachments must be explicitly included for reconciliation")
        document_id = _valid_id(item.get("document_id"), "attachment document ID")
        if document_id == statement_id or document_id in seen_attachment_ids:
            raise ReconciliationError("supporting document IDs must be unique and differ from the statement")
        seen_attachment_ids.add(document_id)
        record = documents.get(document_id)
        digest = _validate_document(document_id, record)
        if record.get("document_family") == "expense_report":
            raise ReconciliationError("another expense statement cannot be supporting evidence")
        attachment_bindings.append({"document_id": document_id, "source_sha256": digest})
        selected.append((attachment_bindings[-1], record))

    statement_binding = {"document_id": statement_id, "source_sha256": statement_hash}
    case_revision = _revision_digest(
        case_id, statement_binding, attachment_bindings, line_bindings, source_set_revision,
    )
    line_results = []
    suggested_document_ids: set[str] = set()
    for line, line_binding in zip(statement_lines, line_bindings, strict=True):
        line_amount = _amount(_candidate_value(line.get("amount", {})))
        line_currency = _currency(_candidate_value(line.get("currency", {})))
        possible_line_amounts = _candidate_possible_values(line.get("amount", {}), _amount)
        possible_line_currencies = _candidate_possible_values(line.get("currency", {}), _currency)
        line_date = _date(_candidate_value(line.get("date", {})))
        line_merchant = _merchant(_candidate_value(line.get("merchant", {})))
        uncertain = any(
            isinstance(line.get(field), dict)
            and line[field].get("status") in {"uncertain", "unreadable"}
            for field in _LINE_FIELDS
        )
        suggestions = []
        amount_conflicts = []
        for binding, record in selected:
            amount_name, amount_candidate, doc_amount = _first_observed_field(record, ("total_amount", "amount_due"), _amount)
            currency_name, currency_candidate, doc_currency = _first_observed_field(record, ("currency",), _currency)
            date_name, date_candidate, doc_date = _first_observed_field(
                record, ("transaction_date", "issue_date", "invoice_date", "document_date"), _date
            )
            merchant_name, merchant_candidate, doc_merchant = _first_observed_field(record, ("merchant_name",), _merchant)
            match_amount_name = amount_name or next((
                name for name in ("total_amount", "amount_due")
                if _candidate_possible_values(record.get("fields", {}).get(name, {}), _amount)
            ), None)
            match_currency_name = currency_name or next((
                name for name in ("currency",)
                if _candidate_possible_values(record.get("fields", {}).get(name, {}), _currency)
            ), None)
            reasons = []
            matched_fields = {}
            amount_equal = line_amount is not None and doc_amount is not None and line_amount == doc_amount
            currency_equal = line_currency is not None and doc_currency is not None and line_currency == doc_currency
            date_equal = line_date is not None and doc_date is not None and line_date == doc_date
            merchant_equal = line_merchant is not None and doc_merchant is not None and line_merchant == doc_merchant
            # Missing merchant data weakens these signals but does not erase
            # amount/date/currency evidence. A known disagreement still blocks
            # the conflict signal; every result remains a review suggestion.
            merchant_compatible = (
                line_merchant is None or doc_merchant is None or merchant_equal
            )
            possible_doc_amounts = _candidate_possible_values(
                record.get("fields", {}).get(match_amount_name, {}) if match_amount_name else {}, _amount,
            )
            possible_doc_currencies = _candidate_possible_values(
                record.get("fields", {}).get(match_currency_name, {}) if match_currency_name else {}, _currency,
            )
            amount_pair = next((
                (line_value, doc_value)
                for line_value in possible_line_amounts for doc_value in possible_doc_amounts
                if line_value[0] == doc_value[0]
            ), None)
            currency_pair = next((
                (line_value, doc_value)
                for line_value in possible_line_currencies for doc_value in possible_doc_currencies
                if line_value[0] == doc_value[0]
            ), None)
            if amount_pair is not None and currency_pair is not None:
                is_possible = any(item[2] for pair in (amount_pair, currency_pair) for item in pair)
                reasons.append(
                    "possible_amount_and_currency_match" if is_possible else "amount_and_currency_match"
                )
                matched_fields[match_amount_name] = deepcopy(amount_pair[1][1])
                matched_fields[match_currency_name] = deepcopy(currency_pair[1][1])
            if date_equal:
                reasons.append("date_match")
                matched_fields[date_name] = deepcopy(date_candidate)
            if merchant_equal:
                reasons.append("merchant_match")
                matched_fields[merchant_name] = deepcopy(merchant_candidate)
            if line_amount is not None and doc_amount is not None and line_amount != doc_amount:
                if date_equal and merchant_compatible and line_currency is not None and line_currency == doc_currency:
                    amount_conflicts.append(binding["document_id"])
                    reasons.append("amount_conflict")
                    matched_fields[amount_name] = deepcopy(amount_candidate)
                    matched_fields[currency_name] = deepcopy(currency_candidate)
            if amount_equal and date_equal and merchant_compatible and line_currency is not None and doc_currency is not None and line_currency != doc_currency:
                reasons.append("currency_conflict")
                matched_fields[amount_name] = deepcopy(amount_candidate)
                matched_fields[currency_name] = deepcopy(currency_candidate)
                matched_fields[date_name] = deepcopy(date_candidate)
                if merchant_name:
                    matched_fields[merchant_name] = deepcopy(merchant_candidate)
            if amount_equal and currency_equal and merchant_compatible and line_date is not None and doc_date is not None and line_date != doc_date:
                reasons.append("date_conflict")
                matched_fields[amount_name] = deepcopy(amount_candidate)
                matched_fields[currency_name] = deepcopy(currency_candidate)
                matched_fields[date_name] = deepcopy(date_candidate)
                if merchant_name is not None:
                    matched_fields[merchant_name] = deepcopy(merchant_candidate)
            if reasons:
                suggestions.append({
                    "document_id": binding["document_id"],
                    "source_sha256": binding["source_sha256"],
                    "reasons": reasons,
                    "supporting_fields": matched_fields,
                    "signal_count": sum(not reason.endswith("_conflict") for reason in reasons),
                })
                suggested_document_ids.add(binding["document_id"])
        # Preserve equal-signal ambiguity while displaying stronger evidence first.
        suggestions.sort(key=lambda item: (
            -item["signal_count"],
            sum(reason.endswith("_conflict") for reason in item["reasons"]),
            sum(reason.startswith("possible_") for reason in item["reasons"]),
            item["document_id"],
        ))
        findings = []
        if not suggestions:
            findings.append("missing_support")
        if uncertain:
            findings.append("uncertain_statement_fields")
        if amount_conflicts:
            findings.append("amount_conflict")
        if any("currency_conflict" in item["reasons"] for item in suggestions):
            findings.append("currency_conflict")
        if any("date_conflict" in item["reasons"] for item in suggestions):
            findings.append("date_conflict")
        if len(suggestions) > 1 and suggestions[0]["signal_count"] == suggestions[1]["signal_count"]:
            findings.append("ambiguous_candidates")
        for suggestion in suggestions:
            suggestion.pop("signal_count")
        line_results.append({
            "line_id": line_binding["line_id"],
            "evidence_sha256": line_binding["evidence_sha256"],
            "fields": deepcopy({key: line[key] for key in _LINE_FIELDS if key in line}),
            "status": "unreviewed",
            "current_review_event_id": None,
            "suggestions": suggestions,
            "findings": findings,
        })

    claim_groups: dict[tuple[Any, ...], list[str]] = {}
    for line in statement_lines:
        signature = (
            _amount(_candidate_value(line.get("amount", {}))),
            _currency(_candidate_value(line.get("currency", {}))),
            _date(_candidate_value(line.get("date", {}))),
            _merchant(_candidate_value(line.get("merchant", {}))),
        )
        # The extractor intentionally does not guess a merchant. Amount, date,
        # currency, and (when available) merchant form a conservative duplicate
        # key; absent merchants still allow a possible-duplicate warning.
        if all(value is not None for value in signature[:3]):
            claim_groups.setdefault(signature, []).append(line["line_id"])
    possible_duplicate_groups = []
    for signature, line_ids in claim_groups.items():
        if len(line_ids) > 1:
            for line_result in line_results:
                if line_result["line_id"] in line_ids:
                    line_result["findings"].append("possible_duplicate_claim")
            possible_duplicate_groups.append({
                "line_ids": line_ids,
                "amount": str(signature[0]),
                "currency": signature[1],
                "date": signature[2],
                "merchant": signature[3],
            })

    duplicate_groups: dict[str, list[str]] = {}
    for binding in attachment_bindings:
        duplicate_groups.setdefault(binding["source_sha256"], []).append(binding["document_id"])
    duplicates = [
        {"source_sha256": digest, "document_ids": ids}
        for digest, ids in sorted(duplicate_groups.items()) if len(ids) > 1
    ]
    return {
        "reconciliation_version": "0.1.0",
        "case_id": case_id,
        "case_revision": case_revision,
        "source_set_revision": source_set_revision,
        "statement": statement_binding,
        "attachments": attachment_bindings,
        "lines": line_results,
        "duplicate_source_groups": duplicates,
        "possible_duplicate_claim_groups": possible_duplicate_groups,
        "unused_document_ids": sorted(seen_attachment_ids - suggested_document_ids),
        "review_events": [],
    }


def validate_reconciliation(reconciliation: dict, documents: Mapping[str, dict]) -> None:
    """Validate bindings, line digests, and append-only review event integrity."""
    if not isinstance(reconciliation, dict) or reconciliation.get("reconciliation_version") != "0.1.0":
        raise ReconciliationError("reconciliation version is invalid")
    statement = reconciliation.get("statement")
    if not isinstance(statement, dict):
        raise ReconciliationError("reconciliation statement binding is invalid")
    statement_id = _valid_id(statement.get("document_id"), "statement document ID")
    statement_hash = _valid_hash(statement.get("source_sha256"), "statement hash")
    record = documents.get(statement_id)
    if _validate_document(statement_id, record) != statement_hash:
        raise ReconciliationError("statement source binding changed")
    bindings = reconciliation.get("attachments")
    if not isinstance(bindings, list):
        raise ReconciliationError("attachment source bindings are invalid")
    for binding in bindings:
        if not isinstance(binding, dict):
            raise ReconciliationError("attachment source binding is invalid")
        document_id = _valid_id(binding.get("document_id"), "attachment document ID")
        digest = _valid_hash(binding.get("source_sha256"), "attachment hash")
        if _validate_document(document_id, documents.get(document_id)) != digest:
            raise ReconciliationError("attachment source binding changed")
    lines = reconciliation.get("lines")
    source_set_revision = _valid_hash(reconciliation.get("source_set_revision"), "source-set revision")
    if not isinstance(lines, list):
        raise ReconciliationError("reconciliation lines are invalid")
    line_ids = set()
    statement_pages = {page["page_number"] for page in record["pages"]}
    for line in lines:
        if not isinstance(line, dict):
            raise ReconciliationError("reconciliation line is invalid")
        line_id = _valid_id(line.get("line_id"), "line ID")
        if line_id in line_ids or not _valid_hash(line.get("evidence_sha256"), "line evidence digest"):
            raise ReconciliationError("reconciliation line binding is invalid")
        fields = line.get("fields")
        if not isinstance(fields, dict):
            raise ReconciliationError("reconciliation line fields are invalid")
        binding = _validate_statement_line({"line_id": line_id, **fields}, statement_hash, statement_pages)
        if binding["evidence_sha256"] != line["evidence_sha256"]:
            raise ReconciliationError("reconciliation line evidence digest changed")
        line_ids.add(line_id)
    revision_lines = [{"line_id": item["line_id"], "evidence_sha256": item["evidence_sha256"]} for item in lines]
    if _revision_digest(
        _valid_id(reconciliation.get("case_id"), "case ID"),
        {"document_id": statement_id, "source_sha256": statement_hash},
        [{"document_id": item["document_id"], "source_sha256": item["source_sha256"]} for item in bindings],
        revision_lines,
        source_set_revision,
    ) != reconciliation.get("case_revision"):
        raise ReconciliationError("case revision digest does not match its source bindings")
    events = reconciliation.get("review_events")
    if not isinstance(events, list):
        raise ReconciliationError("review events must be an array")
    event_ids = set()
    for sequence, event in enumerate(events, start=1):
        _validate_review_event(event, sequence)
        if event.get("event_id") in event_ids:
            raise ReconciliationError("review event IDs must be unique")
        event_ids.add(event.get("event_id"))
        if event.get("case_revision") == reconciliation.get("case_revision"):
            line = next((item for item in lines if item["line_id"] == event.get("line_id")), None)
            if line is None or line["evidence_sha256"] != event.get("line_evidence_sha256"):
                raise ReconciliationError("review event line evidence binding changed")
            if not isinstance(event.get("candidate_sources"), list):
                raise ReconciliationError("review event candidate sources are invalid")
            for source in event["candidate_sources"]:
                if not isinstance(source, dict) or not any(
                    source.get("document_id") == binding["document_id"]
                    and source.get("source_sha256") == binding["source_sha256"]
                    for binding in bindings
                ):
                    raise ReconciliationError("review event candidate source is not bound to this revision")
    latest: dict[str, dict[str, Any]] = {}
    for event in events:
        if event.get("case_revision") == reconciliation.get("case_revision"):
            latest[event["line_id"]] = event
    for line in lines:
        current_event = latest.get(line["line_id"])
        expected_status = current_event["action"] if current_event else "unreviewed"
        expected_event_id = current_event["event_id"] if current_event else None
        if line.get("status") != expected_status or line.get("current_review_event_id") != expected_event_id:
            raise ReconciliationError("current line review projection does not match append-only events")
    rebuilt = build_reconciliation(
        reconciliation["case_id"],
        statement_id,
        statement_hash,
        [{"line_id": item["line_id"], **item["fields"]} for item in lines],
        [{"document_id": item["document_id"], "included": True} for item in bindings],
        documents,
        source_set_revision=source_set_revision,
    )
    current_payload = {key: value for key, value in reconciliation.items() if key != "review_events"}
    rebuilt_payload = {key: value for key, value in rebuilt.items() if key != "review_events"}
    for line in rebuilt_payload["lines"]:
        current = next(item for item in current_payload["lines"] if item["line_id"] == line["line_id"])
        line["status"] = current.get("status")
        line["current_review_event_id"] = current.get("current_review_event_id")
    if rebuilt_payload != current_payload:
        raise ReconciliationError("reconciliation suggestions do not match their source-bound inputs")


def append_line_review(
    reconciliation: dict,
    *,
    expected_case_revision: str,
    line_id: str,
    expected_line_evidence_sha256: str,
    action: str,
    candidate_sources: list[dict],
    event_id: str,
    reviewer_note: str | None,
) -> dict:
    """Append a source- and revision-bound human review event, idempotently."""
    result = deepcopy(reconciliation)
    if not isinstance(result, dict) or expected_case_revision != result.get("case_revision"):
        raise ReconciliationError("expected case revision is stale")
    _valid_id(event_id, "review event ID")
    _valid_id(line_id, "statement line ID")
    _valid_hash(expected_line_evidence_sha256, "line evidence digest")
    if action not in _ACTIONS or not isinstance(candidate_sources, list):
        raise ReconciliationError("review action or candidate sources are invalid")
    if reviewer_note is not None and (not isinstance(reviewer_note, str) or len(reviewer_note) > 2000):
        raise ReconciliationError("reviewer note is invalid")
    line = next((item for item in result.get("lines", []) if item.get("line_id") == line_id), None)
    if line is None or line.get("evidence_sha256") != expected_line_evidence_sha256:
        raise ReconciliationError("line evidence binding is stale")
    if action == "confirmed" and not candidate_sources:
        raise ReconciliationError("confirmation requires a selected supporting source")
    if action == "excluded_with_reason" and not (reviewer_note and reviewer_note.strip()):
        raise ReconciliationError("exclusion requires a reviewer reason")
    allowed_sources = {item["document_id"]: item["source_sha256"] for item in result.get("attachments", [])}
    normalized_sources = []
    seen_sources = set()
    for item in candidate_sources:
        if not isinstance(item, dict):
            raise ReconciliationError("review candidate source is invalid")
        document_id = _valid_id(item.get("document_id"), "review candidate document ID")
        digest = _valid_hash(item.get("source_sha256"), "review candidate source hash")
        if document_id in seen_sources or allowed_sources.get(document_id) != digest:
            raise ReconciliationError("review candidate source is not bound to this case")
        seen_sources.add(document_id)
        normalized_sources.append({"document_id": document_id, "source_sha256": digest})
    body = {
        "event_id": event_id,
        "case_revision": expected_case_revision,
        "line_id": line_id,
        "line_evidence_sha256": expected_line_evidence_sha256,
        "action": action,
        "candidate_sources": normalized_sources,
        "reviewer_note": reviewer_note,
    }
    digest = _canonical_digest(body)
    events = result.setdefault("review_events", [])
    bindings = result.get("attachments", [])
    current_lines = result.get("lines", [])
    seen_event_ids = set()
    for sequence, prior_event in enumerate(events, start=1):
        _validate_review_event(prior_event, sequence)
        if prior_event["event_id"] in seen_event_ids:
            raise ReconciliationError("review event IDs must be unique")
        seen_event_ids.add(prior_event["event_id"])
        if prior_event["case_revision"] == result.get("case_revision"):
            prior_line = next((item for item in current_lines if item.get("line_id") == prior_event["line_id"]), None)
            if prior_line is None or prior_line.get("evidence_sha256") != prior_event["line_evidence_sha256"]:
                raise ReconciliationError("existing review event line binding is stale")
            for source in prior_event["candidate_sources"]:
                if not any(
                    source["document_id"] == binding.get("document_id")
                    and source["source_sha256"] == binding.get("source_sha256")
                    for binding in bindings
                ):
                    raise ReconciliationError("existing review event source is not bound to this revision")
    latest_events = {}
    for prior_event in events:
        if prior_event["case_revision"] == result.get("case_revision"):
            latest_events[prior_event["line_id"]] = prior_event
    for existing_line in current_lines:
        latest = latest_events.get(existing_line.get("line_id"))
        if (
            existing_line.get("status") != (latest["action"] if latest else "unreviewed")
            or existing_line.get("current_review_event_id") != (latest["event_id"] if latest else None)
        ):
            raise ReconciliationError("current line review projection does not match append-only events")
    prior = next((event for event in events if event.get("event_id") == event_id), None)
    if prior is not None:
        if prior.get("event_sha256") != digest:
            raise ReconciliationError("conflicting review event replay")
        return result
    event = {**body, "sequence": len(events) + 1, "event_sha256": digest}
    _validate_review_event(event, len(events) + 1)
    events.append(event)
    line["status"] = action
    line["current_review_event_id"] = event_id
    # The store performs full source-record validation before commit. Here we
    # protect the append operation against malformed revision/event history
    # without pretending this API has access to the archived source records.
    line_bindings = []
    for item in result.get("lines", []):
        fields = item.get("fields")
        if not isinstance(fields, dict):
            raise ReconciliationError("reconciliation line fields are invalid")
        evidence_pages = {
            evidence.get("page_number")
            for candidate in fields.values() if isinstance(candidate, dict)
            for evidence in candidate.get("evidence", []) if isinstance(evidence, dict)
        }
        binding = _validate_statement_line(
            {"line_id": item.get("line_id"), **fields},
            result["statement"]["source_sha256"], evidence_pages,
        )
        if binding["evidence_sha256"] != item.get("evidence_sha256"):
            raise ReconciliationError("reconciliation line evidence digest changed")
        line_bindings.append(binding)
    expected_revision = _revision_digest(
        result["case_id"], result["statement"], result.get("attachments", []), line_bindings,
        _valid_hash(result.get("source_set_revision"), "source-set revision"),
    )
    if expected_revision != result.get("case_revision"):
        raise ReconciliationError("case revision digest does not match its source bindings")
    return result

