"""Backup and restore of the encrypted archive (REQ-086)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from alfa_document_intelligence.local_document_store import LocalDocumentStore, StoreRejected

from test_document_library import _record
from test_local_document_store import SyntheticProtector


class OtherProtector(SyntheticProtector):
    _key = b"another-user-synthetic-protector"


class ArchiveBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.protector = SyntheticProtector()
        self.store = LocalDocumentStore(self.root / "archive.sqlite3", protector=self.protector)
        for index in (1, 2):
            record, source = _record(index)
            self.store.save(record, source)
        self.store.set_tags("doc-001", ["Trasferta"], actor="u")

    def _snapshot(self, store):
        results, _ = store.search_library(limit=200)
        return [
            (item.document_id, item.tags, hashlib.sha256(store.get(item.document_id).source_bytes).hexdigest())
            for item in results
        ]

    def test_backup_then_restore_returns_identical_content(self):
        expected = self._snapshot(self.store)
        manifest = self.store.backup_to(self.root / "backup")
        self.assertEqual((manifest["documents"], manifest["schema_version"]), (2, 4))
        self.store.delete("doc-002")
        self.store.set_tags("doc-001", [], actor="u")
        self.store.restore_from(self.root / "backup")
        self.assertEqual(self._snapshot(self.store), expected)
        self.assertTrue((self.root / "archive.sqlite3.before-restore").exists())

    def test_backup_files_are_encrypted_and_described(self):
        self.store.set_display_name("doc-001", "Nome riconoscibile", actor="u")
        self.store.backup_to(self.root / "backup")
        data = (self.root / "backup" / "archive.sqlite3").read_bytes()
        self.assertNotIn(b"riconoscibile", data)
        manifest = json.loads((self.root / "backup" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["format"], "ocr2-archive-backup-v1")
        self.assertEqual(manifest["sha256"], hashlib.sha256(data).hexdigest())

    def test_a_damaged_backup_is_refused_and_the_archive_is_untouched(self):
        self.store.backup_to(self.root / "backup")
        copy_path = self.root / "backup" / "archive.sqlite3"
        copy_path.write_bytes(copy_path.read_bytes()[:-100])
        before = self._snapshot(self.store)
        with self.assertRaises(StoreRejected):
            self.store.restore_from(self.root / "backup")
        self.assertEqual(self._snapshot(self.store), before)

    def test_a_backup_of_another_user_is_refused(self):
        other = LocalDocumentStore(self.root / "other" / "archive.sqlite3", protector=OtherProtector())
        record, source = _record(9)
        other.save(record, source)
        other.backup_to(self.root / "other-backup")
        with self.assertRaises(StoreRejected):
            self.store.restore_from(self.root / "other-backup")
        self.assertEqual([item[0] for item in self._snapshot(self.store)], ["doc-001", "doc-002"])

    def test_backup_refuses_an_existing_target(self):
        (self.root / "backup").mkdir()
        (self.root / "backup" / "manifest.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(StoreRejected):
            self.store.backup_to(self.root / "backup")


if __name__ == "__main__":
    unittest.main()
