"""Dependency-free tests for raster decoder dispatch and page contracts.

These tests replace Pillow with a synthetic in-memory stand-in. They verify
the application boundary only; they do not prove that Pillow can decode real
JPEG, WebP, PNG, or TIFF files.
"""
from __future__ import annotations

import hashlib
import sys
import types
import unittest
from unittest.mock import patch

from alfa_document_intelligence.document_decoder import (
    DecodeLimits,
    DocumentDecodeError,
    iter_decoded_pages,
)


class _RgbImage:
    def __init__(self, width: int, height: int, marker: int):
        self.size = (width, height)
        self._marker = marker

    def tobytes(self) -> bytes:
        return bytes([self._marker]) * (self.size[0] * self.size[1] * 3)

    def close(self) -> None:
        pass


class _SyntheticSource:
    def __init__(self, image_format: str, sizes: tuple[tuple[int, int], ...]):
        self.format = image_format
        self._sizes = sizes
        self.n_frames = len(sizes)
        self._frame = 0

    @property
    def size(self) -> tuple[int, int]:
        return self._sizes[self._frame]

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        pass

    def seek(self, index: int) -> None:
        self._frame = index

    def load(self) -> None:
        pass

    def convert(self, mode: str) -> _RgbImage:
        if mode != "RGB":
            raise AssertionError(f"unexpected output mode: {mode}")
        width, height = self.size
        return _RgbImage(width, height, self._frame + 1)


def _install_synthetic_pillow(source: _SyntheticSource):
    package = types.ModuleType("PIL")
    package.__path__ = []
    image_module = types.ModuleType("PIL.Image")
    image_module.open = lambda _file: source
    image_ops_module = types.ModuleType("PIL.ImageOps")
    image_ops_module.exif_transpose = lambda image: image
    package.Image = image_module
    package.ImageOps = image_ops_module
    return patch.dict(sys.modules, {
        "PIL": package,
        "PIL.Image": image_module,
        "PIL.ImageOps": image_ops_module,
    })


class RasterDecoderContractTests(unittest.TestCase):
    def _decode(self, kind: str, image_format: str, sizes: tuple[tuple[int, int], ...]):
        data = f"synthetic {kind} source".encode("ascii")
        source = _SyntheticSource(image_format, sizes)
        with _install_synthetic_pillow(source):
            pages = list(iter_decoded_pages(
                data,
                kind,
                source_sha256=hashlib.sha256(data).hexdigest(),
            ))
        return pages

    def test_supported_raster_kinds_dispatch_to_the_expected_decoder_format(self):
        for kind, image_format in (
            ("png", "PNG"),
            ("jpeg", "JPEG"),
            ("webp", "WEBP"),
            ("tiff", "TIFF"),
        ):
            with self.subTest(kind=kind):
                pages = self._decode(kind, image_format, ((3, 2),))
                self.assertEqual(len(pages), 1)
                self.assertEqual(pages[0].page_count, 1)
                self.assertEqual(pages[0].raster.page_number, 1)
                self.assertEqual((pages[0].raster.width_px, pages[0].raster.height_px), (3, 2))
                self.assertEqual(len(pages[0].raster.image_bytes), 3 * 2 * 3)

    def test_raster_decoder_rejects_format_that_disagrees_with_inventory(self):
        data = b"synthetic jpeg source"
        source = _SyntheticSource("PNG", ((3, 2),))
        with _install_synthetic_pillow(source):
            with self.assertRaisesRegex(DocumentDecodeError, "format does not match inventory"):
                list(iter_decoded_pages(
                    data,
                    "jpeg",
                    source_sha256=hashlib.sha256(data).hexdigest(),
                ))

    def test_multipage_tiff_emits_each_page_in_source_order(self):
        pages = self._decode("tiff", "TIFF", ((3, 2), (2, 1), (1, 1)))
        self.assertEqual([page.raster.page_number for page in pages], [1, 2, 3])
        self.assertEqual([page.page_count for page in pages], [3, 3, 3])
        self.assertEqual(
            [(page.raster.width_px, page.raster.height_px) for page in pages],
            [(3, 2), (2, 1), (1, 1)],
        )
        self.assertEqual([page.raster.image_bytes[0] for page in pages], [1, 2, 3])

    def test_decoder_rejects_non_string_media_kind_with_contract_error(self):
        data = b"synthetic source"
        with self.assertRaisesRegex(DocumentDecodeError, "unsupported media kind"):
            list(iter_decoded_pages(
                data,
                [],
                source_sha256=hashlib.sha256(data).hexdigest(),
            ))


class PdfDecoderResourceContractTests(unittest.TestCase):
    def test_closes_pdf_resources_when_consumer_stops_early(self):
        closed = []

        class FakeRgbImage:
            size = (198, 198)

            def tobytes(self):
                return bytes(self.size[0] * self.size[1] * 3)

            def close(self):
                closed.append("rgb")

        class FakeImage:
            def convert(self, mode):
                if mode != "RGB":
                    raise AssertionError(f"unexpected output mode: {mode}")
                return FakeRgbImage()

            def close(self):
                closed.append("image")

        class FakeBitmap:
            def to_pil(self):
                return FakeImage()

            def close(self):
                closed.append("bitmap")

        class FakePage:
            def get_size(self):
                return 72, 72

            def render(self, *, scale):
                if scale <= 0:
                    raise AssertionError("render scale must be positive")
                return FakeBitmap()

            def close(self):
                closed.append("page")

        class FakePdfDocument:
            raw = object()

            def __init__(self, _data):
                self.page = FakePage()

            def __len__(self):
                return 1

            def __getitem__(self, _index):
                return self.page

            def close(self):
                closed.append("document")

        pdfium = types.SimpleNamespace(
            PdfDocument=FakePdfDocument,
            raw=types.SimpleNamespace(FPDF_GetSecurityHandlerRevision=lambda _raw: -1),
        )
        data = b"synthetic PDF bytes"
        with patch.dict(sys.modules, {"pypdfium2": pdfium}):
            pages = iter_decoded_pages(
                data,
                "pdf",
                source_sha256=hashlib.sha256(data).hexdigest(),
            )
            next(pages)
            pages.close()

        self.assertCountEqual(closed, {"rgb", "image", "bitmap", "page", "document"})


class _SyntheticPdfRgb:
    def __init__(self, size, marker, closed):
        self.size = size
        self.marker = marker
        self.closed = closed

    def tobytes(self):
        return bytes([self.marker]) * (self.size[0] * self.size[1] * 3)

    def close(self):
        self.closed.append("rgb")


class _SyntheticPdfImage:
    def __init__(self, size, marker, closed):
        self.size = size
        self.marker = marker
        self.closed = closed

    def convert(self, mode):
        if mode != "RGB":
            raise AssertionError(f"unexpected PDF image mode: {mode}")
        return _SyntheticPdfRgb(self.size, self.marker, self.closed)

    def close(self):
        self.closed.append("image")


class _SyntheticPdfBitmap:
    def __init__(self, size, marker, closed):
        self.size = size
        self.marker = marker
        self.closed = closed

    def to_pil(self):
        return _SyntheticPdfImage(self.size, self.marker, self.closed)

    def close(self):
        self.closed.append("bitmap")


class _SyntheticPdfPage:
    def __init__(self, size, marker, closed):
        self.size = size
        self.marker = marker
        self.closed = closed
        self.scale = None
        self.was_closed = False

    def get_size(self):
        return (72.0, 72.0)

    def render(self, *, scale):
        self.scale = scale
        return _SyntheticPdfBitmap(self.size, self.marker, self.closed)

    def close(self):
        self.was_closed = True


class _SyntheticPdfDocument:
    def __init__(self, page_specs):
        self.closed_resources = []
        self.pages = [
            _SyntheticPdfPage(size, marker, self.closed_resources)
            for size, marker in page_specs
        ]
        self.raw = object()
        self.accessed = []
        self.was_closed = False

    def __len__(self):
        return len(self.pages)

    def __getitem__(self, index):
        self.accessed.append(index)
        return self.pages[index]

    def close(self):
        self.was_closed = True


def _install_synthetic_pdfium(document, security_revision=-1):
    package = types.ModuleType("pypdfium2")
    package.PdfDocument = lambda _data: document
    package.raw = types.SimpleNamespace(
        FPDF_GetSecurityHandlerRevision=lambda _raw: security_revision
    )
    return patch.dict(sys.modules, {"pypdfium2": package})


class PdfDecoderContractTests(unittest.TestCase):
    def _decode(self, document, *, security_revision=-1, limits=DecodeLimits()):
        data = b"%PDF synthetic bytes"
        with _install_synthetic_pdfium(document, security_revision):
            pages = list(iter_decoded_pages(
                data,
                "pdf",
                source_sha256=hashlib.sha256(data).hexdigest(),
                limits=limits,
            ))
        return pages

    def test_pdf_decoder_emits_ordered_pages_and_closes_native_resources(self):
        document = _SyntheticPdfDocument([
            ((2, 3), 21),
            ((3, 1), 22),
        ])
        pages = self._decode(document)
        self.assertEqual([page.raster.page_number for page in pages], [1, 2])
        self.assertEqual([page.page_count for page in pages], [2, 2])
        self.assertEqual(
            [(page.raster.width_px, page.raster.height_px) for page in pages],
            [(2, 3), (3, 1)],
        )
        self.assertEqual([page.raster.image_bytes[0] for page in pages], [21, 22])
        self.assertEqual(document.accessed, [0, 1])
        self.assertTrue(document.was_closed)
        self.assertTrue(all(page.was_closed for page in document.pages))
        self.assertEqual(
            document.closed_resources,
            ["rgb", "image", "bitmap", "rgb", "image", "bitmap"],
        )

    def test_encrypted_pdf_is_rejected_before_page_access_and_document_is_closed(self):
        document = _SyntheticPdfDocument([((1, 1), 1)])
        data = b"%PDF synthetic bytes"
        with _install_synthetic_pdfium(document, security_revision=0):
            with self.assertRaisesRegex(DocumentDecodeError, "encrypted PDF"):
                list(iter_decoded_pages(
                    data,
                    "pdf",
                    source_sha256=hashlib.sha256(data).hexdigest(),
                ))
        self.assertEqual(document.accessed, [])
        self.assertTrue(document.was_closed)

    def test_pdf_page_limit_is_checked_before_page_resources_are_opened(self):
        document = _SyntheticPdfDocument([
            ((1, 1), 1),
            ((1, 1), 2),
        ])
        data = b"%PDF synthetic bytes"
        with _install_synthetic_pdfium(document):
            with self.assertRaisesRegex(DocumentDecodeError, "page count"):
                list(iter_decoded_pages(
                    data,
                    "pdf",
                    source_sha256=hashlib.sha256(data).hexdigest(),
                    limits=DecodeLimits(max_pages=1),
                ))
        self.assertEqual(document.accessed, [])
        self.assertTrue(document.was_closed)

    def test_stopping_after_first_pdf_page_closes_every_open_resource(self):
        document = _SyntheticPdfDocument([
            ((2, 2), 3),
            ((2, 2), 4),
        ])
        data = b"%PDF synthetic bytes"
        with _install_synthetic_pdfium(document):
            pages = iter_decoded_pages(
                data,
                "pdf",
                source_sha256=hashlib.sha256(data).hexdigest(),
            )
            first = next(pages)
            self.assertEqual(first.raster.page_number, 1)
            pages.close()
        self.assertTrue(document.was_closed)
        self.assertTrue(document.pages[0].was_closed)
        self.assertEqual(document.pages[1].was_closed, False)
        self.assertEqual(document.closed_resources, ["rgb", "image", "bitmap"])


if __name__ == "__main__":
    unittest.main()
