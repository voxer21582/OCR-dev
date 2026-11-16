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
