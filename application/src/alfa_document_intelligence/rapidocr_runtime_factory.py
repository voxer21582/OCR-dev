"""Opt-in, offline factory for the reviewed RapidOCR PP-OCRv6 candidate.

Importing this module does not import RapidOCR. The callable is intended to
run only inside the resource-limited OCR worker after the user explicitly
selects a trusted factory reference.
"""
from __future__ import annotations

import hashlib
from importlib import import_module, metadata
from pathlib import Path
from types import ModuleType

from .rapidocr_adapter import RapidOCRAdapter

RAPIDOCR_VERSION = "3.10.0"
MODEL_ARTIFACTS = (
    ("PP-OCRv6_det_small.onnx", "090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f"),
    ("PP-OCRv6_rec_small.onnx", "6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884"),
)


class RapidOCRFactoryError(RuntimeError):
    """Raised when the pinned, local OCR runtime cannot be verified safely."""


def package_version(distribution: str) -> str:
    """Resolve a distribution version without importing its runtime package."""
    return metadata.version(distribution)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verified_models(package: ModuleType) -> tuple[Path, tuple[Path, Path]]:
    package_file = getattr(package, "__file__", None)
    if not isinstance(package_file, str) or not package_file:
        raise RapidOCRFactoryError("RapidOCR package has no concrete installation path")
    package_root = Path(package_file).resolve().parent
    model_root = (package_root / "models").resolve()
    try:
        model_root.relative_to(package_root)
    except ValueError as exc:
        raise RapidOCRFactoryError("RapidOCR model directory escapes the package") from exc

    verified: list[Path] = []
    for filename, expected_digest in MODEL_ARTIFACTS:
        path = (model_root / filename).resolve()
        try:
            path.relative_to(model_root)
        except ValueError as exc:
            raise RapidOCRFactoryError(f"model path escapes the local model directory: {filename}") from exc
        if not path.is_file():
            raise RapidOCRFactoryError(f"required local model is missing: {filename}")
        if _sha256(path) != expected_digest:
            raise RapidOCRFactoryError(f"local model hash mismatch: {filename}")
        verified.append(path)
    if len(verified) != 2:
        raise RapidOCRFactoryError("the pinned detector and recognizer models are required")
    return model_root, (verified[0], verified[1])


def create_rapidocr_v6_multilingual_adapter() -> RapidOCRAdapter:
    """Construct an OCR2 adapter from only the exact, hash-verified local models."""
    try:
        installed_version = package_version("rapidocr")
    except metadata.PackageNotFoundError as exc:
        raise RapidOCRFactoryError("RapidOCR is not installed in this worker") from exc
    if installed_version != RAPIDOCR_VERSION:
        raise RapidOCRFactoryError(
            f"unsupported RapidOCR version {installed_version!r}; expected {RAPIDOCR_VERSION}"
        )

    try:
        package = import_module("rapidocr")
        model_root, models = _verified_models(package)
        constructor = getattr(package, "RapidOCR", None)
        if not callable(constructor):
            raise RapidOCRFactoryError("RapidOCR package has no callable RapidOCR constructor")
        params = {
            "Global.model_root_dir": str(model_root),
            "Global.use_cls": False,
            "Det.lang_type": "multi",
            "Det.model_path": str(models[0]),
            "Rec.lang_type": "multi",
            "Rec.model_path": str(models[1]),
        }
        engine = constructor(params=params)
        return RapidOCRAdapter(engine, installed_version)
    except RapidOCRFactoryError:
        raise
    except Exception as exc:
        raise RapidOCRFactoryError("could not construct the verified local RapidOCR runtime") from exc

