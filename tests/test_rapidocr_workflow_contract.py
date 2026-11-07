import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "rapidocr-windows-synthetic-smoke.yml").read_text(
    encoding="utf-8"
)
RUNTIME_LOCK = (ROOT / "requirements" / "rapidocr-win-cp313-x64.lock").read_text(encoding="utf-8")
BUILD_LOCK = (ROOT / "requirements" / "rapidocr-build-tools-win-cp313.lock").read_text(encoding="utf-8")


class RapidOCRWorkflowContractTests(unittest.TestCase):
    def test_evaluation_is_one_named_branch_push_with_no_other_triggers(self):
        self.assertIn("branches:\n      - codex/rapidocr-windows-smoke-20261107", WORKFLOW)
        for trigger in ("pull_request", "schedule:", "workflow_dispatch", "workflow_call"):
            self.assertNotIn(trigger, WORKFLOW)

    def test_runner_actions_permissions_and_modules_are_fixed(self):
        self.assertIn("runs-on: windows-2025", WORKFLOW)
        self.assertIn("permissions:\n  contents: read", WORKFLOW)
        self.assertIn("permissions:\n      contents: read", WORKFLOW)
        self.assertIn("test_synthetic_page_generator", WORKFLOW)
        self.assertIn("test_rapidocr_windows_smoke_contract", WORKFLOW)
        self.assertNotIn("discover", WORKFLOW.lower())
        self.assertNotIn("upload-artifact", WORKFLOW)
        refs = re.findall(r"^\s*uses:\s*[^\s]+@([0-9a-f]{40})", WORKFLOW, re.MULTILINE)
        self.assertEqual(len(refs), 2)

    def test_install_commands_require_exact_hashes_and_control_the_sdist_build(self):
        self.assertIn("--require-hashes", WORKFLOW)
        self.assertIn("--no-build-isolation", WORKFLOW)
        self.assertIn("--only-binary=:all:", WORKFLOW)
        self.assertIn("antlr4-python3-runtime==4.9.3 --hash=sha256:", RUNTIME_LOCK)
        for lock in (RUNTIME_LOCK, BUILD_LOCK):
            for line in lock.splitlines():
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                self.assertRegex(line, r"^[A-Za-z0-9_.-]+==[^ ]+ --hash=sha256:[0-9a-f]{64}$")

    def test_runtime_lock_contains_the_reviewed_onnx_rapidocr_pair(self):
        self.assertIn("rapidocr==3.10.0 --hash=sha256:2fc34e26cd0f48514804a94f8832283039c7334076bff60768b1fed9ad068050", RUNTIME_LOCK)
        self.assertIn("onnxruntime==1.31.1 --hash=sha256:0558f29d5f6ac09957390c9c5495931485ee8ae7f0ce781ccee86a0ae5c2348b", RUNTIME_LOCK)
        self.assertNotIn("paddlepaddle", RUNTIME_LOCK.lower())
        self.assertNotIn("paddleocr", RUNTIME_LOCK.lower())


if __name__ == "__main__":
    unittest.main()
