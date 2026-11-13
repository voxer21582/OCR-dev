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


if __name__ == "__main__":
    unittest.main()
