import unittest

from alfa_document_intelligence.benchmark import evaluate


class EvidenceLocalizationCoverageTests(unittest.TestCase):
    def result(self, gold_evidence, predictions):
        label = {"case_id": "synthetic", "split": "development", "fields": {}, "evidence": gold_evidence}
        prediction = {"case_id": "synthetic", "split": "development", "fields": predictions}
        return evaluate([label], [prediction], "development")["evidence_localization"]

    def candidate(self, evidence):
        return {"status": "uncertain", "value": None, "evidence": evidence}

    def test_missing_and_empty_gold_references_are_unassessable(self):
        result = self.result({"empty": []}, {
            "missing": self.candidate([{"page_number": 1}]),
            "empty": self.candidate([{"page_number": 2}, {"page_number": 3}]),
        })
        self.assertIn("unassessable_predicted_references", result)
        self.assertEqual(result["unassessable_predicted_references"], 3)
        self.assertEqual(result["predicted_references"], 0)
        self.assertEqual(result["labeled_references"], 0)
        self.assertEqual(result["matched_references"], 0)
        self.assertIsNone(result["precision"])
        self.assertIsNone(result["recall"])

    def test_mixed_gold_preserves_assessable_metrics(self):
        result = self.result({"assessed": [{"page_number": 1}, {"page_number": 2}]}, {
            "assessed": self.candidate([{"page_number": 1}, {"page_number": 3}]),
            "unassessed": self.candidate([{"page_number": 1}]),
        })
        self.assertIn("unassessable_predicted_references", result)
        self.assertEqual(result["unassessable_predicted_references"], 1)
        self.assertEqual(result["predicted_references"], 2)
        self.assertEqual(result["labeled_references"], 2)
        self.assertEqual(result["matched_references"], 1)
        self.assertEqual(result["precision"], 0.5)
        self.assertEqual(result["recall"], 0.5)

    def test_empty_predictions_have_no_denominators(self):
        result = self.result({}, {})
        self.assertIn("unassessable_predicted_references", result)
        self.assertEqual(result["unassessable_predicted_references"], 0)
        self.assertEqual(result["predicted_references"], 0)
        self.assertEqual(result["labeled_references"], 0)
        self.assertIsNone(result["precision"])
        self.assertIsNone(result["recall"])

    def test_malformed_unassessable_references_fail_closed(self):
        for evidence in ("bad", ["bad"], [{"page_number": 0}], [{"page_number": True}],
                         [{"page_number": 1, "region": {"polygon": [[0, 0]]}}]):
            with self.subTest(evidence=evidence):
                with self.assertRaisesRegex(ValueError, "predictions: evidence|predictions: region"):
                    self.result({}, {"unassessed": self.candidate(evidence)})

    def test_malformed_orphan_gold_evidence_fails_closed(self):
        for evidence in ("bad", ["bad"], [{"page_number": 0}]):
            with self.subTest(evidence=evidence):
                with self.assertRaisesRegex(ValueError, "labels: evidence"):
                    self.result({"orphan": evidence}, {})

    def test_valid_orphan_gold_evidence_does_not_change_scores(self):
        predictions = {"assessed": self.candidate([{"page_number": 1}])}
        gold = {"assessed": [{"page_number": 1}]}
        baseline = self.result(gold, predictions)
        result = self.result({**gold, "orphan": [{"page_number": 2}]}, predictions)
        self.assertEqual(result, baseline)

    def test_page_match_and_optional_region_matching(self):
        square = {"polygon": [[0, 0], [0.4, 0], [0.4, 0.4], [0, 0.4]]}
        other = {"polygon": [[0.6, 0.6], [1, 0.6], [1, 1], [0.6, 1]]}
        gold = {"page_only": [{"page_number": 1, "region": square}],
                "different_region": [{"page_number": 2, "region": square}],
                "different_page": [{"page_number": 3}]}
        predictions = {"page_only": self.candidate([{"page_number": 1}]),
                       "different_region": self.candidate([{"page_number": 2, "region": other}]),
                       "different_page": self.candidate([{"page_number": 4}])}
        result = self.result(gold, predictions)
        self.assertEqual(result["matched_references"], 1)
        self.assertEqual(result["labeled_references"], 3)
        self.assertEqual(result["predicted_references"], 3)
        self.assertAlmostEqual(result["precision"], 1 / 3)
        self.assertAlmostEqual(result["recall"], 1 / 3)

    def test_precision_scope_is_explicit(self):
        result = self.result({}, {})
        self.assertEqual(result.get("precision_scope"), "field_cases_with_labeled_evidence")

    def test_field_names_are_shared_across_cases_for_evidence_scoring(self):
        labels = [
            {"case_id": "one", "split": "development", "fields": {},
             "evidence": {"custom": [{"page_number": 1}]}},
            {"case_id": "two", "split": "development", "fields": {"custom": "value"}},
        ]
        predictions = [
            {"case_id": "one", "split": "development", "fields": {}},
            {"case_id": "two", "split": "development", "fields": {}},
        ]
        result = evaluate(labels, predictions, "development")["evidence_localization"]
        self.assertEqual(result["labeled_references"], 1)
        self.assertEqual(result["predicted_references"], 0)
        self.assertEqual(result["matched_references"], 0)
        self.assertIsNone(result["precision"])
        self.assertEqual(result["recall"], 0)


if __name__ == "__main__":
    unittest.main()
