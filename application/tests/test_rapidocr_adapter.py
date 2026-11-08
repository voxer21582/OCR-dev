import ctypes
import gc
import sys
import unittest
import weakref
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

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
    def test_default_bridge_declares_rgb_and_owns_buffer_through_engine_call(self):
        rgb = bytes((5, 17, 241, 42, 83, 127, 9, 111, 202, 210, 16, 3))
        page = RasterPage(1, 2, 2, rgb)
        captured = {}
        buffer_refs = []
        array_calls = []
        create_buffer = ctypes.create_string_buffer

        def tracked_buffer(*args):
            buffer = create_buffer(*args)
            buffer_refs.append(weakref.ref(buffer))
            return buffer

        def raw_memory_image(**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(**kwargs)

        def fake_frombuffer(*args, **kwargs):
            array_calls.append((args, kwargs))
            return SimpleNamespace(reshape=lambda shape: SimpleNamespace(shape=shape))

        package = ModuleType("rapidocr")
        utils = ModuleType("rapidocr.utils")
        image_module = ModuleType("rapidocr.utils.load_image")
        image_module.RawMemoryImage = raw_memory_image
        numpy_module = ModuleType("numpy")
        numpy_module.uint8 = "synthetic uint8"
        numpy_module.frombuffer = fake_frombuffer
        modules = {
            "rapidocr": package,
            "rapidocr.utils": utils,
            "rapidocr.utils.load_image": image_module,
            "numpy": numpy_module,
        }

        def engine(image):
            self.assertEqual(getattr(image, "pixel_format", None), "RGB")
            self.assertEqual((image.width, image.height, image.stride, image.length), (2, 2, 6, 12))
            gc.collect()
            self.assertEqual(len(buffer_refs), 1)
            owner = buffer_refs[0]()
            self.assertIsNotNone(owner)
            self.assertEqual(image.address, ctypes.addressof(owner))
            self.assertEqual(ctypes.string_at(image.address, image.length), rgb)
            return SimpleNamespace(boxes=[], txts=[], scores=[])

        with patch.dict(sys.modules, modules), patch.object(
            ctypes, "create_string_buffer", side_effect=tracked_buffer
        ):
            adapter = RapidOCRAdapter(engine, "3.10.0")
            self.assertEqual(adapter.recognize(page, ("it", "en")), ())

        self.assertEqual(captured["pixel_format"], "RGB")
        self.assertEqual(array_calls, [])
        gc.collect()
        self.assertIsNone(buffer_refs[0]())

    def test_default_bridge_rejects_versions_without_raw_memory_image(self):
        for version in ("3.9.9", "3", "unknown"):
            with self.subTest(version=version):
                with self.assertRaisesRegex(ValueError, "requires RapidOCR >=3.10"):
                    RapidOCRAdapter(FakeEngine(None), version)

    def test_injected_decoder_preserves_single_object_and_legacy_version(self):
        marker = (object(), object())
        page = RasterPage(1, 1, 1, b"synthetic callback data")
        decoded = []

        def decode(supplied_page):
            decoded.append(supplied_page)
            return marker

        for version in ("3.9.9", "external-engine"):
            with self.subTest(version=version):
                engine = FakeEngine(SimpleNamespace(boxes=[], txts=[], scores=[]))
                adapter = RapidOCRAdapter(engine, version, image_decoder=decode)
                with patch.dict(sys.modules, {"rapidocr": None, "numpy": None}):
                    self.assertEqual(adapter.recognize(page, ("it", "en")), ())
                self.assertIs(adapter.image_decoder, decode)
                self.assertIs(engine.seen[0], marker)
        self.assertEqual(decoded, [page, page])

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
