"""Embedded PDF text is used as a distinct producer instead of OCR (REQ-027)."""
from __future__ import annotations

from io import BytesIO

from PIL import Image

from alfa_document_intelligence.document_processing import process_document_record
from alfa_document_intelligence.expense_reports import create_expense_report_intake_session
from alfa_document_intelligence.ingestion import materialize_stream_batch
from alfa_document_intelligence.pdf_text_layer import PDF_TEXT_PRODUCER_NAME, extract_text_tokens


def _text_pdf(lines: list[str]) -> bytes:
    """A minimal one-page PDF (A4) with Helvetica text, built byte by byte."""
    content = "BT /F1 14 Tf 72 760 Td 18 TL " + " ".join(f"({line}) Tj T*" for line in lines) + " ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


def _image_pdf() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (200, 100), "white").save(buffer, "PDF", resolution=72.0)
    return buffer.getvalue()


class _MustNotRun:
    name = "MustNotRun"
    version = "1"

    def recognize(self, page, languages):
        raise AssertionError("OCR ran on a page with an embedded text layer")


class _Blank:
    name = "BlankOCR"
    version = "1"

    def recognize(self, page, languages):
        return []


def _process(data: bytes, adapter):
    batch = materialize_stream_batch([("nota.pdf", BytesIO(data))])
    intake = create_expense_report_intake_session(
        batch, expense_report_id="report-t", note_document_id="doc-t", document_ids=["doc-t"],
        session_id="session-t", received_at="2026-11-15T10:00:00+00:00",
    )
    return process_document_record(intake.documents["doc-t"], intake.source_bytes["doc-t"], adapter)


def test_text_pdf_yields_words_with_boxes_inside_the_page():
    tokens = extract_text_tokens(_text_pdf(["Ricevuta 001", "Totale: EUR 12,34"]), 1)
    assert tokens is not None
    assert [token.text for token in tokens] == ["Ricevuta", "001", "Totale:", "EUR", "12,34"]
    for token in tokens:
        assert token.confidence is None
        xs = [x for x, _ in token.polygon]
        ys = [y for _, y in token.polygon]
        assert 0.0 <= min(xs) < max(xs) <= 1.0
        assert 0.0 <= min(ys) < max(ys) <= 1.0
    first, second = tokens[0], tokens[3]
    assert min(y for _, y in first.polygon) < min(y for _, y in second.polygon)  # top line first


def test_image_only_or_blank_pdf_has_no_usable_text():
    assert extract_text_tokens(_image_pdf(), 1) is None
    assert extract_text_tokens(_text_pdf(["   "]), 1) is None
    assert extract_text_tokens(_text_pdf(["ok"]), 1) is None  # under the minimum of useful characters


def test_pipeline_uses_the_text_layer_and_names_it_as_producer():
    result = _process(_text_pdf(["Taxi aeroporto", "Totale EUR 12,34"]), _MustNotRun())
    ocr = result["processing"]["ocr"]
    assert ocr["status"] == "completed"
    assert ocr["producer"]["name"] == PDF_TEXT_PRODUCER_NAME
    assert result["source"]["page_count"] == 1


def test_pipeline_falls_back_to_ocr_without_a_text_layer():
    result = _process(_image_pdf(), _Blank())
    assert result["processing"]["ocr"]["producer"]["name"] == "BlankOCR"
