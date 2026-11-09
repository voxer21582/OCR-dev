import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from alfa_document_intelligence.archive_restore import (
    ArchiveRestoreManager,
    RestoreStartError,
)
from alfa_document_intelligence.local_document_store import StoreOperationCancelled


class ControlledStore:
    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()
        self.published = False
        self.fail_with = None

    def restore_backup_to(
        self,
        source,
        destination,
        *,
        progress_callback=None,
        phase_callback=None,
        cancel_requested=None,
        publication_callback=None,
    ):
        if phase_callback:
            phase_callback("copying")
        if progress_callback:
            progress_callback(4, 8)
        self.started.set()
        self.release.wait(2)
        if cancel_requested and cancel_requested():
            raise StoreOperationCancelled("archive operation cancelled")
        if self.fail_with is not None:
            raise self.fail_with
        if phase_callback:
            phase_callback("validating")
            phase_callback("publishing")

        def commit():
            self.published = True

        if publication_callback is None or not publication_callback(commit):
            raise StoreOperationCancelled("archive operation cancelled")
        return type("Restored", (), {"path": Path(destination)})()


class ArchiveRestoreManagerTests(unittest.TestCase):
    def _wait_for(self, manager, job_id, phase):
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            status = manager.snapshot(job_id)
            if status is not None and status.phase == phase:
                return status
            time.sleep(0.005)
        self.fail(f"restore job did not reach {phase}")

    def test_job_is_async_reports_aggregate_progress_and_discloses_path_only_on_success(self):
        store = ControlledStore()
        manager = ArchiveRestoreManager(store)
        job_id = manager.start("synthetic-backup.sqlite3", "synthetic-restored.sqlite3")
        self.assertTrue(store.started.wait(1))
        status = manager.snapshot(job_id)
        self.assertEqual(status.phase, "copying")
        self.assertEqual((status.remaining_pages, status.total_pages), (4, 8))
        self.assertIsNone(status.destination)
        store.release.set()
        status = self._wait_for(manager, job_id, "succeeded")
        self.assertEqual(status.destination, "synthetic-restored.sqlite3")
        self.assertIsNone(status.error_code)
        self.assertIsNone(manager._source)
        self.assertIsNone(manager._destination)

    def test_only_one_restore_may_be_active_and_unknown_ids_are_private(self):
        store = ControlledStore()
        manager = ArchiveRestoreManager(store)
        job_id = manager.start("synthetic-source", "synthetic-destination")
        self.assertTrue(store.started.wait(1))
        self.assertIsNone(manager.snapshot("another-session-job"))
        with self.assertRaises(RestoreStartError):
            manager.start("other-source", "other-destination")
        store.release.set()
        self._wait_for(manager, job_id, "succeeded")

    def test_cancel_before_publish_prevents_publication_and_hides_paths(self):
        store = ControlledStore()
        manager = ArchiveRestoreManager(store)
        job_id = manager.start("synthetic-private-source", "synthetic-private-destination")
        self.assertTrue(store.started.wait(1))
        self.assertTrue(manager.cancel(job_id))
        store.release.set()
        status = self._wait_for(manager, job_id, "cancelled")
        self.assertFalse(store.published)
        self.assertIsNone(status.destination)
        self.assertIsNone(status.error_code)

    def test_failures_use_a_generic_error_without_echoing_paths(self):
        store = ControlledStore()
        store.fail_with = OSError("secret path C:\\Users\\private\\backup.sqlite3")
        manager = ArchiveRestoreManager(store)
        job_id = manager.start("synthetic-private-source", "synthetic-private-destination")
        self.assertTrue(store.started.wait(1))
        store.release.set()
        status = self._wait_for(manager, job_id, "failed")
        self.assertEqual(status.error_code, "archive_restore_failed")
        self.assertIsNone(status.destination)
        self.assertNotIn("private", repr(status))

    def test_worker_start_failure_is_reported_and_does_not_strand_active_job(self):
        store = ControlledStore()
        manager = ArchiveRestoreManager(store)
        with patch("alfa_document_intelligence.archive_restore.threading.Thread.start", side_effect=RuntimeError("synthetic start failure")):
            with self.assertRaises(RestoreStartError):
                manager.start("synthetic-source", "synthetic-destination")
        status = manager.last_status()
        self.assertEqual(status.phase, "failed")
        self.assertEqual(status.error_code, "restore_start_failed")
        self.assertIsNone(status.destination)


if __name__ == "__main__":
    unittest.main()
