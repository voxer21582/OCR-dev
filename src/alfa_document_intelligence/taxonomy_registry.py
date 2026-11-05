"""Bounded, versioned metadata catalog isolated from document records and OCR."""
from __future__ import annotations

from contextlib import closing
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Any

from jsonschema import Draft202012Validator


CATALOG_SCHEMA_VERSION = "1.0.0"
CATALOG_SCHEMA_VERSION_V2 = "2.0.0"
CATALOG_DB_SCHEMA_VERSION = "1"
MAX_CATALOG_BYTES = 64 * 1024
MAX_TYPES = 64
MAX_FIELDS_PER_TYPE = 128
MAX_LABEL_LENGTH = 80
MAX_ID_LENGTH = 64
MAX_CATALOG_VERSION = 2**31 - 1
DATABASE_NAME = "taxonomy.sqlite3"
_ID = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_VALUE_KINDS = {"text", "identifier", "date", "money", "currency", "percentage", "boolean"}


class TaxonomyError(ValueError):
    """Stable, non-sensitive taxonomy validation or persistence failure."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class TaxonomyConflict(TaxonomyError):
    """The catalog changed after the editor loaded its expected version."""


def _field(field_id: str, label: str, value_kind: str = "text") -> dict[str, Any]:
    return {
        "id": field_id,
        "label": label,
        "value_kind": value_kind,
        "required": False,
        "review_only": False,
        "extraction_mode": "built_in",
    }


_BUILTIN_TYPES: tuple[dict[str, Any], ...] = (
    {"id": "invoice", "label": "Fattura", "role": "document_family", "fields": (
        _field("supplier_name", "Fornitore"), _field("merchant_name", "Esercente"),
        _field("issue_date", "Data documento", "date"), _field("document_number", "Numero documento", "identifier"),
        _field("total_amount", "Totale", "money"), _field("currency", "Valuta", "currency"),
        _field("vat_amount", "IVA", "money"), _field("taxable_base", "Imponibile", "money"),
        _field("vat_rate", "Aliquota IVA", "percentage"),
    )},
    {"id": "expense_report", "label": "Nota spese", "role": "expense_report", "fields": (
        _field("traveler_name", "Viaggiatore"), _field("trip_destination", "Destinazione"),
        _field("trip_purpose", "Motivo trasferta"), _field("trip_start_date", "Inizio trasferta", "date"),
        _field("trip_end_date", "Fine trasferta", "date"),
    )},
    {"id": "fiscal_receipt", "label": "Documento commerciale", "role": "document_family", "fields": (
        _field("merchant_name", "Esercente"), _field("issue_date", "Data documento", "date"),
        _field("total_amount", "Totale", "money"), _field("currency", "Valuta", "currency"),
        _field("vat_amount", "IVA", "money"), _field("vat_rate", "Aliquota IVA", "percentage"),
    )},
    {"id": "parking_receipt", "label": "Ricevuta parcheggio", "role": "document_family", "fields": (
        _field("merchant_name", "Esercente"), _field("issue_date", "Data documento", "date"),
        _field("total_amount", "Totale", "money"), _field("currency", "Valuta", "currency"),
    )},
    {"id": "hotel_document", "label": "Documento hotel", "role": "document_family", "fields": (
        _field("supplier_name", "Struttura"), _field("issue_date", "Data documento", "date"),
        _field("check_in_date", "Check-in", "date"), _field("check_out_date", "Check-out", "date"),
        _field("total_amount", "Totale", "money"), _field("currency", "Valuta", "currency"),
    )},
    {"id": "pos_slip", "label": "POS — prova di pagamento", "role": "payment_evidence", "fields": (
        _field("merchant_name", "Esercente"), _field("issue_date", "Data pagamento", "date"),
        _field("total_amount", "Importo pagamento", "money"), _field("currency", "Valuta", "currency"),
        _field("payment_method", "Metodo pagamento"), _field("payment_reference", "Riferimento pagamento", "identifier"),
    )},
    {"id": "other", "label": "Altro documento", "role": "other", "fields": (
        _field("merchant_name", "Esercente"), _field("issue_date", "Data documento", "date"),
        _field("description", "Descrizione"),
    )},
    {"id": "unknown", "label": "Da classificare", "role": "unknown", "fields": ()},
)
_BUILTIN_BY_ID = {item["id"]: item for item in _BUILTIN_TYPES}
_BUILTIN_TYPES_V2 = []
for _builtin_type in _BUILTIN_TYPES:
    _v2_type = deepcopy(_builtin_type)
    if _v2_type["id"] == "invoice":
        _v2_type["fields"] = (*_v2_type["fields"], _field("invoice_subtotal", "Subtotale", "money"))
    _BUILTIN_TYPES_V2.append(_v2_type)
_BUILTIN_TYPES_V2 = tuple(_BUILTIN_TYPES_V2)
_BUILTIN_BY_ID_V2 = {item["id"]: item for item in _BUILTIN_TYPES_V2}
_SCHEMA_PATHS = {
    CATALOG_SCHEMA_VERSION: Path(__file__).with_name("schemas") / "taxonomy_catalog_v1.schema.json",
    CATALOG_SCHEMA_VERSION_V2: Path(__file__).with_name("schemas") / "taxonomy_catalog_v2.schema.json",
}


def _schema_validator(schema_version: str = CATALOG_SCHEMA_VERSION) -> Draft202012Validator:
    schema_path = _SCHEMA_PATHS.get(schema_version) if isinstance(schema_version, str) else None
    if schema_path is None:
        raise TaxonomyError("taxonomy_schema_unsupported")
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise TaxonomyError("taxonomy_schema_unavailable") from error


def canonical_json(document: dict[str, Any]) -> str:
    try:
        encoded = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, UnicodeError, RecursionError) as error:
        raise TaxonomyError("taxonomy_json_invalid") from error
    if len(encoded.encode("utf-8")) > MAX_CATALOG_BYTES:
        raise TaxonomyError("taxonomy_catalog_too_large")
    return encoded


def catalog_sha256(document: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(document).encode("utf-8")).hexdigest()


def default_catalog() -> dict[str, Any]:
    return {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "version": 1,
        "types": [
            {
                "id": item["id"], "label": item["label"], "enabled": True,
                "role": item["role"], "extraction_mode": "built_in",
                "fields": deepcopy(list(item["fields"])),
            }
            for item in _BUILTIN_TYPES
        ],
    }


def default_catalog_v2() -> dict[str, Any]:
    """Return the v2 vocabulary without changing the v1-compatible default."""
    return {
        "schema_version": CATALOG_SCHEMA_VERSION_V2,
        "version": 1,
        "types": [
            {
                "id": item["id"], "label": item["label"], "enabled": True,
                "role": item["role"], "extraction_mode": "built_in",
                "fields": deepcopy(list(item["fields"])),
            }
            for item in _BUILTIN_TYPES_V2
        ],
    }


def _validate_identity(document: dict[str, Any], schema_version: str) -> None:
    builtin_by_id = (_BUILTIN_BY_ID_V2 if schema_version == CATALOG_SCHEMA_VERSION_V2
                     else _BUILTIN_BY_ID)
    entries = document["types"]
    by_id: dict[str, dict[str, Any]] = {}
    for item in entries:
        identifier = item["id"]
        if identifier in by_id:
            raise TaxonomyError("taxonomy_duplicate_type_id")
        by_id[identifier] = item
    if not set(builtin_by_id) <= set(by_id):
        raise TaxonomyError("taxonomy_builtin_type_missing")
    for type_id, base in builtin_by_id.items():
        item = by_id[type_id]
        if (item["role"] != base["role"] or item["extraction_mode"] != "built_in"
                or (type_id == "pos_slip" and item["label"] != base["label"])):
            raise TaxonomyError("taxonomy_builtin_identity_changed")
        item_fields = {field["id"]: field for field in item["fields"]}
        if len(item_fields) != len(item["fields"]):
            raise TaxonomyError("taxonomy_duplicate_field_id")
        base_fields = {field["id"]: field for field in base["fields"]}
        if not set(base_fields) <= set(item_fields):
            raise TaxonomyError("taxonomy_builtin_field_missing")
        for field_id, base_field in base_fields.items():
            current = item_fields[field_id]
            for invariant in ("value_kind", "review_only", "extraction_mode", "label"):
                if current[invariant] != base_field[invariant]:
                    raise TaxonomyError("taxonomy_builtin_field_changed")
        for field_id, current in item_fields.items():
            if field_id not in base_fields and not _is_manual_field(current):
                raise TaxonomyError("taxonomy_custom_field_not_manual")

    for item in entries:
        if item["id"] in builtin_by_id:
            continue
        if (not item["id"].startswith("custom_") or item["role"] != "custom_manual"
                or item["extraction_mode"] != "manual_only"):
            raise TaxonomyError("taxonomy_custom_type_not_manual")
        field_ids: set[str] = set()
        if not item["fields"]:
            raise TaxonomyError("taxonomy_custom_type_requires_field")
        for field in item["fields"]:
            if field["id"] in field_ids:
                raise TaxonomyError("taxonomy_duplicate_field_id")
            field_ids.add(field["id"])
            if not _is_manual_field(field):
                raise TaxonomyError("taxonomy_custom_field_not_manual")


def _is_manual_field(field: dict[str, Any]) -> bool:
    return (field["id"].startswith("custom_") and field["extraction_mode"] == "manual_only"
            and field["review_only"] is True)


def validate_catalog(document: Any) -> tuple[str, str]:
    if type(document) is not dict:
        raise TaxonomyError("taxonomy_catalog_invalid")
    canonical = canonical_json(document)
    schema_version = document.get("schema_version")
    errors = list(_schema_validator(schema_version).iter_errors(document))
    if errors:
        raise TaxonomyError("taxonomy_catalog_invalid")
    if len(document["types"]) > MAX_TYPES:
        raise TaxonomyError("taxonomy_catalog_invalid")
    for item in document["types"]:
        if len(item["fields"]) > MAX_FIELDS_PER_TYPE:
            raise TaxonomyError("taxonomy_catalog_invalid")
        if len(item["id"]) > MAX_ID_LENGTH or not _ID.fullmatch(item["id"]):
            raise TaxonomyError("taxonomy_catalog_invalid")
        for field in item["fields"]:
            if len(field["id"]) > MAX_ID_LENGTH or not _ID.fullmatch(field["id"]):
                raise TaxonomyError("taxonomy_catalog_invalid")
    _validate_identity(document, schema_version)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return canonical, digest


def parse_catalog_json(raw: str | bytes) -> dict[str, Any]:
    if isinstance(raw, str):
        try:
            payload = raw.encode("utf-8")
        except UnicodeError as error:
            raise TaxonomyError("taxonomy_catalog_invalid") from error
    elif type(raw) is bytes:
        payload = raw
    else:
        raise TaxonomyError("taxonomy_catalog_invalid")
    if len(payload) > MAX_CATALOG_BYTES:
        raise TaxonomyError("taxonomy_catalog_too_large")
    try:
        result = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise TaxonomyError("taxonomy_catalog_invalid") from error
    validate_catalog(result)
    return result


def is_manual_only_type(item: Any) -> bool:
    return (isinstance(item, dict) and item.get("role") == "custom_manual"
            and item.get("extraction_mode") == "manual_only")


class TaxonomyStore:
    """Separate SQLite catalog. It never opens or mutates the document database."""

    def __init__(
        self, library_root: str | os.PathLike[str], *, initial_generation: str = CATALOG_SCHEMA_VERSION,
    ) -> None:
        if not isinstance(initial_generation, str) or initial_generation not in (
            CATALOG_SCHEMA_VERSION, CATALOG_SCHEMA_VERSION_V2,
        ):
            raise TaxonomyError("taxonomy_schema_unsupported")
        self._initial_generation = initial_generation
        try:
            root = Path(library_root).expanduser().resolve()
            if not root.is_dir():
                raise TaxonomyError("taxonomy_root_unavailable")
            self._database_path = root / DATABASE_NAME
            self._initialize()
        except TaxonomyError:
            raise
        except (OSError, RuntimeError, ValueError) as error:
            raise TaxonomyError("taxonomy_root_unavailable") from error

    def _connect(self) -> sqlite3.Connection:
        try:
            connection = sqlite3.connect(self._database_path, timeout=5.0, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA busy_timeout=5000")
            return connection
        except sqlite3.DatabaseError as error:
            raise TaxonomyError("taxonomy_store_unavailable") from error

    @staticmethod
    def _tables(connection: sqlite3.Connection) -> set[str]:
        return {row["name"] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )}

    def _initialize(self) -> None:
        existed = self._database_path.exists()
        try:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                tables = self._tables(connection)
                expected = {"taxonomy_metadata", "taxonomy_versions"}
                if not tables and not existed:
                    connection.execute("CREATE TABLE taxonomy_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                    connection.execute(
                        "CREATE TABLE taxonomy_versions (version INTEGER PRIMARY KEY, catalog_json TEXT NOT NULL, catalog_sha256 TEXT NOT NULL)"
                    )
                    connection.execute("INSERT INTO taxonomy_metadata(key,value) VALUES('schema_version',?)",
                                       (CATALOG_DB_SCHEMA_VERSION,))
                    document = (default_catalog_v2() if self._initial_generation == CATALOG_SCHEMA_VERSION_V2
                                else default_catalog())
                    canonical, digest = validate_catalog(document)
                    connection.execute("INSERT INTO taxonomy_versions VALUES(?,?,?)",
                                       (1, canonical, digest))
                    connection.execute("INSERT INTO taxonomy_metadata(key,value) VALUES('current_version','1')")
                    connection.execute("COMMIT")
                    return
                if tables != expected:
                    raise TaxonomyError("taxonomy_store_corrupt")
                metadata = {row["key"]: row["value"] for row in connection.execute(
                    "SELECT key,value FROM taxonomy_metadata"
                )}
                if metadata.get("schema_version") != CATALOG_DB_SCHEMA_VERSION:
                    raise TaxonomyError("taxonomy_store_unsupported")
                current_raw = metadata.get("current_version")
                if (not isinstance(current_raw, str) or not current_raw.isascii() or not current_raw.isdecimal()
                        or len(current_raw) > len(str(MAX_CATALOG_VERSION))):
                    raise TaxonomyError("taxonomy_store_corrupt")
                current_version = int(current_raw)
                if not 1 <= current_version <= MAX_CATALOG_VERSION:
                    raise TaxonomyError("taxonomy_store_corrupt")
                rows = list(connection.execute(
                    "SELECT version,catalog_json,catalog_sha256 FROM taxonomy_versions ORDER BY version"
                ))
                if not rows or len(rows) != current_version:
                    raise TaxonomyError("taxonomy_store_corrupt")
                for expected_version, row in enumerate(rows, start=1):
                    if row["version"] != expected_version:
                        raise TaxonomyError("taxonomy_store_corrupt")
                    self._decode_row(row)
                connection.execute("COMMIT")
        except TaxonomyError:
            self._rollback_if_open()
            raise
        except sqlite3.DatabaseError as error:
            self._rollback_if_open()
            raise TaxonomyError("taxonomy_store_corrupt") from error

    def _rollback_if_open(self) -> None:
        try:
            with closing(self._connect()) as connection:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
        except (TaxonomyError, sqlite3.DatabaseError):
            pass

    @staticmethod
    def _decode_row(row: sqlite3.Row) -> tuple[dict[str, Any], str]:
        try:
            document = json.loads(row["catalog_json"])
            canonical, digest = validate_catalog(document)
            if (document["version"] != row["version"] or canonical != row["catalog_json"]
                    or digest != row["catalog_sha256"]):
                raise TaxonomyError("taxonomy_catalog_corrupt")
            return document, digest
        except TaxonomyError:
            raise
        except Exception as error:
            raise TaxonomyError("taxonomy_catalog_corrupt") from error

    def get_current(self) -> tuple[dict[str, Any], str]:
        try:
            with closing(self._connect()) as connection:
                row = connection.execute(
                    "SELECT v.version,v.catalog_json,v.catalog_sha256 FROM taxonomy_versions v "
                    "JOIN taxonomy_metadata m ON m.key='current_version' AND m.value=CAST(v.version AS TEXT)"
                ).fetchone()
                if row is None:
                    raise TaxonomyError("taxonomy_store_corrupt")
                document, digest = self._decode_row(row)
                return deepcopy(document), digest
        except TaxonomyError:
            raise
        except sqlite3.DatabaseError as error:
            raise TaxonomyError("taxonomy_store_corrupt") from error

    def get_version(self, version: int) -> tuple[dict[str, Any], str] | None:
        if type(version) is not int or not 1 <= version <= MAX_CATALOG_VERSION:
            raise TaxonomyError("taxonomy_version_invalid")
        try:
            with closing(self._connect()) as connection:
                row = connection.execute(
                    "SELECT version,catalog_json,catalog_sha256 FROM taxonomy_versions WHERE version=?",
                    (version,),
                ).fetchone()
                if row is None:
                    return None
                document, digest = self._decode_row(row)
                return deepcopy(document), digest
        except TaxonomyError:
            raise
        except sqlite3.DatabaseError as error:
            raise TaxonomyError("taxonomy_store_corrupt") from error

    def _before_commit(self) -> None:
        """Narrow failure seam used to verify transaction rollback with synthetic tests."""

    @staticmethod
    def _validate_custom_history(previous: dict[str, Any], candidate: dict[str, Any]) -> None:
        current_types = {item["id"]: item for item in candidate["types"]}
        for old_type in previous["types"]:
            type_id = old_type["id"]
            if type_id.startswith("custom_"):
                new_type = current_types.get(type_id)
                if new_type is None or any(
                    new_type.get(key) != old_type.get(key)
                    for key in ("role", "extraction_mode")
                ):
                    raise TaxonomyError("taxonomy_custom_identity_reused")
                fields = {item["id"]: item for item in new_type["fields"]}
                for old_field in old_type["fields"]:
                    new_field = fields.get(old_field["id"])
                    if new_field is None or any(
                        new_field.get(key) != old_field.get(key)
                        for key in ("value_kind", "review_only", "extraction_mode")
                    ):
                        raise TaxonomyError("taxonomy_custom_field_identity_reused")
            old_fields = {field["id"]: field for field in old_type["fields"]}
            new_type = current_types.get(type_id)
            if new_type is None:
                raise TaxonomyError("taxonomy_builtin_identity_changed")
            new_fields = {field["id"]: field for field in new_type["fields"]}
            for old_field_id, old_field in old_fields.items():
                if old_field_id.startswith("custom_"):
                    new_field = new_fields.get(old_field_id)
                    if new_field is None or any(
                        new_field.get(key) != old_field.get(key)
                        for key in ("value_kind", "review_only", "extraction_mode")
                    ):
                        raise TaxonomyError("taxonomy_custom_field_identity_reused")

    def save_catalog(
        self, document: Any, *, expected_version: int, expected_sha256: str
    ) -> tuple[dict[str, Any], str]:
        if (type(expected_version) is not int or not 1 <= expected_version < MAX_CATALOG_VERSION
                or type(expected_sha256) is not str or not _SHA256.fullmatch(expected_sha256)):
            raise TaxonomyError("taxonomy_precondition_invalid")
        canonical, digest = validate_catalog(document)
        if document["version"] != expected_version + 1:
            raise TaxonomyError("taxonomy_version_invalid")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            metadata = {row["key"]: row["value"] for row in connection.execute(
                "SELECT key,value FROM taxonomy_metadata"
            )}
            if metadata.get("schema_version") != CATALOG_DB_SCHEMA_VERSION:
                raise TaxonomyError("taxonomy_store_unsupported")
            current_raw = metadata.get("current_version", "")
            if current_raw != str(expected_version):
                raise TaxonomyConflict("taxonomy_version_conflict")
            current_row = connection.execute(
                "SELECT version,catalog_json,catalog_sha256 FROM taxonomy_versions WHERE version=?",
                (expected_version,),
            ).fetchone()
            if current_row is None:
                raise TaxonomyError("taxonomy_store_corrupt")
            previous, previous_hash = self._decode_row(current_row)
            if previous_hash != expected_sha256:
                raise TaxonomyConflict("taxonomy_version_conflict")
            if previous["schema_version"] != document["schema_version"]:
                raise TaxonomyError("taxonomy_generation_change_requires_upgrade")
            self._validate_custom_history(previous, document)
            connection.execute("INSERT INTO taxonomy_versions(version,catalog_json,catalog_sha256) VALUES(?,?,?)",
                               (document["version"], canonical, digest))
            connection.execute("UPDATE taxonomy_metadata SET value=? WHERE key='current_version'",
                               (str(document["version"]),))
            self._before_commit()
            connection.execute("COMMIT")
            return deepcopy(document), digest
        except TaxonomyError:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        except sqlite3.DatabaseError as error:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise TaxonomyError("taxonomy_store_write_failed") from error
        except Exception as error:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise TaxonomyError("taxonomy_store_write_failed") from error
        finally:
            connection.close()

    def upgrade_to_v2(
        self, *, expected_version: int, expected_sha256: str,
    ) -> tuple[dict[str, Any], str]:
        """Append the v2 invoice field while preserving the current v1 revision."""
        if (type(expected_version) is not int or not 1 <= expected_version < MAX_CATALOG_VERSION
                or type(expected_sha256) is not str or not _SHA256.fullmatch(expected_sha256)):
            raise TaxonomyError("taxonomy_precondition_invalid")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            metadata = {row["key"]: row["value"] for row in connection.execute(
                "SELECT key,value FROM taxonomy_metadata"
            )}
            if metadata.get("schema_version") != CATALOG_DB_SCHEMA_VERSION:
                raise TaxonomyError("taxonomy_store_unsupported")
            current_raw = metadata.get("current_version")
            if current_raw is None:
                raise TaxonomyError("taxonomy_store_corrupt")
            if current_raw != str(expected_version):
                raise TaxonomyConflict("taxonomy_version_conflict")
            current_row = connection.execute(
                "SELECT version,catalog_json,catalog_sha256 FROM taxonomy_versions WHERE version=?",
                (expected_version,),
            ).fetchone()
            if current_row is None:
                raise TaxonomyError("taxonomy_store_corrupt")
            previous, previous_hash = self._decode_row(current_row)
            if previous_hash != expected_sha256:
                raise TaxonomyConflict("taxonomy_version_conflict")
            if previous["schema_version"] != CATALOG_SCHEMA_VERSION:
                raise TaxonomyError("taxonomy_upgrade_not_applicable")

            upgraded = deepcopy(previous)
            upgraded["schema_version"] = CATALOG_SCHEMA_VERSION_V2
            upgraded["version"] = expected_version + 1
            invoice = next((item for item in upgraded["types"] if item["id"] == "invoice"), None)
            if invoice is None:
                raise TaxonomyError("taxonomy_builtin_type_missing")
            if any(field["id"] == "invoice_subtotal" for field in invoice["fields"]):
                raise TaxonomyError("taxonomy_builtin_identity_changed")
            v2_invoice = _BUILTIN_BY_ID_V2["invoice"]
            subtotal = deepcopy(next(
                field for field in v2_invoice["fields"] if field["id"] == "invoice_subtotal"
            ))
            invoice["fields"].append(subtotal)
            self._validate_custom_history(previous, upgraded)
            canonical, digest = validate_catalog(upgraded)
            connection.execute(
                "INSERT INTO taxonomy_versions(version,catalog_json,catalog_sha256) VALUES(?,?,?)",
                (upgraded["version"], canonical, digest),
            )
            connection.execute("UPDATE taxonomy_metadata SET value=? WHERE key='current_version'",
                               (str(upgraded["version"]),))
            self._before_commit()
            connection.execute("COMMIT")
            return deepcopy(upgraded), digest
        except TaxonomyError:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        except sqlite3.DatabaseError as error:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise TaxonomyError("taxonomy_store_write_failed") from error
        except Exception as error:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise TaxonomyError("taxonomy_store_write_failed") from error
        finally:
            connection.close()
