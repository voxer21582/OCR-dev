"""Start the local browser intake app using only the existing Python environment."""
from __future__ import annotations

import argparse
import importlib
import os
import platform
import secrets
import sys
import time
from pathlib import Path
from typing import Sequence

# Remedies the installer accepts: reinstalling replaces a damaged version, and
# the Start-menu entry activates the previous one (R38, from #151).
_REPAIR_ADVICE = (
    "Installa di nuovo OCR2 con il suo installer, oppure dal menu Start usa "
    "«Torna alla versione precedente»."
)
_START_FAILURE_MESSAGE = (
    "Impossibile avviare OCR2. Attendi la fine di eventuali installazioni o disinstallazioni "
    "di OCR2 e riprova; se il problema resta, installa di nuovo OCR2 con il suo installer."
)


class _SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        # argparse errors can echo untrusted argument values and program paths.
        safe_messages = {
            "La finestra dell'app è disponibile solo su Windows",
            "LOCALAPPDATA non è disponibile: archivio locale non inizializzabile",
        }
        detail = message if message in safe_messages else "argomenti o configurazione non validi"
        self.exit(2, f"OCR2_ARGUMENT_ERROR: {detail}.\n")


# The dialogs stay generic; the launch log contains stable, non-sensitive codes.
_LAUNCH_LOG_HINT = "Dettagli in %LOCALAPPDATA%\\OCR2\\logs\\launcher-safe.log"
_LAUNCH_LOG_LIMIT_BYTES = 256 * 1024
_LAUNCH_LOG_ENTRY_BYTES = 64 * 1024
_LAUNCH_LOG_CODES = {
    'import': 'OCR2_START_IMPORT',
    'integrità': 'OCR2_START_INTEGRITY',
    'archivio più recente': 'OCR2_START_ARCHIVE_VERSION',
    'uscita anomala': 'OCR2_START_EXIT',
    'eccezione': 'OCR2_START_EXCEPTION',
}


def _write_launch_log(kind: str, message: str = "", error: BaseException | None = None) -> None:
    """Append a start-up failure to the separate safe log; never raise.

    Only fixed event codes are persisted. Arbitrary exception messages, stderr,
    paths, identifiers and tracebacks are deliberately excluded.
    """
    try:
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data or not os.path.isabs(local_app_data):
            return
        code = _LAUNCH_LOG_CODES.get(kind, 'OCR2_START_OTHER')
        data = f"=== {time.strftime('%Y-%m-%dT%H:%M:%S%z')} · {code} ===\n\n".encode('utf-8')
        folder = os.path.join(local_app_data, "OCR2", "logs")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, "launcher-safe.log")
        # No lock between processes: two launchers failing at the same moment
        # may interleave their entries or both rotate. Accepted, because only a
        # failed start writes and a second launcher normally just reuses the
        # running instance.
        try:
            if os.path.getsize(path) + len(data) > _LAUNCH_LOG_LIMIT_BYTES:
                os.replace(path, path + ".1")
        except OSError:
            pass  # No log yet, or the backup cannot be replaced: append anyway.
        with open(path, "ab") as log:
            log.write(data)
    except Exception:
        pass  # The log is a help; the dialog and the original error come first.


class _StderrTail:
    """Forward stderr (absent under pythonw) and keep its end for the launch log."""

    def __init__(self, target, limit: int = 16 * 1024) -> None:
        self.target = target
        self.limit = limit
        self.text = ""
        self.capturing = True

    def write(self, text):
        if self.capturing:
            try:
                self.text = (self.text + str(text))[-self.limit:]
            except Exception:
                pass
        if self.target is None:
            return len(text)
        return self.target.write(text)

    def flush(self) -> None:
        if self.target is not None:
            self.target.flush()


def _end_startup_capture() -> None:
    """Stop keeping stderr once the server is about to serve.

    After start-up stderr carries request lines (search terms, tags, document
    ids): they must never reach the plaintext launch log. The original stream
    comes back, so under pythonw sys.stderr is None again, as before.
    """
    tail = sys.stderr
    if isinstance(tail, _StderrTail):
        tail.capturing = False
        tail.text = ""
        sys.stderr = tail.target


def _emit_stable_code(code: str) -> None:
    try:
        stream = sys.stderr
        if stream is not None:
            stream.write(code + "\n")
            stream.flush()
    except Exception:
        pass  # Reporting must never raise from inside a hook.


def _thread_exception_hook(args) -> None:
    # The default hook prints the thread name, a traceback with installation
    # paths and the exception message, which can carry document text (REQ-124).
    if args.exc_type is SystemExit:
        return  # The default hook ignores SystemExit too.
    _emit_stable_code("OCR2_THREAD_ERROR")


def _unraisable_hook(unraisable) -> None:
    # The default hook prints the object's repr and a traceback (REQ-124).
    _emit_stable_code("OCR2_UNRAISABLE_ERROR")


def _warning_hook(message, category, filename, lineno, file=None, line=None) -> None:
    # The default prints the source file path (the installation, with the user
    # name), the line and the warning text, which can carry a value (REQ-124).
    _emit_stable_code("OCR2_PYTHON_WARNING")


def _install_safe_exception_hooks() -> None:
    """Report errors and warnings outside the main flow as stable codes only."""
    import threading
    import warnings

    threading.excepthook = _thread_exception_hook
    sys.unraisablehook = _unraisable_hook
    warnings.showwarning = _warning_hook


def _show_bootstrap_error() -> None:
    """Make an application import failure visible in window mode; details go to the launch log."""
    if os.name == "nt" and "--app-window" in sys.argv[1:]:
        _write_launch_log("import", error=sys.exc_info()[1])
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                None, "Impossibile avviare OCR2. " + _REPAIR_ADVICE + "\n\n" + _LAUNCH_LOG_HINT,
                "OCR2 — avvio non riuscito", 0x10,
            )
        except Exception:
            pass  # Preserve the original import failure.


try:
    from . import __version__
    from .app_instance import InstanceLock, acquire, running_instance
    from .app_lifetime import AppInfo, AppLifetime, WindowPresence
    from .app_window import open_window
    from .local_intake_app import serve_expense_report_local
    from .local_document_store import LocalDocumentStore, NewerStoreSchemaError
    from .document_decoder import DecodeLimits
    from .document_family_catalog import DocumentFamilyCatalogError, DocumentFamilyCatalogStore
    from .expense_case_processing import ExpenseCaseProcessingManager
    from .ocr_engine_registry import EngineManifest, EngineRegistryError, discover_engines
    from .ocr_processing import OCRProcessLimits, OCRProcessingManager
    from .runtime_manifest import verify_installation
except Exception:
    _show_bootstrap_error()
    if __name__ == "__main__":
        try:
            if sys.stderr is not None:
                print("OCR2_START_IMPORT", file=sys.stderr)
        except Exception:
            pass
        raise SystemExit(1) from None
    raise


# The Edge app window and the single-instance lock are Windows features (REQ-100).
_APP_WINDOW_AVAILABLE = os.name == "nt"
# Wait for an instance that holds the lock but does not answer: it is still
# starting, or it is closing after «Esci» (or crashed) and will let go.
_STARTING_INSTANCE_WAIT_SECONDS = 15.0
_startup_error_shown = False


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


def _installation_root() -> Path:
    return Path(sys.executable).resolve().parent.parent


def _is_installed(root: Path) -> bool:
    return Path(__file__).resolve().parent.parent == (root / "app").resolve()


def _show_error_dialog(message: str, title: str) -> None:
    """Report a local startup error without starting a server; the details are in the launch log."""
    global _startup_error_shown
    if os.name == "nt":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message + "\n\n" + _LAUNCH_LOG_HINT, title, 0x10)
        _startup_error_shown = True


def _show_integrity_error(message: str) -> None:
    _show_error_dialog(message, "OCR2 — installazione non valida")


def _show_startup_error(message: str) -> None:
    _show_error_dialog(message, "OCR2 — avvio non riuscito")


def main(argv: Sequence[str] | None = None) -> None:
    parser = _SafeArgumentParser(description="Start the loopback-only expense document review app.")
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

    install_root = _installation_root()
    runtime_manifest = install_root / "runtime-manifest.json"
    runtime_status = "non verificato (avvio da sorgenti)"
    if runtime_manifest.exists() or runtime_manifest.is_symlink() or _is_installed(install_root):
        verification = verify_installation(install_root, runtime_manifest)
        if not verification.ok:
            message = "Installazione non valida (OCR2_START_INTEGRITY). " + _REPAIR_ADVICE
            print(message, file=sys.stderr)
            if args.app_window:
                _write_launch_log("integrità", message)
                _show_integrity_error(message)
            raise SystemExit(2)
        runtime_status = "verificato"

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
                    print("OCR2 è già in avvio ma non risponde. Riprova tra qualche secondo.", file=sys.stderr)
                    raise SystemExit(1)
        if running_port is not None:
            _open_app_window(f"http://127.0.0.1:{running_port}/", app_data_dir)
            return
    elif os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            parser.error("LOCALAPPDATA non è disponibile: archivio locale non inizializzabile")
        instance_lock = acquire(Path(local_app_data) / "OCR2")
        if instance_lock is None:
            print("OCR2 è già in uso o in manutenzione. Chiudilo e riprova.", file=sys.stderr)
            raise SystemExit(1)
    try:
        _serve(parser, args, engines, app_data_dir, instance_lock, runtime_status)
    finally:
        if instance_lock is not None:
            instance_lock.release()


def _serve(parser, args, engines, app_data_dir, instance_lock, runtime_status="non verificato (avvio da sorgenti)") -> None:
    manifest = engines.get(args.ocr_engine)
    if manifest is not None:
        runtime = _runtime_check(manifest)
        if runtime is not None:
            for warning in runtime.warnings:
                if warning == "pypdfium2 non è installato: i PDF non possono essere letti":
                    print("Attenzione: pypdfium2 non è installato: i PDF non possono essere letti.", file=sys.stderr)
                else:
                    print("OCR2_OCR_RUNTIME_WARNING", file=sys.stderr)
            if not runtime.ok:
                parser.exit(2, "OCR2_OCR_RUNTIME_ERROR: OCR locale non utilizzabile.\n")

    archive_store = None
    family_catalog_store = None
    custom_family_catalog = None
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            parser.error("LOCALAPPDATA non è disponibile: archivio locale non inizializzabile")
        try:
            archive_store = LocalDocumentStore(
                Path(local_app_data) / "OCR2" / "document-archive.sqlite3"
            )
        except NewerStoreSchemaError:
            message = "Questo archivio è stato aggiornato da una versione più recente di OCR2. Reinstalla quella versione."
            print(message, file=sys.stderr)
            if args.app_window:
                _write_launch_log("archivio più recente", message)
                _show_error_dialog(message, "OCR2 — archivio non compatibile")
            raise SystemExit(2)
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
        app_lifetime = AppLifetime(WindowPresence(), lambda: server_holder[0].shutdown())
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
        print("Archivio locale cifrato attivo.")
    else:
        print("Archivio persistente non disponibile fuori da Windows senza un protettore esplicito.")
    try:
        if app_lifetime is not None:
            server_holder.append(server)
            instance_lock.publish(port, instance_id)
            _open_app_window(f"http://{host}:{port}/", app_data_dir)
            app_lifetime.start()
        _end_startup_capture()
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


def _run_entrypoint(argv: Sequence[str] | None = None) -> None:
    """Show a generic error for window-mode failures otherwise hidden by pythonw, and log the details."""
    global _startup_error_shown
    _startup_error_shown = False
    arguments = list(sys.argv[1:] if argv is None else argv)
    window = "--app-window" in arguments
    stderr_tail = None
    if window:
        # parser.error() and the launcher's own messages go to stderr, which
        # pythonw discards: keep their end for the log.
        stderr_tail = _StderrTail(sys.stderr)
        sys.stderr = stderr_tail
    try:
        main(arguments)
    except SystemExit as exc:
        code = exc.code
        successful_exit = code is None or (issubclass(type(code), int) and int.__int__(code) == 0)
        if not successful_exit and window and not _startup_error_shown:
            _write_launch_log("uscita anomala")
            _show_startup_error(_START_FAILURE_MESSAGE)
        raise
    except Exception as exc:
        if window:
            _write_launch_log("eccezione")
            if not _startup_error_shown:
                _show_startup_error(_START_FAILURE_MESSAGE)
        raise
    finally:
        if stderr_tail is not None and sys.stderr is stderr_tail:
            sys.stderr = stderr_tail.target


def _cli_entrypoint() -> None:
    """Keep unexpected exception details out of the process output."""
    _install_safe_exception_hooks()
    try:
        _run_entrypoint()
    except SystemExit as exc:
        if exc.code is None:
            raise
        if issubclass(type(exc.code), int):
            raise SystemExit(int.__int__(exc.code)) from None
        raise SystemExit(1) from None
    except Exception:
        try:
            if sys.stderr is not None:
                print("OCR2_UNEXPECTED_ERROR", file=sys.stderr)
        except Exception:
            pass
        raise SystemExit(1) from None


if __name__ == "__main__":
    _cli_entrypoint()
