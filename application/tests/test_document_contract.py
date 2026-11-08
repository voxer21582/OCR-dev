import copy
import json
import unittest
from pathlib import Path

from alfa_document_intelligence.contracts import validate_document_record
from alfa_document_intelligence.document_family_catalog import load_custom_family_catalog

ROOT = Path(__file__).parents[1]
SCHEMA_PATH = ROOT / "src" / "alfa_document_intelligence" / "schemas" / "document.schema.json"
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "synthetic_invoice.json"


class DocumentContractTests(unittest.TestCase):
    def test_selected_custom_family_candidate_also_requires_snapshot(self):
        for version in ("0.1.0", "0.2.0"):
            with self.subTest(version=version):
                record = copy.deepcopy(self.fixture)
                record["schema_version"] = version
                record["fields"]["document_family_candidates"] = {
                    "value": "custom_taxi_receipt", "status": "observed",
                    "alternatives": [],
                    "evidence": copy.deepcopy(record["fields"]["issue_date"]["evidence"]),
                }
                self.assertTrue(any(
                    "custom family candidate requires its snapshot" in issue
                    for issue in validate_document_record(record)
                ))

    def test_legacy_record_cannot_declare_even_empty_snapshots(self):
        record = copy.deepcopy(self.fixture)
        record["document_family_definitions"] = []
        self.assertTrue(any(
            "custom families require schema 0.2.0" in issue
            for issue in validate_document_record(record)
        ))

    def test_non_string_schema_version_returns_an_issue(self):
        for version in ([], {}, None, 2):
            with self.subTest(version=version):
                record = copy.deepcopy(self.fixture)
                record["schema_version"] = version
                self.assertTrue(any(
                    issue.startswith("schema_version:")
                    for issue in validate_document_record(record)
                ))

    def test_schema_accepts_typed_catalog_v2_snapshot_fields(self):
        definition = self.schema["$defs"]["documentFamilyDefinition"]
        self.assertEqual(definition["properties"]["catalog_version"]["enum"], ["1", "2"])
        field_properties = definition["properties"]["family"]["properties"]["fields"]["items"]["properties"]
        field_type = field_properties["type"]
        self.assertEqual(field_type["enum"], ["text", "identifier", "date", "amount"])
        self.assertEqual(field_properties["required"]["type"], "boolean")

    def test_schema_forbids_typed_fields_in_catalog_v1_snapshots(self):
        definition = self.schema["$defs"]["documentFamilyDefinition"]
        v1_rule = next(
            rule for rule in definition["allOf"]
            if rule["if"]["properties"]["catalog_version"].get("const") == "1"
        )
        field_item = v1_rule["then"]["properties"]["family"]["properties"]["fields"]["items"]
        forbidden = field_item["not"]["anyOf"]
        self.assertIn({"required": ["type"]}, forbidden)
        self.assertIn({"required": ["required"]}, forbidden)

    def test_legacy_records_remain_valid_and_custom_family_requires_self_verifying_snapshot(self):
        self.assertEqual(self.fixture["schema_version"], "0.1.0")
        self.assertEqual(validate_document_record(self.fixture), [])

        catalog = load_custom_family_catalog(json.dumps({
            "catalog_version": "1",
            "families": [{
                "id": "custom_taxi_receipt", "label": "Ricevuta taxi",
                "title_cues": ["RICEVUTA TAXI"], "fields": [],
            }],
        }, ensure_ascii=False))
        custom = copy.deepcopy(self.fixture)
        custom["schema_version"] = "0.2.0"
        custom["document_family"] = "custom_taxi_receipt"
        custom["document_family_definitions"] = [catalog.snapshot_for("custom_taxi_receipt")]
        self.assertEqual(validate_document_record(custom), [])

        custom["document_family_definitions"][0]["family"]["label"] = "Altered"
        self.assertTrue(any(
            "family_sha256" in issue for issue in validate_document_record(custom)
        ))

    def test_custom_family_candidate_requires_snapshot_even_before_human_selection(self):
        candidate = copy.deepcopy(self.fixture)
        candidate["schema_version"] = "0.2.0"
        candidate["fields"]["document_family_candidates"] = {
            "value": None, "status": "uncertain", "evidence": [],
            "alternatives": [{
                "value": "custom_taxi_receipt", "status": "observed",
                "evidence": [copy.deepcopy(self.fixture["fields"]["issue_date"]["evidence"][0])],
            }],
        }
        self.assertTrue(any(
            "custom family candidate requires its snapshot" in issue
            for issue in validate_document_record(candidate)
        ))

    def test_custom_typed_field_is_valid_with_catalog_v2_snapshot(self):
        catalog = load_custom_family_catalog(json.dumps({
            "catalog_version": "2",
            "families": [{
                "id": "custom_taxi_receipt", "label": "Ricevuta taxi",
                "title_cues": ["RICEVUTA TAXI"],
                "fields": [{"id": "trip_date", "label": "Data corsa", "aliases": ["Data"], "type": "date"}],
            }],
        }, ensure_ascii=False))
        record = copy.deepcopy(self.fixture)
        record["schema_version"] = "0.2.0"
        record["document_family_definitions"] = [catalog.snapshot_for("custom_taxi_receipt")]
        evidence = copy.deepcopy(record["fields"]["issue_date"]["evidence"][0])
        record["fields"]["custom_taxi_receipt_trip_date"] = {
            "value": None,
            "status": "uncertain",
            "evidence": [evidence],
            "alternatives": [{
                "value": "2026-03-02", "status": "observed", "evidence": [evidence],
                "normalization": {
                    "rule_id": "date-dmy", "rule_version": "1",
                    "original_literal": "02/03/2026", "normalized_value": "2026-03-02",
                },
            }],
        }

        self.assertEqual(validate_document_record(record), [])

    def test_custom_typed_values_must_match_snapshot_type(self):
        catalog = load_custom_family_catalog(json.dumps({
            "catalog_version": "2",
            "families": [{
                "id": "custom_taxi_receipt", "label": "Ricevuta taxi",
                "title_cues": ["RICEVUTA TAXI"],
                "fields": [
                    {"id": "trip_date", "label": "Data corsa", "aliases": ["Data"], "type": "date"},
                    {"id": "fare", "label": "Tariffa", "aliases": ["Importo"], "type": "amount"},
                    {"id": "reference", "label": "Riferimento", "aliases": ["Codice"], "type": "identifier"},
                ],
            }],
        }, ensure_ascii=False))
        record = copy.deepcopy(self.fixture)
        record["schema_version"] = "0.2.0"
        record["document_family_definitions"] = [catalog.snapshot_for("custom_taxi_receipt")]
        evidence = copy.deepcopy(record["fields"]["issue_date"]["evidence"][0])
        for name, value in (
            ("custom_taxi_receipt_trip_date", "02/03/2026"),
            ("custom_taxi_receipt_fare", "12,50"),
            ("custom_taxi_receipt_reference", {"not": "an identifier"}),
        ):
            record["fields"][name] = {
                "value": value, "status": "observed", "alternatives": [], "evidence": [evidence],
            }

        issues = validate_document_record(record)

        self.assertTrue(any("custom date value must be a valid ISO date" in issue for issue in issues))
        self.assertTrue(any("custom amount value must be a canonical decimal string" in issue for issue in issues))
        self.assertTrue(any("custom identifier value must be text" in issue for issue in issues))

    def test_record_rejects_mixed_catalog_snapshot_versions(self):
        v1 = load_custom_family_catalog(json.dumps({
            "catalog_version": "1", "families": [{
                "id": "custom_taxi_receipt", "label": "Taxi", "title_cues": ["TAXI"], "fields": [],
            }],
        }))
        v2 = load_custom_family_catalog(json.dumps({
            "catalog_version": "2", "families": [{
                "id": "custom_hotel_receipt", "label": "Hotel", "title_cues": ["HOTEL"], "fields": [],
            }],
        }))
        record = copy.deepcopy(self.fixture)
        record["schema_version"] = "0.2.0"
        record["document_family_definitions"] = [
            v1.snapshot_for("custom_taxi_receipt"),
            v2.snapshot_for("custom_hotel_receipt"),
        ]

        self.assertTrue(any(
            "snapshots use mixed catalog versions" in issue
            for issue in validate_document_record(record)
        ))

    def test_custom_field_name_requires_a_matching_family_snapshot(self):
        record = copy.deepcopy(self.fixture)
        record["fields"]["custom_taxi_receipt_pickup_city"] = copy.deepcopy(
            record["fields"]["issue_date"]
        )

        issues = validate_document_record(record)

        self.assertTrue(any(
            "custom field requires a matching family snapshot" in issue for issue in issues
        ))

    def test_custom_field_name_must_be_declared_by_its_family_snapshot(self):
        catalog = load_custom_family_catalog(json.dumps({
            "catalog_version": "1",
            "families": [{
                "id": "custom_taxi_receipt", "label": "Ricevuta taxi",
                "title_cues": ["RICEVUTA TAXI"],
                "fields": [{"id": "pickup_city", "label": "Città di partenza", "aliases": ["Partenza"]}],
            }],
        }, ensure_ascii=False))
        record = copy.deepcopy(self.fixture)
        record["schema_version"] = "0.2.0"
        record["document_family_definitions"] = [catalog.snapshot_for("custom_taxi_receipt")]
        record["fields"]["custom_taxi_receipt_unlisted"] = copy.deepcopy(record["fields"]["issue_date"])

        issues = validate_document_record(record)

        self.assertTrue(any(
            "custom field is not declared by its family snapshot" in issue for issue in issues
        ))

    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_schema_is_draft_2020_12_and_defines_evidence_binding(self):
        self.assertEqual(self.schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(self.schema["properties"]["schema_version"]["enum"], ["0.1.0", "0.2.0"])
        evidence = self.schema["$defs"]["evidence"]
        self.assertIn("source_sha256", evidence["required"])
        self.assertIn("page_number", evidence["required"])
        self.assertIn("producer", evidence["required"])

    def test_synthetic_invoice_satisfies_cross_record_invariants(self):
        self.assertEqual(validate_document_record(self.fixture), [])

    def test_evidence_must_bind_to_source_hash_and_inventoried_page(self):
        invalid = copy.deepcopy(self.fixture)
        invalid["fields"]["total_amount"]["evidence"][0]["source_sha256"] = "b" * 64
        invalid["fields"]["total_amount"]["evidence"][0]["page_number"] = 2
        issues = validate_document_record(invalid)
        self.assertTrue(any("must bind to this document" in issue for issue in issues))
        self.assertTrue(any("inventoried page" in issue for issue in issues))

    def test_fiscal_classification_evidence_must_bind_to_source_and_page(self):
        invalid = copy.deepcopy(self.fixture)
        evidence = invalid["fiscal_document_state"]["evidence"][0]
        evidence["source_sha256"] = "b" * 64
        evidence["page_number"] = 2
        issues = validate_document_record(invalid)
        self.assertTrue(any("fiscal_document_state.evidence[0].source_sha256" in issue for issue in issues))
        self.assertTrue(any("fiscal_document_state.evidence[0].page_number" in issue for issue in issues))

    def test_non_unknown_fiscal_classification_requires_evidence(self):
        invalid = copy.deepcopy(self.fixture)
        invalid["fiscal_document_state"] = {"status": "payment_evidence", "evidence": []}
        self.assertTrue(any("required for payment_evidence classification" in issue for issue in validate_document_record(invalid)))

    def test_unknown_fiscal_state_may_have_no_evidence(self):
        valid = copy.deepcopy(self.fixture)
        valid["fiscal_document_state"] = {"status": "unknown", "evidence": []}
        self.assertEqual(validate_document_record(valid), [])

    def test_pos_slip_cannot_establish_fiscal_document_status(self):
        invalid = copy.deepcopy(self.fixture)
        invalid["document_family"] = "pos_slip"
        invalid["fiscal_document_state"]["status"] = "fiscal_document"
        invalid["fiscal_document_state"]["evidence"] = self.fixture["fields"]["total_amount"]["evidence"]
        self.assertTrue(any("POS slip alone" in issue for issue in validate_document_record(invalid)))

    def test_uncertain_null_value_requires_alternatives_and_evidence(self):
        invalid = copy.deepcopy(self.fixture)
        candidate = invalid["fields"]["issue_date"]
        candidate["value"] = None
        candidate["status"] = "uncertain"
        candidate["alternatives"] = []
        self.assertTrue(any("alternatives: required" in issue for issue in validate_document_record(invalid)))

    def test_financial_values_are_decimal_strings(self):
        invalid = copy.deepcopy(self.fixture)
        invalid["fields"]["total_amount"]["value"] = 123.45
        self.assertTrue(any("JSON numbers are forbidden" in issue for issue in validate_document_record(invalid)))


    def test_valid_alternative_is_checked_without_mutating_extracted_candidate(self):
        record = copy.deepcopy(self.fixture)
        candidate = record["fields"]["issue_date"]
        alternative = {
            "value": "2026-10-13",
            "status": "observed",
            "evidence": [copy.deepcopy(candidate["evidence"][0])],
        }
        candidate["alternatives"] = [alternative]
        self.assertEqual(validate_document_record(record), [])
        self.assertEqual(candidate["value"], "2026-10-12")
        self.assertEqual(candidate["status"], "observed")

    def test_alternative_requires_supported_status_value_and_evidence(self):
        record = copy.deepcopy(self.fixture)
        record["fields"]["issue_date"]["alternatives"] = [
            {"value": 42.5, "status": "confirmed", "evidence": []}
        ]
        issues = validate_document_record(record)
        self.assertTrue(any("unsupported alternative status" in issue for issue in issues))
        self.assertTrue(any("JSON numbers are forbidden" in issue for issue in issues))
        self.assertTrue(any("at least one evidence reference" in issue for issue in issues))

    def test_alternative_evidence_must_bind_to_source_and_page(self):
        record = copy.deepcopy(self.fixture)
        evidence = copy.deepcopy(record["fields"]["issue_date"]["evidence"][0])
        evidence["source_sha256"] = "b" * 64
        evidence["page_number"] = 2
        record["fields"]["issue_date"]["alternatives"] = [
            {"value": "2026-10-13", "status": "observed", "evidence": [evidence]}
        ]
        issues = validate_document_record(record)
        self.assertTrue(any("alternatives[0].evidence[0].source_sha256" in issue for issue in issues))
        self.assertTrue(any("alternatives[0].evidence[0].page_number" in issue for issue in issues))

    def test_alternative_normalization_must_match_its_value(self):
        record = copy.deepcopy(self.fixture)
        evidence = copy.deepcopy(record["fields"]["issue_date"]["evidence"][0])
        record["fields"]["issue_date"]["alternatives"] = [{
            "value": "2026-10-13",
            "status": "observed",
            "evidence": [evidence],
            "normalization": {
                "rule_id": "synthetic-date-rule",
                "rule_version": "1",
                "original_literal": "13/10/2026",
                "normalized_value": "2026-10-12",
            },
        }]
        self.assertTrue(any(
            "alternatives[0].normalization: normalized_value must equal" in issue
            for issue in validate_document_record(record)
        ))

    def test_schema_local_references_resolve(self):
        definitions = self.schema["$defs"]
        references = []

        def walk(node):
            if isinstance(node, dict):
                reference = node.get("$ref")
                if isinstance(reference, str) and reference.startswith("#/$defs/"):
                    references.append(reference.split("/", 2)[2])
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(self.schema)
        self.assertTrue(references)
        self.assertTrue(all(reference in definitions for reference in references))

    def test_observed_candidate_requires_value(self):
        invalid = copy.deepcopy(self.fixture)
        invalid["fields"]["issue_date"]["value"] = None
        self.assertTrue(any("observed candidate requires a value" in issue for issue in validate_document_record(invalid)))

    def test_normalized_value_must_match_candidate(self):
        invalid = copy.deepcopy(self.fixture)
        invalid["fields"]["total_amount"]["normalization"]["normalized_value"] = "999.99"
        self.assertTrue(any("normalized_value must equal candidate value" in issue for issue in validate_document_record(invalid)))
if __name__ == "__main__":
    unittest.main()
