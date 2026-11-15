import os
import tempfile
import unittest
from unittest.mock import patch

from alfa_document_intelligence import __main__ as launcher
from alfa_document_intelligence.ocr_engine_registry import EngineManifest

_SYNTHETIC_MANIFEST = EngineManifest(
    engine_id="synthetic-x", name="SyntheticX", version="7", languages=("it",), license="MIT",
    artifacts=(), factory_ref="tests.fake_engine:make", runtime_check_ref="tests.fake_engine:check",
)
_HIDDEN_MANIFEST = EngineManifest(
    engine_id="hidden-x", name="Hidden", version="1", languages=("it",), license="MIT",
    artifacts=(), factory_ref="tests.fake_engine:make", runtime_check_ref=None, selectable=False,
)


class _Report:
    def __init__(self, problems=(), warnings=()):
        self.problems = tuple(problems)
        self.warnings = tuple(warnings)
        self.ok = not self.problems


class _FakeServer:
    server_address = ("127.0.0.1", 8765)

    def __init__(self):
        self.closed = False

    def serve_forever(self):
        raise KeyboardInterrupt

    def server_close(self):
        self.closed = True


class _FakeManager:
    instances = []

    def __init__(self, factory_ref, limits, expected_identity=None):
        self.factory_ref = factory_ref
        self.limits = limits
        self.expected_identity = expected_identity
        self.closed = False
        self.__class__.instances.append(self)

    def close(self):
        self.closed = True


class _FakeCaseProcessingManager:
    instances = []

    def __init__(self, store, worker, limits, decode_limits, **kwargs):
        self.store = store
        self.worker = worker
        self.limits = limits
        self.decode_limits = decode_limits
        self.kwargs = kwargs
        self.closed = False
        self.__class__.instances.append(self)

    def close(self):
        self.closed = True


class OCRLauncherContractTests(unittest.TestCase):
    def setUp(self):
        _FakeManager.instances.clear()
        _FakeCaseProcessingManager.instances.clear()
        self.server = _FakeServer()
        self.calls = []

    def _run(self, args, report=None, engines=None):
        def create_server(**kwargs):
            self.calls.append(kwargs)
            manager = kwargs.get("ocr_processing_manager")
            case_manager = kwargs.get("expense_case_processing_manager")
            self.server.ocr2_close = lambda: (
                case_manager.close() if case_manager is not None else None,
                manager.close() if manager is not None else None,
            )
            return self.server

        with tempfile.TemporaryDirectory() as local_app_data:
            with patch.dict(os.environ, {"LOCALAPPDATA": local_app_data}):
                with patch.object(launcher, "serve_expense_report_local", side_effect=create_server):
                    with patch.object(launcher, "OCRProcessingManager", _FakeManager):
                        with patch.object(launcher, "_runtime_check",
                                          return_value=report or _Report()) as check:
                            self.check = check
                            with patch.object(launcher, "ExpenseCaseProcessingManager", _FakeCaseProcessingManager):
                                if engines is None:
                                    launcher.main(args)
                                else:
                                    with patch.object(launcher, "discover_engines", return_value=engines):
                                        launcher.main(args)

    def test_launcher_default_keeps_ocr_disabled(self):
        with patch("builtins.print") as output:
            self._run([])
        self.assertEqual(len(self.calls), 1)
        self.assertIsNone(self.calls[0]["ocr_processing_manager"])
        self.assertEqual(_FakeManager.instances, [])
        self.assertEqual(_FakeCaseProcessingManager.instances, [])
        output_text = " ".join(str(args) for args, _ in output.call_args_list)
        self.assertIn("OCR resta disattivato", output_text)

    @unittest.skipUnless(os.name == "nt", "the launcher builds the archive and case manager only on Windows; the Windows CI job runs this test")
    def test_explicit_rapidocr_option_uses_only_the_fixed_factory_and_limits(self):
        self._run(["--ocr-engine", "rapidocr-v6"])
        self.assertEqual(len(_FakeManager.instances), 1)
        manager = _FakeManager.instances[0]
        self.assertEqual(
            manager.factory_ref,
            "alfa_document_intelligence.rapidocr_runtime_factory:create_rapidocr_v6_multilingual_adapter",
        )
        self.assertEqual(manager.expected_identity, ("RapidOCR", "3.10.0"))
        self.assertEqual(manager.limits.job_timeout_seconds, 900)
        self.assertEqual(manager.limits.cleanup_grace_seconds, 3)
        self.assertEqual(manager.limits.child_memory_limit_bytes, 2 * 1024 * 1024 * 1024 - 1)
        self.assertEqual(manager.limits.max_input_frame_bytes, 64 * 1024 * 1024)
        self.assertEqual(manager.limits.max_result_frame_bytes, 16 * 1024 * 1024)
        self.assertEqual(manager.limits.max_aggregate_result_bytes, 64 * 1024 * 1024)
        self.assertIs(self.calls[0]["ocr_processing_manager"], manager)
        case_manager = _FakeCaseProcessingManager.instances[0]
        self.assertIs(self.calls[0]["expense_case_processing_manager"], case_manager)
        self.assertIs(case_manager.store, self.calls[0]["archive_store"])
        self.assertIs(case_manager.worker, manager)
        self.assertFalse(case_manager.kwargs["close_worker_on_close"])
        self.assertTrue(case_manager.closed)
        self.assertTrue(manager.closed)

    def test_default_launch_does_not_check_the_ocr_runtime(self):
        self._run([])
        self.check.assert_not_called()

    def test_unusable_runtime_stops_before_any_worker_or_server(self):
        report = _Report(problems=("RapidOCR non è installato", "ONNX Runtime non è installato"))
        with patch("sys.stderr"), self.assertRaises(SystemExit) as caught:
            self._run(["--ocr-engine", "rapidocr-v6"], report)
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(self.calls, [])
        self.assertEqual(_FakeManager.instances, [])

    def test_runtime_warnings_are_shown_but_do_not_stop_the_launch(self):
        report = _Report(warnings=("pypdfium2 non è installato: i PDF non possono essere letti",))
        with patch("builtins.print") as output:
            self._run(["--ocr-engine", "rapidocr-v6"], report)
        self.assertEqual(len(self.calls), 1)
        text = " ".join(str(args) for args, _ in output.call_args_list)
        self.assertIn("pypdfium2", text)


    def test_engine_choices_come_from_the_registry(self):
        engines = {"synthetic-x": _SYNTHETIC_MANIFEST, "hidden-x": _HIDDEN_MANIFEST}
        with patch("builtins.print"):
            self._run(["--ocr-engine", "synthetic-x"], engines=engines)
        manager = _FakeManager.instances[0]
        self.assertEqual(manager.factory_ref, "tests.fake_engine:make")
        self.assertEqual(manager.expected_identity, ("SyntheticX", "7"))
        self.assertEqual(self.check.call_args.args[0], _SYNTHETIC_MANIFEST)

    def test_unknown_or_hidden_engine_is_rejected(self):
        engines = {"synthetic-x": _SYNTHETIC_MANIFEST, "hidden-x": _HIDDEN_MANIFEST}
        for engine_id in ("does-not-exist", "hidden-x"):
            with self.subTest(engine_id=engine_id):
                with patch("sys.stderr"), self.assertRaises(SystemExit) as caught:
                    self._run(["--ocr-engine", engine_id], engines=engines)
                self.assertEqual(caught.exception.code, 2)
                self.assertEqual(_FakeManager.instances, [])


if __name__ == "__main__":
    unittest.main()
