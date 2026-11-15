"""After deletion nothing of the document stays readable in the archive file (REQ-085).

Payloads are encrypted, and ``secure_delete`` overwrites the freed pages: the
encrypted record, source and library metadata of a deleted document must not be
found in the archive file afterwards. Limits are in docs/product/deletion-limits.md.
"""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from alfa_document_intelligence.local_document_store import LocalDocumentStore

from test_document_library import _record
from test_local_document_store import SyntheticProtector


class DeletionTraceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "archive.sqlite3"
        self.store = LocalDocumentStore(self.path, protector=SyntheticProtector())
        for index in (1, 2):
            record, source = _record(index)
            self.store.save(record, source)
        self.store.set_display_name("doc-001", "Documento da eliminare", actor="u")
        self.store.set_tags("doc-001", ["privato"], actor="u")

    def _payload_samples(self) -> list[bytes]:
        with closing(sqlite3.connect(self.path)) as connection:
            rows = connection.execute("SELECT record_payload, source_payload FROM documents").fetchall()
            library = connection.execute("SELECT library_payload FROM document_library").fetchall()
        return [bytes(blob) for row in rows for blob in row] + [bytes(row[0]) for row in library]

    def test_deleted_payloads_are_not_left_in_the_file(self):
        before = set(self._payload_samples())
        self.assertTrue(self.store.delete("doc-001"))
        remaining = set(self._payload_samples())
        removed = before - remaining
        self.assertEqual(len(removed), 3, "record, source and library metadata of doc-001")
        data = self.path.read_bytes()
        for blob in removed:
            # the start of the authenticated ciphertext is unique to each payload
            self.assertNotIn(blob[6:70], data)
        self.assertFalse(list(self.path.parent.glob("*-journal")), "no rollback journal is left behind")
        self.assertIsNotNone(self.store.get("doc-002"), "the other document is untouched")


if __name__ == "__main__":
    unittest.main()
