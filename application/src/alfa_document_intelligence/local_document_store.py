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
import uuid
from typing import Iterator, Protocol

from .contracts import validate_document_record

DEFAULT_MAX_DOCUMENT_BYTES = 25 * 1024 * 1024
_SCHEMA_VERSION = 3
_INDEX_KEY_NAME = "document-id-hmac-v1"
_INDEX_KEY_PREFIX = b"OCR2-IDX1"
_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
_STORE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_MAX_CASE_ATTACHMENTS = 100
_MAX_CASE_SOURCE_BYTES = 2525 * 1024 * 1024
_MAX_CASE_CHUNK_DOCUMENTS = 20
_MAX_CASE_CHUNK_BYTES = 100 * 1024 * 1024
_MAX_CASE_RECORD_METADATA_BYTES = 1024 * 1024
_MAX_CASE_TOTAL_METADATA_BYTES = (_MAX_CASE_ATTACHMENTS + 1) * _MAX_CASE_RECORD_METADATA_BYTES


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
        self._known_case_entries: dict[str, str] = {}
        self._initialize()
        self._verify_index_integrity()
        self._verify_case_index_integrity()

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
                    connection.execute("PRAGMA user_version = 2")
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
                    connection.execute("PRAGMA user_version = 2")
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
                if version < 3:
                    self._migrate_schema_v3(connection)
                else:
                    self._validate_schema_v3(connection)
        except StoreSchemaError:
            raise
        except StoreError:
            raise
        except sqlite3.Error as exc:
            raise StoreSchemaError("could not initialize local document-store database") from exc

    @staticmethod
    def _validate_schema_v3(connection: sqlite3.Connection) -> None:
        expected = {
            "cases": {"entry_id", "case_id_index", "case_payload"},
            "case_documents": {"entry_id", "case_id_index", "document_id_index", "binding_payload"},
            "document_retention": {"document_id_index", "independently_retained"},
        }
        for table, columns in expected.items():
            actual = {row[1] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
            if actual != columns:
                raise StoreSchemaError(f"local document-store {table} table shape is invalid")
        for table, key_column in (("cases", "entry_id"), ("case_documents", "entry_id"), ("document_retention", "document_id_index")):
            primary_keys = [row for row in connection.execute(f"PRAGMA table_info({table})").fetchall() if row[5] == 1]
            if len(primary_keys) != 1 or primary_keys[0][1] != key_column or primary_keys[0][3] != 1:
                raise StoreSchemaError(f"local document-store {table} primary key is invalid")
        indexes = {
            row[1]: row for row in connection.execute("PRAGMA index_list(cases)").fetchall()
        }
        if "cases_case_id_index_unique" not in indexes or not indexes["cases_case_id_index_unique"][2]:
            raise StoreSchemaError("local case ID index is missing or non-unique")
        case_index_columns = [row[2] for row in connection.execute(
            "PRAGMA index_info(cases_case_id_index_unique)"
        ).fetchall()]
        if case_index_columns != ["case_id_index"]:
            raise StoreSchemaError("local case ID index targets the wrong column")
        ref_indexes = {
            row[1]: row for row in connection.execute("PRAGMA index_list(case_documents)").fetchall()
        }
        if "case_documents_case_document_unique" not in ref_indexes or not ref_indexes["case_documents_case_document_unique"][2]:
            raise StoreSchemaError("local case-document reference index is missing or non-unique")
        ref_index_columns = [row[2] for row in connection.execute(
            "PRAGMA index_info(case_documents_case_document_unique)"
        ).fetchall()]
        if ref_index_columns != ["case_id_index", "document_id_index"]:
            raise StoreSchemaError("local case-document reference index targets the wrong columns")

    def _migrate_schema_v3(self, connection: sqlite3.Connection) -> None:
        """Add encrypted case payloads and retention markers without changing v2 records."""
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "CREATE TABLE cases (entry_id TEXT PRIMARY KEY NOT NULL, case_id_index TEXT NOT NULL, case_payload BLOB NOT NULL)"
            )
            connection.execute(
                "CREATE UNIQUE INDEX cases_case_id_index_unique ON cases(case_id_index)"
            )
            connection.execute(
                "CREATE TABLE case_documents (entry_id TEXT PRIMARY KEY NOT NULL, case_id_index TEXT NOT NULL, document_id_index TEXT NOT NULL, binding_payload BLOB NOT NULL)"
            )
            connection.execute(
                "CREATE UNIQUE INDEX case_documents_case_document_unique ON case_documents(case_id_index, document_id_index)"
            )
            connection.execute(
                "CREATE INDEX case_documents_document_index ON case_documents(document_id_index)"
            )
            connection.execute(
                "CREATE TABLE document_retention (document_id_index TEXT PRIMARY KEY NOT NULL, independently_retained INTEGER NOT NULL CHECK(independently_retained IN (0, 1)))"
            )
            # Existing v2 documents were individually archived; preserve them as independent records.
            connection.execute(
                "INSERT INTO document_retention(document_id_index, independently_retained) "
                "SELECT document_id_index, 1 FROM documents"
            )
            connection.execute("PRAGMA user_version = 3")
            connection.commit()
        except sqlite3.Error as exc:
            connection.rollback()
            raise StoreSchemaError("could not migrate local document-store schema to version 3") from exc
        self._validate_schema_v3(connection)

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

    def _case_id_index(self, case_id: str) -> str:
        return hmac.new(self._index_key, b"case\0" + case_id.encode("utf-8"), hashlib.sha256).hexdigest()

    @staticmethod
    def _canonical_json(value: object) -> bytes:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")

    @classmethod
    def _case_revision(cls, case: dict) -> str:
        payload = copy.deepcopy(case)
        payload.pop("case_revision", None)
        return hashlib.sha256(cls._canonical_json(payload)).hexdigest()

    @classmethod
    def _validate_case(cls, case: object, *, verify_revision: bool = True) -> dict:
        if not isinstance(case, dict):
            raise StoreRejected("case manifest must be an object")
        if case.get("schema_version") != "0.1.0":
            raise StoreRejected("case manifest schema_version is unsupported")
        case_id = case.get("case_id")
        statement_id = case.get("statement_document_id")
        statement_hash = case.get("statement_sha256")
        if not isinstance(case_id, str) or not _STORE_ID.fullmatch(case_id):
            raise StoreRejected("case_id must be an opaque identifier")
        if not isinstance(statement_id, str) or not _STORE_ID.fullmatch(statement_id):
            raise StoreRejected("statement_document_id must be an opaque identifier")
        if not isinstance(statement_hash, str) or not _SHA256.fullmatch(statement_hash):
            raise StoreRejected("statement_sha256 must be a SHA-256 digest")
        attachments = case.get("attachments")
        if not isinstance(attachments, list) or len(attachments) > _MAX_CASE_ATTACHMENTS:
            raise StoreRejected("case attachments must be an array of at most 100 documents")
        seen = {statement_id}
        for item in attachments:
            if not isinstance(item, dict):
                raise StoreRejected("case attachment reference must be an object")
            document_id = item.get("document_id")
            source_hash = item.get("source_sha256")
            if not isinstance(document_id, str) or not _STORE_ID.fullmatch(document_id) or document_id in seen:
                raise StoreRejected("case document IDs must be unique opaque identifiers")
            if not isinstance(source_hash, str) or not _SHA256.fullmatch(source_hash):
                raise StoreRejected("case attachment source_sha256 must be a SHA-256 digest")
            if type(item.get("included")) is not bool:
                raise StoreRejected("case attachment inclusion state must be boolean")
            seen.add(document_id)
        retained_bytes = case.get("retained_source_bytes")
        if not isinstance(retained_bytes, int) or isinstance(retained_bytes, bool) or not 1 <= retained_bytes <= _MAX_CASE_SOURCE_BYTES:
            raise StoreRejected("case retained_source_bytes is outside its configured limit")
        for name in ("chunks", "review_events", "inclusion_events"):
            if not isinstance(case.get(name, []), list):
                raise StoreRejected(f"case {name} must be an array")
        chunk_ids = set()
        chunk_document_ids = set()
        for chunk in case.get("chunks", []):
            if (
                not isinstance(chunk, dict)
                or not isinstance(chunk.get("chunk_id"), str)
                or not _STORE_ID.fullmatch(chunk["chunk_id"])
                or chunk["chunk_id"] in chunk_ids
                or not isinstance(chunk.get("chunk_digest"), str)
                or not _SHA256.fullmatch(chunk["chunk_digest"])
                or not isinstance(chunk.get("document_ids"), list)
            ):
                raise StoreRejected("case upload chunk ledger is invalid")
            if not chunk["document_ids"] or any(
                not isinstance(document_id, str) or not _STORE_ID.fullmatch(document_id) or document_id in chunk_document_ids
                for document_id in chunk["document_ids"]
            ):
                raise StoreRejected("case upload chunk document references are invalid")
            chunk_ids.add(chunk["chunk_id"])
            chunk_document_ids.update(chunk["document_ids"])
        if chunk_document_ids != {item["document_id"] for item in attachments}:
            raise StoreRejected("case upload chunk ledger does not match its attachment list")
        if any(item.get("chunk_id") not in chunk_ids for item in attachments):
            raise StoreRejected("case attachment does not bind to an upload chunk")
        event_ids = set()
        latest_inclusion = {}
        for sequence, event in enumerate(case.get("inclusion_events", []), start=1):
            if not isinstance(event, dict):
                raise StoreRejected("case inclusion event is invalid")
            event_id = event.get("event_id")
            document_id = event.get("document_id")
            body = {key: value for key, value in event.items() if key not in {"sequence", "event_sha256"}}
            if (
                set(event) != {"event_id", "case_revision", "document_id", "source_sha256", "included", "reason", "sequence", "event_sha256"}
                or not isinstance(event_id, str) or not _STORE_ID.fullmatch(event_id) or event_id in event_ids
                or event.get("sequence") != sequence
                or not isinstance(event.get("case_revision"), str) or not _SHA256.fullmatch(event["case_revision"])
                or not isinstance(document_id, str) or not _STORE_ID.fullmatch(document_id)
                or not isinstance(event.get("source_sha256"), str) or not _SHA256.fullmatch(event["source_sha256"])
                or type(event.get("included")) is not bool
                or not isinstance(event.get("reason"), str) or not event["reason"].strip() or len(event["reason"]) > 2000
                or event.get("event_sha256") != hashlib.sha256(cls._canonical_json(body)).hexdigest()
            ):
                raise StoreRejected("case inclusion event failed its append-only contract")
            event_ids.add(event_id)
            latest_inclusion[document_id] = event
        attachment_by_id = {item["document_id"]: item for item in attachments}
        if any(
            document_id not in attachment_by_id
            or attachment_by_id[document_id]["source_sha256"].lower() != event["source_sha256"].lower()
            for document_id, event in latest_inclusion.items()
        ):
            raise StoreRejected("case inclusion history references a missing or changed source")
        for item in attachments:
            latest = latest_inclusion.get(item["document_id"])
            if latest is not None and (
                latest["source_sha256"].lower() != item["source_sha256"].lower()
                or latest["included"] != item["included"]
            ):
                raise StoreRejected("case attachment inclusion state does not match its event history")
        processing = case.get("processing", {})
        if not isinstance(processing, dict):
            raise StoreRejected("case processing state must be an object")
        result_bytes = processing.get("result_bytes", 0)
        if not isinstance(result_bytes, int) or isinstance(result_bytes, bool) or not 0 <= result_bytes <= 256 * 1024 * 1024:
            raise StoreRejected("case processing result byte count exceeds its configured limit")
        if "committed_chunks" in processing and not isinstance(processing["committed_chunks"], list):
            raise StoreRejected("case processing chunk ledger must be an array")
        try:
            cls._canonical_json(case)
        except (TypeError, ValueError) as exc:
            raise StoreRejected("case manifest must be finite JSON data") from exc
        revision = case.get("case_revision")
        if verify_revision and (not isinstance(revision, str) or not _SHA256.fullmatch(revision) or revision.lower() != cls._case_revision(case)):
            raise StoreIntegrityError("case manifest revision digest is invalid")
        return case

    def _protect_case_payload(self, case: dict) -> bytes:
        envelope = {"format_version": 1, "case": case, "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        try:
            protected = self._protector.protect(self._canonical_json(envelope))
        except Exception as exc:
            raise StoreProtectionError("could not protect local case manifest") from exc
        if not isinstance(protected, bytes) or not protected:
            raise StoreProtectionError("payload protector returned invalid case ciphertext")
        return protected

    def _decode_case_payload(self, protected: bytes) -> dict:
        try:
            envelope = json.loads(self._protector.unprotect(bytes(protected)).decode("utf-8"))
            if (
                not isinstance(envelope, dict)
                or set(envelope) != {"format_version", "case", "saved_at"}
                or envelope.get("format_version") != 1
                or not isinstance(envelope.get("saved_at"), str)
            ):
                raise ValueError("invalid case envelope")
            case = self._validate_case(envelope["case"])
            return copy.deepcopy(case)
        except StoreError as exc:
            raise StoreIntegrityError("stored case manifest failed integrity validation") from exc
        except Exception as exc:
            raise StoreIntegrityError("stored case manifest could not be authenticated or decoded") from exc

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

    def _verify_index_integrity(self) -> None:
        """Check every encrypted record's opaque ID index before serving this store instance."""
        try:
            with self._connect() as connection:
                for entry_id, record, _ in self._iter_records(connection):
                    document_index = self._document_id_index(record["document_id"])
                    if connection.execute(
                        "SELECT 1 FROM document_retention WHERE document_id_index = ?", (document_index,)
                    ).fetchone() is None:
                        raise StoreIntegrityError("document retention state is missing")
                    self._known_index_entries[document_index] = entry_id
                if connection.execute(
                    "SELECT 1 FROM document_retention r LEFT JOIN documents d "
                    "ON d.document_id_index = r.document_id_index WHERE d.entry_id IS NULL LIMIT 1"
                ).fetchone():
                    raise StoreIntegrityError("local document retention index has orphan entries")
        except StoreError:
            raise
        except sqlite3.Error as exc:
            raise StoreIntegrityError("local document-store ID index could not be verified") from exc

    def _case_row_for_id(self, connection: sqlite3.Connection, case_id: str):
        index = self._case_id_index(case_id)
        row = connection.execute(
            "SELECT entry_id, case_id_index, case_payload FROM cases WHERE case_id_index = ?", (index,)
        ).fetchone()
        if row is None:
            known_entry_id = self._known_case_entries.get(index)
            if known_entry_id is not None:
                row = connection.execute(
                    "SELECT entry_id, case_id_index, case_payload FROM cases WHERE entry_id = ?", (known_entry_id,)
                ).fetchone()
                if row is None:
                    self._known_case_entries.pop(index, None)
        if row is not None:
            self._known_case_entries[index] = row[0]
            if row[1] != index:
                raise StoreIntegrityError("case ID index changed after integrity verification")
        return row

    def _protect_case_reference(self, *, source_hash: str, role: str, case_owned: bool) -> bytes:
        payload = {"format_version": 1, "source_sha256": source_hash.lower(), "role": role, "case_owned": case_owned}
        try:
            protected = self._protector.protect(self._canonical_json(payload))
        except Exception as exc:
            raise StoreProtectionError("could not protect local case-document binding") from exc
        if not isinstance(protected, bytes) or not protected:
            raise StoreProtectionError("payload protector returned invalid case-document ciphertext")
        return protected

    def _decode_case_reference(self, protected: bytes) -> dict:
        try:
            payload = json.loads(self._protector.unprotect(bytes(protected)).decode("utf-8"))
            if (
                not isinstance(payload, dict)
                or set(payload) != {"format_version", "source_sha256", "role", "case_owned"}
                or payload.get("format_version") != 1
                or not isinstance(payload.get("source_sha256"), str)
                or not _SHA256.fullmatch(payload["source_sha256"])
                or payload.get("role") not in {"expense_statement", "supporting_document"}
                or type(payload.get("case_owned")) is not bool
            ):
                raise ValueError("invalid case-document binding")
            return payload
        except Exception as exc:
            raise StoreIntegrityError("stored case-document binding could not be authenticated") from exc

    @staticmethod
    def _manifest_document_refs(case: dict) -> list[dict[str, str]]:
        return [
            {"document_id": case["statement_document_id"], "source_sha256": case["statement_sha256"], "role": "expense_statement"},
            *[
                {"document_id": item["document_id"], "source_sha256": item["source_sha256"], "role": "supporting_document"}
                for item in case.get("attachments", [])
            ],
        ]

    def _validate_case_references(self, connection: sqlite3.Connection, case: dict, case_index: str) -> list[dict]:
        expected = {
            self._document_id_index(item["document_id"]): item
            for item in self._manifest_document_refs(case)
        }
        rows = connection.execute(
            "SELECT document_id_index, binding_payload FROM case_documents WHERE case_id_index = ?",
            (case_index,),
        ).fetchall()
        if {row[0] for row in rows} != set(expected):
            raise StoreIntegrityError("case-document references do not match the encrypted case manifest")
        ownership = {}
        actual_bytes = 0
        actual_metadata_bytes = 0
        for document_index, binding_payload in rows:
            binding = self._decode_case_reference(binding_payload)
            ref = expected[document_index]
            if binding["source_sha256"].lower() != ref["source_sha256"].lower() or binding["role"] != ref["role"]:
                raise StoreIntegrityError("case-document reference binding does not match the manifest")
            doc_row = connection.execute(
                "SELECT entry_id, document_id_index, record_payload, source_payload FROM documents WHERE document_id_index = ?",
                (document_index,),
            ).fetchone()
            if doc_row is None:
                raise StoreIntegrityError("case references a missing local document")
            _, stored_index, record_payload, source_payload = doc_row
            record, saved_at = self._decode_record(record_payload)
            doc_id, source_hash = self._validate_record(record)
            if self._document_id_index(doc_id) != stored_index or stored_index != document_index:
                raise StoreIntegrityError("case document index points to a different record")
            if doc_id != ref["document_id"] or source_hash != ref["source_sha256"].lower():
                raise StoreIntegrityError("case source hash does not match the archived document")
            if not isinstance(source_payload, bytes) or not source_payload:
                raise StoreIntegrityError("case source ciphertext is missing")
            metadata_size = len(self._canonical_json({
                "format_version": 1, "record": record, "saved_at": saved_at,
            }))
            if metadata_size > _MAX_CASE_RECORD_METADATA_BYTES:
                raise StoreIntegrityError("case document metadata exceeds its configured limit")
            actual_metadata_bytes += metadata_size
            actual_bytes += record["source"]["byte_length"]
            ownership[doc_id] = binding["case_owned"]
        if actual_bytes != case.get("retained_source_bytes"):
            raise StoreIntegrityError("case retained-source byte count does not match archived documents")
        if actual_metadata_bytes > _MAX_CASE_TOTAL_METADATA_BYTES:
            raise StoreIntegrityError("case retained metadata exceeds its configured limit")
        return ownership

    def _verify_case_index_integrity(self) -> None:
        try:
            with self._connect() as connection:
                rows = connection.execute("SELECT entry_id, case_id_index, case_payload FROM cases ORDER BY entry_id").fetchall()
                for entry_id, case_index, payload in rows:
                    case = self._decode_case_payload(payload)
                    expected_index = self._case_id_index(case["case_id"])
                    if case_index != expected_index:
                        raise StoreIntegrityError("case ID index failed integrity validation")
                    self._known_case_entries[case_index] = entry_id
                    self._validate_case_references(connection, case, case_index)
        except StoreError:
            raise
        except sqlite3.Error as exc:
            raise StoreIntegrityError("local case indexes could not be verified") from exc

    @classmethod
    def _seal_case(cls, case: dict) -> dict:
        sealed = copy.deepcopy(case)
        sealed["case_revision"] = cls._case_revision(sealed)
        return cls._validate_case(sealed)

    def _get_case_in_connection(self, connection: sqlite3.Connection, case_id: str):
        row = self._case_row_for_id(connection, case_id)
        if row is None:
            return None
        _, case_index, payload = row
        case = self._decode_case_payload(payload)
        if case.get("case_id") != case_id or self._case_id_index(case_id) != case_index:
            raise StoreIntegrityError("case ID index points to a different case")
        self._validate_case_references(connection, case, case_index)
        return case

    @staticmethod
    def case_chunk_digest(source_records: list[dict]) -> str:
        """Return the canonical digest required for an idempotent upload chunk."""
        if not isinstance(source_records, list):
            raise StoreRejected("case source_records must be an array")
        summary = []
        for item in source_records:
            if not isinstance(item, dict) or set(item) != {"record", "source_bytes"}:
                raise StoreRejected("case source record must include record and source_bytes")
            record = item["record"]
            source_bytes = item["source_bytes"]
            document_id, source_hash = LocalDocumentStore._validate_record(record)
            if not isinstance(source_bytes, bytes) or hashlib.sha256(source_bytes).hexdigest() != source_hash:
                raise StoreRejected("case source bytes do not match their record hash")
            record_size = LocalDocumentStore._case_record_metadata_size(record)
            summary.append({
                "document_id": document_id,
                "source_sha256": source_hash,
                "byte_length": len(source_bytes),
                "record_sha256": hashlib.sha256(LocalDocumentStore._canonical_json(record)).hexdigest(),
                "record_payload_size": record_size,
            })
        return hashlib.sha256(LocalDocumentStore._canonical_json(summary)).hexdigest()

    @staticmethod
    def _case_record_metadata_size(record: dict) -> int:
        """Bound the canonical encrypted record envelope, including its archive reference."""
        if not isinstance(record, dict):
            raise StoreRejected("case document record must be an object")
        document_id, _ = LocalDocumentStore._validate_record(record)
        archived_record = copy.deepcopy(record)
        source = archived_record.get("source")
        if not isinstance(source, dict):
            raise StoreRejected("case document source metadata must be an object")
        source["storage_ref"] = f"local-archive://{document_id}"
        envelope = {
            "format_version": 1,
            "record": archived_record,
            "saved_at": "2000-01-01T00:00:00+00:00",
        }
        try:
            size = len(LocalDocumentStore._canonical_json(envelope))
        except (TypeError, ValueError) as exc:
            raise StoreRejected("case document metadata must be finite JSON data") from exc
        if size > _MAX_CASE_RECORD_METADATA_BYTES:
            raise StoreRejected("case document metadata exceeds the 1 MiB metadata limit")
        return size

    def create_case(self, case_manifest: dict, statement_record: dict, source_bytes: bytes) -> dict:
        """Atomically archive the statement, its opaque binding, and the encrypted case manifest."""
        case = copy.deepcopy(case_manifest) if isinstance(case_manifest, dict) else case_manifest
        if not isinstance(case, dict):
            raise StoreRejected("case manifest must be an object")
        case.setdefault("attachments", [])
        case.setdefault("chunks", [])
        case.setdefault("review_events", [])
        case.setdefault("inclusion_events", [])
        case.setdefault("processing", {"state": "not_started", "cursor": None, "result_bytes": 0})
        if case["attachments"]:
            raise StoreRejected("a new case cannot contain attachments before chunk upload")
        document_id, source_hash = self._validate_record(statement_record)
        if statement_record.get("document_family") != "expense_report":
            raise StoreRejected("case statement document must have expense_report family")
        statement_digest = case.get("statement_sha256")
        if (
            case.get("statement_document_id") != document_id
            or not isinstance(statement_digest, str)
            or statement_digest.lower() != source_hash
        ):
            raise StoreRejected("case statement binding does not match the statement record")
        if not isinstance(source_bytes, bytes):
            raise StoreRejected("case statement source_bytes must be bytes")
        if not source_bytes or len(source_bytes) > self._max_document_bytes:
            raise StoreRejected("case statement source is empty or exceeds configured byte limit")
        statement_storage_bytes = len(source_bytes) + self._case_record_metadata_size(statement_record)
        try:
            free_bytes = shutil.disk_usage(self.path.parent).free
        except OSError as exc:
            raise StoreRejected("could not verify free space for the local case statement") from exc
        if free_bytes < 2 * statement_storage_bytes + 64 * 1024 * 1024:
            raise StoreRejected("insufficient free space for a safe local case statement")
        case["retained_source_bytes"] = len(source_bytes)
        case = self._seal_case(case)
        case_index = self._case_id_index(case["case_id"])
        protected_case = self._protect_case_payload(case)
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                if self._case_row_for_id(connection, case["case_id"]) is not None:
                    raise StoreSourceConflict("case ID already exists")
                stored_id, stored_hash, created = self._insert_case_document(connection, statement_record, source_bytes)
                if stored_id != document_id or stored_hash != source_hash:
                    raise StoreIntegrityError("stored statement does not match its case binding")
                case_entry = str(uuid.uuid4())
                connection.execute(
                    "INSERT INTO cases(entry_id, case_id_index, case_payload) VALUES (?, ?, ?)",
                    (case_entry, case_index, protected_case),
                )
                self._insert_case_binding(
                    connection, case_index=case_index, document_id=document_id,
                    source_hash=source_hash, role="expense_statement", case_owned=created,
                )
                self._validate_case_references(connection, case, case_index)
                connection.commit()
                self._known_case_entries[case_index] = case_entry
            return copy.deepcopy(case)
        except StoreError:
            raise
        except sqlite3.Error as exc:
            raise StoreError("could not create local expense case") from exc

    def get_case(self, case_id: str) -> dict | None:
        if not isinstance(case_id, str) or not case_id:
            return None
        try:
            with self._connect() as connection:
                return self._get_case_in_connection(connection, case_id)
        except StoreError:
            raise
        except sqlite3.Error as exc:
            raise StoreError("could not read local expense case") from exc

    def save_case(self, case: dict, *, expected_revision: str | None = None) -> dict:
        """Persist a manifest update with optimistic concurrency and unchanged source refs."""
        if not isinstance(case, dict):
            raise StoreRejected("case manifest must be an object")
        supplied = copy.deepcopy(case)
        case_id = supplied.get("case_id")
        if expected_revision is not None and (
            not isinstance(expected_revision, str) or not _SHA256.fullmatch(expected_revision)
        ):
            raise StoreRejected("expected_revision must be a SHA-256 digest")
        supplied.pop("case_revision", None)
        saved = self._seal_case(supplied)
        case_index = self._case_id_index(saved["case_id"])
        protected = self._protect_case_payload(saved)
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = self._case_row_for_id(connection, case_id)
                if row is None:
                    raise StoreConcurrentUpdate("case no longer exists")
                current = self._decode_case_payload(row[2])
                if expected_revision is not None and current["case_revision"] != expected_revision.lower():
                    raise StoreConcurrentUpdate("case changed since it was read")
                if (
                    supplied.get("statement_document_id") != current["statement_document_id"]
                    or supplied.get("statement_sha256") != current["statement_sha256"]
                    or supplied.get("attachments") != current["attachments"]
                    or supplied.get("chunks") != current["chunks"]
                    or supplied.get("inclusion_events") != current["inclusion_events"]
                    or supplied.get("retained_source_bytes") != current["retained_source_bytes"]
                ):
                    raise StoreRejected("save_case cannot change source membership, upload, or inclusion history")
                prior_reviews = current.get("review_events", [])
                updated_reviews = supplied.get("review_events", [])
                if updated_reviews[:len(prior_reviews)] != prior_reviews or len(updated_reviews) < len(prior_reviews):
                    raise StoreRejected("case review events are append-only")
                self._validate_case_references(connection, saved, case_index)
                connection.execute("UPDATE cases SET case_payload = ? WHERE entry_id = ?", (protected, row[0]))
                connection.commit()
            return copy.deepcopy(saved)
        except StoreError:
            raise
        except sqlite3.Error as exc:
            raise StoreError("could not save local expense case") from exc

    def list_cases(self, query: str = "", *, limit: int = 100) -> list[dict]:
        if not isinstance(query, str):
            raise ValueError("query must be text")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
            raise ValueError("limit must be an integer from 1 to 100")
        needle = query.strip().casefold()
        try:
            matches = []
            with self._connect() as connection:
                rows = connection.execute("SELECT entry_id, case_id_index, case_payload FROM cases ORDER BY entry_id").fetchall()
                for entry_id, case_index, payload in rows:
                    case = self._decode_case_payload(payload)
                    if self._case_id_index(case["case_id"]) != case_index:
                        raise StoreIntegrityError("case ID index failed integrity validation")
                    self._known_case_entries[case_index] = entry_id
                    self._validate_case_references(connection, case, case_index)
                    searchable = f"{case['case_id']} {case.get('status', '')} {case.get('processing', {}).get('state', '')}".casefold()
                    if not needle or needle in searchable:
                        matches.append(case)
                        if len(matches) >= limit:
                            break
            return matches
        except StoreError:
            raise
        except sqlite3.Error as exc:
            raise StoreError("could not list local expense cases") from exc

    def delete_case(self, case_id: str) -> bool:
        if not isinstance(case_id, str) or not case_id:
            return False
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = self._case_row_for_id(connection, case_id)
                if row is None:
                    connection.commit()
                    return False
                case_entry, case_index, payload = row
                case = self._decode_case_payload(payload)
                if case["case_id"] != case_id or self._case_id_index(case_id) != case_index:
                    raise StoreIntegrityError("case ID index points to a different case")
                self._validate_case_references(connection, case, case_index)
                refs = self._manifest_document_refs(case)
                connection.execute("DELETE FROM case_documents WHERE case_id_index = ?", (case_index,))
                connection.execute("DELETE FROM cases WHERE entry_id = ?", (case_entry,))
                for ref in refs:
                    document_index = self._document_id_index(ref["document_id"])
                    retained = connection.execute(
                        "SELECT independently_retained FROM document_retention WHERE document_id_index = ?",
                        (document_index,),
                    ).fetchone()
                    if retained is None:
                        raise StoreIntegrityError("document retention state is missing")
                    still_referenced = connection.execute(
                        "SELECT 1 FROM case_documents WHERE document_id_index = ? LIMIT 1", (document_index,)
                    ).fetchone()
                    if not retained[0] and still_referenced is None:
                        doc_row = connection.execute(
                            "SELECT entry_id, document_id_index, record_payload, source_payload FROM documents WHERE document_id_index = ?",
                            (document_index,),
                        ).fetchone()
                        if doc_row is None:
                            raise StoreIntegrityError("case-owned document disappeared before deletion")
                        entry_id, stored_index, record_payload, source_payload = doc_row
                        record, _ = self._decode_record(record_payload)
                        doc_id, source_hash = self._validate_record(record)
                        if doc_id != ref["document_id"] or source_hash != ref["source_sha256"].lower() or stored_index != document_index:
                            raise StoreIntegrityError("case-owned document binding changed before deletion")
                        self._decode_source(source_payload, expected_hash=source_hash, expected_length=record["source"]["byte_length"])
                        connection.execute("DELETE FROM documents WHERE entry_id = ?", (entry_id,))
                        connection.execute("DELETE FROM document_retention WHERE document_id_index = ?", (document_index,))
                        self._known_index_entries.pop(document_index, None)
                connection.commit()
                self._known_case_entries.pop(case_index, None)
            return True
        except StoreError:
            raise
        except sqlite3.Error as exc:
            raise StoreError("could not delete local expense case") from exc

    def append_case_chunk(
        self, case_id: str, expected_revision: str, chunk_id: str, chunk_digest: str, source_records: list[dict]
    ) -> dict:
        if not isinstance(chunk_id, str) or not _STORE_ID.fullmatch(chunk_id):
            raise StoreRejected("chunk_id must be an opaque identifier")
        if not isinstance(chunk_digest, str) or not _SHA256.fullmatch(chunk_digest):
            raise StoreRejected("chunk_digest must be a SHA-256 digest")
        calculated = self.case_chunk_digest(source_records)
        if calculated != chunk_digest.lower():
            raise StoreRejected("chunk digest does not match the uploaded source records")
        if not source_records or len(source_records) > _MAX_CASE_CHUNK_DOCUMENTS:
            raise StoreRejected("case chunk must contain from 1 to 20 documents")
        if not isinstance(expected_revision, str) or not _SHA256.fullmatch(expected_revision):
            raise StoreRejected("expected_revision must be a SHA-256 digest")
        current_case = self.get_case(case_id)
        if current_case is None:
            raise StoreConcurrentUpdate("case no longer exists")
        prior_chunk = next((item for item in current_case.get("chunks", []) if item.get("chunk_id") == chunk_id), None)
        if prior_chunk is not None:
            if prior_chunk.get("chunk_digest") != calculated:
                raise StoreSourceConflict("chunk ID was already used for different source bytes")
            return current_case
        chunk_source_bytes = sum(len(item["source_bytes"]) for item in source_records)
        chunk_metadata_bytes = sum(self._case_record_metadata_size(item["record"]) for item in source_records)
        chunk_storage_bytes = chunk_source_bytes + chunk_metadata_bytes
        if chunk_storage_bytes > _MAX_CASE_CHUNK_BYTES:
            raise StoreRejected("case chunk exceeds the 100 MiB request limit including metadata")
        try:
            free_bytes = shutil.disk_usage(self.path.parent).free
        except OSError as exc:
            raise StoreRejected("could not verify free space for the local case upload") from exc
        if free_bytes < 2 * chunk_storage_bytes + 64 * 1024 * 1024:
            raise StoreRejected("insufficient free space for a safe local case upload")
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = self._case_row_for_id(connection, case_id)
                if row is None:
                    raise StoreConcurrentUpdate("case no longer exists")
                case_index = row[1]
                case = self._decode_case_payload(row[2])
                self._validate_case_references(connection, case, case_index)
                prior = next((item for item in case.get("chunks", []) if item.get("chunk_id") == chunk_id), None)
                if prior is not None:
                    if prior.get("chunk_digest") != calculated:
                        raise StoreSourceConflict("chunk ID was already used for different source bytes")
                    connection.commit()
                    return copy.deepcopy(case)
                if case["case_revision"] != expected_revision.lower():
                    raise StoreConcurrentUpdate("case changed since it was read")
                existing_ids = {item["document_id"] for item in case["attachments"]}
                source_ids = [self._validate_record(item["record"])[0] for item in source_records]
                if len(source_ids) != len(set(source_ids)) or existing_ids.intersection(source_ids):
                    raise StoreRejected("case chunk document IDs must be unique")
                if any(item["record"].get("document_family") == "expense_report" for item in source_records):
                    raise StoreRejected("supporting documents cannot be another expense statement")
                if len(existing_ids) + len(source_ids) > _MAX_CASE_ATTACHMENTS:
                    raise StoreRejected("case cannot contain more than 100 supporting documents")
                if case.get("retained_source_bytes", 0) + chunk_source_bytes > _MAX_CASE_SOURCE_BYTES:
                    raise StoreRejected("case retained-source byte quota exceeded")
                existing_metadata_bytes = 0
                for ref in self._manifest_document_refs(case):
                    ref_row = self._row_for_document_id(connection, ref["document_id"])
                    if ref_row is None:
                        raise StoreIntegrityError("case references a missing local document")
                    _, _, record_payload, _ = ref_row
                    existing_record, saved_at = self._decode_record(record_payload)
                    existing_metadata_bytes += len(self._canonical_json({
                        "format_version": 1, "record": existing_record, "saved_at": saved_at,
                    }))
                if existing_metadata_bytes + chunk_metadata_bytes > _MAX_CASE_TOTAL_METADATA_BYTES:
                    raise StoreRejected("case retained metadata byte quota exceeded")
                created_docs = []
                for item in source_records:
                    document_id, source_hash, created = self._insert_case_document(
                        connection, item["record"], item["source_bytes"]
                    )
                    created_docs.append((document_id, source_hash, created))
                for document_id, source_hash, created in created_docs:
                    case["attachments"].append({
                        "document_id": document_id, "source_sha256": source_hash,
                        "included": True, "chunk_id": chunk_id,
                    })
                    self._insert_case_binding(
                        connection, case_index=case_index, document_id=document_id,
                        source_hash=source_hash, role="supporting_document", case_owned=created,
                    )
                case["chunks"].append({
                    "chunk_id": chunk_id, "chunk_digest": calculated, "document_ids": source_ids,
                })
                case["retained_source_bytes"] = case.get("retained_source_bytes", 0) + chunk_source_bytes
                if case.get("processing", {}).get("state") not in {None, "not_started"}:
                    case.setdefault("derived_state", {})["status"] = "stale"
                    case["processing"]["state"] = "stale"
                    case["processing"]["cursor"] = None
                saved = self._seal_case(case)
                protected = self._protect_case_payload(saved)
                self._validate_case_references(connection, saved, case_index)
                connection.execute("UPDATE cases SET case_payload = ? WHERE entry_id = ?", (protected, row[0]))
                connection.commit()
                return copy.deepcopy(saved)
        except StoreError:
            raise
        except sqlite3.Error as exc:
            raise StoreError("could not append local expense-case chunk") from exc

    def append_attachment_inclusion_event(
        self, case_id: str, expected_revision: str, document_id: str, source_sha256: str,
        included: bool, reason: str, event_id: str,
    ) -> dict:
        if not isinstance(expected_revision, str) or not _SHA256.fullmatch(expected_revision):
            raise StoreRejected("expected_revision must be a SHA-256 digest")
        if not isinstance(document_id, str) or not _STORE_ID.fullmatch(document_id):
            raise StoreRejected("document_id must be an opaque identifier")
        if not isinstance(source_sha256, str) or not _SHA256.fullmatch(source_sha256):
            raise StoreRejected("source_sha256 must be a SHA-256 digest")
        if type(included) is not bool:
            raise StoreRejected("included must be a boolean")
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
            raise StoreRejected("inclusion change requires a reason of at most 2000 characters")
        if not isinstance(event_id, str) or not _STORE_ID.fullmatch(event_id):
            raise StoreRejected("event_id must be an opaque identifier")
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = self._case_row_for_id(connection, case_id)
                if row is None:
                    raise StoreConcurrentUpdate("case no longer exists")
                case_entry, case_index, payload = row
                case = self._decode_case_payload(payload)
                self._validate_case_references(connection, case, case_index)
                attachment = next((item for item in case["attachments"] if item["document_id"] == document_id), None)
                if attachment is None or attachment["source_sha256"].lower() != source_sha256.lower():
                    raise StoreSourceConflict("attachment source is not bound to this case")
                body = {
                    "event_id": event_id, "case_revision": expected_revision.lower(),
                    "document_id": document_id, "source_sha256": source_sha256.lower(),
                    "included": included, "reason": reason.strip(),
                }
                event_digest = hashlib.sha256(self._canonical_json(body)).hexdigest()
                prior = next((item for item in case["inclusion_events"] if item["event_id"] == event_id), None)
                if prior is not None:
                    if prior["event_sha256"] != event_digest:
                        raise StoreSourceConflict("inclusion event ID was already used for a different action")
                    connection.commit()
                    return copy.deepcopy(case)
                if case["case_revision"] != expected_revision.lower():
                    raise StoreConcurrentUpdate("case changed since it was read")
                if expected_revision.lower() != case["case_revision"]:
                    raise StoreConcurrentUpdate("inclusion event revision is stale")
                attachment["included"] = included
                case["inclusion_events"].append({
                    **body, "sequence": len(case["inclusion_events"]) + 1, "event_sha256": event_digest,
                })
                case.setdefault("derived_state", {})
                case["derived_state"]["status"] = "stale"
                processing = case.setdefault("processing", {})
                processing["state"] = "stale"
                processing["cursor"] = None
                saved = self._seal_case(case)
                protected = self._protect_case_payload(saved)
                connection.execute("UPDATE cases SET case_payload = ? WHERE entry_id = ?", (protected, case_entry))
                connection.commit()
                return copy.deepcopy(saved)
        except StoreError:
            raise
        except sqlite3.Error as exc:
            raise StoreError("could not record case attachment inclusion change") from exc

    def commit_case_processing_chunk(
        self, case_id: str, expected_revision: str, chunk_id: str,
        updated_records: list[dict], next_manifest: dict,
    ) -> dict:
        if not isinstance(chunk_id, str) or not _STORE_ID.fullmatch(chunk_id):
            raise StoreRejected("processing chunk ID must be opaque")
        if not isinstance(expected_revision, str) or not _SHA256.fullmatch(expected_revision):
            raise StoreRejected("expected_revision must be a SHA-256 digest")
        if not isinstance(updated_records, list) or not updated_records:
            raise StoreRejected("processing chunk must contain updated document records")
        if not isinstance(next_manifest, dict):
            raise StoreRejected("next case manifest must be an object")
        record_digests = []
        prepared = []
        for record in updated_records:
            document_id, source_hash = self._validate_record(record)
            payload = self._canonical_json(record)
            record_digest = hashlib.sha256(payload).hexdigest()
            record_digests.append({"document_id": document_id, "source_sha256": source_hash, "record_sha256": record_digest})
            envelope = {
                "format_version": 1,
                "record": copy.deepcopy(record),
                "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            protected = self._protector.protect(self._canonical_json(envelope))
            if not isinstance(protected, bytes) or not protected:
                raise StoreProtectionError("payload protector returned invalid processing output ciphertext")
            prepared.append((document_id, source_hash, protected))
        processing_digest = hashlib.sha256(self._canonical_json(record_digests)).hexdigest()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = self._case_row_for_id(connection, case_id)
                if row is None:
                    raise StoreConcurrentUpdate("case no longer exists")
                case_entry, case_index, payload = row
                current = self._decode_case_payload(payload)
                self._validate_case_references(connection, current, case_index)
                processing = current.setdefault("processing", {})
                committed = processing.setdefault("committed_chunks", [])
                prior = next((item for item in committed if item.get("chunk_id") == chunk_id), None)
                if prior is not None:
                    if prior.get("chunk_digest") != processing_digest:
                        raise StoreSourceConflict("processing chunk ID was reused for different OCR output")
                    connection.commit()
                    return copy.deepcopy(current)
                if current["case_revision"] != expected_revision.lower():
                    raise StoreConcurrentUpdate("case changed since processing started")
                next_case = copy.deepcopy(next_manifest)
                next_case.pop("case_revision", None)
                if next_case.get("case_id") != case_id:
                    raise StoreRejected("processing update cannot change case identity")
                if (
                    next_case.get("statement_document_id") != current.get("statement_document_id")
                    or next_case.get("statement_sha256") != current.get("statement_sha256")
                    or next_case.get("attachments") != current.get("attachments")
                    or next_case.get("chunks") != current.get("chunks")
                    or next_case.get("inclusion_events") != current.get("inclusion_events")
                    or next_case.get("review_events") != current.get("review_events")
                    or next_case.get("retained_source_bytes") != current.get("retained_source_bytes")
                ):
                    raise StoreRejected("processing update cannot change case source references")
                next_processing = next_case.setdefault("processing", {})
                next_committed = next_processing.setdefault("committed_chunks", [])
                if next_committed != committed:
                    raise StoreRejected("processing update must preserve the committed chunk ledger")
                next_committed.append({"chunk_id": chunk_id, "chunk_digest": processing_digest})
                processable_ids = {current["statement_document_id"]} | {
                    item["document_id"] for item in current["attachments"] if item["included"]
                }
                if len({document_id for document_id, _, _ in prepared}) != len(prepared):
                    raise StoreRejected("processing output document IDs must be unique")
                for document_id, source_hash, protected_record in prepared:
                    if document_id not in processable_ids:
                        raise StoreRejected("processing output document is not currently included in this case")
                    doc_row = self._row_for_document_id(connection, document_id)
                    if doc_row is None:
                        raise StoreIntegrityError("processing output document is missing from the archive")
                    entry_id, document_index, _, source_payload = doc_row
                    existing_record, _ = self._decode_record(doc_row[2])
                    existing_hash = existing_record["source"]["sha256"].lower()
                    if existing_hash != source_hash:
                        raise StoreSourceConflict("processing output source hash changed")
                    if existing_record["source"].get("storage_ref") != f"local-archive://{document_id}":
                        raise StoreIntegrityError("processing output has an invalid archive reference")
                    self._decode_source(source_payload, expected_hash=source_hash, expected_length=existing_record["source"]["byte_length"])
                    connection.execute("UPDATE documents SET record_payload = ? WHERE entry_id = ?", (protected_record, entry_id))
                saved = self._seal_case(next_case)
                saved_payload = self._protect_case_payload(saved)
                self._validate_case_references(connection, saved, case_index)
                connection.execute("UPDATE cases SET case_payload = ? WHERE entry_id = ?", (saved_payload, case_entry))
                connection.commit()
                return copy.deepcopy(saved)
        except StoreError:
            raise
        except sqlite3.Error as exc:
            raise StoreError("could not commit local case processing chunk") from exc

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

    def _insert_case_document(self, connection: sqlite3.Connection, record: dict, source_bytes: bytes) -> tuple[str, str, bool]:
        """Insert or verify a source inside the caller's transaction; new records are case-owned."""
        document_id, source_hash = self._validate_record(record)
        if not isinstance(source_bytes, bytes) or not source_bytes:
            raise StoreRejected("case source document must be non-empty bytes")
        if len(source_bytes) > self._max_document_bytes:
            raise StoreRejected("case source document exceeds configured byte limit")
        if record["source"].get("byte_length") != len(source_bytes):
            raise StoreRejected("case source bytes do not match record.source.byte_length")
        if hashlib.sha256(source_bytes).hexdigest() != source_hash:
            raise StoreRejected("case source bytes do not match record.source.sha256")
        archived_record = copy.deepcopy(record)
        archived_record["source"]["storage_ref"] = f"local-archive://{document_id}"
        issues = validate_document_record(archived_record)
        if issues:
            raise StoreRejected("case document record violates contract: " + "; ".join(issues))
        envelope = {
            "format_version": 1,
            "record": archived_record,
            "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        if len(self._canonical_json(envelope)) > _MAX_CASE_RECORD_METADATA_BYTES:
            raise StoreRejected("case document metadata exceeds the 1 MiB metadata limit")
        try:
            record_payload = self._protector.protect(self._canonical_json(envelope))
            source_payload = self._protector.protect(source_bytes)
        except Exception as exc:
            raise StoreProtectionError("could not protect case document payload") from exc
        if not isinstance(record_payload, bytes) or not record_payload or not isinstance(source_payload, bytes) or not source_payload:
            raise StoreProtectionError("payload protector returned invalid case document ciphertext")
        index = self._document_id_index(document_id)
        existing = self._row_for_document_id(connection, document_id)
        if existing is not None:
            entry_id, existing_index, existing_record_payload, existing_source_payload = existing
            old_record, _ = self._decode_record(existing_record_payload)
            if old_record["document_id"] != document_id or existing_index != index:
                raise StoreIntegrityError("document ID index points to a different record")
            if old_record["source"]["sha256"].lower() != source_hash or self._decode_source(
                existing_source_payload,
                expected_hash=source_hash,
                expected_length=old_record["source"]["byte_length"],
            ) != source_bytes:
                raise StoreSourceConflict("document ID already belongs to different source bytes")
            if connection.execute(
                "SELECT 1 FROM document_retention WHERE document_id_index = ?", (index,)
            ).fetchone() is None:
                raise StoreIntegrityError("document retention state is missing")
            return document_id, source_hash, False
        entry_id = str(uuid.uuid4())
        connection.execute(
            "INSERT INTO documents(entry_id, document_id_index, record_payload, source_payload) VALUES (?, ?, ?, ?)",
            (entry_id, index, record_payload, source_payload),
        )
        connection.execute(
            "INSERT INTO document_retention(document_id_index, independently_retained) VALUES (?, 0)",
            (index,),
        )
        self._known_index_entries[index] = entry_id
        return document_id, source_hash, True

    def _insert_case_binding(
        self, connection: sqlite3.Connection, *, case_index: str, document_id: str,
        source_hash: str, role: str, case_owned: bool,
    ) -> None:
        if role not in {"expense_statement", "supporting_document"}:
            raise StoreRejected("unsupported case-document role")
        document_index = self._document_id_index(document_id)
        connection.execute(
            "INSERT INTO case_documents(entry_id, case_id_index, document_id_index, binding_payload) VALUES (?, ?, ?, ?)",
            (
                str(uuid.uuid4()), case_index, document_index,
                self._protect_case_reference(source_hash=source_hash, role=role, case_owned=case_owned),
            ),
        )

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
                connection.execute(
                    "INSERT INTO document_retention(document_id_index, independently_retained) VALUES (?, 1) "
                    "ON CONFLICT(document_id_index) DO UPDATE SET independently_retained = 1",
                    (index,),
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
                if connection.execute(
                    "SELECT 1 FROM case_documents WHERE document_id_index = ? LIMIT 1", (index,)
                ).fetchone():
                    raise StoreRejected("document is bound to an active case; delete the case explicitly")
                row = self._row_for_document_id(connection, document_id)
                if row is None:
                    connection.commit()
                    return False
                entry_id, document_id_index, protected_record, _ = row
                record, _ = self._decode_record(protected_record)
                if record["document_id"] != document_id or self._document_id_index(document_id) != document_id_index:
                    raise StoreIntegrityError("document ID index points to a different record")
                connection.execute("DELETE FROM documents WHERE entry_id = ?", (entry_id,))
                connection.execute("DELETE FROM document_retention WHERE document_id_index = ?", (index,))
                self._known_index_entries.pop(index, None)
                connection.commit()
            return True
        except StoreError:
            raise
        except sqlite3.Error as exc:
            raise StoreError("could not delete local document") from exc
