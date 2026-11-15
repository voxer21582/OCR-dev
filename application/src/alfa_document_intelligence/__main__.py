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

from . import __version__
from .app_instance import acquire, running_instance
from .app_lifetime import AppInfo, AppLifetime, WindowPresence
from .app_window import open_window
from .local_intake_app import serve_expense_report_local
from .local_document_store import LocalDocumentStore
from .document_decoder import DecodeLimits
from .document_family_catalog import DocumentFamilyCatalogError, DocumentFamilyCatalogStore
from .expense_case_processing import ExpenseCaseProcessingManager
from .ocr_engine_registry import EngineManifest, EngineRegistryError, discover_engines
from .ocr_processing import OCRProcessLimits, OCRProcessingManager


# The Edge app window and the single-instance lock are Windows features (REQ-100).
_APP_WINDOW_AVAILABLE = os.name == "nt"
# Wait for an instance that holds the lock but has not published its port yet.
_STARTING_INSTANCE_WAIT_SECONDS = 15.0


def _open_app_window(url: str, data_dir: Path) -> None:
    if open_window(url, data_dir) == "browser":
        print("Edge non trovato: OCR2 si apre nel browser predefinito.", file=sys.stderr)


def _wait_for_running_instance(data_dir: Path) -> int | None:
    deadline = time.monotonic() + _STARTING_INSTANCE_WAIT_SECONDS
    while True:
        port = running_instance(data_dir)
        if port is not None or time.monotonic() >= deadline:
            return port
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
    parser = argparse.ArgumentParser(description="Start the loopback-only expense document review app.")
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
                # Another launcher holds the lock and is still starting.
                running_port = _wait_for_running_instance(app_data_dir)
                if running_port is None:
                    print("OCR2 è già in avvio ma non risponde. Riprova tra qualche secondo.", file=sys.stderr)
                    raise SystemExit(1)
        if running_port is not None:
            _open_app_window(f"http://127.0.0.1:{running_port}/", app_data_dir)
            return
    try:
        _serve(parser, args, engines, app_data_dir, instance_lock)
    finally:
        if instance_lock is not None:
            instance_lock.release()


def _serve(parser, args, engines, app_data_dir, instance_lock) -> None:
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
        archive_store = LocalDocumentStore(
            Path(local_app_data) / "OCR2" / "document-archive.sqlite3"
        )
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
                runtime_status="non verificato (avvio da sorgenti)",
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
