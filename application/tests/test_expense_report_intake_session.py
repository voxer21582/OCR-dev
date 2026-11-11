import hashlib
import io
import unittest
import zipfile

from alfa_document_intelligence.expense_reports import (
    ExpenseReportBundleError,
    create_expense_report_intake_session,
)
from alfa_document_intelligence.ingestion import materialize_stream_batch


PDF_NOTE = b"%PDF-1.7\nsynthetic expense note\n"
PDF_RECEIPT = b"%PDF-1.7\nsynthetic receipt\n"
RECEIVED_AT = "2026-10-15T10:30:00+02:00"


def _batch():
    with io.BytesIO() as archive_buffer:
        with zipfile.ZipFile(archive_buffer, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("trip/note.pdf", PDF_NOTE)
            archive.writestr("receipts/receipt.pdf", PDF_RECEIPT)
        archive_bytes = archive_buffer.getvalue()

    return materialize_stream_batch([("trip.zip", io.BytesIO(archive_bytes))])


def _session(batch=None):
    return create_expense_report_intake_session(
        batch or _batch(),
        expense_report_id="expense-report-001",
        note_document_id="doc-001",
        document_ids=["doc-001", "doc-002"],
        session_id="session-001",
        received_at=RECEIVED_AT,
    )


class ExpenseReportIntakeSessionTests(unittest.TestCase):
    def test_materialized_zip_becomes_source_bound_note_and_independent_attachment(self):
        batch = _batch()
        session = _session(batch)

        self.assertEqual(session.bundle["note_document_id"], "doc-001")
        self.assertEqual([item["document_id"] for item in session.bundle["attachments"]], ["doc-002"])
        self.assertEqual(session.documents["doc-001"]["document_family"], "expense_report")
        self.assertEqual(session.documents["doc-002"]["document_family"], "unknown")
        self.assertEqual(session.documents["doc-001"]["source"]["original_filename"], "trip/note.pdf")
        self.assertEqual(session.documents["doc-002"]["source"]["original_filename"], "receipts/receipt.pdf")
        self.assertEqual(session.documents["doc-001"]["source"]["storage_ref"], "memory://session-001/doc-001")
        self.assertEqual(session.source_bytes, {"doc-001": PDF_NOTE, "doc-002": PDF_RECEIPT})
        self.assertEqual(session.documents["doc-001"]["source"]["sha256"], hashlib.sha256(PDF_NOTE).hexdigest())
        self.assertEqual(session.documents["doc-002"]["source"]["sha256"], hashlib.sha256(PDF_RECEIPT).hexdigest())
        self.assertEqual(session.documents["doc-001"]["processing"]["ocr"]["status"], "not_started")

    def test_intake_requires_one_unique_id_per_materialized_document(self):
        batch = _batch()
        with self.assertRaisesRegex(ExpenseReportBundleError, "one document ID"):
            create_expense_report_intake_session(
                batch,
                expense_report_id="case-1",
                note_document_id="doc-001",
                document_ids=["doc-001"],
                session_id="session-001",
                received_at=RECEIVED_AT,
            )

        with self.assertRaisesRegex(ExpenseReportBundleError, "unique"):
            create_expense_report_intake_session(
                batch,
                expense_report_id="case-1",
                note_document_id="doc-001",
                document_ids=["doc-001", "doc-001"],
                session_id="session-001",
                received_at=RECEIVED_AT,
            )

    def test_intake_requires_explicit_note_selection_and_timezone_aware_timestamp(self):
        batch = _batch()
        with self.assertRaisesRegex(ExpenseReportBundleError, "selected expense note"):
            create_expense_report_intake_session(
                batch,
                expense_report_id="case-1",
                note_document_id="absent",
                document_ids=["doc-001", "doc-002"],
                session_id="session-001",
                received_at=RECEIVED_AT,
            )

        with self.assertRaisesRegex(ExpenseReportBundleError, "include a timezone"):
            create_expense_report_intake_session(
                batch,
                expense_report_id="case-1",
                note_document_id="doc-001",
                document_ids=["doc-001", "doc-002"],
                session_id="session-001",
                received_at="2026-10-15T10:30:00",
            )
