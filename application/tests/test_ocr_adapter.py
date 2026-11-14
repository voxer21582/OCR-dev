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
        self.assertEqual(result[0].tokens[0].text, "EUR 12,50")
        self.assertEqual(self.adapter.calls, [(1, ("it", "en"))])

    def test_page_status_is_explicit_and_rejects_unknown_values(self):
        result = run_ocr(
            self.adapter, self.pages, source_sha256=SOURCE_HASH,
        )[0]
        self.assertEqual(result.status, "complete")
        with self.assertRaisesRegex(ValueError, "status must be complete, partial, or failed"):
            OCRPageResult(
                SOURCE_HASH, 1, "synthetic-ocr", "test-1", "it", (),
                status="unknown",
            )

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


if __name__ == "__main__":
    unittest.main()
