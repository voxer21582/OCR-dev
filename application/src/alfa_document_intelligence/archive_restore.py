"""Single-operation, in-memory coordinator for local archive restoration."""
from __future__ import annotations

from dataclasses import dataclass, replace
import secrets
import threading
from typing import Callable

from .local_document_store import LocalDocumentStore, StoreOperationCancelled

_ACTIVE_PHASES = {"queued", "copying", "validating", "publishing", "cancelling"}
_TERMINAL_PHASES = {"succeeded", "failed", "cancelled"}


class RestoreStartError(RuntimeError):
    """The local restore worker could not be started or another restore is active."""


@dataclass(frozen=True)
class RestoreStatus:
    job_id: str
    phase: str
    remaining_pages: int
    total_pages: int
    destination: str | None = None
    error_code: str | None = None


class ArchiveRestoreManager:
    """Run at most one cancellable archive restore in a daemon thread."""

    def __init__(self, store: LocalDocumentStore) -> None:
        self._store = store
        self._lock = threading.Lock()
        self._status: RestoreStatus | None = None
        self._source: str | None = None
        self._destination: str | None = None
        self._cancel_requested = False
        self._thread: threading.Thread | None = None

    def start(self, source: str, destination: str) -> str:
        job_id = secrets.token_urlsafe(18)
        with self._lock:
            if self._status is not None and self._status.phase in _ACTIVE_PHASES:
                raise RestoreStartError("an archive restore is already active")
            self._status = RestoreStatus(job_id, "queued", 0, 0)
            self._source = source
            self._destination = destination
            self._cancel_requested = False
            thread = threading.Thread(
                target=self._run,
                args=(job_id,),
                name="ocr2-archive-restore",
                daemon=True,
            )
            self._thread = thread
            try:
                thread.start()
            except Exception as exc:
                self._status = replace(
                    self._status, phase="failed", error_code="restore_start_failed"
                )
                self._source = None
                self._destination = None
                raise RestoreStartError("could not start archive restore") from exc
        return job_id

    def snapshot(self, job_id: str) -> RestoreStatus | None:
        with self._lock:
            if self._status is None or self._status.job_id != job_id:
                return None
            return self._status

    def last_status(self) -> RestoreStatus | None:
        """Return the latest status for local shutdown/tests; routes use opaque IDs."""
        with self._lock:
            return self._status

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            if self._status is None or self._status.job_id != job_id:
                return False
            if self._status.phase in _TERMINAL_PHASES:
                return False
            self._cancel_requested = True
            self._status = replace(self._status, phase="cancelling")
            return True

    def close(self, *, join_timeout_seconds: float = 3.0) -> None:
        with self._lock:
            status = self._status
            thread = self._thread
            job_id = status.job_id if status is not None else None
        if job_id is not None:
            self.cancel(job_id)
        if thread is not None and thread is not threading.current_thread():
            thread.join(join_timeout_seconds)

    def _is_cancelled(self, job_id: str) -> bool:
        with self._lock:
            return bool(
                self._status is None
                or self._status.job_id != job_id
                or self._cancel_requested
            )

    def _set_phase(self, job_id: str, phase: str) -> None:
        with self._lock:
            if self._status is None or self._status.job_id != job_id:
                return
            if self._cancel_requested and phase not in _TERMINAL_PHASES:
                self._status = replace(self._status, phase="cancelling")
            elif self._status.phase not in _TERMINAL_PHASES:
                self._status = replace(self._status, phase=phase)

    def _set_progress(self, job_id: str, remaining: int, total: int) -> None:
        if (
            not isinstance(remaining, int)
            or isinstance(remaining, bool)
            or not isinstance(total, int)
            or isinstance(total, bool)
            or remaining < 0
            or total < 0
            or remaining > total
        ):
            raise ValueError("archive progress must contain bounded non-negative page counts")
        with self._lock:
            if self._status is None or self._status.job_id != job_id:
                return
            if self._status.phase not in _TERMINAL_PHASES:
                self._status = replace(
                    self._status,
                    remaining_pages=remaining,
                    total_pages=total,
                )

    def _publish(self, job_id: str, destination: str, atomic_publish: Callable[[], None]) -> bool:
        # The callback only wraps the atomic rename/link commit point; snapshot
        # flushing and validation occur outside this lock in LocalDocumentStore.
        with self._lock:
            if (
                self._status is None
                or self._status.job_id != job_id
                or self._cancel_requested
                or self._status.phase in _TERMINAL_PHASES
            ):
                return False
            atomic_publish()
            self._status = replace(
                self._status,
                phase="succeeded",
                destination=destination,
                error_code=None,
            )
            self._source = None
            self._destination = None
            return True

    def _finish(self, job_id: str, *, phase: str, error_code: str | None = None) -> None:
        with self._lock:
            if self._status is None or self._status.job_id != job_id:
                return
            if self._status.phase == "succeeded":
                return
            self._status = replace(
                self._status,
                phase=phase,
                destination=None,
                error_code=error_code,
            )
            self._source = None
            self._destination = None

    def _run(self, job_id: str) -> None:
        with self._lock:
            if self._status is None or self._status.job_id != job_id:
                return
            source = self._source
            destination = self._destination
        if source is None or destination is None:
            self._finish(job_id, phase="failed", error_code="archive_restore_failed")
            return
        try:
            self._store.restore_backup_to(
                source,
                destination,
                progress_callback=lambda remaining, total: self._set_progress(
                    job_id, remaining, total
                ),
                phase_callback=lambda phase: self._set_phase(job_id, phase),
                cancel_requested=lambda: self._is_cancelled(job_id),
                publication_callback=lambda publish: self._publish(
                    job_id, destination, publish
                ),
            )
            self._finish(job_id, phase="succeeded")
        except StoreOperationCancelled:
            self._finish(job_id, phase="cancelled")
        except Exception:
            self._finish(job_id, phase="failed", error_code="archive_restore_failed")
