"""Invoice line items and tables with evidence, and the sum-versus-total check (REQ-053)."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from alfa_document_intelligence.contracts import validate_document_record
from alfa_document_intelligence.document_validation import validate_document_consistency
from alfa_document_intelligence.invoice_line_items import extract_line_items
from alfa_document_intelligence.ocr_adapter import OCRPageResult, OCRToken


def _row(index: int, top: float, cells: list[tuple[float, str]]) -> list[OCRToken]:
    return [
        OCRToken(f"r{index}c{column}", text, ((x, top), (x + 0.15, top), (x + 0.15, top + 0.02), (x, top + 0.02)), 0.9)
        for column, (x, text) in enumerate(cells)
    ]


def _invoice_page(rows: list[list[tuple[float, str]]]) -> OCRPageResult:
    tokens = []
    for index, cells in enumerate(rows):
        tokens.extend(_row(index, 0.05 + index * 0.05, cells))
    return OCRPageResult(
        source_sha256="e" * 64, page_number=1, engine_name="synthetic", engine_version="1",
        language="it+en", tokens=tuple(tokens),
    )


INVOICE = [
    [(0.05, "Fattura n. 12")],
    [(0.05, "Descrizione"), (0.5, "Qtà"), (0.65, "Prezzo"), (0.8, "Importo")],
    [(0.05, "Consulenza"), (0.5, "2"), (0.65, "50,00"), (0.8, "100,00")],
    [(0.05, "Trasferta"), (0.5, "1"), (0.65, "30,00"), (0.8, "30,00")],
    [(0.05, "Materiale"), (0.8, "12,50")],
    [(0.05, "Totale"), (0.8, "142,50")],
    [(0.05, "Grazie 1,00")],
]


def _first(candidate):
    if candidate["status"] == "observed":
        return candidate["value"]
    return candidate["alternatives"][0]["value"] if candidate["alternatives"] else None


class LineItemExtractionTests(unittest.TestCase):
    def test_table_rows_become_items_with_evidence(self):
        items = extract_line_items([_invoice_page(INVOICE)])
        self.assertEqual([_first(item["description"]) for item in items], ["Consulenza", "Trasferta", "Materiale"])
        self.assertEqual([_first(item["amount"]) for item in items], ["100.00", "30.00", "12.50"])
        self.assertEqual([_first(item["unit_price"]) for item in items], ["50.00", "30.00", None])
        self.assertEqual([_first(item["quantity"]) for item in items], ["2", "1", None])
        first = items[0]
        self.assertEqual(first["line_id"], "item-p0001-00003")
        self.assertEqual(first["amount"]["status"], "uncertain")
        evidence = first["amount"]["evidence"][0]
        self.assertEqual(evidence["page_number"], 1)
        self.assertEqual(evidence["source_sha256"], "e" * 64)
        self.assertTrue(evidence["token_ids"])
        self.assertEqual(evidence["region"]["coordinate_space"], "normalized_page")

    def test_no_header_means_no_items(self):
        rows = [row for row in INVOICE if row[0][1] != "Descrizione"]
        self.assertEqual(extract_line_items([_invoice_page(rows)]), [])

    def test_quantity_needs_a_quantity_column(self):
        rows = [[(0.05, "Descrizione"), (0.8, "Importo")], [(0.05, "Camera 2 notti"), (0.8, "160,00")]]
        items = extract_line_items([_invoice_page(rows)])
        self.assertEqual(_first(items[0]["quantity"]), None)
        self.assertEqual(_first(items[0]["amount"]), "160.00")


    def test_a_row_read_as_one_text_is_split_into_words(self):
        rows = [[(0.05, "Descrizione Qtà Prezzo Importo")], [(0.05, "Consulenza 2 50,00 100,00")], [(0.05, "Totale 100,00")]]
        items = extract_line_items([_invoice_page(rows)])
        self.assertEqual(
            [(_first(item["description"]), _first(item["quantity"]), _first(item["unit_price"]), _first(item["amount"])) for item in items],
            [("Consulenza", "2", "50.00", "100.00")],
        )

    def test_quantity_header_read_without_its_accent(self):
        # Observed OCR readings of "Qtà": accent dropped, or replaced by a non-Latin character.
        for header in ("Qt", "Qt凶", "Qtá", "Qta."):
            with self.subTest(header=header):
                rows = [[(0.05, "Descrizione"), (0.5, header), (0.65, "Prezzo"), (0.8, "Importo")],
                        [(0.05, "Consulenza"), (0.5, "2"), (0.65, "50,00"), (0.8, "100,00")]]
                item = extract_line_items([_invoice_page(rows)])[0]
                self.assertEqual((_first(item["description"]), _first(item["quantity"])), ("Consulenza", "2"))

def _record(items, total_value, total_status="uncertain"):
    record = json.loads((Path(__file__).parent / "fixtures" / "synthetic_invoice.json").read_text(encoding="utf-8"))
    record["schema_version"] = "0.3.0"
    evidence = record["fields"]["total_amount"]["evidence"]
    if total_status == "observed":
        record["fields"]["total_amount"] = {"value": total_value, "status": "observed", "alternatives": [], "evidence": evidence}
    else:
        record["fields"]["total_amount"] = {
            "value": None, "status": "uncertain", "evidence": evidence,
            "alternatives": [{"value": total_value, "status": "observed", "evidence": evidence}],
        }
    # Bind the synthetic items to the fixture's own source (same evidence shape as OCR output).
    source = record["source"]["sha256"]
    for item in items:
        for name in ("description", "quantity", "unit_price", "amount"):
            for evidence_item in item[name]["evidence"]:
                evidence_item["source_sha256"] = source
            for alternative in item[name]["alternatives"]:
                for evidence_item in alternative["evidence"]:
                    evidence_item["source_sha256"] = source
    record["line_items"] = items
    return record


class LineItemSumTests(unittest.TestCase):
    def setUp(self):
        self.items = extract_line_items([_invoice_page(INVOICE)])

    def _finding(self, record):
        findings = [item for item in validate_document_consistency(record) if item["rule_id"] == "line-items-sum-total"]
        self.assertEqual(len(findings), 1)
        return findings[0]

    def test_record_with_items_satisfies_the_contract(self):
        self.assertEqual(validate_document_record(_record(copy.deepcopy(self.items), "142.50")), [])

    def test_matching_sum_needs_review_when_values_are_uncertain(self):
        finding = self._finding(_record(copy.deepcopy(self.items), "142.50"))
        self.assertEqual((finding["outcome"], finding["message_code"]), ("indeterminate", "line_items_sum_matches_total_requires_review"))
        self.assertEqual(finding["field_names"], ["total_amount"])

    def test_different_sum_is_flagged_for_review(self):
        finding = self._finding(_record(copy.deepcopy(self.items), "150.00"))
        self.assertEqual((finding["outcome"], finding["message_code"]), ("indeterminate", "line_items_sum_differs_from_total"))



class LineItemPresentationTests(unittest.TestCase):
    def test_review_page_lists_the_line_items(self):
        from alfa_document_intelligence.local_intake_app import _render_editable_record

        items = extract_line_items([_invoice_page(INVOICE)])
        html = _render_editable_record(_record(items, "142.50"), document_id="doc-1", has_source=False)
        self.assertIn("Righe del documento", html)
        self.assertIn("<td>Consulenza</td><td>2</td><td>50.00</td><td>100.00</td><td>1</td>", html)
        self.assertIn("da verificare", html)


if __name__ == "__main__":
    unittest.main()
