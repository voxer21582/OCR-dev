"""Synthetic contract tests for evidence-backed expense reconciliation."""
import copy
import hashlib
import json
from pathlib import Path
import unittest

from alfa_document_intelligence.expense_reconciliation import (
    ReconciliationError,
    append_line_review,
    build_reconciliation,
    validate_reconciliation,
)


def _candidate(value, source_hash, *, status="observed", page=1):
    evidence = []
    if status in {"observed", "uncertain", "unreadable", "rejected"}:
        evidence = [{
            "source_sha256": source_hash, "page_number": page,
            "text_span": {"start": 0, "end": 1, "unit": "unicode_codepoint"},
            "producer": {"stage": "semantic_extraction", "name": "synthetic-test", "version": "1"},
        }]
    return {"value": value, "status": status, "alternatives": [], "evidence": evidence}


_FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_fiscal_receipt.json"


def _document(document_id, digest, *, family="fiscal_receipt", amount="42.50", currency="EUR", date="2026-10-01", merchant="Caffe Test"):
    record = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    original_hash = record["source"]["sha256"]
    record["document_id"] = document_id
    record["document_family"] = family
    record["source"]["sha256"] = digest

    def replace_source_hashes(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "source_sha256" and child == original_hash:
                    value[key] = digest
                else:
                    replace_source_hashes(child)
        elif isinstance(value, list):
            for child in value:
                replace_source_hashes(child)

    replace_source_hashes(record)
    for field, value in (("total_amount", amount), ("currency", currency), ("issue_date", date), ("transaction_date", date), ("merchant_name", merchant)):
        if field in record["fields"]:
            candidate = record["fields"][field]
            candidate["value"] = value
            for evidence in candidate["evidence"]:
                evidence["literal"] = value
            if candidate.get("normalization"):
                candidate["normalization"]["original_literal"] = value
                candidate["normalization"]["normalized_value"] = value
    return record


def _case():
    statement_hash = "a" * 64
    line = {
        "line_id": "line-1",
        "amount": _candidate("42.50", statement_hash),
        "currency": _candidate("EUR", statement_hash),
        "date": _candidate("2026-10-01", statement_hash),
        "merchant": _candidate("Caffe Test", statement_hash),
        "description": _candidate("Pranzo", statement_hash),
    }
    docs = {
        "statement": _document("statement", statement_hash, family="expense_report"),
        "receipt-1": _document("receipt-1", "b" * 64),
    }
    return line, docs


class ExpenseReconciliationTests(unittest.TestCase):
    def build(self, line=None, docs=None, attachments=None):
        default_line, default_docs = _case()
        return build_reconciliation(
            "case-1", "statement", default_docs["statement"]["source"]["sha256"],
            [line or default_line], attachments or [{"document_id": "receipt-1", "included": True}],
            docs or default_docs,
        )

    def test_exact_amount_and_currency_match_ranks_first_with_explainable_reasons(self):
        result = self.build()
        suggestion = result["lines"][0]["suggestions"][0]
        self.assertEqual(suggestion["document_id"], "receipt-1")
        self.assertIn("amount_and_currency_match", suggestion["reasons"])
        self.assertEqual(suggestion["supporting_fields"]["total_amount"]["evidence"][0]["source_sha256"], "b" * 64)
        self.assertIn("page_number", suggestion["supporting_fields"]["total_amount"]["evidence"][0])
        self.assertNotIn("probability", suggestion)

    def test_date_and_vendor_are_supporting_signals(self):
        line, docs = _case()
        docs["receipt-1"]["fields"]["total_amount"] = _candidate("99.00", "b" * 64)
        result = self.build(line, docs)
        reasons = result["lines"][0]["suggestions"][0]["reasons"]
        self.assertIn("date_match", reasons)
        self.assertIn("merchant_match", reasons)
        self.assertIn("amount_conflict", result["lines"][0]["findings"])

    def test_currency_and_date_discrepancies_are_explicit_findings(self):
        line, docs = _case()
        currency = docs["receipt-1"]["fields"]["currency"]
        currency["value"] = "USD"
        currency["evidence"][0]["literal"] = "USD"
        currency["normalization"] = {
            "rule_id": "synthetic-currency", "rule_version": "1",
            "original_literal": "USD", "normalized_value": "USD",
        }
        currency_result = self.build(line, docs)
        self.assertIn("currency_conflict", currency_result["lines"][0]["findings"])
        docs = _case()[1]
        docs["receipt-1"]["fields"]["issue_date"]["value"] = "2026-10-02"
        docs["receipt-1"]["fields"]["issue_date"]["evidence"][0]["literal"] = "2026-10-02"
        docs["receipt-1"]["fields"]["issue_date"]["normalization"]["original_literal"] = "2026-10-02"
        docs["receipt-1"]["fields"]["issue_date"]["normalization"]["normalized_value"] = "2026-10-02"
        date_result = self.build(line, docs)
        self.assertIn("date_conflict", date_result["lines"][0]["findings"])

    def test_identical_statement_lines_are_flagged_as_possible_duplicates_only(self):
        line, docs = _case()
        duplicate = copy.deepcopy(line)
        duplicate["line_id"] = "line-2"
        result = build_reconciliation(
            "case-1", "statement", "a" * 64, [line, duplicate],
            [{"document_id": "receipt-1", "included": True}], docs,
        )
        self.assertEqual(result["possible_duplicate_claim_groups"][0]["line_ids"], ["line-1", "line-2"])
        self.assertIn("possible_duplicate_claim", result["lines"][0]["findings"])
        self.assertEqual(result["lines"][0]["status"], "unreviewed")

    def test_missing_support_and_unused_receipt_are_reported(self):
        line, docs = _case()
        docs["receipt-1"]["fields"] = {}
        docs["receipt-2"] = _document("receipt-2", "c" * 64, amount="8.00", date="2026-08-02", merchant="Altro")
        result = self.build(line, docs, [
            {"document_id": "receipt-1", "included": True},
            {"document_id": "receipt-2", "included": True},
        ])
        self.assertIn("missing_support", result["lines"][0]["findings"])
        self.assertEqual(result["unused_document_ids"], ["receipt-1", "receipt-2"])

    def test_duplicate_source_is_reported_without_dropping_documents(self):
        line, docs = _case()
        docs["receipt-2"] = _document("receipt-2", "b" * 64)
        result = self.build(line, docs, [
            {"document_id": "receipt-1", "included": True},
            {"document_id": "receipt-2", "included": True},
        ])
        self.assertEqual(len(result["duplicate_source_groups"]), 1)
        self.assertEqual(result["duplicate_source_groups"][0]["document_ids"], ["receipt-1", "receipt-2"])

    def test_equal_rank_candidates_are_ambiguous(self):
        line, docs = _case()
        docs["receipt-2"] = _document("receipt-2", "c" * 64)
        result = self.build(line, docs, [
            {"document_id": "receipt-1", "included": True},
            {"document_id": "receipt-2", "included": True},
        ])
        self.assertIn("ambiguous_candidates", result["lines"][0]["findings"])

    def test_absent_and_uncertain_values_do_not_become_matches(self):
        line, docs = _case()
        line["amount"] = _candidate(None, "a" * 64, status="uncertain")
        line["amount"]["alternatives"] = [{"value": "42.50", "status": "uncertain", "evidence": line["amount"]["evidence"]}]
        line["currency"] = _candidate(None, "a" * 64, status="absent")
        result = self.build(line, docs)
        self.assertIn("uncertain_statement_fields", result["lines"][0]["findings"])
        self.assertNotIn("amount_and_currency_match", result["lines"][0]["suggestions"][0]["reasons"])

    def test_evidence_hash_must_bind_to_the_exact_source_document(self):
        line, docs = _case()
        line["amount"]["evidence"][0]["source_sha256"] = "f" * 64
        with self.assertRaisesRegex(ReconciliationError, "evidence"):
            self.build(line, docs)

    def test_review_is_revision_and_source_bound_and_idempotent(self):
        result = self.build()
        line = result["lines"][0]
        event = {
            "event_id": "event-1", "sequence": 1, "case_revision": result["case_revision"],
            "line_id": line["line_id"], "line_evidence_sha256": line["evidence_sha256"],
            "action": "confirmed", "candidate_sources": [{"document_id": "receipt-1", "source_sha256": "b" * 64}],
            "reviewer_note": "",
        }
        review = {
            "line_id": event["line_id"], "expected_line_evidence_sha256": event["line_evidence_sha256"],
            "action": event["action"], "candidate_sources": event["candidate_sources"],
            "event_id": event["event_id"], "reviewer_note": event["reviewer_note"],
        }
        first = append_line_review(result, expected_case_revision=result["case_revision"], **review)
        replay = append_line_review(first, expected_case_revision=result["case_revision"], **review)
        self.assertEqual(len(replay["review_events"]), 1)
        self.assertEqual(replay["lines"][0]["status"], "confirmed")
        self.assertEqual(replay["lines"][0]["current_review_event_id"], "event-1")
        altered = copy.deepcopy(event)
        altered["reviewer_note"] = "conflicting replay"
        with self.assertRaisesRegex(ReconciliationError, "conflicting"):
            append_line_review(first, expected_case_revision=result["case_revision"], **{**review, "reviewer_note": altered["reviewer_note"]})
        with self.assertRaisesRegex(ReconciliationError, "revision"):
            append_line_review(result, expected_case_revision="0" * 64, **review)
        with self.assertRaisesRegex(ReconciliationError, "source"):
            bad = copy.deepcopy(event)
            bad["candidate_sources"][0]["source_sha256"] = "f" * 64
            append_line_review(result, expected_case_revision=result["case_revision"], **{**review, "candidate_sources": bad["candidate_sources"]})
        validate_reconciliation(first, {"statement": _case()[1]["statement"], "receipt-1": _case()[1]["receipt-1"]})

    def test_review_history_remains_valid_but_stale_after_source_revision_changes(self):
        original = self.build()
        line = original["lines"][0]
        reviewed = append_line_review(
            original, expected_case_revision=original["case_revision"],
            line_id=line["line_id"], expected_line_evidence_sha256=line["evidence_sha256"],
            action="confirmed", candidate_sources=[{"document_id": "receipt-1", "source_sha256": "b" * 64}],
            event_id="event-stale", reviewer_note=None,
        )
        next_docs = _case()[1]
        next_docs["receipt-1"] = _document("receipt-1", "d" * 64)
        current = self.build(docs=next_docs)
        current["review_events"] = reviewed["review_events"]
        self.assertNotEqual(current["case_revision"], reviewed["case_revision"])
        validate_reconciliation(current, next_docs)
        self.assertEqual(current["lines"][0]["status"], "unreviewed")

    def test_latest_same_revision_event_is_the_current_projection(self):
        result = self.build()
        line = result["lines"][0]
        first = append_line_review(
            result, expected_case_revision=result["case_revision"],
            line_id=line["line_id"], expected_line_evidence_sha256=line["evidence_sha256"],
            action="confirmed", candidate_sources=[{"document_id": "receipt-1", "source_sha256": "b" * 64}],
            event_id="event-first", reviewer_note=None,
        )
        second = append_line_review(
            first, expected_case_revision=result["case_revision"],
            line_id=line["line_id"], expected_line_evidence_sha256=line["evidence_sha256"],
            action="rejected", candidate_sources=[{"document_id": "receipt-1", "source_sha256": "b" * 64}],
            event_id="event-second", reviewer_note=None,
        )
        self.assertEqual(second["lines"][0]["status"], "rejected")
        self.assertEqual(second["lines"][0]["current_review_event_id"], "event-second")

    def test_tampered_review_event_digest_is_rejected(self):
        result = self.build()
        line = result["lines"][0]
        reviewed = append_line_review(
            result, expected_case_revision=result["case_revision"],
            line_id=line["line_id"], expected_line_evidence_sha256=line["evidence_sha256"],
            action="confirmed", candidate_sources=[{"document_id": "receipt-1", "source_sha256": "b" * 64}],
            event_id="event-tamper", reviewer_note=None,
        )
        reviewed["review_events"][0]["action"] = "rejected"
        _, docs = _case()
        with self.assertRaisesRegex(ReconciliationError, "digest"):
            validate_reconciliation(reviewed, docs)

    def test_append_rejects_semantically_invalid_prior_event_even_with_recomputed_digest(self):
        result = self.build()
        line = result["lines"][0]
        invalid_body = {
            "event_id": "invalid-prior", "case_revision": result["case_revision"],
            "line_id": line["line_id"], "line_evidence_sha256": line["evidence_sha256"],
            "action": "confirmed", "candidate_sources": [], "reviewer_note": None,
        }
        invalid_digest = hashlib.sha256(json.dumps(
            invalid_body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")).hexdigest()
        result["review_events"] = [{**invalid_body, "sequence": 1, "event_sha256": invalid_digest}]
        line["status"] = "confirmed"
        line["current_review_event_id"] = "invalid-prior"
        with self.assertRaisesRegex(ReconciliationError, "confirmation requires"):
            append_line_review(
                result, expected_case_revision=result["case_revision"],
                line_id=line["line_id"], expected_line_evidence_sha256=line["evidence_sha256"],
                action="rejected", candidate_sources=[], event_id="event-next", reviewer_note=None,
            )

    def test_tampered_suggestion_is_rejected_against_current_source_records(self):
        result = self.build()
        result["lines"][0]["suggestions"][0]["reasons"] = ["merchant_match"]
        _, docs = _case()
        with self.assertRaisesRegex(ReconciliationError, "suggestions"):
            validate_reconciliation(result, docs)


if __name__ == "__main__":
    unittest.main()
