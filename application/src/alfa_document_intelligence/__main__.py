"""Start the local browser intake app using only the existing Python environment."""
from __future__ import annotations

import argparse
import html
import importlib
import os
import platform
import re
import secrets
import sys
import tempfile
import time
import traceback
import webbrowser
from pathlib import Path
from typing import Sequence

from . import __version__
from . import runtime_manifest
from .app_instance import InstanceLock, acquire, running_instance
from .app_lifetime import AppInfo, AppLifetime, WindowPresence
from .app_window import open_window
from .local_intake_app import _SESSION_IDLE_SECONDS, serve_expense_report_local
from .local_document_store import LocalDocumentStore, StoreSchemaError
from .local_document_store import _SCHEMA_VERSION as _SUPPORTED_ARCHIVE_SCHEMA
from .document_decoder import DecodeLimits
from .document_family_catalog import DocumentFamilyCatalogError, DocumentFamilyCatalogStore
from .expense_case_processing import ExpenseCaseProcessingManager
from .ocr_engine_registry import EngineManifest, EngineRegistryError, discover_engines
from .ocr_processing import OCRProcessLimits, OCRProcessingManager


# The Edge app window and the single-instance lock are Windows features (REQ-100).
_APP_WINDOW_AVAILABLE = os.name == "nt"
# Wait for an instance that holds the lock but does not answer: it is still
# starting, or it is closing after «Esci» (or crashed) and will let go.
_STARTING_INSTANCE_WAIT_SECONDS = 15.0


def _program_folder() -> Path:
    """The installed program folder ``versions/<v>`` (R4); tests replace this function.

    Absolute but not resolved: started through a short (8.3) path, the folder keeps
    that form, so every file stays below MAX_PATH as it was when Python found it.
    """
    import alfa_document_intelligence

    return Path(os.path.abspath(alfa_document_intelligence.__file__)).parents[2]


_ERROR_PAGE = (
    '<!doctype html><html lang="it"><head><meta charset="utf-8">'
    "<title>OCR2 non si avvia</title></head>"
    '<body style="font-family:sans-serif;max-width:40em;margin:2em auto">'
    "<h1>OCR2 non si avvia</h1>"
    "<p>{message}</p><ul>{items}</ul></body></html>"
)
# R38: the installer refuses the active version, so the remedies are a rollback or
# uninstall (keeping the data) and install again; there is no in-place repair.
_RUNTIME_ERROR_MESSAGE = (
    "I file del programma non corrispondono all'installazione. "
    "Dal menu Start usa «Torna alla versione precedente», "
    "oppure disinstalla OCR2 mantenendo i dati e installalo di nuovo."
)
NEWER_ARCHIVE_MESSAGE = (
    "Questo archivio è stato aggiornato da una versione più recente di OCR2. Reinstalla quella versione."
)


def _show_error_page(message: str, problems: Sequence[str], data_dir: Path | None) -> None:
    """Write the static error page (no script) and open it as a file in the default browser.

    ``open_window`` accepts only the local server address, so the file URI goes
    through ``webbrowser.open``.
    """
    if data_dir is None:
        return
    items = "".join(f"<li>{html.escape(problem)}</li>" for problem in problems)
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        page = data_dir / "runtime-error.html"
        page.write_text(_ERROR_PAGE.replace("{message}", html.escape(message)).replace("{items}", items), encoding="utf-8")
        webbrowser.open(page.resolve().as_uri())
    except OSError:
        pass


def _show_runtime_error(problems: Sequence[str], data_dir: Path | None) -> None:
    _show_error_page(_RUNTIME_ERROR_MESSAGE, problems, data_dir)


# --- R39: in app-window mode (pythonw, no console) no failed start is silent ---

_UNEXPECTED_ERROR_MESSAGE = "OCR2 si è fermato per un errore imprevisto"
_LAUNCH_LOG_NAME = "launcher.log"
_CAPTURED_STDERR_LIMIT = 32 * 1024


class _LauncherExit(SystemExit):
    """A failed start with a one-line Italian summary; ``shown`` = its own page is already open."""

    def __init__(self, code: int, summary: str, *, shown: bool = False) -> None:
        super().__init__(code)
        self.summary = summary
        self.shown = shown


class _LauncherParser(argparse.ArgumentParser):
    """``error`` prints as argparse does (usage, message, exit 2) and keeps the message as the summary."""

    def error(self, message: str):  # type: ignore[override]
        self.print_usage(sys.stderr)
        self._print_message(f"{self.prog}: error: {message}\n", sys.stderr)
        raise _LauncherExit(2, message)


class _StderrCapture:
    """Passes writes through to the real stderr (``None`` under pythonw) and keeps the last part."""

    def __init__(self, original) -> None:
        self.original = original
        self._parts: list[str] = []
        self._size = 0

    def write(self, text: str) -> int:
        if self.original is not None:
            try:
                self.original.write(text)
            except (OSError, ValueError):
                pass
        self._parts.append(text)
        self._size += len(text)
        while self._size > _CAPTURED_STDERR_LIMIT and len(self._parts) > 1:
            self._size -= len(self._parts.pop(0))
        return len(text)

    def flush(self) -> None:
        if self.original is not None:
            try:
                self.original.flush()
            except (OSError, ValueError):
                pass

    def text(self) -> str:
        return "".join(self._parts)[-_CAPTURED_STDERR_LIMIT:]


def _report_data_dir() -> Path:
    """``<LOCALAPPDATA>/OCR2``; without LOCALAPPDATA the temporary folder, so the failure still shows."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    return Path(local_app_data or tempfile.gettempdir()) / "OCR2"


def _append_launch_log(log_path: Path, entry: str) -> None:
    """Append to ``logs/launcher.log``; never fails because logging fails."""
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(entry)
    except Exception:  # noqa: BLE001 - the report must never fail because of the log
        pass


def _report_failed_start(summary: str, details: str, *, page_shown: bool) -> None:
    data_dir = _report_data_dir()
    log_path = data_dir / "logs" / _LAUNCH_LOG_NAME
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    _append_launch_log(log_path, f"[{stamp}] OCR2 {__version__}: {summary}\n{details.rstrip()}\n\n")
    if not page_shown:
        _show_error_page(summary, (f"Dettagli nel file {log_path}",), data_dir)


def _is_app_window_argument(argument: str) -> bool:
    # argparse accepts unambiguous prefixes such as «--app».
    return len(argument) >= 5 and "--app-window".startswith(argument)


def _archive_schema_version(path: Path) -> int | None:
    """``user_version`` read from the SQLite header (bytes 60-63) without opening a connection."""
    try:
        with Path(path).open("rb") as stream:
            header = stream.read(100)
    except OSError:
        return None
    if len(header) < 64 or not header.startswith(b"SQLite format 3\x00"):
        return None
    return int.from_bytes(header[60:64], "big", signed=True)


def _open_archive(path: Path, app_window: bool) -> LocalDocumentStore:
    """Open the archive; one written by a newer OCR2 stops the start (exit 2), the file untouched.

    The store refuses a ``user_version`` above the supported one before any write;
    only that case gets the reinstall message, every other schema error propagates.
    """
    try:
        return LocalDocumentStore(path)
    except StoreSchemaError:
        version = _archive_schema_version(path)
        if version is None or version <= _SUPPORTED_ARCHIVE_SCHEMA:
            raise
    print(NEWER_ARCHIVE_MESSAGE, file=sys.stderr)
    if app_window:
        _show_error_page(NEWER_ARCHIVE_MESSAGE, (), Path(path).parent)
    raise _LauncherExit(2, NEWER_ARCHIVE_MESSAGE, shown=app_window)


_INSTALLED_VERSION = re.compile(r"\d+\.\d+\.\d+")


def _is_installed_layout(folder: Path) -> bool:
    """``versions/<x.y.z>/`` holding ``app/`` next to ``python/``, as ``install_state.installed_base`` expects (R37)."""
    return (
        folder.parent.name == "versions"
        and _INSTALLED_VERSION.fullmatch(folder.name) is not None
        and (folder / "app").is_dir()
        and (folder / "python").is_dir()
    )


def _verify_runtime(app_window: bool) -> str:
    """Check the installed files before a port is opened; exit 2 on failure. Returns the status text.

    Only a folder outside the installed layout runs from sources unverified; in
    the installed layout a missing manifest is a verification failure (R37).
    """
    program = _program_folder()
    manifest_path = program / runtime_manifest.MANIFEST_NAME
    if not manifest_path.is_file() and not _is_installed_layout(program):
        return "non verificato (avvio da sorgenti)"
    result = None
    if not manifest_path.is_file():
        problems, ok = (f"File mancante: {runtime_manifest.MANIFEST_NAME}",), False
    else:
        try:
            result = runtime_manifest.verify_installation(manifest_path.parent, manifest_path)
            problems = result.problems
            ok = result.ok
        except Exception:  # last safety net: never start unverified because verification crashed
            problems, ok = ("Verifica del runtime non riuscita",), False
    if not ok:
        print("I file di OCR2 non sono integri:", file=sys.stderr)
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
        if app_window:
            local_app_data = os.environ.get("LOCALAPPDATA")
            _show_runtime_error(problems, Path(local_app_data) / "OCR2" if local_app_data else None)
        raise _LauncherExit(2, "I file di OCR2 non sono integri: " + "; ".join(problems), shown=app_window)
    return f"verificato ({result.checked_files} file, {result.seconds:.1f} s)"


def _open_app_window(url: str, data_dir: Path) -> None:
    if open_window(url, data_dir) == "browser":
        print("Edge non trovato: OCR2 si apre nel browser predefinito.", file=sys.stderr)


def _wait_for_instance_or_lock(data_dir: Path) -> tuple[int | None, InstanceLock | None]:
    """Until the deadline: the port of an instance that answers, or the lock once it is free."""
    deadline = time.monotonic() + _STARTING_INSTANCE_WAIT_SECONDS
    while True:
        port = running_instance(data_dir)
        if port is not None:
            return port, None
        lock = acquire(data_dir)
        if lock is not None:
            return None, lock
        if time.monotonic() >= deadline:
            return None, None
        time.sleep(0.25)


def _runtime_check(manifest: EngineManifest):
    """Run the engine's start-up check named by its manifest (it must not import the engine)."""
    if manifest.runtime_check_ref is None:
        return None
    module_name, qualified_name = manifest.runtime_check_ref.split(":", 1)
    target = importlib.import_module(module_name)
    for part in qualified_name.split("."):
        target = getattr(target, part)
    return target()


def _ocr_limits() -> OCRProcessLimits:
    """Explicit provisional bounds for the opt-in local OCR worker."""
    return OCRProcessLimits(
        job_timeout_seconds=900,
        cleanup_grace_seconds=3,
        child_memory_limit_bytes=2 * 1024 * 1024 * 1024 - 1,
        max_input_frame_bytes=64 * 1024 * 1024,
        max_status_frame_bytes=4 * 1024,
        max_result_frame_bytes=16 * 1024 * 1024,
        max_aggregate_result_bytes=64 * 1024 * 1024,
        max_page_output_bytes=8 * 1024 * 1024,
        max_ipc_messages=100_000,
    )


def _port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("port must be an integer from 0 to 65535") from exc
    if not 0 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 0 and 65535")
    return port


def main(argv: Sequence[str] | None = None) -> None:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not any(_is_app_window_argument(argument) for argument in arguments):
        _main(arguments)
        return
    # R39: started by the Start-menu shortcut through pythonw, nobody sees stderr:
    # every exit other than a clean one shows a page and goes to launcher.log.
    captured = _StderrCapture(sys.stderr)
    sys.stderr = captured
    try:
        _main(arguments)
    except KeyboardInterrupt:
        raise
    except SystemExit as exc:
        if exc.code in (None, 0):
            raise
        if isinstance(exc, _LauncherExit):
            summary, page_shown = exc.summary, exc.shown
        else:
            summary, page_shown = f"OCR2 si è fermato (codice di uscita {exc.code})", False
        _report_failed_start(summary, f"codice di uscita {exc.code}\n{captured.text()}", page_shown=page_shown)
        raise
    except BaseException as exc:
        _report_failed_start(
            f"{_UNEXPECTED_ERROR_MESSAGE} ({type(exc).__name__}).",
            f"{traceback.format_exc()}\n{captured.text()}",
            page_shown=False,
        )
        raise
    finally:
        sys.stderr = captured.original


def _main(argv: Sequence[str]) -> None:
    parser = _LauncherParser(description="Start the loopback-only expense document review app.")
    parser.add_argument("--port", type=_port, default=None, help="loopback TCP port (default: 8000; 0 selects a free port)")
    try:
        engines = {engine_id: manifest for engine_id, manifest in discover_engines().items() if manifest.selectable}
    except EngineRegistryError as exc:
        parser.error(f"registro dei motori OCR non valido ({exc.code})")
    parser.add_argument(
        "--ocr-engine", choices=("disabled", *sorted(engines)), default="disabled",
        help="optional local OCR worker from the engine registry (default: disabled; an engine requires its verified local package and models)",
    )
    parser.add_argument(
        "--app-window", action="store_true",
        help="open OCR2 in its own Edge window, one instance per user; stop when the window closes (default port: 0)",
    )
    args = parser.parse_args(argv)
    if args.port is None:
        args.port = 0 if args.app_window else 8000

    instance_lock = None
    app_data_dir = None
    if args.app_window:
        if not _APP_WINDOW_AVAILABLE:
            parser.error("La finestra dell'app è disponibile solo su Windows")
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            parser.error("LOCALAPPDATA non è disponibile: archivio locale non inizializzabile")
        app_data_dir = Path(local_app_data) / "OCR2"
        running_port = running_instance(app_data_dir)
        if running_port is None:
            instance_lock = acquire(app_data_dir)
            if instance_lock is None:
                running_port, instance_lock = _wait_for_instance_or_lock(app_data_dir)
                if running_port is None and instance_lock is None:
                    message = "OCR2 è già in avvio ma non risponde. Riprova tra qualche secondo."
                    print(message, file=sys.stderr)
                    raise _LauncherExit(1, message)
        if running_port is not None:
            _open_app_window(f"http://127.0.0.1:{running_port}/", app_data_dir)
            return
    try:
        # An instance that was already running verified the runtime at its own start (R19).
        runtime_status = _verify_runtime(args.app_window)
        _serve(parser, args, engines, app_data_dir, instance_lock, runtime_status)
    finally:
        if instance_lock is not None:
            instance_lock.release()


def _serve(parser, args, engines, app_data_dir, instance_lock, runtime_status) -> None:
    manifest = engines.get(args.ocr_engine)
    if manifest is not None:
        runtime = _runtime_check(manifest)
        if runtime is not None:
            for warning in runtime.warnings:
                print(f"Attenzione: {warning}.", file=sys.stderr)
            if not runtime.ok:
                parser.error("OCR locale non utilizzabile: " + "; ".join(runtime.problems))

    archive_store = None
    family_catalog_store = None
    custom_family_catalog = None
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            parser.error("LOCALAPPDATA non è disponibile: archivio locale non inizializzabile")
        archive_store = _open_archive(Path(local_app_data) / "OCR2" / "document-archive.sqlite3", args.app_window)
        # The user's document-type catalog (REQ-041) lives next to the archive.
        family_catalog_store = DocumentFamilyCatalogStore(Path(local_app_data) / "OCR2" / "family-catalog.json")
        try:
            custom_family_catalog = family_catalog_store.load()
        except DocumentFamilyCatalogError:
            print("Attenzione: catalogo dei tipi non valido: ignorato. Correggilo dalla pagina Catalogo.", file=sys.stderr)
            custom_family_catalog = None
    ocr_manager = None
    if manifest is not None:
        ocr_manager = OCRProcessingManager(
            manifest.factory_ref, _ocr_limits(), expected_identity=(manifest.name, manifest.version),
        )
    case_processing_manager = None
    if archive_store is not None and ocr_manager is not None:
        case_processing_manager = ExpenseCaseProcessingManager(
            archive_store,
            ocr_manager,
            _ocr_limits(),
            DecodeLimits(),
            close_worker_on_close=False,
            custom_family_catalog=custom_family_catalog,
        )
    app_services = {}
    app_lifetime = None
    if args.app_window:
        server_holder = []
        # The guard thread stops the server; it starts only after the server exists.
        # R41: a window restored by navigation (e.g. the raw view of an original
        # document) lives as long as the session idle time, not 180 s.
        presence = WindowPresence(navigation_expiry_seconds=_SESSION_IDLE_SECONDS)
        app_lifetime = AppLifetime(presence, lambda: server_holder[0].shutdown())
        instance_id = secrets.token_urlsafe(16)
        app_services = {
            "app_lifetime": app_lifetime,
            "app_info": AppInfo(
                version=__version__,
                python_version=platform.python_version(),
                ocr_engine=None if manifest is None else f"{manifest.name} {manifest.version}",
                runtime_status=runtime_status,
                instance_id=instance_id,
            ),
        }
    server = serve_expense_report_local(
        port=args.port,
        archive_store=archive_store,
        ocr_processing_manager=ocr_manager,
        expense_case_processing_manager=case_processing_manager,
        custom_family_catalog=custom_family_catalog,
        family_catalog_store=family_catalog_store,
        **app_services,
    )
    host, port = server.server_address[:2]
    print(f"Apri http://{host}:{port}/ nel browser. Il server ascolta solo su loopback.")
    if ocr_manager is None:
        print("OCR resta disattivato. Nessun motore o modello è stato caricato.")
    else:
        print(
            f"OCR locale {manifest.name} {manifest.version} abilitato su richiesta; "
            "pacchetto, modelli e identità del motore saranno verificati nel worker isolato."
        )
    if archive_store is not None:
        print(f"Archivio locale cifrato attivo: {archive_store.path}")
    else:
        print("Archivio persistente non disponibile fuori da Windows senza un protettore esplicito.")
    try:
        if app_lifetime is not None:
            server_holder.append(server)
            instance_lock.publish(port, instance_id)
            _open_app_window(f"http://{host}:{port}/", app_data_dir)
            app_lifetime.start()
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArresto richiesto.")
    finally:
        if app_lifetime is not None:
            # Ends the guard thread; shutdown() on a stopped server returns at once.
            app_lifetime.request_exit()
        close_app = getattr(server, "ocr2_close", None)
        if callable(close_app):
            close_app()
        server.server_close()


if __name__ == "__main__":
    main()
