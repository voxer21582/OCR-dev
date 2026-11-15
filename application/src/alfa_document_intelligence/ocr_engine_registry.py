"""Registry of OCR engines declared by manifest modules (REQ-022, REQ-023).

Every module in ``alfa_document_intelligence.engines`` defines ``MANIFEST``, an
:class:`EngineManifest`. Adding an engine means adding one such module (plus
its adapter); nothing else changes. Manifest modules must not import the OCR
engine itself: discovery runs in the web process, the engine only in the
isolated worker through ``factory_ref``.
"""
from __future__ import annotations

from dataclasses import dataclass
import importlib
import importlib.util
import pkgutil
import re

DEFAULT_PACKAGE = "alfa_document_intelligence.engines"
_ENGINE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REFERENCE = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*:[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*$")


class EngineRegistryError(ValueError):
    """A manifest is invalid or an engine is unknown. ``code`` is stable and non-sensitive."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class EngineManifest:
    """Identity, licence, artifacts and entry points of one OCR engine."""

    engine_id: str
    name: str
    version: str
    languages: tuple[str, ...]
    license: str
    artifacts: tuple[tuple[str, str], ...]
    factory_ref: str
    runtime_check_ref: str | None
    selectable: bool = True


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid(manifest: object) -> bool:
    if not isinstance(manifest, EngineManifest):
        return False
    return (
        isinstance(manifest.engine_id, str) and bool(_ENGINE_ID.fullmatch(manifest.engine_id))
        and _text(manifest.name) and _text(manifest.version) and _text(manifest.license)
        and isinstance(manifest.languages, tuple) and bool(manifest.languages)
        and all(_text(language) for language in manifest.languages)
        and isinstance(manifest.artifacts, tuple)
        and all(
            isinstance(item, tuple) and len(item) == 2 and _text(item[0])
            and isinstance(item[1], str) and bool(_SHA256.fullmatch(item[1]))
            for item in manifest.artifacts
        )
        and isinstance(manifest.factory_ref, str) and bool(_REFERENCE.fullmatch(manifest.factory_ref))
        and (manifest.runtime_check_ref is None or (
            isinstance(manifest.runtime_check_ref, str) and bool(_REFERENCE.fullmatch(manifest.runtime_check_ref))
        ))
        and isinstance(manifest.selectable, bool)
    )


def _module_exists(reference: str) -> bool:
    """The referenced module can be found, without running it (only parent packages import)."""
    try:
        return importlib.util.find_spec(reference.split(":", 1)[0]) is not None
    except (ImportError, ValueError):
        return False


def discover_engines(package: str = DEFAULT_PACKAGE) -> dict[str, EngineManifest]:
    """Import every manifest module of ``package`` and return manifests by engine id."""
    root = importlib.import_module(package)
    engines: dict[str, EngineManifest] = {}
    for module_info in sorted(pkgutil.iter_modules(root.__path__), key=lambda item: item.name):
        if module_info.ispkg or module_info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{package}.{module_info.name}")
        manifest = getattr(module, "MANIFEST", None)
        if not _valid(manifest) or not all(
            _module_exists(reference) for reference in (manifest.factory_ref, manifest.runtime_check_ref)
            if reference is not None
        ):
            raise EngineRegistryError("manifest_invalid")
        if manifest.engine_id in engines:
            raise EngineRegistryError("engine_id_duplicate")
        engines[manifest.engine_id] = manifest
    return engines


def get_engine(engine_id: str, *, package: str = DEFAULT_PACKAGE) -> EngineManifest:
    """Return one manifest or raise ``EngineRegistryError('engine_unknown')``."""
    manifest = discover_engines(package).get(engine_id)
    if manifest is None:
        raise EngineRegistryError("engine_unknown")
    return manifest
