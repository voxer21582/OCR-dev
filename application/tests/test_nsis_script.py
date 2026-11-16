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
    assert '"verify_release_inventory.py" "${OCR2_PAYLOAD}"' in script


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


def test_launch_failure_names_remedies_the_installer_supports():
    """R38 (from #151): the Start-menu launch failure says what works in this installer."""
    script = (Path(__file__).resolve().parents[2] / 'installer/ocr2.nsi').read_text(encoding='utf-8')
    launch = script.split('Function un.onInit', 1)[1].split('launch_ok:', 1)[0]
    message = re.search(r'MessageBox MB_OK\|MB_ICONSTOP "([^"]*)"', launch).group(1)
    assert message.startswith('Impossibile avviare la versione attiva di OCR2.')
    assert 'Installa di nuovo OCR2 con il suo installer' in message
    assert '«Torna alla versione precedente»' in message


def test_uninstaller_deletes_nothing_before_finding_a_verified_ocr2_version():
    """From #151's final review: remove files only from a folder that really holds OCR2."""
    script = (Path(__file__).resolve().parents[2] / 'installer/ocr2.nsi').read_text(encoding='utf-8')
    uninstall = script.split('Section "Uninstall"', 1)[1]
    search = uninstall.split('cleanup_done:', 1)[0]
    assert 'install_state --base "$INSTDIR" verify "$4"' in search
    assert 'Nessuna versione integra disponibile' in search
    for removal in ('RMDir', 'Delete ', 'WriteUninstaller'):
        assert removal not in search
    # Staging and quarantine debris go only after a version verified itself.
    assert search.count('--cleanup-debris') == 1
    assert search.index('verify "$4"') < search.index('--cleanup-debris')


def test_failed_cleanup_after_activation_keeps_the_new_version():
    """From #151's final review: a prune failure never undoes or deletes the active version."""
    script = (Path(__file__).resolve().parents[2] / 'installer/ocr2.nsi').read_text(encoding='utf-8')
    section = script.split('Section "OCR2"', 1)[1].split('SectionEnd', 1)[0]
    assert section.index('activation_ok:') < section.index('install_state --base "$INSTDIR" prune')
    failure = section.split('prune_failed:', 1)[1].split('prune_ok:', 1)[0]
    assert 'MB_ICONEXCLAMATION' in failure
    for undo in ('Abort', 'rollback', 'activate', 'RMDir', 'Delete', 'Rename', 'SetErrorLevel'):
        assert undo not in failure


def _preprocess(defines):
    """Evaluate the conditional directives of ocr2.nsi for a set of /D defines.

    Returns the first active ``!error`` message (or None) and the active lines.
    Only ``!ifdef``/``!ifndef``/``!else``/``!endif`` are interpreted; everything
    else is returned as written, so two configurations can be compared line by line.
    """
    script = (Path(__file__).resolve().parents[2] / 'installer/ocr2.nsi').read_text(encoding='utf-8')
    stack = []
    active = []
    for raw in script.splitlines():
        line = raw.strip()
        enabled = all(stack)
        match = re.fullmatch(r'!(ifdef|ifndef)\s+(\S+)', line)
        if match:
            defined = match.group(2) in defines
            stack.append(defined if match.group(1) == 'ifdef' else not defined)
            continue
        if line == '!else':
            stack[-1] = not stack[-1]
            continue
        if line == '!endif':
            stack.pop()
            continue
        if not enabled:
            continue
        error = re.fullmatch(r'!error\s+"([^"]*)"', line)
        if error:
            return error.group(1), active
        active.append(line)
    assert not stack
    return None, active


_BASE = {'OCR2_VERSION', 'OCR2_PAYLOAD', 'OCR2_OUTPUT'}
_SIGNED = _BASE | {'OCR2_CERT_THUMBPRINT', 'OCR2_SIGN_COMMAND'}
_UNSIGNED = _BASE | {'OCR2_UNSIGNED_RELEASE'}


def _body(lines):
    """Lines after the build-time gates: what ends up in the installer itself."""
    return lines[next(i for i, line in enumerate(lines) if line.startswith('Name ')):]


def test_release_without_signing_still_fails_unless_explicitly_unsigned():
    error, _ = _preprocess(_BASE)
    assert error is not None
    error, _ = _preprocess(_BASE | {'OCR2_CERT_THUMBPRINT'})
    assert error == 'Release builds require signing'


def test_unsigned_release_skips_only_the_authenticode_steps():
    error, unsigned = _preprocess(_UNSIGNED)
    assert error is None
    error, signed = _preprocess(_SIGNED)
    assert error is None
    gates = [line for line in unsigned if line.startswith('!system')]
    # Manifest with version equality, then rebuilt inventory and notices: same as a signed release.
    assert any('"verify_payload.py" "${OCR2_PAYLOAD}" "${OCR2_VERSION}"' in line for line in gates)
    assert any('"verify_release_inventory.py" "${OCR2_PAYLOAD}"' in line for line in gates)
    assert gates == [line for line in signed if line.startswith('!system') and 'verify-runtime-signatures.ps1' not in line]
    assert any('verify-runtime-signatures.ps1' in line for line in signed)
    assert not any('verify-runtime-signatures.ps1' in line or 'verify-signature.ps1' in line for line in unsigned)
    assert not any(line.startswith(('!finalize', '!uninstfinalize')) for line in unsigned)


def test_unsigned_release_behaves_like_a_signed_release():
    _, unsigned = _preprocess(_UNSIGNED)
    _, signed = _preprocess(_SIGNED)
    branding = [line for line in _body(unsigned) if line.startswith('BrandingText')]
    assert branding == ['BrandingText "OCR2 ${OCR2_VERSION} — non firmato"']
    assert [line for line in _body(unsigned) if not line.startswith('BrandingText')] == _body(signed)
    body = '\n'.join(_body(unsigned))
    # Release paths: real install folder, real data folder, Start-menu shortcuts, data question.
    assert r'StrCpy $INSTDIR "$LOCALAPPDATA\Programs\OCR2"' in body
    assert r'StrCpy $8 "$LOCALAPPDATA\OCR2"' in body
    assert 'test-user-data' not in body
    assert r'CreateShortcut "$SMPROGRAMS\OCR2\OCR2.lnk"' in body
    assert r'Delete "$SMPROGRAMS\OCR2\Disinstalla OCR2.lnk"' in body
    assert '"Vuoi eliminare anche i dati locali OCR2?"' in body
    assert '/TEST-REMOVE-DATA' not in body
    assert r'''Exec '"$INSTDIR\versions\$1\python\pythonw.exe"''' in body


def test_signed_release_is_not_labelled_unsigned():
    _, signed = _preprocess(_SIGNED)
    assert not any('non firmato' in line for line in signed)


def test_unsigned_release_refuses_signing_inputs_and_test_mode():
    for extra in ({'OCR2_CERT_THUMBPRINT'}, {'OCR2_SIGN_COMMAND'},
                  {'OCR2_CERT_THUMBPRINT', 'OCR2_SIGN_COMMAND'}, {'OCR2_TEST'}):
        error, lines = _preprocess(_UNSIGNED | extra)
        assert error is not None and 'OCR2_UNSIGNED_RELEASE' in error, extra
        # The refusal comes before any build-time command runs.
        assert not any(line.startswith('!system') for line in lines), extra


def test_test_build_is_unchanged_by_the_unsigned_option():
    error, lines = _preprocess(_BASE | {'OCR2_TEST'})
    assert error is None
    assert not any(line.startswith('!system') or 'non firmato' in line for line in lines)
