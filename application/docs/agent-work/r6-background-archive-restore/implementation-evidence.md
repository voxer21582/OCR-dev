# R6 background archive restore: implementation evidence

Date: 2026-11-09
Branch: `codex/r6-background-archive-restore`
Base: `aed04ac` (`feat: show fiscal review evidence history`)
Status: local candidate; independent review READY; GitHub Actions, browser acceptance, and merge are pending.

## Scope

Implements the approved background archive-restore design in the isolated canonical `OCR-dev` worktree. It does not change the original checkout, the source `document-intelligence` checkout, R7/R8, OCR activation, installer/runtime configuration, GitHub governance, or the separately owned Actions workflow.

Changed files:

- `application/src/alfa_document_intelligence/local_document_store.py`: SQLite online snapshot copy, free-space preflight, schema/integrity/record/source validation, cancellation hooks, no-overwrite atomic publication, and backup/restore APIs.
- `application/src/alfa_document_intelligence/archive_restore.py`: single in-memory background job, opaque identifier, aggregate progress, cancellation, and sanitized failure state.
- `application/src/alfa_document_intelligence/local_intake_app.py`: local restore form/status/cancel routes, same-origin POST enforcement, path privacy until publication, and bounded worker cancellation on local server close.
- `application/tests/test_local_document_store.py`, `application/tests/test_archive_restore.py`, and `application/tests/test_local_document_archive_ui.py`: synthetic regression coverage.
- `application/CURRENT_STATE.md`: dated candidate state and limitations.

## Acceptance evidence

The following commands passed on CPython 3.13.15 without installing dependencies:

```powershell
$env:PYTHONPATH='application/src;application/tests'
python -B -m unittest test_local_document_archive_ui test_archive_restore -v
```

Result: 15 tests passed. This covers loopback UI route behavior, path privacy before successful publish, same-origin cancellation, manager progress/cancellation/failure handling, and worker startup failure.

The full `LocalDocumentStoreTests` test case was run with its Windows DPAPI integration test omitted:

```powershell
$env:PYTHONPATH='application/src;application/tests'
@'
import unittest
import test_local_document_store
suite = unittest.defaultTestLoader.loadTestsFromTestCase(test_local_document_store.LocalDocumentStoreTests)
suite._tests = [test for test in suite if test._testMethodName != "test_windows_dpapi_protects_and_reopens_synthetic_archive"]
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
'@ | python -B
```

Result: 31 tests passed. Added coverage checks a synthetic encrypted backup round-trip, exact source-byte preservation, no overwrite, insufficient-space rejection before staging, cancellation before and during SQLite copy with staging cleanup, and status/API behavior. A broad invocation also ran the omitted DPAPI case once; it failed with Windows API error 2 in this runtime. It was not retried. This result does not establish DPAPI runtime acceptance.

## Not established

- No GitHub Actions workflow was modified or run for this candidate. The explicit test selectors need review through the separately owned workflow path.
- No browser-level interaction or Windows user acceptance has been performed.
- The restore writes a new archive file and leaves it separate; automatic switching of the running application to the restored archive is not implemented.
- The visible workflow accepts local source and destination paths. It does not provide a backup-download button; `LocalDocumentStore.backup_to` is available to an integrating local caller.
- Server shutdown requests cancellation and joins the worker for up to three seconds. A filesystem or SQLite operation that remains blocked beyond that window could outlive server shutdown; this case has not been simulated.
- On POSIX, publication uses a hard link to preserve no-overwrite semantics. If removing the temporary hard-link alias fails even after final cleanup retries, the restore may succeed while leaving an encrypted hidden staging alias; this cleanup-failure path is not simulated.
- No real archive or user document was used. This is not a release or proof of disaster-recovery readiness.
- Independent review is READY. GitHub Actions verification, browser acceptance, and owner-approved merge remain pending.
