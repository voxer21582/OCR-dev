"""installer/user-footprint.ps1 against synthetic folder trees (M6 Task 10, REQ-102, REQ-104).

The script lists files and folders under the user profile roots and the *names*
of registry keys (never values); ``-Compare`` prints only differences. The tests
point it at temporary roots through -LocalAppData / -StartMenu / -RegistryRoot
and run only on Windows (Windows PowerShell 5.1 is the contract).
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "installer" / "user-footprint.ps1"
pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="user-footprint.ps1 is Windows PowerShell")


def _powershell() -> str:
    return shutil.which("powershell") or shutil.which("pwsh") or "powershell"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(_SCRIPT), *args],
        capture_output=True, text=True, encoding="utf-8", timeout=120,
    )


@pytest.fixture()
def roots(tmp_path):
    local = tmp_path / "local"
    start = tmp_path / "start"
    (local / "OCR2" / "edge-profile").mkdir(parents=True)
    (local / "OCR2" / "data.bin").write_bytes(b"x" * 10)
    (local / "Other").mkdir()
    (local / "Other" / "b.txt").write_text("bb")
    (start / "Programs").mkdir(parents=True)
    return local, start


@pytest.fixture()
def registry_root():
    name = f"OCR2FootprintTest-{uuid.uuid4().hex}"
    path = f"HKCU:\\Software\\{name}"
    create = (
        f"New-Item -Path '{path}\\Alfa\\Beta' -Force | Out-Null; "
        f"New-ItemProperty -Path '{path}\\Alfa' -Name v -Value 'segreto-da-non-leggere' | Out-Null"
    )
    subprocess.run([_powershell(), "-NoProfile", "-Command", create], check=True, capture_output=True)
    try:
        yield path
    finally:
        subprocess.run(
            [_powershell(), "-NoProfile", "-Command", f"Remove-Item -Path '{path}' -Recurse -Force"],
            capture_output=True,
        )


def _snapshot(tmp_path, roots, registry_root, name="s.txt") -> tuple[Path, subprocess.CompletedProcess]:
    local, start = roots
    out = tmp_path / "out" / name
    out.parent.mkdir(exist_ok=True)
    result = _run("-Out", str(out), "-LocalAppData", str(local), "-StartMenu", str(start),
                  "-RegistryRoot", registry_root)
    return out, result


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8-sig").splitlines()


def test_snapshot_lists_files_folders_and_key_names_only(tmp_path, roots, registry_root):
    out, result = _snapshot(tmp_path, roots, registry_root)
    assert result.returncode == 0, result.stdout + result.stderr
    lines = _lines(out)
    assert "LOCALAPPDATA\tD\tOCR2" in lines
    assert "LOCALAPPDATA\tD\tOCR2\\edge-profile" in lines
    assert "LOCALAPPDATA\tF\tOCR2\\data.bin\t10" in lines
    assert "LOCALAPPDATA\tF\tOther\\b.txt\t2" in lines
    assert "STARTMENU\tD\tPrograms" in lines
    assert "HKCU\tK\tAlfa" in lines
    assert "HKCU\tK\tAlfa\\Beta" in lines
    assert "segreto-da-non-leggere" not in out.read_text(encoding="utf-8-sig")


def test_snapshot_is_sorted_and_deterministic(tmp_path, roots, registry_root):
    first, _ = _snapshot(tmp_path, roots, registry_root, "a.txt")
    second, _ = _snapshot(tmp_path, roots, registry_root, "b.txt")
    assert first.read_bytes() == second.read_bytes()
    body = [line for line in _lines(first) if not line.startswith("#")]
    assert body == sorted(body, key=lambda text: text.encode("utf-16-be"))


def test_snapshot_is_read_only_outside_out_file(tmp_path, roots, registry_root):
    local, start = roots

    def tree():
        return sorted(
            (str(p), p.stat().st_size, p.stat().st_mtime_ns)
            for root in (local, start) for p in root.rglob("*")
        )

    before = tree()
    out, result = _snapshot(tmp_path, roots, registry_root)
    assert result.returncode == 0
    assert tree() == before
    assert out.is_file() and sorted(p.name for p in out.parent.iterdir()) == ["s.txt"]


def test_compare_prints_only_differences(tmp_path, roots, registry_root):
    local, _ = roots
    before, _ = _snapshot(tmp_path, roots, registry_root, "before.txt")
    same = _run("-Compare", str(before), str(before))
    assert same.returncode == 0
    assert [line for line in same.stdout.splitlines() if line.strip().startswith(("+", "-", "~"))] == []

    (local / "OCR2" / "new.txt").write_text("n")
    (local / "Other" / "b.txt").unlink()
    (local / "OCR2" / "data.bin").write_bytes(b"x" * 11)
    after, _ = _snapshot(tmp_path, roots, registry_root, "after.txt")
    diff = _run("-Compare", str(before), str(after))
    assert diff.returncode == 0, diff.stdout + diff.stderr
    changes = [line for line in diff.stdout.splitlines() if line[:1] in "+-~" and line.strip()]
    assert sorted(changes) == sorted([
        "+ LOCALAPPDATA\tF\tOCR2\\new.txt\t1",
        "- LOCALAPPDATA\tF\tOther\\b.txt\t2",
        "~ LOCALAPPDATA\tF\tOCR2\\data.bin\t10 -> 11",
    ])
    assert "Alfa" not in diff.stdout  # unchanged entries are not echoed


def test_access_denied_folder_is_reported_not_fatal(tmp_path, roots, registry_root):
    local, _ = roots
    locked = local / "Locked"
    (locked / "inner").mkdir(parents=True)
    grant = subprocess.run(["icacls", str(locked), "/deny", "*S-1-1-0:(RD)"], capture_output=True, text=True)
    if grant.returncode != 0:
        pytest.skip("cannot set a deny ACL here")
    try:
        try:
            list(os.scandir(locked))
        except PermissionError:
            pass
        else:
            pytest.skip("deny ACL has no effect for this account")
        out, result = _snapshot(tmp_path, roots, registry_root)
        assert result.returncode == 0, result.stdout + result.stderr
        lines = _lines(out)
        assert "LOCALAPPDATA\tD\tLocked" in lines
        assert "LOCALAPPDATA\tDENIED\tLocked" in lines
        assert "LOCALAPPDATA\tF\tOther\\b.txt\t2" in lines
    finally:
        subprocess.run(["icacls", str(locked), "/remove:d", "*S-1-1-0"], capture_output=True)
