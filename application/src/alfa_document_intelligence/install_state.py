"""Installed versions of OCR2 and which one is active (M6 Task 8, REQ-102, REQ-104, REQ-106).

Layout of the per-user program folder (``<base>``, normally
``%LOCALAPPDATA%\\Programs\\OCR2``)::

    OCR2.exe            small NSIS launcher: reads active.txt, starts the active version
    uninstall.exe       NSIS uninstaller
    active.txt          line 1 active version, line 2 previous version (may be empty)
    versions/<v>/       python/, app/, runtime-manifest.json of one version

The NSIS installer extracts a version into ``versions/<v>`` and then runs this
module with that version's Python (``python.exe -B -m
alfa_document_intelligence.install_state activate <v>``).  ``active.txt`` changes
only after the new version passes ``verify_installation`` and is always written
atomically (temporary file + ``os.replace``), so an interrupted update leaves the
previous version active.  ``rollback`` swaps the two lines; ``prune`` keeps only
the two versions named in ``active.txt``; ``check-closed`` (run by the installer
with the active version's Python before it touches any version folder) only
refuses while OCR2 is running; ``uninstall`` runs before NSIS removes
the program files and deletes the user's data only on explicit request.

The user's data folder is resolved, as the launcher does, from the
``LOCALAPPDATA`` environment variable: ``<LOCALAPPDATA>/OCR2``.  Nothing else is
ever deleted from it.  Messages are in Italian; they are shown by the installer.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import stat
import sys
from typing import Sequence

from .app_instance import running_instance
from .runtime_manifest import MANIFEST_NAME, _is_link, verify_installation

STATE_NAME = "active.txt"
VERSIONS_DIR = "versions"
DATA_DIR_NAME = "OCR2"
_VERSION = re.compile(r"\d+\.\d+\.\d+")
_MAX_STATE_BYTES = 256
_MAX_SHOWN_PROBLEMS = 5
# R42: closing the window is enough; the server stops a few seconds later.
_RUNNING = "Chiudi la finestra di OCR2 (o usa Esci), attendi qualche secondo e riprova."


class InstallStateError(RuntimeError):
    """The requested change is refused; the message is shown to the user."""


def _check_version(version: str) -> str:
    if not isinstance(version, str) or _VERSION.fullmatch(version) is None:
        raise InstallStateError(f"Versione non valida: {version!r}")
    return version


def _state_path(base: Path) -> Path:
    return Path(base) / STATE_NAME


def read_state(base: Path) -> tuple[str, str] | None:
    """``(active, previous)`` from ``active.txt``; ``None`` when there is no state file.

    ``previous`` is ``""`` when there is none.  A malformed file raises ``InstallStateError``.
    """
    path = _state_path(base)
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise InstallStateError("Stato dell'installazione non leggibile (active.txt).") from exc
    try:
        if len(raw) > _MAX_STATE_BYTES:
            raise ValueError("too large")
        lines = raw.decode("ascii").splitlines()
        if not 1 <= len(lines) <= 2:
            raise ValueError("wrong line count")
        active = _check_version(lines[0].strip())
        previous = lines[1].strip() if len(lines) == 2 else ""
        if previous:
            _check_version(previous)
    except (ValueError, InstallStateError) as exc:
        raise InstallStateError("Stato dell'installazione non leggibile (active.txt).") from exc
    return active, previous


def _write_state(base: Path, active: str, previous: str) -> None:
    """Write ``active.txt`` atomically; on any failure the old file stays as it was."""
    path = _state_path(base)
    temporary = path.with_name(STATE_NAME + ".tmp")
    try:
        with open(temporary, "w", encoding="ascii", newline="\n") as stream:
            stream.write(f"{active}\n{previous}\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise InstallStateError("Impossibile aggiornare lo stato dell'installazione (active.txt).") from exc


def _data_dir() -> Path | None:
    """``<LOCALAPPDATA>/OCR2`` from the environment, as the launcher resolves it; ``None`` if unusable."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data or not os.path.isabs(local_app_data):
        return None
    return Path(local_app_data) / DATA_DIR_NAME


def _refuse_while_running() -> None:
    data_dir = _data_dir()
    if data_dir is not None and running_instance(data_dir) is not None:
        raise InstallStateError(_RUNNING)


def check_closed() -> None:
    """The installer's first step, before any version folder changes (R42).

    Run with the active version's Python: reinstalling the previous (rollback)
    version while OCR2 is open must not delete that folder first.
    """
    _refuse_while_running()


def _verify(base: Path, version: str) -> None:
    folder = Path(base) / VERSIONS_DIR / version
    if not folder.is_dir() or _is_link(folder):
        raise InstallStateError(f"La versione {version} non è presente.")
    result = verify_installation(folder, folder / MANIFEST_NAME)
    if not result.ok:
        shown = "; ".join(result.problems[:_MAX_SHOWN_PROBLEMS])
        raise InstallStateError(f"I file della versione {version} non sono integri: {shown}")


def _current(base: Path) -> tuple[str, str] | None:
    """State for ``activate``: an unreadable file is replaced (repair), never trusted."""
    try:
        return read_state(base)
    except InstallStateError:
        return None


def activate(base: Path, version: str) -> None:
    """Make ``version`` active once its files verify, keep the old one as previous, prune to two.

    Every failure raises before ``active.txt`` changes; a prune failure after the
    switch is only a warning on stderr (exit 0), never a failed activation.
    """
    _check_version(version)
    base = Path(base)
    _refuse_while_running()
    _verify(base, version)
    state = _current(base)
    if state is None:
        previous = ""
    elif state[0] == version:
        previous = state[1]
    else:
        previous = state[0]
    _write_state(base, version, previous)
    # The switch is done: from here nothing may report a failed activation, or the
    # installer would delete the version that active.txt now names.  An old folder
    # that cannot be deleted (locked file) stays until the next successful prune.
    try:
        prune(base)
    except InstallStateError as exc:
        print(f"Attenzione: {exc} Verrà eliminata al prossimo aggiornamento.", file=sys.stderr)


def rollback(base: Path) -> str:
    """Make the previous version active again (after it verifies); return the active version."""
    base = Path(base)
    state = read_state(base)
    if state is None:
        raise InstallStateError("Nessuna versione attiva.")
    active, previous = state
    if not previous:
        raise InstallStateError("Nessuna versione precedente disponibile.")
    _verify(base, previous)
    _write_state(base, previous, active)
    return previous


def _remove_tree(path: Path) -> None:
    """``shutil.rmtree`` that also clears read-only files; links inside are removed, not followed."""
    def make_writable_and_retry(function, name, _error):
        os.chmod(name, stat.S_IWRITE)
        function(name)

    shutil.rmtree(path, onexc=make_writable_and_retry)


def prune(base: Path) -> list[str]:
    """Delete every ``versions/<v>`` except the active and the previous one; return the deleted versions.

    Only folders named like a version are touched; links are never followed or deleted.
    """
    base = Path(base)
    _refuse_while_running()
    state = read_state(base)
    if state is None:
        raise InstallStateError("Nessuna versione attiva.")
    keep = {version for version in state if version}
    versions = base / VERSIONS_DIR
    removed: list[str] = []
    if not versions.is_dir() or _is_link(versions):
        return removed
    for entry in sorted(versions.iterdir()):
        if entry.name in keep or _VERSION.fullmatch(entry.name) is None:
            continue
        if _is_link(entry) or not entry.is_dir():
            continue
        try:
            _remove_tree(entry)
        except OSError as exc:
            raise InstallStateError(f"Impossibile eliminare la versione {entry.name}.") from exc
        removed.append(entry.name)
    return removed


def _inside(path: Path, root: Path) -> bool:
    try:
        resolved_root = root.resolve()
        return path.resolve() != resolved_root and path.resolve().is_relative_to(resolved_root)
    except (OSError, ValueError):
        return False


def remove_data(test_data_root: Path | None = None) -> bool:
    """Delete ``<LOCALAPPDATA>/OCR2`` and nothing else; ``False`` when it does not exist."""
    data_dir = _data_dir()
    if data_dir is None:
        raise InstallStateError("LOCALAPPDATA non è disponibile: i dati non sono stati eliminati.")
    if test_data_root is not None and not _inside(data_dir, Path(test_data_root)):
        raise InstallStateError("Cartella dei dati fuori dalla cartella di prova: i dati non sono stati eliminati.")
    if _is_link(data_dir):
        raise InstallStateError("La cartella dei dati è un collegamento: i dati non sono stati eliminati.")
    if not data_dir.exists():
        return False
    if not data_dir.is_dir() or data_dir.name != DATA_DIR_NAME:
        raise InstallStateError("La cartella dei dati non è una cartella OCR2: i dati non sono stati eliminati.")
    try:
        _remove_tree(data_dir)
    except OSError as exc:
        raise InstallStateError(
            "Impossibile eliminare tutti i dati di OCR2: chiudi le finestre di OCR2 e riprova."
        ) from exc
    return True


def uninstall(base: Path, *, remove_user_data: bool = False, test_data_root: Path | None = None) -> str:
    """Checks before NSIS removes the program files; deletes the data only on request."""
    _refuse_while_running()
    if not remove_user_data:
        return "I dati di OCR2 restano sul computer."
    if remove_data(test_data_root):
        return "Dati di OCR2 eliminati."
    return "Nessun dato di OCR2 da eliminare."


def installed_base(package_file: Path | None = None) -> Path:
    """``<base>`` of the installed program running this module (``<base>/versions/<v>/app/<package>``)."""
    if package_file is None:
        import alfa_document_intelligence

        package_file = Path(alfa_document_intelligence.__file__)
    # Absolute, not resolved (as the launcher's program folder): keeps a short (8.3) path short.
    path = Path(os.path.abspath(package_file))
    parents = path.parents
    if len(parents) < 5 or parents[1].name != "app" or parents[3].name != VERSIONS_DIR or _VERSION.fullmatch(parents[2].name) is None:
        raise InstallStateError("install_state va eseguito dal programma installato.")
    return parents[4]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="install_state", description="Versioni installate di OCR2.")
    parser.add_argument("--base", type=Path, default=None, help=argparse.SUPPRESS)
    commands = parser.add_subparsers(dest="command", required=True)
    activate_parser = commands.add_parser("activate")
    activate_parser.add_argument("version")
    commands.add_parser("rollback")
    commands.add_parser("prune")
    commands.add_parser("check-closed")
    uninstall_parser = commands.add_parser("uninstall")
    uninstall_parser.add_argument("--remove-data", action="store_true")
    uninstall_parser.add_argument("--test-data-root", type=Path, default=None)
    for sub in (activate_parser, commands.choices["rollback"], commands.choices["prune"], commands.choices["check-closed"], uninstall_parser):
        sub.add_argument("--base", type=Path, default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        base = args.base if args.base is not None else installed_base()
        if args.command == "activate":
            activate(base, args.version)
            print(f"Versione attiva: {args.version}")
        elif args.command == "rollback":
            print(f"Versione attiva: {rollback(base)}")
        elif args.command == "check-closed":
            check_closed()
            print("OCR2 è chiuso.")
        elif args.command == "prune":
            removed = prune(base)
            print("Versioni eliminate: " + (", ".join(removed) if removed else "nessuna"))
        else:
            print(uninstall(base, remove_user_data=args.remove_data, test_data_root=args.test_data_root))
    except InstallStateError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
