import os
import tempfile
import unittest
from unittest.mock import patch

from alfa_document_intelligence import __main__ as launcher


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

    def __init__(self, factory_ref, limits):
        self.factory_ref = factory_ref
        self.limits = limits
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

    def _run(self, args):
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
                        with patch.object(launcher, "ExpenseCaseProcessingManager", _FakeCaseProcessingManager):
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

    def test_explicit_rapidocr_option_uses_only_the_fixed_factory_and_limits(self):
        self._run(["--ocr-engine", "rapidocr-v6"])
        self.assertEqual(len(_FakeManager.instances), 1)
        manager = _FakeManager.instances[0]
        self.assertEqual(manager.factory_ref, launcher._RAPIDOCR_FACTORY)
        self.assertEqual(manager.limits.job_timeout_seconds, 300)
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


if __name__ == "__main__":
    unittest.main()
