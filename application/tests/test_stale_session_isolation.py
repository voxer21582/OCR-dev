import io
import unittest
from html.parser import HTMLParser
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlsplit

from alfa_document_intelligence import local_intake_app


OLD_SOURCE = b"%PDF-1.7\nsynthetic old document\n"
NEW_SOURCE = b"%PDF-1.7\nsynthetic new document\n"


class _Page(HTMLParser):
    def __init__(self, body):
        super().__init__()
        self.links = []
        self.forms = []
        self.images = []
        self._form = None
        self.feed(body.decode("utf-8"))

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and "href" in attrs:
            self.links.append(attrs["href"])
        elif tag == "img" and "src" in attrs:
            self.images.append(attrs["src"])
        elif tag == "form":
            self._form = {"action": attrs.get("action", ""), "fields": []}
            self.forms.append(self._form)
        elif tag == "input" and self._form is not None and attrs.get("name"):
            if attrs.get("type", "text").lower() == "hidden":
                self._form["fields"].append((attrs["name"], attrs.get("value", "")))

    def handle_endtag(self, tag):
        if tag == "form":
            self._form = None

    def form(self, action):
        return next(form for form in self.forms if action in form["action"])

    def link(self, suffix):
        return next(link for link in self.links if urlsplit(link).path.endswith(suffix))


def _request(app, method="GET", url="/", body=b"", content_type="", origin="http://127.0.0.1:8080"):
    result = {}
    parsed = urlsplit(url)

    def start_response(status, headers):
        result["status"] = status
        result["headers"] = dict(headers)

    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": parsed.path,
        "QUERY_STRING": parsed.query,
        "HTTP_HOST": "127.0.0.1:8080",
        "HTTP_ORIGIN": origin,
        "CONTENT_LENGTH": str(len(body)) if body else "",
        "CONTENT_TYPE": content_type,
        "wsgi.input": io.BytesIO(body),
    }
    result["body"] = b"".join(app(environ, start_response))
    return result


def _post(app, form, fields=(), origin="http://127.0.0.1:8080"):
    overrides = dict(fields)
    body = urlencode([(key, value) for key, value in form["fields"] if key not in overrides] + list(fields)).encode("ascii")
    return _request(app, "POST", form["action"], body, "application/x-www-form-urlencoded", origin)


def _upload(app, page, source, origin="http://127.0.0.1:8080", action=None):
    form = _Page(page).form("/upload")
    boundary = "synthetic-boundary"
    parts = []
    for name, value in form["fields"]:
        parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n').encode())
    parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="note.pdf"\r\nContent-Type: application/pdf\r\n\r\n').encode() + source + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return _request(app, "POST", action or form["action"], b"".join(parts), f"multipart/form-data; boundary={boundary}", origin)


class StaleSessionIsolationTests(unittest.TestCase):
    def test_expired_review_link_cannot_open_replacement_session(self):
        now = [0.0]
        app = local_intake_app.create_expense_report_app(clock=lambda: now[0], idle_timeout_seconds=5)
        first = _upload(app, _request(app)["body"], OLD_SOURCE)
        assigned = _post(app, _Page(first["body"]).form("/assign-note"), [("note_document_id", "doc-001")])
        self.assertEqual(assigned["status"], "200 OK")
        old_link = _Page(assigned["body"]).link("/reviews/doc-001")
        now[0] = 6.0
        self.assertIn(_request(app, url=old_link)["status"].split()[0], {"404", "409"})
        second = _upload(app, _request(app)["body"], NEW_SOURCE)
        assigned = _post(app, _Page(second["body"]).form("/assign-note"), [("note_document_id", "doc-001")])
        self.assertEqual(assigned["status"], "200 OK")
        self.assertIn(_request(app, url=old_link)["status"].split()[0], {"404", "409"})
        self.assertEqual(_request(app, url=_Page(assigned["body"]).link("/reviews/doc-001"))["status"], "200 OK")

    def test_empty_upload_page_cannot_start_session_after_clear_or_expiry(self):
        now = [0.0]
        app = local_intake_app.create_expense_report_app(clock=lambda: now[0], idle_timeout_seconds=5)
        empty = _request(app)["body"]
        uploaded = _upload(app, empty, OLD_SOURCE)
        self.assertEqual(uploaded["status"], "200 OK")
        cleared = _post(app, _Page(uploaded["body"]).form("/clear"))
        self.assertEqual(cleared["status"], "200 OK")
        stale = _upload(app, empty, OLD_SOURCE)
        self.assertIn(stale["status"].split()[0], {"404", "409"})
        current = _upload(app, cleared["body"], NEW_SOURCE)
        self.assertEqual(current["status"], "200 OK")
        expired_clear = _Page(current["body"]).form("/clear")
        now[0] = 6.0
        self.assertIn(_post(app, expired_clear)["status"].split()[0], {"404", "409"})
        fresh_empty = _request(app)["body"]
        self.assertEqual(_upload(app, fresh_empty, NEW_SOURCE)["status"], "200 OK")

    def test_duplicate_session_query_rejected_without_mutation(self):
        app = local_intake_app.create_expense_report_app()
        empty = _request(app)["body"]
        upload_action = _Page(empty).form("/upload")["action"]
        tokens = parse_qs(urlsplit(upload_action).query).get("_ocr2_session", [])
        self.assertEqual(len(tokens), 1)
        duplicate = upload_action + "&" + urlencode({"_ocr2_session": tokens[0]})
        self.assertIn(_upload(app, empty, OLD_SOURCE, action=duplicate)["status"].split()[0], {"400", "404", "409"})
        uploaded = _upload(app, empty, NEW_SOURCE)
        self.assertEqual(uploaded["status"], "200 OK")
        clear = _Page(uploaded["body"]).form("/clear")
        clear_tokens = parse_qs(urlsplit(clear["action"]).query).get("_ocr2_session", [])
        self.assertEqual(len(clear_tokens), 1)
        duplicate_clear = dict(clear, action=clear["action"] + "&" + urlencode({"_ocr2_session": clear_tokens[0]}))
        self.assertIn(_post(app, duplicate_clear)["status"].split()[0], {"400", "404", "409"})
        self.assertEqual(_post(app, clear)["status"], "200 OK")

    def test_opaque_origin_multipart_and_urlencoded_forms_keep_session_binding(self):
        app = local_intake_app.create_expense_report_app()
        empty = _request(app)["body"]
        uploaded = _upload(app, empty, OLD_SOURCE, origin="null")
        self.assertEqual(uploaded["status"], "200 OK")
        old_clear = _Page(uploaded["body"]).form("/clear")
        cleared = _post(app, old_clear, origin="null")
        self.assertEqual(cleared["status"], "200 OK")
        current = _upload(app, cleared["body"], NEW_SOURCE, origin="null")
        self.assertEqual(current["status"], "200 OK")
        self.assertIn(_post(app, old_clear, origin="null")["status"].split()[0], {"404", "409"})
        self.assertEqual(_post(app, _Page(current["body"]).form("/clear"), origin="null")["status"], "200 OK")

    def test_stale_review_links_and_forms_cannot_access_or_change_replacement_session(self):
        sessions = []
        original_create = local_intake_app.create_expense_report_intake_session

        def create_with_candidate(*args, **kwargs):
            session = original_create(*args, **kwargs)
            record = session.documents["doc-001"]
            record["pages"] = [{"page_number": 1}]
            record["fields"]["merchant_name"] = {
                "value": "Synthetic merchant", "status": "uncertain", "alternatives": [],
                "evidence": [{"source_sha256": record["source"]["sha256"], "page_number": 1,
                              "region": {"x": 10, "y": 10, "width": 100, "height": 20},
                              "literal": "Synthetic merchant"}],
            }
            record["fields"]["shop_code"] = {
                "value": None, "status": "absent", "alternatives": [], "evidence": [],
            }
            sessions.append(session)
            return session

        with patch.object(local_intake_app, "create_expense_report_intake_session", create_with_candidate):
            app = local_intake_app.create_expense_report_app()
            start = _request(app)
            first_upload = _upload(app, start["body"], OLD_SOURCE)
            self.assertEqual(first_upload["status"], "200 OK")
            first_assignment = _post(app, _Page(first_upload["body"]).form("/assign-note"), [("note_document_id", "doc-001")])
            self.assertEqual(first_assignment["status"], "200 OK")
            first_bundle = _Page(first_assignment["body"])
            old_review_link = first_bundle.link("/reviews/doc-001")
            old_clear = first_bundle.form("/clear")
            old_review = _request(app, url=old_review_link)
            self.assertEqual(old_review["status"], "200 OK")
            old_page = _Page(old_review["body"])
            old_source_link = old_page.link("/reviews/doc-001/source")
            old_root_link = old_page.link("/")
            old_chatgpt_link = first_bundle.link("/chatgpt")
            old_times_link = first_bundle.link("/review-times.csv")
            old_preview = next(src for src in old_page.images if urlsplit(src).path.endswith("/pages/1.png"))
            old_correction = old_page.form("/fields/merchant_name")
            cleared = _post(app, old_clear)
            self.assertEqual(cleared["status"], "200 OK")

            second_upload = _upload(app, cleared["body"], NEW_SOURCE)
            self.assertEqual(second_upload["status"], "200 OK")
            second_assignment = _post(app, _Page(second_upload["body"]).form("/assign-note"), [("note_document_id", "doc-001")])
            self.assertEqual(second_assignment["status"], "200 OK")
            current_link = _Page(second_assignment["body"]).link("/reviews/doc-001")
            current_record = sessions[-1].documents["doc-001"]
            initial_events = list(current_record["review"]["events"])

            for url in (old_review_link, old_source_link, old_root_link, old_chatgpt_link, old_times_link, old_preview):
                response = _request(app, url=url)
                self.assertIn(response["status"].split()[0], {"404", "409"})
                self.assertNotIn(NEW_SOURCE, response["body"])
            # The unbound root is an explicit entry point, not a bypass for
            # session-specific resources or an already-bound stale root link.
            self.assertEqual(_request(app, url="/")["status"], "200 OK")
            for url in ("/reviews/doc-001", "/reviews/doc-001/source", "/reviews/doc-001/pages/1.png", "/chatgpt", "/review-times.csv"):
                self.assertIn(_request(app, url=url)["status"].split()[0], {"404", "409"})
            self.assertEqual(sessions[-1].documents["doc-001"]["review"]["events"], initial_events)
            correction = _post(app, old_correction, [("value", "Stale correction"), ("review_seconds", "1")])
            self.assertIn(correction["status"].split()[0], {"404", "409"})
            clear_again = _post(app, old_clear)
            self.assertIn(clear_again["status"].split()[0], {"404", "409"})
            self.assertEqual(sessions[-1].documents["doc-001"]["review"]["events"], initial_events)
            current_review = _request(app, url=current_link)
            self.assertEqual(current_review["status"], "200 OK")
            self.assertNotIn(b"Stale correction", current_review["body"])
            current_bundle = _Page(second_assignment["body"])
            self.assertEqual(_request(app, url=current_bundle.link("/chatgpt"))["status"], "200 OK")
            self.assertEqual(_request(app, url=current_bundle.link("/review-times.csv"))["status"], "200 OK")
            current_preview = next(src for src in _Page(current_review["body"]).images if urlsplit(src).path.endswith("/pages/1.png"))
            with patch.object(local_intake_app, "_source_page_png", return_value=b"synthetic png"):
                self.assertEqual(_request(app, url=current_preview)["body"], b"synthetic png")
            current_source = _request(app, url=_Page(current_review["body"]).link("/reviews/doc-001/source"))
            self.assertEqual(current_source["status"], "200 OK")
            self.assertEqual(current_source["body"], NEW_SOURCE)


if __name__ == "__main__":
    unittest.main()
