"""REQ-124 guards: unexpected errors reach the output only as stable codes.

Every test plants a synthetic document text and a synthetic private path in an
unexpected exception and checks that neither, nor a traceback, reaches the
captured output.
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

from alfa_document_intelligence import install_state, removal_check

SENTINEL_TEXT = "SYNTHETIC_DOCUMENT_TEXT_R124 Ricevuta 999 importo 12,34"
SENTINEL_PATH = r"C:\Users\SYNTHETIC_USER_R124\AppData\Local\OCR2\document-archive.sqlite3"


def _assert_clean(output: str) -> None:
    assert "SYNTHETIC_DOCUMENT_TEXT_R124" not in output
    assert "SYNTHETIC_USER_R124" not in output
    assert "Traceback" not in output


@pytest.mark.parametrize("error_type", [RuntimeError, KeyError, TypeError, ValueError])
def test_install_state_unexpected_error_prints_only_stable_code(tmp_path, monkeypatch, capsys, error_type):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    def fail(*args):
        raise error_type(SENTINEL_TEXT + " " + SENTINEL_PATH)

    monkeypatch.setattr(install_state, "rollback", fail)
    assert install_state.main(["--base", str(tmp_path), "rollback"]) == 1
    output = capsys.readouterr()
    _assert_clean(output.out + output.err)
    assert output.err.strip() == "OCR2_INSTALL_ERROR"


def test_install_state_deeply_nested_state_file_prints_only_stable_code(tmp_path, monkeypatch, capsys):
    # A damaged active.json nested beyond the JSON parser's recursion limit
    # raised RecursionError, outside the handled types, with a full traceback.
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    (tmp_path / "active.json").write_text("[" * 200_000, encoding="utf-8")
    assert install_state.main(["--base", str(tmp_path), "active"]) == 1
    output = capsys.readouterr()
    _assert_clean(output.out + output.err)
    assert output.err.strip() == "OCR2_INSTALL_ERROR"


@pytest.mark.parametrize("error_type", [RuntimeError, KeyError, TypeError])
def test_removal_check_unexpected_error_prints_only_stable_code(tmp_path, monkeypatch, capsys, error_type):
    def fail(*args):
        raise error_type(SENTINEL_TEXT + " " + SENTINEL_PATH)

    monkeypatch.setattr(removal_check, "validate_removal", fail)
    assert removal_check.main(["--base", str(tmp_path)]) == 1
    output = capsys.readouterr()
    _assert_clean(output.out + output.err)
    assert output.err.strip() == "OCR2_REMOVE_ERROR"


_THREAD_SCRIPT = r'''
import sys, threading
from alfa_document_intelligence import __main__ as launcher
launcher._install_safe_exception_hooks()
def fail():
    raise RuntimeError(sys.argv[1] + " " + sys.argv[2])
thread = threading.Thread(target=fail, name="ocr2-synthetic-" + sys.argv[1][:20])
thread.start()
thread.join()
print("DONE", flush=True)
'''

_UNRAISABLE_SCRIPT = r'''
import gc, sys
from alfa_document_intelligence import __main__ as launcher
launcher._install_safe_exception_hooks()
class Finalizer:
    def __repr__(self):
        return sys.argv[2]
    def __del__(self):
        raise RuntimeError(sys.argv[1])
item = Finalizer()
del item
gc.collect()
print("DONE", flush=True)
'''


def _run_script(script: str, tmp_path) -> subprocess.CompletedProcess:
    environment = dict(os.environ, LOCALAPPDATA=str(tmp_path))
    return subprocess.run(
        [sys.executable, "-B", "-c", script, SENTINEL_TEXT, SENTINEL_PATH],
        env=environment, capture_output=True, text=True, timeout=30, check=False,
    )


def test_launcher_thread_exception_prints_only_stable_code(tmp_path):
    result = _run_script(_THREAD_SCRIPT, tmp_path)
    assert result.returncode == 0, "the synthetic script must complete"
    assert result.stdout.strip() == "DONE"
    _assert_clean(result.stdout + result.stderr)
    assert result.stderr.strip() == "OCR2_THREAD_ERROR"


def test_launcher_unraisable_exception_prints_only_stable_code(tmp_path):
    result = _run_script(_UNRAISABLE_SCRIPT, tmp_path)
    assert result.returncode == 0, "the synthetic script must complete"
    assert result.stdout.strip() == "DONE"
    _assert_clean(result.stdout + result.stderr)
    assert result.stderr.strip() == "OCR2_UNRAISABLE_ERROR"


def test_launcher_hooks_tolerate_missing_stderr(tmp_path):
    script = _THREAD_SCRIPT.replace(
        "launcher._install_safe_exception_hooks()",
        "launcher._install_safe_exception_hooks(); sys.stderr = None",
    )
    result = _run_script(script, tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == "DONE"
    assert result.stderr == ""


def test_cli_entrypoint_installs_safe_exception_hooks(tmp_path):
    script = r'''
import sys, threading
from alfa_document_intelligence import __main__ as launcher
def run():
    def fail():
        raise RuntimeError(sys.argv[1] + " " + sys.argv[2])
    thread = threading.Thread(target=fail)
    thread.start()
    thread.join()
launcher._run_entrypoint = run
launcher._cli_entrypoint()
print("DONE", flush=True)
'''
    result = _run_script(script, tmp_path)
    assert result.returncode == 0
    _assert_clean(result.stdout + result.stderr)
    assert result.stderr.strip() == "OCR2_THREAD_ERROR"
