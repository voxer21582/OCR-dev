"""Exporters behind a registry: a new format means new files only (REQ-090)."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from alfa_document_intelligence.exporter_registry import (
    ExporterRegistryError,
    discover_exporters,
    export_case,
    export_document,
    selectable_case_exporters,
    selectable_document_exporters,
)
from alfa_document_intelligence.exporters.case_json import CASE_EXPORT_KEYS

_FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_invoice.json"


class ExporterRegistryTests(unittest.TestCase):
    def test_json_and_csv_are_registered_for_documents(self):
        exporters = selectable_document_exporters()
        self.assertEqual([(item.exporter_id, item.suffix) for item in exporters],
                         [("document-csv", "csv"), ("document-json", "json")])
        for item in exporters:
            self.assertTrue(item.label_it and item.media_type.endswith("charset=utf-8"))

    def test_export_by_suffix_matches_the_existing_serializers(self):
        from alfa_document_intelligence.document_export import export_document_csv, export_document_json

        record = json.loads(_FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(export_document(record, "json")[0], export_document_json(record))
        self.assertEqual(export_document(record, "csv")[0], export_document_csv(record))
        with self.assertRaises(ExporterRegistryError):
            export_document(record, "exe")

    def test_case_formats_are_registered(self):
        self.assertEqual([(item.exporter_id, item.suffix) for item in selectable_case_exporters()],
                         [("case-json", "json"), ("case-review-csv", "csv")])
        reconciliation = {key: [] for key in CASE_EXPORT_KEYS}
        reconciliation.update({"statement": None, "case_revision": 1})
        text, manifest = export_case("case-x", reconciliation, "json")
        self.assertEqual(json.loads(text)["export_schema_version"], "1.0.0")
        self.assertEqual(manifest.media_type, "application/json; charset=utf-8")
        csv_text, _ = export_case("case-x", reconciliation, "csv")
        self.assertEqual(csv_text.splitlines()[0], "export_format_version,case_id,review_event_json")
        with self.assertRaises(ExporterRegistryError):
            export_case("case-x", reconciliation, "xml")

    def test_hidden_exporters_are_discovered_but_not_offered(self):
        everything = discover_exporters()
        offered = {item.exporter_id for item in selectable_document_exporters()}
        hidden = {exporter_id for exporter_id, item in everything.items() if not item.selectable}
        self.assertFalse(hidden & offered)


if __name__ == "__main__":
    unittest.main()
