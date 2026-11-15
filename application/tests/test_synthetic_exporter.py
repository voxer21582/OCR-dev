"""A hidden synthetic exporter is found by the registry without touching other files (REQ-090)."""
from __future__ import annotations

import importlib
import json
from pathlib import Path
import unittest

from alfa_document_intelligence.exporter_registry import (
    ExporterRegistryError,
    discover_exporters,
    export_document,
    selectable_document_exporters,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_invoice.json"


class SyntheticExporterTests(unittest.TestCase):
    def test_it_is_discovered_hidden_and_works(self):
        manifest = discover_exporters()["synthetic-field-list"]
        self.assertFalse(manifest.selectable)
        self.assertNotIn("synthetic-field-list", {item.exporter_id for item in selectable_document_exporters()})
        with self.assertRaises(ExporterRegistryError):
            export_document({}, "txt")  # not offered, so not reachable from the pages
        module_name, attribute = manifest.function_ref.split(":")
        function = getattr(importlib.import_module(module_name), attribute)
        record = json.loads(_FIXTURE.read_text(encoding="utf-8"))
        lines = function(record).splitlines()
        self.assertEqual(lines, sorted(lines))
        self.assertTrue(lines)


if __name__ == "__main__":
    unittest.main()
