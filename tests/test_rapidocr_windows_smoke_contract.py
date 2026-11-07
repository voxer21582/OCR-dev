import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "tools" / "rapidocr_synthetic_windows_smoke.py"
SPEC = importlib.util.spec_from_file_location("rapidocr_smoke", SCRIPT)
SMOKE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SMOKE)


class AggregateMetricTests(unittest.TestCase):
    def test_report_contains_aggregate_metrics_and_never_echoes_text(self):
        gold = {f"case-{i}": f"SYNTHETIC GOLD {i}" for i in range(7)}
        observed = {case: f"PRIVATE OCR TEXT {i}" for i, case in enumerate(gold)}

        report = SMOKE.aggregate_metrics(gold, observed)
        encoded = json.dumps(report, sort_keys=True)

        self.assertEqual(report["case_count"], 7)
        self.assertGreater(report["character_count"], 0)
        self.assertIn("character_error_rate", report)
        self.assertIn("word_error_rate", report)
        self.assertNotIn("SYNTHETIC GOLD", encoded)
        self.assertNotIn("PRIVATE OCR TEXT", encoded)

    def test_rejects_missing_or_extra_synthetic_cases(self):
        gold = {f"case-{i}": f"GOLD {i}" for i in range(7)}
        observed = dict(gold)
        del observed["case-6"]

        with self.assertRaisesRegex(ValueError, "case identities"):
            SMOKE.aggregate_metrics(gold, observed)

    def test_edit_distance_aggregates_transpositions_as_two_edits(self):
        self.assertEqual(SMOKE.edit_distance("AB", "BA"), 2)

    def test_word_error_rate_uses_word_tokens_not_character_edits(self):
        gold = {f"case-{i}": "TOTAL EUR" for i in range(7)}
        observed = {f"case-{i}": "TOTAL USD" for i in range(7)}

        report = SMOKE.aggregate_metrics(gold, observed)

        self.assertEqual(report["word_errors"], 7)
        self.assertEqual(report["word_count"], 14)
        self.assertEqual(report["word_error_rate"], 0.5)


if __name__ == "__main__":
    unittest.main()
