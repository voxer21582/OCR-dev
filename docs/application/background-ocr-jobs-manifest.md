# Isolated background OCR jobs — local candidate

Date: 2026-11-11. Branch: `codex/ocr-processing-jobs`. Base: `90ae4f9111af5ddad9272ffc20a96acb5311a2f5`. This candidate is locally prepared and unpublished. It follows the owner-approved design and implementation plan recorded in the local task dossier; the source checkout and original project remain untouched.

## Scope and provenance

All implementation changes are made in a clean clone of public OCR-dev. No source or artifact is copied from the old OCR project or the dirty source worktree.

| File | Change | Purpose |
| --- | --- | --- |
| `application/src/alfa_document_intelligence/ocr_processing.py` | New | Explicit resource limits, strict bounded JSON IPC, spawned worker, monotonic supervisor deadline, cancellation, cleanup and one-shot results |
| `application/src/alfa_document_intelligence/local_intake_app.py` | Modified | Optional injected manager, aggregate progress/cancel routes, generation-bound publication, pending-state guards and lifecycle invalidation |
| `application/src/alfa_document_intelligence/__main__.py` | Modified | `--ocr-engine disabled` default and fixed `rapidocr-v6` opt-in; bounded shutdown hook |
| `application/tests/test_ocr_processing.py` | New | Synthetic limits, protocol, child lifecycle, in-process fake decoder, race and cleanup contracts |
| `application/tests/test_ocr_job_ui.py` | New | Synthetic WSGI status, cancellation, idle timeout, invalidation, clear/result race and one-shot publication contracts |
| `application/tests/test_ocr_launcher_contract.py` | New | Standard-library tests for disabled default and fixed factory/limit wiring |
| `application/CURRENT_STATE.md` | Modified | Dated local evidence and remaining limits |

`docs/agent-work/2026-11-11-background-ocr-jobs/` contains the local plan identity, progress ledger and raw command outputs. Those local logs are not part of a public release manifest; they include machine-specific execution context. Do not publish them without a separate content review.

## Behavior and boundaries

- The standard launcher defaults to `disabled`. No adapter factory is taken from browser input. The only enabled CLI choice is the fixed `rapidocr-v6` factory reference; the existing runtime factory checks RapidOCR `3.10.0` and the pinned detector/recognizer hashes inside the child process.
- Explicit provisional limits for the opt-in are: 300-second whole-job deadline, 3-second cleanup grace, child memory bound 2 GiB minus one byte, input frame 64 MiB, status frame 4 KiB, result frame 16 MiB, aggregate result 64 MiB, page output 8 MiB and 100,000 IPC messages. These are engineering caps, not workload calibration.
- One spawned child handles documents sequentially. JSON frames use strict versioned schemas and byte caps before parse. On Windows, the gated child must attach to the existing Job Object mechanism before trusted factory import. Parent-side full OCR results are validated outside the session lock and published atomically only if generation, document IDs, source hashes, contracts and result digest still match.
- Clear, upload replacement, expiry, cancellation and shutdown invalidate results. Explicit cancellation can defeat a worker-succeeded but not yet published result; after one-shot publication, cancellation cannot relabel it. Polling does not extend session idle time. Mutation/review and archive state transitions are blocked while processing is pending.
- A4 PaddleOCR/medium research remains separate. This opt-in does not approve either runtime for production, install dependencies, fetch models, launch inference by default, or establish Windows 11 acceptance.

## Verification

Successful command, run from `application/` on 2026-11-11:

```powershell
$env:PYTHONPATH='src;tests'
python -B -m unittest tests.test_ocr_processing tests.test_ocr_job_ui tests.test_ocr_launcher_contract tests.test_local_intake_app tests.test_local_document_archive_ui tests.test_loopback_csrf tests.test_document_processing tests.test_ocr_adapter tests.test_analysis_pipeline tests.test_semantic_proposals tests.test_rapidocr_adapter tests.test_rapidocr_runtime_factory -v
```

Result: **132 tests, OK**. Raw output is retained locally at `docs/agent-work/2026-11-11-background-ocr-jobs/task5-6-explicit-synthetic-tests-final.log`, SHA-256 `773A420F5C21A0B0E4632A6288DAB0CC00DEE7CECA1DFD312EA2DA158DE352F8`. Fixtures and runtime packages are fake/synthetic; runtime factory tests use temporary hash fixtures and do not load the vendor runtime. The Windows child-attachment tests passed in this Windows environment. Added concurrency regressions verify clear/upload replacement during worker startup, concurrent successful polls, one-shot publication and session invalidation.

An earlier wider `unittest` invocation attempted to import three existing pytest-based modules and reported `ModuleNotFoundError: pytest`; those modules were omitted from the successful explicit list. No dependency was installed for this candidate test run. The 132-test command used fake/synthetic OCR only; it did not run native OCR inference or access model files. A separate local RapidOCR smoke attempt is outside this verification and has an unconfirmed result. No browser, real document, GitHub Actions run, or release was used for this candidate.

`py_compile` and `git diff --check` passed for implementation files. New untracked files were compiled and covered by their direct tests; `git diff --check` alone does not inspect untracked files. Independent static review returned READY after race corrections; the reviewer did not run tests. No push or merge has been made; the candidate remains for publication review on its dedicated branch.

## Not established

The fake-worker and factory contract tests do not demonstrate successful RapidOCR inference, model compatibility on this machine, native-library memory behavior, OCR accuracy, or total process-tree memory. The application integration is opt-in and not wired into an engine-acceptance claim. Manual Windows 11/runtime acceptance, actual installed package/model verification, workload fit, licensing review and owner acceptance remain open. R7/R8 and their stop/no-retry constraints were not touched.
