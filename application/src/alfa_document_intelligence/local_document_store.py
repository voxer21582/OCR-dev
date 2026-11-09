"""Encrypted, local-only persistence for validated document records."""
from __future__ import annotations

import base64
import copy
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import ntpath
import os
from pathlib import Path
import re
import shutil
import sqlite3
import secrets
import tempfile
import uuid
from typing import Callable, Iterator, Protocol

from .contracts import validate_document_record

DEFAULT_MAX_DOCUMENT_BYTES = 25 * 1024 * 1024
_SCHEMA_VERSION = 2
_INDEX_KEY_NAME = "document-id-hmac-v1"
_INDEX_KEY_PREFIX = b"OCR2-IDX1"
_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")


def _drive_type(root: str) -> int:
    if os.name != "nt":
        raise StoreRejected("Windows local-drive validation is unavailable")
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("Kernel32", use_last_error=True)
    get_drive_type = kernel32.GetDriveTypeW
    get_drive_type.argtypes = [wintypes.LPCWSTR]
    get_drive_type.restype = wintypes.UINT
    return int(get_drive_type(root))


def _has_reparse_component(path: str, *, lstat_lookup=None) -> bool:
    if os.name != "nt" and lstat_lookup is None:
        return False
    lookup = lstat_lookup or os.lstat
    drive, tail = ntpath.splitdrive(path)
    if not drive or drive.startswith("\\\\"):
        return False
    current = f"{drive}\\"
    components = [part for part in tail.split("\\") if part]
    for component in components:
        current = ntpath.join(current, component)
        try:
            metadata = lookup(current)
        except FileNotFoundError:
            return False
        except OSError:
            return True
        attributes = getattr(metadata, "st_file_attributes", 0)
        if attributes & 0x400:  # FILE_ATTRIBUTE_REPARSE_POINT
            return True
    return False


def _validate_local_archive_path(
    path: str, *, drive_type_lookup=None, lstat_lookup=None
) -> None:
    if path.startswith(("\\\\", "//")):
        raise StoreRejected("network archive paths are not supported")
    if os.name == "nt" or drive_type_lookup is not None:
        drive, _ = ntpath.splitdrive(path)
        if not drive or drive.startswith("\\\\"):
            raise StoreRejected("archive path must use a local fixed drive")
        lookup = drive_type_lookup or _drive_type
        try:
            kind = lookup(f"{drive}\\")
        except Exception as exc:
            raise StoreRejected("could not verify that archive path is local") from exc
        if kind != 3:  # DRIVE_FIXED; fail closed for mapped, removable, and unknown drives.
            raise StoreRejected("archive path must reside on a fixed local drive")
    if _has_reparse_component(path, lstat_lookup=lstat_lookup):
        raise StoreRejected("archive path must not traverse a reparse point")


class StoreError(RuntimeError):
    """Base exception for local document-store failures."""


class StoreOperationCancelled(StoreError):
    """A cancellable local archive operation stopped before publication."""


class StoreRejected(StoreError):
    """An input document does not satisfy the persistence contract."""


class StoreIntegrityError(StoreError):
    """Stored ciphertext, record, or source bytes failed integrity checks."""


class StoreSourceConflict(StoreError):
    """A document ID was reused for different source bytes."""


class StoreConcurrentUpdate(StoreError):
    """A record changed after the caller read it and before its update."""


class StoreSchemaError(StoreError):
    """The database schema is unsupported or malformed."""


class StoreProtectionError(StoreError):
    """The platform payload-protection operation failed."""


class PayloadProtector(Protocol):
    def protect(self, plaintext: bytes) -> bytes: ...

    def unprotect(self, protected: bytes) -> bytes: ...


@dataclass(frozen=True)
class StoredDocument:
    record: dict
    source_bytes: bytes
    saved_at: str


@dataclass(frozen=True)
class StoredDocumentSummary:
    document_id: str
    filename: str
    document_family: str
    source_sha256: str
    page_count: int
    saved_at: str


class WindowsDpapiProtector:
    """Protect payloads for the current Windows user with CryptProtectData."""

    _CRYPTPROTECT_UI_FORBIDDEN = 0x1

    @staticmethod
    def _crypt(data: bytes, *, protect: bool) -> bytes:
        if os.name != "nt":
            raise StoreProtectionError("Windows DPAPI is required for the default store protector")
        import ctypes
        from ctypes import wintypes

        class DataBlob(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

        source_buffer = ctypes.create_string_buffer(data, max(1, len(data)))
        source = DataBlob(len(data), ctypes.cast(source_buffer, ctypes.POINTER(ctypes.c_ubyte)))
        destination = DataBlob()
        crypt32 = ctypes.WinDLL("Crypt32", use_last_error=True)
        kernel32 = ctypes.WinDLL("Kernel32", use_last_error=True)
        local_free = kernel32.LocalFree
        local_free.argtypes = [ctypes.c_void_p]
        local_free.restype = ctypes.c_void_p
        crypt_protect = crypt32.CryptProtectData
        crypt_protect.argtypes = [
            ctypes.POINTER(DataBlob), wintypes.LPCWSTR, ctypes.POINTER(DataBlob),
            ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DataBlob),
        ]
        crypt_protect.restype = wintypes.BOOL
        crypt_unprotect = crypt32.CryptUnprotectData
        crypt_unprotect.argtypes = [
            ctypes.POINTER(DataBlob), ctypes.POINTER(wintypes.LPWSTR), ctypes.POINTER(DataBlob),
            ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DataBlob),
        ]
        crypt_unprotect.restype = wintypes.BOOL

        if protect:
            ok = crypt_protect(
                ctypes.byref(source), "OCR2 local document archive", None, None, None,
                WindowsDpapiProtector._CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(destination),
            )
        else:
            ok = crypt_unprotect(
                ctypes.byref(source), None, None, None, None,
                WindowsDpapiProtector._CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(destination),
            )
        if not ok:
            error = ctypes.get_last_error()
            raise StoreProtectionError(f"Windows DPAPI operation failed with error {error}")
        try:
            return ctypes.string_at(destination.pbData, destination.cbData)
        finally:
            local_free(ctypes.cast(destination.pbData, ctypes.c_void_p))

    def protect(self, plaintext: bytes) -> bytes:
        return self._crypt(plaintext, protect=True)

    def unprotect(self, protected: bytes) -> bytes:
        return self._crypt(protected, protect=False)


class LocalDocumentStore:
    """Explicit local archive. Data stays encrypted at rest and never leaves this process."""

    def __init__(
        self,
        path: str | Path,
        *,
        protector: PayloadProtector | None = None,
        max_document_bytes: int = DEFAULT_MAX_DOCUMENT_BYTES,
        _cancel_requested: Callable[[], bool] | None = None,
    ) -> None:
        if (
            not isinstance(max_document_bytes, int)
            or isinstance(max_document_bytes, bool)
            or not 1 <= max_document_bytes <= DEFAULT_MAX_DOCUMENT_BYTES
        ):
            raise ValueError(f"max_document_bytes must be from 1 to {DEFAULT_MAX_DOCUMENT_BYTES}")
        if not isinstance(path, (str, Path)) or not str(path):
            raise ValueError("database path is required")
        if protector is None and os.name != "nt":
            raise StoreProtectionError("Windows DPAPI is required; tests may inject a synthetic protector")
        absolute_path = Path(path).expanduser().absolute()
        _validate_local_archive_path(str(absolute_path))
        self.path = absolute_path
        self._protector = protector or WindowsDpapiProtector()
        self._max_document_bytes = max_document_bytes
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._index_key = b""
        self._known_index_entries: dict[str, str] = {}
        self._initialize()
        self._verify_index_integrity(cancel_requested=_cancel_requested)

    @staticmethod
    def _new_local_file_path(path: str | Path) -> Path:
        if not isinstance(path, (str, Path)) or not str(path):
            raise StoreRejected("archive file path is required")
        absolute_path = Path(path).expanduser().absolute()
        _validate_local_archive_path(str(absolute_path))
        if not absolute_path.parent.is_dir():
            raise StoreRejected("archive file parent directory must already exist")
        if os.path.lexists(absolute_path):
            raise StoreRejected("archive file already exists")
        return absolute_path

    @staticmethod
    def _copy_sqlite_snapshot(
        source_path: Path,
        temporary_path: Path,
        *,
        progress_callback: Callable[[int, int], None] | None = None,
        cancel_requested: Callable[[], bool] | None = None,
    ) -> None:
        source = target = None
        try:
            if cancel_requested is not None and cancel_requested():
                raise StoreOperationCancelled("archive operation cancelled")
            source = sqlite3.connect(source_path.as_uri() + "?mode=ro", uri=True, timeout=10)
            target = sqlite3.connect(temporary_path, timeout=10)
            target.execute("PRAGMA synchronous = FULL")

            def report_progress(_status: int, remaining_pages: int, total_pages: int) -> None:
                if progress_callback is not None:
                    progress_callback(remaining_pages, total_pages)
                if cancel_requested is not None and cancel_requested():
                    # Abort the SQLite backup at a page boundary. The
                    # resulting database error is translated below.
                    target.interrupt()

            source.backup(
                target,
                pages=128,
                progress=report_progress if progress_callback is not None or cancel_requested is not None else None,
                sleep=0.01,
            )
            if cancel_requested is not None and cancel_requested():
                raise StoreOperationCancelled("archive operation cancelled")
            target.commit()
            if cancel_requested is not None and cancel_requested():
                raise StoreOperationCancelled("archive operation cancelled")
        except StoreOperationCancelled:
            raise
        except sqlite3.Error as exc:
            if cancel_requested is not None and cancel_requested():
                raise StoreOperationCancelled("archive operation cancelled") from exc
            raise StoreIntegrityError("could not create a consistent local archive snapshot") from exc
        finally:
            if target is not None:
                target.close()
            if source is not None:
                source.close()

    @classmethod
    def _validate_snapshot(
        cls,
        path: Path,
        *,
        protector: PayloadProtector,
        max_document_bytes: int,
        cancel_requested: Callable[[], bool] | None = None,
    ) -> LocalDocumentStore:
        try:
            connection = sqlite3.connect(path)
            try:
                if cancel_requested is not None and cancel_requested():
                    raise StoreOperationCancelled("archive operation cancelled")
                if cancel_requested is not None:
                    connection.set_progress_handler(lambda: int(cancel_requested()), 1000)
                integrity = [row[0] for row in connection.execute("PRAGMA integrity_check")]
                version = connection.execute("PRAGMA user_version").fetchone()[0]
            finally:
                connection.close()
            if integrity != ["ok"]:
                raise StoreIntegrityError("archive snapshot failed SQLite integrity validation")
            if version != _SCHEMA_VERSION:
                raise StoreSchemaError("archive snapshot schema version is unsupported")
            candidate = cls(
                path,
                protector=protector,
                max_document_bytes=max_document_bytes,
                _cancel_requested=cancel_requested,
            )
            with candidate._connect() as connection:
                for _, record, _ in candidate._iter_records(connection):
                    if cancel_requested is not None and cancel_requested():
                        raise StoreOperationCancelled("archive operation cancelled")
                    row = candidate._row_for_document_id(connection, record["document_id"])
                    if row is None:
                        raise StoreIntegrityError("archive snapshot record disappeared during validation")
                    source = record["source"]
                    candidate._decode_source(
                        row[3],
                        expected_hash=source["sha256"].lower(),
                        expected_length=source["byte_length"],
                    )
            return candidate
        except StoreError:
            raise
        except sqlite3.Error as exc:
            if cancel_requested is not None and cancel_requested():
                raise StoreOperationCancelled("archive operation cancelled") from exc
            raise StoreIntegrityError("archive snapshot could not be validated") from exc

    @staticmethod
    def _publish_snapshot(
        temporary_path: Path,
        destination: Path,
        *,
        publication_callback: Callable[[Callable[[], None]], bool] | None = None,
    ) -> None:
        published = False

        with temporary_path.open("rb+") as snapshot:
            os.fsync(snapshot.fileno())

        def atomic_publish() -> None:
            nonlocal published
            if os.name == "nt":
                os.rename(temporary_path, destination)
            else:
                os.link(temporary_path, destination)
                try:
                    temporary_path.unlink()
                except OSError:
                    pass
            published = True

        try:
            if publication_callback is None:
                atomic_publish()
                return
            try:
                allowed = publication_callback(atomic_publish)
            except Exception:
                if not published:
                    raise
                return
            if not published and not allowed:
                raise StoreOperationCancelled("archive operation cancelled before publication")
            if not published:
                raise StoreError("publication callback returned success without publishing")
        except StoreOperationCancelled:
            raise
        except FileExistsError as exc:
            raise StoreRejected("archive file already exists") from exc
        except OSError as exc:
            raise StoreError("filesystem cannot atomically publish the archive snapshot") from exc

    def backup_to(self, destination: str | Path) -> Path:
        """Create a validated encrypted snapshot at a new local path; never overwrite."""
        destination_path = self._new_local_file_path(destination)
        temporary_path = None
        published = False
        try:
            descriptor, name = tempfile.mkstemp(
                prefix=f".{destination_path.name}.", suffix=".tmp", dir=destination_path.parent
            )
            os.close(descriptor)
            temporary_path = Path(name)
            self._copy_sqlite_snapshot(self.path, temporary_path)
            self._validate_snapshot(
                temporary_path,
                protector=self._protector,
                max_document_bytes=self._max_document_bytes,
            )
            self._publish_snapshot(temporary_path, destination_path)
            published = True
            return destination_path
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    if not published:
                        raise

    def restore_backup_to(
        self,
        source: str | Path,
        destination: str | Path,
        *,
        progress_callback: Callable[[int, int], None] | None = None,
        phase_callback: Callable[[str], None] | None = None,
        cancel_requested: Callable[[], bool] | None = None,
        publication_callback: Callable[[Callable[[], None]], bool] | None = None,
    ) -> LocalDocumentStore:
        """Restore using this store's protector into a new path without changing this store."""
        return type(self).restore_backup(
            source,
            destination,
            protector=self._protector,
            max_document_bytes=self._max_document_bytes,
            progress_callback=progress_callback,
            phase_callback=phase_callback,
            cancel_requested=cancel_requested,
            publication_callback=publication_callback,
        )

    @classmethod
    def restore_backup(
        cls,
        source: str | Path,
        destination: str | Path,
        *,
        protector: PayloadProtector | None = None,
        max_document_bytes: int = DEFAULT_MAX_DOCUMENT_BYTES,
        progress_callback: Callable[[int, int], None] | None = None,
        phase_callback: Callable[[str], None] | None = None,
        cancel_requested: Callable[[], bool] | None = None,
        publication_callback: Callable[[Callable[[], None]], bool] | None = None,
    ) -> LocalDocumentStore:
        """Restore a verified backup to a new local archive path without overwriting."""
        source_path = Path(source).expanduser().absolute() if isinstance(source, (str, Path)) else None
        if source_path is None or not source_path.is_file() or source_path.is_symlink():
            raise StoreRejected("archive backup must be an existing regular local file")
        _validate_local_archive_path(str(source_path))
        destination_path = cls._new_local_file_path(destination)
        if os.path.normcase(str(source_path)) == os.path.normcase(str(destination_path)):
            raise StoreRejected("restore source and destination must be different files")
        try:
            required_bytes = source_path.stat().st_size
            available_bytes = shutil.disk_usage(destination_path.parent).free
        except OSError as exc:
            raise StoreRejected("could not check destination free space") from exc
        if available_bytes < required_bytes:
            raise StoreRejected("insufficient free space for archive restore")
        selected_protector = protector or (WindowsDpapiProtector() if os.name == "nt" else None)
        if selected_protector is None:
            raise StoreProtectionError("Windows DPAPI is required; tests may inject a synthetic protector")
        if cancel_requested is not None and cancel_requested():
            raise StoreOperationCancelled("archive operation cancelled")
        temporary_path = None
        published = False
        try:
            descriptor, name = tempfile.mkstemp(
                prefix=f".{destination_path.name}.", suffix=".tmp", dir=destination_path.parent
            )
            os.close(descriptor)
            temporary_path = Path(name)
            if phase_callback is not None:
                phase_callback("copying")
            cls._copy_sqlite_snapshot(
                source_path,
                temporary_path,
                progress_callback=progress_callback,
                cancel_requested=cancel_requested,
            )
            if cancel_requested is not None and cancel_requested():
                raise StoreOperationCancelled("archive operation cancelled")
            if phase_callback is not None:
                phase_callback("validating")
            candidate = cls._validate_snapshot(
                temporary_path,
                protector=selected_protector,
                max_document_bytes=max_document_bytes,
                cancel_requested=cancel_requested,
            )
            if cancel_requested is not None and cancel_requested():
                raise StoreOperationCancelled("archive operation cancelled")
            if phase_callback is not None:
                phase_callback("publishing")
            if cancel_requested is not None and cancel_requested():
                raise StoreOperationCancelled("archive operation cancelled")
            cls._publish_snapshot(
                temporary_path,
                destination_path,
                publication_callback=publication_callback,
            )
            published = True
            candidate.path = destination_path
            return candidate
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    if not published:
                        raise

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            connection.execute("PRAGMA secure_delete = ON")
            connection.execute("PRAGMA synchronous = FULL")
            yield connection
        finally:
            connection.close()

    @staticmethod
    def _validate_entry_id_primary_key(
        connection: sqlite3.Connection, *, require_not_null: bool
    ) -> None:
        columns = {
            row[1]: row for row in connection.execute("PRAGMA table_info(documents)").fetchall()
        }
        entry_id = columns.get("entry_id")
        if entry_id is None or entry_id[5] != 1:
            raise StoreSchemaError("local document-store entry_id must be a primary key")
        if require_not_null and entry_id[3] != 1:
            raise StoreSchemaError("local document-store entry_id must be NOT NULL")
        if connection.execute("SELECT 1 FROM documents WHERE entry_id IS NULL LIMIT 1").fetchone():
            raise StoreSchemaError("local document-store contains a NULL entry_id")

    def _initialize(self) -> None:
        try:
            with self._connect() as connection:
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                if version > _SCHEMA_VERSION or version < 0:
                    raise StoreSchemaError(f"unsupported local document-store schema version: {version}")
                if version == 0:
                    existing = connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                    ).fetchall()
                    if existing:
                        raise StoreSchemaError("unversioned database contains unknown tables")
                    self._index_key = secrets.token_bytes(32)
                    protected_key = self._protect_index_key(self._index_key)
                    connection.execute("BEGIN IMMEDIATE")
                    connection.execute(
                        "CREATE TABLE documents (entry_id TEXT PRIMARY KEY NOT NULL, document_id_index TEXT NOT NULL, record_payload BLOB NOT NULL, source_payload BLOB NOT NULL)"
                    )
                    connection.execute(
                        "CREATE UNIQUE INDEX documents_document_id_index_unique ON documents(document_id_index)"
                    )
                    connection.execute(
                        "CREATE TABLE store_metadata (key_name TEXT PRIMARY KEY, value_payload BLOB NOT NULL)"
                    )
                    connection.execute(
                        "INSERT INTO store_metadata(key_name, value_payload) VALUES (?, ?)",
                        (_INDEX_KEY_NAME, protected_key),
                    )
                    connection.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
                    connection.commit()
                elif version == 1:
                    columns = {
                        row[1] for row in connection.execute("PRAGMA table_info(documents)").fetchall()
                    }
                    if columns != {"entry_id", "record_payload", "source_payload"}:
                        raise StoreSchemaError("version-1 local document-store table shape is invalid")
                    self._validate_entry_id_primary_key(connection, require_not_null=False)
                    self._index_key = secrets.token_bytes(32)
                    protected_key = self._protect_index_key(self._index_key)
                    connection.execute("BEGIN IMMEDIATE")
                    connection.execute(
                        "CREATE TABLE store_metadata (key_name TEXT PRIMARY KEY, value_payload BLOB NOT NULL)"
                    )
                    connection.execute(
                        "INSERT INTO store_metadata(key_name, value_payload) VALUES (?, ?)",
                        (_INDEX_KEY_NAME, protected_key),
                    )
                    connection.execute(
                        "CREATE TABLE documents_v2 (entry_id TEXT PRIMARY KEY NOT NULL, document_id_index TEXT NOT NULL, record_payload BLOB NOT NULL, source_payload BLOB NOT NULL)"
                    )
                    legacy_rows = connection.execute(
                        "SELECT entry_id, record_payload, source_payload FROM documents"
                    ).fetchall()
                    for entry_id, payload, source_payload in legacy_rows:
                        record, _ = self._decode_record(payload)
                        digest = self._document_id_index(record["document_id"])
                        connection.execute(
                            "INSERT INTO documents_v2(entry_id, document_id_index, record_payload, source_payload) VALUES (?, ?, ?, ?)",
                            (entry_id, digest, payload, source_payload),
                        )
                    connection.execute("DROP TABLE documents")
                    connection.execute("ALTER TABLE documents_v2 RENAME TO documents")
                    connection.execute(
                        "CREATE UNIQUE INDEX documents_document_id_index_unique ON documents(document_id_index)"
                    )
                    connection.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
                    connection.commit()
                else:
                    columns = {
                        row[1] for row in connection.execute("PRAGMA table_info(documents)").fetchall()
                    }
                    if columns != {"entry_id", "document_id_index", "record_payload", "source_payload"}:
                        raise StoreSchemaError("local document-store table shape is invalid")
                    self._validate_entry_id_primary_key(connection, require_not_null=True)
                    indexes = connection.execute("PRAGMA index_list(documents)").fetchall()
                    if not any(
                        row[1] == "documents_document_id_index_unique" and row[2]
                        for row in indexes
                    ):
                        raise StoreSchemaError("local document-store ID index is missing or non-unique")
                    indexed_columns = [
                        row[2]
                        for row in connection.execute(
                            "PRAGMA index_info(documents_document_id_index_unique)"
                        ).fetchall()
                    ]
                    if indexed_columns != ["document_id_index"]:
                        raise StoreSchemaError("local document-store ID index targets the wrong column")
                    metadata_columns = {
                        row[1] for row in connection.execute("PRAGMA table_info(store_metadata)").fetchall()
                    }
                    if metadata_columns != {"key_name", "value_payload"}:
                        raise StoreSchemaError("local document-store metadata shape is invalid")
                    metadata_info = {
                        row[1]: row for row in connection.execute("PRAGMA table_info(store_metadata)").fetchall()
                    }
                    if metadata_info["key_name"][5] != 1 or metadata_info["value_payload"][3] != 1:
                        raise StoreSchemaError("local document-store metadata constraints are invalid")
                    metadata_count = connection.execute(
                        "SELECT COUNT(*) FROM store_metadata"
                    ).fetchone()[0]
                    if metadata_count != 1:
                        raise StoreSchemaError("local document-store metadata contains unexpected entries")
                    row = connection.execute(
                        "SELECT value_payload FROM store_metadata WHERE key_name = ?",
                        (_INDEX_KEY_NAME,),
                    ).fetchone()
                    if row is None:
                        raise StoreSchemaError("local document-store index key is missing")
                    self._index_key = self._unprotect_index_key(row[0])
        except StoreSchemaError:
            raise
        except StoreError:
            raise
        except sqlite3.Error as exc:
            raise StoreSchemaError("could not initialize local document-store database") from exc

    def _protect_index_key(self, key: bytes) -> bytes:
        try:
            protected = self._protector.protect(_INDEX_KEY_PREFIX + key)
        except Exception as exc:
            raise StoreProtectionError("could not protect local archive index key") from exc
        if not isinstance(protected, bytes) or not protected:
            raise StoreProtectionError("payload protector returned an invalid index key")
        return protected

    def _unprotect_index_key(self, protected: bytes) -> bytes:
        try:
            plaintext = self._protector.unprotect(bytes(protected))
        except Exception as exc:
            raise StoreProtectionError("could not unprotect local archive index key") from exc
        if not isinstance(plaintext, bytes) or not plaintext.startswith(_INDEX_KEY_PREFIX):
            raise StoreIntegrityError("local archive index key is invalid")
        key = plaintext[len(_INDEX_KEY_PREFIX):]
        if len(key) != 32:
            raise StoreIntegrityError("local archive index key has an invalid length")
        return key

    def _document_id_index(self, document_id: str) -> str:
        return hmac.new(self._index_key, document_id.encode("utf-8"), hashlib.sha256).hexdigest()

    @staticmethod
    def _validate_record(record: object) -> tuple[str, str]:
        if not isinstance(record, dict):
            raise StoreRejected("document record must be an object")
        issues = validate_document_record(record)
        if issues:
            raise StoreRejected("document record violates contract: " + "; ".join(issues))
        document_id = record.get("document_id")
        if not isinstance(document_id, str) or not document_id.strip() or len(document_id) > 128:
            raise StoreRejected("document_id must be a non-empty string of at most 128 characters")
        source = record.get("source")
        source_hash = source.get("sha256") if isinstance(source, dict) else None
        if not isinstance(source_hash, str) or not _SHA256.fullmatch(source_hash):
            raise StoreRejected("source.sha256 must be a 64-character hexadecimal digest")
        return document_id, source_hash.lower()

    def _decode_record(self, protected: bytes) -> tuple[dict, str]:
        try:
            plaintext = self._protector.unprotect(bytes(protected))
            envelope = json.loads(plaintext.decode("utf-8"))
            if (
                not isinstance(envelope, dict)
                or set(envelope) != {"format_version", "record", "saved_at"}
                or envelope.get("format_version") != 1
                or not isinstance(envelope.get("saved_at"), str)
            ):
                raise ValueError("invalid record envelope")
            record = envelope["record"]
            _, source_hash = self._validate_record(record)
            source = record["source"]
            if source.get("storage_ref") != f"local-archive://{record['document_id']}":
                raise ValueError("stored record has an invalid archive reference")
            byte_length = source.get("byte_length")
            if not isinstance(byte_length, int) or isinstance(byte_length, bool) or byte_length < 1:
                raise ValueError("stored source length is invalid")
            return copy.deepcopy(record), envelope["saved_at"]
        except StoreError as exc:
            raise StoreIntegrityError("stored document record failed integrity validation") from exc
        except Exception as exc:
            raise StoreIntegrityError("stored document record could not be authenticated or decoded") from exc

    def _decode_source(self, protected: bytes, *, expected_hash: str, expected_length: int) -> bytes:
        try:
            source_bytes = self._protector.unprotect(bytes(protected))
            if not isinstance(source_bytes, bytes) or len(source_bytes) != expected_length:
                raise ValueError("stored source length does not match its record")
            if not source_bytes or len(source_bytes) > self._max_document_bytes:
                raise ValueError("stored source is empty or exceeds configured limit")
            if hashlib.sha256(source_bytes).hexdigest() != expected_hash:
                raise ValueError("stored source hash does not match its record")
            return source_bytes
        except Exception as exc:
            raise StoreIntegrityError("stored source could not be authenticated or verified") from exc

    def _iter_records(self, connection: sqlite3.Connection) -> Iterator[tuple[str, dict, str]]:
        cursor = connection.execute(
            "SELECT entry_id, document_id_index, record_payload FROM documents ORDER BY entry_id"
        )
        for entry_id, document_id_index, payload in cursor:
            record, saved_at = self._decode_record(payload)
            if self._document_id_index(record["document_id"]) != document_id_index:
                raise StoreIntegrityError("document ID index failed integrity validation")
            yield entry_id, record, saved_at

    def _verify_index_integrity(self, *, cancel_requested: Callable[[], bool] | None = None) -> None:
        """Check every encrypted record's opaque ID index before serving this store instance."""
        try:
            with self._connect() as connection:
                for entry_id, record, _ in self._iter_records(connection):
                    if cancel_requested is not None and cancel_requested():
                        raise StoreOperationCancelled("archive operation cancelled")
                    self._known_index_entries[self._document_id_index(record["document_id"])] = entry_id
        except StoreError:
            raise
        except sqlite3.Error as exc:
            raise StoreIntegrityError("local document-store ID index could not be verified") from exc

    def _row_for_document_id(self, connection: sqlite3.Connection, document_id: str):
        index = self._document_id_index(document_id)
        row = connection.execute(
            "SELECT entry_id, document_id_index, record_payload, source_payload "
            "FROM documents WHERE document_id_index = ?",
            (index,),
        ).fetchone()
        if row is not None:
            self._known_index_entries[index] = row[0]
            return row
        known_entry_id = self._known_index_entries.get(index)
        if known_entry_id is None:
            return None
        row = connection.execute(
            "SELECT entry_id, document_id_index, record_payload, source_payload "
            "FROM documents WHERE entry_id = ?",
            (known_entry_id,),
        ).fetchone()
        if row is None:
            self._known_index_entries.pop(index, None)
            return None
        if row[1] != index:
            raise StoreIntegrityError("document ID index changed after integrity verification")
        return row

    def save(
        self,
        record: dict,
        source_bytes: bytes,
        *,
        expected_record_sha256: str | None = None,
    ) -> str:
        if expected_record_sha256 is not None and (
            not isinstance(expected_record_sha256, str)
            or not _SHA256.fullmatch(expected_record_sha256)
        ):
            raise StoreRejected("expected_record_sha256 must be a 64-character hexadecimal digest")
        document_id, source_hash = self._validate_record(record)
        if not isinstance(source_bytes, bytes):
            raise StoreRejected("source_bytes must be bytes")
        if not source_bytes:
            raise StoreRejected("source document must not be empty")
        if len(source_bytes) > self._max_document_bytes:
            raise StoreRejected("source document exceeds configured byte limit")
        if record["source"].get("byte_length") != len(source_bytes):
            raise StoreRejected("source bytes do not match record.source.byte_length")
        if hashlib.sha256(source_bytes).hexdigest() != source_hash:
            raise StoreRejected("source bytes do not match record.source.sha256")

        archived_record = copy.deepcopy(record)
        archived_record["source"]["storage_ref"] = f"local-archive://{document_id}"
        issues = validate_document_record(archived_record)
        if issues:
            raise StoreRejected("archived record violates contract: " + "; ".join(issues))
        envelope = {
            "format_version": 1,
            "record": archived_record,
            "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        try:
            record_plaintext = json.dumps(
                envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise StoreRejected("document record must be finite, JSON-serializable data") from exc
        try:
            protected_record = self._protector.protect(record_plaintext)
            protected_source = self._protector.protect(source_bytes)
            if not isinstance(protected_record, bytes) or not protected_record:
                raise StoreProtectionError("payload protector returned invalid record ciphertext")
            if not isinstance(protected_source, bytes) or not protected_source:
                raise StoreProtectionError("payload protector returned invalid source ciphertext")
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                entry_id = None
                found_existing = False
                index = self._document_id_index(document_id)
                existing = self._row_for_document_id(connection, document_id)
                if existing is not None:
                    entry_id, existing_index, existing_payload, existing_source = existing
                    existing_record, _ = self._decode_record(existing_payload)
                    if existing_record["document_id"] != document_id or existing_index != index:
                        raise StoreIntegrityError("document ID index points to a different record")
                    found_existing = True
                    existing_hash = existing_record["source"]["sha256"].lower()
                    existing_length = existing_record["source"]["byte_length"]
                    original = self._decode_source(
                        existing_source, expected_hash=existing_hash, expected_length=existing_length
                    )
                    if existing_hash != source_hash or original != source_bytes:
                        raise StoreSourceConflict("document ID already belongs to different source bytes")
                    if expected_record_sha256 is not None:
                        current = json.dumps(
                            existing_record,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                            allow_nan=False,
                        ).encode("utf-8")
                        if hashlib.sha256(current).hexdigest() != expected_record_sha256.lower():
                            raise StoreConcurrentUpdate("saved document changed since it was read")
                if expected_record_sha256 is not None and not found_existing:
                    raise StoreConcurrentUpdate("saved document no longer exists")
                if entry_id is None:
                    entry_id = str(uuid.uuid4())
                    connection.execute(
                        "INSERT INTO documents(entry_id, document_id_index, record_payload, source_payload) VALUES (?, ?, ?, ?)",
                        (entry_id, index, protected_record, protected_source),
                    )
                    self._known_index_entries[index] = entry_id
                else:
                    connection.execute(
                        "UPDATE documents SET record_payload = ?, source_payload = ? WHERE entry_id = ?",
                        (protected_record, protected_source, entry_id),
                    )
                connection.commit()
                return document_id
        except StoreError:
            raise
        except sqlite3.Error as exc:
            raise StoreError("could not save local document") from exc
        except Exception as exc:
            raise StoreProtectionError("could not protect local document payload") from exc

    def get(self, document_id: str) -> StoredDocument | None:
        if not isinstance(document_id, str) or not document_id:
            return None
        try:
            with self._connect() as connection:
                row = self._row_for_document_id(connection, document_id)
                if row is None:
                    return None
                _, document_id_index, protected_record, protected_source = row
                record, saved_at = self._decode_record(protected_record)
                if record["document_id"] != document_id or self._document_id_index(document_id) != document_id_index:
                    raise StoreIntegrityError("document ID index points to a different record")
                source = record["source"]
                source_bytes = self._decode_source(
                    protected_source, expected_hash=source["sha256"].lower(), expected_length=source["byte_length"]
                )
            return StoredDocument(record, source_bytes, saved_at)
        except StoreError:
            raise
        except sqlite3.Error as exc:
            raise StoreError("could not read local document") from exc

    @staticmethod
    def _summary(record: dict, saved_at: str) -> StoredDocumentSummary:
        source = record["source"]
        return StoredDocumentSummary(
            document_id=record["document_id"],
            filename=str(source.get("original_filename", "")),
            document_family=str(record.get("document_family", "unknown")),
            source_sha256=source["sha256"].lower(),
            page_count=len(record.get("pages", [])),
            saved_at=saved_at,
        )

    def search(self, query: str, *, limit: int = 100) -> list[StoredDocumentSummary]:
        if not isinstance(query, str):
            raise ValueError("query must be text")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 500:
            raise ValueError("limit must be an integer from 1 to 500")
        needle = query.strip().casefold()
        try:
            matches = []
            with self._connect() as connection:
                for _, record, saved_at in self._iter_records(connection):
                    searchable = json.dumps(record, ensure_ascii=False, sort_keys=True).casefold()
                    if not needle or needle in searchable:
                        matches.append(self._summary(record, saved_at))
                        if len(matches) >= limit:
                            break
            return matches
        except StoreError:
            raise
        except sqlite3.Error as exc:
            raise StoreError("could not search local documents") from exc

    def delete(self, document_id: str) -> bool:
        if not isinstance(document_id, str) or not document_id:
            return False
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                index = self._document_id_index(document_id)
                row = self._row_for_document_id(connection, document_id)
                if row is None:
                    connection.commit()
                    return False
                entry_id, document_id_index, protected_record, _ = row
                record, _ = self._decode_record(protected_record)
                if record["document_id"] != document_id or self._document_id_index(document_id) != document_id_index:
                    raise StoreIntegrityError("document ID index points to a different record")
                connection.execute("DELETE FROM documents WHERE entry_id = ?", (entry_id,))
                self._known_index_entries.pop(index, None)
                connection.commit()
            return True
        except StoreError:
            raise
        except sqlite3.Error as exc:
            raise StoreError("could not delete local document") from exc
