from contextlib import closing
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

from alfa_document_intelligence.fingerprints import SqliteFingerprintRegistry
from alfa_document_intelligence.ingestion import inventory_upload

PDF = b"%PDF-1.7\nsynthetic-only\n"

class FingerprintRegistryTests(unittest.TestCase):
    def write_pdf(self, path):
        path.write_bytes(PDF)
        return inventory_upload(path)

    def test_detects_duplicate_across_separate_batches_without_losing_occurrences(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            upload1 = self.write_pdf(folder / "first.pdf")
            upload2 = self.write_pdf(folder / "second.pdf")
            registry = SqliteFingerprintRegistry(folder / "private" / "fingerprints.sqlite3")
            first = registry.register([upload1])
            second = registry.register([upload2])
            self.assertEqual(first.duplicate_document_sha256, ())
            self.assertEqual(second.duplicate_document_sha256, (upload1.source.sha256,))
            with closing(sqlite3.connect(registry.database_path)) as db:
                self.assertEqual(db.execute("SELECT occurrence_count FROM fingerprints WHERE content_role='document'").fetchone()[0], 2)

    def test_separates_archive_and_document_fingerprints(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            archive_path = folder / "batch.zip"
            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_STORED) as archive:
                archive.writestr("receipt.pdf", PDF)
            upload = inventory_upload(archive_path)
            registry = SqliteFingerprintRegistry(folder / "fingerprints.sqlite3")
            registry.register([upload])
            repeated = registry.register([upload])
        self.assertEqual(repeated.duplicate_archive_sha256, (upload.source.sha256,))
        self.assertEqual(repeated.duplicate_document_sha256, (upload.documents[0].sha256,))

    def test_registry_stores_only_role_hash_and_occurrence_count(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            upload = self.write_pdf(folder / "employee-name.pdf")
            registry = SqliteFingerprintRegistry(folder / "fingerprints.sqlite3")
            registry.register([upload])
            with closing(sqlite3.connect(registry.database_path)) as db:
                columns = [row[1] for row in db.execute("PRAGMA table_info(fingerprints)")]
        self.assertEqual(columns, ["content_role", "sha256", "occurrence_count"])
        self.assertNotIn("name", columns)

if __name__ == "__main__":
    unittest.main()
