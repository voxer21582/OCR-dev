from __future__ import annotations

from dataclasses import FrozenInstanceError
import copy
import unittest

from alfa_document_intelligence.extraction_contracts import (
    CandidateAlternative,
    CandidateState,
    ExtractionContractError,
    FieldCandidate,
    OCRObservationReference,
    SourceRegionReference,
    validate_field_candidate,
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


SOURCE_SHA256 = "a" * 64


def region() -> TextRegion:
    return TextRegion(((0.1, 0.1), (0.8, 0.1), (0.8, 0.3), (0.1, 0.3)))


def engine() -> EngineIdentity:
    return EngineIdentity("synthetic-engine", "0", None, None, "synthetic-runtime", "0")


def page_result(texts: tuple[str, ...] = ("synthetic value",), page_number: int = 1) -> PageOCRResult:
    provenance = PageProvenance(SOURCE_SHA256, page_number)
    observations = tuple(TextObservation(text, region()) for text in texts)
    return PageOCRResult(provenance, engine(), observations)


def taxonomy_binding(catalog: dict | None = None) -> dict:
    selected = default_catalog() if catalog is None else catalog
    _canonical, digest = validate_catalog(selected)
    return create_taxonomy_binding(selected, digest)


def alternative(
    result: PageOCRResult, index: int = 0, *, normalized_value: str | None = "normalized value"
) -> CandidateAlternative:
    observation = result.observations[index]
    return CandidateAlternative(
        (observation.text,), normalized_value,
        (OCRObservationReference(result.provenance, index, observation.region),),
    )


def candidate(
    binding: dict,
    state: CandidateState,
    alternatives: tuple[CandidateAlternative, ...],
    *,
    type_id: str = "invoice",
    field_id: str = "issue_date",
    unreadable_region: SourceRegionReference | None = None,
) -> FieldCandidate:
    return FieldCandidate(
        binding["catalog_schema_version"], binding["catalog_version"], binding["catalog_sha256"],
        type_id, field_id, state, alternatives, unreadable_region,
    )


class ExtractionContractTests(unittest.TestCase):
    def test_proposed_candidate_keeps_literal_text_and_exact_taxonomy_identity(self):
        binding = taxonomy_binding()
        page = page_result(("02/01/2026",))
        value = alternative(page, normalized_value="2026-01-02")
        proposed = candidate(binding, CandidateState.PROPOSED, (value,))

        validated = validate_field_candidate(proposed, binding, (page,))

        self.assertIs(validated, proposed)
        self.assertEqual(value.literal_segments, ("02/01/2026",))
        self.assertEqual(value.normalized_value, "2026-01-02")
        self.assertEqual(proposed.taxonomy_sha256, binding["catalog_sha256"])

    def test_uncertain_candidate_preserves_distinct_alternatives(self):
        binding = taxonomy_binding()
        first_page = page_result(("12,50",))
        second_page = PageOCRResult(
            PageProvenance("b" * 64, 1), engine(), (TextObservation("72,50", region()),)
        )
        uncertain = candidate(
            binding,
            CandidateState.UNCERTAIN,
            (alternative(first_page, normalized_value="12.50"),
             alternative(second_page, normalized_value="72.50")),
            field_id="total_amount",
        )

        validate_field_candidate(uncertain, binding, (first_page, second_page))

        self.assertEqual(tuple(item.literal_segments for item in uncertain.alternatives), (("12,50",), ("72,50",)))

    def test_missing_candidate_has_no_value_or_evidence(self):
        binding = taxonomy_binding()
        missing = candidate(binding, CandidateState.MISSING, ())

        validate_field_candidate(missing, binding, ())

        self.assertEqual(missing.alternatives, ())

    def test_unreadable_candidate_retains_only_a_source_region(self):
        binding = taxonomy_binding()
        page = page_result(())
        unreadable = candidate(
            binding, CandidateState.UNREADABLE, (),
            unreadable_region=SourceRegionReference(page.provenance, region()),
        )

        validate_field_candidate(unreadable, binding, (page,))

        self.assertEqual(unreadable.unreadable_region.region, region())

    def test_rejected_candidate_keeps_its_observation_without_human_approval_metadata(self):
        binding = taxonomy_binding()
        page = page_result(("synthetic candidate",))
        rejected = candidate(binding, CandidateState.REJECTED, (alternative(page),))

        validate_field_candidate(rejected, binding, (page,))

        self.assertEqual(rejected.alternatives[0].literal_segments, ("synthetic candidate",))

    def test_candidate_rejects_unknown_and_manual_only_fields(self):
        catalog = default_catalog()
        invoice = next(item for item in catalog["types"] if item["id"] == "invoice")
        invoice["fields"].append({
            "id": "custom_manual_code", "label": "Manual field", "value_kind": "text",
            "required": False, "review_only": True, "extraction_mode": "manual_only",
        })
        binding = taxonomy_binding(catalog)
        page = page_result()
        proposed = alternative(page)

        for field_id in ("unknown_field", "custom_manual_code"):
            with self.subTest(field_id=field_id), self.assertRaises(ExtractionContractError) as raised:
                validate_field_candidate(
                    candidate(binding, CandidateState.PROPOSED, (proposed,), field_id=field_id),
                    binding, (page,),
                )
            self.assertEqual(raised.exception.code, "extraction_field_not_eligible")

    def test_candidate_rejects_unknown_type(self):
        binding = taxonomy_binding()
        page = page_result()

        with self.assertRaises(ExtractionContractError) as raised:
            validate_field_candidate(
                candidate(binding, CandidateState.PROPOSED, (alternative(page),), type_id="unknown_type"),
                binding, (page,),
            )

        self.assertEqual(raised.exception.code, "extraction_field_not_eligible")

    def test_observation_reference_must_match_source_page_index_and_region(self):
        binding = taxonomy_binding()
        page = page_result(("synthetic value", "second value"))
        invalid_references = (
            OCRObservationReference(PageProvenance("b" * 64, 1), 0, region()),
            OCRObservationReference(PageProvenance(SOURCE_SHA256, 2), 0, region()),
            OCRObservationReference(page.provenance, 2, region()),
            OCRObservationReference(page.provenance, 0, TextRegion(((0.2, 0.2), (0.7, 0.2), (0.7, 0.4)))),
        )
        for reference in invalid_references:
            with self.subTest(reference=reference), self.assertRaises(ExtractionContractError):
                bad_alternative = CandidateAlternative(("synthetic value",), None, (reference,))
                validate_field_candidate(
                    candidate(binding, CandidateState.PROPOSED, (bad_alternative,)), binding, (page,)
                )

    def test_literal_segments_must_match_the_indexed_ocr_observations(self):
        binding = taxonomy_binding()
        page = page_result(("synthetic value",))
        bad_alternative = CandidateAlternative(
            ("different literal",), None,
            (OCRObservationReference(page.provenance, 0, page.observations[0].region),),
        )

        with self.assertRaises(ExtractionContractError) as raised:
            validate_field_candidate(
                candidate(binding, CandidateState.PROPOSED, (bad_alternative,)), binding, (page,)
            )

        self.assertEqual(raised.exception.code, "extraction_evidence_mismatch")

    def test_candidate_must_match_the_exact_taxonomy_binding(self):
        binding = taxonomy_binding()
        other = copy.deepcopy(binding)
        other["catalog_sha256"] = "0" * 64
        page = page_result()

        with self.assertRaises(ExtractionContractError) as raised:
            validate_field_candidate(candidate(binding, CandidateState.PROPOSED, (alternative(page),)), other, (page,))

        self.assertEqual(raised.exception.code, "extraction_taxonomy_binding_invalid")

    def test_candidate_taxonomy_identity_mismatch_is_rejected(self):
        binding = taxonomy_binding()
        page = page_result()
        bad_candidate = FieldCandidate(
            binding["catalog_schema_version"], binding["catalog_version"], "0" * 64,
            "invoice", "issue_date", CandidateState.PROPOSED, (alternative(page),),
        )

        with self.assertRaises(ExtractionContractError) as raised:
            validate_field_candidate(bad_candidate, binding, (page,))

        self.assertEqual(raised.exception.code, "extraction_taxonomy_mismatch")

    def test_candidate_rejects_malformed_taxonomy_and_field_identities(self):
        binding = taxonomy_binding()
        page = page_result()
        invalid_values = (
            ("", binding["catalog_version"], binding["catalog_sha256"], "invoice", "issue_date"),
            (binding["catalog_schema_version"], True, binding["catalog_sha256"], "invoice", "issue_date"),
            (binding["catalog_schema_version"], binding["catalog_version"], "not-a-sha256", "invoice", "issue_date"),
            (binding["catalog_schema_version"], binding["catalog_version"], binding["catalog_sha256"], "Invoice", "issue_date"),
            (binding["catalog_schema_version"], binding["catalog_version"], binding["catalog_sha256"], "invoice", "issue-date"),
        )

        for schema_version, version, digest, type_id, field_id in invalid_values:
            with self.subTest(type_id=type_id, field_id=field_id), self.assertRaises(ExtractionContractError):
                FieldCandidate(
                    schema_version, version, digest, type_id, field_id, CandidateState.PROPOSED,
                    (alternative(page),),
                )

    def test_candidate_states_reject_contradictory_value_shapes(self):
        binding = taxonomy_binding()
        page = page_result()
        value = alternative(page)
        unreadable = SourceRegionReference(page.provenance, region())

        invalid_shapes = (
            (CandidateState.PROPOSED, ()),
            (CandidateState.PROPOSED, (value, value)),
            (CandidateState.MISSING, (value,)),
            (CandidateState.UNREADABLE, (value,)),
            (CandidateState.REJECTED, ()),
        )
        for state, alternatives in invalid_shapes:
            with self.subTest(state=state), self.assertRaises(ExtractionContractError):
                candidate(binding, state, alternatives)
        with self.assertRaises(ExtractionContractError):
            candidate(binding, CandidateState.MISSING, (), unreadable_region=unreadable)

    def test_page_provenance_must_resolve_uniquely(self):
        binding = taxonomy_binding()
        page = page_result()
        duplicate = PageOCRResult(page.provenance, page.engine, page.observations)

        with self.assertRaises(ExtractionContractError) as raised:
            validate_field_candidate(
                candidate(binding, CandidateState.PROPOSED, (alternative(page),)), binding, (page, duplicate)
            )

        self.assertEqual(raised.exception.code, "extraction_page_ambiguous")

    def test_candidate_records_and_nested_values_are_immutable(self):
        binding = taxonomy_binding()
        page = page_result()
        value = alternative(page)
        proposed = candidate(binding, CandidateState.PROPOSED, (value,))

        with self.assertRaises(FrozenInstanceError):
            proposed.state = CandidateState.UNCERTAIN
        with self.assertRaises(FrozenInstanceError):
            value.normalized_value = "changed"


if __name__ == "__main__":
    unittest.main()
