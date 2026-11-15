"""Catalog editor: create, import, export and keep versions of document types (REQ-045, REQ-042)."""
from __future__ import annotations

import io
import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlencode

from alfa_document_intelligence.catalog_editor import CatalogFormError, family_from_form
from alfa_document_intelligence.document_family_catalog import DocumentFamilyCatalogStore, load_custom_family_catalog
from alfa_document_intelligence.local_intake_app import create_expense_report_app
from alfa_document_intelligence.ocr_adapter import OCRPageResult, OCRToken
from alfa_document_intelligence.semantic_proposals import propose_common_fields

_HOST = "127.0.0.1:8080"


def _request(app, method="GET", path="/", body=b"", content_type="", origin="http://127.0.0.1:8080"):
    response = {}

    def start_response(status, headers):
        response["status"] = status
        response["headers"] = dict(headers)

    environ = {
        "REQUEST_METHOD": method, "PATH_INFO": path, "HTTP_HOST": _HOST, "HTTP_ORIGIN": origin,
        "CONTENT_LENGTH": str(len(body)) if body else "", "CONTENT_TYPE": content_type,
        "wsgi.input": io.BytesIO(body),
    }
    payload = b"".join(app(environ, start_response))
    return response["status"], response["headers"], payload


def _form(**values) -> tuple[bytes, str]:
    return urlencode(values).encode("utf-8"), "application/x-www-form-urlencoded"


def _upload(name: str, data: bytes) -> tuple[bytes, str]:
    boundary = "catalog-boundary"
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; filename=\"{name}\"\r\n"
        "Content-Type: application/json\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


TAXI_FORM = {
    "label": "Ricevuta taxi",
    "title_cues": "RICEVUTA TAXI, TAXI RECEIPT",
    "fields": "Città di partenza: Partenza, Da [testo]\nImporto corsa: Corsa [importo] [obbligatorio]",
}


class FamilyFormTests(unittest.TestCase):
    def test_form_becomes_a_valid_family(self):
        family = family_from_form(**TAXI_FORM)
        self.assertEqual(family["id"], "custom_ricevuta_taxi")
        self.assertEqual(family["title_cues"], ["RICEVUTA TAXI", "TAXI RECEIPT"])
        self.assertEqual(family["fields"][0], {"id": "citta_di_partenza", "label": "Città di partenza", "aliases": ["Partenza", "Da"]})
        self.assertEqual(family["fields"][1], {
            "id": "importo_corsa", "label": "Importo corsa", "aliases": ["Corsa"], "type": "amount", "required": True,
        })
        load_custom_family_catalog(json.dumps({"catalog_version": "2", "families": [family]}))

    def test_bad_form_lines_are_explained(self):
        with self.assertRaisesRegex(CatalogFormError, "riga 1"):
            family_from_form(label="Taxi", title_cues="TAXI", fields="senza due punti")
        with self.assertRaisesRegex(CatalogFormError, "parola chiave"):
            family_from_form(label="Taxi", title_cues=" , ", fields="")


class CatalogRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "family-catalog.json"
        self.store = DocumentFamilyCatalogStore(self.path)
        self.app = create_expense_report_app(family_catalog_store=self.store)
        self.addCleanup(self.app.close)

    def test_create_a_type_then_see_and_export_it(self):
        status, _, page = _request(self.app, path="/catalog")
        self.assertEqual(status, "200 OK")
        self.assertIn("Aggiungi un tipo".encode(), page)
        body, kind = _form(**TAXI_FORM)
        status, _, page = _request(self.app, "POST", "/catalog/families", body, kind)
        self.assertEqual(status, "200 OK")
        self.assertIn("Ricevuta taxi".encode(), page)
        self.assertEqual([family.id for family in self.store.load().families], ["custom_ricevuta_taxi"])
        status, headers, exported = _request(self.app, path="/catalog/export")
        self.assertEqual(status, "200 OK")
        self.assertIn("attachment", headers.get("Content-Disposition", ""))
        self.assertEqual(json.loads(exported)["families"][0]["id"], "custom_ricevuta_taxi")

    def test_each_change_keeps_the_previous_version(self):
        body, kind = _form(**TAXI_FORM)
        _request(self.app, "POST", "/catalog/families", body, kind)
        second = dict(TAXI_FORM, label="Ricevuta parcheggio", title_cues="TICKET PARCHEGGIO")
        body, kind = _form(**second)
        _request(self.app, "POST", "/catalog/families", body, kind)
        history = sorted((self.path.parent / "catalog-history").glob("*.json"))
        self.assertEqual(len(history), 1)  # the first save had no previous file
        self.assertEqual([item["id"] for item in json.loads(history[0].read_text(encoding="utf-8"))["families"]], ["custom_ricevuta_taxi"])

    def test_duplicate_type_and_invalid_import_leave_the_file_unchanged(self):
        body, kind = _form(**TAXI_FORM)
        _request(self.app, "POST", "/catalog/families", body, kind)
        before = self.path.read_bytes()
        status, _, page = _request(self.app, "POST", "/catalog/families", body, kind)
        self.assertEqual(status, "400 Bad Request")
        self.assertIn("Esiste già".encode(), page)
        body, kind = _upload("catalogo.json", b"{not json")
        status, _, page = _request(self.app, "POST", "/catalog/import", body, kind)
        self.assertEqual(status, "400 Bad Request")
        self.assertEqual(self.path.read_bytes(), before)

    def test_import_replaces_the_catalog(self):
        data = json.dumps({"catalog_version": "2", "families": [family_from_form(**TAXI_FORM)]}).encode()
        body, kind = _upload("catalogo.json", data)
        status, _, _ = _request(self.app, "POST", "/catalog/import", body, kind)
        self.assertEqual(status, "200 OK")
        self.assertEqual(self.store.load().families[0].label, "Ricevuta taxi")

    def test_wrong_origin_is_refused(self):
        body, kind = _form(**TAXI_FORM)
        status, _, _ = _request(self.app, "POST", "/catalog/families", body, kind, origin="http://evil.example")
        self.assertEqual(status, "403 Forbidden")
        self.assertFalse(self.path.exists())


class CatalogRuleTests(unittest.TestCase):
    def test_a_type_defined_only_in_the_catalog_is_proposed(self):
        catalog = load_custom_family_catalog(json.dumps({"catalog_version": "2", "families": [family_from_form(**TAXI_FORM)]}))
        page = OCRPageResult(
            source_sha256="a" * 64, page_number=1, engine_name="synthetic", engine_version="1", language="it+en",
            tokens=(OCRToken("t1", "RICEVUTA TAXI", ((0.1, 0.1), (0.5, 0.1), (0.5, 0.15), (0.1, 0.15)), 0.9),),
        )
        proposals = propose_common_fields([page], custom_family_catalog=catalog)
        candidate = proposals["document_family_candidates"]
        values = {candidate.get("value")} | {item.get("value") for item in candidate.get("alternatives", [])}
        self.assertIn("custom_ricevuta_taxi", values)



class CatalogReachesCaseProcessingTests(unittest.TestCase):
    def test_saved_catalog_is_given_to_case_processing_for_later_jobs(self):
        from alfa_document_intelligence.expense_case_processing import ExpenseCaseProcessingManager

        self.assertTrue(callable(getattr(ExpenseCaseProcessingManager, "set_custom_family_catalog", None)))

        class Manager:
            received = None

            def set_custom_family_catalog(self, catalog):
                self.received = catalog

            def close(self):
                pass

        with tempfile.TemporaryDirectory() as temp:
            store = DocumentFamilyCatalogStore(Path(temp) / "family-catalog.json")
            manager = Manager()
            app = create_expense_report_app(family_catalog_store=store, expense_case_processing_manager=manager)
            try:
                body, kind = _form(**TAXI_FORM)
                _request(app, "POST", "/catalog/families", body, kind)
            finally:
                app.close()
        self.assertEqual([family.id for family in manager.received.families], ["custom_ricevuta_taxi"])


class OpaqueOriginFormTests(unittest.TestCase):
    def test_form_posted_from_the_sandboxed_page_is_accepted(self):
        # Pages are served with a CSP sandbox, so the browser posts with Origin: null
        # and the CSRF gate reads the body first; the route must reuse it.
        import re

        with tempfile.TemporaryDirectory() as temp:
            store = DocumentFamilyCatalogStore(Path(temp) / "family-catalog.json")
            app = create_expense_report_app(family_catalog_store=store)
            try:
                page = _request(app, path="/catalog")[2].decode("utf-8")
                token = re.search(r'name="_ocr2_csrf" value="([^"]+)"', page).group(1)
                body, kind = _form(_ocr2_csrf=token, **TAXI_FORM)
                status, _, _ = _request(app, "POST", "/catalog/families", body, kind, origin="null")
            finally:
                app.close()
            self.assertEqual(status, "200 OK")
            self.assertEqual([family.id for family in store.load().families], ["custom_ricevuta_taxi"])


class CatalogSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "family-catalog.json"
        self.store = DocumentFamilyCatalogStore(self.path)
        self.app = create_expense_report_app(family_catalog_store=self.store)
        self.addCleanup(self.app.close)

    def _history(self):
        return sorted((self.path.parent / "catalog-history").glob("*.json"))

    def test_import_that_redefines_an_existing_type_is_refused(self):
        body, kind = _form(**TAXI_FORM)
        _request(self.app, "POST", "/catalog/families", body, kind)
        before = self.path.read_bytes()
        changed = family_from_form(**dict(TAXI_FORM, title_cues="SOLO TAXI"))
        body, kind = _upload("c.json", json.dumps({"catalog_version": "2", "families": [changed]}).encode())
        status, _, page = _request(self.app, "POST", "/catalog/import", body, kind)
        self.assertEqual(status, "400 Bad Request")
        self.assertIn("definizione diversa".encode(), page)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self._history(), [])

    def test_adding_to_a_version_1_catalog_keeps_its_version(self):
        v1 = {"catalog_version": "1", "families": [{"id": "custom_park", "label": "Parcheggio",
              "title_cues": ["TICKET PARK"], "fields": [{"id": "plate", "label": "Targa", "aliases": ["Targa"]}]}]}
        self.path.write_text(json.dumps(v1), encoding="utf-8")
        app = create_expense_report_app(family_catalog_store=self.store, custom_family_catalog=self.store.load())
        try:
            body, kind = _form(label="Ricevuta bar", title_cues="BAR", fields="Tavolo: Tavolo")
            status, _, _ = _request(app, "POST", "/catalog/families", body, kind)
            self.assertEqual(status, "200 OK")
            self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["catalog_version"], "1")
            body, kind = _form(label="Ricevuta hotel", title_cues="HOTEL", fields="Notti: Notti [importo]")
            status, _, page = _request(app, "POST", "/catalog/families", body, kind)
            self.assertEqual(status, "400 Bad Request")
            self.assertIn("formato 1".encode(), page)
        finally:
            app.close()

    def test_errors_say_what_to_fix(self):
        cases = [
            (dict(TAXI_FORM, fields="Partenza: Corsa\nArrivo: Corsa"), "alias «Corsa»"),
            (dict(TAXI_FORM, fields="Data: Giorno\nData!: Quando"), "righe 1 e 2"),
        ]
        for form, expected in cases:
            with self.subTest(expected=expected):
                body, kind = _form(**form)
                status, _, page = _request(self.app, "POST", "/catalog/families", body, kind)
                self.assertEqual(status, "400 Bad Request")
                self.assertIn(expected.encode(), page)
        body, kind = _upload("big.json", b"{" + b" " * (70 * 1024) + b"}")
        status, _, page = _request(self.app, "POST", "/catalog/import", body, kind)
        self.assertEqual(status, "400 Bad Request")
        self.assertIn("troppo grande".encode(), page)


if __name__ == "__main__":
    unittest.main()
