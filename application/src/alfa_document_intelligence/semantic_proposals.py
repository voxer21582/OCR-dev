"""Evidence-bound, conservative proposals for common fields from OCR tokens.

This module does not run OCR. Narrow, explicit date and total labels can guide
uncertain proposals; all candidates still require human review.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math
import re
from typing import Iterable

from .ocr_adapter import OCRPageResult, OCRToken
from .document_family_catalog import CatalogProposalLimitError, DocumentFamilyCatalog, build_custom_family_proposals

_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
_ISO_DATE = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
_NUMERIC_DATE = re.compile(r"(?<!\d)(\d{1,2}[/. -]\d{1,2}[/. -]\d{4})(?!\d)")
_DATE_ROLE_LABELS = {
    "issue_date": re.compile(
        r"(?i)\b(?:data(?:\s+di)?\s+(?:emissione|documento)|invoice\s+date|"
        r"document\s+date|date\s+of\s+issue|issue\s+date)\b[\s:=-]*$"
    ),
    "check_in_date": re.compile(
        r"(?i)\b(?:check[\s-]*in(?:\s+date)?|arrival(?:\s+date)?|"
        r"data\s+(?:di\s+)?arrivo|arrivo)\b[\s:=-]*$"
    ),
    "check_out_date": re.compile(
        r"(?i)\b(?:check[\s-]*out(?:\s+date)?|departure(?:\s+date)?|"
        r"data\s+(?:di\s+)?partenza|partenza)\b[\s:=-]*$"
    ),
    "trip_start_date": re.compile(r"(?i)\b(?:inizio\s+trasferta|data\s+inizio\s+trasferta|trip\s+start(?:\s+date)?|business\s+trip\s+start)\b[\s:=-]*$"),
    "trip_end_date": re.compile(r"(?i)\b(?:fine\s+trasferta|data\s+fine\s+trasferta|trip\s+end(?:\s+date)?|business\s+trip\s+end)\b[\s:=-]*$"),
}
_EXPENSE_TEXT_LABELS = {
    "traveler_name": re.compile(r"(?i)^\s*(?:nome\s+(?:trasfertista|dipendente|viaggiatore)|dipendente|traveler\s+name|employee\s+name)\s*[:=-]\s*(.+?)\s*$"),
    "trip_destination": re.compile(r"(?i)^\s*(?:destinazione\s+(?:della\s+)?trasferta|luogo\s+trasferta|trip\s+destination|destination)\s*[:=-]\s*(.+?)\s*$"),
    "trip_purpose": re.compile(r"(?i)^\s*(?:causale\s+trasferta|motivo\s+(?:della\s+)?trasferta|finalita\s+trasferta|trip\s+purpose|business\s+purpose)\s*[:=-]\s*(.+?)\s*$"),
}
_AMOUNT = re.compile(r"(?<![\w.,])([+-]?(?:\d{1,3}(?:[., ]\d{3})+|\d+)[.,]\d{2})(?![\w.,])")
_CURRENCY_CODE = re.compile(r"(?i)(?<![A-Z])(?:EUR|USD|GBP|CHF|CAD|AUD|JPY)(?![A-Z])")
_DOCUMENT_FAMILY_CUES = (
    ("invoice", re.compile(r"(?i)^\s*(?:fattura|invoice)\s*$")),
    ("fiscal_receipt", re.compile(r"(?i)^\s*(?:ricevuta fiscale|scontrino fiscale|fiscal receipt)\s*$")),
    ("parking_receipt", re.compile(r"(?i)^\s*(?:ricevuta (?:di )?parcheggio|parking receipt|parking ticket)\s*$")),
    ("hotel_document", re.compile(r"(?i)^\s*(?:hotel (?:invoice|receipt|folio)|(?:invoice|receipt) for (?:hotel|lodging|accommodation)|documento hotel)\s*$")),
    ("pos_slip", re.compile(r"(?i)^\s*(?:pos (?:receipt|slip)|card payment slip|payment card receipt)\s*$")),
)
_ENTITY_LABELS = {
    "merchant_name": re.compile(r"(?i)\b(?:esercente|venditore|seller|merchant(?:\s+name)?)\s*[:=-]\s*(.+?)\s*$"),
    "supplier_name": re.compile(r"(?i)\b(?:fornitore|supplier|vendor)\s*[:=-]\s*(.+?)\s*$"),
    "bill_to_name": re.compile(r"(?i)^\s*bill\s+to\s*[:=-]\s*(.+?)\s*$"),
    "sold_to_name": re.compile(r"(?i)^\s*sold\s+to\s*[:=-]\s*(.+?)\s*$"),
}
_DOCUMENT_NUMBER_LABEL = re.compile(
    r"(?i)^\s*(?:numero\s+(?:fattura|documento)|"
    r"n(?:[.°º])?\s*(?:fattura|doc(?:umento)?\.?)|"
    r"invoice\s+(?:number|no\.?)|document\s+(?:number|no\.?))"
    r"\s*[:#=-]?\s*([A-Z0-9][A-Z0-9./_-]*)\s*$"
)
_TIP_AMOUNT_LABEL = re.compile(
    r"(?i)^\s*(?:importo\s+di\s+mancia|mancia|tip|gratuity)\b[\s:=-]*(?:€|£|\$|EUR|GBP|USD)?\s*$"
)
_PAID_AMOUNT_LABEL = re.compile(
    r"(?i)^\s*(?:importo\s+pagato|somma\s+pagata|pagato|amount\s+paid|paid\s+amount)\b[\s:=-]*(?:€|£|\$|EUR|GBP|USD)?\s*$"
)
_PAYMENT_REFERENCE_LABEL = re.compile(
    r"(?i)^\s*(?:riferimento\s+pagamento|rif\.?\s+pagamento|rif\.?\s+transazione|payment\s+reference|transaction\s+reference)\s*[:#=-]\s*([A-Z0-9][A-Z0-9./_-]*)\s*$"
)
_PAYMENT_METHOD_LABEL = re.compile(
    r"(?i)^\s*(?:metodo\s+di\s+pagamento|payment\s+method|pagamento\s+con|pagato\s+con|paid\s+by|payment\s+by)\s*[:=-]?\s*"
)
_PAYMENT_METHOD_VALUES = {
    "cash": ("cash", "contanti"),
    "card": ("card", "carta", "carta di credito", "carta di debito"),
    "bank_transfer": ("bank transfer", "bonifico", "bonifico bancario"),
    "cheque": ("cheque", "check", "assegno"),
}
_TOTAL_LABEL = re.compile(
    r"(?i)\b(?:importo\s+totale(?:\s+(?:da\s+pagare|dovuto|complessivo))?"
    r"|totale(?:\s+(?:da\s+pagare|dovuto|complessivo))?"
    r"|grand\s+total|total(?:\s+(?:due|amount))?|amount\s+due)\b"
    r"[\s:=-]*(?:€|£|\$|EUR|GBP|USD)?\s*$"
)
_TAX_AMOUNT_LABELS = {
    "vat_amount": re.compile(r"(?i)\b(?:iva|vat|mwst)(?:\s+(?:amount|importo|betrag))?(?:\s+[0-9]{1,2}(?:[.,][0-9]+)?\s*%)?[\s:=-]*(?:€|£|\$|EUR|GBP|USD)?[\s:=-]*$"),
    "taxable_base": re.compile(r"(?i)\b(?:imponibile|taxable\s+(?:base|amount)|net\s+amount)\b[\s:=-]*(?:€|£|\$|EUR|GBP|USD)?[\s:=-]*$"),
}
_TAX_RATE_LABEL = re.compile(r"(?i)\b(?:aliquota(?:\s+iva)?|(?:iva|vat)\s+(?:rate|aliquota)|vat\s+percentage|tax\s+rate|(?:iva|vat))\b[\s:=-]*(?:\d{1,2}(?:[.,]\d{1,2})?)?[\s:=-]*$")
_PERCENTAGE = re.compile(r"(?<![\d.,])(\d{1,2}(?:[.,]\d{1,2})?)\s*%(?!\w)")
_BUYER_TRAILING_FIELD_LABEL = re.compile(
    r"(?i)\s+(?:invoice\s+(?:date|number|no\.?)|date\s+of\s+issue|"
    r"payment\s+(?:method|reference|amount)|phone(?:\s+number)?|e-?mail|"
    r"address|ship\s+to|vat(?:\s+(?:id|number))?|tax\s+id|amount\s+due|total\s+due)\s*[:=-]?\s*"
)
_VAT_REGISTRATION_LABEL = re.compile(
    r"(?i)^\s*(?:p\.?\s*iva|partita\s+iva|vat\s+(?:id|number|no\.?))"
    r"\s*[:#=-]?\s*((?:IT\s*)?[0-9][0-9./ -]{9,20})\s*$"
)
MAX_PROPOSALS_PER_FIELD = 100


class SemanticProposalError(ValueError):
    """OCR pages cannot safely be converted to bounded, source-bound proposals."""

class SemanticProposalLimitError(SemanticProposalError):
    """A fixed proposal review limit was exceeded."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)



@dataclass(frozen=True)
class _Proposal:
    value: str
    evidence: dict[str, object]
    rule_id: str
    original_literal: str


def _validate_pages(pages: Iterable[OCRPageResult]) -> tuple[OCRPageResult, ...]:
    materialized = tuple(pages)
    if not materialized:
        raise SemanticProposalError("at least one OCR page is required")
    expected_hash: str | None = None
    seen_pages: set[int] = set()
    for page in materialized:
        if not isinstance(page, OCRPageResult):
            raise SemanticProposalError("pages must contain OCRPageResult values")
        if not isinstance(page.source_sha256, str) or not _SHA256.fullmatch(page.source_sha256):
            raise SemanticProposalError("page source_sha256 must be 64 hexadecimal characters")
        if expected_hash is None:
            expected_hash = page.source_sha256
        elif page.source_sha256 != expected_hash:
            raise SemanticProposalError("all OCR pages must bind to the same source document")
        if not isinstance(page.page_number, int) or isinstance(page.page_number, bool) or page.page_number < 1:
            raise SemanticProposalError("page_number must be a positive integer")
        if page.page_number in seen_pages:
            raise SemanticProposalError("page_number must be unique")
        seen_pages.add(page.page_number)
        if not isinstance(page.engine_name, str) or not page.engine_name.strip() or not isinstance(page.engine_version, str) or not page.engine_version.strip():
            raise SemanticProposalError("OCR engine name and version are required for provenance")
        token_ids: set[str] = set()
        for token in page.tokens:
            if not isinstance(token, OCRToken):
                raise SemanticProposalError("pages must contain OCRToken values")
            if not isinstance(token.token_id, str) or not token.token_id.strip() or token.token_id in token_ids:
                raise SemanticProposalError("each OCR page requires unique OCRToken identifiers")
            token_ids.add(token.token_id)
            if not isinstance(token.text, str) or not token.text.strip():
                raise SemanticProposalError("OCR token text must be non-empty")
            if not isinstance(token.polygon, tuple) or len(token.polygon) < 3:
                raise SemanticProposalError("OCR token polygon must contain at least three points")
            for point in token.polygon:
                if not isinstance(point, tuple) or len(point) != 2:
                    raise SemanticProposalError("OCR token polygon points must be x,y tuples")
                for coordinate in point:
                    if (not isinstance(coordinate, (int, float)) or isinstance(coordinate, bool)
                            or not math.isfinite(coordinate) or not 0 <= coordinate <= 1):
                        raise SemanticProposalError("OCR token polygon coordinates must be finite and normalized")
    return tuple(sorted(materialized, key=lambda item: item.page_number))


def _evidence(page: OCRPageResult, token: OCRToken, literal: str) -> dict[str, object]:
    return {
        "source_sha256": page.source_sha256,
        "page_number": page.page_number,
        "region": {
            "coordinate_space": "normalized_page",
            "polygon": [[float(x), float(y)] for x, y in token.polygon],
        },
        "token_ids": [token.token_id],
        "literal": literal,
        "producer": {
            "stage": "ocr",
            "name": page.engine_name,
            "version": page.engine_version,
        },
    }


def _date_proposals(literal: str) -> list[tuple[str, str]]:
    proposals: list[tuple[str, str]] = []
    for match in _ISO_DATE.finditer(literal):
        try:
            normalized = date(*(int(part) for part in match.groups())).isoformat()
        except ValueError:
            continue
        proposals.append((normalized, "date-iso8601"))
    for match in _NUMERIC_DATE.finditer(literal):
        value = match.group(1)
        parts = re.split(r"[/. -]", value)
        first, second, year = (int(part) for part in parts)
        # Preserve both interpretations when the document's language/date convention
        # cannot resolve day-first versus month-first.
        interpretations = (
            ("date-dmy", (year, second, first)),
            ("date-mdy", (year, first, second)),
        )
        seen: set[str] = set()
        for rule_id, components in interpretations:
            try:
                normalized = date(*components).isoformat()
            except ValueError:
                continue
            if normalized not in seen:
                proposals.append((normalized, rule_id))
                seen.add(normalized)
    return proposals


def _normalize_amount(literal: str) -> str:
    sign = "-" if literal.startswith("-") else ""
    unsigned = literal.lstrip("+-")
    integer = re.sub(r"[., ]", "", unsigned[:-3])
    fraction = unsigned[-2:]
    return f"{sign}{integer}.{fraction}"


def _candidate(proposals: list[_Proposal]) -> dict[str, object] | None:
    if not proposals:
        return None
    if len(proposals) > MAX_PROPOSALS_PER_FIELD:
        raise SemanticProposalLimitError("semantic_proposal_field_limit")
    evidence: list[dict[str, object]] = []
    alternatives: list[dict[str, object]] = []
    for proposal in proposals:
        evidence.append(proposal.evidence)
        alternatives.append({
            "value": proposal.value,
            "status": "observed",
            "evidence": [proposal.evidence],
            "normalization": {
                "rule_id": proposal.rule_id,
                "rule_version": "1",
                "original_literal": proposal.original_literal,
                "normalized_value": proposal.value,
            },
        })
    return {
        "value": None,
        "status": "uncertain",
        "alternatives": alternatives,
        "evidence": evidence,
    }


def propose_common_fields(pages: Iterable[OCRPageResult], *, document_family: str | None = None, custom_family_catalog: DocumentFamilyCatalog | None = None) -> dict[str, dict[str, object]]:
    """Return review-required date, amount, and explicit-currency proposals.

    Amount/date semantics are deliberately unresolved. The function never
    promotes a single visible amount to a total or a date to an issue date.
    Ambiguous dates keep both valid interpretations as evidence-linked alternatives.
    """
    ordered_pages = _validate_pages(pages)
    dates: list[_Proposal] = []
    role_dates: dict[str, list[_Proposal]] = {name: [] for name in _DATE_ROLE_LABELS if name not in {"trip_start_date", "trip_end_date"} or document_family == "expense_report"}
    expense_text: dict[str, list[_Proposal]] = {name: [] for name in _EXPENSE_TEXT_LABELS} if document_family == "expense_report" else {}
    amounts: list[_Proposal] = []
    labelled_totals: list[_Proposal] = []
    paid_amounts: list[_Proposal] = []
    tip_amounts: list[_Proposal] = []
    payment_methods: list[_Proposal] = []
    payment_references: list[_Proposal] = []
    currencies: list[_Proposal] = []
    tax_proposals: dict[str, list[_Proposal]] = {name: [] for name in ('vat_amount', 'taxable_base', 'vat_rate')}
    entity_proposals: dict[str, list[_Proposal]] = {name: [] for name in _ENTITY_LABELS}
    document_numbers: list[_Proposal] = []
    vat_registration_numbers: list[_Proposal] = []
    family_proposals: list[_Proposal] = []

    for page in ordered_pages:
        for token in page.tokens:
            if document_family == "expense_report":
                for field_name, label_pattern in _EXPENSE_TEXT_LABELS.items():
                    match = label_pattern.fullmatch(token.text)
                    if match and match.group(1).strip() and any(ch.isalpha() for ch in match.group(1)):
                        literal = token.text.strip()
                        value = match.group(1).strip()
                        expense_text[field_name].append(_Proposal(value, _evidence(page, token, literal), f"explicit-{field_name}-label-preserve-literal", value))
            family_literal = token.text.strip()
            for family, cue_pattern in _DOCUMENT_FAMILY_CUES:
                if cue_pattern.fullmatch(token.text):
                    family_proposals.append(_Proposal(
                        family, _evidence(page, token, family_literal),
                        "explicit-document-family-cue-preserve-literal", family_literal,
                    ))
            number_match = _DOCUMENT_NUMBER_LABEL.fullmatch(token.text)
            if number_match is not None:
                literal = token.text.strip()
                value = number_match.group(1)
                document_numbers.append(_Proposal(
                    value, _evidence(page, token, literal),
                    "explicit-document-number-label-preserve-literal", value,
                ))
            vat_match = _VAT_REGISTRATION_LABEL.fullmatch(token.text)
            if vat_match is not None:
                value = vat_match.group(1).strip()
                if len(re.sub(r"\D", "", value)) == 11:
                    literal = token.text.strip()
                    vat_registration_numbers.append(_Proposal(
                        value, _evidence(page, token, literal),
                        "explicit-vat-registration-label-preserve-literal", value,
                    ))
            for field_name, label_pattern in _ENTITY_LABELS.items():
                entity_match = label_pattern.search(token.text)
                if entity_match is not None:
                    literal = token.text.strip()
                    value = entity_match.group(1).strip()
                    if field_name in {"bill_to_name", "sold_to_name"}:
                        # Do not match embedded cues or let one buyer-role value
                        # absorb a second buyer role in a single OCR token.
                        if entity_match.start() != len(token.text) - len(token.text.lstrip()):
                            continue
                        if re.search(r"(?i)\b(?:bill\s+to|sold\s+to)\s*[:=-]", value):
                            continue
                        if _BUYER_TRAILING_FIELD_LABEL.search(value):
                            continue
                    if value and any(character.isalpha() for character in value):
                        entity_proposals[field_name].append(_Proposal(
                            value, _evidence(page, token, literal),
                            f"explicit-{field_name}-label-trim-whitespace", entity_match.group(1),
                        ))
            date_matches = [
                (match, match.group(0), match.start(), match.end())
                for match in _ISO_DATE.finditer(token.text)
            ]
            date_matches.extend(
                (match, match.group(1), match.start(1), match.end(1))
                for match in _NUMERIC_DATE.finditer(token.text)
            )
            for match, literal, date_start, date_end in date_matches:
                for normalized, rule_id in _date_proposals(literal):
                    dates.append(_Proposal(normalized, _evidence(page, token, literal), rule_id, literal))
                    for field_name, label_pattern in _DATE_ROLE_LABELS.items():
                        if field_name not in role_dates:
                            continue
                        label = label_pattern.search(token.text[:date_start])
                        if label is not None:
                            role_literal = token.text[label.start():date_end]
                            role_dates[field_name].append(_Proposal(
                                normalized, _evidence(page, token, role_literal),
                                f"explicit-{field_name}-label-{rule_id}", literal,
                            ))
            reference_match = _PAYMENT_REFERENCE_LABEL.fullmatch(token.text)
            if reference_match is not None:
                reference = reference_match.group(1)
                payment_references.append(_Proposal(
                    reference, _evidence(page, token, token.text.strip()),
                    "explicit-payment-reference-label-preserve-literal", reference,
                ))
            method_label = _PAYMENT_METHOD_LABEL.search(token.text)
            if method_label is not None:
                method_literal = token.text.strip()
                method_text = token.text[method_label.end():].strip().strip(" .,:;=-")
                normalized_method = next(
                    (canonical for canonical, values in _PAYMENT_METHOD_VALUES.items()
                     if method_text.casefold() in values),
                    None,
                )
                if normalized_method is not None:
                    payment_methods.append(_Proposal(
                        normalized_method, _evidence(page, token, method_literal),
                        "explicit-payment-method-label-controlled-value", method_text,
                    ))
            for match in _AMOUNT.finditer(token.text):
                literal = match.group(1)
                normalized = _normalize_amount(literal)
                amounts.append(_Proposal(normalized, _evidence(page, token, literal),
                                         "decimal-separator-last", literal))
                for field_name, label_pattern in _TAX_AMOUNT_LABELS.items():
                    tax_label = label_pattern.search(token.text[:match.start()])
                    if tax_label is not None:
                        role_literal = token.text[tax_label.start():match.end()]
                        tax_proposals[field_name].append(_Proposal(
                            normalized, _evidence(page, token, role_literal),
                            f"explicit-{field_name}-label-decimal-separator-last", literal,
                        ))
                tip_label = _TIP_AMOUNT_LABEL.search(token.text[:match.start()])
                if tip_label is not None:
                    tip_literal = token.text[tip_label.start():match.end()]
                    tip_amounts.append(_Proposal(
                        normalized, _evidence(page, token, tip_literal),
                        "explicit-tip-amount-label-decimal-separator-last", literal,
                    ))
                paid_label = _PAID_AMOUNT_LABEL.search(token.text[:match.start()])
                if paid_label is not None:
                    paid_literal = token.text[paid_label.start():match.end()]
                    paid_amounts.append(_Proposal(
                        normalized, _evidence(page, token, paid_literal),
                        "explicit-paid-amount-label-decimal-separator-last", literal,
                    ))
                label = _TOTAL_LABEL.search(token.text[:match.start()])
                if label is not None:
                    # Keep the role cue and amount together in the source literal.
                    # This only proposes a candidate; it never confirms the total.
                    labelled_literal = token.text[label.start():match.end()]
                    labelled_totals.append(_Proposal(
                        normalized,
                        _evidence(page, token, labelled_literal),
                        "explicit-total-label-decimal-separator-last",
                        literal,
                    ))
            for match in _PERCENTAGE.finditer(token.text):
                tax_label = _TAX_RATE_LABEL.search(token.text[:match.start()])
                if tax_label is not None:
                    literal = match.group(1)
                    normalized = literal.replace(',', '.')
                    if '.' in normalized:
                        normalized = normalized.rstrip('0').rstrip('.')
                    role_literal = token.text[tax_label.start():match.end()]
                    tax_proposals['vat_rate'].append(_Proposal(
                        normalized, _evidence(page, token, role_literal),
                        'explicit-vat-rate-label-percentage', literal,
                    ))
            for match in _CURRENCY_CODE.finditer(token.text):
                literal = match.group(0)
                currencies.append(_Proposal(
                    literal.upper(), _evidence(page, token, literal), "explicit-iso-currency", literal
                ))
            for match in re.finditer(r"€", token.text):
                literal = match.group(0)
                currencies.append(_Proposal(
                    "EUR", _evidence(page, token, literal), "explicit-euro-symbol", literal
                ))

    proposals = {
        "date_candidates": _candidate(dates),
        **{name: _candidate(items) for name, items in role_dates.items()},
        **{name: _candidate(items) for name, items in expense_text.items()},
        "amount_candidates": _candidate(amounts),
        "total_amount": _candidate(labelled_totals),
        "payment_amount": _candidate(paid_amounts),
        "tip_amount": _candidate(tip_amounts),
        "payment_method": _candidate(payment_methods),
        "payment_reference": _candidate(payment_references),
        "currency": _candidate(currencies),
        **{name: _candidate(items) for name, items in tax_proposals.items()},
        **{name: _candidate(items) for name, items in entity_proposals.items()},
        "document_number": _candidate(document_numbers),
        "vat_registration_number": _candidate(vat_registration_numbers),
        "document_family_candidates": _candidate(family_proposals),
    }
    result = {name: value for name, value in proposals.items() if value is not None}
    if custom_family_catalog is not None:
        try:
            custom = build_custom_family_proposals(ordered_pages, custom_family_catalog)
        except CatalogProposalLimitError as exc:
            raise SemanticProposalLimitError("semantic_proposal_catalog_limit") from exc
        except ValueError as exc:
            raise SemanticProposalError("custom document-family catalog proposal failed") from exc
        for name, candidate in custom.items():
            if name in result:
                if name != "document_family_candidates":
                    raise SemanticProposalError("custom field identifier collides with a built-in field")
                combined = result[name]
                if len(combined["alternatives"]) + len(candidate["alternatives"]) > MAX_PROPOSALS_PER_FIELD:
                    raise SemanticProposalLimitError("semantic_proposal_family_limit")
                combined["alternatives"].extend(candidate["alternatives"])
                combined["evidence"].extend(candidate["evidence"])
            else:
                result[name] = candidate
    return result
