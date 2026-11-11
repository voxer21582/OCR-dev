import copy
import hashlib
import io
import threading
import unittest
from urllib.parse import urlencode

from alfa_document_intelligence.local_intake_app import create_expense_report_app
from alfa_document_intelligence.ocr_processing import (
    OCRJobStatus,
    PROTOCOL_VERSION,
    encode_frame,
)


def _zip_upload():
    import zipfile

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("synthetic/note.pdf", b"%PDF-1.7\nsynthetic note\n")
    boundary = "ocr-job-test"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="files"; filename="synthetic.zip"\r\n'
        "Content-Type: application/zip\r\n\r\n"
    ).encode() + output.getvalue() + f"\r\n--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def _request(app, method="GET", path="/", body=b"", content_type="", *, origin="http://127.0.0.1:8000"):
    response = {}

    def start_response(status, headers):
        response["status"] = status
        response["headers"] = dict(headers)

    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "HTTP_HOST": "127.0.0.1:8000",
        "HTTP_ORIGIN": origin,
        "CONTENT_LENGTH": str(len(body)) if body else "",
        "CONTENT_TYPE": content_type,
        "QUERY_STRING": "",
        "wsgi.url_scheme": "http",
        "wsgi.input": io.BytesIO(body),
    }
    result = b"".join(app(environ, start_response))
    return response["status"], response["headers"], result


class _FakeOCRManager:
    def __init__(self):
        self.started = []
        self.cancelled = []
        self.published = []
        self.statuses = {}
        self.frames = {}
        self.closed = False
        self.catalogs = []

    def start(self, generation_id, intake, *, decode_limits, custom_family_catalog=None):
        job_id = f"{len(self.started) + 1:032x}"
        self.started.append((job_id, generation_id, intake))
        self.catalogs.append(custom_family_catalog)
        self.statuses[job_id] = OCRJobStatus(job_id, generation_id, "queued", 0, 1, 0, 0, None)
        return job_id

    def snapshot(self, job_id):
        return self.statuses.get(job_id)

    def result_frame(self, generation_id, job_id):
        started = next((item for item in self.started if item[0] == job_id), None)
        if started is None or started[1] != generation_id:
            return None
        return self.frames.get(job_id)

    def publish_if_current(self, generation_id, job_id, digest):
        frame = self.frames.get(job_id)
        item = next((entry for entry in self.started if entry[0] == job_id), None)
        if item is None or item[1] != generation_id or frame is None:
            return False
        if hashlib.sha256(frame).hexdigest() != digest or (job_id, digest) in self.published:
            return False
        self.published.append((job_id, digest))
        self.frames.pop(job_id)
        return True

    def mark_cancelled(self, generation_id):
        self.cancelled.append(generation_id)
        for job_id, current_generation, _intake in self.started:
            if current_generation != generation_id:
                continue
            current = self.statuses[job_id]
            if current.phase == "succeeded":
                self.frames.pop(job_id, None)
                self.statuses[job_id] = OCRJobStatus(
                    job_id, generation_id, "cancelled", current.completed_documents,
                    current.total_documents, current.current_page, current.total_pages, None,
                )
            elif current.phase not in {"failed", "cancelled"}:
                self.statuses[job_id] = OCRJobStatus(
                    job_id, generation_id, "cancelling", current.completed_documents,
                    current.total_documents, current.current_page, current.total_pages, None,
                )

    def close(self):
        self.closed = True


class OCRJobUiTests(unittest.TestCase):
    def setUp(self):
        self.manager = _FakeOCRManager()
        self.app = create_expense_report_app(ocr_processing_manager=self.manager)
        body, content_type = _zip_upload()
        status, _, page = _request(self.app, "POST", "/upload", body, content_type)
        self.assertEqual(status, "200 OK")
        self.assertIn(b"synthetic/note.pdf", page)

    def _assign_note(self):
        body = urlencode({"note_document_id": "doc-001"}).encode()
        return _request(
            self.app, "POST", "/assign-note", body,
            "application/x-www-form-urlencoded",
        )

    def test_manager_mode_starts_job_and_exposes_only_aggregate_status(self):
        status, _, page = self._assign_note()
        self.assertEqual(status, "200 OK")
        self.assertEqual(len(self.manager.started), 1)
        job_id = self.manager.started[0][0]
        self.assertIn(b"00000000000000000000000000000001", page)
        self.assertIn(b"Elaborazione OCR", page)
        self.assertNotIn(b"source_bytes", page)

        self.manager.statuses[job_id] = OCRJobStatus(
            job_id, self.manager.started[0][1], "processing", 0, 1, 2, 4, None,
        )
        status, _, progress = _request(self.app, path=f"/ocr/jobs/{job_id}")
        self.assertEqual(status, "200 OK")
        self.assertIn(b"2 / 4", progress)
        self.assertNotIn(b"synthetic note", progress)

    def test_custom_family_catalog_is_forwarded_to_the_manager(self):
        sentinel_catalog = object()
        manager = _FakeOCRManager()
        app = create_expense_report_app(
            ocr_processing_manager=manager,
            custom_family_catalog=sentinel_catalog,
        )
        body, content_type = _zip_upload()
        _request(app, "POST", "/upload", body, content_type)
        status, _, _ = _request(
            app, "POST", "/assign-note",
            urlencode({"note_document_id": "doc-001"}).encode(),
            "application/x-www-form-urlencoded",
        )
        self.assertEqual(status, "200 OK")
        self.assertEqual(manager.catalogs, [sentinel_catalog])
        app.close()

    def test_clear_during_worker_start_cancels_detached_generation(self):
        entered = threading.Event()
        release = threading.Event()

        class SlowStartManager(_FakeOCRManager):
            def start(inner_self, generation_id, intake, *, decode_limits, custom_family_catalog=None):
                entered.set()
                if not release.wait(3):
                    raise TimeoutError("synthetic worker-start gate timed out")
                return super(SlowStartManager, inner_self).start(
                    generation_id, intake, decode_limits=decode_limits,
                    custom_family_catalog=custom_family_catalog,
                )

        manager = SlowStartManager()
        app = create_expense_report_app(ocr_processing_manager=manager)
        body, content_type = _zip_upload()
        _request(app, "POST", "/upload", body, content_type)
        assigned = []
        thread = threading.Thread(
            target=lambda: assigned.append(_request(
                app, "POST", "/assign-note",
                urlencode({"note_document_id": "doc-001"}).encode(),
                "application/x-www-form-urlencoded",
            )),
            daemon=True,
        )
        thread.start()
        self.assertTrue(entered.wait(2))
        status, _, _ = _request(
            app, "POST", "/clear", b"clear=1",
            "application/x-www-form-urlencoded",
        )
        self.assertEqual(status, "200 OK")
        release.set()
        thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(assigned[0][0], "409 Conflict")
        self.assertEqual(len(manager.started), 1)
        generation = manager.started[0][1]
        self.assertIn(generation, manager.cancelled)
        self.assertEqual(manager.snapshot(manager.started[0][0]).phase, "cancelling")
        app.close()

    def test_upload_replacement_during_worker_start_cancels_detached_generation(self):
        entered = threading.Event()
        release = threading.Event()

        class SlowStartManager(_FakeOCRManager):
            def start(inner_self, generation_id, intake, *, decode_limits, custom_family_catalog=None):
                entered.set()
                if not release.wait(3):
                    raise TimeoutError("synthetic worker-start gate timed out")
                return super(SlowStartManager, inner_self).start(
                    generation_id, intake, decode_limits=decode_limits,
                    custom_family_catalog=custom_family_catalog,
                )

        manager = SlowStartManager()
        app = create_expense_report_app(ocr_processing_manager=manager)
        body, content_type = _zip_upload()
        _request(app, "POST", "/upload", body, content_type)
        assigned = []
        thread = threading.Thread(
            target=lambda: assigned.append(_request(
                app, "POST", "/assign-note",
                urlencode({"note_document_id": "doc-001"}).encode(),
                "application/x-www-form-urlencoded",
            )),
            daemon=True,
        )
        thread.start()
        self.assertTrue(entered.wait(2))
        replacement_body, replacement_type = _zip_upload()
        status, _, _ = _request(app, "POST", "/upload", replacement_body, replacement_type)
        self.assertEqual(status, "200 OK")
        release.set()
        thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(assigned[0][0], "409 Conflict")
        self.assertEqual(len(manager.started), 1)
        generation = manager.started[0][1]
        self.assertIn(generation, manager.cancelled)
        self.assertEqual(manager.snapshot(manager.started[0][0]).phase, "cancelling")
        app.close()

    def test_concurrent_success_polls_consume_one_result_without_poisoning_session(self):
        status, _, _ = self._assign_note()
        self.assertEqual(status, "200 OK")
        job_id, generation_id, intake = self.manager.started[0]
        candidate = copy.deepcopy(intake.documents)
        candidate["doc-001"]["processing"]["ocr"]["status"] = "completed"
        self.manager.frames[job_id] = encode_frame({
            "version": PROTOCOL_VERSION,
            "kind": "result",
            "payload": {"job_id": job_id, "generation_id": generation_id, "documents": candidate},
        }, max_bytes=10 * 1024 * 1024)
        self.manager.statuses[job_id] = OCRJobStatus(job_id, generation_id, "succeeded", 1, 1, 1, 1, None)
        barrier = threading.Barrier(2)
        original_result_frame = self.manager.result_frame

        def synchronized_result_frame(requested_generation, requested_job):
            frame = original_result_frame(requested_generation, requested_job)
            barrier.wait(3)
            return frame

        self.manager.result_frame = synchronized_result_frame
        responses = []
        threads = [threading.Thread(
            target=lambda: responses.append(_request(self.app, path="/")), daemon=True,
        ) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(3)
            self.assertFalse(thread.is_alive())
        self.assertEqual([item[0] for item in responses], ["200 OK", "200 OK"])
        self.assertEqual(len(self.manager.published), 1)
        self.assertNotIn(b"Risultato rifiutato", responses[0][2] + responses[1][2])

    def test_cancellation_is_same_origin_protected_and_invalidates_generation(self):
        status, _, page = self._assign_note()
        self.assertEqual(status, "200 OK")
        generation = self.manager.started[0][1]
        job_id = self.manager.started[0][0]
        status, _, _ = _request(
            self.app, "POST", f"/ocr/jobs/{job_id}/cancel", b"",
            "application/x-www-form-urlencoded", origin="http://evil.example",
        )
        self.assertEqual(status, "403 Forbidden")
        self.assertEqual(self.manager.cancelled, [])
        status, _, _ = _request(
            self.app, "POST", f"/ocr/jobs/{job_id}/cancel", b"",
            "application/x-www-form-urlencoded",
        )
        self.assertEqual(status, "200 OK")
        self.assertEqual(self.manager.cancelled, [generation])

    def test_document_mutation_routes_are_blocked_while_job_is_pending(self):
        status, _, page = self._assign_note()
        self.assertEqual(status, "200 OK")
        status, _, result = _request(
            self.app, "POST", "/reviews/doc-001/complete",
            urlencode({"review_seconds": "1"}).encode(),
            "application/x-www-form-urlencoded",
        )
        self.assertEqual(status, "409 Conflict")
        self.assertIn(b"Elaborazione OCR in corso", result)

    def test_clear_cancels_old_generation_and_status_cannot_reach_replacement(self):
        status, _, _ = self._assign_note()
        self.assertEqual(status, "200 OK")
        old_job, old_generation, _ = self.manager.started[0]
        status, _, _ = _request(
            self.app, "POST", "/clear", b"clear=1",
            "application/x-www-form-urlencoded",
        )
        self.assertEqual(status, "200 OK")
        self.assertIn(old_generation, self.manager.cancelled)
        status, _, missing = _request(self.app, path=f"/ocr/jobs/{old_job}")
        self.assertEqual(status, "404 Not Found")
        self.assertEqual(self.manager.published, [])

    def test_replacing_session_cancels_old_generation_and_rejects_old_status(self):
        status, _, _ = self._assign_note()
        self.assertEqual(status, "200 OK")
        old_job, old_generation, _ = self.manager.started[0]
        body, content_type = _zip_upload()
        status, _, _ = _request(self.app, "POST", "/upload", body, content_type)
        self.assertEqual(status, "200 OK")
        self.assertIn(old_generation, self.manager.cancelled)
        status, _, _ = _request(self.app, path=f"/ocr/jobs/{old_job}")
        self.assertEqual(status, "404 Not Found")
        self.assertEqual(self.manager.published, [])

    def test_successful_result_is_validated_then_published_once(self):
        status, _, _ = self._assign_note()
        self.assertEqual(status, "200 OK")
        job_id, generation_id, intake = self.manager.started[0]
        candidate = copy.deepcopy(intake.documents)
        for record in candidate.values():
            record["processing"]["ocr"]["status"] = "completed"
        self.manager.frames[job_id] = encode_frame({
            "version": PROTOCOL_VERSION,
            "kind": "result",
            "payload": {
                "job_id": job_id,
                "generation_id": generation_id,
                "documents": candidate,
            },
        }, max_bytes=10 * 1024 * 1024)
        self.manager.statuses[job_id] = OCRJobStatus(job_id, generation_id, "succeeded", 1, 1, 1, 1, None)

        status, _, page = _request(self.app, path=f"/ocr/jobs/{job_id}")
        self.assertEqual(status, "200 OK")
        self.assertIn(b"Elaborazione completata", page)
        self.assertEqual(len(self.manager.published), 1)
        status, _, _ = _request(self.app, path=f"/ocr/jobs/{job_id}")
        self.assertEqual(status, "200 OK")
        self.assertEqual(len(self.manager.published), 1)

    def test_result_with_changed_source_binding_is_rejected_and_not_published(self):
        status, _, _ = self._assign_note()
        self.assertEqual(status, "200 OK")
        job_id, generation_id, intake = self.manager.started[0]
        candidate = copy.deepcopy(intake.documents)
        candidate["doc-001"]["source"]["sha256"] = "0" * 64
        self.manager.frames[job_id] = encode_frame({
            "version": PROTOCOL_VERSION,
            "kind": "result",
            "payload": {"job_id": job_id, "generation_id": generation_id, "documents": candidate},
        }, max_bytes=10 * 1024 * 1024)
        self.manager.statuses[job_id] = OCRJobStatus(job_id, generation_id, "succeeded", 1, 1, 1, 1, None)
        status, _, page = _request(self.app, path=f"/ocr/jobs/{job_id}")
        self.assertEqual(status, "409 Conflict")
        self.assertIn(b"Risultato rifiutato", page)
        self.assertEqual(self.manager.published, [])

    def test_cancel_after_worker_success_but_before_publication_wins(self):
        status, _, _ = self._assign_note()
        self.assertEqual(status, "200 OK")
        job_id, generation_id, intake = self.manager.started[0]
        candidate = copy.deepcopy(intake.documents)
        candidate["doc-001"]["processing"]["ocr"]["status"] = "completed"
        self.manager.frames[job_id] = encode_frame({
            "version": PROTOCOL_VERSION,
            "kind": "result",
            "payload": {"job_id": job_id, "generation_id": generation_id, "documents": candidate},
        }, max_bytes=10 * 1024 * 1024)
        self.manager.statuses[job_id] = OCRJobStatus(job_id, generation_id, "succeeded", 1, 1, 1, 1, None)

        status, _, page = _request(
            self.app, "POST", f"/ocr/jobs/{job_id}/cancel", b"",
            "application/x-www-form-urlencoded",
        )
        self.assertEqual(status, "200 OK")
        self.assertIn(b"Elaborazione annullata", page)
        self.assertEqual(self.manager.published, [])
        self.assertIsNone(self.manager.frames.get(job_id))

    def test_clear_wins_while_result_validation_is_outside_the_state_lock(self):
        status, _, _ = self._assign_note()
        self.assertEqual(status, "200 OK")
        job_id, generation_id, intake = self.manager.started[0]
        candidate = copy.deepcopy(intake.documents)
        candidate["doc-001"]["processing"]["ocr"]["status"] = "completed"
        frame = encode_frame({
            "version": PROTOCOL_VERSION,
            "kind": "result",
            "payload": {"job_id": job_id, "generation_id": generation_id, "documents": candidate},
        }, max_bytes=10 * 1024 * 1024)
        self.manager.frames[job_id] = frame
        self.manager.statuses[job_id] = OCRJobStatus(job_id, generation_id, "succeeded", 1, 1, 1, 1, None)
        entered = threading.Event()
        release = threading.Event()
        original_result_frame = self.manager.result_frame
        first = [True]
        result_frame_lock = threading.Lock()

        def paused_result_frame(requested_generation, requested_job):
            with result_frame_lock:
                pause = first[0]
                first[0] = False
            if pause:
                entered.set()
                if not release.wait(3):
                    raise TimeoutError("synthetic result validation gate timed out")
            return original_result_frame(requested_generation, requested_job)

        self.manager.result_frame = paused_result_frame
        response = []
        request_thread = threading.Thread(
            target=lambda: response.append(_request(self.app, path="/")),
            daemon=True,
        )
        request_thread.start()
        self.assertTrue(entered.wait(2), "result validation did not reach the synthetic gate")
        status, _, _ = _request(
            self.app, "POST", "/clear", b"clear=1",
            "application/x-www-form-urlencoded",
        )
        self.assertEqual(status, "200 OK")
        release.set()
        request_thread.join(3)
        self.assertFalse(request_thread.is_alive())
        self.assertEqual(len(response), 1)
        self.assertEqual(self.manager.published, [])

    def test_status_poll_does_not_extend_session_idle_deadline(self):
        now = [0.0]
        manager = _FakeOCRManager()
        app = create_expense_report_app(
            ocr_processing_manager=manager,
            idle_timeout_seconds=10,
            clock=lambda: now[0],
        )
        body, content_type = _zip_upload()
        _request(app, "POST", "/upload", body, content_type)
        _request(app, "POST", "/assign-note", urlencode({"note_document_id": "doc-001"}).encode(),
                 "application/x-www-form-urlencoded")
        job_id, generation, _ = manager.started[0]
        now[0] = 9
        _request(app, path=f"/ocr/jobs/{job_id}")
        now[0] = 11
        status, _, _ = _request(app, path=f"/ocr/jobs/{job_id}")
        self.assertEqual(status, "404 Not Found")
        self.assertIn(generation, manager.cancelled)

    def test_app_close_closes_optional_manager(self):
        _, generation, _ = self.manager.started[0] if self.manager.started else (None, None, None)
        if generation is None:
            self._assign_note()
            generation = self.manager.started[0][1]
        self.app.close()
        self.assertTrue(self.manager.closed)
        self.assertIn(generation, self.manager.cancelled)
        status, _, _ = _request(self.app)
        self.assertEqual(status, "503 Service Unavailable")


if __name__ == "__main__":
    unittest.main()
