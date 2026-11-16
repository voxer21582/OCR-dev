"""Installer payload build (M6 Task 6) with a synthetic embeddable Python and synthetic wheels.

No network: the embeddable and the wheel are minimal zips made here; pip installs
the wheel offline with ``--no-index --require-hashes``.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import sys
import zipfile

import pytest

_REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPOSITORY / "installer"))

import build_payload  # noqa: E402
from alfa_document_intelligence.runtime_manifest import MANIFEST_NAME, verify_installation  # noqa: E402

_ORIGINAL_PTH = "python313.zip\n.\n\n# Uncomment to run site.main() automatically\n#import site\n"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _embeddable(folder: Path) -> Path:
    path = folder / "python-3.13.99-embed-amd64.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("python.exe", b"MZ synthetic")
        archive.writestr("pythonw.exe", b"MZ synthetic w")
        archive.writestr("python313.dll", b"synthetic dll")
        archive.writestr("python313.zip", b"PK synthetic stdlib")
        archive.writestr("python313._pth", _ORIGINAL_PTH)
        archive.writestr("LICENSE.txt", "PSF synthetic licence\n")
    return path


def _wheel(folder: Path) -> Path:
    """A ``py3-none-any`` wheel whose package carries an FFmpeg DLL (as opencv's does) and a console script."""
    name = "fakecv-1.0-py3-none-any.whl"
    files = {
        "fakecv/__init__.py": b"VALUE = 1\n",
        "fakecv/opencv_videoio_ffmpeg4110_64.dll": b"ffmpeg",
        "fakecv/OPENCV_VIDEOIO_FFMPEG_UPPER.DLL": b"ffmpeg upper",
        "fakecv-1.0.dist-info/METADATA": b"Metadata-Version: 2.1\nName: fakecv\nVersion: 1.0\nLicense: MIT\nLicense-File: LICENSE\n",
        "fakecv-1.0.dist-info/licenses/LICENSE": b"Synthetic MIT text\n",
        "fakecv-1.0.dist-info/WHEEL": b"Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        "fakecv-1.0.dist-info/entry_points.txt": b"[console_scripts]\nfakecv-tool = fakecv:VALUE\n",
    }
    record = []
    for member, data in files.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
        record.append(f"{member},sha256={digest},{len(data)}")
    record.append("fakecv-1.0.dist-info/RECORD,,")
    files["fakecv-1.0.dist-info/RECORD"] = ("\n".join(record) + "\n").encode()
    wheel_dir = folder / "wheels"
    wheel_dir.mkdir()
    path = wheel_dir / name
    with zipfile.ZipFile(path, "w") as archive:
        for member, data in files.items():
            archive.writestr(member, data)
    return path


def _app_source(folder: Path) -> Path:
    package = folder / "src" / "alfa_document_intelligence"
    (package / "__pycache__").mkdir(parents=True)
    (package / "tests").mkdir()
    (package / "schemas").mkdir()
    (package / "__init__.py").write_text("__version__ = '0.0.0'\n", encoding="utf-8")
    (package / "__main__.py").write_text("print('ok')\n", encoding="utf-8")
    (package / "schemas" / "document.schema.json").write_text("{}\n", encoding="utf-8")
    (package / "__pycache__" / "__init__.cpython-313.pyc").write_bytes(b"pyc")
    (package / "stray.pyc").write_bytes(b"pyc")
    (package / "tests" / "test_x.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
    return package


@pytest.fixture
def built(tmp_path):
    embeddable = _embeddable(tmp_path)
    wheel = _wheel(tmp_path)
    lock = tmp_path / "runtime.lock"
    lock.write_text(
        f"--only-binary=:all:\nfakecv==1.0 \\\n    --hash=sha256:{_sha256(wheel.read_bytes())}\n", encoding="utf-8"
    )
    target = build_payload.build_payload(
        embeddable_zip=embeddable,
        wheel_dir=wheel.parent,
        app_src=_app_source(tmp_path),
        out_dir=tmp_path / "out",
        version="0.6.0",
        lock=lock,
    )
    return target


def _files(root: Path) -> set[str]:
    return {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}


def test_pth_enables_site_and_app(built):
    assert built.name == "0.6.0"
    pth = (built / "python" / "python313._pth").read_text(encoding="utf-8")
    assert pth.splitlines() == ["python313.zip", ".", "..\\app", "Lib\\site-packages", "import site"]
    assert (built / "python" / "python.exe").is_file()
    assert (built / "python" / "Lib" / "site-packages" / "fakecv" / "__init__.py").is_file()
    assert (built / "app" / "alfa_document_intelligence" / "__main__.py").is_file()
    # Console-script launchers name the build machine's Python; they are not shipped.
    assert not (built / "python" / "Lib" / "site-packages" / "bin").exists()
    assert not (built / "python" / "Lib" / "site-packages" / "Scripts").exists()


def test_site_packages_bytecode_names_no_build_path(built):
    """Bytecode is hash-checked and carries relative file names, not the build machine's folders."""
    site_packages = built / "python" / "Lib" / "site-packages"
    compiled = list(site_packages.rglob("*.pyc"))
    assert compiled
    for path in compiled:
        data = path.read_bytes()
        assert int.from_bytes(data[4:8], "little") == 0b11  # checked-hash pyc (PEP 552)
        assert str(built).encode() not in data
        assert built.parents[1].name.encode() not in data  # the test's own folder name


def test_build_version_is_stamped_in_payload(built, tmp_path):
    stamped = built / "app" / "alfa_document_intelligence" / "__init__.py"
    text = stamped.read_text(encoding="utf-8")
    assert '__version__ = "0.6.0"' in text and "0.0.0" not in text
    # The source package is not modified.
    assert "0.0.0" in (tmp_path / "src" / "alfa_document_intelligence" / "__init__.py").read_text(encoding="utf-8")
    manifest = json.loads((built / MANIFEST_NAME).read_text(encoding="utf-8"))
    entry = manifest["files"]["app/alfa_document_intelligence/__init__.py"]
    assert entry["sha256"] == _sha256(stamped.read_bytes()) and entry["size"] == stamped.stat().st_size


@pytest.mark.parametrize("version", ["0.6", "v0.6.0", "0.6.0-rc1", "../0.6.0", "0.6.0 ", ""])
def test_version_must_be_major_minor_patch(tmp_path, version):
    with pytest.raises(build_payload.BuildError):
        build_payload.build_payload(
            embeddable_zip=_embeddable(tmp_path), wheel_dir=tmp_path, app_src=_app_source(tmp_path),
            out_dir=tmp_path / "out", version=version, lock=tmp_path / "missing.lock",
        )
    assert not (tmp_path / "out").exists()


def test_repository_version_is_release_version():
    import alfa_document_intelligence

    assert alfa_document_intelligence.__version__ == "0.6.0"


def test_tests_and_pycache_are_not_copied(built):
    app = _files(built / "app")
    assert app == {
        "alfa_document_intelligence/__init__.py",
        "alfa_document_intelligence/__main__.py",
        "alfa_document_intelligence/schemas/document.schema.json",
    }


def test_ffmpeg_dll_is_removed(built):
    names = [name.lower() for name in _files(built)]
    assert not [name for name in names if "opencv_videoio_ffmpeg" in name]


def test_sbom_and_notices_are_in_the_version_folder_and_manifest(built):
    manifest = json.loads((built / MANIFEST_NAME).read_text(encoding="utf-8"))
    for name in ("sbom.cdx.json", "THIRD_PARTY_NOTICES.txt"):
        assert (built / name).is_file() and name in manifest["files"]
    assert "Synthetic MIT text" in (built / "THIRD_PARTY_NOTICES.txt").read_text(encoding="utf-8")
    components = json.loads((built / "sbom.cdx.json").read_text(encoding="utf-8"))["components"]
    assert any(c["name"] == "fakecv" for c in components)


def test_manifest_matches_payload(built):
    manifest_path = built / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["version"] == "0.6.0"
    assert set(manifest["files"]) == _files(built) - {MANIFEST_NAME}
    result = verify_installation(built, manifest_path)
    assert result.ok, result.problems
    assert result.checked_files == len(manifest["files"])


def test_rebuild_replaces_previous_payload(tmp_path, built):
    stale = built / "app" / "stale.py"
    stale.write_text("x = 1\n", encoding="utf-8")
    lock = tmp_path / "runtime.lock"
    again = build_payload.build_payload(
        embeddable_zip=tmp_path / "python-3.13.99-embed-amd64.zip",
        wheel_dir=tmp_path / "wheels",
        app_src=tmp_path / "src" / "alfa_document_intelligence",
        out_dir=tmp_path / "out",
        version="0.6.0",
        lock=lock,
    )
    assert not (again / "app" / "stale.py").exists()
    assert verify_installation(again, again / MANIFEST_NAME).ok


def test_embeddable_with_unsafe_member_is_refused(tmp_path):
    embeddable = tmp_path / "evil.zip"
    with zipfile.ZipFile(embeddable, "w") as archive:
        archive.writestr("python313._pth", _ORIGINAL_PTH)
        archive.writestr("../escape.txt", b"x")
    with pytest.raises(build_payload.BuildError):
        build_payload.extract_embeddable(embeddable, tmp_path / "python")
    assert not (tmp_path / "escape.txt").exists()


def _pin(data: bytes, name: str = "python-3.13.99-embed-amd64.zip") -> dict:
    return {"file": name, "url": f"https://example.invalid/{name}", "sha256": _sha256(data), "size": len(data)}


def test_wrong_pin_stops_build(tmp_path):
    published = b"the published archive"
    pin = _pin(published)
    pins = {"embeddable": pin, "nsis": _pin(b"nsis zip", "nsis-3.99.zip")}
    pins_path = tmp_path / "pins.json"
    pins_path.write_text(json.dumps(pins), encoding="utf-8")
    downloads = []

    def tampered_download(url: str, destination: Path) -> None:
        downloads.append(url)
        destination.write_bytes(b"a different archive!")

    def no_pip(*args, **kwargs):  # pragma: no cover - must not be reached
        raise AssertionError("wheels must not be fetched after a pin mismatch")

    out_dir = tmp_path / "out"
    with pytest.raises(build_payload.PinMismatchError):
        build_payload.run(
            version="0.6.0",
            pins_path=pins_path,
            cache_dir=tmp_path / "cache",
            out_dir=out_dir,
            download=tampered_download,
            download_wheels=no_pip,
        )
    assert downloads == [pin["url"]]  # one attempt, no other source (V6)
    assert not (tmp_path / "cache" / pin["file"]).exists()
    assert not out_dir.exists()


def test_cached_file_with_wrong_hash_stops_without_downloading(tmp_path):
    pin = _pin(b"the published archive")
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / pin["file"]).write_bytes(b"altered in the cache!")

    def download(url, destination):  # pragma: no cover - must not be reached
        raise AssertionError("a cached file that does not match is not replaced")

    with pytest.raises(build_payload.PinMismatchError):
        build_payload.fetch_pinned(pin, cache, download=download)


def test_matching_pin_is_downloaded_once(tmp_path):
    published = b"the published archive"
    pin = _pin(published)
    calls = []

    def download(url, destination):
        calls.append(url)
        destination.write_bytes(published)

    first = build_payload.fetch_pinned(pin, tmp_path / "cache", download=download)
    second = build_payload.fetch_pinned(pin, tmp_path / "cache", download=download)
    assert first == second and first.read_bytes() == published
    assert calls == [pin["url"]]


def test_repository_pins_are_complete():
    pins = json.loads((_REPOSITORY / "installer" / "pins.json").read_text(encoding="utf-8"))
    embeddable, nsis = pins["embeddable"], pins["nsis"]
    assert embeddable["file"] == f"python-{embeddable['version']}-embed-amd64.zip"
    assert embeddable["url"] == (
        f"https://www.python.org/ftp/python/{embeddable['version']}/{embeddable['file']}"
    )
    assert embeddable["version"].startswith("3.13.")
    assert nsis["file"] == f"nsis-{nsis['version']}.zip" and nsis["version"].startswith("3.")
    assert nsis["url"].startswith("https://downloads.sourceforge.net/project/nsis/")
    for pin in (embeddable, nsis):
        assert len(pin["sha256"]) == 64 and int(pin["sha256"], 16) >= 0
        assert isinstance(pin["size"], int) and pin["size"] > 0
