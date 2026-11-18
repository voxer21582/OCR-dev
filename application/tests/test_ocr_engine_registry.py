"""Engine registry: manifests are discovered without importing OCR engines (REQ-022)."""
from __future__ import annotations

import importlib
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest
import uuid

from alfa_document_intelligence.ocr_engine_registry import (
    EngineManifest,
    EngineRegistryError,
    discover_engines,
    get_engine,
)

_GOOD = '''
from alfa_document_intelligence.ocr_engine_registry import EngineManifest
MANIFEST = EngineManifest(
    engine_id={engine_id!r}, name="Fake", version="1", languages=("it",), license="MIT",
    artifacts=(("model.onnx", "{digest}"),), factory_ref="json:dumps", runtime_check_ref=None,
)
'''


class _TemporaryEnginePackage:
    """A throwaway package of manifest modules on sys.path."""

    def __init__(self, modules: dict[str, str]):
        self.modules = modules
        self.name = "engines_" + uuid.uuid4().hex

    def __enter__(self) -> str:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name) / self.name
        root.mkdir()
        (root / "__init__.py").write_text("", encoding="utf-8")
        for module, source in self.modules.items():
            (root / f"{module}.py").write_text(textwrap.dedent(source), encoding="utf-8")
        sys.path.insert(0, self.temp.name)
        importlib.invalidate_caches()
        return self.name

    def __exit__(self, *exc) -> None:
        sys.path.remove(self.temp.name)
        for key in [key for key in sys.modules if key == self.name or key.startswith(self.name + ".")]:
            del sys.modules[key]
        self.temp.cleanup()


class EngineRegistryTests(unittest.TestCase):
    def test_startup_discovery_and_runtime_check_do_not_import_native_engines(self):
        code = (
            "import sys\n"
            "from alfa_document_intelligence import __main__ as launcher\n"
            "launcher._runtime_check(launcher.discover_engines()['rapidocr-v6'])\n"
            "native = ('PIL', 'pypdfium2', 'rapidocr', 'onnxruntime', 'numpy', 'cv2')\n"
            "assert not [name for name in sys.modules if any(name == p or name.startswith(p + '.') for p in native)]\n"
        )
        src = Path(__file__).resolve().parents[1] / 'src'
        result = subprocess.run([sys.executable, '-B', '-c', code], cwd=str(src), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_discovers_rapidocr_manifest_without_importing_rapidocr(self):
        code = (
            "import sys\n"
            "from alfa_document_intelligence.ocr_engine_registry import discover_engines\n"
            "engines = discover_engines()\n"
            "assert 'rapidocr-v6' in engines, engines\n"
            "manifest = engines['rapidocr-v6']\n"
            "assert manifest.version == '3.10.0' and manifest.name == 'RapidOCR'\n"
            "assert manifest.selectable and len(manifest.artifacts) == 2\n"
            "assert 'rapidocr' not in sys.modules and 'onnxruntime' not in sys.modules\n"
        )
        src = Path(__file__).resolve().parents[1] / "src"
        result = subprocess.run([sys.executable, "-B", "-c", code], cwd=str(src), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rejects_duplicate_ids(self):
        digest = "a" * 64
        modules = {"one": _GOOD.format(engine_id="same", digest=digest), "two": _GOOD.format(engine_id="same", digest=digest)}
        with _TemporaryEnginePackage(modules) as package:
            with self.assertRaises(EngineRegistryError) as caught:
                discover_engines(package)
        self.assertEqual(caught.exception.code, "engine_id_duplicate")

    def test_rejects_invalid_manifest(self):
        cases = {
            "bad id": _GOOD.format(engine_id="Bad Id", digest="a" * 64),
            "bad hash": _GOOD.format(engine_id="fake", digest="xyz"),
            "empty version": _GOOD.format(engine_id="fake", digest="a" * 64).replace('version="1"', 'version=""'),
            "bad factory": _GOOD.format(engine_id="fake", digest="a" * 64).replace('"json:dumps"', '"no-colon"'),
            "missing factory module": _GOOD.format(engine_id="fake", digest="a" * 64).replace('"json:dumps"', '"missing_module_ocr2_zz:make"'),
            "no manifest": "VALUE = 1\n",
        }
        for label, source in cases.items():
            with self.subTest(label=label):
                with _TemporaryEnginePackage({"engine": source}) as package:
                    with self.assertRaises(EngineRegistryError) as caught:
                        discover_engines(package)
                self.assertEqual(caught.exception.code, "manifest_invalid")

    def test_unknown_engine_has_stable_code(self):
        with self.assertRaises(EngineRegistryError) as caught:
            get_engine("does-not-exist")
        self.assertEqual(caught.exception.code, "engine_unknown")

    def test_manifest_is_immutable(self):
        manifest = get_engine("rapidocr-v6")
        self.assertIsInstance(manifest, EngineManifest)
        with self.assertRaises(Exception):
            manifest.version = "9"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
