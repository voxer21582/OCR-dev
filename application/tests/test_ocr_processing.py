from __future__ import annotations

import math
import hashlib
import os
import threading
import time
import unittest
from unittest.mock import patch

from alfa_document_intelligence import ocr_processing as manager_module
from alfa_document_intelligence.ocr_processing import (
    OCRJobProtocolError,
    OCRProcessLimits,
    decode_frame,
    encode_frame,
)


def valid_limits() -> dict[str, int | float]:
    return {
        "job_timeout_seconds": 60.0,
        "cleanup_grace_seconds": 2.0,
        # Leave room for CPython and the test module to initialize on POSIX
        # before the worker reaches the engine; production uses the same cap.
        "child_memory_limit_bytes": 2 * 1024 * 1024 * 1024 - 1,
        "max_input_frame_bytes": 1024 * 1024,
        "max_status_frame_bytes": 4096,
        "max_result_frame_bytes": 1024 * 1024,
        "max_aggregate_result_bytes": 4 * 1024 * 1024,
        "max_page_output_bytes": 128 * 1024,
        "max_ipc_messages": 1000,
    }


def valid_status() -> dict[str, object]:
    return {
        "version": 1,
        "kind": "status",
        "payload": {
            "job_id": "job-synthetic-1",
            "phase": "processing",
            "completed_documents": 0,
            "total_documents": 1,
            "current_page": 1,
            "total_pages": 2,
            "error_code": None,
        },
    }


def valid_input() -> dict[str, object]:
    return {
        "version": 1,
        "kind": "input",
        "payload": {
            "job_id": "job-synthetic-1",
            "generation_id": "generation-synthetic-1",
            "documents": [{"id": "document-synthetic-1", "source_bytes_b64": "c3ludGhldGlj"}],
            "decode_limits": {"max_pages": 2},
            "catalog": None,
        },
    }


def synthetic_factory_raises():
    raise RuntimeError("synthetic factory failure")


def synthetic_factory_sleeps():
    time.sleep(30)
    raise RuntimeError("synthetic timeout sentinel")


class OCRProcessLimitsTests(unittest.TestCase):
    def test_requires_explicit_finite_positive_bounds(self):
        limits = OCRProcessLimits(**valid_limits())
        self.assertEqual(limits.job_timeout_seconds, 60.0)
        self.assertEqual(limits.max_ipc_messages, 1000)

    def test_rejects_zero_negative_bool_and_nonfinite_values(self):
        for key in valid_limits():
            invalid_values: tuple[object, ...]
            if key.endswith("seconds"):
                invalid_values = (0, -1, True, math.nan, math.inf, -math.inf)
            else:
                invalid_values = (0, -1, True, 1.5, math.nan, math.inf)
            for value in invalid_values:
                with self.subTest(key=key, value=value):
                    params = valid_limits()
                    params[key] = value  # type: ignore[assignment]
                    with self.assertRaises((TypeError, ValueError)):
                        OCRProcessLimits(**params)  # type: ignore[arg-type]

    def test_requires_every_limit_without_implicit_defaults(self):
        for key in valid_limits():
            with self.subTest(missing=key):
                params = valid_limits()
                params.pop(key)
                with self.assertRaises(TypeError):
                    OCRProcessLimits(**params)  # type: ignore[arg-type]

    def test_rejects_unsupported_platform(self):
        with patch("alfa_document_intelligence.ocr_processing.os.name", "unsupported"):
            with self.assertRaisesRegex(ValueError, "unsupported platform"):
                OCRProcessLimits(**valid_limits())


class OCRFrameProtocolTests(unittest.TestCase):
    def test_worker_kind_peek_accepts_only_deterministic_kind_prefix(self):
        from alfa_document_intelligence.ocr_processing import _peek_canonical_kind

        self.assertEqual(_peek_canonical_kind(encode_frame(valid_status(), max_bytes=4096)), "status")
        with self.assertRaises(OCRJobProtocolError):
            _peek_canonical_kind(b'{"version":1,"kind":"status","payload":{}}')

    def test_status_frame_round_trips_as_deterministic_utf8_json(self):
        message = valid_status()
        frame = encode_frame(message, max_bytes=4096)
        self.assertIn(b'"version":1', frame)
        self.assertEqual(decode_frame(frame, max_bytes=4096, expected_kind="status"), message)
        self.assertEqual(encode_frame(message, max_bytes=4096), frame)

    def test_rejects_frame_over_byte_limit_before_parsing(self):
        frame = encode_frame(valid_status(), max_bytes=4096)
        with self.assertRaises(OCRJobProtocolError):
            decode_frame(frame, max_bytes=len(frame) - 1, expected_kind="status")

    def test_rejects_malformed_utf8_and_json(self):
        for frame in (b"\xff", b"{", b"null"):
            with self.subTest(frame=frame), self.assertRaises(OCRJobProtocolError):
                decode_frame(frame, max_bytes=4096, expected_kind="status")

    def test_rejects_unknown_keys_duplicate_keys_wrong_version_and_wrong_kind(self):
        bad_frames = (
            b'{"version":1,"kind":"status","payload":{},"extra":0}',
            b'{"version":1,"version":1,"kind":"status","payload":{}}',
            b'{"version":2,"kind":"status","payload":{}}',
            b'{"version":1,"kind":"result","payload":{}}',
            b'{"version":1,"kind":"status","payload":{"private":1}}',
        )
        for frame in bad_frames:
            with self.subTest(frame=frame), self.assertRaises(OCRJobProtocolError):
                decode_frame(frame, max_bytes=4096, expected_kind="status")

    def test_rejects_invalid_field_types_and_excessive_depth_or_collection_size(self):
        invalid_status_payload = {
            "job_id": "j", "phase": "processing", "completed_documents": True,
            "total_documents": 1, "current_page": 1, "total_pages": 1, "error_code": None,
        }
        with self.assertRaises(OCRJobProtocolError):
            encode_frame(
                {"version": 1, "kind": "status", "payload": invalid_status_payload},
                max_bytes=4096,
            )

        deep_value: object = 0
        for _ in range(20):
            deep_value = [deep_value]
        payloads = (
            {"documents": [deep_value]},
            {"documents": list(range(4097))},
            {"documents": [{"text": "x" * (36 * 1024 * 1024 + 1)}]},
        )
        for replacement in payloads:
            message = valid_input()
            payload = dict(message["payload"])  # type: ignore[arg-type]
            payload["documents"] = replacement["documents"]
            message["payload"] = payload
            with self.subTest(documents_type=type(payload["documents"]).__name__), self.assertRaises(OCRJobProtocolError):
                encode_frame(message, max_bytes=16 * 1024 * 1024)

    def test_decoder_rejects_structurally_excessive_nested_payload(self):
        message = valid_input()
        payload = dict(message["payload"])  # type: ignore[arg-type]
        nested: object = 0
        for _ in range(20):
            nested = [nested]
        payload["documents"] = [{"data": nested}]
        message["payload"] = payload
        import json
        frame = json.dumps(message, separators=(",", ":")).encode("utf-8")
        with self.assertRaises(OCRJobProtocolError):
            decode_frame(frame, max_bytes=4096, expected_kind="input")

    def test_encoding_rejects_non_json_values_and_output_over_byte_limit(self):
        with self.assertRaises(OCRJobProtocolError):
            encode_frame({"version": 1, "kind": "status", "payload": {"x": object()}}, max_bytes=4096)
        with self.assertRaises(OCRJobProtocolError):
            encode_frame(valid_status(), max_bytes=10)

    def test_encoding_preflights_aggregate_size_before_full_serialization(self):
        message = valid_input()
        payload = dict(message["payload"])  # type: ignore[arg-type]
        payload["documents"] = ["x" * (8 * 1024 * 1024)] * 3
        message["payload"] = payload
        with patch("alfa_document_intelligence.ocr_processing.json.dumps") as dumps:
            with self.assertRaises(OCRJobProtocolError):
                encode_frame(message, max_bytes=16 * 1024 * 1024)
            dumps.assert_not_called()


class OCRWorkerBootstrapTests(unittest.TestCase):
    def test_factory_reference_must_be_a_trusted_importable_callable(self):
        from alfa_document_intelligence.ocr_processing import OCRProcessingManager

        for invalid in (
            "", "factory", ":call", "tests.test_ocr_processing:",
            "tests.test_ocr_processing:local.<locals>.factory",
            "__main__:factory", "tests.test_ocr_processing:factory()",
        ):
            with self.subTest(reference=invalid), self.assertRaises(ValueError):
                OCRProcessingManager(invalid, OCRProcessLimits(**valid_limits()))

    def test_job_status_is_immutable_and_contains_aggregate_values_only(self):
        from dataclasses import FrozenInstanceError
        from alfa_document_intelligence.ocr_processing import OCRJobStatus

        status = OCRJobStatus(
            "job-synthetic", "generation-synthetic", "processing", 0, 1, 1, 2, None,
        )
        self.assertEqual((status.completed_documents, status.current_page, status.total_pages), (0, 1, 2))
        self.assertFalse(hasattr(status, "filename"))
        with self.assertRaises(FrozenInstanceError):
            status.phase = "succeeded"  # type: ignore[misc]

    def test_spawned_child_is_attached_before_trusted_factory_import_and_fails_closed(self):
        from io import BytesIO
        from alfa_document_intelligence.document_decoder import DecodeLimits
        from alfa_document_intelligence.expense_reports import create_expense_report_intake_session
        from alfa_document_intelligence.ingestion import materialize_stream_batch
        from alfa_document_intelligence.ocr_processing import OCRProcessingManager

        intake = create_expense_report_intake_session(
            materialize_stream_batch([("synthetic.pdf", BytesIO(b"%PDF-1.7\nsynthetic note"))]),
            expense_report_id="synthetic-report-1", note_document_id="synthetic-doc-1",
            document_ids=["synthetic-doc-1"], session_id="synthetic-session-1",
            received_at="2026-11-11T10:00:00+00:00",
        )
        limits = OCRProcessLimits(**valid_limits())
        manager = OCRProcessingManager(
            "tests.test_ocr_processing:synthetic_factory_raises", limits,
        )
        try:
            job_id = manager.start("synthetic-generation", intake, decode_limits=DecodeLimits())
            deadline = time.monotonic() + 10
            status = manager.snapshot(job_id)
            while status is not None and status.phase not in {"succeeded", "failed", "cancelled"}:
                if time.monotonic() >= deadline:
                    self.fail("synthetic child did not reach a terminal state")
                time.sleep(0.02)
                status = manager.snapshot(job_id)
            self.assertIsNotNone(status)
            self.assertEqual(status.phase, "failed")
            self.assertEqual(status.error_code, "worker_failed")
            self.assertIsNone(manager.result_frame("synthetic-generation", job_id))
            self.assertFalse(manager._job.process.is_alive())
        finally:
            manager.close()

    def test_deadline_terminates_worker_without_status_polling(self):
        from io import BytesIO
        from alfa_document_intelligence.document_decoder import DecodeLimits
        from alfa_document_intelligence.expense_reports import create_expense_report_intake_session
        from alfa_document_intelligence.ingestion import materialize_stream_batch
        from alfa_document_intelligence.ocr_processing import OCRProcessingManager

        intake = create_expense_report_intake_session(
            materialize_stream_batch([("synthetic.pdf", BytesIO(b"%PDF-1.7\nsynthetic note"))]),
            expense_report_id="synthetic-report-2", note_document_id="synthetic-doc-2",
            document_ids=["synthetic-doc-2"], session_id="synthetic-session-2",
            received_at="2026-11-11T10:00:00+00:00",
        )
        values = valid_limits()
        values["job_timeout_seconds"] = 0.5
        values["cleanup_grace_seconds"] = 0.2
        manager = OCRProcessingManager(
            "tests.test_ocr_processing:synthetic_factory_sleeps", OCRProcessLimits(**values),
        )
        try:
            job_id = manager.start("synthetic-generation-2", intake, decode_limits=DecodeLimits())
            time.sleep(0.9)  # No snapshot/poll call occurs during the deadline window.
            status = manager.snapshot(job_id)
            self.assertEqual(status.phase, "failed")
            self.assertEqual(status.error_code, "job_timeout")
            self.assertIsNone(manager.result_frame("synthetic-generation-2", job_id))
            self.assertFalse(manager._job.process.is_alive())
            self.assertTrue(manager._job.input_sender.closed)
            self.assertTrue(manager._job.output_receiver.closed)
        finally:
            manager.close()

    def test_cancellation_reaps_child_and_invalidates_generation(self):
        from io import BytesIO
        from alfa_document_intelligence.document_decoder import DecodeLimits
        from alfa_document_intelligence.expense_reports import create_expense_report_intake_session
        from alfa_document_intelligence.ingestion import materialize_stream_batch
        from alfa_document_intelligence.ocr_processing import OCRProcessingManager

        intake = create_expense_report_intake_session(
            materialize_stream_batch([("synthetic.pdf", BytesIO(b"%PDF-1.7\nsynthetic note"))]),
            expense_report_id="synthetic-report-3", note_document_id="synthetic-doc-3",
            document_ids=["synthetic-doc-3"], session_id="synthetic-session-3",
            received_at="2026-11-11T10:00:00+00:00",
        )
        manager = OCRProcessingManager(
            "tests.test_ocr_processing:synthetic_factory_sleeps",
            OCRProcessLimits(**valid_limits()),
        )
        try:
            job_id = manager.start("synthetic-generation-3", intake, decode_limits=DecodeLimits())
            manager.mark_cancelled("synthetic-generation-3")
            deadline = time.monotonic() + 5
            status = manager.snapshot(job_id)
            while status is not None and status.phase not in {"succeeded", "failed", "cancelled"}:
                if time.monotonic() >= deadline:
                    self.fail("cancelled child did not reach a terminal state")
                time.sleep(0.02)
                status = manager.snapshot(job_id)
            self.assertEqual(status.phase, "cancelled")
            self.assertIsNone(manager.result_frame("synthetic-generation-3", job_id))
            self.assertFalse(manager._job.process.is_alive())
            self.assertTrue(manager._job.input_sender.closed)
            self.assertTrue(manager._job.output_receiver.closed)
        finally:
            manager.close()

    def test_result_publication_is_generation_bound_and_one_shot(self):
        from alfa_document_intelligence.ocr_processing import OCRJobStatus, OCRProcessingManager

        manager = OCRProcessingManager(
            "tests.test_ocr_processing:synthetic_factory_raises",
            OCRProcessLimits(**valid_limits()),
        )
        result = b"synthetic complete result frame"
        digest = hashlib.sha256(result).hexdigest()
        manager._job = manager_module._ManagedJob(
            "job-synthetic", "generation-synthetic",
            OCRJobStatus("job-synthetic", "generation-synthetic", "succeeded", 1, 1, 1, 1, None),
            b"", time.monotonic() + 10, threading.Event(), result=result,
        )
        try:
            self.assertIsNone(manager.result_frame("stale-generation", "job-synthetic"))
            self.assertFalse(manager.publish_if_current("generation-synthetic", "job-synthetic", "0" * 64))
            self.assertEqual(manager.result_frame("generation-synthetic", "job-synthetic"), result)
            self.assertTrue(manager.publish_if_current("generation-synthetic", "job-synthetic", digest))
            self.assertFalse(manager.publish_if_current("generation-synthetic", "job-synthetic", digest))
            self.assertIsNone(manager.result_frame("generation-synthetic", "job-synthetic"))
        finally:
            manager.close()

    def test_session_invalidation_discards_completed_unpublished_result(self):
        from alfa_document_intelligence.ocr_processing import OCRJobStatus, OCRProcessingManager

        manager = OCRProcessingManager(
            "tests.test_ocr_processing:synthetic_factory_raises",
            OCRProcessLimits(**valid_limits()),
        )
        result = b"synthetic private result frame"
        manager._job = manager_module._ManagedJob(
            "job-invalidate", "generation-invalidate",
            OCRJobStatus("job-invalidate", "generation-invalidate", "succeeded", 1, 1, 1, 1, None),
            b"", time.monotonic() + 10, threading.Event(), result=result,
        )
        try:
            manager.mark_cancelled("generation-invalidate")
            self.assertIsNone(manager.result_frame("generation-invalidate", "job-invalidate"))
            self.assertEqual(manager.snapshot("job-invalidate").phase, "cancelled")
            self.assertFalse(manager.publish_if_current(
                "generation-invalidate", "job-invalidate", hashlib.sha256(result).hexdigest(),
            ))
        finally:
            manager.close()

    def test_windows_job_attachment_failure_reaps_gated_child(self):
        if os.name != "nt":
            self.skipTest("Windows Job Object attachment is platform-specific")
        from io import BytesIO
        from alfa_document_intelligence.document_decoder import DecodeLimits
        from alfa_document_intelligence.expense_reports import create_expense_report_intake_session
        from alfa_document_intelligence.ingestion import materialize_stream_batch
        from alfa_document_intelligence.ocr_processing import OCRProcessingManager

        intake = create_expense_report_intake_session(
            materialize_stream_batch([("synthetic.pdf", BytesIO(b"%PDF-1.7\nsynthetic note"))]),
            expense_report_id="synthetic-report-4", note_document_id="synthetic-doc-4",
            document_ids=["synthetic-doc-4"], session_id="synthetic-session-4",
            received_at="2026-11-11T10:00:00+00:00",
        )
        manager = OCRProcessingManager(
            "tests.test_ocr_processing:synthetic_factory_raises",
            OCRProcessLimits(**valid_limits()),
        )
        with patch(
            "alfa_document_intelligence.isolated_decoder._attach_windows_job",
            side_effect=OSError("synthetic attachment refusal"),
        ):
            with self.assertRaisesRegex(RuntimeError, "safely started"):
                manager.start("synthetic-generation-4", intake, decode_limits=DecodeLimits())
        try:
            self.assertEqual(manager._job.status.phase, "failed")
            self.assertEqual(manager._job.status.error_code, "worker_start_failed")
            self.assertFalse(manager._job.process.is_alive())
            self.assertTrue(manager._job.input_sender.closed)
            self.assertTrue(manager._job.output_receiver.closed)
        finally:
            manager.close()

    def test_input_documents_are_processed_sequentially_with_in_process_decoder(self):
        from dataclasses import asdict
        from io import BytesIO
        from alfa_document_intelligence.document_decoder import DecodeLimits
        from alfa_document_intelligence.expense_reports import create_expense_report_intake_session
        from alfa_document_intelligence.ingestion import materialize_stream_batch
        from alfa_document_intelligence.ocr_adapter import run_ocr
        from alfa_document_intelligence.ocr_processing import _process_input_documents
        from alfa_document_intelligence.contracts import validate_document_record
        from test_document_processing import FakeEngine, _decoder
        from alfa_document_intelligence.paddle_adapter import PaddleOCRAdapter
        import base64

        first_bytes = b"%PDF-1.7\nsynthetic note one"
        second_bytes = b"%PDF-1.7\nsynthetic note two"
        intake = create_expense_report_intake_session(
            materialize_stream_batch([
                ("synthetic-one.pdf", BytesIO(first_bytes)),
                ("synthetic-two.pdf", BytesIO(second_bytes)),
            ]),
            expense_report_id="synthetic-report-5", note_document_id="synthetic-doc-1",
            document_ids=["synthetic-doc-1", "synthetic-doc-2"],
            session_id="synthetic-session-5", received_at="2026-11-11T10:00:00+00:00",
        )
        limits = OCRProcessLimits(**valid_limits())
        decode_limits = DecodeLimits()
        payload = {
            "job_id": "job-synthetic-5", "generation_id": "generation-synthetic-5",
            "documents": [
                {
                    "document_id": document_id,
                    "record": record,
                    "source_bytes_b64": base64.b64encode(intake.source_bytes[document_id]).decode("ascii"),
                }
                for document_id, record in intake.documents.items()
            ],
            "decode_limits": asdict(decode_limits), "catalog": None,
        }
        adapter = PaddleOCRAdapter(FakeEngine(), "3.7.0", image_decoder=lambda _page: None)
        progress = []
        result = _process_input_documents(
            payload, adapter, limits, decoder=_decoder(),
            report_progress=lambda *values: progress.append(values),
        )
        self.assertEqual(list(result), ["synthetic-doc-1", "synthetic-doc-2"])
        self.assertEqual(result["synthetic-doc-1"]["processing"]["ocr"]["status"], "completed")
        self.assertEqual(result["synthetic-doc-2"]["processing"]["ocr"]["status"], "completed")
        self.assertEqual(progress[-1], (
            "job-synthetic-5", "generation-synthetic-5", 2, 2, 2, 2,
        ))
        self.assertTrue(all(not validate_document_record(record) for record in result.values()))


if __name__ == "__main__":
    unittest.main()
