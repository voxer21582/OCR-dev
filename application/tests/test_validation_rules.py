"""Versioned validation rules; reviewed records keep their findings (REQ-064)."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from alfa_document_intelligence.contracts import validate_document_record
from alfa_document_intelligence.document_validation import validate_document_consistency
from alfa_document_intelligence.validation_rules import RULES, RuleSpec, revalidate, ruleset

_FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_invoice.json"


def _record() -> dict:
    record = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    record["schema_version"] = "0.3.0"
    for name, value in (("taxable_base", "100.00"), ("vat_amount", "23.45")):
        candidate = copy.deepcopy(record["fields"]["total_amount"])
        candidate.pop("normalization", None)
        record["fields"][name] = candidate | {"value": value}
    return record


EXTRA = RuleSpec("synthetic-extra-rule", "1", "date_consistency", "regola di prova")


def _with_extra(record: dict) -> list[dict]:
    return validate_document_consistency(record) + [{
        "rule_id": "synthetic-extra-rule", "rule_version": "1", "dimension": "date_consistency",
        "severity": "info", "outcome": "pass", "evidence": [], "field_names": ["issue_date"],
        "message_code": "synthetic_extra_rule_passed",
    }]


class ValidationRuleRegistryTests(unittest.TestCase):
    def test_every_finding_carries_the_registered_version(self):
        findings = validate_document_consistency(_record())
        self.assertTrue(findings)
        for finding in findings:
            self.assertIn(finding["rule_id"], RULES)
            self.assertEqual(finding["rule_version"], RULES[finding["rule_id"]].version)

    def test_registry_lists_every_rule_with_a_description(self):
        self.assertEqual(set(RULES), {
            "hotel-stay-date-order", "taxable-base-vat-total-arithmetic",
            "required-custom-field", "line-items-sum-total",
        })
        for rule_id, spec in RULES.items():
            self.assertEqual(spec.rule_id, rule_id)
            self.assertTrue(spec.description_it)
        self.assertEqual(ruleset(), {rule_id: spec.version for rule_id, spec in RULES.items()})

    def test_a_new_rule_applies_to_unreviewed_records_only(self):
        rules = dict(RULES, **{EXTRA.rule_id: EXTRA})
        fresh = revalidate(_record(), validate=_with_extra, rules=rules)
        self.assertIn("synthetic-extra-rule", {item["rule_id"] for item in fresh["validation_findings"]})
        self.assertEqual(fresh["validation_ruleset"]["synthetic-extra-rule"], "1")

        reviewed = revalidate(_record())
        reviewed["review"] = {"status": "in_progress", "events": [{"event_id": "synthetic"}]}
        before = copy.deepcopy(reviewed)
        after = revalidate(reviewed, validate=_with_extra, rules=rules)
        self.assertEqual(after, before)

    def test_ruleset_is_part_of_a_valid_record(self):
        record = revalidate(_record())
        self.assertEqual(record["validation_ruleset"], ruleset())
        self.assertEqual(validate_document_record(record), [])
        broken = dict(record, validation_ruleset={"rule": 1})
        self.assertTrue(validate_document_record(broken))


    def test_review_page_names_the_rules_used(self):
        from alfa_document_intelligence.local_intake_app import _render_editable_record

        html = _render_editable_record(revalidate(_record()), document_id="doc-1", has_source=False)
        self.assertIn("Verifiche eseguite con le regole:", html)
        self.assertIn("Imponibile più IVA è uguale al totale. (versione 1)", html)
        self.assertNotIn("data di partenza", html)  # the hotel rule did not apply to this invoice


    def test_registry_dimensions_match_the_findings_and_the_schema(self):
        import json as _json
        schema = _json.loads((Path(__file__).resolve().parents[1] / "src" / "alfa_document_intelligence" / "schemas" / "document.schema.json").read_text(encoding="utf-8"))
        allowed = set(schema["$defs"]["validationFinding"]["properties"]["dimension"]["enum"])
        for spec in RULES.values():
            self.assertIn(spec.dimension, allowed, spec.rule_id)
        for finding in validate_document_consistency(_record()):
            self.assertEqual(finding["dimension"], RULES[finding["rule_id"]].dimension)

    def test_ruleset_versions_must_be_plain_digits(self):
        record = revalidate(_record())
        self.assertTrue(validate_document_record(dict(record, validation_ruleset={"line-items-sum-total": "\u00b2"})))
        self.assertTrue(validate_document_record(dict(record, validation_ruleset={"Bad Id": "1"})))

    def test_a_queued_status_without_events_is_not_a_review(self):
        record = revalidate(_record())
        record["review"] = {"status": "queued", "events": []}
        record["validation_findings"] = []
        self.assertTrue(revalidate(record)["validation_findings"])


if __name__ == "__main__":
    unittest.main()
