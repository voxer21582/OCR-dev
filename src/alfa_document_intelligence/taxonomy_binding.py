"""Canonical, self-contained taxonomy snapshots for persisted document cases."""
from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Mapping

from .taxonomy_registry import (
    CATALOG_SCHEMA_VERSION,
    CATALOG_SCHEMA_VERSION_V2,
    MAX_CATALOG_BYTES,
    TaxonomyError,
    validate_catalog,
)


BINDING_SCHEMA_VERSION = "1.0.0"
DOCUMENT_SCHEMA_VERSION = "0.2.0"
DOCUMENT_SCHEMA_VERSION_V3 = "0.3.0"
_SUPPORTED_CATALOG_SCHEMA_VERSIONS = frozenset({
    CATALOG_SCHEMA_VERSION,
    CATALOG_SCHEMA_VERSION_V2,
})
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_BINDING_KEYS = {
    "schema_version", "catalog_schema_version", "catalog_version", "catalog_sha256", "snapshot",
}


class TaxonomyBindingError(ValueError):
    """Stable, sanitized per-case taxonomy binding failure."""

    def __init__(self, code: str = "taxonomy_binding_invalid") -> None:
        self.code = code
        super().__init__(code)


def _validated_snapshot(catalog: Any, digest: Any) -> tuple[dict[str, Any], str]:
    if type(catalog) is not dict or type(digest) is not str or not _SHA256.fullmatch(digest):
        raise TaxonomyBindingError()
    try:
        canonical, actual = validate_catalog(catalog)
    except (TaxonomyError, TypeError, ValueError) as error:
        raise TaxonomyBindingError() from error
    if len(canonical.encode("utf-8")) > MAX_CATALOG_BYTES:
        raise TaxonomyBindingError("taxonomy_binding_too_large")
    if actual != digest:
        raise TaxonomyBindingError("taxonomy_binding_hash_mismatch")
    return deepcopy(catalog), actual


def create_taxonomy_binding(catalog: Mapping[str, Any], digest: str) -> dict[str, Any]:
    """Build an immutable-by-convention exact catalog copy with its verified identity."""
    if not isinstance(catalog, Mapping):
        raise TaxonomyBindingError()
    try:
        source = deepcopy(dict(catalog))
    except (TypeError, ValueError) as error:
        raise TaxonomyBindingError() from error
    snapshot, actual = _validated_snapshot(source, digest)
    return {
        "schema_version": BINDING_SCHEMA_VERSION,
        "catalog_schema_version": snapshot["schema_version"],
        "catalog_version": snapshot["version"],
        "catalog_sha256": actual,
        "snapshot": snapshot,
    }


def validate_taxonomy_binding(binding: Any) -> tuple[dict[str, Any], str]:
    """Return a defensive snapshot and canonical digest after strict validation."""
    if type(binding) is not dict or set(binding) != _BINDING_KEYS:
        raise TaxonomyBindingError()
    catalog_schema_version = binding.get("catalog_schema_version")
    if (binding.get("schema_version") != BINDING_SCHEMA_VERSION
            or type(catalog_schema_version) is not str
            or catalog_schema_version not in _SUPPORTED_CATALOG_SCHEMA_VERSIONS
            or type(binding.get("catalog_version")) is not int
            or not isinstance(binding.get("snapshot"), dict)):
        raise TaxonomyBindingError()
    snapshot, digest = _validated_snapshot(binding["snapshot"], binding.get("catalog_sha256"))
    if (binding["catalog_version"] != snapshot.get("version")
            or catalog_schema_version != snapshot.get("schema_version")):
        raise TaxonomyBindingError("taxonomy_binding_version_mismatch")
    return snapshot, digest


def bind_document_record(record: Mapping[str, Any], binding: Mapping[str, Any]) -> dict[str, Any]:
    """Return a bound document copy using the catalog generation's document schema."""
    record_schema_version = record.get("schema_version") if isinstance(record, Mapping) else None
    if (not isinstance(record, Mapping) or not isinstance(record_schema_version, str)
            or record_schema_version not in {"0.1.0", DOCUMENT_SCHEMA_VERSION}):
        raise TaxonomyBindingError()
    snapshot, digest = validate_taxonomy_binding(dict(binding))
    result = deepcopy(dict(record))
    result["schema_version"] = (
        DOCUMENT_SCHEMA_VERSION if snapshot["schema_version"] == CATALOG_SCHEMA_VERSION
        else DOCUMENT_SCHEMA_VERSION_V3
    )
    result["taxonomy_binding"] = {
        "schema_version": BINDING_SCHEMA_VERSION,
        "catalog_schema_version": snapshot["schema_version"],
        "catalog_version": snapshot["version"],
        "catalog_sha256": digest,
        "snapshot": snapshot,
    }
    return result


__all__ = [
    "BINDING_SCHEMA_VERSION", "DOCUMENT_SCHEMA_VERSION", "DOCUMENT_SCHEMA_VERSION_V3",
    "TaxonomyBindingError",
    "bind_document_record", "create_taxonomy_binding", "validate_taxonomy_binding",
]
