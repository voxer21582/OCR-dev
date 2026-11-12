"""Conservative, evidence-bound expense-line proposals from local OCR tokens."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import re
import math
from typing import Any, Iterable

from .ocr_adapter import OCRPageResult

_AMOUNT = re.compile(r"(?<![\w.,])([+-]?(?:\d{1,3}(?:[., ]\d{3})+|\d+)[.,]\d{2})(?![\w.,])")
_DATE = re.compile(r"(?<!\d)(\d{4}-\d{2}-\d{2}|\d{1,2}[/. -]\d{1,2}[/. -]\d{4})(?!\d)")
_CURRENCY = re.compile(r"(?i)(?<![A-Z])(?:EUR|USD|GBP|CHF|CAD|AUD|JPY)(?![A-Z])|€|\$|£")
_CURRENCY_CODES = {"€": "EUR", "£": "GBP"}
_MAX_LINES = 10_000
_MAX_LINE_TEXT_CHARS = 16_384


class ExpenseLineProposalLimitError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _bbox(token):
    xs = [point[0] for point in token.polygon]
    ys = [point[1] for point in token.polygon]
    box = (min(xs), min(ys), max(xs), max(ys))
    if box[2] <= box[0] or box[3] <= box[1]:
        raise ValueError("OCR token region must have positive area")
    return box


def _rows(page: OCRPageResult):
    entries = [(token, _bbox(token)) for token in page.tokens]
    entries.sort(key=lambda item: ((item[1][1] + item[1][3]) / 2, item[1][0]))
    rows: list[list[tuple[Any, tuple[float, float, float, float]]]] = []
    for entry in entries:
        _, box = entry
        best = None
        best_overlap = 0.0
        height = box[3] - box[1]
        for index, row in enumerate(rows):
            row_top = min(item[1][1] for item in row)
            row_bottom = max(item[1][3] for item in row)
            overlap = max(0.0, min(box[3], row_bottom) - max(box[1], row_top))
            ratio = overlap / max(0.000001, min(height, row_bottom - row_top))
            if ratio >= 0.5 and ratio > best_overlap:
                best = index
                best_overlap = ratio
        if best is None:
            rows.append([entry])
        else:
            rows[best].append(entry)
    for row in rows:
        row.sort(key=lambda item: item[1][0])
    return rows


def _region(row):
    x1 = min(item[1][0] for item in row)
    y1 = min(item[1][1] for item in row)
    x2 = max(item[1][2] for item in row)
    y2 = max(item[1][3] for item in row)
    return {"coordinate_space": "normalized_page", "polygon": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]}


def _decimal_amount(literal: str) -> str | None:
    compact = literal.replace(" ", "")
    separator = "," if compact.rfind(",") > compact.rfind(".") else "."
    decimal_index = compact.rfind(separator)
    integer = re.sub(r"[.,]", "", compact[:decimal_index])
    canonical = integer + "." + compact[decimal_index + 1:]
    try:
        amount = Decimal(canonical)
    except InvalidOperation:
        return None
    return format(amount, ".2f") if amount.is_finite() else None


def _date_values(literal: str) -> list[tuple[str, str]]:
    values = []
    for match in _DATE.finditer(literal):
        value = match.group(0)
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            try:
                normalized = date.fromisoformat(value).isoformat()
            except ValueError:
                continue
            values.append((value, normalized))
            continue
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%m/%d/%Y", "%m-%d-%Y", "%m.%d.%Y"):
            try:
                parsed = datetime.strptime(value, fmt).date()
            except ValueError:
                continue
            pair = (value, parsed.isoformat())
            if pair not in values:
                values.append(pair)
    return values


def _candidate(values, evidence, *, normalization_rule=None):
    unique = {}
    for literal, normalized in values:
        unique.setdefault(normalized, literal)
    def normalization(literal, value):
        return {
            "rule_id": normalization_rule,
            "rule_version": "1",
            "original_literal": literal,
            "normalized_value": value,
        } if normalization_rule else None
    if not unique:
        return {"value": None, "status": "absent", "alternatives": [], "evidence": []}
    alternatives = []
    for value, literal in unique.items():
        item = {"value": value, "status": "observed", "evidence": [evidence]}
        norm = normalization(literal, value)
        if norm:
            item["normalization"] = norm
        alternatives.append(item)
    if len(unique) == 1:
        value, literal = next(iter(unique.items()))
        result = {"value": value, "status": "observed", "alternatives": [], "evidence": [evidence]}
        norm = normalization(literal, value)
        if norm:
            result["normalization"] = norm
        return result
    return {"value": None, "status": "uncertain", "alternatives": alternatives, "evidence": [evidence]}


def _currency_candidate(text, evidence):
    matches = [match.group(0) for match in _CURRENCY.finditer(text)]
    explicit_codes = [(value, value.upper()) for value in matches if value.isalpha()]
    if explicit_codes:
        return _candidate(explicit_codes, evidence, normalization_rule="currency-code")

    symbols = [(value, _CURRENCY_CODES.get(value, value)) for value in matches]
    if any(literal == "$" for literal, _ in symbols):
        alternatives = []
        for literal, value in symbols:
            if value not in {item["value"] for item in alternatives}:
                alternatives.append({"value": value, "status": "uncertain", "evidence": [evidence]})
        return {"value": None, "status": "uncertain", "alternatives": alternatives, "evidence": [evidence]}
    return _candidate(symbols, evidence, normalization_rule="currency-code")


def _valid_evidence_producer(producer):
    return (
        isinstance(producer, dict)
        and set(producer) == {"stage", "name", "version"}
        and producer.get("stage") == "ocr"
        and all(isinstance(producer.get(key), str) and producer[key] for key in ("name", "version"))
    )


def _evidence_region_error(region):
    if (
        not isinstance(region, dict)
        or region.get("coordinate_space") != "normalized_page"
        or not isinstance(region.get("polygon"), list)
        or len(region["polygon"]) < 3
    ):
        return "requires a normalized page region"
    if any(
        not isinstance(point, list) or len(point) != 2
        or any(not isinstance(coord, (int, float)) or isinstance(coord, bool) or not math.isfinite(coord) or not 0 <= coord <= 1 for coord in point)
        for point in region["polygon"]
    ):
        return "region coordinates are invalid"
    return None


def extract_expense_lines(pages: Iterable[OCRPageResult]) -> list[dict[str, Any]]:
    """Group OCR tokens by visual row and propose values without confirming them."""
    result = []
    seen_page_numbers = set()
    for page in sorted(pages, key=lambda item: item.page_number):
        if not isinstance(page, OCRPageResult) or page.page_number in seen_page_numbers:
            raise ValueError("OCR page results must be unique and typed")
        seen_page_numbers.add(page.page_number)
        for row_number, row in enumerate(_rows(page), start=1):
            text = " ".join(token.text.strip() for token, _ in row).strip()
            if not text:
                continue
            if len(text) > _MAX_LINE_TEXT_CHARS:
                raise ExpenseLineProposalLimitError("expense_line_text_limit")
            token_ids = [token.token_id for token, _ in row]
            evidence = {
                "source_sha256": page.source_sha256,
                "page_number": page.page_number,
                "region": _region(row),
                "token_ids": token_ids,
                "literal": text,
                "producer": {"stage": "ocr", "name": page.engine_name, "version": page.engine_version},
            }
            amounts = [(match.group(0), _decimal_amount(match.group(0))) for match in _AMOUNT.finditer(text)]
            amounts = [(literal, value) for literal, value in amounts if value is not None]
            currency = _currency_candidate(text, evidence)
            dates = _date_values(text)
            result.append({
                "line_id": f"line-p{page.page_number:04d}-{row_number:05d}",
                "description": {"value": text, "status": "observed", "alternatives": [], "evidence": [evidence]},
                "amount": _candidate(amounts, evidence, normalization_rule="decimal-amount"),
                "currency": currency,
                "date": _candidate(dates, evidence, normalization_rule="iso-date"),
                "merchant": {"value": None, "status": "absent", "alternatives": [], "evidence": []},
            })
            if len(result) > _MAX_LINES:
                raise ExpenseLineProposalLimitError("expense_line_limit")
    return result


def validate_expense_lines(lines, source_hash: str, page_numbers: set[int]) -> list[str]:
    """Validate generated or stored line proposals against OCR source evidence."""
    issues = []
    if not isinstance(lines, list) or len(lines) > _MAX_LINES:
        return ["expense_lines: expected an array within the configured limit"]
    seen = set()
    allowed_status = {"observed", "uncertain", "unreadable", "absent", "not_applicable", "rejected"}
    for index, line in enumerate(lines):
        prefix = f"expense_lines[{index}]"
        if not isinstance(line, dict) or set(line) != {"line_id", "description", "amount", "currency", "date", "merchant"}:
            issues.append(f"{prefix}: invalid line shape")
            continue
        line_id = line.get("line_id")
        if not isinstance(line_id, str) or not re.fullmatch(r"line-p\d{4}-\d{5}", line_id) or line_id in seen:
            issues.append(f"{prefix}.line_id: invalid or duplicate")
            encoded_page = None
        else:
            encoded_page = int(line_id[6:10])
        seen.add(line_id)
        for field in ("description", "amount", "currency", "date", "merchant"):
            candidate = line.get(field)
            path = f"{prefix}.{field}"
            if not isinstance(candidate, dict) or set(candidate) - {"value", "status", "alternatives", "evidence", "normalization"}:
                issues.append(f"{path}: invalid candidate")
                continue
            if candidate.get("status") not in allowed_status or not isinstance(candidate.get("alternatives"), list) or not isinstance(candidate.get("evidence"), list):
                issues.append(f"{path}: invalid candidate status or evidence arrays")
                continue
            if candidate["status"] == "observed" and not isinstance(candidate.get("value"), str):
                issues.append(f"{path}: observed candidate requires text value")
            if candidate["status"] in {"absent", "unreadable", "not_applicable"} and candidate.get("value") is not None:
                issues.append(f"{path}: null-status candidate must have null value")
            evidence = candidate["evidence"]
            if candidate["status"] in {"observed", "uncertain", "unreadable", "rejected"} and not evidence:
                issues.append(f"{path}: non-absent candidate requires evidence")
            for item in evidence:
                if not isinstance(item, dict) or item.get("source_sha256") != source_hash or item.get("page_number") not in page_numbers:
                    issues.append(f"{path}: evidence must bind to this source and an inventoried page")
                    continue
                if encoded_page != item.get("page_number"):
                    issues.append(f"{path}: line ID page differs from its evidence page")
                if not isinstance(item.get("literal"), str) or len(item["literal"]) > _MAX_LINE_TEXT_CHARS or not isinstance(item.get("token_ids"), list) or not item["token_ids"] or any(not isinstance(token_id, str) or not token_id or len(token_id) > 256 for token_id in item.get("token_ids", [])) or len(set(item.get("token_ids", []))) != len(item.get("token_ids", [])):
                    issues.append(f"{path}: evidence requires literal and token IDs")
                producer = item.get("producer")
                if not _valid_evidence_producer(producer):
                    issues.append(f"{path}: evidence producer is invalid")
                region = item.get("region")
                region_error = _evidence_region_error(region)
                if region_error:
                    issues.append(f"{path}: evidence {region_error}")
            normalization = candidate.get("normalization")
            if normalization is not None and (not isinstance(normalization, dict) or normalization.get("normalized_value") != candidate.get("value")):
                issues.append(f"{path}: normalization does not match candidate value")
            if candidate["status"] == "uncertain" and candidate.get("value") is None and not candidate["alternatives"]:
                issues.append(f"{path}: uncertain candidate requires alternatives")
            for alternative in candidate["alternatives"]:
                if not isinstance(alternative, dict) or set(alternative) - {"value", "status", "evidence", "normalization"} or alternative.get("status") not in {"observed", "uncertain", "unreadable", "rejected"} or not isinstance(alternative.get("value"), str) or not isinstance(alternative.get("evidence"), list) or not alternative["evidence"]:
                    issues.append(f"{path}: alternative candidate is invalid")
                    continue
                alt_normalization = alternative.get("normalization")
                if alt_normalization is not None and (not isinstance(alt_normalization, dict) or alt_normalization.get("normalized_value") != alternative.get("value")):
                    issues.append(f"{path}: alternative normalization does not match its value")
                for item in alternative["evidence"]:
                    if not isinstance(item, dict) or item.get("source_sha256") != source_hash or item.get("page_number") not in page_numbers or not isinstance(item.get("literal"), str) or not isinstance(item.get("token_ids"), list) or not item["token_ids"]:
                        issues.append(f"{path}: alternative evidence is not source-bound")
                        continue
                    if not _valid_evidence_producer(item.get("producer")):
                        issues.append(f"{path}: alternative evidence producer is invalid")
                    region_error = _evidence_region_error(item.get("region"))
                    if region_error:
                        issues.append(f"{path}: alternative evidence {region_error}")
    return issues
