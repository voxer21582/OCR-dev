"""Static checks of the two NSIS scripts and the installer build helper (M6 Task 8, V4, DEC-032).

``installer/ocr2.nsi`` (per-user installer and uninstaller) and
``installer/launcher.nsi`` (``OCR2.exe``, R6) must never touch the registry, ask
for administrator rights, write outside the per-user folders or contain a URL.
``build_installer`` is exercised with synthetic zips only (no makensis run).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

import pytest

_REPOSITORY = Path(__file__).resolve().parents[2]
_INSTALLER = _REPOSITORY / "installer"
sys.path.insert(0, str(_INSTALLER))

import build_installer  # noqa: E402
import build_payload  # noqa: E402
from alfa_document_intelligence.runtime_manifest import MANIFEST_NAME, build_manifest, write_manifest  # noqa: E402

_SCRIPTS = ("ocr2.nsi", "launcher.nsi")
_FORBIDDEN = (
    re.compile(r"WriteReg", re.IGNORECASE),
    re.compile(r"DeleteReg", re.IGNORECASE),
    re.compile(r"RequestExecutionLevel\s+(admin|highest)", re.IGNORECASE),
    re.compile(r"\$PROGRAMFILES", re.IGNORECASE),
    re.compile(r"\$WINDIR", re.IGNORECASE),
    re.compile(r"\$SYSDIR", re.IGNORECASE),
    re.compile(r"SetShellVarContext\s+all", re.IGNORECASE),
    re.compile(r"https?:", re.IGNORECASE),
    re.compile(r"WriteINIStr", re.IGNORECASE),
)


def _text(name: str) -> str:
    return (_INSTALLER / name).read_text(encoding="utf-8")


def _code_lines(name: str) -> list[str]:
    """Script lines without comments (``;`` or ``#`` at the start)."""
    return [line.strip() for line in _text(name).splitlines() if line.strip() and not line.strip().startswith((";", "#"))]


@pytest.mark.parametrize("name", _SCRIPTS)
def test_script_has_no_registry_admin_system_paths_or_urls(name):
    text = _text(name)
    for pattern in _FORBIDDEN:
        assert pattern.search(text) is None, f"{name}: {pattern.pattern}"
    assert re.search(r"^RequestExecutionLevel user$", text, re.MULTILINE)
    assert re.search(r"^Unicode true$", text, re.MULTILINE)


def test_installer_uses_the_per_user_folder_and_italian():
    text = _text("ocr2.nsi")
    assert 'InstallDir "$LOCALAPPDATA\\Programs\\OCR2"' in text
    assert "SetShellVarContext current" in text
    assert '!insertmacro MUI_LANGUAGE "Italian"' in text
    # $LOCALAPPDATA only for the install folder (and the test-build guard against it): data is never deleted by NSIS.
    for line in _code_lines("ocr2.nsi"):
        if "$LOCALAPPDATA" in line:
            assert "Programs\\OCR2" in line, line


def test_installer_extracts_activates_and_cleans_up_only_its_version():
    text = _text("ocr2.nsi")
    assert 'SetOutPath "$INSTDIR\\versions\\${VERSION}"' in text
    assert 'File /r "${PAYLOAD_DIR}\\*.*"' in text
    assert "-B -m alfa_document_intelligence.install_state activate ${VERSION}" in text
    assert 'WriteUninstaller "$INSTDIR\\uninstall.exe"' in text
    assert "Questa versione di OCR2 è già installata." in text  # R7
    for line in _code_lines("ocr2.nsi"):
        if line.upper().startswith("RMDIR /R"):
            assert line.startswith('RMDir /r "$INSTDIR\\versions'), line
    lines = _code_lines("ocr2.nsi")
    extract = lines.index('File /r "${PAYLOAD_DIR}\\*.*"')
    leftover = lines.index('RMDir /r "$INSTDIR\\versions\\${VERSION}"')
    assert leftover < extract  # R7: a non-active leftover is deleted before extracting


def test_failed_activation_never_deletes_the_version_active_txt_names():
    lines = _code_lines("ocr2.nsi")
    activate = next(i for i, line in enumerate(lines) if "install_state activate ${VERSION}" in line)
    failure = lines.index('${If} $0 != "0"', activate)
    cleanup = lines.index('RMDir /r "$INSTDIR\\versions\\${VERSION}"', failure)
    branch = lines[failure:cleanup]
    # active.txt is read again; if it names this version the branch aborts before the delete.
    assert branch[1] == "Call ReadActive" and branch[2] == '${If} $R0 == "${VERSION}"'
    inner = branch[2:branch.index("${EndIf}")]
    assert "Abort" in inner and not any("Resta attiva la versione precedente" in line for line in inner)
    assert any("Resta attiva la versione precedente" in line for line in branch[branch.index("${EndIf}"):])


def test_shortcuts_only_outside_test_builds_and_only_to_fixed_targets():
    lines = _code_lines("ocr2.nsi")
    depth_test = []
    shortcuts = []
    for line in lines:
        if line.startswith(("!ifdef", "!ifndef")):
            depth_test.append(line == "!ifndef OCR2_TEST")
        elif line == "!endif":
            depth_test.pop()
        elif line == "!else" and depth_test:
            depth_test[-1] = not depth_test[-1]
        elif line.startswith(("CreateShortcut", "CreateDirectory")):
            assert depth_test and depth_test[-1], f"outside !ifndef OCR2_TEST: {line}"
            shortcuts.append(line)
    assert shortcuts == [
        'CreateDirectory "$SMPROGRAMS\\OCR2"',
        'CreateShortcut "$SMPROGRAMS\\OCR2\\OCR2.lnk" "$INSTDIR\\OCR2.exe"',
        'CreateShortcut "$SMPROGRAMS\\OCR2\\Torna alla versione precedente.lnk" "$INSTDIR\\OCR2.exe" "/rollback"',
        'CreateShortcut "$SMPROGRAMS\\OCR2\\Disinstalla OCR2.lnk" "$INSTDIR\\uninstall.exe"',
    ]


def test_uninstaller_asks_about_data_and_deletes_it_only_through_install_state():
    text = _text("ocr2.nsi")
    assert "MB_YESNO" in text and "MB_DEFBUTTON2" in text and "/SD IDNO" in text
    assert "Eliminare anche i dati di OCR2 (archivio e catalogo)?" in text
    assert '"/REMOVEDATA"' in text
    assert "-B -m alfa_document_intelligence.install_state uninstall" in text
    assert "--remove-data" in text and '--test-data-root "${OCR2_TEST_DATA_ROOT}"' in text
    # The uninstaller removes only the program's own items.
    deletes = [line for line in _code_lines("ocr2.nsi") if line.startswith(("Delete ", "RMDir "))]
    for line in deletes:
        assert line.startswith(('Delete "$INSTDIR\\', 'RMDir "$INSTDIR"', 'RMDir /r "$INSTDIR\\versions', 'Delete "$SMPROGRAMS\\OCR2\\', 'RMDir "$SMPROGRAMS\\OCR2"')), line


def test_launcher_reads_active_txt_and_starts_the_active_version():
    text = _text("launcher.nsi")
    assert re.search(r"^SilentInstall silent$", text, re.MULTILINE)
    assert '"$EXEDIR\\active.txt"' in text
    assert (
        "Exec '\"$EXEDIR\\versions\\$R0\\python\\pythonw.exe\" -B -m alfa_document_intelligence "
        "--app-window --ocr-engine rapidocr-v6'"
    ) in text
    assert '"/rollback"' in text
    assert "-B -m alfa_document_intelligence.install_state rollback" in text
    # Quit alone exits with code 2: a successful rollback says 0 explicitly.
    assert re.search(r'MessageBox MB_ICONINFORMATION "\$3"\s+SetErrorLevel 0', text)
    assert not re.search(r"^\s*File\s", text, re.MULTILINE)  # no files: a stub only


def _nsis_zip(folder: Path, version: str = "9.99", members: dict | None = None) -> tuple[Path, dict]:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"nsis-{version}.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in (members or {f"nsis-{version}/makensis.exe": b"MZ synthetic", f"nsis-{version}/Include/MUI2.nsh": b";"}).items():
            archive.writestr(name, data)
    data = path.read_bytes()
    pin = {"file": path.name, "version": version, "size": len(data), "sha256": hashlib.sha256(data).hexdigest(), "url": "x"}
    return path, pin


def test_unpack_nsis_checks_the_pin_first(tmp_path):
    cache = tmp_path / "cache"
    _path, pin = _nsis_zip(cache)
    makensis = build_installer.unpack_nsis(pin, cache)
    assert makensis == cache / "nsis-9.99" / "makensis.exe" and makensis.read_bytes() == b"MZ synthetic"
    (cache / "nsis-9.99" / "planted.exe").write_bytes(b"x")
    build_installer.unpack_nsis(pin, cache)  # always unpacked afresh
    assert not (cache / "nsis-9.99" / "planted.exe").exists()
    with pytest.raises(build_payload.PinMismatchError):
        build_installer.unpack_nsis(dict(pin, sha256="0" * 64), cache)


def test_unpack_nsis_refuses_paths_outside_its_folder(tmp_path):
    cache = tmp_path / "cache"
    _path, pin = _nsis_zip(cache, members={"nsis-9.99/makensis.exe": b"MZ", "nsis-9.99/../../evil.txt": b"x"})
    with pytest.raises(build_payload.BuildError):
        build_installer.unpack_nsis(pin, cache)
    assert not (tmp_path / "evil.txt").exists()


def _payload(out: Path, version: str) -> Path:
    folder = out / version
    (folder / "python").mkdir(parents=True)
    (folder / "python" / "python.exe").write_bytes(b"MZ")
    write_manifest(build_manifest(folder, version=version, excluded_globs=()), folder / MANIFEST_NAME)
    return folder


def test_payload_must_verify_and_match_the_version(tmp_path):
    folder = _payload(tmp_path, "0.6.1")
    build_installer.check_payload(folder, "0.6.1")
    with pytest.raises(build_payload.BuildError, match="versione"):
        build_installer.check_payload(folder, "0.6.2")
    (folder / "python" / "python.exe").write_bytes(b"tampered")
    with pytest.raises(build_payload.BuildError, match="File alterato"):
        build_installer.check_payload(folder, "0.6.1")
    with pytest.raises(build_payload.BuildError):
        build_installer.check_payload(tmp_path / "missing", "0.6.1")


def test_makensis_commands_for_release_and_test_builds(tmp_path):
    makensis = tmp_path / "nsis" / "makensis.exe"
    payload = tmp_path / "out" / "0.6.1"
    out = tmp_path / "out"
    launcher, installer = build_installer.makensis_commands(makensis, "0.6.1", payload, out)
    assert launcher[0] == str(makensis) and launcher[-1] == str(_INSTALLER / "launcher.nsi")
    assert f"-DOUTFILE={out / 'launcher' / 'OCR2.exe'}" in launcher
    assert installer[-1] == str(_INSTALLER / "ocr2.nsi")
    assert "-DVERSION=0.6.1" in installer and f"-DPAYLOAD_DIR={payload}" in installer
    assert f"-DLAUNCHER_EXE={out / 'launcher' / 'OCR2.exe'}" in installer
    assert f"-DOUTFILE={out / 'OCR2-0.6.1-setup.exe'}" in installer
    assert not any(argument.startswith("-DOCR2_TEST") for argument in installer)
    test_root = tmp_path / "scratch"
    _launcher, test_installer = build_installer.makensis_commands(makensis, "0.6.1", payload, out, test_data_root=test_root)
    assert "-DOCR2_TEST" in test_installer and f"-DOCR2_TEST_DATA_ROOT={test_root}" in test_installer
    assert f"-DOUTFILE={out / 'OCR2-0.6.1-setup-test.exe'}" in test_installer
    with pytest.raises(build_payload.BuildError):
        build_installer.makensis_commands(makensis, "0.6", payload, out)


def test_build_installer_main_requires_a_test_root_for_test_builds(capsys):
    with pytest.raises(SystemExit):
        build_installer.main(["--version", "0.6.1", "--test"])
    assert "--test-data-root" in capsys.readouterr().err


def test_pins_name_the_nsis_version_unpacked():
    pins = json.loads((_INSTALLER / "pins.json").read_text(encoding="utf-8"))
    assert pins["nsis"]["version"] == "3.13" and pins["nsis"]["file"] == "nsis-3.13.zip"
