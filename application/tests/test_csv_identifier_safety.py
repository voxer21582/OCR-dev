import copy
import csv
import io
import json
import unittest
from pathlib import Path

from alfa_document_intelligence.document_export import ExportValidationError, export_document_csv


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "synthetic_invoice.json"


class CsvIdentifierSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_invalid_document_identifiers_are_rejected_without_mutation(self):
        for identifier in ("=2+2", "+1", "-1", "@sum", "\t=2+2", "\r=2+2", " =2+2", "", "a" * 129):
            with self.subTest(identifier=identifier):
                record = copy.deepcopy(self.fixture)
                record["document_id"] = identifier
                before = copy.deepcopy(record)
                with self.assertRaises(ExportValidationError):
                    export_document_csv(record)
                self.assertEqual(record, before)

    def test_invalid_field_names_are_rejected_without_mutation(self):
        for name in ("=2+2", "+1", "-1", "@sum", "\t=2+2", "\r=2+2", " =2+2", "", "a", "a" * 65):
            with self.subTest(name=name):
                record = copy.deepcopy(self.fixture)
                candidate = record["fields"].pop("issue_date")
                record["fields"][name] = candidate
                before = copy.deepcopy(record)
                with self.assertRaises(ExportValidationError):
                    export_document_csv(record)
                self.assertEqual(record, before)

    def test_valid_identifiers_are_preserved_in_csv_without_mutation(self):
        record = copy.deepcopy(self.fixture)
        record["document_id"] = "A-01.example:2_3"
        record["fields"]["test_field_01"] = record["fields"].pop("issue_date")
        before = copy.deepcopy(record)
        rows = list(csv.DictReader(io.StringIO(export_document_csv(record))))
        self.assertTrue(rows)
        self.assertTrue(all(row["document_id"] == "A-01.example:2_3" for row in rows))
        self.assertIn("test_field_01", [row["field_name"] for row in rows])
        self.assertEqual(record, before)

    def test_maximum_length_identifiers_are_preserved(self):
        record = copy.deepcopy(self.fixture)
        record["document_id"] = "a" * 128
        record["fields"]["b" * 64] = record["fields"].pop("issue_date")
        rows = list(csv.DictReader(io.StringIO(export_document_csv(record))))
        self.assertTrue(all(row["document_id"] == "a" * 128 for row in rows))
        self.assertIn("b" * 64, [row["field_name"] for row in rows])
