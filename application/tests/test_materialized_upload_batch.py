import hashlib
import io
import zipfile

import unittest

from alfa_document_intelligence.ingestion import (
    IngestionLimits,
    UploadRejected,
    materialize_stream_batch,
    materialize_stream_upload,
)


def _pdf(label):
    return b"%PDF-1.7\n" + label.encode("ascii") + b"\n%%EOF\n"


def _zip(files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, data in files:
            archive.writestr(name, data)
    return output.getvalue()


class NonSeekable:
    def __init__(self, value):
        self._stream = io.BytesIO(value)

    def read(self, size=-1):
        return self._stream.read(size)

    def seek(self, *args):
        raise AssertionError("input stream should not be seeked")


class MaterializedUploadBatchTests(unittest.TestCase):
    def test_nonseekable_pdf_keeps_exact_source_bytes_in_memory(self):
        data = _pdf("expense-note")
        result = materialize_stream_upload(NonSeekable(data), "note.pdf")

        self.assertFalse(result.inventory.archive)
        self.assertEqual(len(result.documents), 1)
        self.assertEqual(result.documents[0].data, data)
        self.assertEqual(result.documents[0].inventory.sha256, hashlib.sha256(data).hexdigest())
        self.assertEqual(result.documents[0].inventory.name, "note.pdf")

    def test_batch_expands_zip_to_ordered_documents_and_reports_duplicates(self):
        note = _pdf("note")
        receipt = _pdf("receipt")
        archive = _zip([
            ("receipts/first.pdf", receipt),
            ("receipts/second.pdf", receipt),
        ])
        result = materialize_stream_batch([
            ("expense-note.pdf", io.BytesIO(note)),
            ("attachments.zip", io.BytesIO(archive)),
        ])

        self.assertEqual(
            [item.inventory.source.name for item in result.uploads],
            ["expense-note.pdf", "attachments.zip"],
        )
        members = result.uploads[1].documents
        self.assertEqual(
            [item.inventory.name for item in members],
            ["receipts/first.pdf", "receipts/second.pdf"],
        )
        self.assertEqual([item.data for item in members], [receipt, receipt])
        self.assertEqual(result.duplicate_document_sha256, (hashlib.sha256(receipt).hexdigest(),))
        self.assertEqual(result.duplicate_source_sha256, ())

    def test_batch_enforces_cumulative_uncompressed_document_limit(self):
        first = _pdf("first")
        second = _pdf("second")
        with self.assertRaisesRegex(UploadRejected, "batch documents"):
            materialize_stream_batch(
                [("first.pdf", io.BytesIO(first)), ("second.pdf", io.BytesIO(second))],
                max_batch_document_bytes=len(first) + len(second) - 1,
            )

    def test_batch_rejects_invalid_cumulative_limit(self):
        with self.assertRaisesRegex(ValueError, "max_batch_document_bytes"):
            materialize_stream_batch([], max_batch_document_bytes=0)

    def test_zip_preserves_inventory_and_rejects_unsafe_archives(self):
        traversal = _zip([("../escape.pdf", _pdf("unsafe"))])
        with self.assertRaisesRegex(UploadRejected, "traversal"):
            materialize_stream_upload(io.BytesIO(traversal), "unsafe.zip")

        empty = _zip([])
        with self.assertRaisesRegex(UploadRejected, "no supported documents"):
            materialize_stream_upload(io.BytesIO(empty), "empty.zip")

    def test_batch_reports_duplicate_input_containers(self):
        data = _pdf("same")
        result = materialize_stream_batch([
            ("one.pdf", io.BytesIO(data)),
            ("two.pdf", io.BytesIO(data)),
        ])

        self.assertEqual(result.duplicate_source_sha256, (hashlib.sha256(data).hexdigest(),))
        self.assertEqual(result.duplicate_document_sha256, (hashlib.sha256(data).hexdigest(),))
