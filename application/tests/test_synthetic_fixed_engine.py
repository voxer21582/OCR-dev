"""An engine added with new files only goes through the registry and the pipeline (REQ-023)."""
from __future__ import annotations

from io import BytesIO
import importlib

from PIL import Image

from alfa_document_intelligence.document_processing import process_document_record
from alfa_document_intelligence.expense_reports import create_expense_report_intake_session
from alfa_document_intelligence.ingestion import materialize_stream_batch
from alfa_document_intelligence.ocr_engine_registry import discover_engines


def _png() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (120, 80), "white").save(buffer, "PNG")
    return buffer.getvalue()


def test_registry_lists_synthetic_engine_but_the_launcher_does_not_offer_it():
    manifest = discover_engines()["synthetic-fixed"]
    assert manifest.selectable is False
    assert manifest.artifacts == ()
    launcher = importlib.import_module("alfa_document_intelligence.__main__")
    assert launcher is not None
    selectable = {engine_id for engine_id, item in discover_engines().items() if item.selectable}
    assert "synthetic-fixed" not in selectable


def test_document_processed_end_to_end_with_synthetic_engine():
    manifest = discover_engines()["synthetic-fixed"]
    module_name, attribute = manifest.factory_ref.split(":")
    adapter = getattr(importlib.import_module(module_name), attribute)()
    assert (adapter.name, adapter.version) == (manifest.name, manifest.version)

    batch = materialize_stream_batch([("ricevuta.png", BytesIO(_png()))])
    intake = create_expense_report_intake_session(
        batch, expense_report_id="report-s", note_document_id="doc-s", document_ids=["doc-s"],
        session_id="session-s", received_at="2026-11-15T10:00:00+00:00",
    )
    result = process_document_record(intake.documents["doc-s"], intake.source_bytes["doc-s"], adapter)

    assert result["processing"]["ocr"]["status"] == "completed"
    assert result["processing"]["ocr"]["producer"] == {"stage": "ocr", "name": "synthetic-fixed", "version": "1"}
    assert result["source"]["sha256"] == intake.documents["doc-s"]["source"]["sha256"]
    assert result["pages"] == [{"page_number": 1, "width_px": 120, "height_px": 80}]
