"""The CI workflow must run every application test module on Ubuntu and Windows (REQ-004)."""
from __future__ import annotations

from pathlib import Path
import re
import unittest

_REPOSITORY = Path(__file__).resolve().parents[2]
_WORKFLOW = _REPOSITORY / ".github" / "workflows" / "ocr2-synthetic-taxonomy.yml"


def _job_block(text: str, job: str) -> str:
    match = re.search(rf"^  {re.escape(job)}:\n(.*?)(?=^  [A-Za-z0-9_-]+:\n|\Z)", text, re.MULTILINE | re.DOTALL)
    if match is None:
        raise AssertionError(f"job {job} not found")
    return match.group(1)


def _listed_modules(block: str) -> set[str]:
    return set(re.findall(r"tests/(test_[A-Za-z0-9_]+)\.py", block))


class CiWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.text = _WORKFLOW.read_text(encoding="utf-8")
        self.modules = {path.stem for path in (_REPOSITORY / "application" / "tests").glob("test_*.py")}

    def test_ubuntu_job_runs_every_application_test_module(self):
        listed = _listed_modules(_job_block(self.text, "taxonomy-contract"))
        self.assertEqual(sorted(self.modules - listed), [])

    def test_windows_job_runs_every_application_test_module(self):
        block = _job_block(self.text, "windows-contracts")
        self.assertIn("runs-on: windows-2025", block)
        self.assertIn("requirements/ci-tests-cp313-win-amd64.lock", block)
        self.assertEqual(sorted(self.modules - _listed_modules(block)), [])

    def test_required_check_name_is_unchanged(self):
        self.assertIn("name: Taxonomy registry and binding", _job_block(self.text, "taxonomy-contract"))


if __name__ == "__main__":
    unittest.main()
