"""GOAL field state and reason shown in the review page and in the CSV export (REQ-060)."""
from __future__ import annotations

import copy
import csv
import io
import json
from pathlib import Path
import unittest

from alfa_document_intelligence.document_export import CSV_EXPORT_VERSION, export_document_csv
from alfa_document_intelligence.local_intake_app import _render_editable_record

_FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_invoice.json"


def _record() -> dict:
    record = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    total = record["fields"]["total_amount"]
    evidence = total["evidence"]
    record["fields"]["total_amount"] = {
        "value": None, "status": "uncertain", "evidence": copy.deepcopy(evidence),
        "alternatives": [
            {"value": "12.34", "status": "uncertain", "evidence": copy.deepcopy(evidence)},
            {"value": "12.43", "status": "uncertain", "evidence": copy.deepcopy(evidence)},
        ],
    }
    record["fields"]["currency"] = {"value": None, "status": "absent", "evidence": [], "alternatives": []}
    return record


class FieldStatusPresentationTests(unittest.TestCase):
    def test_csv_has_goal_status_and_reason_columns(self):
        rows = list(csv.DictReader(io.StringIO(export_document_csv(_record()))))
        self.assertEqual(CSV_EXPORT_VERSION, "ocr2-document-csv-v3")
        by_field = {row["field_name"]: row for row in rows}
        self.assertEqual(by_field["merchant_name"]["goal_status"], "valido")
        self.assertEqual(by_field["merchant_name"]["goal_status_reason"], "letto dal documento")
        self.assertEqual(by_field["total_amount"]["goal_status"], "incerto")
        self.assertEqual(by_field["total_amount"]["goal_status_reason"], "più letture possibili: 2")
        self.assertEqual(by_field["currency"]["goal_status"], "mancante")
        header = next(csv.reader(io.StringIO(export_document_csv(_record()))))
        self.assertEqual(header.index("goal_status"), header.index("field_name") + 1)

    def test_review_shows_alternatives_regions_and_neutral_value_label(self):
        record = _record()
        record["fields"]["total_amount"]["alternatives"][0]["value"] = "<12.34>"
        html = _render_editable_record(record, document_id="doc-1", has_source=False)
        self.assertIn("&lt;12.34&gt;", html)
        self.assertIn("12.43", html)
        self.assertIn("normalized_page", html)
        self.assertIn("0.8", html)
        self.assertNotIn("Valore verificato:", html)
        self.assertIn("Valore corrente:", html)

    def test_original_alternatives_remain_visible_after_correction(self):
        from alfa_document_intelligence.local_intake_app import _apply_field_correction
        record = _record()
        corrected = _apply_field_correction(record, field_name="total_amount", value="12.34", timestamp="2026-11-15T12:00:00Z")
        html = _render_editable_record(corrected, document_id="doc-1", has_source=False)
        self.assertIn("Alternative originali", html)
        self.assertIn("12.43", html)
        self.assertIn("Valore corrente: 12.34", html)

    def test_review_history_shows_previous_and_new_values_with_evidence(self):
        from alfa_document_intelligence.local_intake_app import _apply_field_correction
        from unittest.mock import patch
        record = _record()
        original = record["fields"]["merchant_name"]["value"]
        with patch("alfa_document_intelligence.local_intake_app._windows_review_actor", return_value="synthetic-reviewer"):
            first = _apply_field_correction(record, field_name="merchant_name", value="<prima>", timestamp="2026-11-15T12:00:00Z")
            second = _apply_field_correction(first, field_name="merchant_name", value="seconda", timestamp="2026-11-15T12:01:00Z")
        html = _render_editable_record(second, document_id="doc-1", has_source=False)
        self.assertIn("Cronologia revisioni", html)
        self.assertIn("synthetic-reviewer", html)
        self.assertIn("2026-11-15T12:01:00Z", html)
        self.assertIn(str(original), html)
        self.assertIn("&lt;prima&gt;", html)
        self.assertIn("seconda", html)
        self.assertIn("Pagina 1", html)
        self.assertIn("human_corrected", html)

    def test_review_history_includes_fiscal_before_after_and_evidence(self):
        from alfa_document_intelligence.review_ledger import append_review_event
        record = _record()
        for action in ("queued", "opened"):
            record = append_review_event(record, actor_id="synthetic", action=action, timestamp="2026-11-15T12:00:00Z")
        old = record["fiscal_document_state"]["status"]
        state = {"status":"payment_evidence", "evidence":copy.deepcopy(record["fiscal_document_state"]["evidence"])}
        record = append_review_event(record, actor_id="synthetic", action="fiscal_state_corrected",
            timestamp="2026-11-15T12:01:00Z", fiscal_state=state, reason_code="synthetic_reason")
        html = _render_editable_record(record, document_id="doc-1", has_source=False)
        self.assertIn("Cronologia revisioni", html)
        self.assertIn(str(old), html)
        self.assertIn("payment_evidence", html)
        self.assertIn("synthetic_reason", html)
        self.assertIn("Pagina 1", html)

    def test_review_history_preserves_original_and_prior_document_family(self):
        from alfa_document_intelligence.review_ledger import append_review_event
        record = _record()
        record["document_family"] = "unknown"
        evidence = copy.deepcopy(record["fiscal_document_state"]["evidence"])
        alternatives = [{"value": name, "status": "observed", "evidence": evidence} for name in ("invoice", "other")]
        record["fields"]["document_family_candidates"] = {"value": None, "status": "uncertain", "alternatives": alternatives, "evidence": evidence}
        for action in ("queued", "opened"):
            record = append_review_event(record, actor_id="synthetic", action=action, timestamp="2026-11-15T12:00:00Z")
        for name in ("invoice", "other"):
            candidate = {"value": name, "status": "observed", "alternatives": [], "evidence": evidence}
            record = append_review_event(record, actor_id="synthetic", action="field_corrected", field_name="document_family",
                candidate=candidate, reason_code="family_review", timestamp="2026-11-15T12:00:00Z")
        html = _render_editable_record(record, document_id="doc-1", has_source=False)
        self.assertIn("campo document_family; precedente unknown; nuovo invoice; prove precedenti: non disponibili", html)
        self.assertIn("campo document_family; precedente unknown; nuovo invoice", html)
        self.assertIn("campo document_family; precedente invoice; nuovo other", html)

    def test_observed_alternative_can_be_selected_with_its_evidence(self):
        from alfa_document_intelligence.local_intake_app import _apply_alternative_selection
        from alfa_document_intelligence.review_ledger import reviewed_overlay
        record = _record()
        record["fields"]["total_amount"]["alternatives"][1]["status"] = "observed"
        result = _apply_alternative_selection(record, field_name="total_amount", alternative_index="1", timestamp="2026-11-15T12:00:00Z")
        event = result["review"]["events"][-1]
        self.assertEqual(event["action"], "alternative_selected")
        self.assertEqual(event["candidate"]["value"], "12.43")
        self.assertEqual(event["candidate"]["evidence"], record["fields"]["total_amount"]["alternatives"][1]["evidence"])
        from alfa_document_intelligence.review_ledger import ReviewRejected, verify_review_ledger, _event_hash
        forged = copy.deepcopy(result)
        forged_event = forged["review"]["events"][-1]
        forged_event["candidate"]["evidence"][0]["literal"] = "altered"
        forged_event["event_hash"] = _event_hash({k: v for k, v in forged_event.items() if k != "event_hash"})
        with self.assertRaises(ReviewRejected):
            verify_review_ledger(forged)
        self.assertEqual(reviewed_overlay(result)["reviewed_fields"]["total_amount"]["value"], "12.43")
        html = _render_editable_record(record, document_id="doc-1", has_source=True)
        self.assertIn("Seleziona questa alternativa", html)

    def test_alternative_selection_rejects_uncertain_or_out_of_range(self):
        from alfa_document_intelligence.local_intake_app import _apply_alternative_selection, IntakeRequestError
        record = _record()
        for index in ("0", "9", "-1", "1.0"):
            with self.subTest(index=index):
                with self.assertRaises(IntakeRequestError):
                    _apply_alternative_selection(record, field_name="total_amount", alternative_index=index, timestamp="2026-11-15T12:00:00Z")

    def test_review_page_shows_state_label_and_reason(self):
        html = _render_editable_record(_record(), document_id="doc-1", has_source=False)
        self.assertIn("Stato: Incerto — più letture possibili: 2", html)
        self.assertIn("Stato: Valido — letto dal documento", html)
        self.assertIn("Stato: Mancante — non trovato nel documento", html)


if __name__ == "__main__":
    unittest.main()
