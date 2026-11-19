"""Library page: filters, pages, rename, tags, backup download and restore upload (REQ-081, 083, 084, 086, 088)."""
from __future__ import annotations

import io
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
import zipfile

from alfa_document_intelligence.local_document_store import LocalDocumentStore
from alfa_document_intelligence.local_intake_app import create_expense_report_app

from test_document_library import _record
from test_local_document_archive_ui import _request
from test_local_document_store import SyntheticProtector
from test_archive_backup import OtherProtector

_ACTOR = patch("alfa_document_intelligence.local_intake_app._windows_review_actor", return_value="synthetic-user")


def _form(**values):
    return urlencode(values).encode("ascii"), "application/x-www-form-urlencoded"


def _multipart(zip_bytes: bytes, confirm: bool = True, boundary: str = "library-test"):
    parts = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; filename=\"backup.zip\"\r\n"
        "Content-Type: application/zip\r\n\r\n".encode("ascii") + zip_bytes + b"\r\n",
    ]
    if confirm:
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"confirm\"\r\n\r\nyes\r\n".encode("ascii"))
    return b"".join(parts) + f"--{boundary}--\r\n".encode("ascii"), f"multipart/form-data; boundary={boundary}"


class LibraryPageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = LocalDocumentStore(self.root / "archive.sqlite3", protector=SyntheticProtector())
        for index in range(1, 31):
            family = "invoice" if index % 2 else "fiscal_receipt"
            record, source = _record(index, family=family, status="completed" if index % 5 == 0 else "not_started")
            self.store.save(record, source)
        self.app = create_expense_report_app(archive_store=self.store)
        self.addCleanup(self.app.close)
        _ACTOR.start()
        self.addCleanup(_ACTOR.stop)

    def page(self, query=""):
        status, _, body = _request(self.app, path="/archive", query=query)
        return status, body.decode("utf-8")

    def test_pages_of_25_with_previous_and_next(self):
        status, first = self.page()
        self.assertEqual(status, "200 OK")
        self.assertIn("Documenti 1–25 di 30", first)
        self.assertIn('href="/archive?page=1">Pagina successiva', first)
        self.assertNotIn("Pagina precedente", first)
        _, beyond = self.page("page=999999")
        self.assertIn("Documenti 26–30 di 30 · pagina 2 di 2", beyond, "a page past the end shows the last one")
        _, second = self.page("page=1")
        self.assertIn("Documenti 26–30 di 30", second)
        self.assertIn("Pagina precedente", second)
        self.assertNotIn("Pagina successiva", second)

    def test_filters_combine_and_survive_paging(self):
        _, body = self.page(urlencode({"family": "fiscal_receipt", "status": "completed"}))
        self.assertIn("Documenti 1–3 di 3", body)
        self.assertIn('<option value="fiscal_receipt" selected>', body)
        _, body = self.page(urlencode({"family": "invoice"}))
        self.assertIn("di 15", body)
        for bad in ("family=evil", "status=x", "from=ieri", "page=-1", "unknown=1", "q=a&q=b"):
            with self.subTest(bad=bad):
                self.assertEqual(self.page(bad)[0], "400 Bad Request")

    def test_rename_and_tags_show_up_and_filter(self):
        body, content_type = _form(display_name="Cena cliente Rossi", back="/archive?family=invoice")
        status, _, page = _request(self.app, "POST", "/archive/rename/doc-003", body, content_type)
        self.assertEqual(status, "200 OK")
        self.assertIn("Nome aggiornato.", page.decode("utf-8"))
        self.assertIn('<option value="invoice" selected>', page.decode("utf-8"), "the filters are kept")
        body, content_type = _form(tags="Trasferta Milano, cene", back="/archive")
        self.assertEqual(_request(self.app, "POST", "/archive/tags/doc-003", body, content_type)[0], "200 OK")
        _, listing = self.page(urlencode({"tag": "trasferta milano"}))
        self.assertIn("Documenti 1–1 di 1", listing)
        self.assertIn("Cena cliente Rossi", listing)
        self.assertIn("Etichette: Trasferta Milano, cene", listing)
        self.assertEqual(self.store.library_events("doc-003")[0]["actor"], "synthetic-user")

    def test_library_writes_need_a_same_origin_post_and_valid_values(self):
        body, content_type = _form(display_name="X", back="/archive")
        self.assertEqual(_request(self.app, "POST", "/archive/rename/doc-001", body, content_type,
                                  origin="http://evil.example")[0], "403 Forbidden")
        body, content_type = _form(display_name="", back="/archive")
        self.assertEqual(_request(self.app, "POST", "/archive/rename/doc-001", body, content_type)[0], "400 Bad Request")
        body, content_type = _form(display_name="X", back="/archive")
        self.assertEqual(_request(self.app, "POST", "/archive/rename/doc-999", body, content_type)[0], "400 Bad Request")
        self.assertIsNone(self.store.search_library("doc-001")[0][0].display_name)

    def test_export_links_come_from_the_registry(self):
        _, body = self.page()
        self.assertIn('href="/archive/export/doc-001.json">Esporta JSON', body)
        self.assertIn('href="/archive/export/doc-001.csv">Esporta CSV', body)
        self.assertNotIn(".txt", body, "hidden formats are not offered")
        self.assertEqual(_request(self.app, path="/archive/export/doc-001.txt")[0], "404 Not Found")

    def test_backup_download_and_restore_upload(self):
        status, headers, data = _request(self.app, path="/archive/backup")
        self.assertEqual(status, "200 OK")
        self.assertEqual(headers["Content-Type"], "application/zip")
        self.assertRegex(headers["Content-Disposition"], r'attachment; filename="ocr2-backup-\d{8}-\d{6}\.zip"')
        self.assertEqual(sorted(zipfile.ZipFile(io.BytesIO(data)).namelist()), ["archive.sqlite3", "manifest.json"])
        self.store.delete("doc-001")
        body, content_type = _multipart(data)
        status, _, page = _request(self.app, "POST", "/archive/restore", body, content_type)
        self.assertEqual(status, "200 OK", page[:300])
        self.assertIn("Backup ripristinato: 30 documenti", page.decode("utf-8"))
        self.assertIsNotNone(self.store.get("doc-001"))

    def test_restore_refuses_bad_files_without_touching_the_archive(self):
        _, _, good = _request(self.app, path="/archive/backup")
        foreign = LocalDocumentStore(self.root / "other.sqlite3", protector=OtherProtector())
        record, source = _record(99)
        foreign.save(record, source)
        foreign_app = create_expense_report_app(archive_store=foreign)
        self.addCleanup(foreign_app.close)
        _, _, foreign_zip = _request(foreign_app, path="/archive/backup")
        tampered = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(good)) as source_zip, zipfile.ZipFile(tampered, "w") as target:
            target.writestr("manifest.json", source_zip.read("manifest.json"))
            target.writestr("archive.sqlite3", source_zip.read("archive.sqlite3")[:-200])
        extra = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(good)) as source_zip, zipfile.ZipFile(extra, "w") as target:
            for name in source_zip.namelist():
                target.writestr(name, source_zip.read(name))
            target.writestr("../evil.txt", b"x")
        self.store.delete("doc-002")
        cases = {
            "not a zip": _multipart(b"PK not really"),
            "truncated copy": _multipart(tampered.getvalue()),
            "unexpected member": _multipart(extra.getvalue()),
            "another Windows user": _multipart(foreign_zip),
        }
        for label, (body, content_type) in cases.items():
            with self.subTest(label):
                status, _, page = _request(self.app, "POST", "/archive/restore", body, content_type)
                self.assertEqual(status, "400 Bad Request")
                self.assertIn("non è stato toccato", page.decode("utf-8"))
                self.assertIsNone(self.store.get("doc-002"))
        body, content_type = _multipart(good, confirm=False)
        self.assertEqual(_request(self.app, "POST", "/archive/restore", body, content_type)[0], "400 Bad Request")
        body, content_type = _multipart(good)
        self.assertEqual(_request(self.app, "POST", "/archive/restore", body, content_type,
                                  origin="http://evil.example")[0], "403 Forbidden")
        self.assertIsNone(self.store.get("doc-002"))
        self.assertFalse(list(self.root.glob(".restore-*")), "no staging copy is left behind")

    def test_restore_waits_for_a_running_case_job(self):
        class _BusyCaseManager:
            def has_active_job(self):
                return True

            def set_custom_family_catalog(self, catalog):
                pass

            def close(self):
                pass

        _, _, good = _request(self.app, path="/archive/backup")
        busy_app = create_expense_report_app(archive_store=self.store, expense_case_processing_manager=_BusyCaseManager())
        self.addCleanup(busy_app.close)
        body, content_type = _multipart(good)
        self.assertEqual(_request(busy_app, "POST", "/archive/restore", body, content_type)[0], "409 Conflict")

    def test_cases_can_be_renamed_from_the_cases_page(self):
        from test_expense_case_store import _case, _source_record

        source = b"%PDF synthetic statement for the cases page"
        statement = _source_record("statement-page", source)
        case = self.store.create_case(_case(statement), statement, source)
        body, content_type = _form(label="Trasferta Roma")
        status, headers, _ = _request(self.app, "POST", f"/cases/{case['case_id']}/label", body, content_type)
        self.assertEqual(status, "303 See Other")
        self.assertEqual(headers["Location"], "/cases?notice=renamed")
        self.assertEqual(headers["Cache-Control"], "no-store")
        status, _, page = _request(self.app, path="/cases", query="notice=renamed")
        self.assertEqual(status, "200 OK")
        self.assertIn("Nome aggiornato.", page.decode("utf-8"))
        self.assertIn("Trasferta Roma", page.decode("utf-8"))
        status, _, page = _request(self.app, path="/cases")
        self.assertIn(f'href="/cases/{case["case_id"]}/intake">Trasferta Roma</a>', page.decode("utf-8"))
        self.assertEqual(_request(self.app, "POST", f"/cases/{case['case_id']}/label", body, content_type,
                                  origin="http://evil.example")[0], "403 Forbidden")
        self.assertEqual(_request(self.app, "POST", "/cases/case-unknown/label", body, content_type)[0], "400 Bad Request")

    def test_page_has_no_raw_unescaped_names(self):
        body, content_type = _form(display_name='<script>alert(1)</script>', back="/archive")
        _, _, page = _request(self.app, "POST", "/archive/rename/doc-001", body, content_type)
        self.assertNotIn("<script>alert", page.decode("utf-8"))
        self.assertTrue(re.search(r"&lt;script&gt;", page.decode("utf-8")))


if __name__ == "__main__":
    unittest.main()
