"""A synthetic text exporter for tests (REQ-090).

It lists field names one per line, is hidden from the pages (``selectable=False``)
and exists to prove that a format is added with new files only: this module and its test.
"""
from __future__ import annotations

from typing import Any

from ..exporter_registry import ExporterManifest

MANIFEST = ExporterManifest(
    exporter_id="synthetic-field-list",
    label_it="Elenco campi (prova)",
    applies_to="document",
    media_type="text/plain; charset=utf-8",
    suffix="txt",
    function_ref="alfa_document_intelligence.exporters.synthetic_field_list:export_field_list",
    selectable=False,
)


def export_field_list(record: dict[str, Any]) -> str:
    fields = record.get("fields") if isinstance(record.get("fields"), dict) else {}
    return "".join(f"{name}\n" for name in sorted(str(key) for key in fields))
