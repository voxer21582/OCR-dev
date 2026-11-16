"""CycloneDX 1.5 SBOM of the installer payload (M6 Task 7, REQ-107).

Deterministic: no timestamp, ``serialNumber`` derived from the content, sorted
components, ``json.dumps(..., indent=2, sort_keys=True)``.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
import uuid

import _distinfo

_REPOSITORY = Path(__file__).resolve().parent.parent
try:
    from alfa_document_intelligence.rapidocr_runtime_factory import MODEL_ARTIFACTS
except ImportError:  # run as a script from the repository
    sys.path.insert(0, str(_REPOSITORY / "application" / "src"))
    from alfa_document_intelligence.rapidocr_runtime_factory import MODEL_ARTIFACTS

_LOCK_LINE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s\\]+)")
_LOCK_HASH = re.compile(r"--hash=sha256:([0-9a-f]{64})")
_REPOSITORY_LICENCES = {"MIT License": "MIT", "Apache License": "Apache-2.0"}


class SbomError(RuntimeError):
    """The SBOM cannot be built from the given inputs."""


def parse_lock(lock: Path) -> list[tuple[str, str, list[str]]]:
    """``(name, version, [sha256, ...])`` for every pinned requirement, in file order."""
    entries: list[tuple[str, str, list[str]]] = []
    for line in Path(lock).read_text(encoding="utf-8").splitlines():
        match = _LOCK_LINE.match(line)
        if match:
            entries.append((match.group(1), match.group(2), _LOCK_HASH.findall(line)))
        elif entries:
            entries[-1][2].extend(_LOCK_HASH.findall(line))
    return entries


def _licence_entry(licence: str, is_expression: bool) -> dict:
    if is_expression:
        return {"expression": licence}
    return {"license": {"name": licence}}


def _sha(value: str) -> dict:
    return {"alg": "SHA-256", "content": value}


def _python_component(pins: dict) -> dict:
    pin = pins["embeddable"]
    return {
        "bom-ref": f"cpython@{pin['version']}", "type": "library", "name": "cpython", "version": pin["version"],
        "purl": f"pkg:generic/cpython@{pin['version']}", "scope": "required",
        "hashes": [_sha(pin["sha256"])], "licenses": [{"license": {"id": "PSF-2.0"}}],
        "description": f"CPython embeddable package ({pin['file']})",
    }


def _nsis_component(pins: dict) -> dict:
    pin = pins["nsis"]
    return {
        "bom-ref": f"nsis@{pin['version']}", "type": "application", "name": "nsis", "version": pin["version"],
        "purl": f"pkg:generic/nsis@{pin['version']}", "scope": "excluded",
        "hashes": [_sha(pin["sha256"])], "licenses": [{"license": {"id": "Zlib"}}],
        "description": "Build tool only (not part of the installed payload)",
    }


def _model_components(rapidocr_version: str) -> list[dict]:
    components = []
    for filename, digest in MODEL_ARTIFACTS:
        name = filename.removesuffix(".onnx")
        components.append({
            "bom-ref": f"model:{name}", "type": "machine-learning-model", "name": name, "version": "v6",
            "scope": "required", "hashes": [_sha(digest)], "licenses": [{"license": {"id": "Apache-2.0"}}],
            "description": f"PP-OCRv6 model shipped by rapidocr {rapidocr_version}; see MODEL_LICENSES.md",
        })
    return components


def _ocr2_component(version: str) -> dict:
    first = (_REPOSITORY / "LICENSE").read_text(encoding="utf-8").splitlines()[0].strip()
    spdx = _REPOSITORY_LICENCES.get(first)
    licence = {"license": {"id": spdx}} if spdx else {"license": {"name": _distinfo.NOASSERTION}}
    return {
        "bom-ref": f"ocr2@{version}", "type": "application", "name": "ocr2", "version": version,
        "purl": f"pkg:generic/ocr2@{version}", "scope": "required", "licenses": [licence],
    }


def build_sbom(payload_root: Path, lock: Path, pins: Path, overrides: dict | None = None) -> dict:
    payload_root = Path(payload_root)
    pins_data = json.loads(Path(pins).read_text(encoding="utf-8"))
    installed = {_distinfo.normalise(info.name): info for info in _distinfo.read_all(payload_root, overrides)}
    components = []
    rapidocr_version = ""
    for name, version, hashes in parse_lock(lock):
        key = _distinfo.normalise(name)
        info = installed.get(key)
        if info is None or info.version != version:
            raise SbomError(f"{name}=={version} del lock non e' nel contenuto costruito")
        if key == "rapidocr":
            rapidocr_version = version
        component = {
            "bom-ref": f"pkg:pypi/{key}@{version}", "type": "library", "name": key, "version": version,
            "purl": f"pkg:pypi/{key}@{version}", "scope": "required",
            "hashes": [_sha(h) for h in sorted(hashes)],
            "licenses": [_licence_entry(info.licence, info.licence_is_expression)],
        }
        if info.override_source:
            component["properties"] = [{"name": "ocr2:licence-text-source", "value": info.override_source}]
        components.append(component)
    components.append(_python_component(pins_data))
    components.extend(_model_components(rapidocr_version))
    components.append(_ocr2_component(payload_root.name))
    components.append(_nsis_component(pins_data))
    components.sort(key=lambda c: (c["type"], c["name"], c["version"]))
    canonical = json.dumps(components, sort_keys=True, separators=(",", ":")).encode("utf-8")
    serial = uuid.UUID(bytes=hashlib.sha256(canonical).digest()[:16], version=4)
    return {
        "bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1, "serialNumber": f"urn:uuid:{serial}",
        "metadata": {"tools": {"components": [{"type": "application", "name": "ocr2-installer-sbom"}]}},
        "components": components,
    }


def dump_sbom(sbom: dict) -> str:
    return json.dumps(sbom, indent=2, sort_keys=True) + "\n"


def write_sbom(sbom: dict, path: Path) -> None:
    Path(path).write_text(dump_sbom(sbom), encoding="utf-8", newline="\n")
