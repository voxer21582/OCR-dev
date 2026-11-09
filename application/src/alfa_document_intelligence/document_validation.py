"""Deterministic document-level consistency checks.

These checks report findings only. They do not alter extracted fields or make
administrative, reimbursement, payment, or accounting decisions.
"""
from __future__ import annotations

from datetime import date
import json
import re
from typing import Any

from .contracts import validate_document_record

_RULES = {
    "hotel_document": (
        "check_in_date",
        "check_out_date",
        "hotel-stay-date-order",
        ("hotel_stay_dates_require_review", "hotel_stay_date_order_valid", "hotel_checkout_precedes_checkin"),
    ),
    "expense_report": (
        "trip_start_date",
        "trip_end_date",
        "trip-date-order",
        ("trip_dates_require_review", "trip_date_order_valid", "trip_end_precedes_start"),
    ),
}
_TAX_ARITHMETIC_FAMILIES = {"invoice", "fiscal_receipt", "hotel_document"}
_TAX_ARITHMETIC_FIELDS = ("taxable_base", "vat_amount", "total_amount")
# Bound only tax-amount arithmetic; this is not a total input-size limit.
# Longer candidates require review even if their textual amount is valid.
_MAX_CENT_AMOUNT_LENGTH = 128
_CENT_AMOUNT = re.compile(r"^-?(?:0|[1-9][0-9]*)\.[0-9]{2}$")


class DocumentValidationError(ValueError):
    """The record is malformed or not ready for document validation."""


def _candidate_evidence(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = list(candidate.get("evidence", []))
    for alternative in candidate.get("alternatives", []):
        evidence.extend(alternative.get("evidence", []))
    unique: dict[str, dict[str, Any]] = {}
    for item in evidence:
        unique[json.dumps(item, ensure_ascii=False, sort_keys=True)] = item
    return [unique[key] for key in sorted(unique)]


def _date_value(candidate: dict[str, Any]) -> date | None:
    if candidate.get("status") != "observed":
        return None
    value = candidate.get("value")
    if not isinstance(value, str):
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == value else None



def _unique_evidence(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        for item in _candidate_evidence(candidate):
            unique[json.dumps(item, ensure_ascii=False, sort_keys=True)] = item
    return [unique[key] for key in sorted(unique)]


def _observed_cents(candidate: dict[str, Any]) -> int | None:
    if candidate.get("status") != "observed":
        return None
    value = candidate.get("value")
    if (
        not isinstance(value, str)
        or len(value) > _MAX_CENT_AMOUNT_LENGTH
        or not _CENT_AMOUNT.fullmatch(value)
    ):
        return None
    # The bounded canonical form converts exactly, independent of Decimal context.
    return int(value.replace(".", ""))


def _tax_arithmetic_finding(fields: dict[str, Any]) -> dict[str, Any] | None:
    if not all(name in fields for name in _TAX_ARITHMETIC_FIELDS):
        return None
    candidates = [fields[name] for name in _TAX_ARITHMETIC_FIELDS]
    values = [_observed_cents(candidate) for candidate in candidates]
    evidence = _unique_evidence(candidates)
    if all(value is not None for value in values) and values[0] + values[1] == values[2]:
        outcome, severity, message_code = "pass", "info", "taxable_base_vat_sum_matches_total"
    else:
        # A difference can reflect discounts, charges, rounding, or uncertain
        # extraction; it is a review signal, never a fiscal failure verdict.
        outcome, severity, message_code = (
            "indeterminate", "warning", "tax_total_arithmetic_requires_review"
        )
    return {
        "rule_id": "taxable-base-vat-total-arithmetic",
        "rule_version": "1",
        "dimension": "amount_arithmetic_consistency",
        "severity": severity,
        "outcome": outcome,
        "evidence": evidence,
        "field_names": list(_TAX_ARITHMETIC_FIELDS),
        "message_code": message_code,
    }

def _required_custom_field_findings(record: dict[str, Any]) -> list[dict[str, Any]]:
    fields = record["fields"]
    family_candidate = fields.get("document_family_candidates")
    if not isinstance(family_candidate, dict):
        return []
    active_family_ids = {
        alternative.get("value")
        for alternative in family_candidate.get("alternatives", [])
        if isinstance(alternative, dict)
        and alternative.get("status") == "observed"
        and isinstance(alternative.get("value"), str)
        and alternative["value"].startswith("custom_")
    }
    if not active_family_ids:
        return []

    findings: list[dict[str, Any]] = []
    seen_fields: set[str] = set()
    for snapshot in record.get("document_family_definitions", []):
        family = snapshot.get("family", {})
        family_id = family.get("id")
        if family_id not in active_family_ids:
            continue
        for definition in family.get("fields", []):
            if definition.get("required") is not True:
                continue
            field_name = f"{family_id}_{definition['id']}"
            if field_name in seen_fields:
                continue
            seen_fields.add(field_name)
            candidate = fields.get(field_name)
            if isinstance(candidate, dict) and candidate.get("status") == "observed":
                continue
            missing = not isinstance(candidate, dict) or candidate.get("status") == "absent"
            findings.append({
                "rule_id": "required-custom-field",
                "rule_version": "1",
                "dimension": "document_consistency",
                "severity": "warning",
                "outcome": "indeterminate",
                "evidence": [] if missing else _candidate_evidence(candidate),
                "field_names": [field_name],
                "message_code": (
                    "required_custom_field_missing"
                    if missing else "required_custom_field_requires_review"
                ),
            })
    return findings

def validate_document_consistency(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Check supported document relationships and return evidence-bound findings.

    Hotel stay and expense-report trip dates are ordered when both are observed ISO dates. For invoices,
    fiscal receipts, and hotel documents, an arithmetic-only check compares
    explicitly represented taxable base plus VAT amount with total. A mismatch,
    an uncertain value, or a non-canonical amount is indeterminate and requires
    review because other charges, discounts, or rounding may explain it. Neither
    rule establishes tax treatment, fiscal validity, or administrative approval.
    """
    contract_issues = validate_document_record(record)
    if contract_issues:
        raise DocumentValidationError("record contract failed: " + "; ".join(contract_issues))
    fields = record["fields"]
    findings: list[dict[str, Any]] = _required_custom_field_findings(record)
    rule = _RULES.get(record.get("document_family"))
    if rule is not None:
        start_name, end_name, rule_id, message_codes = rule
        if start_name in fields and end_name in fields:
            start, end = fields[start_name], fields[end_name]
            evidence = _unique_evidence([start, end])
            start_value, end_value = _date_value(start), _date_value(end)
            if start_value is None or end_value is None:
                outcome, severity, message_code = (
                    "indeterminate", "warning", message_codes[0]
                )
            elif start_value <= end_value:
                outcome, severity, message_code = "pass", "info", message_codes[1]
            else:
                outcome, severity, message_code = "fail", "error", message_codes[2]
            findings.append({
                "rule_id": rule_id,
                "rule_version": "1",
                "dimension": "date_consistency",
                "severity": severity,
                "outcome": outcome,
                "evidence": evidence,
                "field_names": [start_name, end_name],
                "message_code": message_code,
            })
    if record.get("document_family") in _TAX_ARITHMETIC_FAMILIES:
        finding = _tax_arithmetic_finding(fields)
        if finding is not None:
            findings.append(finding)
    return findings
