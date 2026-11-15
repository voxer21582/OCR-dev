import json
from pathlib import Path

import pytest

from alfa_document_intelligence.runtime_manifest import build_manifest, verify_installation


def test_manifest_detects_changed_missing_extra_and_forbidden_files(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "python").mkdir()
    (tmp_path / "app" / "a.py").write_bytes(b"original")
    (tmp_path / "python" / "p.dll").write_bytes(b"runtime")
    manifest = build_manifest(tmp_path, version="1", excluded_globs=())
    path = tmp_path / "runtime-manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert verify_installation(tmp_path, path).ok
    (tmp_path / "app" / "a.py").write_bytes(b"changed")
    (tmp_path / "python" / "p.dll").unlink()
    (tmp_path / "python" / "opencv_videoio_ffmpeg123.dll").write_bytes(b"x")
    result = verify_installation(tmp_path, path)
    assert not result.ok
    assert any("a.py" in item for item in result.problems)
    assert any("p.dll" in item for item in result.problems)
    assert any("ffmpeg" in item for item in result.problems)


def test_manifest_rejects_symlink(tmp_path):
    (tmp_path / "app").mkdir()
    target = tmp_path / "target"
    target.write_bytes(b"x")
    try:
        (tmp_path / "app" / "link").symlink_to(target)
    except OSError:
        pytest.skip("symlink creation unavailable")
    with pytest.raises(ValueError):
        build_manifest(tmp_path, version="1", excluded_globs=())
