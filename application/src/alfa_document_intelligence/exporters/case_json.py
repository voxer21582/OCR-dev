"""Expense case reconciliation as versioned JSON (REQ-089)."""
from __future__ import annotations

import json
from typing import Any

from ..exporter_registry import ExporterManifest

MANIFEST = ExporterManifest(
    exporter_id="case-json",
    label_it="Esporta confronto locale (JSON)",
    applies_to="case",
    media_type="application/json; charset=utf-8",
    suffix="json",
    function_ref="alfa_document_intelligence.exporters.case_json:export_case_json",
)

CASE_EXPORT_SCHEMA_VERSION = "1.0.0"
CASE_EXPORT_KEYS = (
    "statement", "case_revision", "attachments", "lines", "unused_document_ids",
    "duplicate_source_groups", "possible_duplicate_claim_groups", "review_events",
)


def export_case_json(case_id: str, reconciliation: dict[str, Any]) -> str:
    payload: dict[str, Any] = {"export_schema_version": CASE_EXPORT_SCHEMA_VERSION, "case_id": case_id}
    payload.update({key: reconciliation[key] for key in CASE_EXPORT_KEYS})
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
