"""Optional local, content-only fingerprint registry for duplicate review."""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Iterable

from .ingestion import UploadInventory


@dataclass(frozen=True)
class DuplicateReport:
    duplicate_document_sha256: tuple[str, ...]
    duplicate_archive_sha256: tuple[str, ...]


class SqliteFingerprintRegistry:
    """Persist only SHA-256 fingerprints; caller must choose an approved private DB path."""
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            connection.execute("PRAGMA user_version")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise RuntimeError("unsupported fingerprint registry schema version")
            connection.execute("""
                CREATE TABLE IF NOT EXISTS fingerprints (
                    content_role TEXT NOT NULL CHECK(content_role IN ('document', 'archive')),
                    sha256 TEXT NOT NULL CHECK(length(sha256) = 64),
                    occurrence_count INTEGER NOT NULL CHECK(occurrence_count > 0),
                    PRIMARY KEY(content_role, sha256)
                )
            """)
            connection.execute("PRAGMA user_version = 1")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10, isolation_level=None)
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def register(self, uploads: Iterable[UploadInventory]) -> DuplicateReport:
        """Record each occurrence atomically and report repeats; never merges/rejects files."""
        document_hashes: list[str] = []
        archive_hashes: list[str] = []
        for upload in uploads:
            if upload.archive:
                archive_hashes.append(upload.source.sha256)
                document_hashes.extend(item.sha256 for item in upload.documents)
            else:
                document_hashes.append(upload.source.sha256)

        duplicates: dict[str, list[str]] = {"document": [], "archive": []}
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                for role, hashes in (("archive", archive_hashes), ("document", document_hashes)):
                    for digest in hashes:
                        row = connection.execute(
                            "SELECT occurrence_count FROM fingerprints WHERE content_role = ? AND sha256 = ?",
                            (role, digest),
                        ).fetchone()
                        if row is not None:
                            duplicates[role].append(digest)
                            connection.execute(
                                "UPDATE fingerprints SET occurrence_count = occurrence_count + 1 WHERE content_role = ? AND sha256 = ?",
                                (role, digest),
                            )
                        else:
                            connection.execute(
                                "INSERT INTO fingerprints(content_role, sha256, occurrence_count) VALUES (?, ?, 1)",
                                (role, digest),
                            )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
        return DuplicateReport(
            duplicate_document_sha256=tuple(duplicates["document"]),
            duplicate_archive_sha256=tuple(duplicates["archive"]),
        )
