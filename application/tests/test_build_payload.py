import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

import pytest


def _builder():
    path = Path(__file__).resolve().parents[2] / "installer" / "build_payload.py"
    spec = importlib.util.spec_from_file_location("ocr2_build_payload", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_payload_rejects_unpinned_embed_before_extraction(tmp_path):
    builder = _builder()
    archive = tmp_path / "python.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("python.exe", b"synthetic")
    with pytest.raises(builder.PayloadBuildError):
        builder._extract_embeddable(archive, tmp_path / "payload", "0" * 64)
    assert not (tmp_path / "payload" / "python.exe").exists()


def test_payload_rejects_zip_traversal_and_preserves_destination(tmp_path):
    builder = _builder()
    archive = tmp_path / "python.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("../outside", b"synthetic")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    with pytest.raises(builder.PayloadBuildError):
        builder._extract_embeddable(archive, tmp_path / "payload", digest)
    assert not (tmp_path / "outside").exists()


def test_payload_python_path_is_offline_and_enables_application(tmp_path):
    builder = _builder()
    python = tmp_path / "python"
    python.mkdir()
    builder._configure_python_path(python)
    lines = (python / "python313._pth").read_text(encoding="utf-8").splitlines()
    assert lines == ["python313.zip", ".", "..\\app", "Lib\\site-packages", "import site"]


@pytest.mark.parametrize("name", ["a/../outside", "dir//file", "CON.txt", "dir/NUL", "dir/file ", "C:/escape"])
def test_payload_rejects_ambiguous_windows_archive_names(tmp_path, name):
    builder = _builder()
    archive = tmp_path / "python.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr(name, b"synthetic")
    with pytest.raises(builder.PayloadBuildError):
        builder._extract_embeddable(archive, tmp_path / "payload", hashlib.sha256(archive.read_bytes()).hexdigest())


def test_payload_refuses_existing_destination(tmp_path):
    builder = _builder()
    archive = tmp_path / "python.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("python.exe", b"synthetic")
    destination = tmp_path / "payload"
    destination.mkdir()
    with pytest.raises(builder.PayloadBuildError):
        builder._extract_embeddable(archive, destination, hashlib.sha256(archive.read_bytes()).hexdigest())


def test_extraction_uses_same_open_file_that_was_hashed(monkeypatch, tmp_path):
    builder = _builder()
    archive = tmp_path / "python.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("python.exe", b"synthetic")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    original_zip = zipfile.ZipFile
    def require_open_handle(file, *args, **kwargs):
        assert hasattr(file, "read") and hasattr(file, "seek")
        return original_zip(file, *args, **kwargs)
    monkeypatch.setattr(builder.zipfile, "ZipFile", require_open_handle)
    builder._extract_embeddable(archive, tmp_path / "payload", digest)
    assert (tmp_path / "payload" / "python.exe").read_bytes() == b"synthetic"


def test_build_payload_excludes_tests_caches_and_ffmpeg_and_verifies(monkeypatch, tmp_path):
    from alfa_document_intelligence.runtime_manifest import verify_installation
    builder = _builder()
    archive = tmp_path / "python.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("python.exe", b"synthetic")
        output.writestr("pythonw.exe", b"synthetic")
        output.writestr("python313.zip", b"synthetic")
    pins = tmp_path / "pins.json"
    pins.write_text(json.dumps({"python": {"filename": archive.name, "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}}), encoding="utf-8")
    src = tmp_path / "source"
    package = src / "alfa_document_intelligence"
    (package / "__pycache__").mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "__pycache__" / "cache.pyc").write_bytes(b"x")
    (package / "tests").mkdir()
    (package / "tests" / "private.py").write_text("", encoding="utf-8")
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    lock = tmp_path / "requirements.lock"
    lock.write_text("", encoding="utf-8")
    def install(_wheels, _lock, target):
        (target / "cv2").mkdir(parents=True)
        (target / "cv2" / "opencv_videoio_ffmpeg123.dll").write_bytes(b"x")
        (target / "cv2" / "other.pyd").write_bytes(b"y")
        (target / "bin").mkdir()
        (target / "bin" / "rapidocr.exe").write_bytes(b"synthetic generated launcher")
        record = target / "sample-1.0.dist-info" / "RECORD"
        record.parent.mkdir()
        record.write_text('../../bin/rapidocr.exe,sha256=synthetic,1\ncv2/opencv_videoio_ffmpeg123.dll,sha256=synthetic,1\ncv2/other.pyd,sha256=synthetic,1\n', encoding='utf-8')
    monkeypatch.setattr(builder, "_install_wheels", install)
    finalized = []
    monkeypatch.setattr(builder, "_finalize", lambda root, lock, pins, version: finalized.append(root))
    result = builder.build_payload(embeddable_zip=archive, wheel_dir=wheels, app_src=src,
                                   out_dir=tmp_path / "out", version="0.6.0", pins_path=pins, lock_path=lock)
    assert (result / "app" / "alfa_document_intelligence" / "__init__.py").is_file()
    assert '__version__ = "0.6.0"' in (result / "app" / "alfa_document_intelligence" / "__init__.py").read_text(encoding='utf-8')
    assert not (result / "app" / "alfa_document_intelligence" / "tests").exists()
    assert not (result / "app" / "alfa_document_intelligence" / "__pycache__").exists()
    assert not list(result.rglob("opencv_videoio_ffmpeg*.dll"))
    assert not (result / "python/Lib/site-packages/bin").exists()
    record = (result / "python/Lib/site-packages/sample-1.0.dist-info/RECORD").read_text(encoding='utf-8')
    assert 'rapidocr.exe' not in record and 'ffmpeg' not in record and 'other.pyd' in record
    assert verify_installation(result, result / "runtime-manifest.json").ok
    assert finalized == [result]


def test_generated_script_cleanup_rejects_unexpected_entries_before_removal(tmp_path):
    builder = _builder()
    scripts = tmp_path / 'bin'; scripts.mkdir()
    known = scripts / 'rapidocr.exe'; known.write_bytes(b'synthetic')
    unexpected = scripts / 'unknown.exe'; unexpected.write_bytes(b'synthetic')
    with pytest.raises(builder.PayloadBuildError, match='generated script'):
        builder._remove_generated_scripts(tmp_path)
    assert known.exists() and unexpected.exists()


def test_generated_script_cleanup_rejects_link_before_removing_any_entry(tmp_path, monkeypatch):
    from alfa_document_intelligence import runtime_manifest
    builder = _builder()
    scripts = tmp_path / 'bin'; scripts.mkdir()
    a = scripts / 'rapidocr.exe'; a.write_bytes(b'synthetic')
    b = scripts / 'tqdm.exe'; b.write_bytes(b'synthetic')
    original = runtime_manifest._linked
    monkeypatch.setattr(runtime_manifest, '_linked', lambda item: item == b or original(item))
    with pytest.raises(builder.PayloadBuildError, match='generated script'):
        builder._remove_generated_scripts(tmp_path)
    assert a.exists() and b.exists()


@pytest.mark.parametrize('entry', ['../../bin/rapidocr.exe', 'cv2/opencv_videoio_ffmpeg500_64.dll'])
def test_record_cleanup_rejects_entries_not_removed_by_this_build(tmp_path, entry):
    builder = _builder()
    record = tmp_path / 'sample-1.0.dist-info/RECORD'
    record.parent.mkdir()
    record.write_text(entry + ',sha256=synthetic,1\n', encoding='utf-8')
    with pytest.raises(builder.PayloadBuildError, match='not removed'):
        builder._clean_removed_records(tmp_path, set(), set())
    assert entry in record.read_text(encoding='utf-8')


def test_wheel_install_disables_bytecode_compilation(monkeypatch, tmp_path):
    builder = _builder()
    commands = []
    def run(command, check):
        commands.append(command)
        class Result:
            returncode = 0
        return Result()
    monkeypatch.setattr(builder.subprocess, "run", run)
    builder._install_wheels(tmp_path / "wheels", tmp_path / "lock", tmp_path / "target")
    assert "--no-compile" in commands[0]


def test_local_runtime_signing_fails_closed_and_preserves_vendor_files(tmp_path, monkeypatch):
    builder = _builder()
    monkeypatch.setattr(builder, '_verify_runtime_signature', lambda p, thumbprint: None)
    runtime = tmp_path / 'python'
    runtime.mkdir()
    for name in builder.LOCAL_RUNTIME_BINARIES:
        (runtime / name).write_bytes(b'unsigned')
    (runtime / 'libssl-3.dll').write_bytes(b'vendor')
    called = []
    def sign(path):
        called.append(path.name)
        path.write_bytes(b'signed')
    builder._sign_local_runtime(runtime, sign, 'a'*40)
    assert set(called) == set(builder.LOCAL_RUNTIME_BINARIES)
    assert (runtime / 'libssl-3.dll').read_bytes() == b'vendor'
    (runtime / builder.LOCAL_RUNTIME_BINARIES[0]).unlink()
    called.clear()
    with pytest.raises(builder.PayloadBuildError, match='Missing'):
        builder._sign_local_runtime(runtime, sign, 'a'*40)
    assert not called


def test_signer_failure_stops_before_manifest_and_finalization(tmp_path, monkeypatch):
    builder = _builder()
    archive = tmp_path / 'python.zip'
    with zipfile.ZipFile(archive, 'w') as output:
        output.writestr('python.exe', b'synthetic')
        output.writestr('pythonw.exe', b'synthetic')
        output.writestr('python313.zip', b'synthetic')
    pins = tmp_path / 'pins.json'
    pins.write_text(json.dumps({'python': {'filename': archive.name, 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}}), encoding='utf-8')
    src = tmp_path / 'src/alfa_document_intelligence'
    src.mkdir(parents=True); (src / '__init__.py').write_text('', encoding='utf-8')
    wheels = tmp_path / 'wheels'; wheels.mkdir()
    lock = tmp_path / 'lock'; lock.write_text('', encoding='utf-8')
    monkeypatch.setattr(builder, '_install_wheels', lambda w, l, target: target.mkdir(parents=True))
    monkeypatch.setattr(builder, 'LOCAL_BUILD_ARCHIVE_SHA256', hashlib.sha256(archive.read_bytes()).hexdigest())
    finalized = []
    monkeypatch.setattr(builder, '_finalize', lambda *args: finalized.append(True))
    with pytest.raises(builder.PayloadBuildError, match='Missing'):
        builder.build_payload(embeddable_zip=archive, wheel_dir=wheels, app_src=src.parent, out_dir=tmp_path / 'out', version='0.6.0', pins_path=pins, lock_path=lock, local_runtime_signer=lambda p: None, local_runtime_thumbprint='a'*40)
    assert not (tmp_path / 'out/0.6.0/runtime-manifest.json').exists()
    assert not finalized


def test_manifest_is_generated_after_runtime_signer(tmp_path, monkeypatch):
    from alfa_document_intelligence.runtime_manifest import verify_installation
    builder = _builder()
    archive = tmp_path / 'python.zip'
    with zipfile.ZipFile(archive, 'w') as output:
        for name in builder.LOCAL_RUNTIME_BINARIES:
            output.writestr(name, b'unsigned')
        output.writestr('python313.zip', b'stdlib')
    pins = tmp_path / 'pins.json'
    pins.write_text(json.dumps({'python': {'filename': archive.name, 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}}), encoding='utf-8')
    src = tmp_path / 'src/alfa_document_intelligence'
    src.mkdir(parents=True); (src / '__init__.py').write_text('', encoding='utf-8')
    wheels = tmp_path / 'wheels'; wheels.mkdir()
    lock = tmp_path / 'lock'; lock.write_text('', encoding='utf-8')
    monkeypatch.setattr(builder, '_install_wheels', lambda w, l, target: target.mkdir(parents=True))
    monkeypatch.setattr(builder, '_finalize', lambda *args: None)
    monkeypatch.setattr(builder, '_verify_runtime_signature', lambda p, thumbprint: None)
    monkeypatch.setattr(builder, 'LOCAL_BUILD_ARCHIVE_SHA256', hashlib.sha256(archive.read_bytes()).hexdigest())
    def fake_sign(path):
        path.write_bytes(path.read_bytes() + b'-signed')
    result = builder.build_payload(embeddable_zip=archive, wheel_dir=wheels, app_src=src.parent, out_dir=tmp_path / 'out', version='0.6.0', pins_path=pins, lock_path=lock, local_runtime_signer=fake_sign, local_runtime_thumbprint='a'*40)
    assert (result / 'python/python.exe').read_bytes() == b'unsigned-signed'
    assert verify_installation(result, result / 'runtime-manifest.json').ok


def test_runtime_signing_stops_when_independent_verifier_fails(tmp_path, monkeypatch):
    builder = _builder()
    runtime = tmp_path / 'python'; runtime.mkdir()
    for name in builder.LOCAL_RUNTIME_BINARIES:
        (runtime / name).write_bytes(b'unsigned')
    def reject(path, thumbprint):
        raise builder.PayloadBuildError('Runtime signature verification failed')
    monkeypatch.setattr(builder, '_verify_runtime_signature', reject)
    calls = []
    with pytest.raises(builder.PayloadBuildError, match='signature verification'):
        builder._sign_local_runtime(runtime, lambda p: calls.append(p.name), 'a'*40)
    assert len(calls) == 1


def test_runtime_signature_verifier_checks_expected_thumbprint_and_fails_closed(tmp_path, monkeypatch):
    builder = _builder()
    calls = []
    class Result:
        returncode = 1
    def run(args, check):
        calls.append(args)
        return Result()
    monkeypatch.setattr(builder.subprocess, 'run', run)
    with pytest.raises(builder.PayloadBuildError, match='signature verification'):
        builder._verify_runtime_signature(tmp_path / 'python.exe', 'a'*40)
    assert calls[0][-2:] == ['-ExpectedThumbprint', 'a'*40]


def test_release_signature_gate_uses_the_same_local_binary_inventory():
    import re
    builder = _builder()
    gate = (Path(__file__).resolve().parents[2] / 'installer/verify-runtime-signatures.ps1').read_text(encoding='utf-8')
    array = gate.split('$names = @(', 1)[1].split(')', 1)[0]
    assert set(re.findall(r"'([^']+)'", array)) == set(builder.LOCAL_RUNTIME_BINARIES)


def test_release_payload_verifier_rejects_tampering(tmp_path):
    import subprocess, sys
    from alfa_document_intelligence.runtime_manifest import build_manifest
    payload = tmp_path / 'payload'
    for name in ('python/python.exe', 'python/pythonw.exe', 'python/python313.zip', 'app/alfa_document_intelligence/__init__.py'):
        f = payload / name; f.parent.mkdir(parents=True, exist_ok=True); f.write_bytes(b'original')
    (payload / 'sbom.json').write_text('{"bomFormat":"CycloneDX","specVersion":"1.5","version":1,"components":[{"type":"library","name":"synthetic"}]}', encoding='utf-8')
    (payload / 'THIRD_PARTY_NOTICES.txt').write_text('Synthetic notices', encoding='utf-8')
    manifest = build_manifest(payload, version='0.6.0', excluded_globs=())
    (payload / 'runtime-manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    script = Path(__file__).resolve().parents[2] / 'installer/verify_payload.py'
    assert subprocess.run([sys.executable, '-B', str(script), str(payload), '0.6.0'], capture_output=True).returncode == 0
    (payload / 'app/alfa_document_intelligence/__init__.py').write_bytes(b'tampered')
    assert subprocess.run([sys.executable, '-B', str(script), str(payload), '0.6.0'], capture_output=True).returncode != 0


def test_runtime_release_gate_checks_signer_timestamp_and_content(tmp_path):
    import shutil, subprocess
    from alfa_document_intelligence.runtime_manifest import build_manifest
    pwsh = shutil.which('pwsh')
    if not pwsh:
        pytest.skip('PowerShell 7 required for release gate')
    builder = _builder()
    payload = tmp_path / 'payload'
    for name in builder.LOCAL_RUNTIME_BINARIES:
        f = payload / 'python' / name; f.parent.mkdir(parents=True, exist_ok=True); f.write_bytes(b'synthetic')
    for name in ('python/python313.zip', 'app/alfa_document_intelligence/__init__.py'):
        f = payload / name; f.parent.mkdir(parents=True, exist_ok=True); f.write_bytes(b'synthetic')
    manifest = build_manifest(payload, version='0.6.0', excluded_globs=())
    (payload / 'runtime-manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    gate = Path(__file__).resolve().parents[2] / 'installer/verify-runtime-signatures.ps1'
    wrapper = tmp_path / 'mock-gate.ps1'
    wrapper.write_text("""param($Gate, $Payload, $Case)
function Get-AuthenticodeSignature {
    param($LiteralPath)
    $thumb = if ($Case -eq 'wrong') { 'B' * 40 } else { 'A' * 40 }
    $stamp = if ($Case -eq 'no_timestamp') { $null } else { [pscustomobject]@{Subject='synthetic'} }
    $status = if ($Case -eq 'unsigned') { 'NotSigned' } else { 'Valid' }
    [pscustomobject]@{Status=$status; SignerCertificate=[pscustomobject]@{Thumbprint=$thumb}; TimeStamperCertificate=$stamp}
}
& $Gate -Payload $Payload -Thumbprint ('A' * 40)
""", encoding='utf-8')
    def check(case):
        return subprocess.run([pwsh, '-NoProfile', '-NonInteractive', '-File', str(wrapper), str(gate), str(payload), case], capture_output=True).returncode
    assert check('valid') == 0
    assert check('wrong') != 0
    assert check('unsigned') != 0
    assert check('no_timestamp') != 0
    (payload / 'python/python.exe').write_bytes(b'tampered')
    assert check('valid') != 0


def test_release_payload_verifier_rejects_version_mismatch(tmp_path):
    import subprocess, sys
    from alfa_document_intelligence.runtime_manifest import build_manifest
    payload = tmp_path / 'payload'
    for name in ('python/python.exe', 'python/pythonw.exe', 'python/python313.zip', 'app/alfa_document_intelligence/__init__.py'):
        f = payload / name; f.parent.mkdir(parents=True, exist_ok=True); f.write_bytes(b'synthetic')
    (payload / 'sbom.json').write_text('{"bomFormat":"CycloneDX","specVersion":"1.5","version":1,"components":[{"type":"library","name":"synthetic"}]}', encoding='utf-8')
    (payload / 'THIRD_PARTY_NOTICES.txt').write_text('Synthetic notices', encoding='utf-8')
    manifest = build_manifest(payload, version='0.6.0', excluded_globs=())
    (payload / 'runtime-manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    script = Path(__file__).resolve().parents[2] / 'installer/verify_payload.py'
    assert subprocess.run([sys.executable, '-B', str(script), str(payload), '0.6.0'], capture_output=True).returncode == 0
    assert subprocess.run([sys.executable, '-B', str(script), str(payload), '0.6.1'], capture_output=True).returncode != 0


@pytest.mark.parametrize('missing,empty', [('sbom.json', False), ('THIRD_PARTY_NOTICES.txt', False),
                                           ('sbom.json', True), ('THIRD_PARTY_NOTICES.txt', True)])
def test_release_payload_verifier_requires_inventory_and_notices(tmp_path, missing, empty):
    import subprocess, sys
    from alfa_document_intelligence.runtime_manifest import build_manifest
    payload = tmp_path / 'payload'
    for name in ('python/python.exe', 'python/pythonw.exe', 'python/python313.zip', 'app/alfa_document_intelligence/__init__.py'):
        f = payload / name; f.parent.mkdir(parents=True, exist_ok=True); f.write_bytes(b'synthetic')
    (payload / 'sbom.json').write_text('{"bomFormat":"CycloneDX","specVersion":"1.5","version":1,"components":[{"type":"library","name":"synthetic"}]}', encoding='utf-8')
    (payload / 'THIRD_PARTY_NOTICES.txt').write_text('Synthetic notices', encoding='utf-8')
    if empty:
        (payload / missing).write_bytes(b'')
    else:
        (payload / missing).unlink()
    manifest = build_manifest(payload, version='0.6.0', excluded_globs=())
    (payload / 'runtime-manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    script = Path(__file__).resolve().parents[2] / 'installer/verify_payload.py'
    result = subprocess.run([sys.executable, '-B', str(script), str(payload), '0.6.0'], capture_output=True)
    assert result.returncode != 0


@pytest.mark.parametrize('document', ['{"not_a_bom":true}',
                                       '{"bomFormat":"CycloneDX","specVersion":"1.5","components":[null]}',
                                       '{"bomFormat":"CycloneDX","specVersion":"1.5","version":1,"components":[{}]}',
                                       '{"bomFormat":"CycloneDX","specVersion":"1.5","version":1,"components":[{"type":"banana","name":"x"}]}'])
def test_release_payload_verifier_rejects_invalid_inventory(tmp_path, document):
    import subprocess, sys
    from alfa_document_intelligence.runtime_manifest import build_manifest
    payload = tmp_path / 'payload'
    for name in ('python/python.exe', 'python/pythonw.exe', 'python/python313.zip', 'app/alfa_document_intelligence/__init__.py'):
        f = payload / name; f.parent.mkdir(parents=True, exist_ok=True); f.write_bytes(b'synthetic')
    (payload / 'sbom.json').write_text(document, encoding='utf-8')
    (payload / 'THIRD_PARTY_NOTICES.txt').write_text('Synthetic notices', encoding='utf-8')
    manifest = build_manifest(payload, version='0.6.0', excluded_globs=())
    (payload / 'runtime-manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    script = Path(__file__).resolve().parents[2] / 'installer/verify_payload.py'
    assert subprocess.run([sys.executable, '-B', str(script), str(payload), '0.6.0'], capture_output=True).returncode != 0


def test_release_payload_verifier_rejects_blank_notices(tmp_path):
    import subprocess, sys
    from alfa_document_intelligence.runtime_manifest import build_manifest
    payload = tmp_path / 'payload'
    for name in ('python/python.exe', 'python/pythonw.exe', 'python/python313.zip', 'app/alfa_document_intelligence/__init__.py'):
        f = payload / name; f.parent.mkdir(parents=True, exist_ok=True); f.write_bytes(b'synthetic')
    (payload / 'sbom.json').write_text('{"bomFormat":"CycloneDX","specVersion":"1.5","version":1,"components":[{"type":"library","name":"synthetic"}]}', encoding='utf-8')
    (payload / 'THIRD_PARTY_NOTICES.txt').write_text(' \n ', encoding='utf-8')
    (payload / 'runtime-manifest.json').write_text(json.dumps(build_manifest(payload, version='0.6.0', excluded_globs=())), encoding='utf-8')
    script = Path(__file__).resolve().parents[2] / 'installer/verify_payload.py'
    assert subprocess.run([sys.executable, '-B', str(script), str(payload), '0.6.0'], capture_output=True).returncode != 0
