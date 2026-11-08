import unittest
from types import SimpleNamespace

from alfa_document_intelligence.ocr_adapter import OCRContractError, RasterPage, run_ocr
from alfa_document_intelligence.rapidocr_adapter import RapidOCRAdapter


class FakeEngine:
    def __init__(self, result):
        self.result = result
        self.seen = []

    def __call__(self, image):
        self.seen.append(image)
        return self.result


class RapidOCRAdapterContractTests(unittest.TestCase):
    def test_normalizes_rapidocr_boxes_and_binds_page_and_source(self):
        marker = object()
        engine = FakeEngine(SimpleNamespace(
            boxes=[[[10, 20], [50, 20], [50, 40], [10, 40]]],
            txts=["EUR 24,50"], scores=[0.91],
        ))
        adapter = RapidOCRAdapter(engine, "3.10.0", image_decoder=lambda _page: marker)

        result = run_ocr(
            adapter, [RasterPage(3, 100, 80, b"synthetic")],
            source_sha256="a" * 64,
        )[0]

        self.assertEqual(engine.seen, [marker])
        self.assertEqual(result.source_sha256, "a" * 64)
        self.assertEqual(result.page_number, 3)
        self.assertEqual(result.engine_name, "RapidOCR")
        self.assertEqual(result.engine_version, "3.10.0")
        self.assertEqual(result.language, "it+en")
        self.assertEqual(result.tokens[0].text, "EUR 24,50")
        self.assertEqual(result.tokens[0].polygon, (
            (0.1, 0.25), (0.5, 0.25), (0.5, 0.5), (0.1, 0.5),
        ))

    def test_accepts_no_detections_without_loading_optional_runtime(self):
        adapter = RapidOCRAdapter(
            FakeEngine(SimpleNamespace(boxes=None, txts=None, scores=None)),
            "3.10.0", image_decoder=lambda _page: object(),
        )
        self.assertEqual(adapter.recognize(RasterPage(1, 1, 1, b"x"), ("it", "en")), ())

    def test_rejects_misaligned_output_arrays(self):
        adapter = RapidOCRAdapter(
            FakeEngine(SimpleNamespace(boxes=[[[0, 0], [1, 0], [1, 1]]], txts=["x"], scores=[])),
            "3.10.0", image_decoder=lambda _page: object(),
        )
        with self.assertRaisesRegex(ValueError, "do not align"):
            adapter.recognize(RasterPage(1, 10, 10, b"x"), ("it", "en"))

    def test_rejects_points_that_are_not_exactly_xy_pairs(self):
        adapter = RapidOCRAdapter(
            FakeEngine(SimpleNamespace(
                boxes=[[[0, 0, 7], [1, 0], [1, 1]]], txts=["x"], scores=[0.5],
            )),
            "3.10.0", image_decoder=lambda _page: object(),
        )
        with self.assertRaisesRegex(ValueError, "exactly x and y"):
            adapter.recognize(RasterPage(1, 10, 10, b"x"), ("it", "en"))

    def test_contract_rejects_non_normalized_engine_geometry(self):
        adapter = RapidOCRAdapter(
            FakeEngine(SimpleNamespace(
                boxes=[[[0, 0], [11, 0], [11, 1], [0, 1]]], txts=["x"], scores=[0.5],
            )),
            "3.10.0", image_decoder=lambda _page: object(),
        )
        with self.assertRaisesRegex(OCRContractError, "normalized"):
            run_ocr(adapter, [RasterPage(1, 10, 10, b"x")], source_sha256="b" * 64)

    def test_rejects_unsupported_language_routes(self):
        adapter = RapidOCRAdapter(
            FakeEngine(SimpleNamespace(boxes=[], txts=[], scores=[])), "3.10.0",
            image_decoder=lambda _page: object(),
        )
        with self.assertRaisesRegex(ValueError, "expects"):
            adapter.recognize(RasterPage(1, 10, 10, b"x"), ("en",))

    def test_rejects_boolean_and_text_coordinates_before_numeric_conversion(self):
        for invalid_x in (True, "1"):
            with self.subTest(invalid_x=invalid_x):
                adapter = RapidOCRAdapter(
                    FakeEngine(SimpleNamespace(
                        boxes=[[[invalid_x, 0], [1, 0], [1, 1]]],
                        txts=["x"], scores=[0.5],
                    )),
                    "3.10.0", image_decoder=lambda _page: object(),
                )
                with self.assertRaisesRegex(ValueError, "coordinates must be numeric"):
                    adapter.recognize(RasterPage(1, 10, 10, b"x"), ("it", "en"))

    def test_rejects_boolean_or_text_confidence_before_numeric_conversion(self):
        for invalid_score in (True, "0.5"):
            with self.subTest(invalid_score=invalid_score):
                adapter = RapidOCRAdapter(
                    FakeEngine(SimpleNamespace(
                        boxes=[[[0, 0], [1, 0], [1, 1]]],
                        txts=["x"], scores=[invalid_score],
                    )),
                    "3.10.0", image_decoder=lambda _page: object(),
                )
                with self.assertRaisesRegex(ValueError, "confidence must be numeric"):
                    adapter.recognize(RasterPage(1, 10, 10, b"x"), ("it", "en"))

    def test_requires_preconfigured_callable_engine_and_version(self):
        with self.assertRaisesRegex(ValueError, "preconfigured"):
            RapidOCRAdapter(None, "3.10.0")
        with self.assertRaisesRegex(ValueError, "version"):
            RapidOCRAdapter(FakeEngine(None), " ")


if __name__ == "__main__":
    unittest.main()
