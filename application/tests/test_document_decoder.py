import hashlib
import sys
from io import BytesIO
from types import SimpleNamespace

import pytest

from alfa_document_intelligence.document_decoder import (
    DecodeLimits,
    DocumentDecodeError,
    iter_decoded_pages,
)


def _fake_pdfium(pdf_document, security_revision=-1):
    return SimpleNamespace(
        PdfDocument=pdf_document,
        raw=SimpleNamespace(
            FPDF_GetSecurityHandlerRevision=lambda _document: security_revision
        ),
    )


def test_decoder_fails_closed_on_source_hash_mismatch():
    with pytest.raises(DocumentDecodeError, match="do not match"):
        list(iter_decoded_pages(b"pdf", "pdf", source_sha256="0" * 64))


def test_decoder_rejects_unknown_media_before_loading_optional_decoder():
    data = b"data"
    with pytest.raises(DocumentDecodeError, match="unsupported media"):
        list(iter_decoded_pages(data, "docx", source_sha256=hashlib.sha256(data).hexdigest()))


@pytest.mark.parametrize("kwargs", [
    {"max_pages": 0},
    {"max_dimension_px": True},
    {"max_page_pixels": -1},
    {"max_total_pixels": 1.5},
    {"pdf_render_dpi": 601},
    {"max_source_bytes": 0},
])
def test_decode_limits_reject_invalid_values(kwargs):
    with pytest.raises(ValueError):
        DecodeLimits(**kwargs)


def test_raster_decoder_emits_source_bound_rgb8_page_and_enforces_total_pixels():
    image_module = pytest.importorskip("PIL.Image")
    from PIL import Image

    output = BytesIO()
    Image.new("RGBA", (20, 10), (250, 10, 15, 128)).save(output, format="PNG")
    data = output.getvalue()
    pages = list(iter_decoded_pages(data, "png", source_sha256=hashlib.sha256(data).hexdigest()))
    assert len(pages) == 1
    assert pages[0].page_count == 1
    assert pages[0].raster.page_number == 1
    assert (pages[0].raster.width_px, pages[0].raster.height_px) == (20, 10)
    assert len(pages[0].raster.image_bytes) == 20 * 10 * 3
    assert pages[0].raster.image_bytes[:3] == Image.new("RGBA", (1, 1), (250, 10, 15, 128)).convert("RGB").tobytes()

    with pytest.raises(DocumentDecodeError, match="pixel limit"):
        list(iter_decoded_pages(
            data, "png", source_sha256=hashlib.sha256(data).hexdigest(),
            limits=DecodeLimits(max_page_pixels=100, max_total_pixels=100),
        ))


def test_raster_decoder_closes_current_page_if_consumer_stops_early(monkeypatch):
    pytest.importorskip("PIL.Image")
    from PIL import Image

    output = BytesIO()
    Image.new("RGBA", (20, 10), (250, 10, 15, 128)).save(output, format="PNG")
    data = output.getvalue()
    converted = []
    closed = []
    original_convert = Image.Image.convert
    original_close = Image.Image.close

    def track_convert(self, mode=None, *args, **kwargs):
        result = original_convert(self, mode, *args, **kwargs)
        if mode == "RGB":
            converted.append(result)
        return result

    def track_close(self):
        closed.append(self)
        return original_close(self)

    monkeypatch.setattr(Image.Image, "convert", track_convert)
    monkeypatch.setattr(Image.Image, "close", track_close)
    pages = iter_decoded_pages(data, "png", source_sha256=hashlib.sha256(data).hexdigest())
    next(pages)
    pages.close()

    assert converted
    assert converted[-1] in closed


def test_pdf_decoder_closes_page_resources_if_consumer_stops_early(monkeypatch):
    closed = []

    class FakeRgbImage:
        size = (198, 198)

        def tobytes(self):
            return bytes(self.size[0] * self.size[1] * 3)

        def close(self):
            closed.append("rgb")

    class FakeImage:
        def convert(self, mode):
            assert mode == "RGB"
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
            assert scale > 0
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

    monkeypatch.setitem(sys.modules, "pypdfium2", _fake_pdfium(FakePdfDocument))
    data = b"synthetic PDF bytes"
    pages = iter_decoded_pages(
        data, "pdf", source_sha256=hashlib.sha256(data).hexdigest()
    )
    next(pages)
    pages.close()

    assert set(closed) == {"rgb", "image", "bitmap", "page", "document"}



def test_pdf_decoder_wraps_native_open_errors(monkeypatch):
    class BrokenPdfDocument:
        def __init__(self, _data):
            raise RuntimeError("native parser failure")

    monkeypatch.setitem(sys.modules, "pypdfium2", _fake_pdfium(BrokenPdfDocument))
    data = b"synthetic PDF bytes"
    with pytest.raises(DocumentDecodeError, match="^PDF decoding failed$"):
        list(iter_decoded_pages(
            data, "pdf", source_sha256=hashlib.sha256(data).hexdigest()
        ))


def test_pdf_decoder_reports_password_required(monkeypatch):
    class PasswordRequiredError(RuntimeError):
        err_code = 4

    class PasswordProtectedPdfDocument:
        def __init__(self, _data):
            raise PasswordRequiredError("incorrect password")

    pdfium = SimpleNamespace(
        PdfDocument=PasswordProtectedPdfDocument,
        raw=SimpleNamespace(FPDF_ERR_PASSWORD=4),
    )
    monkeypatch.setitem(sys.modules, "pypdfium2", pdfium)
    data = b"synthetic encrypted PDF bytes"

    with pytest.raises(
        DocumentDecodeError,
        match="^password-protected PDF is not supported$",
    ):
        list(iter_decoded_pages(
            data, "pdf", source_sha256=hashlib.sha256(data).hexdigest()
        ))


def test_pdf_decoder_rejects_encrypted_document_before_opening_pages(monkeypatch):
    events = []

    class ProtectedDocument:
        raw = object()

        def __init__(self, _data):
            pass

        def __len__(self):
            events.append("page-count")
            raise AssertionError("encrypted PDF pages must not be inspected")

        def close(self):
            events.append("document-closed")

    pdfium = _fake_pdfium(ProtectedDocument, security_revision=2)
    monkeypatch.setitem(sys.modules, "pypdfium2", pdfium)
    data = b"synthetic PDF accepted with an empty password"

    with pytest.raises(DocumentDecodeError, match="^encrypted PDF is not supported$"):
        list(iter_decoded_pages(
            data, "pdf", source_sha256=hashlib.sha256(data).hexdigest()
        ))

    assert events == ["document-closed"]


def test_pdf_decoder_fails_closed_if_security_status_api_is_missing(monkeypatch):
    class UnverifiableDocument:
        raw = object()

        def __init__(self, _data):
            pass

        def __len__(self):
            raise AssertionError("pages must not be inspected")

        def close(self):
            pass

    pdfium = SimpleNamespace(PdfDocument=UnverifiableDocument, raw=SimpleNamespace())
    monkeypatch.setitem(sys.modules, "pypdfium2", pdfium)
    data = b"synthetic PDF"

    with pytest.raises(DocumentDecodeError, match="PDF encryption status could not be verified"):
        list(iter_decoded_pages(
            data, "pdf", source_sha256=hashlib.sha256(data).hexdigest()
        ))


def test_pdf_decoder_rejects_malformed_bytes():
    pytest.importorskip("pypdfium2")
    data = b"not a valid PDF document"
    with pytest.raises(DocumentDecodeError):
        list(iter_decoded_pages(
            data, "pdf", source_sha256=hashlib.sha256(data).hexdigest()
        ))


def test_pdf_decoder_emits_pages_with_page_count_and_renders_within_pixel_limit():
    pytest.importorskip("pypdfium2")
    pytest.importorskip("PIL.Image")
    from PIL import Image

    output = BytesIO()
    pages = [Image.new("RGB", (72, 72), color) for color in ("white", "gray")]
    pages[0].save(output, format="PDF", save_all=True, append_images=pages[1:], resolution=72)
    data = output.getvalue()
    decoded = list(iter_decoded_pages(
        data, "pdf", source_sha256=hashlib.sha256(data).hexdigest(),
        limits=DecodeLimits(pdf_render_dpi=72, max_page_pixels=20_000, max_total_pixels=40_000),
    ))
    assert len(decoded) == 2
    assert [page.raster.page_number for page in decoded] == [1, 2]
    assert all(page.page_count == 2 for page in decoded)
    assert all(page.raster.width_px <= 72 and page.raster.height_px <= 72 for page in decoded)


def test_decoder_rejects_source_over_byte_limit_before_hash_validation():
    data = b"12345"
    with pytest.raises(DocumentDecodeError, match="source bytes exceed the configured size limit"):
        list(iter_decoded_pages(
            data,
            "pdf",
            source_sha256="invalid",
            limits=DecodeLimits(max_source_bytes=4),
        ))


def test_pdf_decoder_enforces_page_count_before_opening_pages(monkeypatch):
    events = []

    class FakeDocument:
        raw = object()
        def __init__(self, _data):
            pass

        def __len__(self):
            return 2

        def __getitem__(self, _index):
            events.append("page-opened")
            raise AssertionError("page must not be opened after page-count rejection")

        def close(self):
            events.append("document-closed")

    monkeypatch.setitem(sys.modules, "pypdfium2", _fake_pdfium(FakeDocument))
    data = b"synthetic PDF bytes"
    with pytest.raises(DocumentDecodeError, match="page count"):
        list(iter_decoded_pages(
            data,
            "pdf",
            source_sha256=hashlib.sha256(data).hexdigest(),
            limits=DecodeLimits(max_pages=1),
        ))

    assert events == ["document-closed"]


@pytest.mark.parametrize("width_points", [float("nan"), float("inf"), 0])
def test_pdf_decoder_rejects_invalid_page_geometry_before_render(monkeypatch, width_points):
    events = []

    class FakePage:
        def get_size(self):
            return width_points, 72

        def render(self, *, scale):
            events.append("rendered")
            raise AssertionError("invalid geometry must be rejected before render")

        def close(self):
            events.append("page-closed")

    class FakeDocument:
        raw = object()
        def __init__(self, _data):
            self.page = FakePage()

        def __len__(self):
            return 1

        def __getitem__(self, _index):
            return self.page

        def close(self):
            events.append("document-closed")

    monkeypatch.setitem(sys.modules, "pypdfium2", _fake_pdfium(FakeDocument))
    data = b"synthetic PDF bytes"
    with pytest.raises(DocumentDecodeError, match="invalid dimensions"):
        list(iter_decoded_pages(data, "pdf", source_sha256=hashlib.sha256(data).hexdigest()))

    assert events == ["page-closed", "document-closed"]


def test_pdf_decoder_rejects_render_output_over_dimension_limit_and_closes_resources(monkeypatch):
    events = []

    class FakeRgbImage:
        size = (11, 10)

        def tobytes(self):
            events.append("copied-rgb-bytes")
            raise AssertionError("oversized pixels must be rejected before copying bytes")

        def close(self):
            events.append("rgb-closed")

    class FakeImage:
        def convert(self, mode):
            assert mode == "RGB"
            return FakeRgbImage()

        def close(self):
            events.append("image-closed")

    class FakeBitmap:
        def to_pil(self):
            return FakeImage()

        def close(self):
            events.append("bitmap-closed")

    class FakePage:
        def get_size(self):
            return 72, 72

        def render(self, *, scale):
            assert scale > 0
            return FakeBitmap()

        def close(self):
            events.append("page-closed")

    class FakeDocument:
        raw = object()
        def __init__(self, _data):
            self.page = FakePage()

        def __len__(self):
            return 1

        def __getitem__(self, _index):
            return self.page

        def close(self):
            events.append("document-closed")

    monkeypatch.setitem(sys.modules, "pypdfium2", _fake_pdfium(FakeDocument))
    data = b"synthetic PDF bytes"
    with pytest.raises(DocumentDecodeError, match="dimension limit"):
        list(iter_decoded_pages(
            data,
            "pdf",
            source_sha256=hashlib.sha256(data).hexdigest(),
            limits=DecodeLimits(
                max_dimension_px=10,
                max_page_pixels=100,
                max_total_pixels=100,
                pdf_render_dpi=72,
            ),
        ))

    assert "copied-rgb-bytes" not in events
    assert {"rgb-closed", "image-closed", "bitmap-closed", "page-closed", "document-closed"} <= set(events)
