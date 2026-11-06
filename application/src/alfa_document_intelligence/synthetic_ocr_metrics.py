"""Quality metrics for the deliberately small generated OCR corpus.

This measures OCR text errors and downstream evidence-bound field candidate recall.
It is a synthetic integration benchmark, not representative performance evidence.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from .ocr_adapter import OCRPageResult
from .semantic_proposals import propose_common_fields

SYNTHETIC_TEXT_GOLD: dict[str, tuple[str, ...]] = {
    "invoice-it": ("FATTURA", "FORNITORE: HOTEL AURORA", "N DOCUMENTO: 2026-001",
                   "IMPONIBILE EUR 100.00", "IVA 22%", "TOTALE EUR 122.00"),
    "fiscal-receipt-it": ("RICEVUTA FISCALE", "ESERCENTE: CAFE ROMA", "DATA 14 10 2026",
                          "TOTALE EUR 12.50"),
    "parking-receipt-it": ("RICEVUTA PARCHEGGIO", "INGRESSO 14 10 2026",
                           "USCITA 14 10 2026", "TOTALE EUR 8.00"),
    "hotel-invoice-en": ("HOTEL INVOICE", "SUPPLIER: CITY HOTEL", "CHECK IN 12 10 2026",
                         "CHECK OUT 14 10 2026", "TOTAL EUR 244.00"),
    "hotel-receipt-en": ("HOTEL RECEIPT", "MERCHANT: NORTH HOTEL", "DATE 14 10 2026",
                         "TOTAL EUR 180.00"),
    "pos-payment-slip": ("CARD PAYMENT SLIP", "MERCHANT: CAFE ROMA", "DATE 14 10 2026",
                         "AMOUNT EUR 12.50", "PAYMENT APPROVED"),
    "invoice-en": ("INVOICE", "SUPPLIER: ACME SERVICES", "INVOICE NUMBER A-2026-19",
                   "TAXABLE BASE EUR 50.00", "VAT 22%", "GRAND TOTAL EUR 61.00"),
}

# Authored independently from PaddleOCR output. Only fields visibly represented in
# the generated page are scored. POS assertions guard role separation.
SYNTHETIC_FIELD_GOLD: dict[str, dict[str, str]] = {
    "invoice-it": {
        "document_family_candidates": "invoice", "supplier_name": "HOTEL AURORA",
        "taxable_base": "100.00", "vat_rate": "22", "total_amount": "122.00", "currency": "EUR",
    },
    "fiscal-receipt-it": {
        "document_family_candidates": "fiscal_receipt", "merchant_name": "CAFE ROMA",
        "date_candidates": "2026-10-14", "total_amount": "12.50", "currency": "EUR",
    },
    "parking-receipt-it": {
        "document_family_candidates": "parking_receipt", "date_candidates": "2026-10-14",
        "total_amount": "8.00", "currency": "EUR",
    },
    "hotel-invoice-en": {
        "document_family_candidates": "hotel_document", "supplier_name": "CITY HOTEL",
        "check_in_date": "2026-10-12", "check_out_date": "2026-10-14",
        "total_amount": "244.00", "currency": "EUR",
    },
    "hotel-receipt-en": {
        "document_family_candidates": "hotel_document", "merchant_name": "NORTH HOTEL",
        "date_candidates": "2026-10-14", "total_amount": "180.00", "currency": "EUR",
    },
    "pos-payment-slip": {
        "document_family_candidates": "pos_slip", "merchant_name": "CAFE ROMA",
        "date_candidates": "2026-10-14", "amount_candidates": "12.50", "currency": "EUR",
    },
    "invoice-en": {
        "document_family_candidates": "invoice", "supplier_name": "ACME SERVICES",
        "taxable_base": "50.00", "vat_rate": "22", "total_amount": "61.00", "currency": "EUR",
    },
}
_POS_PROHIBITED_FIELDS = frozenset({
    "total_amount", "taxable_base", "vat_amount", "vat_rate",
    "issue_date", "check_in_date", "check_out_date",
})


def _norm_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def _edit_distance(left: list[str], right: list[str]) -> int:
    previous = list(range(len(right) + 1))
    for i, left_item in enumerate(left, start=1):
        current = [i]
        for j, right_item in enumerate(right, start=1):
            current.append(min(
                current[-1] + 1,
                previous[j] + 1,
                previous[j - 1] + (left_item != right_item),
            ))
        previous = current
    return previous[-1]


def _candidate_values(candidate: dict[str, Any] | None) -> list[str]:
    if not candidate:
        return []
    values: list[str] = []
    if isinstance(candidate.get("value"), str):
        values.append(candidate["value"])
    for alternative in candidate.get("alternatives", []):
        if isinstance(alternative, dict) and isinstance(alternative.get("value"), str):
            values.append(alternative["value"])
    return values


def _evidence_counts(proposals: dict[str, dict[str, Any]], source_sha256: str) -> tuple[int, int]:
    total = supported = 0
    for candidate in proposals.values():
        for reference in candidate.get("evidence", []):
            total += 1
            region = reference.get("region", {})
            if (reference.get("source_sha256") == source_sha256
                    and isinstance(reference.get("page_number"), int)
                    and isinstance(region.get("polygon"), list)
                    and len(region["polygon"]) >= 3):
                supported += 1
    return supported, total


_FIELD_CUES = {
    "supplier_name": re.compile(r"(?i)\b(?:fornitore|supplier|vendor)\b"),
    "total_amount": re.compile(r"(?i)\b(?:totale|grand\s+total|total|amount\s+due)\b"),
    "taxable_base": re.compile(r"(?i)\b(?:imponibile|taxable\s+(?:base|amount)|net\s+amount)\b"),
}


def _failure_diagnostics(
    case_id: str, fields: list[str], tokens: tuple[Any, ...]
) -> list[dict[str, Any]]:
    diagnostics = []
    for field in fields:
        cue = _FIELD_CUES.get(field)
        if cue is None:
            continue
        expected = SYNTHETIC_FIELD_GOLD[case_id][field]
        if field in {"supplier_name"}:
            value_pattern = re.compile(re.escape(expected), re.IGNORECASE)
        else:
            value_pattern = re.compile(r"(?<![\w.,])" + re.escape(expected) + r"(?![\w.,])")
        cue_seen = any(cue.search(token.text) for token in tokens)
        value_seen = any(value_pattern.search(token.text) for token in tokens)
        same_token = any(cue.search(token.text) and value_pattern.search(token.text) for token in tokens)
        diagnostics.append({
            "field": field,
            "cue_seen": cue_seen,
            "value_seen": value_seen,
            "cue_and_value_same_token": same_token,
        })
    return diagnostics


def evaluate_page(
    case_id: str,
    page: OCRPageResult,
    recognized_lines: list[str],
    gold_lines: tuple[str, ...],
) -> dict[str, Any]:
    """Return metrics only; never include OCR text or field values in the report."""
    if case_id not in SYNTHETIC_FIELD_GOLD:
        raise ValueError("unknown synthetic case id")
    proposals = propose_common_fields((page,))
    gold = SYNTHETIC_FIELD_GOLD[case_id]
    field_results: dict[str, dict[str, int]] = {}
    for field, expected in gold.items():
        values = _candidate_values(proposals.get(field))
        normalized_expected = expected.casefold() if field in {
            "merchant_name", "supplier_name", "document_family_candidates", "currency"
        } else expected
        matched = sum(value.casefold() == normalized_expected if field in {
            "merchant_name", "supplier_name", "document_family_candidates", "currency"
        } else value == normalized_expected for value in values)
        field_results[field] = {
            "eligible": 1, "candidate_recalled": int(matched > 0),
            "emitted_candidates": len(values), "matching_candidates": matched,
        }

    prohibited = sorted(
        field for field in _POS_PROHIBITED_FIELDS
        if case_id == "pos-payment-slip" and field in proposals
    )
    source_text = _norm_text(" ".join(gold_lines))
    observed_text = _norm_text(" ".join(recognized_lines))
    char_errors = _edit_distance(list(source_text), list(observed_text))
    word_errors = _edit_distance(source_text.split(), observed_text.split())
    evidence_supported, evidence_total = _evidence_counts(proposals, page.source_sha256)
    return {
        "case_id": case_id,
        "character_errors": char_errors, "gold_characters": len(source_text),
        "word_errors": word_errors, "gold_words": len(source_text.split()),
        "field_results": field_results,
        "missed_fields": sorted(name for name, result in field_results.items()
                                if result["candidate_recalled"] == 0),
        "failed_field_diagnostics": _failure_diagnostics(
            case_id,
            [name for name, result in field_results.items() if result["candidate_recalled"] == 0],
            page.tokens,
        ),
        "character_error_rate": round(char_errors / len(source_text), 6) if source_text else None,
        "word_error_rate": round(word_errors / len(source_text.split()), 6) if source_text.split() else None,
        "uncertain_candidates": sum(
            len(candidate.get("alternatives", []))
            for candidate in proposals.values()
            if candidate.get("status") == "uncertain"
        ),
        "confirmed_candidates": sum(candidate.get("status") == "observed"
                                    for candidate in proposals.values()),
        "evidence_supported": evidence_supported, "evidence_total": evidence_total,
        "pos_prohibited_role_proposals": len(prohibited),
    }


def aggregate_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    if not reports:
        raise ValueError("at least one document report is required")
    chars = sum(row["character_errors"] for row in reports)
    gold_chars = sum(row["gold_characters"] for row in reports)
    words = sum(row["word_errors"] for row in reports)
    gold_words = sum(row["gold_words"] for row in reports)
    fields: dict[str, dict[str, int]] = defaultdict(
        lambda: {"eligible": 0, "candidate_recalled": 0,
                 "emitted_candidates": 0, "matching_candidates": 0}
    )
    for row in reports:
        for name, metrics in row["field_results"].items():
            for key, value in metrics.items():
                fields[name][key] += value
    return {
        "documents": len(reports),
        "character_error_rate": round(chars / gold_chars, 6) if gold_chars else None,
        "word_error_rate": round(words / gold_words, 6) if gold_words else None,
        "fields": {
            name: {
                **values,
                "candidate_recall": round(values["candidate_recalled"] / values["eligible"], 6),
                "candidate_precision": round(
                    values["matching_candidates"] / values["emitted_candidates"], 6
                ) if values["emitted_candidates"] else None,
                "review_rate": 1.0 if values["emitted_candidates"] else None,
            }
            for name, values in sorted(fields.items())
        },
        "confirmed_field_count": sum(row["confirmed_candidates"] for row in reports),
        "false_confirmed_rate": None,
        "uncertain_candidate_count": sum(row["uncertain_candidates"] for row in reports),
        "evidence_supported": sum(row["evidence_supported"] for row in reports),
        "evidence_references": sum(row["evidence_total"] for row in reports),
        "pos_prohibited_role_proposals": sum(
            row["pos_prohibited_role_proposals"] for row in reports
        ),
        "limitation": (
            "Generated text-only synthetic integration corpus; metrics are not estimates "
            "of performance on company receipts, photos, scans, or real-world templates."
        ),
    }
