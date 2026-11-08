"""Start the local browser intake app using only the existing Python environment."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Sequence

from .local_intake_app import serve_expense_report_local
from .local_document_store import LocalDocumentStore


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
    args = parser.parse_args(argv)

    archive_store = None
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            parser.error("LOCALAPPDATA non è disponibile: archivio locale non inizializzabile")
        archive_store = LocalDocumentStore(
            Path(local_app_data) / "OCR2" / "document-archive.sqlite3"
        )
    server = serve_expense_report_local(port=args.port, archive_store=archive_store)
    host, port = server.server_address[:2]
    print(f"Apri http://{host}:{port}/ nel browser. Il server ascolta solo su loopback.")
    print("OCR resta disattivato finché non viene fornito un processore locale.")
    if archive_store is not None:
        print(f"Archivio locale cifrato attivo: {archive_store.path}")
    else:
        print("Archivio persistente non disponibile fuori da Windows senza un protettore esplicito.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArresto richiesto.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
