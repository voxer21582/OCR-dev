"""Synthetic WSGI coverage for persistent expense-case intake routes."""
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from alfa_document_intelligence.local_document_store import LocalDocumentStore
from alfa_document_intelligence.local_intake_app import create_expense_report_app
from alfa_document_intelligence.expense_case_processing import ExpenseCaseJobStatus
from test_local_document_store import SyntheticProtector


NOTE = b"%PDF-1.7\nsynthetic final expense statement\n"
RECEIPT = b"%PDF-1.7\nsynthetic supporting receipt\n"


def _multipart(files, boundary="case-boundary", fields=None):
    parts = []
    for name, value in (fields or {}).items():
        parts.extend((
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
            str(value).encode("utf-8"),
            b"\r\n",
        ))
    for filename, data in files:
        parts.extend((
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="files"; filename="{filename}"\r\n'.encode(),
            b"Content-Type: application/pdf\r\n\r\n",
            data,
            b"\r\n",
        ))
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _request(app, method="GET", path="/", body=b"", content_type="", headers=None, host="127.0.0.1:8080", origin="http://127.0.0.1:8080"):
    response = {}

    def start_response(status, response_headers):
        response["status"] = status
        response["headers"] = dict(response_headers)

    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "HTTP_HOST": host,
        "HTTP_ORIGIN": origin,
        "CONTENT_LENGTH": str(len(body)) if body else "",
        "CONTENT_TYPE": content_type,
        "wsgi.input": io.BytesIO(body),
    }
    for name, value in (headers or {}).items():
        environ[name] = value
    payload = b"".join(app(environ, start_response))
    return response["status"], response["headers"], payload


class ExpenseCaseIntakeRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = LocalDocumentStore(Path(self.temp.name) / "archive.sqlite3", protector=SyntheticProtector())
        self.app = create_expense_report_app(archive_store=self.store)
        self.addCleanup(self.app.close)

    def test_statement_and_bounded_attachments_create_resumable_private_case(self):
        status, _, index_page = _request(self.app, path="/cases")
        self.assertEqual(status, "200 OK")
        self.assertIn(b'action="/cases"', index_page)
        self.assertIn(b'name="files"', index_page)
        case_id = "case-" + "a" * 36
        body, content_type = _multipart([("nota riservata.pdf", NOTE)], fields={"_case_id": case_id})
        status, headers, created = _request(self.app, "POST", "/cases", body, content_type)
        self.assertEqual(status, "201 Created")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn(case_id.encode(), created)
        self.assertNotIn("nota riservata.pdf", created.decode())
        status, _, replay_create = _request(self.app, "POST", "/cases", body, content_type)
        self.assertEqual(status, "200 OK")
        self.assertIn(b"non ha duplicato", replay_create)
        self.assertEqual(len(self.store.list_cases()), 1)

        status, _, snapshot = _request(self.app, path=f"/cases/{case_id}")
        self.assertEqual(status, "200 OK")
        safe_status = json.loads(snapshot)
        self.assertEqual(safe_status["attachment_count"], 0)
        self.assertEqual(safe_status["document_count"], 1)
        self.assertNotIn(b"nota riservata", snapshot)
        self.assertNotIn(b"sha256", snapshot.lower())

        revision = safe_status["case_revision"]
        fields = {"_case_revision": revision, "_chunk_id": "upload-01"}
        batch, batch_type = _multipart([("hotel.pdf", RECEIPT), ("taxi.pdf", RECEIPT + b"second")], fields=fields)
        status, _, accepted = _request(
            self.app, "POST", f"/cases/{case_id}/attachments", batch, batch_type,
        )
        self.assertEqual(status, "200 OK")
        self.assertIn(b"Lotto acquisito: 2 giustificativi", accepted)
        accepted_state = json.loads(_request(self.app, path=f"/cases/{case_id}")[2])
        self.assertEqual(accepted_state["attachment_count"], 2)
        self.assertEqual(len(self.store.get_case(case_id)["attachments"]), 2)

        status, _, replay = _request(
            self.app, "POST", f"/cases/{case_id}/attachments", batch, batch_type,
        )
        self.assertEqual(status, "200 OK")
        self.assertIn(b"Lotto acquisito: 2 giustificativi", replay)
        self.assertEqual(json.loads(_request(self.app, path=f"/cases/{case_id}")[2]), accepted_state)
        self.assertEqual(len(self.store.get_case(case_id)["attachments"]), 2)

        changed, changed_type = _multipart([("hotel.pdf", RECEIPT + b"changed")], fields=fields)
        status, _, _ = _request(
            self.app, "POST", f"/cases/{case_id}/attachments", changed, changed_type,
        )
        self.assertEqual(status, "409 Conflict")

    def test_processing_is_explicitly_opt_in_and_status_route_exposes_only_aggregates(self):
        case_id = "case-" + "e" * 36
        body, content_type = _multipart([("private-statement.pdf", NOTE)], fields={"_case_id": case_id})
        status, _, _ = _request(self.app, "POST", "/cases", body, content_type)
        self.assertEqual(status, "201 Created")
        case = self.store.get_case(case_id)
        intake_page = _request(self.app, path=f"/cases/{case_id}/intake")[2]
        self.assertNotIn(b"/process", intake_page)

        class ProcessingManager:
            def __init__(self):
                self.status = None

            def start(self, requested_case_id, revision):
                self.status = ExpenseCaseJobStatus(
                    "a" * 32, requested_case_id, "queued", 0, 1, 0, None,
                )
                self.revision = revision
                return self.status.job_id

            def snapshot(self, job_id):
                return self.status if self.status and self.status.job_id == job_id else None

            def cancel(self, job_id):
                self.status = ExpenseCaseJobStatus(
                    self.status.job_id, self.status.case_id, "cancelled", 0, 1, 0, None,
                )

            def close(self):
                pass

        manager = ProcessingManager()
        app = create_expense_report_app(archive_store=self.store, expense_case_processing_manager=manager)
        self.addCleanup(app.close)
        intake_page = _request(app, path=f"/cases/{case_id}/intake")[2]
        self.assertIn(b"Avvia OCR locale", intake_page)
        form = f"_case_revision={case['case_revision']}".encode("ascii")
        status, _, started = _request(
            app, "POST", f"/cases/{case_id}/process", form,
            "application/x-www-form-urlencoded",
        )
        self.assertEqual(status, "202 Accepted")
        self.assertIn(b"Documenti: 0 / 1", started)
        job_id = manager.status.job_id
        status, _, job_page = _request(app, path=f"/cases/{case_id}/jobs/{job_id}")
        self.assertEqual(status, "200 OK")
        self.assertNotIn(b"private-statement.pdf", job_page)
        self.assertNotIn(b"sha256", job_page.lower())
        status, _, cancelled = _request(app, "POST", f"/cases/{case_id}/jobs/{job_id}/cancel")
        self.assertEqual(status, "200 OK")
        self.assertIn(b"Elaborazione annullata", cancelled)

    def test_case_mutations_reject_wrong_origin_before_consuming_request(self):
        body, content_type = _multipart([("nota.pdf", NOTE)])
        consumed = io.BytesIO(body)
        response = {}

        def start_response(status, headers):
            response["status"] = status

        environ = {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": "/cases",
            "HTTP_HOST": "127.0.0.1:8080",
            "HTTP_ORIGIN": "https://evil.example",
            "CONTENT_LENGTH": str(len(body)),
            "CONTENT_TYPE": content_type,
            "wsgi.input": consumed,
        }
        b"".join(self.app(environ, start_response))
        self.assertEqual(response["status"], "403 Forbidden")
        self.assertEqual(consumed.tell(), 0)
        self.assertEqual(self.store.list_cases(), [])

    def test_case_creation_rejects_zip_that_expands_to_multiple_documents(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("statement.pdf", NOTE)
            archive.writestr("receipt.pdf", RECEIPT)
        body, content_type = _multipart([("bundle.zip", buffer.getvalue())], fields={"_case_id": "case-" + "b" * 36})
        status, _, response = _request(self.app, "POST", "/cases", body, content_type)
        self.assertEqual(status, "400 Bad Request")
        self.assertNotIn(b"statement.pdf", response)
        self.assertEqual(self.store.list_cases(), [])

    def test_attachment_chunk_rejects_more_than_twenty_materialized_documents(self):
        create_case_id = "case-" + "c" * 36
        create_body, create_type = _multipart([("nota.pdf", NOTE)], fields={"_case_id": create_case_id})
        status, _, created = _request(self.app, "POST", "/cases", create_body, create_type)
        self.assertEqual(status, "201 Created")
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
            for index in range(21):
                archive.writestr(f"receipt-{index}.pdf", RECEIPT)
        case_id = create_case_id
        case_snapshot = json.loads(_request(self.app, path=f"/cases/{case_id}")[2])
        fields = {"_case_revision": case_snapshot["case_revision"], "_chunk_id": "upload-oversize"}
        batch, batch_type = _multipart([("many.zip", buffer.getvalue())], fields=fields)
        status, _, _ = _request(self.app, "POST", f"/cases/{case_id}/attachments", batch, batch_type)
        self.assertEqual(status, "400 Bad Request")
        self.assertEqual(self.store.get_case(case_id)["attachments"], [])

    def test_one_hundred_attachments_are_accepted_in_five_http_chunks(self):
        case_id = "case-" + "d" * 36
        body, content_type = _multipart([("nota.pdf", NOTE)], fields={"_case_id": case_id})
        status, _, _ = _request(self.app, "POST", "/cases", body, content_type)
        self.assertEqual(status, "201 Created")

        for batch_index in range(5):
            current = json.loads(_request(self.app, path=f"/cases/{case_id}")[2])
            files = [
                (f"receipt-{batch_index}-{offset}.pdf", RECEIPT + f"{batch_index}-{offset}".encode())
                for offset in range(20)
            ]
            body, content_type = _multipart(
                files,
                fields={
                    "_case_revision": current["case_revision"],
                    "_chunk_id": f"upload-{batch_index}",
                },
            )
            status, _, result = _request(self.app, "POST", f"/cases/{case_id}/attachments", body, content_type)
            self.assertEqual(status, "200 OK")
            self.assertNotIn(b"receipt-", result)

        final = json.loads(_request(self.app, path=f"/cases/{case_id}")[2])
        self.assertEqual(final["attachment_count"], 100)
        self.assertEqual(final["accepted_chunk_count"], 5)

        body, content_type = _multipart(
            [("receipt-101.pdf", RECEIPT + b"101")],
            fields={"_case_revision": final["case_revision"], "_chunk_id": "upload-101"},
        )
        status, _, _ = _request(self.app, "POST", f"/cases/{case_id}/attachments", body, content_type)
        self.assertEqual(status, "400 Bad Request")
        self.assertEqual(json.loads(_request(self.app, path=f"/cases/{case_id}")[2])["attachment_count"], 100)
