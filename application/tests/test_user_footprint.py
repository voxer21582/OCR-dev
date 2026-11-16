"""installer/user-footprint.ps1 on synthetic user folders (REQ-102, REQ-104; from #151).

The script lists file and folder names under %LOCALAPPDATA% and the Start menu
and the names of the keys directly under HKCU\\Software, never values or file
contents; ``-Compare`` prints only the names added (``+``) or removed (``-``).
The tests point LOCALAPPDATA and APPDATA at temporary folders, only read the
registry and run only on Windows (Windows PowerShell, as on the clean PC).
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "installer" / "user-footprint.ps1"
pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="user-footprint.ps1 is a Windows PowerShell script")


def _powershell() -> str:
    return shutil.which("powershell") or shutil.which("pwsh") or "powershell"


def _run(command: str, env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_powershell(), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command",
         "[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false); " + command],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180, env=env,
    )


def _quote(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"


@pytest.fixture()
def profile(tmp_path):
    local = tmp_path / "local"
    roaming = tmp_path / "roaming"
    (local / "OCR2" / "edge-profile").mkdir(parents=True)
    (local / "OCR2" / "document-archive.sqlite3").write_text("contenuto-segreto-di-prova", encoding="utf-8")
    (local / "Programs" / "OCR2" / "versions" / "0.6.0").mkdir(parents=True)
    (local / "Altro").mkdir()
    (local / "Altro" / "b.txt").write_text("bb", encoding="utf-8")
    start = roaming / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "OCR2"
    start.mkdir(parents=True)
    (start / "OCR2.lnk").write_bytes(b"synthetic")
    env = dict(os.environ, LOCALAPPDATA=str(local), APPDATA=str(roaming))
    out = tmp_path / "out"
    out.mkdir()
    return local, roaming, env, out


def _capture(profile, name: str) -> tuple[Path, subprocess.CompletedProcess]:
    _, _, env, out = profile
    target = out / name
    return target, _run(f"& {_quote(_SCRIPT)} -Out {_quote(target)}", env)


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8-sig").splitlines()


def test_capture_lists_names_only_under_the_user_roots(profile):
    target, result = _capture(profile, "prima.txt")
    assert result.returncode == 0, result.stdout + result.stderr
    lines = _lines(target)
    for expected in (
        "LOCALAPPDATA|DIR|OCR2",
        "LOCALAPPDATA|DIR|OCR2\\edge-profile",
        "LOCALAPPDATA|FILE|OCR2\\document-archive.sqlite3",
        "LOCALAPPDATA|DIR|Programs\\OCR2\\versions\\0.6.0",
        "LOCALAPPDATA|FILE|Altro\\b.txt",
        "START_MENU|DIR|Programs\\OCR2",
        "START_MENU|FILE|Programs\\OCR2\\OCR2.lnk",
    ):
        assert expected in lines
    assert any(line.startswith("HKCU_SOFTWARE|KEY|") for line in lines)
    assert "contenuto-segreto-di-prova" not in target.read_text(encoding="utf-8-sig")
    assert str(profile[0]) not in target.read_text(encoding="utf-8-sig")


def test_capture_is_deterministic_and_has_no_duplicates(profile):
    first, _ = _capture(profile, "a.txt")
    second, _ = _capture(profile, "b.txt")
    assert first.read_bytes() == second.read_bytes()
    lines = _lines(first)
    assert len(lines) == len(set(lines))


def test_capture_writes_only_the_out_file(profile):
    local, roaming, _, out = profile

    def tree():
        return sorted(
            (str(path), path.stat().st_size, path.stat().st_mtime_ns)
            for root in (local, roaming) for path in root.rglob("*")
        )

    before = tree()
    target, result = _capture(profile, "s.txt")
    assert result.returncode == 0, result.stdout + result.stderr
    assert tree() == before
    assert [path.name for path in out.iterdir()] == ["s.txt"]


def test_compare_prints_only_added_and_removed_names(profile):
    local, _, env, _ = profile
    before, _ = _capture(profile, "prima.txt")
    same = _run(f"& {_quote(_SCRIPT)} -Compare @({_quote(before)},{_quote(before)})", env)
    assert same.returncode == 0, same.stdout + same.stderr
    assert same.stdout.strip() == ""

    (local / "OCR2" / "instance.json").write_text("{}", encoding="utf-8")
    (local / "Altro" / "b.txt").unlink()
    # A content-only change keeps the same name: the comparison does not see it.
    (local / "OCR2" / "document-archive.sqlite3").write_text("altro contenuto, più lungo", encoding="utf-8")
    after, _ = _capture(profile, "dopo.txt")
    diff = _run(f"& {_quote(_SCRIPT)} -Compare @({_quote(before)},{_quote(after)})", env)
    assert diff.returncode == 0, diff.stdout + diff.stderr
    assert sorted(line for line in diff.stdout.splitlines() if line.strip()) == [
        "+ LOCALAPPDATA|FILE|OCR2\\instance.json",
        "- LOCALAPPDATA|FILE|Altro\\b.txt",
    ]


def test_compare_output_can_be_filtered_to_ocr2_lines(profile):
    """The procedure shares only the lines naming OCR2 (Select-String -Pattern 'OCR2')."""
    local, _, env, out = profile
    before, _ = _capture(profile, "prima.txt")
    shutil.rmtree(local / "OCR2")
    (local / "Altro" / "c.txt").write_text("c", encoding="utf-8")
    after, _ = _capture(profile, "dopo.txt")
    filtered = out / "confronto-ocr2.txt"
    command = (
        f"& {_quote(_SCRIPT)} -Compare @({_quote(before)},{_quote(after)}) | "
        f"Select-String -Pattern 'OCR2' | ForEach-Object {{ $_.Line }} | Set-Content -LiteralPath {_quote(filtered)} -Encoding UTF8"
    )
    result = _run(command, env)
    assert result.returncode == 0, result.stdout + result.stderr
    lines = _lines(filtered)
    assert lines and all("OCR2" in line for line in lines)
    assert "- LOCALAPPDATA|DIR|OCR2" in lines
    assert not any("Altro" in line for line in lines)


def test_capture_refuses_without_user_folders(profile):
    _, _, env, out = profile
    env = dict(env, LOCALAPPDATA="")
    result = _run(f"& {_quote(_SCRIPT)} -Out {_quote(out / 'x.txt')}", env)
    assert result.returncode != 0
    assert "Cartelle utente non disponibili." in result.stdout + result.stderr
    assert not (out / "x.txt").exists()


def test_unreadable_folder_is_reported_as_incomplete(profile):
    """Windows PowerShell 5.1 reads a script without BOM as ANSI: the warning must stay readable."""
    local, _, _, _ = profile
    locked = local / "Bloccata"
    (locked / "interna").mkdir(parents=True)
    deny = subprocess.run(["icacls", str(locked), "/deny", "*S-1-1-0:(RD)"], capture_output=True, text=True)
    if deny.returncode != 0:
        pytest.skip("cannot set a deny ACL here")
    try:
        try:
            list(os.scandir(locked))
        except PermissionError:
            pass
        else:
            pytest.skip("the deny ACL has no effect for this account")
        target, result = _capture(profile, "s.txt")
        assert result.returncode == 0, result.stdout + result.stderr
        assert "l'inventario è incompleto" in result.stdout + result.stderr
        lines = _lines(target)
        assert "LOCALAPPDATA|DIR|Bloccata" in lines
        assert "LOCALAPPDATA|FILE|Altro\\b.txt" in lines
    finally:
        subprocess.run(["icacls", str(locked), "/remove:d", "*S-1-1-0"], capture_output=True)
