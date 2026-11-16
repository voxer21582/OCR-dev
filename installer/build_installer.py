"""Build the OCR2 per-user NSIS installer (M6 Task 8, REQ-102, REQ-104, REQ-106).

Inputs: the payload ``installer/out/<version>/`` built by ``build_payload.py`` and
the pinned NSIS portable zip ``installer/.cache/nsis-3.13.zip`` (``pins.json``).
The zip is checked against its pin (SHA-256 and size) before it is unpacked into
``installer/.cache/nsis-3.13/``, afresh at every build; a mismatch stops the build
(V6).  The payload must verify against its own runtime manifest.

Outputs::

    installer/out/launcher/OCR2.exe          launcher stub (installer/launcher.nsi, R6)
    installer/out/OCR2-<version>-setup.exe   installer (installer/ocr2.nsi)
    installer/out/OCR2-<version>-setup-test.exe   with --test (-DOCR2_TEST): no Start-menu
                                             shortcuts, only under --test-data-root

Usage (Windows dev PC)::

    python installer/build_installer.py --version 0.6.1
    python installer/build_installer.py --version 0.6.1 --test --test-data-root <temporary folder>
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import zipfile

INSTALLER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(INSTALLER_DIR))

import build_payload  # noqa: E402
from build_payload import BuildError, PinMismatchError, runtime_manifest  # noqa: E402

DEFAULT_PINS = build_payload.DEFAULT_PINS
DEFAULT_CACHE = build_payload.DEFAULT_CACHE
DEFAULT_OUT = build_payload.DEFAULT_OUT
LAUNCHER_SCRIPT = INSTALLER_DIR / "launcher.nsi"
INSTALLER_SCRIPT = INSTALLER_DIR / "ocr2.nsi"


def unpack_nsis(pin: dict, cache_dir: Path) -> Path:
    """Check the cached NSIS zip against ``pin``, unpack it afresh, return ``makensis.exe``."""
    cache_dir = Path(cache_dir)
    archive_path = cache_dir / pin["file"]
    if not archive_path.is_file():
        raise BuildError(f"zip di NSIS mancante: {pin['file']} (esegui prima build_payload.py)")
    build_payload._check_pin(archive_path, pin)  # PinMismatchError: stop (V6)
    top = f"nsis-{pin['version']}"
    target = cache_dir / top
    staging = cache_dir / (top + ".part")
    for folder in (target, staging):
        if folder.exists():
            shutil.rmtree(folder)
    staging.mkdir(parents=True)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.infolist():
                parts = PurePosixPath(member.filename).parts
                if (
                    not parts
                    or parts[0] != top
                    or member.filename.startswith(("/", "\\"))
                    or ".." in parts
                    or any(":" in part or "\\" in part for part in parts)
                ):
                    raise BuildError(f"zip di NSIS non valido: {member.filename}")
            archive.extractall(staging)
        os.replace(staging / top, target)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    makensis = target / "makensis.exe"
    if not makensis.is_file():
        raise BuildError("makensis.exe mancante nello zip di NSIS")
    return makensis


def check_payload(payload_dir: Path, version: str) -> None:
    """The payload must exist, be of ``version`` and verify against its manifest."""
    payload_dir = Path(payload_dir)
    manifest_path = payload_dir / runtime_manifest.MANIFEST_NAME
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BuildError(f"contenuto dell'installer mancante o senza manifest: {payload_dir.name}") from exc
    if manifest.get("version") != version:
        raise BuildError(f"il contenuto è della versione {manifest.get('version')!r}, non {version}")
    result = runtime_manifest.verify_installation(payload_dir, manifest_path)
    if not result.ok:
        raise BuildError("contenuto dell'installer non integro: " + "; ".join(result.problems[:5]))


def setup_path(out_dir: Path, version: str, *, test: bool = False) -> Path:
    return Path(out_dir) / f"OCR2-{version}-setup{'-test' if test else ''}.exe"


def makensis_commands(
    makensis: Path, version: str, payload_dir: Path, out_dir: Path, *, test_data_root: Path | None = None
) -> tuple[list[str], list[str]]:
    """The makensis command lines for ``launcher.nsi`` and then ``ocr2.nsi``."""
    if not isinstance(version, str) or not build_payload._VERSION.fullmatch(version):
        raise BuildError(f"versione non valida (atteso MAGGIORE.MINORE.PATCH): {version!r}")
    out_dir = Path(out_dir)
    launcher_exe = out_dir / "launcher" / "OCR2.exe"
    common = [str(makensis), "/V2", "/INPUTCHARSET", "UTF8"]
    launcher = [*common, f"-DOUTFILE={launcher_exe}", str(LAUNCHER_SCRIPT)]
    installer = [
        *common,
        f"-DVERSION={version}",
        f"-DPAYLOAD_DIR={Path(payload_dir)}",
        f"-DLAUNCHER_EXE={launcher_exe}",
        f"-DOUTFILE={setup_path(out_dir, version, test=test_data_root is not None)}",
    ]
    if test_data_root is not None:
        installer += ["-DOCR2_TEST", f"-DOCR2_TEST_DATA_ROOT={Path(test_data_root)}"]
    installer.append(str(INSTALLER_SCRIPT))
    return launcher, installer


def run(
    *, version: str, test_data_root: Path | None = None, pins_path: Path = DEFAULT_PINS,
    cache_dir: Path = DEFAULT_CACHE, out_dir: Path = DEFAULT_OUT,
) -> Path:
    pins = build_payload.load_pins(pins_path)
    payload_dir = Path(out_dir) / version
    check_payload(payload_dir, version)
    makensis = unpack_nsis(pins["nsis"], cache_dir)
    launcher, installer = makensis_commands(makensis, version, payload_dir, out_dir, test_data_root=test_data_root)
    (Path(out_dir) / "launcher").mkdir(parents=True, exist_ok=True)
    for command in (launcher, installer):
        completed = subprocess.run(command, check=False)
        if completed.returncode != 0:
            raise BuildError(f"makensis non riuscito ({Path(command[-1]).name}, codice {completed.returncode})")
    return setup_path(out_dir, version, test=test_data_root is not None)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the OCR2 NSIS installer.")
    parser.add_argument("--version", required=True)
    parser.add_argument("--test", action="store_true", help="test build (-DOCR2_TEST): no Start-menu shortcuts")
    parser.add_argument("--test-data-root", type=Path, default=None, help="required with --test: the only folder it may install into")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    args = parser.parse_args(argv)
    if args.test != (args.test_data_root is not None):
        parser.error("--test e --test-data-root vanno indicati insieme")
    if args.test_data_root is not None and not args.test_data_root.is_absolute():
        parser.error("--test-data-root deve essere un percorso assoluto")
    try:
        setup = run(version=args.version, test_data_root=args.test_data_root, out_dir=args.out_dir, cache_dir=args.cache_dir)
    except PinMismatchError as exc:
        print(f"BLOCCATO: {exc}", file=sys.stderr)
        return 3
    except BuildError as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        return 2
    print(f"Installer costruito: {setup} ({setup.stat().st_size} byte)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
