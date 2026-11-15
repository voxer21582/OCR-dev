"""Registry of validation rules and their versions (REQ-064).

Every finding carries its rule id and the version registered here. A record
stores the rule set it was checked with (``validation_ruleset``). Adding or
changing a rule never rewrites a record a person has started to review: its
findings and rule set stay as they were when the review began.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class RuleSpec:
    rule_id: str
    version: str
    dimension: str
    description_it: str


RULES: dict[str, RuleSpec] = {
    spec.rule_id: spec for spec in (
        RuleSpec("hotel-stay-date-order", "1", "date_consistency",
                 "La data di partenza non precede quella di arrivo."),
        RuleSpec("taxable-base-vat-total-arithmetic", "1", "amount_arithmetic_consistency",
                 "Imponibile più IVA è uguale al totale."),
        RuleSpec("required-custom-field", "1", "required_field_presence",
                 "I campi obbligatori del tipo di documento sono presenti."),
        RuleSpec("line-items-sum-total", "1", "amount_arithmetic_consistency",
                 "La somma delle righe è uguale al totale."),
    )
}


def ruleset(rules: Mapping[str, RuleSpec] = RULES) -> dict[str, str]:
    """Rule id → version, as stored in ``validation_ruleset``."""
    return {rule_id: spec.version for rule_id, spec in sorted(rules.items())}


def version_of(rule_id: str) -> str:
    return RULES[rule_id].version


def is_reviewed(record: Mapping[str, Any]) -> bool:
    review = record.get("review")
    if not isinstance(review, Mapping):
        return False
    return bool(review.get("events")) or review.get("status") not in (None, "not_started")


def revalidate(
    record: Mapping[str, Any], *,
    validate: Callable[[dict[str, Any]], list[dict[str, Any]]] | None = None,
    rules: Mapping[str, RuleSpec] = RULES,
) -> dict[str, Any]:
    """A copy checked with the current rules, unless a review has started (then unchanged)."""
    result = deepcopy(dict(record))
    if is_reviewed(result):
        return result
    if validate is None:
        from .document_validation import validate_document_consistency as validate
    result["validation_findings"] = validate(result)
    result["validation_ruleset"] = ruleset(rules)
    return result
