"""Score a case reconciliation export against the synthetic benchmark manifest.

The result holds only counts and receipt numbers, never document text, so it
can be written to ``docs/evidence``. Each pair is ``[achieved, expected]``.
"""
from __future__ import annotations

import re
from typing import Any

_ROW_LABEL = re.compile(r"Spesa\s*(\d{1,3})")
_MATCH_REASONS = {"amount_and_currency_match", "possible_amount_and_currency_match"}
_CONFLICT_REASONS = {
    "amount_conflict", "possible_amount_conflict", "currency_conflict", "date_conflict",
}
_HEADER = re.compile(r"Pagina\s*\d+\s*di\s*\d+", re.IGNORECASE)


def _field_value(line: dict[str, Any], name: str) -> Any:
    candidate = line.get("fields", {}).get(name)
    return candidate.get("value") if isinstance(candidate, dict) else None


def _row_number(line: dict[str, Any]) -> int | None:
    description = _field_value(line, "description")
    match = _ROW_LABEL.search(description) if isinstance(description, str) else None
    return int(match.group(1)) if match else None


def _first_reading(line: dict[str, Any]) -> tuple[Any, Any]:
    candidate = line.get("fields", {}).get("date")
    if not isinstance(candidate, dict) or candidate.get("status") != "uncertain":
        return None, None
    alternatives = candidate.get("alternatives") or []
    if not alternatives or not isinstance(alternatives[0], dict):
        return None, None
    first = alternatives[0]
    return first.get("value"), (first.get("normalization") or {}).get("rule_id")


def score_case_export(export: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    """Return numeric benchmark measures for one case export."""
    receipt_by_sha = {
        manifest["files"][item["file"]]: item["receipt"] for item in manifest["receipts"]
    }
    receipt_by_document = {
        item["document_id"]: receipt_by_sha.get(item["source_sha256"])
        for item in export.get("attachments", [])
    }
    expected = {item["receipt"]: item["expected"] for item in manifest["receipts"]}
    rows = {row["row"]: row for row in manifest["statement_rows"]}

    lines_by_row: dict[int, dict[str, Any]] = {}
    headers = ambiguous = 0
    for line in export.get("lines", []):
        description = _field_value(line, "description")
        if isinstance(description, str) and _HEADER.search(description):
            headers += 1
        if "ambiguous_candidates" in line.get("findings", []):
            ambiguous += 1
        row = _row_number(line)
        if row in rows and row not in lines_by_row:
            lines_by_row[row] = line

    matched = possible_only = conflicts = missing = hints = 0
    match_total = conflict_total = missing_total = hint_total = 0
    for number, row in rows.items():
        line = lines_by_row.get(number)
        receipt = row["receipt"]
        kind = expected.get(receipt) if receipt is not None else "missing_support"
        suggestions = line.get("suggestions", []) if line else []
        findings = line.get("findings", []) if line else []
        first = suggestions[0] if suggestions else None
        first_receipt = receipt_by_sha.get(first.get("source_sha256")) if first else None
        if kind == "match":
            match_total += 1
            reasons = set(first.get("reasons", [])) if first_receipt == receipt else set()
            if reasons & _MATCH_REASONS and not reasons & _CONFLICT_REASONS:
                matched += 1
                if "amount_and_currency_match" not in reasons:
                    possible_only += 1
        elif kind == "amount_conflict":
            conflict_total += 1
            own = [
                item for item in suggestions
                if receipt_by_sha.get(item.get("source_sha256")) == receipt
            ]
            if any({"amount_conflict", "possible_amount_conflict"} & set(item.get("reasons", [])) for item in own):
                conflicts += 1
        elif kind == "missing_support":
            missing_total += 1
            if "missing_support" in findings:
                missing += 1
        day, month = int(row["date"][-2:]), int(row["date"][5:7])
        # dd/mm is ambiguous only when both readings are dates and differ.
        if day <= 12 and day != month:
            hint_total += 1
            value, rule = _first_reading(line) if line else (None, None)
            if value == row["date"] and rule == "date-dmy-hint":
                hints += 1

    unused = sorted(
        receipt_by_document[document_id]
        for document_id in export.get("unused_document_ids", [])
        if receipt_by_document.get(document_id) is not None
    )
    return {
        "statement_lines_found": [len(lines_by_row), len(rows)],
        "header_lines_proposed": headers,
        "correct_receipt_ranked_first": [matched, match_total],
        # Of those, how many rest only on uncertain OCR values (possible_… reasons).
        "correct_receipt_first_possible_only": possible_only,
        "amount_conflicts_flagged": [conflicts, conflict_total],
        "missing_support_rows": [missing, missing_total],
        "unused_receipts": unused,
        "ambiguous_dates_with_correct_hint": [hints, hint_total],
        "ambiguous_candidates": ambiguous,
    }
