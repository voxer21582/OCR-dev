"""Archived document as versioned CSV (DEC-027)."""
from ..exporter_registry import ExporterManifest

MANIFEST = ExporterManifest(
    exporter_id="document-csv",
    label_it="Esporta CSV",
    applies_to="document",
    media_type="text/csv; charset=utf-8",
    suffix="csv",
    function_ref="alfa_document_intelligence.document_export:export_document_csv",
)
