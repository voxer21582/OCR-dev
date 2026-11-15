"""Line items of invoice-like tables, with evidence (REQ-053).

A table starts at a header row naming a description column and an amount
column. Each following row with an amount is a line item, until a total or
subtotal row. Every value is an uncertain proposal bound to its row's region;
nothing here is an accounting entry.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

from .expense_line_extraction import _AMOUNT, _decimal_amount, _region, _rows
from .ocr_adapter import OCRPageResult

MAX_LINE_ITEMS = 1000
_DESCRIPTION_HEAD = re.compile(r"(?i)\b(?:descrizione|description|articolo|item|prodotto|servizio|service)\b")
_AMOUNT_HEAD = re.compile(r"(?i)\b(?:importo|amount|prezzo|price|totale|total)\b")
# Observed readings of "Qtà": "Qt", "Qtá", or "Qt" followed by a non-Latin character.
_QUANTITY_HEAD = re.compile(r"(?i)(?:\bqt(?![b-z])|\bquantit|\bqty\b|\bquantity\b)")
# Words that may make up a table header; a header is mostly made of them.
_HEADER_WORD = re.compile(
    r"(?i)^(?:descrizione|description|articolo|item|prodotto|servizio|service|qt\S*|quantit\S*|qty|quantity|"
    r"prezzo|price|unitario|unit|importo|amount|totale|total|iva|vat|u\.?m\.?|cod\.?|codice|code|sconto|discount|%|n\.?)$"
)
# Words that may make up a row closing the table (totals, taxes, payments due).
_END_WORD = re.compile(
    r"(?i)^(?:sub|subtotale|subtotal|totale|total|imponibile|iva|vat|tax|importo|documento|fattura|acconto|"
    r"bollo|netto|a|da|pagare|dovuto|complessivo|due|amount|grand|eur|usd|gbp|chf|€|\d+(?:[.,]\d+)?%|:|-)$"
)
_QUANTITY = re.compile(r"^\d{1,6}(?:[.,]\d{1,3})?$")


class LineItemLimitError(ValueError):
    """Too many line items: stable code for the proposal limit."""


def _candidate(values: list[tuple[str, str]], evidence: dict[str, Any], rule: str) -> dict[str, Any]:
    if not values:
        return {"value": None, "status": "absent", "alternatives": [], "evidence": []}
    return {
        "value": None,
        "status": "uncertain",
        "alternatives": [
            {
                "value": value, "status": "observed", "evidence": [evidence],
                "normalization": {"rule_id": rule, "rule_version": "1", "original_literal": literal, "normalized_value": value},
            }
            for literal, value in values
        ],
        "evidence": [evidence],
    }


def _is_header(text: str) -> bool:
    words = text.split()
    if not words or len(words) > 10 or _AMOUNT.search(text):
        return False
    if not (_DESCRIPTION_HEAD.search(text) and _AMOUNT_HEAD.search(text)):
        return False
    return sum(1 for word in words if _HEADER_WORD.fullmatch(word.strip(".:"))) * 2 >= len(words)


def _is_end_row(words: list[str]) -> bool:
    return bool(words) and all(_END_WORD.fullmatch(word.strip(".:")) for word in words)


def extract_line_items(pages: Iterable[OCRPageResult]) -> list[dict[str, Any]]:
    """Propose line items for every table found on the pages, in reading order.

    A table continues on the next page until a closing row (only total, tax or
    payment words plus amounts) or a new header.
    """
    items: list[dict[str, Any]] = []
    in_table = False
    has_quantity_column = False
    for page in sorted(pages, key=lambda item: item.page_number):
        for row_number, row in enumerate(_rows(page), start=1):
            # OCR often returns a whole table row as one text: work on the row text.
            text = " ".join(word for token, _ in row for word in token.text.split())
            if not text:
                continue
            if _is_header(text):
                in_table = True
                has_quantity_column = bool(_QUANTITY_HEAD.search(text))
                continue
            if not in_table:
                continue
            matches = [match for match in _AMOUNT.finditer(text) if _decimal_amount(match.group(0)) is not None]
            amounts = [(match.group(0), _decimal_amount(match.group(0))) for match in matches]
            before = text[:matches[0].start()].split() if matches else text.split()
            rest = " ".join(text[match.end():(matches[index + 1].start() if index + 1 < len(matches) else len(text))]
                            for index, match in enumerate(matches)).split()
            if _is_end_row(before + rest):
                in_table = False
                continue
            if not amounts:
                continue
            quantity = []
            if has_quantity_column and len(before) > 1 and _QUANTITY.fullmatch(before[-1]):
                quantity.append((before[-1], before[-1].replace(",", ".")))
                before = before[:-1]
            evidence = {
                "source_sha256": page.source_sha256,
                "page_number": page.page_number,
                "region": _region(row),
                "token_ids": [token.token_id for token, _ in row],
                "literal": text,
                "producer": {"stage": "ocr", "name": page.engine_name, "version": page.engine_version},
            }
            description = " ".join(before)
            items.append({
                "line_id": f"item-p{page.page_number:04d}-{row_number:05d}",
                "description": _candidate([(description, description)] if description else [], evidence, "line-item-description"),
                "quantity": _candidate(quantity, evidence, "line-item-quantity"),
                "unit_price": _candidate([amounts[0]] if len(amounts) >= 2 else [], evidence, "line-item-unit-price"),
                "amount": _candidate([amounts[-1]], evidence, "line-item-amount"),
            })
            if len(items) > MAX_LINE_ITEMS:
                raise LineItemLimitError("line_item_limit")
    return items


_ITEM_FIELDS = ("description", "quantity", "unit_price", "amount")
_STATUSES = {"observed", "uncertain", "unreadable", "absent", "not_applicable", "rejected"}


def validate_line_items(items: Any, source_hash: str, page_numbers: set[int]) -> list[str]:
    """Shape and evidence binding of stored line items."""
    if not isinstance(items, list) or len(items) > MAX_LINE_ITEMS:
        return ["line_items: expected an array within the configured limit"]
    issues: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        prefix = f"line_items[{index}]"
        if not isinstance(item, dict) or set(item) != {"line_id", *_ITEM_FIELDS}:
            issues.append(f"{prefix}: invalid line item shape")
            continue
        line_id = item["line_id"]
        if not isinstance(line_id, str) or not re.fullmatch(r"item-p\d{4}-\d{5}", line_id) or line_id in seen:
            issues.append(f"{prefix}.line_id: invalid or duplicate")
        seen.add(line_id if isinstance(line_id, str) else "")
        for name in _ITEM_FIELDS:
            candidate = item[name]
            path = f"{prefix}.{name}"
            if (not isinstance(candidate, dict) or candidate.get("status") not in _STATUSES
                    or not isinstance(candidate.get("alternatives"), list) or not isinstance(candidate.get("evidence"), list)):
                issues.append(f"{path}: invalid candidate")
                continue
            if candidate["status"] == "observed":
                issues.append(f"{path}: line items are proposals and cannot be observed")
            if candidate["status"] in {"observed", "uncertain"} and not candidate["evidence"]:
                issues.append(f"{path}: candidate requires evidence")
            evidence = list(candidate["evidence"])
            for alternative in candidate["alternatives"]:
                evidence.extend(alternative.get("evidence", []) if isinstance(alternative, dict) else [None])
            for entry in evidence:
                if (not isinstance(entry, dict) or entry.get("source_sha256") != source_hash
                        or entry.get("page_number") not in page_numbers
                        or not entry.get("token_ids") or not isinstance(entry.get("region"), dict)):
                    issues.append(f"{path}: evidence must bind to an inventoried page of this document")
                    break
    return issues
