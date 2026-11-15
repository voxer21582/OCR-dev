"""Start the local browser intake app using only the existing Python environment."""
from __future__ import annotations

import argparse
import importlib
import os
import sys
from pathlib import Path
from typing import Sequence

from .local_intake_app import serve_expense_report_local
from .local_document_store import LocalDocumentStore
from .document_decoder import DecodeLimits
from .expense_case_processing import ExpenseCaseProcessingManager
from .ocr_engine_registry import EngineManifest, EngineRegistryError, discover_engines
from .ocr_processing import OCRProcessLimits, OCRProcessingManager


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
    parser.add_argument("--port", type=_port, default=8000, help="loopback TCP port (default: 8000; 0 selects a free port)")
    try:
        engines = {engine_id: manifest for engine_id, manifest in discover_engines().items() if manifest.selectable}
    except EngineRegistryError as exc:
        parser.error(f"registro dei motori OCR non valido ({exc.code})")
    parser.add_argument(
        "--ocr-engine", choices=("disabled", *sorted(engines)), default="disabled",
        help="optional local OCR worker from the engine registry (default: disabled; an engine requires its verified local package and models)",
    )
    args = parser.parse_args(argv)

    manifest = engines.get(args.ocr_engine)
    if manifest is not None:
        runtime = _runtime_check(manifest)
        if runtime is not None:
            for warning in runtime.warnings:
                print(f"Attenzione: {warning}.", file=sys.stderr)
            if not runtime.ok:
                parser.error("OCR locale non utilizzabile: " + "; ".join(runtime.problems))

    archive_store = None
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            parser.error("LOCALAPPDATA non è disponibile: archivio locale non inizializzabile")
        archive_store = LocalDocumentStore(
            Path(local_app_data) / "OCR2" / "document-archive.sqlite3"
        )
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
        )
    server = serve_expense_report_local(
        port=args.port,
        archive_store=archive_store,
        ocr_processing_manager=ocr_manager,
        expense_case_processing_manager=case_processing_manager,
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
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArresto richiesto.")
    finally:
        close_app = getattr(server, "ocr2_close", None)
        if callable(close_app):
            close_app()
        server.server_close()


if __name__ == "__main__":
    main()
