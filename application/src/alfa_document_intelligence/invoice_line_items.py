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
_QUANTITY_HEAD = re.compile(r"(?i)(?:\bqt[aà]\.?|\bquantit[aà]\b|\bqty\b|\bquantity\b)")
_END_ROW = re.compile(r"(?i)^\s*(?:sub\s*totale|subtotale|subtotal|totale|total|imponibile|iva|vat|tax)\b")
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


def _cells(row) -> list[str]:
    # OCR often returns a whole table row as one text: work on words.
    return [word for token, _ in row for word in token.text.split()]


def extract_line_items(pages: Iterable[OCRPageResult]) -> list[dict[str, Any]]:
    """Propose line items for every table found on the pages, in reading order."""
    items: list[dict[str, Any]] = []
    for page in sorted(pages, key=lambda item: item.page_number):
        in_table = False
        has_quantity_column = False
        for row_number, row in enumerate(_rows(page), start=1):
            cells = _cells(row)
            text = " ".join(cells)
            if not text:
                continue
            if not in_table:
                if _DESCRIPTION_HEAD.search(text) and _AMOUNT_HEAD.search(text) and not _AMOUNT.search(text):
                    in_table = True
                    has_quantity_column = bool(_QUANTITY_HEAD.search(text))
                continue
            if _END_ROW.search(text):
                in_table = False
                continue
            amounts = [(cell, _decimal_amount(cell)) for cell in cells if _AMOUNT.fullmatch(cell)]
            amounts = [(literal, value) for literal, value in amounts if value is not None]
            if not amounts:
                continue
            amount_cells = {literal for literal, _ in amounts}
            quantity = []
            description_parts = []
            for cell in cells:
                if cell in amount_cells:
                    continue
                if has_quantity_column and not quantity and _QUANTITY.fullmatch(cell):
                    quantity.append((cell, cell.replace(",", ".")))
                    continue
                description_parts.append(cell)
            evidence = {
                "source_sha256": page.source_sha256,
                "page_number": page.page_number,
                "region": _region(row),
                "token_ids": [token.token_id for token, _ in row],
                "literal": text,
                "producer": {"stage": "ocr", "name": page.engine_name, "version": page.engine_version},
            }
            description = " ".join(description_parts)
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
            if candidate["status"] in {"observed", "uncertain"} and not candidate["evidence"]:
                issues.append(f"{path}: candidate requires evidence")
            evidence = list(candidate["evidence"])
            for alternative in candidate["alternatives"]:
                evidence.extend(alternative.get("evidence", []) if isinstance(alternative, dict) else [None])
            for entry in evidence:
                if (not isinstance(entry, dict) or entry.get("source_sha256") != source_hash
                        or entry.get("page_number") not in page_numbers):
                    issues.append(f"{path}: evidence must bind to an inventoried page of this document")
                    break
    return issues
