"""The four GOAL field states (plus 'not applicable') with a reason, from the six internal ones (REQ-060)."""
from __future__ import annotations

import unittest

from alfa_document_intelligence.field_status import GOAL_STATUSES, failed_rules_by_field, goal_status


def _candidate(status, alternatives=()):
    return {"value": None, "status": status, "alternatives": list(alternatives), "evidence": []}


class GoalStatusTests(unittest.TestCase):
    def test_every_internal_status_maps_to_a_goal_status_with_a_reason(self):
        cases = {
            "observed": ("valido", "letto dal documento"),
            "uncertain": ("incerto", "lettura incerta"),
            "absent": ("mancante", "non trovato nel documento"),
            "unreadable": ("mancante", "presente ma illeggibile"),
            "rejected": ("non_valido", "scartato in revisione"),
            "not_applicable": ("non_applicabile", "non previsto per questo tipo di documento"),
            "something-else": ("incerto", "stato non riconosciuto"),
        }
        for status, expected in cases.items():
            with self.subTest(status=status):
                result = goal_status(_candidate(status))
                self.assertEqual(result, expected)
                self.assertIn(result[0], GOAL_STATUSES)
                self.assertTrue(result[1])

    def test_uncertain_with_alternatives_counts_them(self):
        self.assertEqual(
            goal_status(_candidate("uncertain", [{"value": "a"}, {"value": "b"}])),
            ("incerto", "più letture possibili: 2"),
        )

    def test_observed_with_a_failed_rule_is_not_valid(self):
        self.assertEqual(
            goal_status(_candidate("observed"), failed_rule_ids=frozenset({"taxable-base-vat-total-arithmetic"})),
            ("non_valido", "la verifica taxable-base-vat-total-arithmetic non è superata"),
        )

    def test_failed_rules_are_grouped_by_field(self):
        record = {"validation_findings": [
            {"rule_id": "r1", "outcome": "fail", "field_names": ["total_amount", "vat_amount"]},
            {"rule_id": "r2", "outcome": "pass", "field_names": ["total_amount"]},
            {"rule_id": "r3", "outcome": "indeterminate", "field_names": ["issue_date"]},
        ]}
        self.assertEqual(failed_rules_by_field(record), {
            "total_amount": frozenset({"r1"}), "vat_amount": frozenset({"r1"}),
        })

    def test_malformed_input_never_yields_an_empty_reason(self):
        for candidate in (None, {}, {"status": 3}):
            with self.subTest(candidate=candidate):
                status, reason = goal_status(candidate)
                self.assertEqual(status, "incerto")
                self.assertTrue(reason)


if __name__ == "__main__":
    unittest.main()
