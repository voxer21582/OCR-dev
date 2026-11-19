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


def _calls_named(module_file: str, name: str):
    """Every call to ``name`` or ``<anything>.name``, raised directly or not."""
    import ast
    from pathlib import Path

    tree = ast.parse(Path(module_file).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            function = node.func
            called = function.id if isinstance(function, ast.Name) else (
                function.attr if isinstance(function, ast.Attribute) else None)
            if called == name:
                yield node.lineno, node.args, node.keywords


def _source_modules():
    from pathlib import Path
    import alfa_document_intelligence

    return sorted(Path(alfa_document_intelligence.__file__).parent.rglob("*.py"))


def test_intake_request_errors_shown_to_the_user_are_fixed_literals():
    # The HTTP 400 pages print str(exc) of IntakeRequestError: every message,
    # in any module and however the error is built, must be a fixed literal.
    found = []
    for module in _source_modules():
        for line, args, keywords in _calls_named(str(module), "IntakeRequestError"):
            found.append((module.name, line, args, keywords))
    assert len(found) >= 80
    for module_name, line, args, keywords in found:
        where = f"{module_name}:{line}"
        assert len(args) == 1 and not keywords, where
        assert type(args[0]).__name__ == "Constant" and isinstance(args[0].value, str), where


@pytest.mark.parametrize("source, kind", [
    ("def f(value):\n    raise IntakeRequestError(f'valore {value}')\n", "JoinedStr"),
    ("import m\ndef f(value):\n    raise m.IntakeRequestError('a' + value)\n", "BinOp"),
    ("def f(value):\n    error = IntakeRequestError(value)\n    raise error\n", "Name"),
])
def test_static_guard_detects_a_variable_intake_message(tmp_path, source, kind):
    module = tmp_path / "synthetic_module.py"
    module.write_text(source, encoding="utf-8")
    ((line, args, keywords),) = list(_calls_named(str(module), "IntakeRequestError"))
    assert type(args[0]).__name__ == kind


# Launcher output: only literals, the fixed message constants, and these
# formatted values (loopback address, engine manifest identity, stable codes).
_LAUNCHER_OUTPUT_CALLS = {
    "print", "error", "exit", "MessageBoxW", "_show_error_dialog", "_show_integrity_error",
    "_show_startup_error", "_write_launch_log",
}
_LAUNCHER_SAFE_NAMES = {"_REPAIR_ADVICE", "_START_FAILURE_MESSAGE", "_LAUNCH_LOG_HINT", "message", "title"}
_LAUNCHER_SAFE_FORMATTED = {"host", "port", "manifest.name", "manifest.version", "detail", "exc.code"}


def _launcher_safe(node) -> bool:
    import ast

    if isinstance(node, ast.Constant):
        # Text, exit statuses and dialog flags, or None for no owner window.
        return node.value is None or type(node.value) in (str, int)
    if isinstance(node, ast.Name):
        return node.id in _LAUNCHER_SAFE_NAMES
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _launcher_safe(node.left) and _launcher_safe(node.right)
    if isinstance(node, ast.JoinedStr):
        return all(
            isinstance(part, ast.Constant)
            or (isinstance(part, ast.FormattedValue) and ast.unparse(part.value) in _LAUNCHER_SAFE_FORMATTED)
            for part in node.values
        )
    return False


def _launcher_violations(module_file: str) -> list[str]:
    import ast
    from pathlib import Path

    tree = ast.parse(Path(module_file).read_text(encoding="utf-8"))
    violations = []
    for name in _LAUNCHER_OUTPUT_CALLS:
        for line, args, _keywords in _calls_named(module_file, name):
            violations += [f"{name}:{line}" for arg in args if not _launcher_safe(arg)]
    for node in ast.walk(tree):
        # The names allowed above must themselves only ever hold safe text.
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in _LAUNCHER_SAFE_NAMES for target in node.targets
        ) and not _launcher_safe(node.value):
            violations.append(f"assign:{node.lineno}")
    return violations


def test_launcher_prints_and_dialogs_use_only_literals_and_stable_codes():
    from alfa_document_intelligence import __main__ as launcher

    assert _launcher_violations(launcher.__file__) == []


def test_launcher_guard_detects_variable_output(tmp_path):
    module = tmp_path / "synthetic_launcher.py"
    module.write_text(
        "import sys\n"
        "def f(exc, path):\n"
        "    print(str(exc), file=sys.stderr)\n"
        "    parser.error(f'percorso {path}')\n"
        "    message = 'Errore: ' + str(path)\n",
        encoding="utf-8",
    )
    assert sorted(_launcher_violations(str(module))) == ["assign:5", "error:4", "print:3"]


def test_safe_argument_parser_never_echoes_formatted_detail():
    # parser.error may receive a formatted stable code; the parser shows only
    # its fixed messages or a generic text.
    from alfa_document_intelligence import __main__ as launcher

    parser = launcher._SafeArgumentParser()
    with pytest.raises(SystemExit):
        try:
            parser.error("registro SYNTHETIC_USER_R124 " + SENTINEL_PATH)
        except SystemExit as exc:
            assert exc.code == 2
            raise


def test_launcher_python_warnings_print_only_stable_code(tmp_path):
    script = r"""
import sys, warnings
from alfa_document_intelligence import __main__ as launcher
launcher._install_safe_exception_hooks()
warnings.simplefilter("always")
warnings.warn(sys.argv[1] + " " + sys.argv[2], RuntimeWarning)
print("DONE", flush=True)
"""
    result = _run_script(script, tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == "DONE"
    _assert_clean(result.stdout + result.stderr)
    assert result.stderr.strip() == "OCR2_PYTHON_WARNING"
