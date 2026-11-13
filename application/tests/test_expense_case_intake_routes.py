"""Synthetic WSGI coverage for persistent expense-case intake routes."""
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from urllib.parse import urlencode

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

    def _create_case(self, case_id="case-" + "f" * 36):
        body, content_type = _multipart(
            [("private-statement.pdf", NOTE)], fields={"_case_id": case_id},
        )
        status, _, _ = _request(self.app, "POST", "/cases", body, content_type)
        self.assertEqual(status, "201 Created")
        return case_id

    def _add_receipt(self, case_id):
        case = self.store.get_case(case_id)
        body, content_type = _multipart(
            [("private-receipt.pdf", RECEIPT)],
            fields={"_case_revision": case["case_revision"], "_chunk_id": "delete-test-chunk"},
        )
        status, _, _ = _request(
            self.app, "POST", f"/cases/{case_id}/attachments", body, content_type,
        )
        self.assertEqual(status, "200 OK")
        return self.store.get_case(case_id)

    def _delete_case(self, case_id, revision, confirmation):
        body = urlencode({
            "_case_revision": revision, "_confirmation": confirmation,
        }).encode("ascii")
        return _request(
            self.app, "POST", f"/cases/{case_id}/delete", body,
            "application/x-www-form-urlencoded",
        )

    def test_delete_case_confirmation_is_side_effect_free_and_hides_document_details(self):
        case_id = self._create_case()
        case = self._add_receipt(case_id)

        status, headers, page = _request(self.app, path=f"/cases/{case_id}/delete")

        self.assertEqual(status, "200 OK")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn(case_id.encode(), page)
        self.assertIn(b"2 documenti", page)
        self.assertIn(b"_case_revision", page)
        self.assertIn(b"_confirmation", page)
        self.assertIn(b"_ocr2_csrf", page)
        self.assertIn(b"Eliminazione permanente", page)
        self.assertNotIn(b"private-statement.pdf", page)
        self.assertNotIn(b"private-receipt.pdf", page)
        self.assertEqual(self.store.get_case(case_id)["case_revision"], case["case_revision"])

    def test_delete_case_requires_exact_typed_confirmation(self):
        case_id = self._create_case()
        case = self.store.get_case(case_id)

        status, _, _ = self._delete_case(case_id, case["case_revision"], "another-case")

        self.assertEqual(status, "400 Bad Request")
        self.assertIsNotNone(self.store.get_case(case_id))

    def test_delete_case_rejects_stale_revision(self):
        case_id = self._create_case()
        stale_revision = self.store.get_case(case_id)["case_revision"]
        current = self._add_receipt(case_id)

        status, _, _ = self._delete_case(case_id, stale_revision, case_id)

        self.assertEqual(status, "409 Conflict")
        self.assertEqual(self.store.get_case(case_id)["case_revision"], current["case_revision"])

    def test_delete_case_rechecks_revision_atomically_after_confirmation_lookup(self):
        case_id = self._create_case()
        case = self.store.get_case(case_id)
        original_delete = self.store.delete_case

        def concurrent_update_then_delete(requested_case_id, **kwargs):
            latest = self.store.get_case(requested_case_id)
            latest["processing"]["state"] = "stale"
            self.store.save_case(latest, expected_revision=latest["case_revision"])
            return original_delete(requested_case_id, **kwargs)

        self.store.delete_case = concurrent_update_then_delete
        status, _, _ = self._delete_case(case_id, case["case_revision"], case_id)

        self.assertEqual(status, "409 Conflict")
        self.assertEqual(self.store.get_case(case_id)["processing"]["state"], "stale")

    def test_delete_case_rejects_queued_or_processing_cases(self):
        for state, suffix in (("queued", "a"), ("processing", "b")):
            with self.subTest(state=state):
                case_id = self._create_case("case-" + suffix * 36)
                case = self.store.get_case(case_id)
                case["processing"]["state"] = state
                case = self.store.save_case(case, expected_revision=case["case_revision"])

                status, _, _ = self._delete_case(case_id, case["case_revision"], case_id)

                self.assertEqual(status, "409 Conflict")
                self.assertEqual(self.store.get_case(case_id)["processing"]["state"], state)

    def test_delete_case_rejects_wrong_origin_before_consuming_request(self):
        case_id = self._create_case()
        case = self.store.get_case(case_id)
        body = urlencode({
            "_case_revision": case["case_revision"], "_confirmation": case_id,
        }).encode("ascii")

        class TrackedInput(io.BytesIO):
            def read(self, size=-1):
                self.was_read = True
                return super().read(size)

        consumed = TrackedInput(body)
        response = {}

        def start_response(status, headers):
            response["status"] = status

        environ = {
            "REQUEST_METHOD": "POST", "PATH_INFO": f"/cases/{case_id}/delete",
            "HTTP_HOST": "127.0.0.1:8080", "HTTP_ORIGIN": "https://evil.example",
            "CONTENT_LENGTH": str(len(body)), "CONTENT_TYPE": "application/x-www-form-urlencoded",
            "wsgi.input": consumed,
        }

        b"".join(self.app(environ, start_response))

        self.assertEqual(response["status"], "403 Forbidden")
        self.assertFalse(getattr(consumed, "was_read", False))
        self.assertIsNotNone(self.store.get_case(case_id))

    def test_delete_case_missing_id_is_not_found_without_disclosing_case_data(self):
        status, headers, page = _request(self.app, path=f"/cases/{'case-' + '9' * 36}/delete")

        self.assertEqual(status, "404 Not Found")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn(b"Fascicolo non trovato", page)
        self.assertNotIn(b"private-statement", page)

    def test_delete_case_removes_case_and_unshared_documents(self):
        case_id = self._create_case()
        case = self._add_receipt(case_id)
        document_ids = [case["statement_document_id"]] + [
            item["document_id"] for item in case["attachments"]
        ]

        status, _, page = self._delete_case(case_id, case["case_revision"], case_id)

        self.assertEqual(status, "200 OK")
        self.assertIn(b"Fascicolo eliminato", page)
        self.assertIsNone(self.store.get_case(case_id))
        for document_id in document_ids:
            self.assertIsNone(self.store.get(document_id))

    def test_delete_case_preserves_independently_retained_statement(self):
        case_id = self._create_case()
        case = self.store.get_case(case_id)
        statement = self.store.get(case["statement_document_id"])
        self.store.save(statement.record, statement.source_bytes)

        status, _, _ = self._delete_case(case_id, case["case_revision"], case_id)

        self.assertEqual(status, "200 OK")
        self.assertIsNone(self.store.get_case(case_id))
        retained = self.store.get(statement.record["document_id"])
        self.assertIsNotNone(retained)
        self.assertEqual(retained.source_bytes, NOTE)

    def test_delete_case_preserves_attachment_shared_with_another_case(self):
        first_case_id = self._create_case("case-" + "c" * 36)
        first_case = self._add_receipt(first_case_id)
        shared_document_id = first_case["attachments"][0]["document_id"]
        shared_document = self.store.get(shared_document_id)
        second_case_id = self._create_case("case-" + "d" * 36)
        second_case = self.store.get_case(second_case_id)
        shared_source = [{
            "record": shared_document.record,
            "source_bytes": shared_document.source_bytes,
        }]
        self.store.append_case_chunk(
            second_case_id, second_case["case_revision"], "shared-source",
            self.store.case_chunk_digest(shared_source), shared_source,
        )

        status, _, _ = self._delete_case(
            first_case_id, first_case["case_revision"], first_case_id,
        )

        self.assertEqual(status, "200 OK")
        self.assertIsNone(self.store.get_case(first_case_id))
        surviving_case = self.store.get_case(second_case_id)
        self.assertIn(shared_document_id, {
            item["document_id"] for item in surviving_case["attachments"]
        })
        retained = self.store.get(shared_document_id)
        self.assertIsNotNone(retained)
        self.assertEqual(retained.source_bytes, RECEIPT)

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
