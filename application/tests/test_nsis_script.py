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


def test_reinstall_refusal_gives_the_remedies_that_work():
    # R38: no in-place repair; the refusal names the working remedies.
    line = next(line for line in _code_lines("ocr2.nsi") if "Questa versione di OCR2 è già installata." in line)
    assert "Torna alla versione precedente" in line
    assert "disinstalla OCR2 mantenendo i dati" in line and "installalo di nuovo" in line


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


# --- Task 9: optional signing hooks (REQ-105) -------------------------------

_THUMB = "A1B2C3D4E5F60718293A4B5C6D7E8F9012345678"
_TS = "http://timestamp.example.test/ts"


def _sign_commands(tmp_path, **kwargs):
    makensis = tmp_path / "nsis" / "makensis.exe"
    return build_installer.makensis_commands(
        makensis, "0.6.1", tmp_path / "out" / "0.6.1", tmp_path / "out",
        sign_thumbprint=_THUMB, timestamp_url=_TS, **kwargs,
    )


def test_unsigned_build_has_no_signing_defines_and_scripts_gate_hooks_on_them(tmp_path):
    makensis = tmp_path / "nsis" / "makensis.exe"
    launcher, installer = build_installer.makensis_commands(makensis, "0.6.1", tmp_path / "p", tmp_path / "out")
    assert not any("SIGN" in a or "TIMESTAMP" in a for a in launcher + installer)
    for name, hooks in (("ocr2.nsi", ("!finalize", "!uninstfinalize")), ("launcher.nsi", ("!finalize",))):
        lines = _code_lines(name)
        text = "\n".join(lines)
        for hook in hooks:
            assert hook in text, (name, hook)
        # every hook sits inside an !ifdef OCR2_SIGN block, so an unsigned build has none
        depth_sign = 0
        for line in lines:
            s = line.strip()
            if s.startswith("!ifdef OCR2_SIGN"):
                depth_sign += 1
            elif s.startswith("!endif") and depth_sign:
                depth_sign -= 1
            elif s.startswith(("!finalize", "!uninstfinalize")):
                assert depth_sign > 0, (name, s)
        assert "sign.ps1" in text or "OCR2_SIGN_SCRIPT" in text


def test_signing_defines_reach_both_makensis_commands(tmp_path):
    launcher, installer = _sign_commands(tmp_path)
    for command in (launcher, installer):
        assert f"-DOCR2_SIGN_THUMBPRINT={_THUMB}" in command
        assert f"-DOCR2_TIMESTAMP_URL={_TS}" in command
        assert f"-DOCR2_SIGN_SCRIPT={_INSTALLER / 'sign.ps1'}" in command
        assert f"-DOCR2_SIGN_MARKER={tmp_path / 'out' / 'sign-failed.txt'}" in command


def test_signing_needs_both_values_and_valid_shapes(tmp_path):
    makensis = tmp_path / "m.exe"
    args = (makensis, "0.6.1", tmp_path / "p", tmp_path / "o")
    with pytest.raises(build_payload.BuildError):
        build_installer.makensis_commands(*args, sign_thumbprint=_THUMB)
    with pytest.raises(build_payload.BuildError):
        build_installer.makensis_commands(*args, timestamp_url=_TS)
    with pytest.raises(build_payload.BuildError):
        build_installer.makensis_commands(*args, sign_thumbprint="xyz", timestamp_url=_TS)
    with pytest.raises(build_payload.BuildError):
        build_installer.makensis_commands(*args, sign_thumbprint=_THUMB, timestamp_url="file:///x")
    with pytest.raises(build_payload.BuildError):
        build_installer.makensis_commands(*args, sign_thumbprint=_THUMB, timestamp_url='http://a/"b')


def test_build_installer_main_passes_sign_args_through(monkeypatch, tmp_path):
    seen = {}

    def fake_run(**kwargs):
        seen.update(kwargs)
        raise build_payload.BuildError("stop")

    monkeypatch.setattr(build_installer, "run", fake_run)
    build_installer.main(["--version", "0.6.1", "--sign-thumbprint", _THUMB, "--timestamp-url", _TS])
    assert seen["sign_thumbprint"] == _THUMB and seen["timestamp_url"] == _TS
    seen.clear()
    build_installer.main(["--version", "0.6.1"])
    assert seen["sign_thumbprint"] is None and seen["timestamp_url"] is None
    with pytest.raises(SystemExit):
        build_installer.main(["--version", "0.6.1", "--sign-thumbprint", _THUMB])


def test_signing_scripts_are_read_only_on_stores_and_never_hardcode_a_certificate():
    sign = (_INSTALLER / "sign.ps1").read_text(encoding="utf-8")
    verify = (_INSTALLER / "verify-signature.ps1").read_text(encoding="utf-8")
    assert "Cert:\\CurrentUser\\My" in sign and "Set-AuthenticodeSignature" in sign
    assert "-HashAlgorithm SHA256" in sign and "-TimestampServer" in sign
    assert "1.3.6.1.5.5.7.3.3" in sign and "HasPrivateKey" in sign
    for forbidden in ("LocalMachine", "Import-PfxCertificate", "New-SelfSignedCertificate", "Import-Certificate"):
        assert forbidden not in sign and forbidden not in verify
    assert not re.search(r"\b[0-9A-Fa-f]{40}\b", sign + verify)
    assert "Get-AuthenticodeSignature" in verify and "nessuna marca temporale" in verify


def _minimal_unsigned_pe() -> bytes:
    """A tiny valid 64-bit PE with no Authenticode block (synthetic)."""
    import struct

    dos = bytearray(64); dos[0:2]=b"MZ"; struct.pack_into("<I",dos,0x3C,64)
    coff = struct.pack("<HHIIIHH",0x8664,1,0,0,0,240,0x22)
    opt = bytearray(240)
    struct.pack_into("<HBBIII",opt,0,0x20B,0,0,0x200,0,0)
    struct.pack_into("<IIQ",opt,16,0x1000,0x1000,0x140000000)  # entry? approx
    struct.pack_into("<II",opt,32,0x1000,0x200)  # SectionAlignment, FileAlignment
    struct.pack_into("<HHHHHHI",opt,40,6,0,0,0,6,0,0)
    struct.pack_into("<II",opt,56,0x2000,0x200)  # SizeOfImage, SizeOfHeaders
    struct.pack_into("<HH",opt,68,3,0x8160)
    struct.pack_into("<I",opt,108,16)  # NumberOfRvaAndSizes
    sec = struct.pack("<8sIIIIIIHHI",b".text",0x100,0x1000,0x200,0x200,0,0,0,0,0x60000020)
    hdr = bytes(dos)+b"PE\0\0"+coff+bytes(opt)+sec
    return hdr.ljust(0x200,b"\0")+b"\xC3".ljust(0x200,b"\0")


@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell Authenticode is Windows only")
def test_verify_signature_reports_not_signed_and_exits_1(tmp_path):
    import shutil
    import subprocess

    shell = shutil.which("powershell") or shutil.which("pwsh")
    if shell is None:
        pytest.skip("PowerShell non disponibile")
    exe = tmp_path / "unsigned.exe"
    exe.write_bytes(_minimal_unsigned_pe())
    done = subprocess.run(
        [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(_INSTALLER / "verify-signature.ps1"), "-Path", str(exe)],
        capture_output=True, text=True, timeout=120,
    )
    assert done.returncode == 1, done.stdout + done.stderr
    assert "NotSigned" in done.stdout


def test_a_failed_signing_hook_stops_the_build_because_makensis_only_warns(monkeypatch, tmp_path):
    out = tmp_path / "out"
    (out / "0.6.1").mkdir(parents=True)
    monkeypatch.setattr(build_installer.build_payload, "load_pins", lambda _p: {"nsis": {}})
    monkeypatch.setattr(build_installer, "check_payload", lambda *_a: None)
    monkeypatch.setattr(build_installer, "unpack_nsis", lambda *_a: tmp_path / "makensis.exe")
    calls = []

    class Done:
        returncode = 0

    def fake_subprocess(command, check=False):
        calls.append(command)
        if len(calls) == 2:  # the hook of the installer build failed: sign.ps1 left its marker
            (out / "sign-failed.txt").write_text("Certificato non trovato", encoding="utf-8")
        return Done()

    monkeypatch.setattr(build_installer.subprocess, "run", fake_subprocess)
    with pytest.raises(build_payload.BuildError, match="firma non riuscita"):
        build_installer.run(version="0.6.1", out_dir=out, sign_thumbprint=_THUMB, timestamp_url=_TS)
    # unsigned builds never look at the marker nor run verify-signature.ps1
    calls.clear()
    (out / "sign-failed.txt").unlink()
    build_installer.run(version="0.6.1", out_dir=out)
    assert len(calls) == 2


def test_every_finalize_hook_aborts_the_build_on_a_nonzero_exit():
    for name in ("ocr2.nsi", "launcher.nsi"):
        hooks = [l for l in _code_lines(name) if l.startswith(("!finalize", "!uninstfinalize"))]
        assert hooks, name
        for hook in hooks:
            assert hook.endswith("' = 0"), (name, hook)
    assert sum(l.startswith("!uninstfinalize") for l in _code_lines("ocr2.nsi")) == 1
