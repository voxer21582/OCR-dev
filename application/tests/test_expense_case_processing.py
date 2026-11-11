"""Synthetic tests for case-wide OCR page and pixel budgets."""
from dataclasses import asdict
import base64
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from alfa_document_intelligence.document_decoder import DecodeLimits, DecodedPage
from alfa_document_intelligence.ocr_adapter import RasterPage
from alfa_document_intelligence.ocr_processing import (
    OCRCaseBudget,
    OCRJobStatus,
    OCRProcessLimits,
    _process_input_documents,
    encode_frame,
)
from alfa_document_intelligence.expense_case_processing import (
    ExpenseCaseProcessingManager,
    _group_case_documents,
    _input_payload,
)
from alfa_document_intelligence.local_document_store import LocalDocumentStore
from test_expense_case_store import SyntheticProtector, _case, _source_record
from test_document_processing import FakeEngine, _intake


def _payload(intake, budget):
    return {
        "job_id": "case-job-synthetic",
        "generation_id": "case-generation-synthetic",
        "documents": [
            {
                "document_id": document_id,
                "record": record,
                "source_bytes_b64": base64.b64encode(intake.source_bytes[document_id]).decode("ascii"),
            }
            for document_id, record in intake.documents.items()
        ],
        "decode_limits": asdict(DecodeLimits()),
        "catalog": None,
        "case_budget": budget,
    }


def _two_document_intake():
    from io import BytesIO
    from alfa_document_intelligence.expense_reports import create_expense_report_intake_session
    from alfa_document_intelligence.ingestion import materialize_stream_batch

    batch = materialize_stream_batch([
        ("statement.pdf", BytesIO(b"%PDF-1.7\nsynthetic statement")),
        ("receipt.pdf", BytesIO(b"%PDF-1.7\nsynthetic receipt")),
    ])
    return create_expense_report_intake_session(
        batch,
        expense_report_id="case-budget-report",
        note_document_id="case-budget-doc-1",
        document_ids=["case-budget-doc-1", "case-budget-doc-2"],
        session_id="case-budget-session",
        received_at="2026-11-11T10:00:00+00:00",
    )


class _CountingEngine(FakeEngine):
    def __init__(self):
        super().__init__(text="synthetic token")
        self.calls = 0

    def predict(self, image):
        self.calls += 1
        return super().predict(image)


def _decoder(page_count, width=100, height=80):
    def decode(source_bytes, media_kind, *, source_sha256, limits):
        for page in range(1, page_count + 1):
            yield DecodedPage(
                RasterPage(page, width, height, b"synthetic-rgb"), page_count,
            )
    return decode


class ExpenseCaseWorkerBudgetTests(unittest.TestCase):
    def setUp(self):
        self.intake = _two_document_intake()
        self.limits = OCRProcessLimits(
            job_timeout_seconds=30,
            cleanup_grace_seconds=1,
            child_memory_limit_bytes=128 * 1024 * 1024,
            max_input_frame_bytes=4 * 1024 * 1024,
            max_status_frame_bytes=4096,
            max_result_frame_bytes=4 * 1024 * 1024,
            max_aggregate_result_bytes=4 * 1024 * 1024,
            max_page_output_bytes=128 * 1024,
            max_ipc_messages=100,
        )

    def _run(self, *, budget, page_count=1, width=100, height=80):
        engine = _CountingEngine()
        from alfa_document_intelligence.paddle_adapter import PaddleOCRAdapter

        result = _process_input_documents(
            _payload(self.intake, budget),
            PaddleOCRAdapter(engine, "synthetic-1", image_decoder=lambda _page: None),
            self.limits,
            decoder=_decoder(page_count, width, height),
            report_progress=lambda *_args: None,
        )
        return result, engine

    def test_exact_case_page_and_pixel_limits_allow_all_pages(self):
        result, engine = self._run(budget={"max_pages": 2, "max_total_pixels": 16_000})
        self.assertEqual(len(result), 2)
        self.assertEqual(engine.calls, 2)

    def test_case_page_overflow_is_rejected_before_adapter_on_excess_page(self):
        engine = _CountingEngine()
        from alfa_document_intelligence.ocr_processing import _CaseBudgetExceeded
        from alfa_document_intelligence.paddle_adapter import PaddleOCRAdapter
        with self.assertRaises(_CaseBudgetExceeded) as raised:
            _process_input_documents(
                _payload(self.intake, {"max_pages": 1, "max_total_pixels": 16_000}),
                PaddleOCRAdapter(engine, "synthetic-1", image_decoder=lambda _page: None),
                self.limits,
                decoder=_decoder(1),
                report_progress=lambda *_args: None,
            )
        self.assertEqual(raised.exception.error_code, "case_page_limit")
        self.assertEqual(engine.calls, 1)

    def test_case_pixel_overflow_is_rejected_before_adapter_on_excess_page(self):
        engine = _CountingEngine()
        from alfa_document_intelligence.ocr_processing import _CaseBudgetExceeded
        from alfa_document_intelligence.paddle_adapter import PaddleOCRAdapter
        with self.assertRaises(_CaseBudgetExceeded) as raised:
            _process_input_documents(
                _payload(self.intake, {"max_pages": 2, "max_total_pixels": 15_999}),
                PaddleOCRAdapter(engine, "synthetic-1", image_decoder=lambda _page: None),
                self.limits,
                decoder=_decoder(1),
                report_progress=lambda *_args: None,
            )
        self.assertEqual(raised.exception.error_code, "case_pixel_limit")
        self.assertEqual(engine.calls, 1)


def _limits(max_input_frame_bytes=4 * 1024 * 1024):
    return OCRProcessLimits(
        job_timeout_seconds=30,
        cleanup_grace_seconds=1,
        child_memory_limit_bytes=128 * 1024 * 1024,
        max_input_frame_bytes=max_input_frame_bytes,
        max_status_frame_bytes=4096,
        max_result_frame_bytes=4 * 1024 * 1024,
        max_aggregate_result_bytes=4 * 1024 * 1024,
        max_page_output_bytes=128 * 1024,
        max_ipc_messages=100,
    )


class ExpenseCaseGroupingTests(unittest.TestCase):
    def test_groups_are_derived_from_exact_encoded_frame_size(self):
        intake = _two_document_intake()
        docs = [
            (document_id, record, intake.source_bytes[document_id])
            for document_id, record in intake.documents.items()
        ]
        one_size = len(encode_frame(_input_payload(
            docs[:1], job_id="0" * 32, generation_id="case-generation-synthetic",
            decode_limits=DecodeLimits(), case_budget=OCRCaseBudget(500, 2_000_000_000),
        ), max_bytes=4 * 1024 * 1024))
        together = len(encode_frame(_input_payload(
            docs, job_id="0" * 32, generation_id="case-generation-synthetic",
            decode_limits=DecodeLimits(), case_budget=OCRCaseBudget(500, 2_000_000_000),
        ), max_bytes=4 * 1024 * 1024))
        self.assertGreater(together, one_size)
        groups = list(_group_case_documents(
            iter(docs), generation_id="case-generation-synthetic",
            decode_limits=DecodeLimits(),
            case_budget=OCRCaseBudget(500, 2_000_000_000),
            max_input_frame_bytes=one_size,
        ))
        self.assertEqual([len(group) for group in groups], [1, 1])
        for group in groups:
            encoded = encode_frame(_input_payload(
                group, job_id="1" * 32, generation_id="case-generation-synthetic",
                decode_limits=DecodeLimits(), case_budget=OCRCaseBudget(500, 2_000_000_000),
            ), max_bytes=one_size)
            self.assertLessEqual(len(encoded), one_size)


class _ImmediateWorker:
    def __init__(self, limits, *, fail_on_call=None):
        self.limits = limits
        self.fail_on_call = fail_on_call
        self.calls = 0
        self.status = None
        self.frame = None
        self.generation_id = None
        self.consumed = False

    def start(self, generation_id, intake, *, decode_limits, custom_family_catalog=None, case_budget=None):
        from alfa_document_intelligence.ocr_processing import _process_input_documents
        from alfa_document_intelligence.paddle_adapter import PaddleOCRAdapter

        job_id = "worker-job-synthetic-001"
        self.calls += 1
        self.generation_id = generation_id
        self.consumed = False
        if self.calls == self.fail_on_call:
            self.status = OCRJobStatus(job_id, generation_id, "failed", 0, len(intake.documents), 0, 0, "worker_failed")
            self.frame = None
            return job_id
        payload = _input_payload(
            [
                (document_id, record, intake.source_bytes[document_id])
                for document_id, record in intake.documents.items()
            ],
            job_id=job_id,
            generation_id=generation_id,
            decode_limits=decode_limits,
            case_budget=case_budget,
            custom_family_catalog=custom_family_catalog,
        )["payload"]
        result = _process_input_documents(
            payload,
            PaddleOCRAdapter(FakeEngine(), "synthetic-1", image_decoder=lambda _page: None),
            self.limits,
            decoder=_decoder(1),
            report_progress=lambda *_args: None,
        )
        self.frame = encode_frame({
            "version": 1,
            "kind": "result",
            "payload": {"job_id": job_id, "generation_id": generation_id, "documents": result},
        }, max_bytes=min(self.limits.max_result_frame_bytes, self.limits.max_aggregate_result_bytes))
        self.status = OCRJobStatus(job_id, generation_id, "succeeded", len(result), len(result), len(result), len(result), None)
        return job_id

    def snapshot(self, job_id):
        return self.status if self.status and self.status.job_id == job_id else None

    def result_frame(self, generation_id, job_id):
        return self.frame if generation_id == self.generation_id and self.status.job_id == job_id else None

    def publish_if_current(self, generation_id, job_id, result_digest):
        if (self.consumed or generation_id != self.generation_id or self.status.job_id != job_id
                or self.frame is None or hashlib.sha256(self.frame).hexdigest() != result_digest):
            return False
        self.consumed = True
        return True

    def mark_cancelled(self, generation_id):
        if generation_id == self.generation_id and self.status is not None:
            self.status = OCRJobStatus(
                self.status.job_id, generation_id, "cancelled", self.status.completed_documents,
                self.status.total_documents, self.status.current_page, self.status.total_pages, None,
            )

    def close(self):
        pass


class _GatedWorker(_ImmediateWorker):
    def __init__(self, limits):
        super().__init__(limits)
        import threading
        self.entered = threading.Event()
        self.release = threading.Event()

    def start(self, *args, **kwargs):
        self.entered.set()
        if not self.release.wait(3):
            raise RuntimeError("synthetic gate timeout")
        return super().start(*args, **kwargs)


class _CancelOnPublishWorker(_ImmediateWorker):
    def __init__(self, limits):
        super().__init__(limits)
        import threading
        self.armed = threading.Event()

    def publish_if_current(self, generation_id, job_id, result_digest):
        if not self.armed.wait(2):
            return False
        self.manager.cancel(self.case_job_id)
        return False


class ExpenseCaseProcessingManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = LocalDocumentStore(Path(self.temp.name) / "case.sqlite3", protector=SyntheticProtector())
        statement_bytes = b"%PDF synthetic statement"
        statement = _source_record("statement-processing", statement_bytes, family="expense_report")
        self.case = self.store.create_case(_case(statement), statement, statement_bytes)
        receipt_bytes = b"%PDF synthetic receipt"
        receipt = _source_record("receipt-processing", receipt_bytes, family="fiscal_receipt")
        chunk = [{"record": receipt, "source_bytes": receipt_bytes}]
        digest = self.store.case_chunk_digest(chunk)
        self.case = self.store.append_case_chunk(
            self.case["case_id"], self.case["case_revision"], "chunk-processing",
            digest, chunk,
        )
        self.limits = _limits()

    def _run_to_terminal(self, manager, job_id):
        import time
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            status = manager.snapshot(job_id)
            if status and status.phase in {"succeeded", "failed", "cancelled"}:
                return status
            time.sleep(0.01)
        self.fail("case processing job did not reach a terminal state")

    def _limits_for_one_document_frames(self):
        from alfa_document_intelligence.document_decoder import DecodeLimits

        documents = []
        for document_id in ["statement-processing", "receipt-processing"]:
            stored = self.store.get(document_id)
            documents.append((document_id, stored.record, stored.source_bytes))
        one_frame = encode_frame(_input_payload(
            documents[:1], job_id="0" * 32, generation_id="0" * 32,
            decode_limits=DecodeLimits(), case_budget=OCRCaseBudget(500, 2_000_000_000),
        ), max_bytes=4 * 1024 * 1024)
        return _limits(max_input_frame_bytes=len(one_frame))

    def test_case_processes_and_commits_complete_group_with_evidence_page_metrics(self):
        limits = self._limits_for_one_document_frames()
        worker = _ImmediateWorker(limits)
        manager = ExpenseCaseProcessingManager(
            self.store, worker, limits, DecodeLimits(), poll_interval=0.001,
        )
        job_id = manager.start(self.case["case_id"], self.case["case_revision"])
        status = self._run_to_terminal(manager, job_id)
        self.assertEqual(status.phase, "succeeded")
        self.assertEqual(status.completed_documents, 2)
        saved = self.store.get_case(self.case["case_id"])
        self.assertEqual(saved["processing"]["state"], "completed")
        self.assertEqual(saved["processing"]["cursor"], "2")
        self.assertEqual(saved["processing"]["decoded_pages"], 2)
        self.assertEqual(saved["processing"]["decoded_pixels"], 16_000)
        self.assertEqual(len(saved["processing"]["committed_chunks"]), 2)
        self.assertRegex(saved["processing"]["source_set_sha256"], r"^[0-9a-f]{64}$")
        self.assertGreater(saved["processing"]["result_bytes"], 0)
        for document_id in ("statement-processing", "receipt-processing"):
            record = self.store.get(document_id).record
            self.assertEqual(record["processing"]["ocr"]["status"], "completed")
            self.assertEqual(record["pages"][0]["width_px"] * record["pages"][0]["height_px"], 8_000)
        statement_record = self.store.get("statement-processing").record
        self.assertEqual(statement_record["schema_version"], "0.3.0")
        self.assertTrue(statement_record["expense_lines"])
        self.assertEqual(
            statement_record["expense_lines"][0]["description"]["evidence"][0]["source_sha256"],
            statement_record["source"]["sha256"],
        )

    def test_failed_later_group_keeps_earlier_commit_and_resume_continues_at_cursor(self):
        limits = self._limits_for_one_document_frames()
        worker = _ImmediateWorker(limits, fail_on_call=2)
        manager = ExpenseCaseProcessingManager(
            self.store, worker, limits, DecodeLimits(), poll_interval=0.001,
        )
        job_id = manager.start(self.case["case_id"], self.case["case_revision"])
        status = self._run_to_terminal(manager, job_id)
        self.assertEqual(status.phase, "failed")
        failed_case = self.store.get_case(self.case["case_id"])
        self.assertEqual(failed_case["processing"]["cursor"], "1")
        self.assertEqual(failed_case["processing"]["state"], "failed")
        self.assertEqual(self.store.get("statement-processing").record["processing"]["ocr"]["status"], "completed")
        self.assertEqual(self.store.get("receipt-processing").record["processing"]["ocr"]["status"], "not_started")
        worker.fail_on_call = None
        resumed_job = manager.start(self.case["case_id"], failed_case["case_revision"])
        resumed = self._run_to_terminal(manager, resumed_job)
        self.assertEqual(resumed.phase, "succeeded")
        final_case = self.store.get_case(self.case["case_id"])
        self.assertEqual(final_case["processing"]["cursor"], "2")
        self.assertEqual(final_case["processing"]["state"], "completed")
        self.assertEqual(len(final_case["processing"]["committed_chunks"]), 2)

    def test_cancel_before_worker_result_preserves_sources_without_partial_ocr(self):
        worker = _GatedWorker(self.limits)
        manager = ExpenseCaseProcessingManager(
            self.store, worker, self.limits, DecodeLimits(), poll_interval=0.001,
        )
        job_id = manager.start(self.case["case_id"], self.case["case_revision"])
        self.assertTrue(worker.entered.wait(2))
        manager.cancel(job_id)
        worker.release.set()
        status = self._run_to_terminal(manager, job_id)
        self.assertEqual(status.phase, "cancelled")
        cancelled_case = self.store.get_case(self.case["case_id"])
        self.assertEqual(cancelled_case["processing"]["state"], "cancelled")
        self.assertIsNone(cancelled_case["processing"]["cursor"])
        self.assertEqual(cancelled_case["processing"].get("committed_chunks", []), [])
        self.assertEqual(self.store.get("statement-processing").record["processing"]["ocr"]["status"], "not_started")
        self.assertEqual(self.store.get("receipt-processing").record["processing"]["ocr"]["status"], "not_started")

    def test_cancel_racing_with_result_publication_is_reported_as_cancelled(self):
        worker = _CancelOnPublishWorker(self.limits)
        manager = ExpenseCaseProcessingManager(
            self.store, worker, self.limits, DecodeLimits(), poll_interval=0.001,
        )
        job_id = manager.start(self.case["case_id"], self.case["case_revision"])
        worker.manager = manager
        worker.case_job_id = job_id
        worker.armed.set()
        status = self._run_to_terminal(manager, job_id)
        self.assertEqual(status.phase, "cancelled")
        self.assertEqual(self.store.get_case(self.case["case_id"])["processing"]["state"], "cancelled")

    def test_resume_progress_includes_pages_from_previously_committed_groups(self):
        limits = self._limits_for_one_document_frames()
        worker = _ImmediateWorker(limits, fail_on_call=2)
        manager = ExpenseCaseProcessingManager(
            self.store, worker, limits, DecodeLimits(), poll_interval=0.001,
        )
        failed_id = manager.start(self.case["case_id"], self.case["case_revision"])
        self.assertEqual(self._run_to_terminal(manager, failed_id).phase, "failed")
        failed_case = self.store.get_case(self.case["case_id"])
        self.assertEqual(failed_case["processing"]["decoded_pages"], 1)

        gated_worker = _GatedWorker(limits)
        resumed_manager = ExpenseCaseProcessingManager(
            self.store, gated_worker, limits, DecodeLimits(), poll_interval=0.001,
        )
        resumed_id = resumed_manager.start(self.case["case_id"], failed_case["case_revision"])
        self.assertTrue(gated_worker.entered.wait(2))
        self.assertEqual(resumed_manager.snapshot(resumed_id).completed_pages, 1)
        gated_worker.release.set()
        self.assertEqual(self._run_to_terminal(resumed_manager, resumed_id).phase, "succeeded")

    def test_reopening_exactly_at_page_and_pixel_caps_does_not_reprocess_completed_case(self):
        limits = self._limits_for_one_document_frames()
        worker = _ImmediateWorker(limits)
        manager = ExpenseCaseProcessingManager(
            self.store, worker, limits, DecodeLimits(), poll_interval=0.001,
        )
        with (
            patch("alfa_document_intelligence.expense_case_processing._MAX_CASE_PAGES", 2),
            patch("alfa_document_intelligence.expense_case_processing._MAX_CASE_PIXELS", 16_000),
        ):
            first_job = manager.start(self.case["case_id"], self.case["case_revision"])
            self.assertEqual(self._run_to_terminal(manager, first_job).phase, "succeeded")
            completed = self.store.get_case(self.case["case_id"])
            self.assertEqual(completed["processing"]["decoded_pages"], 2)
            self.assertEqual(completed["processing"]["decoded_pixels"], 16_000)
            calls_after_first_run = worker.calls
            second_job = manager.start(self.case["case_id"], completed["case_revision"])
            self.assertEqual(self._run_to_terminal(manager, second_job).phase, "succeeded")
        self.assertEqual(worker.calls, calls_after_first_run)  # completed cursor skips already processed outputs

    def test_case_processing_rejects_stale_revision_without_overwriting_case(self):
        worker = _ImmediateWorker(self.limits)
        manager = ExpenseCaseProcessingManager(self.store, worker, self.limits, DecodeLimits())
        with self.assertRaisesRegex(ValueError, "case_changed"):
            manager.start(self.case["case_id"], "0" * 64)
        self.assertEqual(self.store.get_case(self.case["case_id"]), self.case)
