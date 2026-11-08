from __future__ import annotations

import hashlib
import importlib
from contextlib import ExitStack, contextmanager
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from alfa_document_intelligence.rapidocr_adapter import RapidOCRAdapter
from alfa_document_intelligence import rapidocr_runtime_factory as runtime_factory


class _FakeRapidOCR:
    def __init__(self, *, params):
        self.params = params

    def __call__(self, _image):
        return types.SimpleNamespace(boxes=[], txts=[], scores=[])


class RapidOCRRuntimeFactoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.package_root = Path(self.temp.name) / "rapidocr"
        self.model_root = self.package_root / "models"
        self.model_root.mkdir(parents=True)
        self.detector_bytes = b"synthetic detector model bytes"
        self.recognizer_bytes = b"synthetic recognizer model bytes"
        (self.model_root / "detector.onnx").write_bytes(self.detector_bytes)
        (self.model_root / "recognizer.onnx").write_bytes(self.recognizer_bytes)
        self.artifacts = (
            ("detector.onnx", hashlib.sha256(self.detector_bytes).hexdigest()),
            ("recognizer.onnx", hashlib.sha256(self.recognizer_bytes).hexdigest()),
        )
        self.package = types.ModuleType("rapidocr")
        self.package.__file__ = str(self.package_root / "__init__.py")
        self.package.RapidOCR = _FakeRapidOCR

    def _patched_factory(self, *, version="3.10.0", artifacts=None):
        @contextmanager
        def activate():
            with ExitStack() as stack:
                stack.enter_context(patch.object(runtime_factory, "MODEL_ARTIFACTS", artifacts or self.artifacts))
                stack.enter_context(patch.object(runtime_factory, "package_version", return_value=version))
                stack.enter_context(patch.object(runtime_factory, "import_module", return_value=self.package))
                yield

        return activate()

    def test_factory_builds_multilingual_adapter_with_verified_local_models(self):
        with self._patched_factory():
            adapter = runtime_factory.create_rapidocr_v6_multilingual_adapter()

        self.assertIsInstance(adapter, RapidOCRAdapter)
        self.assertEqual(adapter.version, "3.10.0")
        self.assertIsInstance(adapter.engine, _FakeRapidOCR)
        params = adapter.engine.params
        self.assertEqual(params["Det.lang_type"], "multi")
        self.assertEqual(params["Rec.lang_type"], "multi")
        self.assertFalse(params["Global.use_cls"])
        self.assertEqual(params["Det.model_path"], str((self.model_root / "detector.onnx").resolve()))
        self.assertEqual(params["Rec.model_path"], str((self.model_root / "recognizer.onnx").resolve()))
        self.assertEqual(params["Global.model_root_dir"], str(self.model_root.resolve()))

    def test_wrong_package_version_fails_before_importing_runtime(self):
        with (
            patch.object(runtime_factory, "MODEL_ARTIFACTS", self.artifacts),
            patch.object(runtime_factory, "package_version", return_value="3.11.0"),
            patch.object(runtime_factory, "import_module") as import_runtime,
        ):
            with self.assertRaises(runtime_factory.RapidOCRFactoryError):
                runtime_factory.create_rapidocr_v6_multilingual_adapter()

        import_runtime.assert_not_called()

    def test_missing_constructor_fails_closed(self):
        del self.package.RapidOCR
        with self._patched_factory():
            with self.assertRaises(runtime_factory.RapidOCRFactoryError):
                runtime_factory.create_rapidocr_v6_multilingual_adapter()

    def test_missing_model_fails_before_constructing_engine(self):
        (self.model_root / "recognizer.onnx").unlink()
        with self._patched_factory():
            with patch.object(self.package, "RapidOCR", wraps=self.package.RapidOCR) as constructor:
                with self.assertRaises(runtime_factory.RapidOCRFactoryError):
                    runtime_factory.create_rapidocr_v6_multilingual_adapter()

        constructor.assert_not_called()

    def test_hash_mismatch_fails_before_constructing_engine(self):
        mismatch = (("detector.onnx", "0" * 64), self.artifacts[1])
        with self._patched_factory(artifacts=mismatch):
            with patch.object(self.package, "RapidOCR", wraps=self.package.RapidOCR) as constructor:
                with self.assertRaises(runtime_factory.RapidOCRFactoryError):
                    runtime_factory.create_rapidocr_v6_multilingual_adapter()

        constructor.assert_not_called()

    def test_model_path_escape_fails_before_constructing_engine(self):
        outside_path = self.package_root / "outside.onnx"
        outside_path.write_bytes(b"synthetic outside model bytes")
        escaping_manifest = (("../outside.onnx", hashlib.sha256(outside_path.read_bytes()).hexdigest()),)
        with self._patched_factory(artifacts=escaping_manifest):
            with patch.object(self.package, "RapidOCR", wraps=self.package.RapidOCR) as constructor:
                with self.assertRaises(runtime_factory.RapidOCRFactoryError):
                    runtime_factory.create_rapidocr_v6_multilingual_adapter()

        constructor.assert_not_called()

    def test_module_import_does_not_import_vendor_package(self):
        sys.modules.pop("rapidocr", None)
        importlib.reload(runtime_factory)
        self.assertNotIn("rapidocr", sys.modules)



if __name__ == "__main__":
    unittest.main()
