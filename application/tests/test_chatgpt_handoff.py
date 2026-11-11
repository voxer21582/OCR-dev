import copy
import json
from pathlib import Path

import unittest

from alfa_document_intelligence.chatgpt_handoff import (
    ChatGPTHandoffError,
    build_chatgpt_handoff_prompt,
    blocked_review_notice,
)
from alfa_document_intelligence.expense_reports import build_expense_report_bundle
from alfa_document_intelligence.review_ledger import append_review_event


FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_invoice.json"


def _record():
    record = json.loads(FIXTURE.read_text(encoding="utf-8"))
    record["document_id"] = "note-001"
    record["document_family"] = "expense_report"
    return record


def _confirm(record, field_name, value, timestamp):
    if record["review"]["status"] == "not_started":
        record = append_review_event(
            record, actor_id="synthetic-reviewer", action="queued", timestamp=timestamp
        )
        record = append_review_event(
            record, actor_id="synthetic-reviewer", action="opened", timestamp=timestamp
        )
    candidate = copy.deepcopy(record["fields"][field_name])
    candidate["value"] = value
    candidate["status"] = "observed"
    candidate["alternatives"] = []
    if isinstance(candidate.get("normalization"), dict):
        candidate["normalization"]["normalized_value"] = value
    return append_review_event(
        record,
        actor_id="synthetic-reviewer",
        action="field_corrected",
        timestamp=timestamp,
        field_name=field_name,
        reason_code="human_corrected",
        candidate=candidate,
    )


class ManualChatGPTHandoffTests(unittest.TestCase):
    def test_includes_only_latest_human_confirmed_structured_fields(self):
        record = _record()
        original_ocr_name = copy.deepcopy(record["fields"]["merchant_name"])
        record = _confirm(record, "total_amount", "25.00", "2026-10-15T10:00:00+02:00")
        record = _confirm(record, "total_amount", "26.00", "2026-10-15T10:01:00+02:00")
        documents = {"note-001": record}
        bundle = build_expense_report_bundle("report-001", "note-001", [], documents)

        prompt = build_chatgpt_handoff_prompt(bundle, documents)

        self.assertIn("riscrivere in italiano", prompt)
        self.assertIn('"role": "expense_note"', prompt)
        self.assertIn('"total_amount"', prompt)
        self.assertIn('"value": "26.00"', prompt)
        self.assertNotIn("25.00", prompt)
        self.assertNotIn("merchant_name", prompt)
        self.assertNotIn("Fattura demo", prompt)
        self.assertNotIn("synthetic-invoice.pdf", prompt)
        self.assertEqual(record["fields"]["merchant_name"], original_ocr_name)
        self.assertNotEqual(record["fields"]["total_amount"]["value"], "26.00")

    def test_excludes_confirmed_identifiers_and_irrelevant_fields(self):
        record = _record()
        record["fields"]["vat_registration_number"] = copy.deepcopy(record["fields"]["total_amount"])
        record["fields"]["payment_reference"] = copy.deepcopy(record["fields"]["total_amount"])
        record = _confirm(record, "total_amount", "26.00", "2026-10-15T10:00:00+02:00")
        record = _confirm(record, "vat_registration_number", "IT12345678901", "2026-10-15T10:01:00+02:00")
        record = _confirm(record, "payment_reference", "TX-SECRET-123", "2026-10-15T10:02:00+02:00")
        documents = {"note-001": record}
        bundle = build_expense_report_bundle("report-001", "note-001", [], documents)

        prompt = build_chatgpt_handoff_prompt(bundle, documents)

        self.assertIn('"total_amount"', prompt)
        self.assertNotIn("IT12345678901", prompt)
        self.assertNotIn("TX-SECRET-123", prompt)
        self.assertNotIn("vat_registration_number", prompt)
        self.assertNotIn("payment_reference", prompt)

    def test_requires_at_least_one_reviewed_field(self):
        record = _record()
        documents = {"note-001": record}
        bundle = build_expense_report_bundle("report-001", "note-001", [], documents)

        with self.assertRaisesRegex(ChatGPTHandoffError, "confirm fields"):
            build_chatgpt_handoff_prompt(bundle, documents)

    def test_rejects_bundle_tampering_before_serializing_values(self):
        record = _confirm(_record(), "total_amount", "26.00", "2026-10-15T10:00:00+02:00")
        documents = {"note-001": record}
        bundle = build_expense_report_bundle("report-001", "note-001", [], documents)
        bundle["note_source_sha256"] = "0" * 64

        with self.assertRaisesRegex(ValueError, "does not match"):
            build_chatgpt_handoff_prompt(bundle, documents)

    def test_includes_confirmed_attachment_values_and_page_evidence_only(self):
        note = _record()
        attachment = json.loads(FIXTURE.read_text(encoding="utf-8"))
        attachment["document_id"] = "receipt-001"
        attachment["source"]["original_filename"] = "synthetic-hotel-receipt.pdf"
        attachment = _confirm(
            attachment, "merchant_name", "Albergo Demo", "2026-10-15T10:02:00+02:00"
        )
        documents = {"note-001": note, "receipt-001": attachment}
        bundle = build_expense_report_bundle(
            "report-001", "note-001", ["receipt-001"], documents
        )

        prompt = build_chatgpt_handoff_prompt(bundle, documents)
        payload = json.loads(prompt.split("DATI CONFERMATI:", 1)[1])

        self.assertEqual(payload, [{
            "role": "supporting_document_1",
            "verified_fields": {
                "merchant_name": {"value": "Albergo Demo", "evidence_pages": [1]}
            },
        }])
        self.assertNotIn("synthetic-hotel-receipt.pdf", prompt)
        self.assertNotIn("Fattura demo", prompt)


class BlockedReviewNoticeTests(unittest.TestCase):
    def test_blocked_review_notice_is_fixed_and_contains_no_private_values(self):
        record = _confirm(
            _record(), "total_amount", "PRIVATE-SYNTHETIC-AMOUNT",
            "2026-10-15T10:00:00+02:00",
        )
        record = append_review_event(
            record, actor_id="synthetic-reviewer", action="flagged",
            timestamp="2026-10-15T10:01:00+02:00", reason_code="PRIVATE-HOLD-REASON",
        )
        documents = {"note-001": record}
        bundle = build_expense_report_bundle("report-001", "note-001", [], documents)
        before = copy.deepcopy(record)

        notice = blocked_review_notice(bundle, documents)

        self.assertIn('role="alert"', notice)
        self.assertIn("Revisione bloccata", notice)
        self.assertIn("incompleta", notice)
        self.assertIn("non approvata", notice)
        self.assertIn("manualmente", notice)
        self.assertNotIn("PRIVATE-SYNTHETIC-AMOUNT", notice)
        self.assertNotIn("PRIVATE-HOLD-REASON", notice)
        self.assertNotIn("note-001", notice)
        self.assertEqual(record, before)

    def test_non_blocked_review_has_no_warning(self):
        record = _confirm(
            _record(), "total_amount", "25.00", "2026-10-15T10:00:00+02:00"
        )
        documents = {"note-001": record}
        bundle = build_expense_report_bundle("report-001", "note-001", [], documents)

        self.assertEqual(blocked_review_notice(bundle, documents), "")

    def test_malformed_review_record_fails_closed_without_echoing_identifiers(self):
        record = _confirm(
            _record(), "total_amount", "PRIVATE-VALUE",
            "2026-10-15T10:00:00+02:00",
        )
        documents = {"note-001": record}
        bundle = build_expense_report_bundle("report-001", "note-001", [], documents)
        malformed = copy.deepcopy(record)
        malformed["review"]["events"][0]["event_hash"] = "PRIVATE-INVALID-HASH"

        notice = blocked_review_notice(bundle, {"note-001": malformed})

        self.assertEqual(notice, "")
