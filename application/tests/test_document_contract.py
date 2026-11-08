import copy
import json
import unittest
from pathlib import Path

from alfa_document_intelligence.contracts import validate_document_record

ROOT = Path(__file__).parents[1]
SCHEMA_PATH = ROOT / "src" / "alfa_document_intelligence" / "schemas" / "document.schema.json"
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "synthetic_invoice.json"


class DocumentContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_schema_is_draft_2020_12_and_defines_evidence_binding(self):
        self.assertEqual(self.schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(self.schema["properties"]["schema_version"]["const"], "0.1.0")
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