"""Bounded, versioned JSON protocol primitives for opt-in OCR jobs.

This module deliberately does not start a process or construct an OCR engine.
Callers must provide all resource bounds explicitly before using a future
worker manager. IPC messages contain only JSON-compatible values.
"""
from __future__ import annotations

import base64
from dataclasses import asdict, dataclass
import hashlib
import importlib
import json
import math
import multiprocessing
import os
import re
import threading
import time
import uuid
from typing import Any, Mapping


PROTOCOL_VERSION = 1
_MAX_NESTING = 16
_MAX_COLLECTION_ITEMS = 4096
_MAX_TOTAL_NODES = 100_000
_MAX_STRING_BYTES = 36 * 1024 * 1024
_MAX_KEY_BYTES = 256
_MAX_INTEGER_DIGITS = 128
_FACTORY_MODULE = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*$")
_BASE64_TEXT = re.compile(r"^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$")

_STATUS_KEYS = frozenset({
    "job_id", "phase", "completed_documents", "total_documents",
    "current_page", "total_pages", "error_code",
})
_INPUT_KEYS = frozenset({
    "job_id", "generation_id", "documents", "decode_limits", "catalog",
})
_RESULT_KEYS = frozenset({"job_id", "generation_id", "documents"})
_TERMINAL_KEYS = frozenset({"job_id", "generation_id", "phase", "error_code"})
_PAYLOAD_KEYS = {
    "status": _STATUS_KEYS,
    "input": _INPUT_KEYS,
    "result": _RESULT_KEYS,
    "terminal": _TERMINAL_KEYS,
}
_STATUS_PHASES = frozenset({
    "queued", "starting_engine", "processing", "cancelling",
    "succeeded", "failed", "cancelled",
})
_TERMINAL_PHASES = frozenset({"succeeded", "failed", "cancelled"})


class OCRJobProtocolError(ValueError):
    """A worker frame is invalid or exceeds a configured protocol bound."""


@dataclass(frozen=True)
class OCRProcessLimits:
    """Explicit per-job process and payload bounds; never supply defaults."""

    job_timeout_seconds: int | float
    cleanup_grace_seconds: int | float
    child_memory_limit_bytes: int
    max_input_frame_bytes: int
    max_status_frame_bytes: int
    max_result_frame_bytes: int
    max_aggregate_result_bytes: int
    max_page_output_bytes: int
    max_ipc_messages: int

    def __post_init__(self) -> None:
        if os.name not in {"nt", "posix"}:
            raise ValueError("unsupported platform")
        for name in ("job_timeout_seconds", "cleanup_grace_seconds"):
            value = getattr(self, name)
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or value <= 0):
                raise ValueError(f"{name} must be finite and positive")
        for name in (
            "child_memory_limit_bytes", "max_input_frame_bytes",
            "max_status_frame_bytes", "max_result_frame_bytes",
            "max_aggregate_result_bytes", "max_page_output_bytes",
            "max_ipc_messages",
        ):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")


@dataclass(frozen=True)
class OCRJobStatus:
    """Privacy-safe aggregate state for one volatile processing job."""

    job_id: str
    generation_id: str
    phase: str
    completed_documents: int
    total_documents: int
    current_page: int
    total_pages: int
    error_code: str | None


@dataclass
class _ManagedJob:
    job_id: str
    generation_id: str
    status: OCRJobStatus
    input_frame: bytes
    deadline: float
    cancelled: threading.Event
    process: Any = None
    input_sender: Any = None
    output_receiver: Any = None
    windows_job: Any = None
    close_windows_job: Any = None
    supervisor: threading.Thread | None = None
    result: bytes | None = None
    result_consumed: bool = False


class _PageOutputLimitError(RuntimeError):
    pass


class _OutputBoundAdapter:
    """Guard the adapter's per-page output before it is accepted as OCR data."""

    def __init__(self, adapter: Any, maximum_bytes: int) -> None:
        self._adapter = adapter
        self._maximum_bytes = maximum_bytes
        self.exceeded = False
        self.name = adapter.name
        self.version = adapter.version

    def recognize(self, page, languages):
        tokens = self._adapter.recognize(page, languages)
        if isinstance(tokens, (str, bytes)) or not isinstance(tokens, (list, tuple)):
            return tokens
        used = 0
        for token in tokens:
            text = getattr(token, "text", "")
            token_id = getattr(token, "token_id", "")
            if isinstance(text, str):
                used += len(text.encode("utf-8", errors="strict"))
            if isinstance(token_id, str):
                used += len(token_id.encode("utf-8", errors="strict"))
            polygon = getattr(token, "polygon", ())
            try:
                used += len(polygon) * 64
            except TypeError:
                used = self._maximum_bytes + 1
            if used > self._maximum_bytes:
                self.exceeded = True
                raise _PageOutputLimitError
        return tokens


def _process_input_documents(
    input_payload: dict[str, object],
    adapter: Any,
    limits: OCRProcessLimits,
    *,
    decoder=None,
    report_progress,
) -> dict[str, Any]:
    """Process a bounded input frame in this process with one decoder per child."""
    from .document_decoder import DecodeLimits, iter_decoded_pages
    from .document_family_catalog import load_custom_family_catalog
    from .document_processing import process_document_record
    from .contracts import validate_document_record

    if decoder is None:
        decoder = iter_decoded_pages
    decode_limits_raw = input_payload["decode_limits"]
    if not isinstance(decode_limits_raw, dict):
        raise OCRJobProtocolError("invalid decode limits")
    decode_limits = DecodeLimits(**decode_limits_raw)
    catalog = None
    catalog_raw = input_payload["catalog"]
    if catalog_raw is not None:
        if not isinstance(catalog_raw, dict) or set(catalog_raw) != {"json", "version", "sha256"}:
            raise OCRJobProtocolError("invalid catalog snapshot")
        catalog = load_custom_family_catalog(catalog_raw["json"])
        if catalog.version != catalog_raw["version"] or catalog.sha256 != catalog_raw["sha256"]:
            raise OCRJobProtocolError("catalog snapshot identity mismatch")

    documents = input_payload["documents"]
    if not isinstance(documents, list) or not documents:
        raise OCRJobProtocolError("invalid document set")
    records: dict[str, dict[str, Any]] = {}
    encoded_sources_by_id: dict[str, str] = {}
    for item in documents:
        if not isinstance(item, dict) or set(item) != {"document_id", "record", "source_bytes_b64"}:
            raise OCRJobProtocolError("invalid input document")
        document_id = item["document_id"]
        record = item["record"]
        encoded_source = item["source_bytes_b64"]
        if (not isinstance(document_id, str) or not document_id or document_id in records
                or not isinstance(record, dict) or record.get("document_id") != document_id
                or not isinstance(encoded_source, str)):
            raise OCRJobProtocolError("invalid input document")
        padding = len(encoded_source) - len(encoded_source.rstrip("="))
        decoded_size = len(encoded_source) * 3 // 4 - padding
        if (not encoded_source or not _BASE64_TEXT.fullmatch(encoded_source)
                or decoded_size <= 0 or decoded_size > decode_limits.max_source_bytes):
            raise OCRJobProtocolError("source exceeds configured limit")
        if validate_document_record(record):
            raise OCRJobProtocolError("input record violates contract")
        records[document_id] = record
        encoded_sources_by_id[document_id] = encoded_source

    total_documents = len(records)
    completed_documents = 0
    total_pages = sum((record.get("source", {}).get("page_count") or 0) for record in records.values())
    output_records: dict[str, Any] = {}
    completed_pages_total = 0
    job_id = input_payload["job_id"]
    generation_id = input_payload["generation_id"]
    for document_id, record in records.items():
        source_bytes = base64.b64decode(encoded_sources_by_id[document_id], validate=True)
        last_page = [0]
        known_pages = record.get("source", {}).get("page_count") or 0

        def on_progress(completed: int, total: int) -> None:
            nonlocal total_pages
            last_page[0] = completed
            aggregate_total = total_pages + max(0, total - known_pages)
            report_progress(
                job_id, generation_id, completed_documents, total_documents,
                completed_pages_total + completed, aggregate_total,
            )

        processed = process_document_record(
            record,
            source_bytes,
            adapter,
            decoder=decoder,
            decode_limits=decode_limits,
            custom_family_catalog=catalog,
            progress_callback=on_progress,
        )
        if isinstance(adapter, _OutputBoundAdapter) and adapter.exceeded:
            raise _PageOutputLimitError
        if processed.get("processing", {}).get("ocr", {}).get("status") != "completed":
            raise RuntimeError("document processing did not complete")
        if validate_document_record(processed):
            raise RuntimeError("processed record violates contract")
        output_records[document_id] = processed
        # Enforce the cumulative result bound after every document, so a long
        # report cannot retain unbounded candidate output before the final frame.
        encode_frame({
            "version": PROTOCOL_VERSION,
            "kind": "result",
            "payload": {
                "job_id": job_id, "generation_id": generation_id,
                "documents": output_records,
            },
        }, max_bytes=min(limits.max_result_frame_bytes, limits.max_aggregate_result_bytes))
        del source_bytes
        completed_documents += 1
        completed_pages_total += last_page[0]
        total_pages = max(total_pages, completed_pages_total)
        report_progress(
            job_id, generation_id, completed_documents, total_documents,
            completed_pages_total, total_pages,
        )
    return output_records


def _validate_factory_reference(reference: str) -> None:
    if not isinstance(reference, str) or reference.count(":") != 1:
        raise ValueError("adapter factory reference must use module:qualified_name")
    module_name, qualified_name = reference.split(":", 1)
    if (module_name == "__main__" or not _FACTORY_MODULE.fullmatch(module_name)
            or not qualified_name or "<" in qualified_name or ">" in qualified_name
            or not all(part.isidentifier() for part in qualified_name.split("."))):
        raise ValueError("adapter factory reference is not importable")


def encode_frame(message: Mapping[str, object], *, max_bytes: int) -> bytes:
    """Return deterministic UTF-8 JSON after validating its bounded schema."""
    _validate_frame_limit(max_bytes)
    try:
        if not isinstance(message, Mapping):
            raise OCRJobProtocolError("invalid worker message")
        normalized = dict(message)
        _validate_envelope(normalized, expected_kind=None)
        _preflight_encoded_size(normalized, max_bytes=max_bytes)
        encoded = json.dumps(
            normalized,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8", errors="strict")
    except OCRJobProtocolError:
        raise
    except (TypeError, ValueError, UnicodeError, OverflowError):
        raise OCRJobProtocolError("invalid worker message") from None
    if len(encoded) > max_bytes:
        raise OCRJobProtocolError("worker message exceeds byte limit")
    return encoded


def decode_frame(frame: bytes, *, max_bytes: int, expected_kind: str) -> dict[str, object]:
    """Decode one frame only after enforcing the byte cap and exact envelope."""
    _validate_frame_limit(max_bytes)
    if not isinstance(frame, bytes) or len(frame) > max_bytes:
        raise OCRJobProtocolError("worker message exceeds byte limit")
    if expected_kind not in _PAYLOAD_KEYS:
        raise OCRJobProtocolError("invalid expected message kind")

    try:
        decoded = frame.decode("utf-8", errors="strict")
        value = json.loads(
            decoded,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
        _validate_envelope(value, expected_kind=expected_kind)
    except OCRJobProtocolError:
        raise
    except (UnicodeError, json.JSONDecodeError, TypeError, ValueError, RecursionError, OverflowError):
        raise OCRJobProtocolError("invalid worker message") from None
    return value


def _validate_frame_limit(max_bytes: int) -> None:
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes <= 0:
        raise OCRJobProtocolError("frame byte limit must be a positive integer")


def _validate_envelope(value: object, *, expected_kind: str | None) -> None:
    if not isinstance(value, dict) or set(value) != {"version", "kind", "payload"}:
        raise OCRJobProtocolError("invalid worker message")
    version = value["version"]
    kind = value["kind"]
    payload = value["payload"]
    if type(version) is not int or version != PROTOCOL_VERSION:
        raise OCRJobProtocolError("invalid worker message")
    if not isinstance(kind, str) or kind not in _PAYLOAD_KEYS:
        raise OCRJobProtocolError("invalid worker message")
    if expected_kind is not None and kind != expected_kind:
        raise OCRJobProtocolError("invalid worker message")
    if not isinstance(payload, dict) or set(payload) != _PAYLOAD_KEYS[kind]:
        raise OCRJobProtocolError("invalid worker message")
    _validate_payload(kind, payload)
    _validate_json_value(value, depth=0, node_budget=[_MAX_TOTAL_NODES])


def _validate_payload(kind: str, payload: dict[str, object]) -> None:
    if kind == "status":
        if not _bounded_text(payload["job_id"], 128, allow_empty=False):
            raise OCRJobProtocolError("invalid worker message")
        if not isinstance(payload["phase"], str) or payload["phase"] not in _STATUS_PHASES:
            raise OCRJobProtocolError("invalid worker message")
        for key in ("completed_documents", "total_documents", "current_page", "total_pages"):
            if not _nonnegative_integer(payload[key]):
                raise OCRJobProtocolError("invalid worker message")
        if payload["error_code"] is not None and not _bounded_text(payload["error_code"], 64):
            raise OCRJobProtocolError("invalid worker message")
        return

    for key in ("job_id", "generation_id"):
        if not _bounded_text(payload[key], 128, allow_empty=False):
            raise OCRJobProtocolError("invalid worker message")
    if kind == "input":
        if (not isinstance(payload["documents"], list)
                or not isinstance(payload["decode_limits"], dict)
                or (payload["catalog"] is not None and not isinstance(payload["catalog"], dict))):
            raise OCRJobProtocolError("invalid worker message")
    elif kind == "result":
        if not isinstance(payload["documents"], dict):
            raise OCRJobProtocolError("invalid worker message")
    else:
        phase = payload["phase"]
        if not isinstance(phase, str) or phase not in _TERMINAL_PHASES:
            raise OCRJobProtocolError("invalid worker message")
        if payload["error_code"] is not None and not _bounded_text(payload["error_code"], 64):
            raise OCRJobProtocolError("invalid worker message")


def _preflight_encoded_size(value: object, *, max_bytes: int) -> None:
    """Count deterministic JSON bytes without materializing the whole frame."""
    remaining = max_bytes

    def text_size(text: str) -> int:
        size = 2  # quotes
        for char in text:
            codepoint = ord(char)
            if char in {'"', "\\"} or codepoint in (8, 9, 10, 12, 13):
                size += 2
            elif codepoint < 0x20:
                size += 6
            else:
                size += len(char.encode("utf-8", errors="strict"))
        return size

    def consume(amount: int) -> None:
        nonlocal remaining
        remaining -= amount
        if remaining < 0:
            raise OCRJobProtocolError("worker message exceeds byte limit")

    def visit(item: object) -> None:
        if item is None:
            consume(4)
        elif item is True:
            consume(4)
        elif item is False:
            consume(5)
        elif isinstance(item, str):
            consume(text_size(item))
        elif isinstance(item, int):
            consume(len(str(item)))
        elif isinstance(item, float):
            # JSON's float spelling is short relative to this fixed allowance;
            # exact length is verified by the final encoder.
            consume(len(json.dumps(item, allow_nan=False, separators=(",", ":"))))
        elif isinstance(item, list):
            consume(2 + max(0, len(item) - 1))
            for child in item:
                visit(child)
        elif isinstance(item, dict):
            consume(2 + max(0, len(item) - 1) + len(item))
            for key, child in item.items():
                consume(text_size(key))
                visit(child)
        else:
            raise OCRJobProtocolError("invalid worker message")

    visit(value)


def _bounded_text(value: object, maximum_bytes: int, *, allow_empty: bool = True) -> bool:
    if not isinstance(value, str) or (not allow_empty and not value):
        return False
    if len(value) > maximum_bytes:
        return False
    try:
        return len(value.encode("utf-8", errors="strict")) <= maximum_bytes
    except UnicodeError:
        return False


def _nonnegative_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _validate_json_value(value: object, *, depth: int, node_budget: list[int]) -> None:
    node_budget[0] -= 1
    if node_budget[0] < 0 or depth > _MAX_NESTING:
        raise OCRJobProtocolError("worker message exceeds structure limits")
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, str):
        if not _bounded_text(value, _MAX_STRING_BYTES):
            raise OCRJobProtocolError("worker message exceeds string limit")
        return
    if isinstance(value, int):
        if len(str(value)) > _MAX_INTEGER_DIGITS:
            raise OCRJobProtocolError("worker message exceeds number limit")
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise OCRJobProtocolError("invalid worker message")
        return
    if isinstance(value, list):
        if len(value) > _MAX_COLLECTION_ITEMS:
            raise OCRJobProtocolError("worker message exceeds collection limit")
        for item in value:
            _validate_json_value(item, depth=depth + 1, node_budget=node_budget)
        return
    if isinstance(value, dict):
        if len(value) > _MAX_COLLECTION_ITEMS:
            raise OCRJobProtocolError("worker message exceeds collection limit")
        for key, item in value.items():
            if not _bounded_text(key, _MAX_KEY_BYTES, allow_empty=False):
                raise OCRJobProtocolError("invalid worker message")
            node_budget[0] -= 1
            if node_budget[0] < 0:
                raise OCRJobProtocolError("worker message exceeds structure limits")
            _validate_json_value(item, depth=depth + 1, node_budget=node_budget)
        return
    raise OCRJobProtocolError("invalid worker message")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise OCRJobProtocolError("invalid worker message")
        result[key] = value
    return result


def _reject_constant(_value: str) -> None:
    raise OCRJobProtocolError("invalid worker message")


def _apply_worker_os_limits(limits: OCRProcessLimits) -> None:
    if os.name == "posix":
        import resource

        if not hasattr(resource, "RLIMIT_AS"):
            raise RuntimeError("process memory limit unavailable")
        memory = limits.child_memory_limit_bytes
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
        if hasattr(resource, "RLIMIT_CPU"):
            seconds = max(1, math.ceil(limits.job_timeout_seconds))
            resource.setrlimit(resource.RLIMIT_CPU, (seconds, seconds + 1))
    elif os.name != "nt":
        raise RuntimeError("unsupported worker platform")


def _resolve_factory(reference: str):
    _validate_factory_reference(reference)
    module_name, qualified_name = reference.split(":", 1)
    target: Any = importlib.import_module(module_name)
    for part in qualified_name.split("."):
        target = getattr(target, part)
    if not callable(target):
        raise TypeError("adapter factory is not callable")
    return target


def _send_worker_frame(connection, kind: str, payload: dict[str, object], limits: OCRProcessLimits, count: list[int]) -> None:
    count[0] += 1
    if count[0] > limits.max_ipc_messages:
        raise OCRJobProtocolError("worker message count limit exceeded")
    max_bytes = limits.max_status_frame_bytes if kind == "status" else limits.max_result_frame_bytes
    connection.send_bytes(encode_frame(
        {"version": PROTOCOL_VERSION, "kind": kind, "payload": payload},
        max_bytes=max_bytes,
    ))


def _ocr_worker_entry(
    input_receiver, output_sender, start_gate, factory_ref: str, limits: OCRProcessLimits,
    diagnostics_enabled: bool = False,
) -> None:
    """Spawn target. It receives no source data until after the parent gate."""
    input_payload: dict[str, object] | None = None
    message_count = [0]
    job_id = "unknown"
    generation_id = "unknown"
    terminal_phase = "failed"
    error_code: str | None = "worker_failed"
    def diagnostic(marker: bytes) -> None:
        if diagnostics_enabled:
            try:
                os.write(2, marker)
            except OSError:
                pass

    try:
        diagnostic(b"OCR2_SYNTHETIC_WORKER_BOOTSTRAP stage=wait_start_gate_begin\n")
        start_gate.wait()
        diagnostic(b"OCR2_SYNTHETIC_WORKER_BOOTSTRAP stage=wait_start_gate_done\n")
        diagnostic(b"OCR2_SYNTHETIC_WORKER_BOOTSTRAP stage=apply_os_limits_begin\n")
        _apply_worker_os_limits(limits)
        diagnostic(b"OCR2_SYNTHETIC_WORKER_BOOTSTRAP stage=apply_os_limits_done\n")
        diagnostic(b"OCR2_SYNTHETIC_WORKER_BOOTSTRAP stage=receive_input_frame_begin\n")
        raw = input_receiver.recv_bytes(maxlength=limits.max_input_frame_bytes)
        diagnostic(b"OCR2_SYNTHETIC_WORKER_BOOTSTRAP stage=receive_input_frame_done\n")
        diagnostic(b"OCR2_SYNTHETIC_WORKER_BOOTSTRAP stage=decode_input_frame_begin\n")
        envelope = _decode_with_kind(raw, limits.max_input_frame_bytes)
        diagnostic(b"OCR2_SYNTHETIC_WORKER_BOOTSTRAP stage=decode_input_frame_done\n")
        diagnostic(b"OCR2_SYNTHETIC_WORKER_BOOTSTRAP stage=validate_input_kind_begin\n")
        if envelope["kind"] != "input":
            raise OCRJobProtocolError("expected input frame")
        diagnostic(b"OCR2_SYNTHETIC_WORKER_BOOTSTRAP stage=validate_input_kind_done\n")
        input_payload = envelope["payload"]
        job_id = input_payload["job_id"]
        generation_id = input_payload["generation_id"]
        diagnostic(b"OCR2_SYNTHETIC_WORKER_BOOTSTRAP stage=send_starting_status_begin\n")
        _send_worker_frame(output_sender, "status", {
            "job_id": job_id, "phase": "starting_engine",
            "completed_documents": 0, "total_documents": len(input_payload["documents"]),
            "current_page": 0, "total_pages": 0, "error_code": None,
        }, limits, message_count)
        diagnostic(b"OCR2_SYNTHETIC_WORKER_BOOTSTRAP stage=send_starting_status_done\n")

        # Imports, catalog reconstruction, and factory construction are delayed
        # until the parent has attached the child to its OS resource boundary.
        diagnostic(b"OCR2_SYNTHETIC_WORKER_BOOTSTRAP stage=resolve_factory_begin\n")
        factory = _resolve_factory(factory_ref)
        diagnostic(b"OCR2_SYNTHETIC_WORKER_BOOTSTRAP stage=resolve_factory_done\n")
        diagnostic(b"OCR2_SYNTHETIC_WORKER_BOOTSTRAP stage=construct_engine_begin\n")
        adapter = _OutputBoundAdapter(factory(), limits.max_page_output_bytes)
        diagnostic(b"OCR2_SYNTHETIC_WORKER_BOOTSTRAP stage=construct_engine_done\n")
        diagnostic(b"OCR2_SYNTHETIC_WORKER_BOOTSTRAP stage=import_document_decoder_begin\n")
        from .document_decoder import iter_decoded_pages
        diagnostic(b"OCR2_SYNTHETIC_WORKER_BOOTSTRAP stage=import_document_decoder_done\n")

        def report_progress(
            status_job_id: str,
            status_generation_id: str,
            completed_documents: int,
            total_documents: int,
            current_page: int,
            total_pages: int,
        ) -> None:
            _send_worker_frame(output_sender, "status", {
                "job_id": status_job_id, "phase": "processing",
                "completed_documents": completed_documents,
                "total_documents": total_documents,
                "current_page": current_page, "total_pages": total_pages,
                "error_code": None,
            }, limits, message_count)

        output_records = _process_input_documents(
            input_payload,
            adapter,
            limits,
            decoder=iter_decoded_pages,
            report_progress=report_progress,
        )

        result_frame = encode_frame({
            "version": PROTOCOL_VERSION,
            "kind": "result",
            "payload": {
                "job_id": job_id, "generation_id": generation_id,
                "documents": output_records,
            },
        }, max_bytes=min(limits.max_result_frame_bytes, limits.max_aggregate_result_bytes))
        message_count[0] += 1
        if message_count[0] > limits.max_ipc_messages:
            raise OCRJobProtocolError("worker message count limit exceeded")
        output_sender.send_bytes(result_frame)
        terminal_phase = "succeeded"
        error_code = None
    except BaseException as exc:
        diagnostic(b"OCR2_SYNTHETIC_WORKER_BOOTSTRAP stage=worker_exception\n")
        if isinstance(exc, _PageOutputLimitError):
            error_code = "page_output_limit"
        elif isinstance(exc, OCRJobProtocolError):
            error_code = "worker_protocol_failed"
        else:
            error_code = "worker_failed"
    finally:
        if input_payload is not None:
            try:
                _send_worker_frame(output_sender, "terminal", {
                    "job_id": job_id, "generation_id": generation_id,
                    "phase": terminal_phase, "error_code": error_code,
                }, limits, message_count)
            except BaseException:
                pass
        input_receiver.close()
        output_sender.close()


def _decode_with_kind(frame: bytes, max_bytes: int) -> dict[str, object]:
    if not isinstance(frame, bytes) or len(frame) > max_bytes:
        raise OCRJobProtocolError("worker message exceeds byte limit")
    try:
        value = json.loads(
            frame.decode("utf-8", errors="strict"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
        kind = value.get("kind") if isinstance(value, dict) else None
        if not isinstance(kind, str):
            raise OCRJobProtocolError("invalid worker message")
        _validate_envelope(value, expected_kind=kind)
        return value
    except OCRJobProtocolError:
        raise
    except (UnicodeError, json.JSONDecodeError, TypeError, ValueError, RecursionError):
        raise OCRJobProtocolError("invalid worker message") from None


def _peek_canonical_kind(frame: bytes) -> str:
    """Identify the deterministic encoder's key-sorted kind prefix without parsing JSON."""
    for kind in ("status", "result", "terminal"):
        prefix = (f'{{"kind":"{kind}",').encode("ascii")
        if frame.startswith(prefix):
            return kind
    raise OCRJobProtocolError("invalid worker message")


class OCRProcessingManager:
    """Own one spawned, bounded OCR job and retain only a complete result frame."""

    def __init__(self, adapter_factory_ref: str, limits: OCRProcessLimits) -> None:
        _validate_factory_reference(adapter_factory_ref)
        if not isinstance(limits, OCRProcessLimits):
            raise ValueError("explicit OCR process limits are required")
        if os.name not in {"nt", "posix"}:
            raise ValueError("unsupported worker platform")
        if os.name == "posix":
            try:
                import resource
            except ImportError as exc:
                raise ValueError("process memory isolation is unavailable") from exc
            if not hasattr(resource, "RLIMIT_AS"):
                raise ValueError("process memory isolation is unavailable")
        self._adapter_factory_ref = adapter_factory_ref
        self._limits = limits
        self._lock = threading.RLock()
        self._job: _ManagedJob | None = None
        self._closed = False

    def start(self, generation_id, intake, *, decode_limits, custom_family_catalog=None) -> str:
        from .document_decoder import DecodeLimits
        from .expense_reports import ExpenseReportIntakeSession

        if (not isinstance(generation_id, str) or not generation_id
                or len(generation_id.encode("utf-8")) > 128):
            raise ValueError("invalid session generation")
        if not isinstance(intake, ExpenseReportIntakeSession):
            raise ValueError("invalid intake session")
        if not isinstance(decode_limits, DecodeLimits):
            raise ValueError("invalid decode limits")
        if not intake.documents or set(intake.documents) != set(intake.source_bytes):
            raise ValueError("intake documents and source bytes do not match")
        job_id = uuid.uuid4().hex
        documents = []
        for document_id, record in intake.documents.items():
            source = intake.source_bytes[document_id]
            if not isinstance(source, bytes) or len(source) > decode_limits.max_source_bytes:
                raise ValueError("source exceeds configured limit")
            documents.append({
                "document_id": document_id,
                "record": record,
                "source_bytes_b64": base64.b64encode(source).decode("ascii"),
            })
        catalog_payload = None
        if custom_family_catalog is not None:
            from .document_family_catalog import DocumentFamilyCatalog, MAX_CATALOG_BYTES
            if not isinstance(custom_family_catalog, DocumentFamilyCatalog):
                raise ValueError("invalid custom family catalog")
            catalog_json = custom_family_catalog.as_json()
            if len(catalog_json.encode("utf-8")) > MAX_CATALOG_BYTES:
                raise ValueError("catalog exceeds configured limit")
            catalog_payload = {
                "json": catalog_json,
                "version": custom_family_catalog.version,
                "sha256": custom_family_catalog.sha256,
            }
        frame = encode_frame({
            "version": PROTOCOL_VERSION,
            "kind": "input",
            "payload": {
                "job_id": job_id,
                "generation_id": generation_id,
                "documents": documents,
                "decode_limits": asdict(decode_limits),
                "catalog": catalog_payload,
            },
        }, max_bytes=self._limits.max_input_frame_bytes)
        with self._lock:
            if self._closed:
                raise RuntimeError("OCR manager is closed")
            if self._job is not None and self._job.status.phase not in _TERMINAL_PHASES:
                raise RuntimeError("an OCR job is already active")
            self._job = _ManagedJob(
                job_id, generation_id,
                OCRJobStatus(job_id, generation_id, "queued", 0, len(documents), 0, 0, None),
                frame, time.monotonic() + float(self._limits.job_timeout_seconds),
                threading.Event(),
            )
            job = self._job
            try:
                self._start_job_locked(job)
            except BaseException:
                job.status = OCRJobStatus(
                    job.job_id, job.generation_id, "failed", 0, len(documents),
                    0, 0, "worker_start_failed",
                )
                raise
        return job_id

    def _start_job_locked(self, job: _ManagedJob) -> None:
        context = multiprocessing.get_context("spawn")
        input_receiver, input_sender = context.Pipe(duplex=False)
        output_receiver, output_sender = context.Pipe(duplex=False)
        start_gate = context.Event()
        process = context.Process(
            target=_ocr_worker_entry,
            args=(
                input_receiver, output_sender, start_gate, self._adapter_factory_ref, self._limits,
                os.environ.get("OCR2_SYNTHETIC_WORKER_DIAGNOSTICS") == "1",
            ),
            daemon=True,
        )
        job.process = process
        job.input_sender = input_sender
        job.output_receiver = output_receiver
        try:
            process.start()
            input_receiver.close()
            output_sender.close()
            if os.name == "nt":
                from .isolated_decoder import _attach_windows_job
                job.windows_job, job.close_windows_job = _attach_windows_job(
                    process, self._limits.child_memory_limit_bytes,
                )
            start_gate.set()
        except BaseException:
            if process.is_alive():
                process.terminate()
                process.join(float(self._limits.cleanup_grace_seconds))
                if process.is_alive() and hasattr(process, "kill"):
                    process.kill()
                    process.join()
            self._close_handles(job, input_receiver=input_receiver, output_sender=output_sender)
            raise RuntimeError("OCR worker could not be safely started") from None
        supervisor = threading.Thread(
            target=self._supervise, args=(job,), name=f"ocr-supervisor-{job.job_id[:8]}", daemon=True,
        )
        job.supervisor = supervisor
        try:
            supervisor.start()
        except BaseException:
            self._stop_process(job)
            self._close_handles(job)
            raise RuntimeError("OCR supervisor could not be safely started") from None

    def _supervise(self, job: _ManagedJob) -> None:
        message_count = 0
        result: bytes | None = None
        terminal: dict[str, object] | None = None
        try:
            if job.cancelled.is_set():
                self._stop_process(job)
                self._set_terminal(job, "cancelled", None)
                return
            job.input_sender.send_bytes(job.input_frame)
            job.input_frame = b""
            job.input_sender.close()
            while True:
                if job.cancelled.is_set():
                    self._stop_process(job)
                    self._set_terminal(job, "cancelled", None)
                    return
                remaining = job.deadline - time.monotonic()
                if remaining <= 0:
                    self._stop_process(job)
                    self._set_terminal(job, "failed", "job_timeout")
                    return
                if job.output_receiver.poll(min(0.05, remaining)):
                    frame = job.output_receiver.recv_bytes(
                        maxlength=max(self._limits.max_status_frame_bytes, self._limits.max_result_frame_bytes),
                    )
                    message_count += 1
                    if message_count > self._limits.max_ipc_messages:
                        raise OCRJobProtocolError("worker message count limit exceeded")
                    kind = _peek_canonical_kind(frame)
                    kind_limit = self._limits.max_status_frame_bytes if kind == "status" else self._limits.max_result_frame_bytes
                    if len(frame) > kind_limit:
                        raise OCRJobProtocolError("worker message exceeds its kind limit")
                    envelope = decode_frame(frame, max_bytes=kind_limit, expected_kind=kind)
                    payload = envelope["payload"]
                    if kind == "status":
                        if payload["job_id"] != job.job_id:
                            raise OCRJobProtocolError("worker job identity mismatch")
                        self._set_status(job, payload)
                    elif kind == "result":
                        if (payload["job_id"] != job.job_id
                                or payload["generation_id"] != job.generation_id
                                or result is not None):
                            raise OCRJobProtocolError("worker result identity mismatch")
                        result = frame
                        if len(result) > self._limits.max_aggregate_result_bytes:
                            raise OCRJobProtocolError("aggregate result limit exceeded")
                    elif kind == "terminal":
                        if (payload["job_id"] != job.job_id
                                or payload["generation_id"] != job.generation_id):
                            raise OCRJobProtocolError("worker terminal identity mismatch")
                        terminal = payload
                        job.process.join(max(0.0, job.deadline - time.monotonic()))
                        if job.process.is_alive() or job.process.exitcode != 0:
                            raise RuntimeError("worker exited unexpectedly")
                        if job.cancelled.is_set():
                            self._set_terminal(job, "cancelled", None)
                        elif terminal["phase"] == "succeeded" and result is not None:
                            with self._lock:
                                if self._job is job and not job.cancelled.is_set():
                                    job.result = result
                                    job.status = OCRJobStatus(
                                        job.job_id, job.generation_id, "succeeded",
                                        job.status.total_documents, job.status.total_documents,
                                        job.status.total_pages, job.status.total_pages, None,
                                    )
                        else:
                            self._set_terminal(job, "failed", terminal.get("error_code") or "worker_failed")
                        return
                elif not job.process.is_alive():
                    if job.output_receiver.poll():
                        continue
                    raise RuntimeError("worker exited without a terminal frame")
        except BaseException:
            if job.cancelled.is_set():
                self._set_terminal(job, "cancelled", None)
            else:
                self._stop_process(job)
                self._set_terminal(job, "failed", "worker_protocol_failed")
        finally:
            if job.process.is_alive():
                self._stop_process(job)
            self._close_handles(job)

    def _set_status(self, job: _ManagedJob, payload: dict[str, object]) -> None:
        with self._lock:
            if self._job is job and not job.cancelled.is_set() and job.status.phase not in _TERMINAL_PHASES:
                job.status = OCRJobStatus(
                    job.job_id, job.generation_id, payload["phase"],
                    payload["completed_documents"], payload["total_documents"],
                    payload["current_page"], payload["total_pages"], payload["error_code"],
                )

    def _set_terminal(self, job: _ManagedJob, phase: str, error_code: str | None) -> None:
        with self._lock:
            if self._job is job and job.status.phase not in _TERMINAL_PHASES:
                job.result = None
                job.status = OCRJobStatus(
                    job.job_id, job.generation_id, phase,
                    job.status.completed_documents, job.status.total_documents,
                    job.status.current_page, job.status.total_pages, error_code,
                )

    def _stop_process(self, job: _ManagedJob) -> None:
        process = job.process
        if process is None:
            return
        try:
            if process.is_alive():
                process.terminate()
                process.join(float(self._limits.cleanup_grace_seconds))
                if process.is_alive() and hasattr(process, "kill"):
                    process.kill()
                    process.join(float(self._limits.cleanup_grace_seconds))
        except (OSError, ValueError):
            pass

    def _close_handles(self, job: _ManagedJob, *, input_receiver=None, output_sender=None) -> None:
        for handle in (job.input_sender, job.output_receiver, input_receiver, output_sender):
            if handle is not None:
                try:
                    handle.close()
                except (OSError, ValueError):
                    pass
        if job.windows_job is not None and job.close_windows_job is not None:
            try:
                job.close_windows_job(job.windows_job)
            except OSError:
                pass
            job.windows_job = None

    def snapshot(self, job_id: str) -> OCRJobStatus | None:
        with self._lock:
            if self._job is None or self._job.job_id != job_id:
                return None
            return self._job.status

    def mark_cancelled(self, generation_id: str) -> None:
        with self._lock:
            job = self._job
            if job is None or job.generation_id != generation_id:
                return
            if job.status.phase in _TERMINAL_PHASES:
                # Cancellation can beat publication after worker success, but cannot relabel
                # a result that has already been atomically consumed by the app.
                if job.status.phase == "succeeded" and not job.result_consumed:
                    job.result = None
                    job.result_consumed = True
                    job.status = OCRJobStatus(
                        job.job_id, job.generation_id, "cancelled",
                        job.status.completed_documents, job.status.total_documents,
                        job.status.current_page, job.status.total_pages, None,
                    )
                return
            job.cancelled.set()
            job.status = OCRJobStatus(
                job.job_id, job.generation_id, "cancelling",
                job.status.completed_documents, job.status.total_documents,
                job.status.current_page, job.status.total_pages, None,
            )

    def result_frame(self, generation_id: str, job_id: str) -> bytes | None:
        with self._lock:
            job = self._job
            if (job is None or job.job_id != job_id or job.generation_id != generation_id
                    or job.status.phase != "succeeded" or job.result_consumed):
                return None
            return bytes(job.result) if job.result is not None else None

    def publish_if_current(self, generation_id: str, job_id: str, result_digest: str) -> bool:
        with self._lock:
            job = self._job
            if (job is None or job.job_id != job_id or job.generation_id != generation_id
                    or job.status.phase != "succeeded" or job.result_consumed or job.result is None
                    or not isinstance(result_digest, str)
                    or hashlib.sha256(job.result).hexdigest() != result_digest):
                return False
            job.result_consumed = True
            job.result = None
            return True

    def close(self) -> None:
        with self._lock:
            self._closed = True
            job = self._job
            if job is not None and job.status.phase not in _TERMINAL_PHASES:
                job.cancelled.set()
        if job is not None and job.supervisor is not None:
            job.supervisor.join(float(self._limits.cleanup_grace_seconds) + 2.0)
            if job.supervisor.is_alive():
                self._stop_process(job)
                job.supervisor.join(float(self._limits.cleanup_grace_seconds))
