import json
import unittest
from pathlib import Path
from unittest.mock import patch
from alfa_document_intelligence import local_intake_app
from alfa_document_intelligence.review_ledger import verify_review_ledger

class ReviewIdentityTests(unittest.TestCase):
    def setUp(self):
        self.record = json.loads((Path(__file__).parent / 'fixtures' / 'synthetic_invoice.json').read_text(encoding='utf-8'))

    def test_new_events_use_server_identity(self):
        with patch.object(local_intake_app, '_windows_review_actor', return_value='synthetic-user'):
            result = local_intake_app._begin_document_review(self.record, timestamp='2026-11-15T12:00:00+00:00')
        self.assertEqual([e['actor_id'] for e in result['review']['events']], ['synthetic-user', 'synthetic-user'])
        self.assertTrue(verify_review_ledger(result))
        self.assertEqual(self.record['review']['events'], [])

    def test_review_page_handles_unavailable_identity_without_recording_events(self):
        from test_evidence_linked_review_ui import _request, _upload
        app = local_intake_app.create_expense_report_app()
        self.assertEqual(_upload(app)[0], "200 OK")
        from urllib.parse import urlencode
        body = urlencode({"note_document_id": "doc-001"}).encode()
        self.assertEqual(_request(app, "POST", "/assign-note", body, "application/x-www-form-urlencoded")[0], "200 OK")
        with patch.object(local_intake_app, "_windows_review_actor", side_effect=local_intake_app.IntakeRequestError("identity unavailable")):
            status, body = _request(app, path="/reviews/doc-001")
        self.assertEqual(status, "503 Service Unavailable")
        self.assertIn("Impossibile identificare".encode(), body)

    def test_stale_review_form_is_rejected_without_overwriting_new_event(self):
        import re
        from urllib.parse import urlencode
        from test_evidence_linked_review_ui import _request, _upload
        app = local_intake_app.create_expense_report_app()
        self.assertEqual(_upload(app)[0], "200 OK")
        self.assertEqual(_request(app, "POST", "/assign-note", b"note_document_id=doc-001", "application/x-www-form-urlencoded")[0], "200 OK")
        status, page = _request(app, path="/reviews/doc-001")
        self.assertEqual(status, "200 OK")
        token = re.search(rb'name="expected_review_head" value="([a-f0-9]{64})"', page)
        self.assertIsNotNone(token)
        form = urlencode({"expected_review_head": token.group(1).decode(), "review_seconds": "0"}).encode()
        self.assertEqual(_request(app, "POST", "/reviews/doc-001/complete", form, "application/x-www-form-urlencoded")[0], "200 OK")
        for suffix, data in (
            ("complete", {}), ("document-family", {"document_family": "invoice"}),
            ("fiscal-state", {"fiscal_status": "uncertain", "evidence_index": "0"}),
            ("alternatives/merchant_name", {"alternative_index": "0"}),
            ("fields/merchant_name", {"value": "Sintetico"}),
        ):
            data.update({"expected_review_head": token.group(1).decode(), "review_seconds": "0"})
            status, conflict = _request(app, "POST", "/reviews/doc-001/" + suffix,
                                        urlencode(data).encode(), "application/x-www-form-urlencoded")
            with self.subTest(route=suffix):
                self.assertEqual(status, "409 Conflict")
                self.assertIn(b'<html lang="it">', conflict)
                self.assertIn(b'<title>Revisione aggiornata</title>', conflict)
                self.assertIn(b'href="/reviews/doc-001"', conflict)
                self.assertIn(b'Apri la revisione aggiornata', conflict)
        self.assertEqual(_request(app, path="/reviews/doc-001")[0], "200 OK")

    def test_simultaneous_review_submissions_accept_at_most_one(self):
        import re
        from concurrent.futures import ThreadPoolExecutor
        from urllib.parse import urlencode
        from test_evidence_linked_review_ui import _request, _upload
        app = local_intake_app.create_expense_report_app()
        self.assertEqual(_upload(app)[0], "200 OK")
        _request(app, "POST", "/assign-note", b"note_document_id=doc-001", "application/x-www-form-urlencoded")
        page = _request(app, path="/reviews/doc-001")[1]
        head = re.search(rb'name="expected_review_head" value="([a-f0-9]{64})"', page).group(1).decode()
        form = urlencode({"expected_review_head": head, "review_seconds": "0"}).encode()
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(lambda _: _request(app, "POST", "/reviews/doc-001/complete", form, "application/x-www-form-urlencoded")[0], range(2)))
        self.assertEqual(sorted(statuses), ["200 OK", "409 Conflict"])

    def test_opening_review_cannot_overwrite_concurrent_completion(self):
        import re
        import threading
        from concurrent.futures import ThreadPoolExecutor
        from urllib.parse import urlencode
        from test_evidence_linked_review_ui import _request, _upload
        app = local_intake_app.create_expense_report_app()
        self.assertEqual(_upload(app)[0], "200 OK")
        _request(app, "POST", "/assign-note", b"note_document_id=doc-001", "application/x-www-form-urlencoded")
        page = _request(app, path="/reviews/doc-001")[1]
        head = re.search(rb'name="expected_review_head" value="([a-f0-9]{64})"', page).group(1).decode()
        entered, release = threading.Event(), threading.Event()
        real = local_intake_app._begin_document_review
        def delayed(record, *, timestamp):
            entered.set()
            if not release.wait(2):
                raise RuntimeError("test release timed out")
            return real(record, timestamp=timestamp)
        form = urlencode({"expected_review_head": head, "review_seconds": "0"}).encode()
        with patch.object(local_intake_app, "_begin_document_review", side_effect=delayed):
            with ThreadPoolExecutor(max_workers=2) as pool:
                opened = pool.submit(_request, app, path="/reviews/doc-001")
                self.assertTrue(entered.wait(2))
                finished = pool.submit(_request, app, "POST", "/reviews/doc-001/complete", form, "application/x-www-form-urlencoded")
                release.set()
                self.assertEqual(opened.result(timeout=3)[0], "200 OK")
                self.assertEqual(finished.result(timeout=3)[0], "200 OK")
        page = _request(app, path="/reviews/doc-001")[1]
        self.assertNotIn(b"Concludi revisione", page)

    def test_slow_upload_does_not_block_session_clear(self):
        import io
        import threading
        from concurrent.futures import ThreadPoolExecutor
        from test_evidence_linked_review_ui import _request
        entered, release = threading.Event(), threading.Event()
        class SlowStream(io.BytesIO):
            def read(self, *args):
                entered.set()
                if not release.wait(3):
                    raise RuntimeError("test release timed out")
                return super().read(*args)
        app = local_intake_app.create_expense_report_app()
        stream = SlowStream(b"x")
        env = {"REQUEST_METHOD":"POST", "PATH_INFO":"/upload", "HTTP_HOST":"127.0.0.1:8080",
               "HTTP_ORIGIN":"http://127.0.0.1:8080", "CONTENT_LENGTH":"1", "CONTENT_TYPE":"multipart/form-data; boundary=x", "wsgi.input":stream}
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                upload = pool.submit(lambda: b"".join(app(env, lambda status, headers: None)))
                self.assertTrue(entered.wait(2))
                clear = pool.submit(_request, app, "POST", "/clear", b"clear=1", "application/x-www-form-urlencoded")
                self.assertEqual(clear.result(timeout=1)[0], "200 OK")
                release.set()
                upload.result(timeout=3)
        finally:
            release.set()

    def test_slow_preview_does_not_block_clear(self):
        import threading
        from concurrent.futures import ThreadPoolExecutor
        from test_evidence_linked_review_ui import _request, _upload
        app = local_intake_app.create_expense_report_app()
        self.assertEqual(_upload(app)[0], "200 OK")
        _request(app, "POST", "/assign-note", b"note_document_id=doc-001", "application/x-www-form-urlencoded")
        entered, release = threading.Event(), threading.Event()
        def preview(*args):
            entered.set()
            if not release.wait(3):
                raise RuntimeError("test release timed out")
            return b"synthetic"
        try:
            with patch.object(local_intake_app, "_source_page_png", side_effect=preview):
                with ThreadPoolExecutor(max_workers=2) as pool:
                    request = pool.submit(_request, app, path="/reviews/doc-001/pages/1.png")
                    self.assertTrue(entered.wait(2))
                    clear = pool.submit(_request, app, "POST", "/clear", b"clear=1", "application/x-www-form-urlencoded")
                    self.assertEqual(clear.result(timeout=1)[0], "200 OK")
                    release.set()
                    request.result(timeout=3)
        finally:
            release.set()

    def test_slow_processor_cannot_publish_after_session_clear(self):
        import threading
        from concurrent.futures import ThreadPoolExecutor
        from test_evidence_linked_review_ui import _request, _upload
        entered, release = threading.Event(), threading.Event()
        def processor(record, source):
            entered.set()
            if not release.wait(3):
                raise RuntimeError("test release timed out")
            return record
        app = local_intake_app.create_expense_report_app(document_processor=processor)
        self.assertEqual(_upload(app)[0], "200 OK")
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                assign = pool.submit(_request, app, "POST", "/assign-note", b"note_document_id=doc-001", "application/x-www-form-urlencoded")
                self.assertTrue(entered.wait(2))
                self.assertEqual(_request(app, "POST", "/clear", b"clear=1", "application/x-www-form-urlencoded")[0], "200 OK")
                release.set()
                self.assertEqual(assign.result(timeout=3)[0], "409 Conflict")
        finally:
            release.set()

    def test_slow_review_body_does_not_block_clear(self):
        import io, threading
        from concurrent.futures import ThreadPoolExecutor
        from test_evidence_linked_review_ui import _request, _upload
        app = local_intake_app.create_expense_report_app()
        self.assertEqual(_upload(app)[0], "200 OK")
        _request(app, "POST", "/assign-note", b"note_document_id=doc-001", "application/x-www-form-urlencoded")
        _request(app, path="/reviews/doc-001")
        entered, release = threading.Event(), threading.Event()
        class SlowStream(io.BytesIO):
            def read(self, *args):
                entered.set()
                if not release.wait(3): raise RuntimeError("test release timed out")
                return super().read(*args)
        body=b"review_seconds=0"
        env={"REQUEST_METHOD":"POST", "PATH_INFO":"/reviews/doc-001/complete", "HTTP_HOST":"127.0.0.1:8080",
             "HTTP_ORIGIN":"http://127.0.0.1:8080", "CONTENT_LENGTH":str(len(body)),
             "CONTENT_TYPE":"application/x-www-form-urlencoded", "wsgi.input":SlowStream(body)}
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                request=pool.submit(lambda: b"".join(app(env, lambda status, headers: None)))
                self.assertTrue(entered.wait(2))
                clear=pool.submit(_request, app, "POST", "/clear", b"clear=1", "application/x-www-form-urlencoded")
                self.assertEqual(clear.result(timeout=1)[0], "200 OK")
                release.set(); request.result(timeout=3)
        finally: release.set()

    def test_slow_assignment_cannot_overwrite_newer_assignment_and_review(self):
        import re, threading
        from concurrent.futures import ThreadPoolExecutor
        from urllib.parse import urlencode
        from test_evidence_linked_review_ui import _request, _upload
        entered, release = threading.Event(), threading.Event()
        first_thread = [None]
        def processor(record, source):
            current = threading.get_ident()
            if first_thread[0] is None: first_thread[0] = current
            if current == first_thread[0] and not release.is_set():
                entered.set()
                if not release.wait(3): raise RuntimeError("test release timed out")
            return record
        app = local_intake_app.create_expense_report_app(document_processor=processor)
        self.assertEqual(_upload(app)[0], "200 OK")
        form = b"note_document_id=doc-001"
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                first = pool.submit(_request, app, "POST", "/assign-note", form, "application/x-www-form-urlencoded")
                self.assertTrue(entered.wait(2))
                self.assertEqual(_request(app, "POST", "/assign-note", form, "application/x-www-form-urlencoded")[0], "200 OK")
                page = _request(app, path="/reviews/doc-001")[1]
                head = re.search(rb'name="expected_review_head" value="([a-f0-9]{64})"', page).group(1).decode()
                done = urlencode({"expected_review_head": head, "review_seconds": "0"}).encode()
                self.assertEqual(_request(app, "POST", "/reviews/doc-001/complete", done, "application/x-www-form-urlencoded")[0], "200 OK")
                release.set(); self.assertEqual(first.result(timeout=3)[0], "409 Conflict")
                self.assertNotIn(b"Concludi revisione", _request(app, path="/reviews/doc-001")[1])
        finally: release.set()

    def test_slow_original_source_does_not_block_clear_or_return_removed_source(self):
        import threading
        from concurrent.futures import ThreadPoolExecutor
        from test_evidence_linked_review_ui import _request, _upload
        app = local_intake_app.create_expense_report_app()
        self.assertEqual(_upload(app)[0], "200 OK")
        _request(app, "POST", "/assign-note", b"note_document_id=doc-001", "application/x-www-form-urlencoded")
        entered, release = threading.Event(), threading.Event()
        original = local_intake_app.create_review_app
        def delayed(*args, **kwargs):
            entered.set()
            if not release.wait(3): raise RuntimeError("test release timed out")
            return original(*args, **kwargs)
        try:
            with patch.object(local_intake_app, "create_review_app", side_effect=delayed):
                with ThreadPoolExecutor(max_workers=2) as pool:
                    request = pool.submit(_request, app, path="/reviews/doc-001/source")
                    self.assertTrue(entered.wait(2))
                    clear = pool.submit(_request, app, "POST", "/clear", b"clear=1", "application/x-www-form-urlencoded")
                    self.assertEqual(clear.result(timeout=1)[0], "200 OK")
                    release.set(); self.assertEqual(request.result(timeout=3)[0], "409 Conflict")
        finally: release.set()

    def test_local_account_can_be_resolved(self):
        self.assertTrue(local_intake_app._windows_review_actor().strip())

    def test_unavailable_identity_cannot_create_events(self):
        with patch.object(local_intake_app, '_windows_review_actor', side_effect=local_intake_app.IntakeRequestError('identity unavailable')):
            with self.assertRaises(local_intake_app.IntakeRequestError):
                local_intake_app._begin_document_review(self.record, timestamp='2026-11-15T12:00:00+00:00')
        self.assertEqual(self.record['review']['events'], [])
