"""Registry of export formats declared by manifest modules (REQ-090).

Every module in ``alfa_document_intelligence.exporters`` defines ``MANIFEST``,
an :class:`ExporterManifest`. Adding a format means adding one such module;
routes and download links are built from the registry, so nothing else changes.
"""
from __future__ import annotations

from dataclasses import dataclass
import importlib
import pkgutil
import re
from typing import Any, Callable

DEFAULT_PACKAGE = "alfa_document_intelligence.exporters"
_EXPORTER_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_SUFFIX = re.compile(r"^[a-z0-9]{1,8}$")
_REFERENCE = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*:[A-Za-z_]\w*$")


class ExporterRegistryError(ValueError):
    """A manifest is invalid or a format is unknown. ``code`` is stable and non-sensitive."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ExporterManifest:
    """One export format: what it applies to, how it is downloaded, which function writes it.

    ``applies_to`` is ``"document"`` (the function takes the archived record) or
    ``"case"`` (the function takes the case id and its reconciliation).
    """

    exporter_id: str
    label_it: str
    applies_to: str
    media_type: str
    suffix: str
    function_ref: str
    selectable: bool = True


def _valid(manifest: object) -> bool:
    return (
        isinstance(manifest, ExporterManifest)
        and isinstance(manifest.exporter_id, str) and bool(_EXPORTER_ID.fullmatch(manifest.exporter_id))
        and isinstance(manifest.label_it, str) and bool(manifest.label_it.strip())
        and manifest.applies_to in ("document", "case")
        and isinstance(manifest.media_type, str) and manifest.media_type.endswith("; charset=utf-8")
        and isinstance(manifest.suffix, str) and bool(_SUFFIX.fullmatch(manifest.suffix))
        and isinstance(manifest.function_ref, str) and bool(_REFERENCE.fullmatch(manifest.function_ref))
        and isinstance(manifest.selectable, bool)
    )


def discover_exporters(package: str = DEFAULT_PACKAGE) -> dict[str, ExporterManifest]:
    """Import every manifest module of ``package`` and return manifests by exporter id."""
    root = importlib.import_module(package)
    exporters: dict[str, ExporterManifest] = {}
    offered: set[tuple[str, str]] = set()
    for module_info in sorted(pkgutil.iter_modules(root.__path__), key=lambda item: item.name):
        if module_info.ispkg or module_info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{package}.{module_info.name}")
        manifest = getattr(module, "MANIFEST", None)
        if not _valid(manifest):
            raise ExporterRegistryError("manifest_invalid")
        if manifest.exporter_id in exporters:
            raise ExporterRegistryError("exporter_id_duplicate")
        if manifest.selectable:
            key = (manifest.applies_to, manifest.suffix)
            if key in offered:
                raise ExporterRegistryError("suffix_duplicate")
            offered.add(key)
        exporters[manifest.exporter_id] = manifest
    return exporters


def _selectable(applies_to: str, package: str) -> list[ExporterManifest]:
    return sorted(
        (item for item in discover_exporters(package).values() if item.applies_to == applies_to and item.selectable),
        key=lambda item: item.exporter_id,
    )


def selectable_document_exporters(package: str = DEFAULT_PACKAGE) -> list[ExporterManifest]:
    """Formats offered for one archived document, ordered by id."""
    return _selectable("document", package)


def selectable_case_exporters(package: str = DEFAULT_PACKAGE) -> list[ExporterManifest]:
    """Formats offered for an expense case, ordered by id."""
    return _selectable("case", package)


def _function(manifest: ExporterManifest) -> Callable[..., str]:
    module_name, attribute = manifest.function_ref.split(":", 1)
    function = getattr(importlib.import_module(module_name), attribute, None)
    if not callable(function):
        raise ExporterRegistryError("manifest_invalid")
    return function


def _by_suffix(applies_to: str, suffix: str, package: str) -> ExporterManifest:
    for manifest in _selectable(applies_to, package):
        if manifest.suffix == suffix:
            return manifest
    raise ExporterRegistryError("format_unknown")


def export_document(record: dict[str, Any], suffix: str, *, package: str = DEFAULT_PACKAGE) -> tuple[str, ExporterManifest]:
    """Write ``record`` in the selectable document format with this suffix."""
    manifest = _by_suffix("document", suffix, package)
    return _function(manifest)(record), manifest


def export_case(case_id: str, reconciliation: dict[str, Any], suffix: str, *,
                package: str = DEFAULT_PACKAGE) -> tuple[str, ExporterManifest]:
    """Write a case in the selectable case format with this suffix."""
    manifest = _by_suffix("case", suffix, package)
    return _function(manifest)(case_id, reconciliation), manifest
