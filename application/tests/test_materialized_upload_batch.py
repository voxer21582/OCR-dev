import hashlib
import io
import zipfile

import pytest

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


def test_materialize_nonseekable_pdf_keeps_exact_source_bytes_in_memory():
    data = _pdf("expense-note")
    result = materialize_stream_upload(NonSeekable(data), "note.pdf")

    assert result.inventory.archive is False
    assert len(result.documents) == 1
    assert result.documents[0].data == data
    assert result.documents[0].inventory.sha256 == hashlib.sha256(data).hexdigest()
    assert result.documents[0].inventory.name == "note.pdf"


def test_materialize_batch_expands_zip_to_independent_ordered_documents_and_reports_duplicates():
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

    assert [item.inventory.source.name for item in result.uploads] == [
        "expense-note.pdf", "attachments.zip"
    ]
    members = result.uploads[1].documents
    assert [item.inventory.name for item in members] == [
        "receipts/first.pdf", "receipts/second.pdf"
    ]
    assert [item.data for item in members] == [receipt, receipt]
    assert result.duplicate_document_sha256 == (hashlib.sha256(receipt).hexdigest(),)
    assert result.duplicate_source_sha256 == ()


def test_materialize_batch_enforces_cumulative_uncompressed_document_limit():
    first = _pdf("first")
    second = _pdf("second")
    with pytest.raises(UploadRejected, match="batch documents"):
        materialize_stream_batch(
            [("first.pdf", io.BytesIO(first)), ("second.pdf", io.BytesIO(second))],
            max_batch_document_bytes=len(first) + len(second) - 1,
        )


def test_materialize_batch_rejects_invalid_cumulative_limit():
    with pytest.raises(ValueError, match="max_batch_document_bytes"):
        materialize_stream_batch([], max_batch_document_bytes=0)


def test_materialize_zip_preserves_container_inventory_and_rejects_unsafe_archives():
    traversal = _zip([("../escape.pdf", _pdf("unsafe"))])
    with pytest.raises(UploadRejected, match="traversal"):
        materialize_stream_upload(io.BytesIO(traversal), "unsafe.zip")

    empty = _zip([])
    with pytest.raises(UploadRejected, match="no supported documents"):
        materialize_stream_upload(io.BytesIO(empty), "empty.zip")


def test_materialize_batch_reports_duplicate_input_containers():
    data = _pdf("same")
    result = materialize_stream_batch([
        ("one.pdf", io.BytesIO(data)),
        ("two.pdf", io.BytesIO(data)),
    ])

    assert result.duplicate_source_sha256 == (hashlib.sha256(data).hexdigest(),)
    assert result.duplicate_document_sha256 == (hashlib.sha256(data).hexdigest(),)
