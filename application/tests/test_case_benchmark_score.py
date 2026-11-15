"""Scoring of a case export against the benchmark manifest (numbers only)."""
from __future__ import annotations

import unittest

from tools.case_benchmark_score import score_case_export


def _sha(n: int) -> str:
    return f"{n:064x}"


def _manifest() -> dict:
    receipts = [
        {"receipt": 1, "file": "receipts/receipt-001.png", "date": "2026-11-02", "amount": "10,00", "expected": "match"},
        {"receipt": 2, "file": "receipts/receipt-002.png", "date": "2026-11-20", "amount": "20,00", "expected": "match"},
        {"receipt": 3, "file": "receipts/receipt-003.jpg", "date": "2026-11-21", "amount": "30,00", "expected": "amount_conflict"},
        {"receipt": 4, "file": "receipts/receipt-004.pdf", "date": "2026-11-05", "amount": "40,00", "expected": "unused"},
    ]
    rows = [
        {"row": 1, "date": "2026-11-02", "amount": "10,00", "currency": "EUR", "receipt": 1},
        {"row": 2, "date": "2026-11-20", "amount": "20,00", "currency": "EUR", "receipt": 2},
        {"row": 3, "date": "2026-11-21", "amount": "31,11", "currency": "EUR", "receipt": 3},
        {"row": 4, "date": "2026-11-07", "amount": "777,77", "currency": "EUR", "receipt": None},
    ]
    files = {"statement.pdf": _sha(100)}
    files.update({item["file"]: _sha(item["receipt"]) for item in receipts})
    return {"version": "ocr2-case-benchmark-v1", "files": files, "statement_rows": rows, "receipts": receipts}


def _line(row: int, *, date_alternatives=None, suggestions=(), findings=()) -> dict:
    date = {"status": "observed", "value": "2026-11-20", "alternatives": []}
    if date_alternatives is not None:
        date = {
            "status": "uncertain", "value": None,
            "alternatives": [
                {"value": value, "status": "uncertain", "normalization": {"rule_id": rule}}
                for value, rule in date_alternatives
            ],
        }
    return {
        "line_id": f"line-{row}",
        "fields": {
            "description": {"status": "observed", "value": f"Spesa {row:03d}", "alternatives": []},
            "date": date,
        },
        "suggestions": [
            {"document_id": f"doc-{n}", "source_sha256": _sha(n), "reasons": list(reasons)}
            for n, reasons in suggestions
        ],
        "findings": list(findings),
    }


def _export() -> dict:
    return {
        "attachments": [{"document_id": f"doc-{n}", "source_sha256": _sha(n)} for n in (1, 2, 3, 4)],
        "lines": [
            _line(1, date_alternatives=[("2026-11-02", "date-dmy-hint"), ("2026-02-11", "iso-date")],
                  suggestions=[(1, ["possible_amount_and_currency_match", "possible_date_match"])]),
            # The right receipt is first but only as a possible conflict: not a match.
            _line(2, suggestions=[(2, ["possible_amount_conflict"])], findings=["possible_amount_conflict"]),
            _line(3, suggestions=[(3, ["possible_amount_conflict"])], findings=["possible_amount_conflict"]),
            _line(4, findings=["missing_support"]),
            {"line_id": "line-header", "fields": {"description": {"status": "observed", "value": "Pagina 1 di 4", "alternatives": []}},
             "suggestions": [], "findings": ["missing_support"]},
        ],
        "unused_document_ids": ["doc-4"],
    }


class CaseBenchmarkScoreTests(unittest.TestCase):
    def test_possible_conflict_is_not_a_match(self):
        score = score_case_export(_export(), _manifest())
        self.assertEqual(score["correct_receipt_ranked_first"], [1, 2])
        self.assertEqual(score["amount_conflicts_flagged"], [1, 1])

    def test_unused_receipts_listed(self):
        score = score_case_export(_export(), _manifest())
        self.assertEqual(score["unused_receipts"], [4])
        self.assertEqual(score["missing_support_rows"], [1, 1])

    def test_lines_headers_and_date_hints_are_counted(self):
        score = score_case_export(_export(), _manifest())
        self.assertEqual(score["statement_lines_found"], [4, 4])
        self.assertEqual(score["header_lines_proposed"], 1)
        self.assertEqual(score["ambiguous_dates_with_correct_hint"], [1, 2])
        self.assertEqual(score["ambiguous_candidates"], 0)

    def test_possible_matches_are_counted_apart_and_conflicting_firsts_are_not_matches(self):
        export = _export()
        score = score_case_export(export, _manifest())
        self.assertEqual(score["correct_receipt_ranked_first"], [1, 2])
        self.assertEqual(score["correct_receipt_first_possible_only"], 1)
        export["lines"][0]["suggestions"][0]["reasons"] = ["amount_and_currency_match", "date_conflict"]
        self.assertEqual(score_case_export(export, _manifest())["correct_receipt_ranked_first"], [0, 2])
        export["lines"][0]["suggestions"][0]["reasons"] = ["amount_and_currency_match"]
        score = score_case_export(export, _manifest())
        self.assertEqual(score["correct_receipt_ranked_first"], [1, 2])
        self.assertEqual(score["correct_receipt_first_possible_only"], 0)

    def test_conflict_counts_only_on_the_expected_receipts_own_suggestion(self):
        export = _export()
        # Receipt 3 is suggested for another reason; the conflict comes from receipt 4.
        export["lines"][2]["suggestions"] = [
            {"document_id": "doc-4", "source_sha256": _sha(4), "reasons": ["possible_amount_conflict"]},
            {"document_id": "doc-3", "source_sha256": _sha(3), "reasons": ["possible_date_match"]},
        ]
        self.assertEqual(score_case_export(export, _manifest())["amount_conflicts_flagged"], [0, 1])

    def test_same_day_and_month_is_not_an_ambiguous_date(self):
        manifest = _manifest()
        manifest["statement_rows"][1]["date"] = "2026-11-11"
        export = _export()
        export["lines"][1]["fields"]["date"] = {"status": "observed", "value": "2026-11-11", "alternatives": []}
        self.assertEqual(score_case_export(export, manifest)["ambiguous_dates_with_correct_hint"], [1, 2])

    def test_output_contains_no_text(self):
        def strings(value):
            if isinstance(value, str):
                yield value
            elif isinstance(value, dict):
                for child in value.values():
                    yield from strings(child)
            elif isinstance(value, list):
                for child in value:
                    yield from strings(child)

        self.assertEqual(list(strings(score_case_export(_export(), _manifest()))), [])


if __name__ == "__main__":
    unittest.main()
