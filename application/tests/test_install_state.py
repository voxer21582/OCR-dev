"""Installed-version state used by the NSIS installer (M6 Task 8, REQ-102, REQ-104, REQ-106).

Synthetic version folders under ``tmp_path``: each has a tiny ``python/`` and
``app/`` and a manifest built by ``runtime_manifest.build_manifest``.  No real
installation and no real ``%LOCALAPPDATA%`` is touched: ``LOCALAPPDATA`` points
into ``tmp_path`` for every test.
"""
from __future__ import annotations

import functools
import hashlib
import os
from pathlib import Path
import sqlite3
import subprocess

import pytest

from alfa_document_intelligence import __main__ as launcher
from alfa_document_intelligence import install_state
from alfa_document_intelligence.install_state import InstallStateError
from alfa_document_intelligence.runtime_manifest import MANIFEST_NAME, build_manifest, write_manifest
from test_local_document_store import SyntheticProtector


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr(install_state, "running_instance", lambda _data_dir: None)


def _version(base: Path, version: str) -> Path:
    folder = base / "versions" / version
    (folder / "python").mkdir(parents=True)
    (folder / "python" / "python.exe").write_bytes(b"MZ synthetic " + version.encode())
    package = folder / "app" / "alfa_document_intelligence"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(f'__version__ = "{version}"\n', encoding="utf-8")
    write_manifest(build_manifest(folder, version=version, excluded_globs=()), folder / MANIFEST_NAME)
    return folder


def _link_dir(link: Path, target: Path) -> None:
    """Directory symlink, or an NTFS junction on Windows where symlinks need a privilege."""
    try:
        os.symlink(target, link, target_is_directory=True)
        return
    except (OSError, NotImplementedError):
        if os.name != "nt":
            pytest.skip("symbolic links are not available")
    made = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True)
    assert made.returncode == 0, made.stderr


def _state(base: Path) -> str:
    return (base / "active.txt").read_text(encoding="utf-8")


def test_activate_switches_only_after_verification(tmp_path):
    base = tmp_path / "Programs" / "OCR2"
    _version(base, "0.6.0")
    install_state.activate(base, "0.6.0")
    assert _state(base) == "0.6.0\n\n"
    _version(base, "0.6.1")
    install_state.activate(base, "0.6.1")
    assert _state(base) == "0.6.1\n0.6.0\n"
    assert install_state.read_state(base) == ("0.6.1", "0.6.0")
    # Activating the active version again keeps the previous one.
    install_state.activate(base, "0.6.1")
    assert _state(base) == "0.6.1\n0.6.0\n"


def test_activate_failure_keeps_previous_active(tmp_path):
    base = tmp_path / "OCR2"
    _version(base, "0.6.0")
    install_state.activate(base, "0.6.0")
    before = (base / "active.txt").read_bytes()
    folder = _version(base, "0.6.1")
    (folder / "app" / "alfa_document_intelligence" / "__init__.py").write_text("tampered", encoding="utf-8")
    with pytest.raises(InstallStateError) as error:
        install_state.activate(base, "0.6.1")
    assert "File alterato: app/alfa_document_intelligence/__init__.py" in str(error.value)
    assert (base / "active.txt").read_bytes() == before
    with pytest.raises(InstallStateError, match="non è presente"):
        install_state.activate(base, "0.9.9")
    with pytest.raises(InstallStateError, match="Versione non valida"):
        install_state.activate(base, "..\\0.6.0")
    assert (base / "active.txt").read_bytes() == before


def test_interrupted_activation_leaves_valid_active_txt(monkeypatch, tmp_path):
    base = tmp_path / "OCR2"
    _version(base, "0.6.0")
    install_state.activate(base, "0.6.0")
    before = (base / "active.txt").read_bytes()
    _version(base, "0.6.1")

    def interrupted(_source, _target):
        raise OSError("simulated power loss before the replace")

    monkeypatch.setattr(install_state.os, "replace", interrupted)
    with pytest.raises(InstallStateError):
        install_state.activate(base, "0.6.1")
    assert (base / "active.txt").read_bytes() == before
    assert install_state.read_state(base) == ("0.6.0", "")
    assert not (base / "active.txt.tmp").exists()


def test_rollback_returns_to_previous(tmp_path):
    base = tmp_path / "OCR2"
    _version(base, "0.6.0")
    install_state.activate(base, "0.6.0")
    with pytest.raises(InstallStateError, match="Nessuna versione precedente disponibile."):
        install_state.rollback(base)
    _version(base, "0.6.1")
    install_state.activate(base, "0.6.1")
    assert install_state.rollback(base) == "0.6.0"
    assert _state(base) == "0.6.0\n0.6.1\n"
    assert install_state.rollback(base) == "0.6.1"
    # A previous version whose files no longer verify is refused, state unchanged.
    (base / "versions" / "0.6.0" / "python" / "python.exe").write_bytes(b"broken")
    with pytest.raises(InstallStateError, match="File alterato"):
        install_state.rollback(base)
    assert _state(base) == "0.6.1\n0.6.0\n"


def test_prune_keeps_two_versions(tmp_path):
    base = tmp_path / "OCR2"
    (base / "versions" / "notes").mkdir(parents=True)
    _version(base, "0.6.0")
    install_state.activate(base, "0.6.0")
    _version(base, "0.6.1")
    install_state.activate(base, "0.6.1")
    assert sorted(path.name for path in (base / "versions").iterdir()) == ["0.6.0", "0.6.1", "notes"]
    _version(base, "0.6.2")
    install_state.activate(base, "0.6.2")  # prunes to active + previous
    assert sorted(path.name for path in (base / "versions").iterdir()) == ["0.6.1", "0.6.2", "notes"]
    _version(base, "0.6.0")
    assert install_state.prune(base) == ["0.6.0"]
    assert install_state.prune(base) == []
    assert sorted(path.name for path in (base / "versions").iterdir()) == ["0.6.1", "0.6.2", "notes"]


def test_prune_without_state_refuses(tmp_path):
    base = tmp_path / "OCR2"
    _version(base, "0.6.0")
    with pytest.raises(InstallStateError, match="Nessuna versione attiva"):
        install_state.prune(base)
    assert (base / "versions" / "0.6.0").is_dir()
    (base / "active.txt").write_text("../../evil\n\n", encoding="utf-8")
    with pytest.raises(InstallStateError, match="non leggibile"):
        install_state.prune(base)
    assert (base / "versions" / "0.6.0").is_dir()


def test_prune_uninstall_and_activate_refuse_while_running(monkeypatch, tmp_path, capsys):
    base = tmp_path / "OCR2"
    _version(base, "0.6.1")
    install_state.activate(base, "0.6.1")
    _version(base, "0.6.2")
    install_state.activate(base, "0.6.2")
    _version(base, "0.6.0")
    data = tmp_path / "local" / "OCR2"
    data.mkdir(parents=True)
    (data / "document-archive.sqlite3").write_bytes(b"synthetic")
    seen = []
    monkeypatch.setattr(install_state, "running_instance", lambda data_dir: seen.append(data_dir) or 51234)
    before = _state(base)
    with pytest.raises(InstallStateError, match="Chiudi OCR2 con Esci e riprova."):
        install_state.prune(base)
    with pytest.raises(InstallStateError, match="Chiudi OCR2 con Esci e riprova."):
        install_state.activate(base, "0.6.0")
    assert (base / "versions" / "0.6.0").is_dir() and _state(base) == before
    assert install_state.main(["uninstall", "--remove-data", "--base", str(base)]) != 0
    assert "Chiudi OCR2 con Esci e riprova." in capsys.readouterr().err
    assert (data / "document-archive.sqlite3").is_file()
    assert seen and all(path == data for path in seen)


def test_uninstall_keeps_data_by_default(tmp_path):
    base = tmp_path / "Programs" / "OCR2"
    _version(base, "0.6.0")
    install_state.activate(base, "0.6.0")
    data = tmp_path / "local" / "OCR2"
    data.mkdir(parents=True)
    (data / "document-archive.sqlite3").write_bytes(b"synthetic archive")
    assert install_state.main(["uninstall", "--base", str(base)]) == 0
    assert (data / "document-archive.sqlite3").read_bytes() == b"synthetic archive"


def test_uninstall_remove_data_deletes_only_ocr2_data(tmp_path, capsys):
    local = tmp_path / "local"
    data = local / "OCR2"
    (data / "edge-profile" / "Default").mkdir(parents=True)
    (data / "document-archive.sqlite3").write_bytes(b"synthetic archive")
    (data / "edge-profile" / "Default" / "Preferences").write_text("{}", encoding="utf-8")
    (local / "OCR2-other").mkdir()
    (local / "OCR2-other" / "keep.txt").write_text("keep", encoding="utf-8")
    (local / "keep.txt").write_text("keep", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "precious.txt").write_text("keep", encoding="utf-8")
    _link_dir(data / "edge-profile" / "linked", outside)
    base = tmp_path / "Programs" / "OCR2"
    _version(base, "0.6.0")
    # A test root that does not contain the data folder: refused, nothing deleted.
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    assert install_state.main(["uninstall", "--remove-data", "--test-data-root", str(elsewhere), "--base", str(base)]) != 0
    assert "fuori dalla cartella di prova" in capsys.readouterr().err
    assert (data / "document-archive.sqlite3").is_file()
    assert install_state.main(["uninstall", "--remove-data", "--test-data-root", str(tmp_path), "--base", str(base)]) == 0
    assert not data.exists()
    assert (local / "OCR2-other" / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert (local / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert (outside / "precious.txt").read_text(encoding="utf-8") == "keep"  # link inside removed, not followed
    assert (base / "versions" / "0.6.0").is_dir()  # the program files are removed by NSIS, not here
    # Already gone: nothing to do, success.
    assert install_state.main(["uninstall", "--remove-data", "--base", str(base)]) == 0


def test_uninstall_remove_data_refuses_link_and_missing_localappdata(monkeypatch, tmp_path, capsys):
    target = tmp_path / "real-data"
    target.mkdir()
    (target / "precious.txt").write_text("keep", encoding="utf-8")
    local = tmp_path / "local"
    local.mkdir()
    _link_dir(local / "OCR2", target)
    base = tmp_path / "OCR2"
    assert install_state.main(["uninstall", "--remove-data", "--base", str(base)]) != 0
    assert "collegamento" in capsys.readouterr().err
    assert (target / "precious.txt").read_text(encoding="utf-8") == "keep"
    assert (local / "OCR2").exists()
    monkeypatch.delenv("LOCALAPPDATA")
    assert install_state.main(["uninstall", "--remove-data", "--base", str(base)]) != 0
    assert "LOCALAPPDATA" in capsys.readouterr().err
    monkeypatch.setenv("LOCALAPPDATA", "relative")
    assert install_state.main(["uninstall", "--remove-data", "--base", str(base)]) != 0


def test_uninstall_remove_data_refuses_a_file_named_ocr2(tmp_path, capsys):
    local = tmp_path / "local"
    local.mkdir()
    (local / "OCR2").write_bytes(b"not a folder")
    assert install_state.main(["uninstall", "--remove-data", "--base", str(tmp_path / "OCR2")]) != 0
    assert "non è una cartella" in capsys.readouterr().err
    assert (local / "OCR2").read_bytes() == b"not a folder"


def test_main_activate_rollback_prune_print_italian_messages(tmp_path, capsys):
    base = tmp_path / "OCR2"
    _version(base, "0.6.0")
    assert install_state.main(["activate", "0.6.0", "--base", str(base)]) == 0
    _version(base, "0.6.1")
    assert install_state.main(["activate", "0.6.1", "--base", str(base)]) == 0
    assert "Versione attiva: 0.6.1" in capsys.readouterr().out
    assert install_state.main(["rollback", "--base", str(base)]) == 0
    assert "Versione attiva: 0.6.0" in capsys.readouterr().out
    assert install_state.main(["prune", "--base", str(base)]) == 0
    assert install_state.main(["activate", "x.y", "--base", str(base)]) != 0
    assert "Versione non valida" in capsys.readouterr().err


def test_base_is_derived_from_the_installed_package(tmp_path):
    base = tmp_path / "Programs" / "OCR2"
    package_file = base / "versions" / "0.6.0" / "app" / "alfa_document_intelligence" / "__init__.py"
    assert install_state.installed_base(package_file) == base
    with pytest.raises(InstallStateError, match="programma installato"):
        install_state.installed_base(tmp_path / "src" / "alfa_document_intelligence" / "__init__.py")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_older_version_refuses_newer_archive_schema(monkeypatch, tmp_path, capsys):
    data = tmp_path / "local" / "OCR2"
    data.mkdir(parents=True)
    archive = data / "document-archive.sqlite3"
    with sqlite3.connect(archive) as connection:
        connection.execute("CREATE TABLE future (value TEXT)")
        connection.execute("PRAGMA user_version = 99")
    connection.close()
    before = _sha256(archive)
    names_before = sorted(path.name for path in data.iterdir())
    monkeypatch.setattr(launcher, "LocalDocumentStore", functools.partial(launcher.LocalDocumentStore, protector=SyntheticProtector()))
    opened = []
    monkeypatch.setattr(launcher.webbrowser, "open", lambda url: opened.append(url) or True)
    with pytest.raises(SystemExit) as exit_info:
        launcher._open_archive(archive, app_window=True)
    assert exit_info.value.code == 2
    message = "Questo archivio è stato aggiornato da una versione più recente di OCR2. Reinstalla quella versione."
    assert message in capsys.readouterr().err
    page = (data / "runtime-error.html").read_text(encoding="utf-8")
    assert message in page and "<script" not in page.lower()
    assert opened == [(data / "runtime-error.html").resolve().as_uri()]
    assert _sha256(archive) == before
    assert sorted(path.name for path in data.iterdir()) == sorted(names_before + ["runtime-error.html"])
    # Any other schema problem is not reported as a newer archive.
    other = data / "other.sqlite3"
    with sqlite3.connect(other) as connection:
        connection.execute("CREATE TABLE unknown (value TEXT)")
    connection.close()
    with pytest.raises(launcher.StoreSchemaError):
        launcher._open_archive(other, app_window=False)
