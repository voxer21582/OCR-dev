from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from dataclasses import FrozenInstanceError
import unittest

from alfa_document_intelligence.extraction_contracts import (
    CandidateAlternative,
    CandidateState,
    FieldCandidate,
    OCRObservationReference,
)
from alfa_document_intelligence.ocr_contracts import (
    EngineIdentity,
    PageOCRResult,
    PageProvenance,
    TextObservation,
    TextRegion,
)
from alfa_document_intelligence.taxonomy_binding import create_taxonomy_binding
from alfa_document_intelligence.taxonomy_registry import default_catalog, validate_catalog
from alfa_document_intelligence.review_contracts import (
    ReviewAction,
    ReviewContractError,
    ReviewStatus,
    append_review_event,
    derived_result_is_current,
    review_status,
    start_review_ledger,
)


SOURCE_SHA256 = "a" * 64
REVIEWED_AT = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)


def region() -> TextRegion:
    return TextRegion(((0.1, 0.1), (0.8, 0.1), (0.8, 0.3), (0.1, 0.3)))


def page_result(text: str = "synthetic source value", source_sha256: str = SOURCE_SHA256) -> PageOCRResult:
    provenance = PageProvenance(source_sha256, 1)
    return PageOCRResult(
        provenance,
        EngineIdentity("synthetic-engine", "0", None, None, "synthetic-runtime", "0"),
        (TextObservation(text, region()),),
    )


def taxonomy_binding(*, required: bool = True) -> dict:
    catalog = default_catalog()
    invoice = next(item for item in catalog["types"] if item["id"] == "invoice")
    issue_date = next(item for item in invoice["fields"] if item["id"] == "issue_date")
    issue_date["required"] = required
    _canonical, digest = validate_catalog(catalog)
    return create_taxonomy_binding(catalog, digest)


def candidate(
    binding: dict, page: PageOCRResult, state: CandidateState = CandidateState.PROPOSED,
) -> FieldCandidate:
    observation = page.observations[0]
    alternative = CandidateAlternative(
        (observation.text,), None,
        (OCRObservationReference(page.provenance, 0, observation.region),),
    )
    return FieldCandidate(
        binding["catalog_schema_version"], binding["catalog_version"], binding["catalog_sha256"],
        "invoice", "issue_date", state,
        () if state is CandidateState.MISSING else (alternative,),
    )


def add_review(ledger, item, binding, page, **changes):
    options = {
        "expected_revision": len(ledger.events),
        "action": ReviewAction.CORRECT,
        "reviewer_id": "reviewer_local_1",
        "reason_code": "value_verified",
        "occurred_at_utc": REVIEWED_AT,
        "corrected_value": "synthetic corrected value",
    }
    options.update(changes)
    return append_review_event(ledger, item, binding, (page,), **options)


class ReviewContractTests(unittest.TestCase):
    def test_empty_ledger_is_unreviewed_and_bound_to_candidate_and_taxonomy(self):
        binding = taxonomy_binding()
        page = page_result()
        item = candidate(binding, page)

        ledger = start_review_ledger("invoice_issue_date_001", item, binding, (page,))

        self.assertEqual(ledger.events, ())
        self.assertEqual(ledger.taxonomy_sha256, binding["catalog_sha256"])
        self.assertEqual(review_status(ledger, item, binding, (page,)), ReviewStatus.UNREVIEWED)

    def test_corrections_append_and_preserve_all_prior_values(self):
        binding = taxonomy_binding()
        page = page_result()
        item = candidate(binding, page)
        original = start_review_ledger("invoice_issue_date_001", item, binding, (page,))

        first = add_review(original, item, binding, page, corrected_value="synthetic correction one")
        second = add_review(first, item, binding, page, corrected_value="synthetic correction two")

        self.assertEqual(original.events, ())
        self.assertEqual(second.source_candidate, item)
        self.assertEqual(tuple(event.revision for event in second.events), (1, 2))
        self.assertEqual(tuple(event.corrected_value for event in second.events),
                         ("synthetic correction one", "synthetic correction two"))
        self.assertEqual(review_status(second, item, binding, (page,)), ReviewStatus.CURRENT)

    def test_confirm_requires_and_preserves_selected_alternative(self):
        binding = taxonomy_binding()
        page = page_result()
        item = candidate(binding, page)
        ledger = start_review_ledger("invoice_issue_date_001", item, binding, (page,))

        reviewed = append_review_event(
            ledger, item, binding, (page,), expected_revision=0, action=ReviewAction.CONFIRM,
            reviewer_id="reviewer_local_1", reason_code="source_verified", occurred_at_utc=REVIEWED_AT,
            selected_alternative_index=0,
        )

        self.assertEqual(reviewed.events[0].selected_alternative_index, 0)
        self.assertIsNone(reviewed.events[0].corrected_value)

    def test_confirm_rejects_an_out_of_range_alternative(self):
        binding = taxonomy_binding()
        page = page_result()
        item = candidate(binding, page)
        ledger = start_review_ledger("invoice_issue_date_001", item, binding, (page,))

        with self.assertRaises(ReviewContractError) as raised:
            append_review_event(
                ledger, item, binding, (page,), expected_revision=0, action=ReviewAction.CONFIRM,
                reviewer_id="reviewer_local_1", reason_code="source_verified", occurred_at_utc=REVIEWED_AT,
                selected_alternative_index=1,
            )

        self.assertEqual(raised.exception.code, "review_selection_invalid")

    def test_confirm_can_record_absence_without_inventing_a_value(self):
        binding = taxonomy_binding()
        page = page_result()
        item = candidate(binding, page, CandidateState.MISSING)
        ledger = start_review_ledger("invoice_issue_date_001", item, binding, ())

        reviewed = append_review_event(
            ledger, item, binding, (), expected_revision=0, action=ReviewAction.CONFIRM,
            reviewer_id="reviewer_local_1", reason_code="absence_checked", occurred_at_utc=REVIEWED_AT,
        )

        self.assertEqual(reviewed.events[0].action, ReviewAction.CONFIRM)
        self.assertIsNone(reviewed.events[0].selected_alternative_index)
        self.assertIsNone(reviewed.events[0].corrected_value)

    def test_correct_requires_a_nonempty_value(self):
        binding = taxonomy_binding()
        page = page_result()
        item = candidate(binding, page)
        ledger = start_review_ledger("invoice_issue_date_001", item, binding, (page,))

        for value in (None, "", "  "):
            with self.subTest(value=value), self.assertRaises(ReviewContractError) as raised:
                add_review(ledger, item, binding, page, corrected_value=value)
            self.assertEqual(raised.exception.code, "review_event_invalid")

    def test_reject_and_defer_cannot_silently_store_a_value(self):
        binding = taxonomy_binding()
        page = page_result()
        item = candidate(binding, page)
        ledger = start_review_ledger("invoice_issue_date_001", item, binding, (page,))

        for action in (ReviewAction.REJECT, ReviewAction.DEFER):
            with self.subTest(action=action), self.assertRaises(ReviewContractError) as raised:
                append_review_event(
                    ledger, item, binding, (page,), expected_revision=0, action=action,
                    reviewer_id="reviewer_local_1", reason_code="source_unclear",
                    occurred_at_utc=REVIEWED_AT, corrected_value="unexpected value",
                )
            self.assertEqual(raised.exception.code, "review_event_invalid")

    def test_stale_expected_revision_is_rejected_without_mutating_ledger(self):
        binding = taxonomy_binding()
        page = page_result()
        item = candidate(binding, page)
        ledger = start_review_ledger("invoice_issue_date_001", item, binding, (page,))

        with self.assertRaises(ReviewContractError) as raised:
            add_review(ledger, item, binding, page, expected_revision=1)

        self.assertEqual(raised.exception.code, "review_revision_conflict")
        self.assertEqual(ledger.events, ())

    def test_changed_candidate_makes_ledger_stale(self):
        binding = taxonomy_binding()
        original_page = page_result()
        changed_page = page_result("synthetic source value", "b" * 64)
        ledger = start_review_ledger(
            "invoice_issue_date_001", candidate(binding, original_page), binding, (original_page,),
        )
        changed = candidate(binding, changed_page)

        self.assertEqual(review_status(ledger, changed, binding, (changed_page,)), ReviewStatus.STALE)

    def test_changed_source_evidence_makes_ledger_stale(self):
        binding = taxonomy_binding()
        original_page = page_result()
        changed_page = page_result("synthetic source value", "b" * 64)
        item = candidate(binding, original_page)
        ledger = start_review_ledger("invoice_issue_date_001", item, binding, (original_page,))

        self.assertEqual(review_status(ledger, item, binding, (changed_page,)), ReviewStatus.STALE)

    def test_changed_taxonomy_makes_ledger_stale(self):
        binding = taxonomy_binding()
        updated_binding = taxonomy_binding(required=False)
        page = page_result()
        ledger = start_review_ledger("invoice_issue_date_001", candidate(binding, page), binding, (page,))
        updated_candidate = candidate(updated_binding, page)

        self.assertEqual(review_status(ledger, updated_candidate, updated_binding, (page,)), ReviewStatus.STALE)

    def test_appending_to_a_changed_candidate_is_rejected(self):
        binding = taxonomy_binding()
        original_page = page_result()
        changed_page = page_result("different synthetic source value")
        item = candidate(binding, original_page)
        ledger = start_review_ledger("invoice_issue_date_001", item, binding, (original_page,))

        with self.assertRaises(ReviewContractError) as raised:
            add_review(ledger, candidate(binding, changed_page), binding, changed_page)

        self.assertEqual(raised.exception.code, "review_candidate_stale")

    def test_old_derived_result_becomes_stale_after_review_revision(self):
        binding = taxonomy_binding()
        page = page_result()
        item = candidate(binding, page)
        ledger = start_review_ledger("invoice_issue_date_001", item, binding, (page,))
        original_snapshot = {
            "candidate_sha256": ledger.candidate_sha256,
            "taxonomy_sha256": ledger.taxonomy_sha256,
            "review_revision": 0,
        }
        reviewed = add_review(ledger, item, binding, page)

        self.assertTrue(derived_result_is_current(
            ledger, item, binding, (page,), **original_snapshot,
        ))
        self.assertFalse(derived_result_is_current(
            reviewed, item, binding, (page,), **original_snapshot,
        ))
        self.assertTrue(derived_result_is_current(
            reviewed, item, binding, (page,), candidate_sha256=reviewed.candidate_sha256,
            taxonomy_sha256=reviewed.taxonomy_sha256, review_revision=1,
        ))

    def test_invalid_candidate_error_does_not_leak_ocr_text(self):
        binding = taxonomy_binding()
        page = page_result("sensitive-looking synthetic text")
        invalid = FieldCandidate(
            binding["catalog_schema_version"], binding["catalog_version"], binding["catalog_sha256"],
            "invoice", "issue_date", CandidateState.PROPOSED,
            (CandidateAlternative(
                ("different synthetic literal",), None,
                (OCRObservationReference(page.provenance, 0, page.observations[0].region),),
            ),),
        )

        with self.assertRaises(ReviewContractError) as raised:
            start_review_ledger("invoice_issue_date_001", invalid, binding, (page,))

        self.assertEqual(raised.exception.code, "review_candidate_invalid")
        self.assertNotIn("sensitive-looking synthetic text", str(raised.exception))

    def test_unencodable_candidate_text_is_sanitized(self):
        binding = taxonomy_binding()
        page = page_result("\ud800")
        item = candidate(binding, page)

        with self.assertRaises(ReviewContractError) as raised:
            start_review_ledger("invoice_issue_date_001", item, binding, (page,))

        self.assertEqual(raised.exception.code, "review_candidate_invalid")

    def test_timestamp_must_be_utc(self):
        binding = taxonomy_binding()
        page = page_result()
        item = candidate(binding, page)
        ledger = start_review_ledger("invoice_issue_date_001", item, binding, (page,))

        for timestamp in (datetime(2026, 11, 6, 12, 0),
                          datetime(2026, 11, 6, 13, 0, tzinfo=timezone(timedelta(hours=1)))):
            with self.subTest(timestamp=timestamp), self.assertRaises(ReviewContractError) as raised:
                add_review(ledger, item, binding, page, occurred_at_utc=timestamp)
            self.assertEqual(raised.exception.code, "review_event_invalid")

    def test_reviewer_and_reason_must_be_opaque_stable_codes(self):
        binding = taxonomy_binding()
        page = page_result()
        item = candidate(binding, page)
        ledger = start_review_ledger("invoice_issue_date_001", item, binding, (page,))

        for name, value in (("reviewer_id", "Windows User"), ("reviewer_id", ""),
                            ("reason_code", "source needs clarification"), ("reason_code", "")):
            with self.subTest(name=name, value=value), self.assertRaises(ReviewContractError) as raised:
                add_review(ledger, item, binding, page, **{name: value})
            self.assertEqual(raised.exception.code, "review_event_invalid")

    def test_ledger_and_events_are_immutable(self):
        binding = taxonomy_binding()
        page = page_result()
        item = candidate(binding, page)
        ledger = start_review_ledger("invoice_issue_date_001", item, binding, (page,))
        reviewed = add_review(ledger, item, binding, page)

        with self.assertRaises(FrozenInstanceError):
            reviewed.events[0].revision = 2
        with self.assertRaises(FrozenInstanceError):
            reviewed.events = ()

    def test_starting_and_appending_do_not_mutate_inputs(self):
        binding = taxonomy_binding()
        page = page_result()
        item = candidate(binding, page)
        before = copy.deepcopy((binding, item, page))
        ledger = start_review_ledger("invoice_issue_date_001", item, binding, (page,))
        reviewed = add_review(ledger, item, binding, page)

        self.assertEqual((binding, item, page), before)
        self.assertEqual(ledger.events, ())
        self.assertEqual(len(reviewed.events), 1)


if __name__ == "__main__":
    unittest.main()
