"""Build the OCR2 installer payload (M6 Task 6).

Layout of ``<out_dir>/<version>/``::

    python/                      CPython embeddable, python313._pth enables site and ..\\app
    python/Lib/site-packages/    wheels of the runtime lock (pip --target --no-deps --no-index --require-hashes)
    app/alfa_document_intelligence/   application sources only (no tests, no __pycache__)
    runtime-manifest.json        SHA-256 of every file, checked by the launcher at start-up

The embeddable and the NSIS zip are pinned in ``installer/pins.json`` and fetched
once into ``installer/.cache/``.  A file that does not match its pin stops the
build (V6): no second attempt, no other source.  The wheels are fetched by
``pip download --require-hashes`` against the runtime lock, so pip enforces their
hashes.  Every ``opencv_videoio_ffmpeg*.dll`` is removed (DEC-030).

Usage (Windows dev PC, Python 3.13)::

    python installer/build_payload.py --version 0.6.0
"""
from __future__ import annotations

import argparse
import compileall
import fnmatch
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import py_compile
import re
import shutil
import subprocess
import sys
from typing import Callable
import urllib.request
import zipfile

INSTALLER_DIR = Path(__file__).resolve().parent
REPOSITORY = INSTALLER_DIR.parent
DEFAULT_PINS = INSTALLER_DIR / "pins.json"
DEFAULT_CACHE = INSTALLER_DIR / ".cache"
DEFAULT_OUT = INSTALLER_DIR / "out"
DEFAULT_LOCK = REPOSITORY / "requirements" / "ocr2-runtime-cp313-win-amd64.lock"
DEFAULT_APP_SRC = REPOSITORY / "application" / "src" / "alfa_document_intelligence"

try:
    from alfa_document_intelligence import runtime_manifest
except ImportError:  # run as a script from the repository
    sys.path.insert(0, str(REPOSITORY / "application" / "src"))
    from alfa_document_intelligence import runtime_manifest

FFMPEG_DLL_GLOB = "opencv_videoio_ffmpeg*.dll"
_APP_IGNORED_DIRS = {"__pycache__", "tests"}
_APP_IGNORED_FILES = ("*.pyc", "*.pyo")
_CHUNK = 1024 * 1024
_VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
_VERSION_LINE = re.compile(r"""^__version__[ \t]*=[ \t]*["'][^"'\r\n]*["'][ \t]*\r?$""", re.MULTILINE)


class BuildError(RuntimeError):
    """The payload cannot be built."""


class PinMismatchError(BuildError):
    """A downloaded or cached file does not match its pin: stop (V6)."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check_pin(path: Path, pin: dict) -> None:
    size = path.stat().st_size
    digest = sha256_file(path)
    if digest != pin["sha256"].lower() or size != pin["size"]:
        raise PinMismatchError(
            f"{pin['file']}: SHA-256 {digest} ({size} byte) diverso dal pin "
            f"{pin['sha256']} ({pin['size']} byte). Costruzione fermata (V6): nessun nuovo tentativo."
        )


def _urllib_download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "ocr2-installer-build"})
    with urllib.request.urlopen(request, timeout=120) as response, destination.open("wb") as target:
        shutil.copyfileobj(response, target, _CHUNK)


def fetch_pinned(pin: dict, cache_dir: Path, *, download: Callable[[str, Path], None] = _urllib_download) -> Path:
    """Return the cached file for ``pin``, downloading it once from its URL.

    A cached file that does not match is not replaced, and a download that does
    not match is discarded: both raise ``PinMismatchError``.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    final = cache_dir / pin["file"]
    if final.exists():
        _check_pin(final, pin)
        return final
    partial = cache_dir / (pin["file"] + ".part")
    partial.unlink(missing_ok=True)
    try:
        download(pin["url"], partial)
        _check_pin(partial, pin)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    os.replace(partial, final)
    return final


def pip_download_wheels(lock: Path, wheel_dir: Path) -> None:
    """Fetch the locked wheels for CPython 3.13 win_amd64; pip refuses any hash mismatch."""
    wheel_dir = Path(wheel_dir)
    wheel_dir.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable, "-m", "pip", "download", "--disable-pip-version-check", "--no-input",
        "--only-binary=:all:", "--require-hashes", "--no-deps",
        "--platform", "win_amd64", "--python-version", "3.13", "--implementation", "cp",
        "-r", str(lock), "-d", str(wheel_dir),
    ]
    if subprocess.run(command).returncode != 0:
        raise PinMismatchError(
            "pip download delle wheel del lock non riuscito (impronta diversa o download fallito). "
            "Costruzione fermata (V6)."
        )


def extract_embeddable(embeddable_zip: Path, python_dir: Path) -> None:
    """Extract the embeddable into ``python_dir``, refusing absolute or escaping member names."""
    with zipfile.ZipFile(embeddable_zip) as archive:
        for member in archive.namelist():
            pure = PurePosixPath(member.replace("\\", "/"))
            if pure.is_absolute() or ".." in pure.parts or ":" in member:
                raise BuildError(f"membro non ammesso nell'embeddable: {member}")
        python_dir.mkdir(parents=True)
        archive.extractall(python_dir)


def write_pth(python_dir: Path) -> Path:
    """Rewrite the embeddable's single ``python3XX._pth``: stdlib zip, its folder, ..\\app, site-packages, site."""
    candidates = sorted(python_dir.glob("python3*._pth"))
    if len(candidates) != 1:
        raise BuildError("l'embeddable deve contenere un solo file python3XX._pth")
    pth = candidates[0]
    lines = [f"{pth.stem}.zip", ".", "..\\app", "Lib\\site-packages", "import site"]
    pth.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return pth


def install_wheels(lock: Path, wheel_dir: Path, site_packages: Path) -> None:
    command = [
        sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--no-input",
        "--target", str(site_packages), "--no-deps", "--no-index", "--find-links", str(wheel_dir), "--no-compile",
        "--only-binary=:all:", "--require-hashes", "-r", str(lock),
    ]
    if subprocess.run(command).returncode != 0:
        raise BuildError("installazione delle wheel del lock non riuscita")
    # Console-script launchers, if pip leaves any, embed the build machine's Python path: not shipped.
    for scripts in ("bin", "Scripts"):
        shutil.rmtree(site_packages / scripts, ignore_errors=True)
    compile_site_packages(site_packages)


def compile_site_packages(site_packages: Path) -> None:
    """Hash-checked bytecode (valid whatever the installed file times) with relative file names.

    pip's own compilation would record the build folder (a user profile path) in every ``.pyc``.
    Python fixes ``co_filename`` to the real source path at import, so nothing is lost.
    Files that do not compile are left as sources, as pip does.
    """
    compileall.compile_dir(
        str(site_packages), quiet=2, stripdir=str(site_packages), prependdir="",
        invalidation_mode=py_compile.PycInvalidationMode.CHECKED_HASH, workers=0,
    )


def remove_ffmpeg_dlls(root: Path) -> list[str]:
    removed = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and fnmatch.fnmatchcase(path.name.lower(), FFMPEG_DLL_GLOB):
            path.unlink()
            removed.append(path.relative_to(root).as_posix())
    return removed


def copy_app(app_src: Path, app_target: Path) -> None:
    def ignore(directory: str, names: list[str]) -> set[str]:
        ignored = set()
        for name in names:
            if name in _APP_IGNORED_DIRS and (Path(directory) / name).is_dir():
                ignored.add(name)
            elif any(fnmatch.fnmatchcase(name.lower(), pattern) for pattern in _APP_IGNORED_FILES):
                ignored.add(name)
        return ignored

    shutil.copytree(app_src, app_target, ignore=ignore)


def stamp_version(init_file: Path, version: str) -> None:
    """Set ``__version__ = "<version>"`` in the copied package (R23); the sources are not touched."""
    text = init_file.read_text(encoding="utf-8")
    stamped, count = _VERSION_LINE.subn(f'__version__ = "{version}"', text)
    if count != 1:
        raise BuildError("__init__.py del pacchetto: serve una sola riga __version__")
    init_file.write_text(stamped, encoding="utf-8", newline="\n")


def build_payload(
    *,
    embeddable_zip: Path,
    wheel_dir: Path,
    app_src: Path,
    out_dir: Path,
    version: str,
    lock: Path = DEFAULT_LOCK,
) -> Path:
    """Assemble ``out_dir/<version>/`` and its runtime manifest; return that folder."""
    if not isinstance(version, str) or not _VERSION.fullmatch(version):
        raise BuildError(f"versione non valida (atteso MAGGIORE.MINORE.PATCH): {version!r}")
    out_dir = Path(out_dir)
    target = out_dir / version
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    python_dir = target / "python"
    extract_embeddable(Path(embeddable_zip), python_dir)
    write_pth(python_dir)
    install_wheels(Path(lock), Path(wheel_dir), python_dir / "Lib" / "site-packages")
    for removed in remove_ffmpeg_dlls(target):
        print(f"Rimosso (DEC-030): {removed}")
    copy_app(Path(app_src), target / "app" / Path(app_src).name)
    stamp_version(target / "app" / Path(app_src).name / "__init__.py", version)
    # No exclusions: a leftover FFmpeg DLL makes build_manifest raise.
    try:
        manifest = runtime_manifest.build_manifest(target, version=version, excluded_globs=())
    except ValueError as exc:
        raise BuildError(f"manifest non costruibile: {exc}") from exc
    manifest_path = target / runtime_manifest.MANIFEST_NAME
    runtime_manifest.write_manifest(manifest, manifest_path)
    check = runtime_manifest.verify_installation(target, manifest_path)
    if not check.ok:
        raise BuildError("verifica del contenuto appena costruito non riuscita: " + "; ".join(check.problems))
    return target


def load_pins(pins_path: Path) -> dict:
    pins = json.loads(Path(pins_path).read_text(encoding="utf-8"))
    for key in ("embeddable", "nsis"):
        pin = pins.get(key)
        if not isinstance(pin, dict) or not all(isinstance(pin.get(field), str) for field in ("file", "url", "sha256")):
            raise BuildError(f"pins.json: voce {key} incompleta")
        if not isinstance(pin.get("size"), int):
            raise BuildError(f"pins.json: dimensione di {key} mancante")
    return pins


def run(
    *,
    version: str,
    pins_path: Path = DEFAULT_PINS,
    cache_dir: Path = DEFAULT_CACHE,
    out_dir: Path = DEFAULT_OUT,
    lock: Path = DEFAULT_LOCK,
    app_src: Path = DEFAULT_APP_SRC,
    download: Callable[[str, Path], None] = _urllib_download,
    download_wheels: Callable[[Path, Path], None] = pip_download_wheels,
) -> Path:
    """Fetch and verify the pins (NSIS too, used by Task 8), fetch the wheels, build."""
    if not isinstance(version, str) or not _VERSION.fullmatch(version):
        raise BuildError(f"versione non valida (atteso MAGGIORE.MINORE.PATCH): {version!r}")
    pins = load_pins(pins_path)
    embeddable = fetch_pinned(pins["embeddable"], cache_dir, download=download)
    fetch_pinned(pins["nsis"], cache_dir, download=download)
    wheel_dir = Path(cache_dir) / "wheels"
    download_wheels(Path(lock), wheel_dir)
    return build_payload(
        embeddable_zip=embeddable, wheel_dir=wheel_dir, app_src=app_src, out_dir=out_dir, version=version, lock=lock,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the OCR2 installer payload.")
    parser.add_argument("--version", required=True, help="application version, e.g. 0.6.0")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    args = parser.parse_args(argv)
    try:
        target = run(version=args.version, out_dir=args.out_dir, cache_dir=args.cache_dir)
    except PinMismatchError as exc:
        print(f"BLOCCATO: {exc}", file=sys.stderr)
        return 3
    except BuildError as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        return 2
    manifest = json.loads((target / runtime_manifest.MANIFEST_NAME).read_text(encoding="utf-8"))
    size = sum(entry["size"] for entry in manifest["files"].values())
    print(f"Contenuto costruito: {target} ({len(manifest['files'])} file, {size} byte)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
