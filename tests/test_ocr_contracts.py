from __future__ import annotations

from dataclasses import FrozenInstanceError
import math
import unittest

from alfa_document_intelligence.ocr_contracts import (
    EngineIdentity,
    OCRContractError,
    PageInput,
    PageOCRResult,
    PageProvenance,
    PageResultStatus,
    TextObservation,
    TextRegion,
    validate_page_result,
)


SOURCE_SHA256 = "a" * 64


def engine_identity() -> EngineIdentity:
    return EngineIdentity("engine-x", "1.2.3", "model-y", "4.5", "runtime-z", "3.13.0")


def page_input() -> PageInput:
    return PageInput(PageProvenance(SOURCE_SHA256, 1), "image/png", b"synthetic image bytes")


def region() -> TextRegion:
    return TextRegion(((0.1, 0.1), (0.8, 0.1), (0.8, 0.3), (0.1, 0.3)))


class OCRContractTests(unittest.TestCase):
    def test_page_result_keeps_provenance_and_declared_engine_identity(self):
        page = page_input()
        observation = TextObservation("synthetic text", region(), 0.875)
        result = PageOCRResult(page.provenance, engine_identity(), (observation,))

        self.assertEqual(validate_page_result(page, result, expected_engine=engine_identity()), result)
        self.assertEqual(result.provenance.source_sha256, SOURCE_SHA256)
        self.assertEqual(result.provenance.page_number, 1)
        self.assertEqual(result.engine.model_id, "model-y")
        self.assertEqual(result.observations[0].text, "synthetic text")

    def test_absent_confidence_is_preserved_as_unknown(self):
        observation = TextObservation("synthetic text", region())

        self.assertIsNone(observation.confidence)

    def test_page_provenance_rejects_invalid_digest_and_page_number(self):
        invalid_values = (
            ("A" * 64, 1),
            ("a" * 63, 1),
            ("a" * 64, 0),
            ("a" * 64, True),
        )
        for digest, page_number in invalid_values:
            with self.subTest(digest=digest[:2], page_number=page_number):
                with self.assertRaises(OCRContractError):
                    PageProvenance(digest, page_number)

    def test_page_input_requires_nonempty_bytes_and_media_type(self):
        provenance = PageProvenance(SOURCE_SHA256, 1)
        for media_type, image_bytes in (("", b"image"), ("image/png", b""), ("image/png", "not bytes")):
            with self.subTest(media_type=media_type, image_bytes=type(image_bytes).__name__):
                with self.assertRaises(OCRContractError):
                    PageInput(provenance, media_type, image_bytes)

    def test_region_rejects_too_few_points(self):
        with self.assertRaises(OCRContractError):
            TextRegion(((0.1, 0.1), (0.8, 0.1)))

    def test_region_rejects_nonfinite_out_of_bounds_and_zero_area(self):
        invalid_polygons = (
            ((0.1, 0.1), (0.8, 0.1), (1.1, 0.3)),
            ((0.1, 0.1), (0.8, 0.1), (float("nan"), 0.3)),
            ((0.1, 0.1), (0.8, 0.1), (10**1000, 0.3)),
            ((0.1, 0.1), (0.5, 0.5), (0.9, 0.9)),
        )
        for polygon in invalid_polygons:
            with self.subTest(polygon=polygon):
                with self.assertRaises(OCRContractError):
                    TextRegion(polygon)

    def test_region_rejects_self_intersection_even_when_signed_area_is_nonzero(self):
        bow_tie = ((0.0, 0.0), (1.0, 1.0), (0.0, 1.0), (0.8, 0.0))

        with self.assertRaises(OCRContractError) as raised:
            TextRegion(bow_tie)

        self.assertEqual(raised.exception.code, "ocr_region_invalid")

    def test_region_rejects_more_than_256_vertices_before_geometry_validation(self):
        vertex_count = 257
        oversized_polygon = tuple(
            (0.5 + 0.4 * math.cos(2 * math.pi * index / vertex_count),
             0.5 + 0.4 * math.sin(2 * math.pi * index / vertex_count))
            for index in range(vertex_count)
        )

        with self.assertRaises(OCRContractError) as raised:
            TextRegion(oversized_polygon)

        self.assertEqual(raised.exception.code, "ocr_region_invalid")

    def test_confidence_rejects_nonfinite_and_out_of_range_values(self):
        for confidence in (-0.01, 1.01, float("inf"), float("nan"), 10**1000, True):
            with self.subTest(confidence=confidence):
                with self.assertRaises(OCRContractError):
                    TextObservation("synthetic text", region(), confidence)

    def test_failed_result_requires_no_observations_and_sanitized_code(self):
        provenance = PageProvenance(SOURCE_SHA256, 1)
        with self.assertRaises(OCRContractError):
            PageOCRResult(provenance, engine_identity(), (), PageResultStatus.FAILED)
        with self.assertRaises(OCRContractError):
            PageOCRResult(provenance, engine_identity(), (TextObservation("x", region()),), PageResultStatus.FAILED, "failed")
        with self.assertRaises(OCRContractError):
            PageOCRResult(provenance, engine_identity(), (), PageResultStatus.FAILED, "C:\\private\\document.pdf")

    def test_failed_result_exposes_only_a_stable_error_code(self):
        result = PageOCRResult(
            PageProvenance(SOURCE_SHA256, 1), engine_identity(), (), PageResultStatus.FAILED, "engine_unavailable"
        )

        self.assertEqual(result.error_code, "engine_unavailable")
        self.assertEqual(result.observations, ())

    def test_partial_result_can_keep_observations_without_claiming_completion(self):
        observation = TextObservation("synthetic text", region())
        result = PageOCRResult(
            PageProvenance(SOURCE_SHA256, 1), engine_identity(), (observation,), PageResultStatus.PARTIAL
        )

        self.assertEqual(result.status, PageResultStatus.PARTIAL)
        self.assertIsNone(result.error_code)

    def test_result_validator_rejects_wrong_source_or_page(self):
        page = page_input()
        mismatched = PageOCRResult(PageProvenance("b" * 64, 2), engine_identity(), ())

        with self.assertRaises(OCRContractError):
            validate_page_result(page, mismatched, expected_engine=engine_identity())

    def test_result_validator_rejects_an_unexpected_engine_identity(self):
        page = page_input()
        result = PageOCRResult(page.provenance, engine_identity(), ())
        other_engine = EngineIdentity("engine-other", "2.0", "model-y", "4.5", "runtime-z", "3.13.0")

        with self.assertRaises(OCRContractError):
            validate_page_result(page, result, expected_engine=other_engine)

    def test_contract_records_are_frozen_and_nested_collections_are_tuples(self):
        polygon = ((0.1, 0.1), (0.8, 0.1), (0.8, 0.3))
        text_region = TextRegion(polygon)
        result = PageOCRResult(
            PageProvenance(SOURCE_SHA256, 1), engine_identity(), (TextObservation("x", text_region),)
        )

        self.assertIsInstance(text_region.polygon, tuple)
        self.assertIsInstance(result.observations, tuple)
        with self.assertRaises(FrozenInstanceError):
            result.status = PageResultStatus.PARTIAL


if __name__ == "__main__":
    unittest.main()
