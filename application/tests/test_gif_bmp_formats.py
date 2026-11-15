"""Single-frame GIF and BMP are admitted under the same limits as other rasters (REQ-014)."""
from __future__ import annotations

import hashlib
from io import BytesIO
import zipfile

from PIL import Image
import pytest

from alfa_document_intelligence.document_decoder import DecodeLimits, DocumentDecodeError, iter_decoded_pages
from alfa_document_intelligence.document_processing import process_document_record
from alfa_document_intelligence.engines.synthetic_fixed import create_adapter
from alfa_document_intelligence.expense_reports import create_expense_report_intake_session
from alfa_document_intelligence.ingestion import UploadRejected, inventory_stream, materialize_stream_batch
from alfa_document_intelligence.review_ui import _signature_matches


def _gif(size=(40, 20), frames=1, transparent=False) -> bytes:
    images = []
    for index in range(frames):
        image = Image.new("P", size, 0)
        image.putpalette([0, 0, 0, 255, 0, 0] + [0] * (256 * 3 - 6))
        image.putpixel((index, 0), 1)
        images.append(image)
    buffer = BytesIO()
    options = {"transparency": 0} if transparent else {}
    images[0].save(buffer, "GIF", save_all=frames > 1, append_images=images[1:], **options)
    return buffer.getvalue()


def _bmp(size=(40, 20)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, "white").save(buffer, "BMP")
    return buffer.getvalue()


@pytest.mark.parametrize("name,data,kind", [("a.gif", _gif(), "gif"), ("a.bmp", _bmp(), "bmp")])
def test_gif_and_bmp_are_inventoried_with_dimensions(name, data, kind):
    inventory = inventory_stream(BytesIO(data), name)
    source = inventory.documents[0]
    assert (source.media_kind, source.width_px, source.height_px, source.page_count) == (kind, 40, 20, 1)


@pytest.mark.parametrize("member,data", [("a.png", _gif()), ("a.gif", _bmp()), ("a.bmp", _gif())])
def test_archive_member_extension_must_match_the_signature(member, data):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(member, data)
    with pytest.raises(UploadRejected):
        inventory_stream(BytesIO(buffer.getvalue()), "pacchetto.zip")


def test_oversize_logical_screen_is_rejected_before_decoding():
    data = bytearray(_gif())
    data[6:10] = (60000).to_bytes(2, "little") + (60000).to_bytes(2, "little")
    with pytest.raises(UploadRejected):
        inventory_stream(BytesIO(bytes(data)), "grande.gif")


@pytest.mark.parametrize("name,data", [("t.gif", _gif()[:12]), ("t.bmp", _bmp()[:20])])
def test_truncated_files_are_rejected(name, data):
    with pytest.raises(UploadRejected):
        inventory_stream(BytesIO(data), name)


def test_animated_gif_is_rejected_by_the_decoder():
    data = _gif(frames=2)
    with pytest.raises(DocumentDecodeError, match="animated"):
        list(iter_decoded_pages(data, "gif", source_sha256=hashlib.sha256(data).hexdigest(), limits=DecodeLimits()))


def test_gif_transparency_is_flattened_on_white():
    data = _gif(transparent=True)
    page = next(iter_decoded_pages(data, "gif", source_sha256=hashlib.sha256(data).hexdigest(), limits=DecodeLimits()))
    raster = page.raster
    assert (raster.width_px, raster.height_px) == (40, 20)
    assert raster.image_bytes[3:6] == b"\xff\xff\xff"  # transparent background pixel → white
    assert raster.image_bytes[0:3] == b"\xff\x00\x00"  # the red pixel stays


@pytest.mark.parametrize("name,data,media_type", [("r.gif", _gif(), "image/gif"), ("r.bmp", _bmp(), "image/bmp")])
def test_gif_and_bmp_go_through_ocr_with_provenance(name, data, media_type):
    batch = materialize_stream_batch([(name, BytesIO(data))])
    intake = create_expense_report_intake_session(
        batch, expense_report_id="report-g", note_document_id="doc-g", document_ids=["doc-g"],
        session_id="session-g", received_at="2026-11-15T10:00:00+00:00",
    )
    document = intake.documents["doc-g"]
    assert document["source"]["media_type"] == media_type
    result = process_document_record(document, intake.source_bytes["doc-g"], create_adapter())
    assert result["processing"]["ocr"]["status"] == "completed"
    assert result["pages"][0]["page_number"] == 1
    assert _signature_matches(data, media_type)


def test_animated_gif_is_rejected_at_upload_with_a_stable_reason():
    with pytest.raises(UploadRejected, match="animated GIF"):
        inventory_stream(BytesIO(_gif(frames=2)), "animata.gif")
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("animata.gif", _gif(frames=3))
    with pytest.raises(UploadRejected, match="animated GIF"):
        inventory_stream(BytesIO(buffer.getvalue()), "pacchetto.zip")


def test_gif_frame_larger_than_the_limit_is_rejected_at_upload():
    data = bytearray(_gif())
    # Enlarge the first image descriptor's width/height beyond the dimension limit.
    descriptor = data.index(b"\x2c", 13)
    data[descriptor + 5:descriptor + 9] = (60000).to_bytes(2, "little") + (60000).to_bytes(2, "little")
    with pytest.raises(UploadRejected):
        inventory_stream(BytesIO(bytes(data)), "frame.gif")
