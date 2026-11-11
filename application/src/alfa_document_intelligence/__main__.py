"""Start the local browser intake app using only the existing Python environment."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Sequence

from .local_intake_app import serve_expense_report_local
from .local_document_store import LocalDocumentStore
from .ocr_processing import OCRProcessLimits, OCRProcessingManager


_RAPIDOCR_FACTORY = (
    "alfa_document_intelligence.rapidocr_runtime_factory:"
    "create_rapidocr_v6_multilingual_adapter"
)


def _rapidocr_limits() -> OCRProcessLimits:
    """Explicit provisional bounds for the opt-in local RapidOCR worker."""
    return OCRProcessLimits(
        job_timeout_seconds=300,
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
    parser.add_argument(
        "--ocr-engine", choices=("disabled", "rapidocr-v6"), default="disabled",
        help="optional local OCR worker (default: disabled; rapidocr-v6 requires verified local package and models)",
    )
    args = parser.parse_args(argv)

    archive_store = None
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            parser.error("LOCALAPPDATA non è disponibile: archivio locale non inizializzabile")
        archive_store = LocalDocumentStore(
            Path(local_app_data) / "OCR2" / "document-archive.sqlite3"
        )
    ocr_manager = None
    if args.ocr_engine == "rapidocr-v6":
        ocr_manager = OCRProcessingManager(_RAPIDOCR_FACTORY, _rapidocr_limits())
    server = serve_expense_report_local(
        port=args.port,
        archive_store=archive_store,
        ocr_processing_manager=ocr_manager,
    )
    host, port = server.server_address[:2]
    print(f"Apri http://{host}:{port}/ nel browser. Il server ascolta solo su loopback.")
    if ocr_manager is None:
        print("OCR resta disattivato. Nessun motore o modello è stato caricato.")
    else:
        print("OCR locale RapidOCR v6 abilitato su richiesta; pacchetto e hash dei modelli saranno verificati nel worker isolato.")
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
