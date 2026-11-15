"""Per-field accuracy of processed records against the field benchmark manifest (numbers only)."""
from __future__ import annotations

from typing import Any, Mapping


def first_value(candidate: Any) -> Any:
    """The value a reviewer sees first: the observed value, else the first alternative."""
    if not isinstance(candidate, Mapping):
        return None
    if candidate.get("status") == "observed":
        return candidate.get("value")
    alternatives = candidate.get("alternatives")
    if isinstance(alternatives, list) and alternatives and isinstance(alternatives[0], Mapping):
        return alternatives[0].get("value")
    return None


def score_records(manifest: Mapping[str, Any], records: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, float]]:
    """``{field: {"correct", "total", "rate"}}`` over every manifest document."""
    totals: dict[str, list[int]] = {}
    for document in manifest["documents"]:
        fields = (records.get(document["document_id"]) or {}).get("fields") or {}
        for name, expected in document["expected"].items():
            counts = totals.setdefault(name, [0, 0])
            counts[1] += 1
            if first_value(fields.get(name)) == expected:
                counts[0] += 1
    return {
        name: {"correct": correct, "total": total, "rate": round(correct / total, 4) if total else 0.0}
        for name, (correct, total) in sorted(totals.items())
    }
