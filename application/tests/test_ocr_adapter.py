import unittest

from alfa_document_intelligence.ocr_adapter import (
    OCRContractError,
    OCRPageResult,
    OCRToken,
    RasterPage,
    run_ocr,
)


SOURCE_HASH = "a" * 64
POLYGON = ((0.1, 0.2), (0.8, 0.2), (0.8, 0.4), (0.1, 0.4))


class FakeAdapter:
    name = "synthetic-test-adapter"
    version = "1"

    def __init__(self, tokens=None):
        self.tokens = tokens if tokens is not None else [
            OCRToken("t1", "EUR 12,50", POLYGON, 0.97)
        ]
        self.calls = []

    def recognize(self, page, languages):
        self.calls.append((page.page_number, languages))
        return self.tokens


class OCRAdapterTests(unittest.TestCase):
    def setUp(self):
        self.pages = [RasterPage(1, 100, 200, b"synthetic-raster")]
        self.adapter = FakeAdapter()

    def test_output_is_bound_to_source_page_and_engine_without_semantic_claims(self):
        result = run_ocr(
            self.adapter, self.pages, source_sha256=SOURCE_HASH,
            languages=("it", "en"),
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].source_sha256, SOURCE_HASH)
        self.assertEqual(result[0].page_number, 1)
        self.assertEqual(result[0].engine_name, self.adapter.name)
        self.assertEqual(result[0].language, "it+en")
        self.assertEqual(result[0].status, "complete")
        self.assertIsNone(result[0].error_code)
        self.assertEqual(result[0].tokens[0].text, "EUR 12,50")
        self.assertEqual(self.adapter.calls, [(1, ("it", "en"))])

    def test_rejects_invalid_source_and_language_contract(self):
        with self.assertRaisesRegex(OCRContractError, "source_sha256"):
            run_ocr(self.adapter, self.pages, source_sha256="bad")
        with self.assertRaisesRegex(OCRContractError, "it/en"):
            run_ocr(self.adapter, self.pages, source_sha256=SOURCE_HASH, languages=("fr",))
        with self.assertRaisesRegex(OCRContractError, "duplicates"):
            run_ocr(self.adapter, self.pages, source_sha256=SOURCE_HASH, languages=("it", "it"))

    def test_rejects_duplicate_pages_and_empty_raster(self):
        with self.assertRaisesRegex(OCRContractError, "unique"):
            run_ocr(
                self.adapter,
                [self.pages[0], RasterPage(1, 100, 200, b"second")],
                source_sha256=SOURCE_HASH,
            )
        with self.assertRaisesRegex(OCRContractError, "non-empty"):
            run_ocr(
                self.adapter, [RasterPage(1, 100, 200, b"")],
                source_sha256=SOURCE_HASH,
            )

    def test_rejects_invalid_polygon_or_confidence(self):
        bad_polygon = OCRToken("t1", "text", ((0.1, 0.2), (1.1, 0.2), (0.8, 0.4)), 0.5)
        with self.assertRaisesRegex(OCRContractError, "normalized"):
            run_ocr(FakeAdapter([bad_polygon]), self.pages, source_sha256=SOURCE_HASH)
        bad_confidence = OCRToken("t1", "text", POLYGON, float("nan"))
        with self.assertRaisesRegex(OCRContractError, "confidence"):
            run_ocr(FakeAdapter([bad_confidence]), self.pages, source_sha256=SOURCE_HASH)

    def test_rejects_duplicate_token_ids_and_empty_text(self):
        duplicate = [OCRToken("t1", "one", POLYGON), OCRToken("t1", "two", POLYGON)]
        with self.assertRaisesRegex(OCRContractError, "unique within a page"):
            run_ocr(FakeAdapter(duplicate), self.pages, source_sha256=SOURCE_HASH)
        empty_text = OCRToken("t1", " ", POLYGON)
        with self.assertRaisesRegex(OCRContractError, "text must be non-empty"):
            run_ocr(FakeAdapter([empty_text]), self.pages, source_sha256=SOURCE_HASH)


class OCRPageResultStatusTests(unittest.TestCase):
    def test_partial_result_keeps_only_observed_tokens_and_a_stable_error_code(self):
        token = OCRToken("t1", "EUR 12,50", POLYGON, 0.97)
        result = OCRPageResult(
            source_sha256=SOURCE_HASH,
            page_number=2,
            engine_name="synthetic-test-adapter",
            engine_version="1",
            language="it+en",
            tokens=(token,),
            status="partial",
            error_code="page_timeout",
        )
        self.assertEqual(result.status, "partial")
        self.assertEqual(result.error_code, "page_timeout")
        self.assertEqual(result.tokens, (token,))

    def test_failed_result_is_representable_without_invented_observations(self):
        result = OCRPageResult(
            source_sha256=SOURCE_HASH,
            page_number=2,
            engine_name="synthetic-test-adapter",
            engine_version="1",
            language="it+en",
            tokens=(),
            status="failed",
            error_code="engine_unavailable",
        )
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error_code, "engine_unavailable")
        self.assertEqual(result.tokens, ())

    def test_status_and_error_code_contract_rejects_invalid_combinations(self):
        common = {
            "source_sha256": SOURCE_HASH,
            "page_number": 1,
            "engine_name": "synthetic-test-adapter",
            "engine_version": "1",
            "language": "it+en",
            "tokens": (),
        }
        invalid = (
            {"status": "unknown"},
            {"status": "complete", "error_code": "engine_error"},
            {"status": "partial"},
            {"status": "failed", "error_code": "engine_error", "tokens": (OCRToken("t1", "x", POLYGON),)},
            {"status": "failed", "error_code": "private_path_credential"},
        )
        for fields in invalid:
            with self.subTest(fields=fields):
                with self.assertRaises(OCRContractError):
                    OCRPageResult(**(common | fields))

    def test_status_metadata_remains_immutable(self):
        result = OCRPageResult(
            source_sha256=SOURCE_HASH,
            page_number=1,
            engine_name="synthetic-test-adapter",
            engine_version="1",
            language="it+en",
            tokens=(),
            status="failed",
            error_code="engine_unavailable",
        )
        with self.assertRaises(AttributeError):
            result.status = "complete"

    def test_result_constructor_validates_provenance_and_immutable_payload(self):
        class HostileInteger(int):
            def __ge__(self, other):
                raise RuntimeError("custom comparison must not run")

        enormous_integer = 10**1000
        token = OCRToken("t1", "observed", POLYGON)
        common = {
            "source_sha256": SOURCE_HASH,
            "page_number": 1,
            "engine_name": "synthetic-test-adapter",
            "engine_version": "1",
            "language": "it+en",
            "tokens": (),
            "status": "partial",
            "error_code": "page_timeout",
        }
        invalid = (
            {"source_sha256": "bad"},
            {"page_number": True},
            {"engine_name": " "},
            {"engine_version": ""},
            {"language": "it+it"},
            {"tokens": [token]},
            {"tokens": (OCRToken("t1", "", POLYGON),)},
            {"tokens": (OCRToken(
                "huge-coordinate", "x",
                ((enormous_integer, 0), (1, 0), (1, 1)),
            ),)},
            {"tokens": (OCRToken(
                "hostile-coordinate", "x",
                ((HostileInteger(0), 0), (1, 0), (1, 1)),
            ),)},
            {"tokens": (OCRToken(
                "huge-confidence", "x", POLYGON, enormous_integer,
            ),)},
        )
        for fields in invalid:
            with self.subTest(fields=fields), self.assertRaises(OCRContractError):
                OCRPageResult(**(common | fields))

    def test_run_ocr_rejects_invalid_page_number_and_engine_identity(self):
        adapter = FakeAdapter()
        pages = [RasterPage(1, 100, 200, b"synthetic-raster")]
        with self.assertRaisesRegex(OCRContractError, "positive integer"):
            run_ocr(
                adapter, [RasterPage(True, 100, 200, b"synthetic-raster")],
                source_sha256=SOURCE_HASH,
            )

        adapter.name = " "
        with self.assertRaisesRegex(OCRContractError, "adapter name"):
            run_ocr(adapter, pages, source_sha256=SOURCE_HASH)

        adapter.name = "synthetic-test-adapter"
        adapter.version = ""
        with self.assertRaisesRegex(OCRContractError, "adapter version"):
            run_ocr(adapter, pages, source_sha256=SOURCE_HASH)


if __name__ == "__main__":
    unittest.main()
