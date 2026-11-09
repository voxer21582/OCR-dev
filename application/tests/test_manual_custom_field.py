import copy
import json
import unittest
from pathlib import Path

from alfa_document_intelligence.document_family_catalog import load_custom_family_catalog
from alfa_document_intelligence.local_intake_app import _apply_field_correction, _render_editable_record
from alfa_document_intelligence.manual_region_review import build_human_region_evidence
from alfa_document_intelligence.review_ledger import append_review_event, reviewed_overlay, verify_review_ledger


class ManualCustomFieldTests(unittest.TestCase):
    def test_custom_typed_fields_explain_required_formats(self):
        page = _render_editable_record(self.record, document_id="synthetic-1", has_source=True)
        self.assertIn("AAAA-MM-GG", page)
        self.assertIn("1234.50", page)

    def setUp(self):
        self.record = json.loads(
            (Path(__file__).parent / "fixtures" / "synthetic_invoice.json").read_text(encoding="utf-8")
        )
        self.record["pages"] = [{"page_number": 1, "orientation": "portrait"}]
        catalog = load_custom_family_catalog(json.dumps({
            "catalog_version": "2",
            "families": [{
                "id": "custom_taxi_receipt", "label": "Ricevuta taxi",
                "title_cues": ["RICEVUTA TAXI"],
                "fields": [
                    {"id": "trip_date", "label": "Data corsa", "aliases": ["Data"], "type": "date"},
                    {"id": "fare", "label": "Tariffa", "aliases": ["Importo"], "type": "amount"},
                    {"id": "reference", "label": "Riferimento", "aliases": ["Codice"], "type": "identifier"},
                    {"id": "note", "label": "Nota", "aliases": ["Nota"], "type": "text"},
                ],
            }],
        }))
        self.record["schema_version"] = "0.2.0"
        self.record["document_family_definitions"] = [catalog.snapshot_for("custom_taxi_receipt")]

    def correct(self, name, value):
        return _apply_field_correction(
            self.record, field_name=name, value=value, timestamp="2026-11-08T10:00:00Z",
            region_page_number=1, region_coordinates=("0.1", "0.2", "0.6", "0.35"),
        )

    def test_declared_missing_fields_are_offered(self):
        page = _render_editable_record(self.record, document_id="synthetic-1", has_source=True)
        for suffix in ("trip_date", "fare", "reference", "note"):
            self.assertIn(f"/fields/custom_taxi_receipt_{suffix}", page)
        self.assertNotIn("/fields/custom_taxi_receipt_unknown", page)

    def test_declared_values_preserve_extraction_and_human_evidence(self):
        for suffix, value in (("trip_date", "2026-03-02"), ("fare", "1234.50"),
                              ("reference", "000123"), ("note", "Corsa sintetica")):
            with self.subTest(field=suffix):
                before = copy.deepcopy(self.record)
                name = f"custom_taxi_receipt_{suffix}"
                updated = self.correct(name, value)
                candidate = reviewed_overlay(updated)["reviewed_fields"][name]
                self.assertEqual(self.record, before)
                self.assertEqual(updated["fields"], before["fields"])
                self.assertEqual(candidate["value"], value)
                self.assertEqual(candidate["status"], "observed")
                evidence = candidate["evidence"][0]
                self.assertEqual(evidence["source_sha256"], before["source"]["sha256"])
                self.assertEqual(evidence["page_number"], 1)
                self.assertEqual(evidence["producer"]["stage"], "human_review")
                self.assertNotIn("literal", evidence)
                self.assertTrue(verify_review_ledger(updated))

    def test_undeclared_custom_field_is_rejected(self):
        with self.assertRaises(ValueError):
            self.correct("custom_taxi_receipt_unknown", "inventato")

    def test_invalid_typed_values_are_rejected(self):
        for name, value in (("custom_taxi_receipt_trip_date", "2026-02-30"),
                            ("custom_taxi_receipt_trip_date", "02/03/2026"),
                            ("custom_taxi_receipt_fare", "12,50"),
                            ("custom_taxi_receipt_fare", "12.5")):
            with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                self.correct(name, value)

    def test_ledger_independently_rejects_invalid_typed_value(self):
        record = append_review_event(self.record, actor_id="tester", action="queued", timestamp="2026-11-08T10:00:00Z")
        record = append_review_event(record, actor_id="tester", action="opened", timestamp="2026-11-08T10:00:01Z")
        candidate = {
            "value": "2026-02-30", "status": "observed", "alternatives": [],
            "evidence": [build_human_region_evidence(record["source"]["sha256"], 1, "0.1", "0.2", "0.6", "0.35")],
        }
        with self.assertRaises(ValueError):
            append_review_event(record, actor_id="tester", action="field_corrected",
                                timestamp="2026-11-08T10:00:02Z", field_name="custom_taxi_receipt_trip_date",
                                reason_code="human_corrected", candidate=candidate)


if __name__ == "__main__":
    unittest.main()
