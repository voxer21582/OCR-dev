from __future__ import annotations

from dataclasses import FrozenInstanceError
import copy
import unittest

from alfa_document_intelligence.extraction_contracts import (
    CandidateAlternative,
    CandidateState,
    FieldCandidate,
    OCRObservationReference,
    SourceRegionReference,
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
from alfa_document_intelligence.validation_contracts import (
    ValidationContractError,
    validate_document_fields,
)


SOURCE_SHA256 = "a" * 64


def region() -> TextRegion:
    return TextRegion(((0.1, 0.1), (0.8, 0.1), (0.8, 0.3), (0.1, 0.3)))


def page_result(text: str = "synthetic value") -> PageOCRResult:
    provenance = PageProvenance(SOURCE_SHA256, 1)
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


def alternative(result: PageOCRResult, text: str | None = None) -> CandidateAlternative:
    observation = result.observations[0]
    return CandidateAlternative(
        (observation.text if text is None else text,), None,
        (OCRObservationReference(result.provenance, 0, observation.region),),
    )


def candidate(
    binding: dict,
    state: CandidateState,
    alternatives: tuple[CandidateAlternative, ...] = (),
    *,
    field_id: str = "issue_date",
    unreadable_region: SourceRegionReference | None = None,
) -> FieldCandidate:
    return FieldCandidate(
        binding["catalog_schema_version"], binding["catalog_version"], binding["catalog_sha256"],
        "invoice", field_id, state, alternatives, unreadable_region,
    )


class ValidationContractTests(unittest.TestCase):
    def test_required_field_without_candidate_is_reported(self):
        binding = taxonomy_binding()

        report = validate_document_fields(binding, "invoice", (), ())

        entry = next(item for item in report.field_entries if item.field_id == "issue_date")
        self.assertEqual(entry.states, ())
        self.assertIn("required_field_missing", {item.code for item in report.findings
                                                if item.field_id == "issue_date"})

    def test_optional_field_without_candidate_is_not_a_gap(self):
        binding = taxonomy_binding(required=False)

        report = validate_document_fields(binding, "invoice", (), ())

        self.assertNotIn("issue_date", {item.field_id for item in report.findings})

    def test_candidate_states_remain_distinct_and_sanitized(self):
        binding = taxonomy_binding()
        page = page_result()
        candidates = (
            candidate(binding, CandidateState.MISSING),
            candidate(binding, CandidateState.UNCERTAIN, (alternative(page),)),
            candidate(binding, CandidateState.UNREADABLE, unreadable_region=SourceRegionReference(
                page.provenance, region(),
            )),
            candidate(binding, CandidateState.REJECTED, (alternative(page),)),
        )

        report = validate_document_fields(binding, "invoice", candidates, (page,))

        findings = {item.code for item in report.findings if item.field_id == "issue_date"}
        self.assertEqual(findings, {
            "field_missing", "field_uncertain", "field_unreadable", "field_rejected",
            "field_candidate_conflict", "required_field_missing",
        })
        self.assertNotIn("synthetic value", repr(report))
        self.assertNotIn(SOURCE_SHA256, repr(report))

    def test_proposed_candidate_satisfies_structural_presence_only(self):
        binding = taxonomy_binding()
        page = page_result()
        proposed = candidate(binding, CandidateState.PROPOSED, (alternative(page),))

        report = validate_document_fields(binding, "invoice", (proposed,), (page,))

        self.assertFalse(any(item.field_id == "issue_date" for item in report.findings))
        self.assertFalse(hasattr(report, "accepted"))
        self.assertFalse(hasattr(report, "is_valid"))

    def test_required_missing_candidate_has_state_and_required_findings(self):
        binding = taxonomy_binding()
        missing = candidate(binding, CandidateState.MISSING)

        report = validate_document_fields(binding, "invoice", (missing,), ())

        codes = {item.code for item in report.findings if item.field_id == "issue_date"}
        self.assertEqual(codes, {"field_missing", "required_field_missing"})

    def test_duplicate_candidates_are_preserved_as_conflict(self):
        binding = taxonomy_binding()
        page = page_result()
        proposed = candidate(binding, CandidateState.PROPOSED, (alternative(page),))
        uncertain = candidate(binding, CandidateState.UNCERTAIN, (alternative(page),))

        report = validate_document_fields(binding, "invoice", (uncertain, proposed), (page,))

        entry = next(item for item in report.field_entries if item.field_id == "issue_date")
        self.assertEqual(entry.states, (CandidateState.PROPOSED, CandidateState.UNCERTAIN))
        self.assertIn("field_candidate_conflict", {item.code for item in report.findings})

    def test_report_carries_exact_taxonomy_identity(self):
        binding = taxonomy_binding()

        report = validate_document_fields(binding, "invoice", (), ())

        self.assertEqual(report.taxonomy_schema_version, binding["catalog_schema_version"])
        self.assertEqual(report.taxonomy_version, binding["catalog_version"])
        self.assertEqual(report.taxonomy_sha256, binding["catalog_sha256"])

    def test_disabled_type_is_rejected_without_catalog_details(self):
        catalog = default_catalog()
        invoice = next(item for item in catalog["types"] if item["id"] == "invoice")
        invoice["enabled"] = False
        _canonical, digest = validate_catalog(catalog)
        binding = create_taxonomy_binding(catalog, digest)

        with self.assertRaises(ValidationContractError) as raised:
            validate_document_fields(binding, "invoice", (), ())

        self.assertEqual(raised.exception.code, "validation_type_not_eligible")
        self.assertNotIn("Fattura", str(raised.exception))

    def test_unknown_and_manual_only_types_are_rejected(self):
        catalog = default_catalog()
        catalog["types"].append({
            "id": "custom_manual_receipt", "label": "Synthetic custom family",
            "enabled": True, "role": "custom_manual", "extraction_mode": "manual_only",
            "fields": [{
                "id": "custom_manual_reference", "label": "Synthetic field", "value_kind": "text",
                "required": True, "review_only": True, "extraction_mode": "manual_only",
            }],
        })
        _canonical, digest = validate_catalog(catalog)
        binding = create_taxonomy_binding(catalog, digest)
        for type_id in ("unknown", "custom_manual_receipt", "not_a_type"):
            with self.subTest(type_id=type_id), self.assertRaises(ValidationContractError) as raised:
                validate_document_fields(binding, type_id, (), ())
            self.assertEqual(raised.exception.code, "validation_type_not_eligible")

    def test_invalid_binding_is_reported_with_stable_code(self):
        binding = taxonomy_binding()
        invalid = copy.deepcopy(binding)
        invalid["catalog_sha256"] = "0" * 64

        with self.assertRaises(ValidationContractError) as raised:
            validate_document_fields(invalid, "invoice", (), ())

        self.assertEqual(raised.exception.code, "validation_taxonomy_binding_invalid")
        self.assertNotIn("0" * 64, str(raised.exception))

    def test_candidate_taxonomy_mismatch_is_rejected(self):
        binding = taxonomy_binding()
        wrong = candidate(binding, CandidateState.MISSING)
        wrong = FieldCandidate(
            wrong.taxonomy_schema_version, wrong.taxonomy_version, "0" * 64,
            wrong.type_id, wrong.field_id, wrong.state, wrong.alternatives,
        )

        with self.assertRaises(ValidationContractError) as raised:
            validate_document_fields(binding, "invoice", (wrong,), ())

        self.assertEqual(raised.exception.code, "validation_candidate_invalid")

    def test_report_is_immutable(self):
        report = validate_document_fields(taxonomy_binding(), "invoice", (), ())

        with self.assertRaises(FrozenInstanceError):
            report.type_id = "other"

    def test_input_order_does_not_change_output_order(self):
        binding = taxonomy_binding()
        page = page_result()
        candidates = (
            candidate(binding, CandidateState.REJECTED, (alternative(page),), field_id="currency"),
            candidate(binding, CandidateState.UNCERTAIN, (alternative(page),), field_id="issue_date"),
        )

        forward = validate_document_fields(binding, "invoice", candidates, (page,))
        reverse = validate_document_fields(binding, "invoice", tuple(reversed(candidates)), (page,))

        self.assertEqual(forward, reverse)
        self.assertEqual(tuple(item.field_id for item in forward.field_entries),
                         tuple(sorted(item.field_id for item in forward.field_entries)))

    def test_inputs_are_not_mutated(self):
        binding = taxonomy_binding()
        page = page_result()
        values = (candidate(binding, CandidateState.PROPOSED, (alternative(page),)),)
        before = copy.deepcopy((binding, values, (page,)))

        validate_document_fields(binding, "invoice", values, (page,))

        self.assertEqual((binding, values, (page,)), before)


if __name__ == "__main__":
    unittest.main()
