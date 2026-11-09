import copy
import hashlib
import hmac
import io
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode

from alfa_document_intelligence.local_document_store import LocalDocumentStore
from alfa_document_intelligence.local_intake_app import create_expense_report_app
from alfa_document_intelligence.archive_restore import RestoreStatus


class _SyntheticProtector:
    """Authenticated test-only transform; it is not production encryption."""

    _key = b"synthetic-archive-ui-test-key"

    def protect(self, plaintext: bytes) -> bytes:
        ciphertext = bytes(value ^ 0xA5 for value in plaintext)
        tag = hmac.new(self._key, ciphertext, hashlib.sha256).digest()
        return b"TESTP1" + tag + ciphertext

    def unprotect(self, protected: bytes) -> bytes:
        if not protected.startswith(b"TESTP1") or len(protected) < 38:
            raise ValueError("invalid test ciphertext")
        tag, ciphertext = protected[6:38], protected[38:]
        expected = hmac.new(self._key, ciphertext, hashlib.sha256).digest()
        if not hmac.compare_digest(tag, expected):
            raise ValueError("tampered test ciphertext")
        return bytes(value ^ 0xA5 for value in ciphertext)


class _FakeRestoreManager:
    job_id = "synthetic-restore-job-0123456789"

    def __init__(self):
        self.status = RestoreStatus(self.job_id, "queued", 0, 0)
        self.started = []
        self.cancelled = []

    def start(self, source, destination):
        self.started.append((source, destination))
        return self.job_id

    def snapshot(self, job_id):
        return self.status if job_id == self.job_id else None

    def cancel(self, job_id):
        self.cancelled.append(job_id)
        if job_id != self.job_id:
            return False
        self.status = RestoreStatus(job_id, "cancelling", 4, 8)
        return True


def _multipart_pdf(filename: str, payload: bytes, boundary: str = "archive-test"):
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="files"; filename="{filename}"\r\n'
        "Content-Type: application/pdf\r\n\r\n"
    ).encode("ascii") + payload + f"\r\n--{boundary}--\r\n".encode("ascii")
    return body, f"multipart/form-data; boundary={boundary}"


def _request(app, method="GET", path="/", body=b"", content_type="", *, query="", origin="http://127.0.0.1:8000"):
    response = {}

    def start_response(status, headers):
        response["status"] = status
        response["headers"] = dict(headers)

    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": str(len(body)) if body else "",
        "CONTENT_TYPE": content_type,
        "HTTP_HOST": "127.0.0.1:8000",
        "SERVER_NAME": "127.0.0.1",
        "SERVER_PORT": "8000",
        "wsgi.url_scheme": "http",
        "wsgi.input": io.BytesIO(body),
    }
    if origin is not None:
        environ["HTTP_ORIGIN"] = origin
    result = b"".join(app(environ, start_response))
    return response["status"], response["headers"], result


class LocalDocumentArchiveUiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = b"%PDF-1.4\nsynthetic archive UI receipt\n%%EOF"
        self.store = LocalDocumentStore(
            Path(self.temp.name) / "archive.sqlite3",
            protector=_SyntheticProtector(),
        )
        self.app = create_expense_report_app(archive_store=self.store)

    def _start_expense_report_session(self, payload=None, filename="synthetic-note.pdf"):
        body, content_type = _multipart_pdf(filename, payload or self.source)
        status, _, page = _request(self.app, "POST", "/upload", body, content_type)
        self.assertEqual(status, "200 OK")
        assignment = urlencode({"note_document_id": "doc-001"}).encode("ascii")
        status, _, bundle = _request(
            self.app, "POST", "/assign-note", assignment,
            "application/x-www-form-urlencoded",
        )
        self.assertEqual(status, "200 OK")
        self.assertIn(b"doc-001", bundle)

    def _save_current_document(self, document_id="doc-001", *, origin="http://127.0.0.1:8000"):
        return _request(
            self.app, "POST", f"/archive/save/{document_id}",
            b"", "application/x-www-form-urlencoded", origin=origin,
        )

    def test_explicit_save_creates_archive_entry_with_unique_persistent_id(self):
        self._start_expense_report_session()
        status, _, _ = _request(self.app, path="/reviews/doc-001")
        self.assertEqual(status, "200 OK")

        status, _, result = self._save_current_document()
        self.assertEqual(status, "200 OK")
        self.assertIn(b"Documento salvato", result)
        matches = self.store.search("synthetic-note.pdf")
        self.assertEqual(len(matches), 1)
        self.assertNotEqual(matches[0].document_id, "doc-001")
        reopened = self.store.get(matches[0].document_id)
        self.assertEqual(reopened.source_bytes, self.source)
        self.assertEqual(reopened.record["source"]["sha256"], hashlib.sha256(self.source).hexdigest())

    def test_archive_restore_form_starts_a_private_async_job_and_hides_paths_until_success(self):
        manager = _FakeRestoreManager()
        app = create_expense_report_app(
            archive_store=self.store, archive_restore_manager=manager
        )
        status, _, archive = _request(app, path="/archive")
        self.assertEqual(status, "200 OK")
        self.assertIn(b"/archive/restore", archive)

        status, _, form = _request(app, path="/archive/restore")
        self.assertEqual(status, "200 OK")
        self.assertIn(b"backup.sqlite3", form)

        source = str(Path(self.temp.name) / "private-backup.sqlite3")
        destination = str(Path(self.temp.name) / "private-restored.sqlite3")
        status, _, started = _request(
            app, "POST", "/archive/restore",
            urlencode({"source": source, "destination": destination}).encode("ascii"),
            "application/x-www-form-urlencoded",
        )
        self.assertEqual(status, "202 Accepted")
        self.assertEqual(manager.started, [(source, destination)])
        self.assertNotIn(source.encode(), started)
        self.assertNotIn(destination.encode(), started)
        self.assertIn(manager.job_id.encode(), started)

        status, _, progress = _request(app, path=f"/archive/restore/{manager.job_id}")
        self.assertEqual(status, "200 OK")
        self.assertIn(b"In coda", progress)
        self.assertNotIn(source.encode(), progress)
        self.assertNotIn(destination.encode(), progress)

        manager.status = RestoreStatus(manager.job_id, "succeeded", 0, 8, destination)
        status, _, complete = _request(app, path=f"/archive/restore/{manager.job_id}")
        self.assertEqual(status, "200 OK")
        self.assertIn(destination.encode(), complete)

    def test_archive_restore_cancel_requires_same_origin_and_keeps_paths_private(self):
        manager = _FakeRestoreManager()
        app = create_expense_report_app(
            archive_store=self.store, archive_restore_manager=manager
        )
        status, _, _ = _request(
            app, "POST", f"/archive/restore/{manager.job_id}/cancel",
            b"", "application/x-www-form-urlencoded", origin="http://evil.example",
        )
        self.assertEqual(status, "403 Forbidden")
        self.assertEqual(manager.cancelled, [])

        status, _, cancelled = _request(
            app, "POST", f"/archive/restore/{manager.job_id}/cancel",
            b"", "application/x-www-form-urlencoded",
        )
        self.assertEqual(status, "200 OK")
        self.assertEqual(manager.cancelled, [manager.job_id])
        self.assertIn(b"Annullamento in corso", cancelled)
        self.assertNotIn(b"private", cancelled)

    def test_archive_list_open_and_json_csv_exports_keep_evidence(self):
        self._start_expense_report_session()
        _request(self.app, path="/reviews/doc-001")
        self._save_current_document()
        document_id = self.store.search("synthetic-note.pdf")[0].document_id

        status, _, archive = _request(self.app, path="/archive", query="q=synthetic-note")
        self.assertEqual(status, "200 OK")
        self.assertIn(b"synthetic-note.pdf", archive)
        self.assertIn(b"Apri", archive)

        status, _, opened = _request(
            self.app, "POST", f"/archive/open/{document_id}",
            b"", "application/x-www-form-urlencoded", origin="http://127.0.0.1:8000",
        )
        self.assertEqual(status, "200 OK")
        self.assertIn(b"Apri revisione", opened)

        status, headers, json_export = _request(
            self.app, path=f"/archive/export/{document_id}.json"
        )
        self.assertEqual(status, "200 OK")
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        record = json.loads(json_export)
        self.assertEqual(record["document_id"], document_id)
        self.assertEqual(record["source"]["sha256"], hashlib.sha256(self.source).hexdigest())
        self.assertIn("evidence", record["fiscal_document_state"])

        status, headers, csv_export = _request(
            self.app, path=f"/archive/export/{document_id}.csv"
        )
        self.assertEqual(status, "200 OK")
        self.assertEqual(headers["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn(b"ocr2-document-csv-v1", csv_export)

    def test_archive_only_open_and_return_does_not_create_a_fake_expense_bundle(self):
        self._start_expense_report_session()
        current_record = self.app_state_record_for_seed()
        current_record["document_id"] = "archive-seed"
        current_record["source"]["storage_ref"] = "local-archive://archive-seed"
        self.store.save(current_record, self.source)
        _request(self.app, "POST", "/clear", b"", "application/x-www-form-urlencoded")

        status, _, opened = _request(
            self.app, "POST", "/archive/open/archive-seed",
            b"", "application/x-www-form-urlencoded", origin="http://127.0.0.1:8000",
        )
        self.assertEqual(status, "200 OK")
        self.assertIn(b"synthetic-note.pdf", opened)
        status, _, _ = _request(
            self.app, "POST", "/archive/delete/archive-seed",
            b"", "application/x-www-form-urlencoded", origin="http://127.0.0.1:8000",
        )
        self.assertEqual(status, "200 OK")
        status, _, refreshed = _request(self.app, path="/")
        self.assertEqual(status, "200 OK")
        self.assertIn(b"Carica nota spese e giustificativi", refreshed)
        status, _, returned = _request(
            self.app, "POST", "/archive/return",
            b"", "application/x-www-form-urlencoded", origin="http://127.0.0.1:8000",
        )
        self.assertEqual(status, "200 OK")
        self.assertIn(b"Carica nota spese e giustificativi", returned)
        self.assertNotIn(b"Riferimento benchmark", returned)

    def app_state_record_for_seed(self):
        status, _, _ = _request(self.app, path="/reviews/doc-001")
        self.assertEqual(status, "200 OK")
        status, _, _ = self._save_current_document()
        self.assertEqual(status, "200 OK")
        archived = self.store.search("synthetic-note.pdf")[0]
        return self.store.get(archived.document_id).record

    def test_delete_requires_confirmation_and_same_origin_post(self):
        self._start_expense_report_session()
        _request(self.app, path="/reviews/doc-001")
        self._save_current_document()
        document_id = self.store.search("synthetic-note.pdf")[0].document_id

        status, _, confirmation = _request(self.app, path=f"/archive/delete/{document_id}")
        self.assertEqual(status, "200 OK")
        self.assertIn(b"Elimina definitivamente", confirmation)
        self.assertIsNotNone(self.store.get(document_id))

        status, _, _ = _request(
            self.app, "POST", f"/archive/delete/{document_id}",
            b"", "application/x-www-form-urlencoded", origin="https://evil.example",
        )
        self.assertEqual(status, "403 Forbidden")
        self.assertIsNotNone(self.store.get(document_id))

        status, _, deleted = _request(
            self.app, "POST", f"/archive/delete/{document_id}",
            b"", "application/x-www-form-urlencoded", origin="http://127.0.0.1:8000",
        )
        self.assertEqual(status, "200 OK")
        self.assertIn(b"Documento eliminato", deleted)
        self.assertIsNone(self.store.get(document_id))

    def test_deleted_archive_alias_can_be_saved_again_from_the_current_session(self):
        self._start_expense_report_session()
        _request(self.app, path="/reviews/doc-001")
        self._save_current_document()
        old_id = self.store.search("synthetic-note.pdf")[0].document_id
        _request(
            self.app, "POST", f"/archive/open/{old_id}",
            b"", "application/x-www-form-urlencoded", origin="http://127.0.0.1:8000",
        )
        _request(
            self.app, "POST", f"/archive/delete/{old_id}",
            b"", "application/x-www-form-urlencoded", origin="http://127.0.0.1:8000",
        )
        status, _, returned = _request(
            self.app, "POST", "/archive/return",
            b"", "application/x-www-form-urlencoded", origin="http://127.0.0.1:8000",
        )
        self.assertEqual(status, "200 OK")
        self.assertIn(b"doc-001", returned)
        status, _, saved = self._save_current_document()
        self.assertEqual(status, "200 OK")
        self.assertIn(b"Documento salvato", saved)
        new_id = self.store.search("synthetic-note.pdf")[0].document_id
        self.assertNotEqual(old_id, new_id)
        self.assertEqual(self.store.get(new_id).source_bytes, self.source)

    def test_cross_origin_save_is_rejected_without_creating_an_archive_record(self):
        self._start_expense_report_session()
        status, _, _ = self._save_current_document(origin="http://attacker.example")
        self.assertEqual(status, "403 Forbidden")
        status, _, _ = self._save_current_document(origin=None)
        self.assertEqual(status, "403 Forbidden")
        self.assertEqual(self.store.search(""), [])

    def test_separate_uploads_with_the_same_temporary_id_get_distinct_archive_ids(self):
        self._start_expense_report_session(self.source, "first.pdf")
        _request(self.app, path="/reviews/doc-001")
        self._save_current_document()

        second_source = b"%PDF-1.4\nsecond synthetic document\n%%EOF"
        self._start_expense_report_session(second_source, "second.pdf")
        _request(self.app, path="/reviews/doc-001")
        status, _, _ = self._save_current_document()
        self.assertEqual(status, "200 OK")
        first = self.store.search("first.pdf")[0]
        second = self.store.search("second.pdf")[0]
        self.assertNotEqual(first.document_id, second.document_id)
        self.assertEqual(self.store.get(first.document_id).source_bytes, self.source)
        self.assertEqual(self.store.get(second.document_id).source_bytes, second_source)

    def test_opened_archive_updates_require_explicit_save_and_detect_stale_record(self):
        self._start_expense_report_session()
        _request(self.app, path="/reviews/doc-001")
        self._save_current_document()
        document_id = self.store.search("synthetic-note.pdf")[0].document_id

        status, _, _ = _request(
            self.app, "POST", f"/archive/open/{document_id}",
            b"", "application/x-www-form-urlencoded", origin="http://127.0.0.1:8000",
        )
        self.assertEqual(status, "200 OK")
        before = self.store.get(document_id).record
        status, _, review = _request(
            self.app, "POST", f"/reviews/{document_id}/open",
            b"", "application/x-www-form-urlencoded", origin="http://127.0.0.1:8000",
        )
        self.assertEqual(status, "200 OK")
        self.assertIn(b"Salva modifiche in archivio", review)
        self.assertEqual(self.store.get(document_id).record, before)

        status, _, saved = _request(
            self.app, "POST", f"/archive/save/{document_id}",
            b"", "application/x-www-form-urlencoded", origin="http://127.0.0.1:8000",
        )
        self.assertEqual(status, "200 OK")
        self.assertIn(b"Documento aggiornato", saved)
        self.assertEqual(self.store.get(document_id).record["review"]["status"], "in_progress")

        _request(
            self.app, "POST", f"/archive/open/{document_id}",
            b"", "application/x-www-form-urlencoded", origin="http://127.0.0.1:8000",
        )
        status, _, reopened_review = _request(
            self.app, "POST", f"/reviews/{document_id}/open",
            b"", "application/x-www-form-urlencoded", origin="http://127.0.0.1:8000",
        )
        self.assertEqual(status, "200 OK")
        self.assertIn(b"Salva modifiche in archivio", reopened_review)

        concurrently_changed = self.store.get(document_id).record
        concurrently_changed["source"]["original_filename"] = "changed-elsewhere.pdf"
        self.store.save(concurrently_changed, self.source)
        status, _, conflict = _request(
            self.app, "POST", f"/archive/save/{document_id}",
            b"", "application/x-www-form-urlencoded", origin="http://127.0.0.1:8000",
        )
        self.assertEqual(status, "409 Conflict")
        self.assertIn(b"cambiato nell", conflict)
        self.assertEqual(self.store.get(document_id).record["source"]["original_filename"], "changed-elsewhere.pdf")


if __name__ == "__main__":
    unittest.main()
