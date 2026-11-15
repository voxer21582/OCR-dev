"""Synthetic library server for the M5 browser walkthrough.

Creates a NEW archive in the folder given on the command line (refusing a
non-empty one), protected with this Windows user's DPAPI, seeds it with 30
synthetic records, and serves the app on loopback. Never touches the real
archive in %LOCALAPPDATA%.

    python application/tools/m5_synthetic_library_server.py <empty-folder> [port]
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

from alfa_document_intelligence.local_document_store import LocalDocumentStore
from alfa_document_intelligence.local_intake_app import serve_expense_report_local

_FIXTURE = Path(__file__).parents[1] / "tests" / "fixtures" / "synthetic_invoice.json"


def _record(index: int, family: str, status: str) -> tuple[dict, bytes]:
    source = f"%PDF-1.4 synthetic library walkthrough {index}\n%%EOF".encode()
    digest = hashlib.sha256(source).hexdigest()
    text = _FIXTURE.read_text(encoding="utf-8")
    old = json.loads(text)["source"]["sha256"]
    record = json.loads(text.replace(old, digest))
    record["document_id"] = f"doc-{index:03d}"
    record["source"].update({"byte_length": len(source), "original_filename": f"ricevuta-sintetica-{index:03d}.pdf",
                             "storage_ref": "volatile-session://synthetic"})
    record["document_family"] = family
    record["review"]["status"] = status
    return record, source


def main(argv: list[str]) -> None:
    folder = Path(argv[1])
    if folder.exists() and any(folder.iterdir()):
        raise SystemExit("the folder must be new or empty")
    folder.mkdir(parents=True, exist_ok=True)
    store = LocalDocumentStore(folder / "document-archive.sqlite3")
    for index in range(1, 31):
        family = "invoice" if index % 2 else "fiscal_receipt"
        record, source = _record(index, family, "completed" if index % 5 == 0 else "not_started")
        store.save(record, source)
    server = serve_expense_report_local(port=int(argv[2]) if len(argv) > 2 else 8765, archive_store=store)
    host, port = server.server_address[:2]
    print(f"Synthetic library on http://{host}:{port}/archive (archive {store.path})", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main(sys.argv)
