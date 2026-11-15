"""Archived document as versioned JSON (DEC-027)."""
from ..exporter_registry import ExporterManifest

MANIFEST = ExporterManifest(
    exporter_id="document-json",
    label_it="Esporta JSON",
    applies_to="document",
    media_type="application/json; charset=utf-8",
    suffix="json",
    function_ref="alfa_document_intelligence.document_export:export_document_json",
)
