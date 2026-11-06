"""Measure synthetic 1,000-document browser intake without running OCR."""
from __future__ import annotations

import io
import json
import time
import tracemalloc
from urllib.parse import urlencode
import zipfile

from alfa_document_intelligence.local_intake_app import create_expense_report_app


_DOCUMENTS = 1_000
_ARCHIVE_COUNT = 10
_DOCUMENTS_PER_ARCHIVE = 100


def _synthetic_archives() -> list[tuple[str, bytes]]:
    archives: list[tuple[str, bytes]] = []
    for archive_number in range(_ARCHIVE_COUNT):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
            for member_number in range(_DOCUMENTS_PER_ARCHIVE):
                unique = archive_number * _DOCUMENTS_PER_ARCHIVE + member_number
                archive.writestr(
                    f"trip-{archive_number:02d}/receipt-{member_number:03d}.pdf",
                    f"%PDF-1.7\nsynthetic receipt {unique:04d}\n".encode("ascii"),
                )
        archives.append((f"trip-{archive_number:02d}.zip", buffer.getvalue()))
    return archives


def _multipart(files: list[tuple[str, bytes]], boundary: str = "synthetic-load-boundary") -> bytes:
    chunks = []
    for filename, data in files:
        headers = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="files"; filename="{filename}"\r\n'
            "Content-Type: application/zip\r\n\r\n"
        ).encode("ascii")
        chunks.extend((headers, data, b"\r\n"))
    chunks.append(f"--{boundary}--\r\n".encode("ascii"))
    return b"".join(chunks)


def _request(app, method: str, path: str, body: bytes, content_type: str) -> tuple[str, bytes]:
    response: dict[str, object] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        response["status"] = status

    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "CONTENT_LENGTH": str(len(body)),
        "CONTENT_TYPE": content_type,
        "wsgi.input": io.BytesIO(body),
    }
    output = b"".join(app(environ, start_response))
    return str(response.get("status", "missing status")), output


def main() -> None:
    generation_started = time.perf_counter()
    archives = _synthetic_archives()
    body = _multipart(archives)
    generation_ms = (time.perf_counter() - generation_started) * 1000
    input_bytes = len(body)

    app = create_expense_report_app()
    tracemalloc.start()
    upload_started = time.perf_counter()
    status, choice_page = _request(
        app, "POST", "/upload", body, "multipart/form-data; boundary=synthetic-load-boundary"
    )
    upload_ms = (time.perf_counter() - upload_started) * 1000
    if status != "200 OK" or b"doc-1000" not in choice_page:
        raise SystemExit("synthetic intake did not materialize 1,000 documents")

    assignment_started = time.perf_counter()
    status, bundle_page = _request(
        app, "POST", "/assign-note", urlencode({"note_document_id": "doc-001"}).encode("ascii"),
        "application/x-www-form-urlencoded",
    )
    bundle_ms = (time.perf_counter() - assignment_started) * 1000
    if status != "200 OK" or bundle_page.count(b"Riferimento benchmark:") != _DOCUMENTS:
        raise SystemExit("synthetic bundle did not link all 1,000 documents")

    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    total_ms = upload_ms + bundle_ms
    print(json.dumps({
        "workload": "synthetic_local_intake_only",
        "documents": _DOCUMENTS,
        "archives": _ARCHIVE_COUNT,
        "documents_per_archive": _DOCUMENTS_PER_ARCHIVE,
        "input_bytes": input_bytes,
        "generation_ms": round(generation_ms, 3),
        "upload_materialization_ms": round(upload_ms, 3),
        "note_assignment_and_bundle_render_ms": round(bundle_ms, 3),
        "intake_total_ms": round(total_ms, 3),
        "intake_documents_per_second": round(_DOCUMENTS * 1000 / total_ms, 3) if total_ms > 0 else None,
        "tracemalloc_peak_mb": round(peak_bytes / (1024 * 1024), 3),
        "ocr_executed": False,
        "real_documents_used": False,
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
