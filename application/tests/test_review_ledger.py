import copy
import json
import unittest
from pathlib import Path

from alfa_document_intelligence.document_family_catalog import load_custom_family_catalog
from alfa_document_intelligence.contracts import validate_document_record
from alfa_document_intelligence.review_ledger import (
    ReviewRejected,
    append_review_event,
    verify_review_ledger,
    reviewed_overlay,
)


FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_invoice.json"
T0 = "2026-10-14T10:00:00Z"


class ReviewLedgerTests(unittest.TestCase):
    def setUp(self):
        self.record = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def _event(self, record, action, actor, event_id, **kwargs):
        return append_review_event(
            record,
            actor_id=actor,
            action=action,
            timestamp=T0,
            event_id=event_id,
            **kwargs,
        )

    def test_review_workflow_is_append_only_and_separate_from_admin(self):
        original = copy.deepcopy(self.record)
        result = self._event(self.record, "queued", "reviewer-ref-1", "event-1")
        result = self._event(result, "opened", "reviewer-ref-1", "event-2")
        candidate = copy.deepcopy(result["fields"]["merchant_name"])
        candidate["value"] = "Hotel Demo S.r.l."
        candidate["evidence"][0]["literal"] = "Hotel Demo S.r.l."
        result = self._event(
            result, "field_corrected", "reviewer-ref-1", "event-3",
            field_name="merchant_name", reason_code="visual_correction", candidate=candidate,
        )
        result = self._event(result, "completed", "reviewer-ref-1", "event-4")

        self.assertEqual(self.record, original)
        self.assertEqual(result["fields"], original["fields"])
        self.assertEqual(result["administrative_verification"], original["administrative_verification"])
        self.assertEqual(result["review"]["status"], "completed")
        self.assertEqual(result["review"]["events"][2]["candidate"]["value"], "Hotel Demo S.r.l.")
        self.assertEqual(verify_review_ledger(result), result["review"]["events"][-1]["event_hash"])

    def test_document_family_review_is_evidence_bound_and_separate_from_fiscal_state(self):
        original = copy.deepcopy(self.record)
        self.record["document_family"] = "unknown"
        evidence = copy.deepcopy(self.record["fiscal_document_state"]["evidence"])
        self.record["fields"]["document_family_candidates"] = {
            "value": None, "status": "uncertain",
            "alternatives": [{"value": "invoice", "status": "observed", "evidence": evidence}],
            "evidence": evidence,
        }
        result = self._event(self.record, "queued", "reviewer-ref-1", "family-1")
        result = self._event(result, "opened", "reviewer-ref-1", "family-2")
        candidate = {"value": "invoice", "status": "observed", "alternatives": [], "evidence": evidence}
        result = self._event(
            result, "field_corrected", "reviewer-ref-1", "family-3",
            field_name="document_family", reason_code="family_review", candidate=candidate,
        )

        overlay = reviewed_overlay(result)

        self.assertEqual(result["document_family"], "unknown")
        self.assertEqual(overlay["extracted_document_family"], "unknown")
        self.assertEqual(overlay["reviewed_document_family"], "invoice")
        self.assertEqual(overlay["extracted_fiscal_document_state"], original["fiscal_document_state"])
        self.assertEqual(overlay["reviewed_fiscal_document_state"], original["fiscal_document_state"])

    def test_document_family_review_must_select_an_evidence_bound_candidate(self):
        self.record["document_family"] = "unknown"
        evidence = copy.deepcopy(self.record["fiscal_document_state"]["evidence"])
        self.record["fields"]["document_family_candidates"] = {
            "value": None, "status": "uncertain",
            "alternatives": [{"value": "invoice", "status": "observed", "evidence": evidence}],
            "evidence": evidence,
        }
        result = self._event(self.record, "queued", "reviewer-ref-1", "family-1")
        result = self._event(result, "opened", "reviewer-ref-1", "family-2")
        mismatched = copy.deepcopy(self.record["fields"]["merchant_name"]["evidence"])
        candidate = {"value": "invoice", "status": "observed", "alternatives": [], "evidence": mismatched}
        with self.assertRaisesRegex(ReviewRejected, "evidence-bound alternative"):
            self._event(
                result, "field_corrected", "reviewer-ref-1", "family-3",
                field_name="document_family", reason_code="family_review", candidate=candidate,
            )

    def test_custom_document_family_review_requires_a_valid_embedded_snapshot(self):
        catalog = load_custom_family_catalog(json.dumps({
            "catalog_version": "1",
            "families": [{
                "id": "custom_taxi_receipt",
                "label": "Ricevuta taxi",
                "title_cues": ["RICEVUTA TAXI"],
                "fields": [{"id": "pickup_city", "label": "Città", "aliases": ["Partenza"]}],
            }],
        }))
        record = copy.deepcopy(self.record)
        record["schema_version"] = "0.2.0"
        record["document_family"] = "unknown"
        record["document_family_definitions"] = [catalog.snapshot_for("custom_taxi_receipt")]
        evidence = copy.deepcopy(record["fiscal_document_state"]["evidence"])
        record["fields"]["document_family_candidates"] = {
            "value": None,
            "status": "uncertain",
            "alternatives": [{"value": "custom_taxi_receipt", "status": "observed", "evidence": evidence}],
            "evidence": evidence,
        }
        queued = self._event(record, "queued", "reviewer-ref-1", "custom-family-1")
        opened = self._event(queued, "opened", "reviewer-ref-1", "custom-family-2")
        candidate = {"value": "custom_taxi_receipt", "status": "observed", "alternatives": [], "evidence": evidence}

        reviewed = self._event(
            opened, "field_corrected", "reviewer-ref-1", "custom-family-3",
            field_name="document_family", reason_code="family_review", candidate=candidate,
        )

        self.assertEqual(record["document_family"], "unknown")
        self.assertEqual(validate_document_record(reviewed), [])
        self.assertEqual(reviewed_overlay(reviewed)["reviewed_document_family"], "custom_taxi_receipt")
        self.assertEqual(reviewed["document_family_definitions"], record["document_family_definitions"])
        self.assertEqual(
            reviewed["review"]["events"][-1]["document_family_snapshot"],
            record["document_family_definitions"][0],
        )

    def test_custom_document_family_review_binds_snapshot_into_event_hash(self):
        catalog = load_custom_family_catalog(json.dumps({
            "catalog_version": "1",
            "families": [{
                "id": "custom_taxi_receipt",
                "label": "Ricevuta taxi",
                "title_cues": ["RICEVUTA TAXI"],
                "fields": [{"id": "pickup_city", "label": "Città", "aliases": ["Partenza"]}],
            }],
        }))
        record = copy.deepcopy(self.record)
        record["schema_version"] = "0.2.0"
        record["document_family"] = "unknown"
        record["document_family_definitions"] = [catalog.snapshot_for("custom_taxi_receipt")]
        evidence = copy.deepcopy(record["fiscal_document_state"]["evidence"])
        record["fields"]["document_family_candidates"] = {
            "value": None,
            "status": "uncertain",
            "alternatives": [{"value": "custom_taxi_receipt", "status": "observed", "evidence": evidence}],
            "evidence": evidence,
        }
        queued = self._event(record, "queued", "reviewer-ref-1", "custom-snapshot-1")
        opened = self._event(queued, "opened", "reviewer-ref-1", "custom-snapshot-2")
        candidate = {"value": "custom_taxi_receipt", "status": "observed", "alternatives": [], "evidence": evidence}
        reviewed = self._event(
            opened, "field_corrected", "reviewer-ref-1", "custom-snapshot-3",
            field_name="document_family", reason_code="family_review", candidate=candidate,
        )

        changed_catalog = load_custom_family_catalog(json.dumps({
            "catalog_version": "1",
            "families": [{
                "id": "custom_taxi_receipt",
                "label": "Ricevuta taxi aggiornata",
                "title_cues": ["RICEVUTA TAXI"],
                "fields": [{"id": "pickup_city", "label": "Città", "aliases": ["Partenza"]}],
            }],
        }))
        reviewed["document_family_definitions"] = [changed_catalog.snapshot_for("custom_taxi_receipt")]
        with self.assertRaisesRegex(ReviewRejected, "does not bind its embedded snapshot"):
            verify_review_ledger(reviewed)

    def test_family_snapshot_cannot_be_added_to_workflow_or_flag_events(self):
        queued = self._event(self.record, "queued", "reviewer-ref-1", "unexpected-snapshot-1")
        queued["review"]["events"][0]["document_family_snapshot"] = {"synthetic": True}
        with self.assertRaisesRegex(ReviewRejected, "allowed only for family selection"):
            verify_review_ledger(queued)

        clean_queued = self._event(self.record, "queued", "reviewer-ref-1", "unexpected-snapshot-2")
        opened = self._event(clean_queued, "opened", "reviewer-ref-1", "unexpected-snapshot-3")
        flagged = self._event(
            opened, "flagged", "reviewer-ref-1", "unexpected-snapshot-4", reason_code="synthetic_flag"
        )
        flagged["review"]["events"][-1]["document_family_snapshot"] = {"synthetic": True}
        with self.assertRaisesRegex(ReviewRejected, "allowed only for family selection"):
            verify_review_ledger(flagged)

    def test_custom_document_family_review_rejects_missing_or_invalid_snapshot(self):
        record = copy.deepcopy(self.record)
        record["schema_version"] = "0.2.0"
        record["document_family"] = "unknown"
        evidence = copy.deepcopy(record["fiscal_document_state"]["evidence"])
        record["fields"]["document_family_candidates"] = {
            "value": None,
            "status": "uncertain",
            "alternatives": [{"value": "custom_taxi_receipt", "status": "observed", "evidence": evidence}],
            "evidence": evidence,
        }
        queued = self._event(record, "queued", "reviewer-ref-1", "custom-invalid-1")
        opened = self._event(queued, "opened", "reviewer-ref-1", "custom-invalid-2")
        candidate = {"value": "custom_taxi_receipt", "status": "observed", "alternatives": [], "evidence": evidence}

        with self.assertRaisesRegex(ReviewRejected, "snapshot"):
            self._event(
                opened, "field_corrected", "reviewer-ref-1", "custom-invalid-3",
                field_name="document_family", reason_code="family_review", candidate=candidate,
            )

        record["document_family_definitions"] = [{
            "catalog_version": "1", "family": {"id": "custom_taxi_receipt"}, "family_sha256": "0" * 64,
        }]
        queued = self._event(record, "queued", "reviewer-ref-1", "custom-invalid-4")
        opened = self._event(queued, "opened", "reviewer-ref-1", "custom-invalid-5")
        with self.assertRaisesRegex(ReviewRejected, "snapshot"):
            self._event(
                opened, "field_corrected", "reviewer-ref-1", "custom-invalid-6",
                field_name="document_family", reason_code="family_review", candidate=candidate,
            )
    def test_fiscal_state_correction_is_logged_without_overwriting_extraction(self):
        result = self._event(self.record, "queued", "reviewer-ref-1", "event-1")
        result = self._event(result, "opened", "reviewer-ref-1", "event-2")
        fiscal_state = {
            "status": "payment_evidence",
            "evidence": copy.deepcopy(self.record["fiscal_document_state"]["evidence"]),
        }
        result = append_review_event(
            result,
            actor_id="reviewer-ref-1",
            action="fiscal_state_corrected",
            timestamp=T0,
            reason_code="document_type_review",
            fiscal_state=fiscal_state,
            event_id="event-3",
        )
        self.assertEqual(result["fiscal_document_state"], self.record["fiscal_document_state"])
        self.assertEqual(result["review"]["events"][-1]["fiscal_state"], fiscal_state)
        self.assertEqual(verify_review_ledger(result), result["review"]["events"][-1]["event_hash"])

    def test_pos_family_and_fiscal_status_remain_separate_with_conflicts_rejected(self):
        record = copy.deepcopy(self.record)
        record["document_family"] = "unknown"
        evidence = copy.deepcopy(record["fiscal_document_state"]["evidence"])
        evidence[0]["literal"] = "CARD PAYMENT SLIP"
        record["fiscal_document_state"] = {"status": "unknown", "evidence": []}
        record["fields"]["document_family_candidates"] = {
            "value": None, "status": "uncertain",
            "alternatives": [{"value": "pos_slip", "status": "observed", "evidence": evidence}],
            "evidence": evidence,
        }
        queued = self._event(record, "queued", "reviewer-ref-1", "pos-1")
        opened = self._event(queued, "opened", "reviewer-ref-1", "pos-2")
        selected = {"value": "pos_slip", "status": "observed", "alternatives": [], "evidence": evidence}
        reviewed = self._event(
            opened, "field_corrected", "reviewer-ref-1", "pos-3",
            field_name="document_family", reason_code="family_review", candidate=selected,
        )
        payment_state = {"status": "payment_evidence", "evidence": evidence}
        reviewed = append_review_event(
            reviewed, actor_id="reviewer-ref-1", action="fiscal_state_corrected",
            timestamp=T0, reason_code="fiscal_review", fiscal_state=payment_state, event_id="pos-4",
        )
        overlay = reviewed_overlay(reviewed)
        self.assertEqual(overlay["reviewed_document_family"], "pos_slip")
        self.assertEqual(overlay["reviewed_fiscal_document_state"]["status"], "payment_evidence")
        self.assertEqual(reviewed["fiscal_document_state"]["status"], "unknown")

        with self.assertRaisesRegex(ReviewRejected, "reviewed POS slip"):
            append_review_event(
                reviewed, actor_id="reviewer-ref-1", action="fiscal_state_corrected",
                timestamp=T0, reason_code="fiscal_review",
                fiscal_state={"status": "fiscal_document", "evidence": evidence}, event_id="pos-5",
            )

    def test_fiscal_document_status_prevents_later_pos_family_selection(self):
        record = copy.deepcopy(self.record)
        record["document_family"] = "unknown"
        evidence = copy.deepcopy(record["fiscal_document_state"]["evidence"])
        evidence[0]["literal"] = "CARD PAYMENT SLIP"
        record["fields"]["document_family_candidates"] = {
            "value": None, "status": "uncertain",
            "alternatives": [{"value": "pos_slip", "status": "observed", "evidence": evidence}],
            "evidence": evidence,
        }
        queued = self._event(record, "queued", "reviewer-ref-1", "pos-1")
        opened = self._event(queued, "opened", "reviewer-ref-1", "pos-2")
        candidate = {"value": "pos_slip", "status": "observed", "alternatives": [], "evidence": evidence}
        with self.assertRaisesRegex(ReviewRejected, "fiscal-document status"):
            self._event(
                opened, "field_corrected", "reviewer-ref-1", "pos-3",
                field_name="document_family", reason_code="family_review", candidate=candidate,
            )
    def test_fiscal_state_correction_requires_bound_evidence(self):
        result = self._event(self.record, "queued", "reviewer-ref-1", "event-1")
        result = self._event(result, "opened", "reviewer-ref-1", "event-2")
        with self.assertRaisesRegex(ReviewRejected, "source-evidence contract"):
            append_review_event(
                result,
                actor_id="reviewer-ref-1",
                action="fiscal_state_corrected",
                timestamp=T0,
                reason_code="document_type_review",
                fiscal_state={"status": "payment_evidence", "evidence": []},
                event_id="event-3",
            )

    def test_reviewed_overlay_derives_corrections_without_mutating_extraction(self):
        original = copy.deepcopy(self.record)
        result = self._event(self.record, "queued", "reviewer-ref-1", "event-1")
        result = self._event(result, "opened", "reviewer-ref-1", "event-2")
        candidate = copy.deepcopy(result["fields"]["merchant_name"])
        candidate["value"] = "Hotel Demo S.r.l."
        candidate["evidence"][0]["literal"] = "Hotel Demo S.r.l."
        result = self._event(
            result,
            "field_corrected",
            "reviewer-ref-1",
            "event-3",
            field_name="merchant_name",
            reason_code="visual_correction",
            candidate=candidate,
        )
        state = {
            "status": "payment_evidence",
            "evidence": copy.deepcopy(result["fiscal_document_state"]["evidence"]),
        }
        result = append_review_event(
            result,
            actor_id="reviewer-ref-1",
            action="fiscal_state_corrected",
            timestamp=T0,
            reason_code="document_type_review",
            fiscal_state=state,
            event_id="event-4",
        )

        overlay = reviewed_overlay(result)
        self.assertEqual(overlay["reviewed_fields"]["merchant_name"]["value"], "Hotel Demo S.r.l.")
        self.assertEqual(overlay["reviewed_fiscal_document_state"], state)
        self.assertEqual(overlay["review_status"], "in_progress")
        self.assertEqual(result["fields"], original["fields"])
        self.assertEqual(result["fiscal_document_state"], original["fiscal_document_state"])

    def test_reviewed_overlay_includes_unmodified_fields_and_extraction(self):
        overlay = reviewed_overlay(self.record)
        self.assertEqual(overlay["extracted_fields"], self.record["fields"])
        self.assertEqual(overlay["reviewed_fields"], self.record["fields"])
        self.assertEqual(
            overlay["reviewed_fiscal_document_state"],
            self.record["fiscal_document_state"],
        )
        self.assertEqual(
            overlay["extracted_fiscal_document_state"],
            self.record["fiscal_document_state"],
        )

    def test_reviewed_overlay_rejects_tampered_ledger(self):
        result = self._event(self.record, "queued", "reviewer-ref-1", "event-1")
        result["review"]["events"][0]["actor_id"] = "changed-actor"
        with self.assertRaisesRegex(ReviewRejected, "hash mismatch"):
            reviewed_overlay(result)

    def test_tampered_event_is_detected(self):
        result = self._event(self.record, "queued", "reviewer-ref-1", "event-1")
        result["review"]["events"][0]["actor_id"] = "changed-actor"
        with self.assertRaisesRegex(ReviewRejected, "hash mismatch"):
            verify_review_ledger(result)

    def test_broken_hash_link_is_detected(self):
        result = self._event(self.record, "queued", "reviewer-ref-1", "event-1")
        result = self._event(result, "opened", "reviewer-ref-1", "event-2")
        result["review"]["events"][1]["previous_event_hash"] = "f" * 64
        with self.assertRaisesRegex(ReviewRejected, "hash chain is broken"):
            verify_review_ledger(result)

    def test_corrected_candidate_must_bind_to_source_evidence(self):
        result = self._event(self.record, "queued", "reviewer-ref-1", "event-1")
        result = self._event(result, "opened", "reviewer-ref-1", "event-2")
        candidate = copy.deepcopy(result["fields"]["merchant_name"])
        candidate["value"] = "Invented Merchant"
        candidate["evidence"][0]["source_sha256"] = "f" * 64
        with self.assertRaisesRegex(ReviewRejected, "source-evidence contract"):
            self._event(
                result, "field_corrected", "reviewer-ref-1", "event-3",
                field_name="merchant_name", reason_code="visual_correction", candidate=candidate,
            )
        self.assertEqual(len(result["review"]["events"]), 2)

    def test_field_change_requires_active_review_and_reason(self):
        candidate = copy.deepcopy(self.record["fields"]["merchant_name"])
        with self.assertRaisesRegex(ReviewRejected, "not allowed"):
            self._event(
                self.record, "field_corrected", "reviewer-ref-1", "event-1",
                field_name="merchant_name", reason_code="correction", candidate=candidate,
            )
        result = self._event(self.record, "queued", "reviewer-ref-1", "event-1")
        result = self._event(result, "opened", "reviewer-ref-1", "event-2")
        with self.assertRaisesRegex(ReviewRejected, "reason_code"):
            self._event(
                result, "field_corrected", "reviewer-ref-1", "event-3",
                field_name="merchant_name", candidate=candidate,
            )

    def test_completed_review_is_terminal(self):
        result = self._event(self.record, "queued", "reviewer-ref-1", "event-1")
        result = self._event(result, "opened", "reviewer-ref-1", "event-2")
        result = self._event(result, "completed", "reviewer-ref-1", "event-3")
        with self.assertRaisesRegex(ReviewRejected, "not allowed"):
            self._event(result, "opened", "reviewer-ref-2", "event-4")


if __name__ == "__main__":
    unittest.main()
