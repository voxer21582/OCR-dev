"""The field states of GOAL.md, with a reason in Italian (REQ-060, DEC-013).

Records keep their six internal candidate states; this module only presents
them as valid / uncertain / missing / not valid (plus "not applicable", which
GOAL does not list but which must not be confused with "missing").
"""
from __future__ import annotations

from typing import Any, Mapping

GOAL_STATUSES = ("valido", "incerto", "mancante", "non_valido", "non_applicabile")

GOAL_STATUS_LABELS = {
    "valido": "Valido",
    "incerto": "Incerto",
    "mancante": "Mancante",
    "non_valido": "Non valido",
    "non_applicabile": "Non applicabile",
}

_FIXED = {
    "absent": ("mancante", "non trovato nel documento"),
    "unreadable": ("mancante", "presente ma illeggibile"),
    "rejected": ("non_valido", "scartato in revisione"),
    "not_applicable": ("non_applicabile", "non previsto per questo tipo di documento"),
}


def goal_status(candidate: Any, *, failed_rule_ids: frozenset[str] = frozenset()) -> tuple[str, str]:
    """Return ``(goal_status, reason)``; the reason is never empty."""
    status = candidate.get("status") if isinstance(candidate, Mapping) else None
    if status == "observed":
        if failed_rule_ids:
            return "non_valido", f"la verifica {', '.join(sorted(failed_rule_ids))} non è superata"
        return "valido", "letto dal documento"
    if status == "uncertain":
        alternatives = candidate.get("alternatives")
        count = len(alternatives) if isinstance(alternatives, list) else 0
        return "incerto", f"più letture possibili: {count}" if count > 1 else "lettura incerta"
    if isinstance(status, str) and status in _FIXED:
        return _FIXED[status]
    return "incerto", "stato non riconosciuto"


def failed_rules_by_field(record: Mapping[str, Any]) -> dict[str, frozenset[str]]:
    """Rule ids with outcome ``fail``, grouped by the fields they name."""
    grouped: dict[str, set[str]] = {}
    findings = record.get("validation_findings") if isinstance(record, Mapping) else None
    for finding in findings if isinstance(findings, list) else []:
        if not isinstance(finding, Mapping) or finding.get("outcome") != "fail":
            continue
        rule_id = finding.get("rule_id")
        names = finding.get("field_names")
        if not isinstance(rule_id, str) or not isinstance(names, list):
            continue
        for name in names:
            if isinstance(name, str):
                grouped.setdefault(name, set()).add(rule_id)
    return {name: frozenset(rules) for name, rules in grouped.items()}


def shown_field_status(
    extracted: Any, shown: Any, failed_rule_ids: frozenset[str] = frozenset(),
) -> tuple[str, str]:
    """State for the value a reviewer sees: a corrected value is not judged by
    validation findings computed on the extracted one."""
    if shown != extracted:
        status, _reason = goal_status(shown)
        if status == "valido":
            return status, "corretto in revisione; le verifiche automatiche valgono per il valore estratto"
        return status, _reason
    return goal_status(shown, failed_rule_ids=failed_rule_ids)
