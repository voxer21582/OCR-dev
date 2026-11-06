"""Optional process-isolated document decoding with OS resource limits.

Use this entry point when a local processor must decode untrusted document bytes.
The worker uses the spawn start method, has a wall-clock deadline, and is placed
under an OS memory limit. It writes no files and receives no OCR model.
"""
from __future__ import annotations

import math
import multiprocessing
import os
import time
from typing import Callable, Iterator

from .document_decoder import (
    DecodeLimits,
    DecodedPage,
    DocumentDecodeError,
    iter_decoded_pages,
)


_DEFAULT_TIMEOUT_SECONDS = 60.0
_DEFAULT_MEMORY_LIMIT_BYTES = 1024 * 1024 * 1024


def _apply_posix_limits(memory_limit_bytes: int, timeout_seconds: float) -> None:
    import resource

    if not hasattr(resource, "RLIMIT_AS"):
        raise RuntimeError("address-space limits are unavailable")
    memory_limit = (memory_limit_bytes, memory_limit_bytes)
    resource.setrlimit(resource.RLIMIT_AS, memory_limit)
    if hasattr(resource, "RLIMIT_CPU"):
        cpu_seconds = max(1, math.ceil(timeout_seconds))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))


def _decode_worker(
    connection,
    start_event,
    source_bytes: bytes,
    media_kind: str,
    source_sha256: str,
    limits: DecodeLimits,
    decoder: Callable,
    memory_limit_bytes: int,
    timeout_seconds: float,
) -> None:
    try:
        start_event.wait()
        if os.name == "posix":
            _apply_posix_limits(memory_limit_bytes, timeout_seconds)
        for page in decoder(
            source_bytes,
            media_kind,
            source_sha256=source_sha256,
            limits=limits,
        ):
            connection.send(("page", page))
        connection.send(("complete", None))
    except DocumentDecodeError as exc:
        try:
            connection.send(("error", str(exc)))
        except (BrokenPipeError, EOFError, OSError):
            pass
    except BaseException:
        try:
            connection.send(("error", "isolated document decoding failed"))
        except (BrokenPipeError, EOFError, OSError):
            pass
    finally:
        connection.close()


def _attach_windows_job(process, memory_limit_bytes: int):
    """Assign the waiting child to a kill-on-close Job Object with memory caps."""
    import ctypes
    from ctypes import wintypes

    class IoCounters(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class BasicLimitInformation(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class ExtendedLimitInformation(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", BasicLimitInformation),
            ("IoInfo", IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD
    ]
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        raise OSError(ctypes.get_last_error(), "cannot create decoder Job Object")
    try:
        info = ExtendedLimitInformation()
        info.BasicLimitInformation.LimitFlags = 0x00000100 | 0x00000200 | 0x00002000
        info.ProcessMemoryLimit = memory_limit_bytes
        info.JobMemoryLimit = memory_limit_bytes
        if not kernel32.SetInformationJobObject(
            job, 9, ctypes.byref(info), ctypes.sizeof(info)
        ):
            raise OSError(ctypes.get_last_error(), "cannot set decoder Job Object limits")
        process_handle = kernel32.OpenProcess(0x0001 | 0x0100 | 0x0400, False, process.pid)
        if not process_handle:
            raise OSError(ctypes.get_last_error(), "cannot open decoder worker process")
        try:
            if not kernel32.AssignProcessToJobObject(job, process_handle):
                raise OSError(ctypes.get_last_error(), "cannot assign decoder worker to Job Object")
        finally:
            kernel32.CloseHandle(process_handle)
        return job, kernel32.CloseHandle
    except BaseException:
        kernel32.CloseHandle(job)
        raise


def iter_decoded_pages_isolated(
    source_bytes: bytes,
    media_kind: str,
    *,
    source_sha256: str,
    limits: DecodeLimits = DecodeLimits(),
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    memory_limit_bytes: int = _DEFAULT_MEMORY_LIMIT_BYTES,
    decoder: Callable = iter_decoded_pages,
) -> Iterator[DecodedPage]:
    """Decode pages in a spawned, time- and memory-bounded child process.

    The decoder must be importable/picklable for the spawn start method. Native
    decoding errors, resource-limit failures, crashes, and timeouts fail closed.
    """
    if not isinstance(source_bytes, bytes) or not source_bytes:
        raise DocumentDecodeError("source bytes must be non-empty")
    if not isinstance(source_sha256, str) or len(source_sha256) != 64:
        raise DocumentDecodeError("source SHA-256 is required")
    if media_kind not in {"pdf", "png", "jpeg", "tiff", "webp"}:
        raise DocumentDecodeError("unsupported media kind")
    if not isinstance(limits, DecodeLimits):
        raise DocumentDecodeError("decode limits are invalid")
    if len(source_bytes) > limits.max_source_bytes:
        raise DocumentDecodeError("source bytes exceed the configured size limit")
    if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool):
        raise ValueError("timeout_seconds must be a finite positive number")
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0 or timeout_seconds > 3600:
        raise ValueError("timeout_seconds must be greater than 0 and at most 3600")
    if not isinstance(memory_limit_bytes, int) or isinstance(memory_limit_bytes, bool):
        raise ValueError("memory_limit_bytes must be a positive integer")
    if memory_limit_bytes < 128 * 1024 * 1024:
        raise ValueError("memory_limit_bytes must be at least 128 MiB")
    if os.name == "posix":
        try:
            import resource
        except ImportError as exc:
            raise DocumentDecodeError("OS memory isolation is unavailable") from exc
        if not hasattr(resource, "RLIMIT_AS"):
            raise DocumentDecodeError("OS memory isolation is unavailable")
    elif os.name != "nt":
        raise DocumentDecodeError("process isolation is unsupported on this operating system")

    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    start_event = context.Event()
    worker = context.Process(
        target=_decode_worker,
        args=(
            sender, start_event, source_bytes, media_kind, source_sha256.lower(),
            limits, decoder, memory_limit_bytes, float(timeout_seconds),
        ),
        daemon=True,
    )
    job = None
    close_job = None
    finished = False
    started = False
    deadline = time.monotonic() + timeout_seconds
    try:
        worker.start()
        started = True
        sender.close()
        if os.name == "nt":
            job, close_job = _attach_windows_job(worker, memory_limit_bytes)
        start_event.set()
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DocumentDecodeError("document decoding timed out")
            if receiver.poll(min(remaining, 0.1)):
                try:
                    kind, payload = receiver.recv()
                except (EOFError, OSError) as exc:
                    raise DocumentDecodeError("isolated document decoder exited unexpectedly") from exc
                if kind == "page":
                    yield payload
                elif kind == "error":
                    raise DocumentDecodeError(payload)
                elif kind == "complete":
                    worker.join(max(0.0, deadline - time.monotonic()))
                    if worker.is_alive() or worker.exitcode != 0:
                        raise DocumentDecodeError("isolated document decoder exited unexpectedly")
                    finished = True
                    return
                else:
                    raise DocumentDecodeError("isolated document decoder returned an invalid message")
            elif not worker.is_alive():
                if receiver.poll():
                    continue
                raise DocumentDecodeError("isolated document decoder exited unexpectedly")
    except DocumentDecodeError:
        raise
    except Exception as exc:
        raise DocumentDecodeError("isolated document decoder could not start") from exc
    finally:
        if started:
            if not finished and worker.is_alive():
                worker.terminate()
                worker.join(2.0)
                if worker.is_alive() and hasattr(worker, "kill"):
                    worker.kill()
                    worker.join()
            else:
                worker.join(0.1)
        receiver.close()
        try:
            sender.close()
        except OSError:
            pass
        if job is not None and close_job is not None:
            close_job(job)
