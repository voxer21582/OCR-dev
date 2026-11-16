from pathlib import Path
import re


def test_nsis_script_is_per_user_and_avoids_system_changes():
    script = (Path(__file__).resolve().parents[2] / 'installer/ocr2.nsi').read_text(encoding='utf-8')
    assert re.search(r'RequestExecutionLevel\s+user', script, re.I)
    assert '$LOCALAPPDATA\\Programs\\OCR2' in script
    for forbidden in ('WriteReg', 'DeleteReg', 'RequestExecutionLevel admin', '$PROGRAMFILES', '$WINDIR', 'SetShellVarContext all', 'http://', 'https://'):
        assert forbidden.lower() not in script.lower()


def test_installer_starts_python_without_bytecode_and_verifies_before_shortcut():
    script = (Path(__file__).resolve().parents[2] / 'installer/ocr2.nsi').read_text(encoding='utf-8')
    assert '-B -m alfa_document_intelligence.install_state' in script
    assert '-B -m alfa_document_intelligence --app-window' in script
    assert script.index('install_state') < script.index('CreateShortcut')


def test_installer_provides_rollback_and_optional_data_removal():
    script = (Path(__file__).resolve().parents[2] / 'installer/ocr2.nsi').read_text(encoding='utf-8')
    assert 'WriteUninstaller' in script
    assert '/ROLLBACK' in script
    assert 'Torna alla versione precedente.lnk' in script
    assert 'Disinstalla OCR2.lnk' in script
    assert 'MB_DEFBUTTON2' in script
    assert '/SD IDNO' in script
    assert 'install_state --base "$INSTDIR" prune' in script


def test_release_installer_requires_signing_both_executables():
    script = (Path(__file__).resolve().parents[2] / 'installer/ocr2.nsi').read_text(encoding='utf-8')
    assert '!uninstfinalize' in script
    assert '!finalize' in script
    assert '!error "Release builds require signing"' in script


def test_installer_stages_files_and_shortcut_resolves_active_version():
    script = (Path(__file__).resolve().parents[2] / 'installer/ocr2.nsi').read_text(encoding='utf-8')
    assert 'GetTempFileName' in script
    assert 'Rename "$0" "$INSTDIR\\versions\\${OCR2_VERSION}"' in script
    assert '"$INSTDIR\\Uninstall.exe" \'/LAUNCH\'' in script
    assert 'Push "active"' in script


def test_uninstaller_stops_if_files_cannot_be_removed():
    script = (Path(__file__).resolve().parents[2] / 'installer/ocr2.nsi').read_text(encoding='utf-8')
    uninstall = script.split('Section "Uninstall"', 1)[1]
    assert 'IfErrors uninstall_failed' in uninstall
    assert uninstall.index('RMDir /r "$INSTDIR\\versions"') < uninstall.index('Delete "$INSTDIR\\active.json"')
    assert 'Call un.AcquireLock' in uninstall
    assert 'kernel32::LockFile' in script
    assert 'CloseHandle' in script
    assert 'removal_check.py" --base "$INSTDIR" --cleanup-debris' in uninstall
    assert '"$INSTDIR\\.child.lock"' in script


def test_shortcut_failure_aborts_before_activation():
    script = (Path(__file__).resolve().parents[2] / 'installer/ocr2.nsi').read_text(encoding='utf-8')
    assert 'IfErrors shortcut_failed' in script
    assert script.index('IfErrors shortcut_failed') < script.index('install_state --base "$INSTDIR" activate')


def test_uninstaller_can_find_another_verified_runtime_for_cleanup():
    script = (Path(__file__).resolve().parents[2] / 'installer/ocr2.nsi').read_text(encoding='utf-8')
    section = script.split('Section "Uninstall"', 1)[1]
    assert 'FindFirst' in section and 'FindNext' in section
    assert 'install_state --base "$INSTDIR" verify "$4"' in section
    assert 'removal_check.py" --base "$INSTDIR" --cleanup-debris' in section


def test_launch_and_rollback_find_a_verified_runtime():
    script = (Path(__file__).resolve().parents[2] / 'installer/ocr2.nsi').read_text(encoding='utf-8')
    assert 'Function un.RunVersionCommand' in script
    assert 'Push "active"' in script
    assert 'Push "rollback"' in script
    assert script.count('Call un.RunVersionCommand') >= 2


def test_release_installer_requires_runtime_signature_gate():
    script = (Path(__file__).resolve().parents[2] / 'installer/ocr2.nsi').read_text(encoding='utf-8')
    assert '!ifndef OCR2_CERT_THUMBPRINT' in script
    assert 'verify-runtime-signatures.ps1' in script
    assert '!system' in script


def test_installer_checks_reparse_paths_before_writing_or_extracting():
    script = (Path(__file__).resolve().parents[2] / 'installer/ocr2.nsi').read_text(encoding='utf-8')
    section = script.split('Section "OCR2"', 1)[1]
    assert section.index('Call ValidateInstallPaths') < section.index('CreateDirectory "$INSTDIR"')
    assert section.index('Call ValidateInstallPaths') < section.index('GetTempFileName')
    assert 'GetFileAttributesW' in script and '0x400' in script


def test_installer_checks_runtime_path_before_executing_it():
    script = (Path(__file__).resolve().parents[2] / 'installer/ocr2.nsi').read_text(encoding='utf-8')
    paths = script.split('Function ${PREFIX}ValidateInstallPaths', 1)[1].split('FunctionEnd', 1)[0]
    assert 'versions\\${OCR2_VERSION}\\python\\python.exe' in paths
    command = script.split('Function un.RunVersionCommand', 1)[1].split('FunctionEnd', 1)[0]
    assert command.index('Call un.AssertSafePath') < command.index('nsExec::ExecToStack')
    uninstall = script.split('Section "Uninstall"', 1)[1]
    assert uninstall.index('Call un.AssertSafePath') < uninstall.index('ExecWait')
