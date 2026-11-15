"""Sequential, resumable OCR orchestration for one encrypted local case."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import threading
import time
import uuid
from typing import Any, Iterable, Iterator

from .expense_reports import ExpenseReportIntakeSession
from .ocr_processing import (
    OCRCaseBudget,
    OCRJobProtocolError,
    OCRProcessLimits,
    decode_frame,
    encode_frame,
)

_MAX_CASE_PAGES = 500
_MAX_CASE_PIXELS = 2_000_000_000
_MAX_CASE_RESULT_BYTES = 256 * 1024 * 1024
_MAX_GROUP_DOCUMENTS = 20
_POLL_INTERVAL_SECONDS = 0.05
_SAFE_ERROR_CODES = frozenset({
    "case_page_limit", "case_pixel_limit", "job_timeout", "page_output_limit",
    "worker_failed", "worker_protocol_failed", "worker_start_failed",
    "case_changed", "case_missing", "worker_result_missing", "worker_result_invalid",
    "case_result_limit", "case_input_limit", "case_state_invalid", "case_cancelled",
})


@dataclass(frozen=True)
class ExpenseCaseJobStatus:
    """Safe aggregate job state; never contains a filename or document value."""

    job_id: str
    case_id: str
    phase: str
    completed_documents: int
    total_documents: int
    completed_pages: int
    error_code: str | None


@dataclass
class _CaseJob:
    job_id: str
    case_id: str
    generation_id: str
    status: ExpenseCaseJobStatus
    cancelled: threading.Event
    thread: threading.Thread | None = None
    worker_job_id: str | None = None


def _input_payload(
    documents: list[tuple[str, dict[str, Any], bytes]],
    *,
    job_id: str,
    generation_id: str,
    decode_limits: Any,
    case_budget: OCRCaseBudget,
    custom_family_catalog: Any = None,
) -> dict[str, Any]:
    import base64

    catalog_payload = None
    if custom_family_catalog is not None:
        catalog_json = custom_family_catalog.as_json()
        catalog_payload = {
            "json": catalog_json,
            "version": custom_family_catalog.version,
            "sha256": custom_family_catalog.sha256,
        }
    return {
        "version": 1,
        "kind": "input",
        "payload": {
            "job_id": job_id,
            "generation_id": generation_id,
            "documents": [
                {
                    "document_id": document_id,
                    "record": record,
                    "source_bytes_b64": base64.b64encode(source).decode("ascii"),
                }
                for document_id, record, source in documents
            ],
            "decode_limits": asdict(decode_limits),
            "catalog": catalog_payload,
            "case_budget": asdict(case_budget),
        },
    }


def _source_set_digest(case: dict[str, Any]) -> str:
    payload = {
        "case_id": case["case_id"],
        "statement": {
            "document_id": case["statement_document_id"],
            "source_sha256": case["statement_sha256"],
        },
        "included_attachments": [
            {"document_id": item["document_id"], "source_sha256": item["source_sha256"]}
            for item in case.get("attachments", []) if item.get("included") is True
        ],
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _group_case_documents(
    documents: Iterable[tuple[str, dict[str, Any], bytes]],
    *,
    generation_id: str,
    decode_limits: Any,
    case_budget: OCRCaseBudget,
    max_input_frame_bytes: int,
    custom_family_catalog: Any = None,
) -> Iterator[list[tuple[str, dict[str, Any], bytes]]]:
    """Yield groups based on the exact encoded frame, retaining at most one lookahead."""
    iterator = iter(documents)
    pending = None
    while True:
        group: list[tuple[str, dict[str, Any], bytes]] = []
        while len(group) < _MAX_GROUP_DOCUMENTS:
            item = pending
            pending = None
            if item is None:
                try:
                    item = next(iterator)
                except StopIteration:
                    break
            candidate = [*group, item]
            try:
                encode_frame(_input_payload(
                    candidate,
                    job_id="0" * 32,
                    generation_id=generation_id,
                    decode_limits=decode_limits,
                    case_budget=case_budget,
                    custom_family_catalog=custom_family_catalog,
                ), max_bytes=max_input_frame_bytes)
            except OCRJobProtocolError:
                if not group:
                    raise ValueError("case_input_limit") from None
                pending = item
                break
            group = candidate
        if not group:
            return
        yield group


class ExpenseCaseProcessingManager:
    """Run bounded sequential worker chunks and commit each only when complete."""

    def __init__(
        self,
        store,
        worker_manager,
        limits: OCRProcessLimits,
        decode_limits,
        *,
        custom_family_catalog=None,
        poll_interval: float = _POLL_INTERVAL_SECONDS,
        close_worker_on_close: bool = True,
    ) -> None:
        from .document_decoder import DecodeLimits

        if not isinstance(limits, OCRProcessLimits) or not isinstance(decode_limits, DecodeLimits):
            raise ValueError("explicit OCR and decode limits are required")
        if not isinstance(poll_interval, (int, float)) or isinstance(poll_interval, bool) or poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
        self._store = store
        self._worker = worker_manager
        self._limits = limits
        self._decode_limits = decode_limits
        self._catalog = custom_family_catalog
        self._poll_interval = float(poll_interval)
        self._close_worker_on_close = close_worker_on_close
        self._lock = threading.RLock()
        self._jobs: dict[str, _CaseJob] = {}
        self._active_job_id: str | None = None
        self._closed = False

    def start(self, case_id: str, case_revision: str) -> str:
        if not isinstance(case_id, str) or not case_id or not isinstance(case_revision, str):
            raise ValueError("case identity and revision are required")
        case = self._store.get_case(case_id)
        if case is None:
            raise ValueError("case_missing")
        if case.get("case_revision") != case_revision:
            raise ValueError("case_changed")
        generation_id = uuid.uuid4().hex
        with self._lock:
            if self._closed:
                raise RuntimeError("case processing manager is closed")
            if self._active_job_id is not None:
                active = self._jobs[self._active_job_id]
                if active.status.phase not in {"succeeded", "failed", "cancelled"}:
                    raise RuntimeError("a case OCR job is already active")
            processing = case.setdefault("processing", {})
            cursor = processing.get("cursor")
            if cursor is not None and (not isinstance(cursor, str) or not cursor.isdecimal()):
                raise ValueError("case_state_invalid")
            processing["state"] = "queued"
            processing["run_id"] = generation_id
            processing["source_set_sha256"] = _source_set_digest(case)
            processing.pop("error_code", None)
            if cursor is None:
                processing.update({"decoded_pages": 0, "decoded_pixels": 0, "result_bytes": 0})
            queued = self._store.save_case(case, expected_revision=case_revision)
            job_id = uuid.uuid4().hex
            case_job = _CaseJob(
                job_id,
                case_id,
                generation_id,
                ExpenseCaseJobStatus(
                    job_id, case_id, "queued", int(cursor or "0"),
                    1 + sum(bool(item.get("included")) for item in queued.get("attachments", [])),
                    int(queued.get("processing", {}).get("decoded_pages", 0)), None,
                ),
                threading.Event(),
            )
            worker = threading.Thread(
                target=self._run, args=(case_job, queued),
                name=f"expense-case-{job_id[:8]}", daemon=True,
            )
            case_job.thread = worker
            self._jobs[job_id] = case_job
            self._active_job_id = job_id
            try:
                worker.start()
            except BaseException:
                self._set_failed(
                    case_job, queued, "worker_start_failed",
                    expected_revision=queued["case_revision"],
                )
                raise RuntimeError("case OCR could not be started") from None
        return job_id

    def snapshot(self, job_id: str) -> ExpenseCaseJobStatus | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.status if job is not None else None

    def cancel(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.status.phase in {"succeeded", "failed", "cancelled"}:
                return
            job.cancelled.set()
            job.status = ExpenseCaseJobStatus(
                job.job_id, job.case_id, "cancelling", job.status.completed_documents,
                job.status.total_documents, job.status.completed_pages, None,
            )
            if job.worker_job_id is not None:
                self._worker.mark_cancelled(job.generation_id)

    def close(self) -> None:
        with self._lock:
            self._closed = True
            jobs = list(self._jobs.values())
        for job in jobs:
            self.cancel(job.job_id)
        for job in jobs:
            if job.thread is not None:
                job.thread.join(float(self._limits.cleanup_grace_seconds) + 2.0)
        if self._close_worker_on_close:
            self._worker.close()

    def _run(self, job: _CaseJob, case: dict[str, Any]) -> None:
        expected_revision = case.get("case_revision")
        try:
            case.setdefault("processing", {})["state"] = "processing"
            case = self._store.save_case(case, expected_revision=expected_revision)
            expected_revision = case["case_revision"]
            processing = case.setdefault("processing", {})
            cursor_raw = processing.get("cursor")
            cursor = int(cursor_raw) if cursor_raw is not None else 0
            page_count = int(processing.get("decoded_pages", 0))
            pixel_count = int(processing.get("decoded_pixels", 0))
            result_bytes = int(processing.get("result_bytes", 0))
            document_ids = [case["statement_document_id"]] + [
                item["document_id"] for item in case.get("attachments", []) if item.get("included")
            ]
            if cursor > len(document_ids):
                raise ValueError("case_state_invalid")
            if job.status.completed_documents != cursor:
                self._set_status(job, phase="processing", completed_documents=cursor)
            expected_revision = case["case_revision"]
            iterator = self._iter_case_documents(document_ids[cursor:])
            next_index = cursor
            remaining_pages = _MAX_CASE_PAGES - page_count
            remaining_pixels = _MAX_CASE_PIXELS - pixel_count
            if cursor < len(document_ids) and (remaining_pages <= 0 or remaining_pixels <= 0):
                raise ValueError("case_page_limit" if remaining_pages <= 0 else "case_pixel_limit")
            case_budget = OCRCaseBudget(max(1, remaining_pages), max(1, remaining_pixels))
            for group in _group_case_documents(
                iterator,
                generation_id=job.generation_id,
                decode_limits=self._decode_limits,
                case_budget=case_budget,
                max_input_frame_bytes=self._limits.max_input_frame_bytes,
                custom_family_catalog=self._catalog,
            ):
                if job.cancelled.is_set():
                    self._set_cancelled(job, expected_revision)
                    return
                group_start = next_index
                next_index += len(group)
                if remaining_pages <= 0 or remaining_pixels <= 0:
                    raise ValueError("case_page_limit" if remaining_pages <= 0 else "case_pixel_limit")
                intake = ExpenseReportIntakeSession(
                    {},
                    {document_id: record for document_id, record, _ in group},
                    {document_id: source for document_id, _, source in group},
                )
                case_budget = OCRCaseBudget(remaining_pages, remaining_pixels)
                try:
                    worker_job_id = self._worker.start(
                        job.generation_id, intake, decode_limits=self._decode_limits,
                        custom_family_catalog=self._catalog, case_budget=case_budget,
                    )
                except BaseException:
                    raise ValueError("worker_start_failed") from None
                job.worker_job_id = worker_job_id
                status = self._wait_worker(job, worker_job_id)
                if job.cancelled.is_set() or status.phase == "cancelled":
                    self._set_cancelled(job, expected_revision)
                    return
                if status.phase != "succeeded":
                    code = status.error_code if status.error_code in _SAFE_ERROR_CODES else "worker_failed"
                    raise ValueError(code)
                frame = self._worker.result_frame(job.generation_id, worker_job_id)
                if not isinstance(frame, bytes):
                    raise ValueError("worker_result_missing")
                try:
                    envelope = decode_frame(
                        frame,
                        max_bytes=min(self._limits.max_result_frame_bytes, self._limits.max_aggregate_result_bytes),
                        expected_kind="result",
                    )
                    payload = envelope["payload"]
                    if payload.get("job_id") != worker_job_id or payload.get("generation_id") != job.generation_id:
                        raise ValueError("worker_result_invalid")
                    records = payload.get("documents")
                    if not isinstance(records, dict) or set(records) != {item[0] for item in group}:
                        raise ValueError("worker_result_invalid")
                    updated_records = self._validate_group_results(group, records)
                    group_pages, group_pixels, group_bytes = self._measure_results(updated_records)
                except (OCRJobProtocolError, KeyError, TypeError, ValueError):
                    raise ValueError("worker_result_invalid") from None
                if page_count + group_pages > _MAX_CASE_PAGES:
                    raise ValueError("case_page_limit")
                if pixel_count + group_pixels > _MAX_CASE_PIXELS:
                    raise ValueError("case_pixel_limit")
                if result_bytes + group_bytes > _MAX_CASE_RESULT_BYTES:
                    raise ValueError("case_result_limit")
                if job.cancelled.is_set():
                    self._worker.mark_cancelled(job.generation_id)
                    self._set_cancelled(job, expected_revision)
                    return
                frame_digest = hashlib.sha256(frame).hexdigest()
                if not self._worker.publish_if_current(job.generation_id, worker_job_id, frame_digest):
                    if job.cancelled.is_set():
                        self._set_cancelled(job, expected_revision)
                        return
                    raise ValueError("worker_result_invalid")
                page_count += group_pages
                pixel_count += group_pixels
                result_bytes += group_bytes
                next_case = self._store.get_case(job.case_id)
                if next_case is None or next_case["case_revision"] != expected_revision:
                    raise ValueError("case_changed")
                next_processing = next_case.setdefault("processing", {})
                next_processing.update({
                    "state": "processing", "cursor": str(next_index),
                    "decoded_pages": page_count, "decoded_pixels": pixel_count,
                    "result_bytes": result_bytes,
                })
                chunk_id = f"{job.generation_id}-{group_start}-{next_index}"
                expected_record_sha256 = {
                    document_id: self._store.record_revision_sha256(record)
                    for document_id, record, _ in group
                }
                case = self._store.commit_case_processing_chunk(
                    job.case_id, expected_revision, chunk_id, updated_records, next_case,
                    expected_record_sha256,
                )
                expected_revision = case["case_revision"]
                remaining_pages = _MAX_CASE_PAGES - page_count
                remaining_pixels = _MAX_CASE_PIXELS - pixel_count
                self._set_status(
                    job,
                    phase="processing",
                    completed_documents=next_index,
                    completed_pages=page_count,
                )
            if job.cancelled.is_set():
                self._set_cancelled(job, expected_revision)
                return
            current = self._store.get_case(job.case_id)
            if current is None or current["case_revision"] != expected_revision:
                raise ValueError("case_changed")
            current.setdefault("processing", {}).update({
                "state": "completed", "cursor": str(len(document_ids)),
                "decoded_pages": page_count, "decoded_pixels": pixel_count,
                "result_bytes": result_bytes,
            })
            self._store.save_case(current, expected_revision=expected_revision)
            self._set_status(
                job, phase="succeeded", completed_documents=len(document_ids),
                completed_pages=page_count,
            )
        except BaseException as exc:
            code = str(exc) if isinstance(exc, ValueError) and str(exc) in _SAFE_ERROR_CODES else "worker_failed"
            case = self._store.get_case(job.case_id)
            if case is not None:
                self._set_failed(job, case, code, expected_revision=expected_revision)

    def _iter_case_documents(self, document_ids: list[str]):
        for document_id in document_ids:
            stored = self._store.get(document_id)
            if stored is None:
                raise ValueError("case_missing")
            yield document_id, stored.record, stored.source_bytes

    @staticmethod
    def _validate_group_results(group, records):
        from .contracts import validate_document_record

        expected_hashes = {document_id: record["source"]["sha256"] for document_id, record, _ in group}
        result = []
        for document_id, record in records.items():
            if not isinstance(record, dict) or record.get("document_id") != document_id:
                raise ValueError("worker_result_invalid")
            if record.get("source", {}).get("sha256") != expected_hashes.get(document_id):
                raise ValueError("worker_result_invalid")
            if record.get("processing", {}).get("ocr", {}).get("status") != "completed":
                raise ValueError("worker_result_invalid")
            if validate_document_record(record):
                raise ValueError("worker_result_invalid")
            result.append(record)
        if len(result) != len(group):
            raise ValueError("worker_result_invalid")
        return result

    @staticmethod
    def _measure_results(records):
        pages = pixels = output_bytes = 0
        for record in records:
            page_records = record.get("pages")
            if not isinstance(page_records, list):
                raise ValueError("worker_result_invalid")
            for page in page_records:
                width = page.get("width_px") if isinstance(page, dict) else None
                height = page.get("height_px") if isinstance(page, dict) else None
                if (not isinstance(width, int) or isinstance(width, bool) or width <= 0
                        or not isinstance(height, int) or isinstance(height, bool) or height <= 0):
                    raise ValueError("worker_result_invalid")
                pages += 1
                pixels += width * height
            output_bytes += len(json.dumps(
                record, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"),
            ).encode("utf-8", errors="strict"))
        return pages, pixels, output_bytes

    def _wait_worker(self, case_job: _CaseJob, worker_job_id: str):
        group_documents_base = case_job.status.completed_documents
        group_pages_base = case_job.status.completed_pages
        while True:
            if case_job.cancelled.is_set():
                self._worker.mark_cancelled(case_job.generation_id)
            status = self._worker.snapshot(worker_job_id)
            if status is None:
                raise ValueError("worker_failed")
            if status.phase in {"succeeded", "failed", "cancelled"}:
                return status
            self._set_status(
                case_job,
                phase="processing",
                completed_documents=group_documents_base + status.completed_documents,
                completed_pages=group_pages_base + status.current_page,
            )
            case_job.cancelled.wait(self._poll_interval)

    def _set_status(self, job, *, phase, completed_documents=None, completed_pages=None, error_code=None):
        with self._lock:
            job.status = ExpenseCaseJobStatus(
                job.job_id, job.case_id, phase,
                job.status.completed_documents if completed_documents is None else completed_documents,
                job.status.total_documents,
                job.status.completed_pages if completed_pages is None else completed_pages,
                error_code,
            )

    def _set_failed(self, job, case, code, *, expected_revision):
        try:
            current = self._store.get_case(job.case_id)
            if current is not None and current.get("case_revision") == expected_revision:
                processing = current.setdefault("processing", {})
                processing["state"] = "failed"
                processing["error_code"] = code if code in _SAFE_ERROR_CODES else "worker_failed"
                self._store.save_case(current, expected_revision=expected_revision)
        except Exception:
            pass
        self._set_status(
            job, phase="failed", error_code=code if code in _SAFE_ERROR_CODES else "worker_failed",
        )

    def _set_cancelled(self, job, expected_revision):
        try:
            case = self._store.get_case(job.case_id)
            if case is not None and case.get("case_revision") == expected_revision:
                case.setdefault("processing", {})["state"] = "cancelled"
                case["processing"].pop("error_code", None)
                self._store.save_case(case, expected_revision=expected_revision)
        except Exception:
            pass
        self._set_status(job, phase="cancelled", error_code=None)
