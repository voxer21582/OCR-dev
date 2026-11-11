# Expense statement reconciliation implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Let a user maintain one encrypted local expense case with one final statement and up to 100 supporting documents, then review evidence-backed reconciliation suggestions.

**Architecture:** Keep document records and OCR worker contracts; add a versioned case manifest to the existing encrypted `LocalDocumentStore`, a deterministic reconciliation module, bounded resumable upload/processing orchestration, and a local review/export route. All uploads and processing remain on loopback; no document or derived value is sent externally.

**Tech Stack:** Python 3.13, standard-library `unittest`, existing WSGI app, SQLite store, existing OCR job manager and schema validation. No new runtime dependency.

**Spec:** `docs/superpowers/specs/2026-11-11-expense-reconciliation-design.md`

## Global Constraints

- One case contains one final expense statement and at most 100 supporting documents.
- The existing loopback-only boundary, encrypted local archive, source hashes, page/region evidence, and human review ledger remain authoritative.
- Cumulative local case limits: 100 supporting documents plus one mandatory statement; 2,525 MiB retained source bytes including excluded attachments; 500 decoded pages, 2,000,000,000 decoded pixels, and 256 MiB OCR output for the mandatory statement plus currently included attachments. Existing per-request bounds remain 20 parts / 100 MiB; existing per-document bound remains 25 MiB; each worker job remains inside its configured frame/output caps.
- OCR stays opt-in; the app never sends real documents, OCR text, or derived values to a remote service.
- Case reconciliation screens/exports do not feed the existing `/chatgpt` manual-copy handoff; that separate route is unchanged and out of scope.
- GitHub CI uses synthetic fixtures only, with explicit test selectors; exclude R7/R8 and all blocked modules.
- Do not add dependencies, download models, change Windows configuration, or modify Google deployments.
- Do not merge or release without the required owner approval.

## Review Focus

- A chunk retry after a timeout must not duplicate or lose previously accepted documents; test with same chunk id/same digest and same chunk id/different digest.
- A sealed source update must make current reconciliation decisions stale while preserving append-only history; test unchanged and changed source hashes and revisions.
- Two cases may reference the same archived source; deleting one case must preserve that source for the other.
- A 100-document case must not be encoded into one IPC frame; test dynamic batch boundaries at one document and at the maximum aggregate.
- Archive interruption, malformed manifest, and stale session generation must fail closed without publishing partial reconciliation or exposing document content through status routes.
- Source-byte quota rejects before chunk commit. Page and decoded-pixel quotas are measured page-by-page before OCR adapter invocation (including PDF pages not counted at intake); an overflowing OCR chunk publishes nothing while preserving accepted sources. OCR-result quota is checked before processing-chunk persistence. Exact-boundary and one-over tests pin each rule.

---

### Task 1: Reconciliation domain contract

**Files:**
- Create: `application/src/alfa_document_intelligence/expense_reconciliation.py`
- Create: `application/tests/test_expense_reconciliation.py`
- Modify: `application/src/alfa_document_intelligence/schemas/document.schema.json` only if the case/line record is embedded in a document record; prefer a separate versioned case manifest.

**Interfaces:**
- `build_reconciliation(case_id: str, statement_id: str, statement_hash: str, statement_lines: list[dict], attachments: list[dict], documents: Mapping[str, dict]) -> dict`
- `validate_reconciliation(reconciliation: dict, documents: Mapping[str, dict]) -> None`
- `append_line_review(reconciliation: dict, *, expected_case_revision: str, line_id: str, expected_line_evidence_sha256: str, action: str, candidate_sources: list[dict], event_id: str, reviewer_note: str | None) -> dict`
- Review event fields are `event_id`, monotonic `sequence`, `case_revision`, `line_id`, `line_evidence_sha256`, `action`, `candidate_sources` (document ID + source SHA-256), and optional reviewer note. Duplicate event IDs are idempotent only when the full event digest is identical; conflicting replays fail. Any source/list revision change marks prior current decisions `stale` without deleting their history.
- Every candidate carries the exact source hash/page/region for the statement line and supporting record; ranking reasons are deterministic and do not claim probability.

- [x] Write failing synthetic tests for exact amount/currency matches, date/vendor supporting signals, missing support, unused receipt, duplicate source, ambiguous ties, amount/currency/date conflicts, possible duplicate claims, absent/uncertain fields, evidence validation, append-only review idempotency, stale history, and tampering.
- [x] From `application/`, set `$env:PYTHONPATH = 'src;tests'` in PowerShell, then run `python -m unittest -v test_expense_reconciliation`; the first run failed because the new module was missing, as expected.
- [x] Implement versioned pure contract and deterministic candidate ranking; do not convert proposals to confirmed outcomes.
- [x] Run the explicit module (15 tests) and all 8 `test_expense_reports` functions; existing suite functions were run using their unittest assertions because the Python `pytest` package is unavailable. Independent code review READY; `compileall` passed.

### Task 2: Encrypted persistent case manifests

**Files:**
- Modify: `application/src/alfa_document_intelligence/local_document_store.py`
- Modify: `application/tests/test_local_document_store.py`
- Create: `application/tests/test_expense_case_store.py`

**Interfaces:**
- Add `save_case(case: dict, *, expected_revision: str | None = None) -> str`, `get_case(case_id: str) -> dict | None`, `list_cases(query: str = "", *, limit: int = 100) -> list[dict]`, and `delete_case(case_id: str) -> bool` to `LocalDocumentStore`.
- Case payloads and event/reconciliation content are protected with the store's existing `PayloadProtector`; case IDs are indexed only through a keyed digest. Keep the existing per-document API and schema-v2 databases readable.
- Case deletion removes only documents unreferenced by another case and must be one transaction.

- [x] Add synthetic-protector tests for case create/read/reopen/search, optimistic revision conflict, schema-v2 migration, tamper detection, reference-aware deletion, and failed transaction rollback.
- [x] Run `python -m unittest -v test_expense_case_store` and the existing local-store test module; confirm RED first.
- [x] Implement schema-v3 encrypted `cases` and `case_documents` tables. Each reference binds case index, document index, role, and source SHA-256; reads and deletes verify the bound digest against the decrypted record before acting. Existing documents migrate as independently retained; case-uploaded documents are case-owned until independently pinned.
- [x] Add APIs `create_case(case_manifest, statement_record, source_bytes)`, `append_case_chunk(case_id, expected_revision, chunk_id, chunk_digest, source_records)`, `commit_case_processing_chunk(case_id, expected_revision, chunk_id, updated_records, next_manifest)`, and `append_attachment_inclusion_event(case_id, expected_revision, document_id, source_sha256, included, reason, event_id)`. Each persists records/references/events and the encrypted manifest/chunk digest in a single `BEGIN IMMEDIATE` transaction. A same-ID/same-digest replay is idempotent; same-ID/different-digest and stale revisions fail without mutation. Inclusion events are append-only; the latest event controls active membership, and every change advances the revision and marks OCR/reconciliation derived state stale.
- [x] Implement `get_case`, `list_cases`, and `delete_case`; deletion removes only unshared case-owned sources, while independently retained or shared sources survive. All references are checked before the transaction commits.
- [x] Run both explicit modules; confirmed pass with the v2 migration fixtures.
- [x] Security review capped canonical document metadata at 1 MiB per record, 101 MiB per case, and included it with source bytes in the 100 MiB per-request and free-space calculation. Chunk digests bind record metadata while normalizing only server-generated receipt time for safe retry.

### Task 3: Resumable bounded case intake

**Files:**
- Modify: `application/src/alfa_document_intelligence/local_intake_app.py`
- Modify: `application/tests/test_local_intake_app.py`
- Modify: `application/src/alfa_document_intelligence/ingestion.py` only if an existing bound cannot express a case chunk.

**Interfaces:**
- `POST /cases` accepts one statement and creates a case.
- `POST /cases/{case_id}/attachments` accepts one bounded chunk (existing maximum 20 uploaded parts / 100 MiB per request), with a stable chunk id and digest.
- `POST /cases/{case_id}/attachments/{document_id}/inclusion` records an explicit include/exclude action with current case revision, source hash, event id, and reason; exclusion retains source bytes but removes that attachment from future OCR and reconciliation input.
- `GET /cases/{case_id}` returns aggregate counts, safe state codes, and the current revision only; it must not return filenames, OCR text, values, source hashes, or document bytes from a progress poll.
- [ ] Add synthetic WSGI tests for 100 supporting documents across at least five chunks, per-request and pre-commit source-byte boundaries, replay idempotency, conflicting replay digest, interrupted chunk, include/exclude event idempotency and stale revision/source rejection, same-origin/CSRF, local-host rejection, free-space threshold at exactly `2 * incoming_chunk_bytes + 64 MiB`, and preserving prior committed chunks. Current coverage: 100 documents in five HTTP chunks; same-request replay and conflicting replay; rejection of a 21-document expanded ZIP; wrong-origin rejection before body read; safe aggregate status. Remaining route tests include inclusion/exclusion, explicit stale revision, and public-data guard.
- [x] Add and run explicit route tests RED before implementation (unknown route), then verify the new selectors pass.
- [x] Route every accepted chunk through the store's atomic `append_case_chunk`; include canonical metadata in per-request space preflight (two times the incoming bytes plus 64 MiB); reject the 101st attachment. PDFs do not require ingestion-time page counts.
- [ ] Run `test_local_intake_app`, `test_local_document_store`, `test_expense_reports`, and `test_public_data_guard`; confirm pass.

### Task 4: Sequential bounded OCR orchestration

**Files:**
- Create: `application/src/alfa_document_intelligence/expense_case_processing.py`
- Create: `application/tests/test_expense_case_processing.py`
- Modify: `application/src/alfa_document_intelligence/local_intake_app.py`

**Interfaces:**
- `ExpenseCaseProcessingManager.start(case_id: str, case_revision: str) -> str`, `snapshot(job_id: str) -> ExpenseCaseJobStatus | None`, `cancel(job_id: str) -> None`, `close() -> None`.
- The case coordinator schedules sequential existing `OCRProcessingManager` jobs for the mandatory statement plus currently included attachments (the statement cannot be excluded), grouping sources so each encoded input remains below `OCRProcessLimits.max_input_frame_bytes` and each output below the result-frame/aggregate limits; derive group boundaries from actual encoded size, not a guessed document count.
- Before a page reaches the OCR adapter, the worker enforces remaining case-wide page and pixel budgets, counting one decoded page and `width_px * height_px` pixels. It reports only fixed safe error codes on exhaustion. A failed group publishes no partial OCR output; accepted source chunks remain intact. After a whole group validates, one store transaction updates all record outputs and the case cursor/result-byte total.

- [ ] Add fake-engine synthetic tests for size-derived chunking, progress totals, cancellation, restart/resume cursor, per-chunk atomic persistence, worker failure isolation, duplicate status polling, end-of-case digest binding, page/pixel quota exact and one-over behavior (pixel count per decoded `width_px * height_px` before adapter invocation), no partial output persistence on overflow, and explicit source-preserving attachment exclusion.
- [ ] Run explicit `test_expense_case_processing` selectors; confirm RED.
- [ ] Implement the coordinator with no new dependency, external process, network access, or default OCR activation.
- [ ] Run the coordinator module plus `test_ocr_processing` and `test_ocr_job_ui`; confirm pass.

### Task 5: Reconciliation review UI and local export

**Files:**
- Modify: `application/src/alfa_document_intelligence/local_intake_app.py`
- Create: `application/tests/test_expense_reconciliation_ui.py`
- Modify: `application/tests/test_local_intake_app.py`

**Interfaces:**
- `GET /cases/{case_id}/reconciliation` displays statement lines, ranked attachment candidates, evidence links, discrepancies, and append-only review state.
- `POST /cases/{case_id}/reconciliation/review` records one explicit human action bound to current case revision and source hashes.
- `GET /cases/{case_id}/export` is a local-only download initiated explicitly by the user; CSV/JSON exports separate machine suggestions from confirmed human decisions and include evidence references.

- [ ] Add synthetic UI tests for every review outcome, source-page navigation, stale revision/source-hash rejection, duplicate review event replay, attachment include/exclude confirmation and history, safe HTML escaping, explicit export, no approval/payment language, and isolation from `/chatgpt` handoff.
- [ ] Run explicit `test_expense_reconciliation_ui`; confirm RED.
- [ ] Implement review, attachment include/exclude, and export routes and a small responsive Italian UI in the existing style; no external script, stylesheet, analytics, or network request.
- [ ] Run the UI module and the existing explicit UI/review/export tests; confirm pass.

### Task 6: Document and CI integration

**Files:**
- Modify: `application/CURRENT_STATE.md`
- Modify: `application/README.md`
- Modify: `.github/workflows/ocr2-synthetic-taxonomy.yml` only through a separate CI change after PR #105 is repaired/merged or replaced.
- Create: `application/docs/expense-reconciliation-manifest.md`

- [ ] Record the exact local commands, synthetic-only suite, artifacts and limitations; do not include real document names, contents, hashes, screenshots, or derived values.
- [ ] Run the existing repository public-data guard and `git diff --check`.
- [ ] Add only explicit new test-module selectors to CI; keep `Taxonomy registry and binding`, permissions, pinned Actions, runner, dependency lock, and R7/R8 exclusions intact.
- [ ] Verify the PR workflow triggers and all affected checks; no merge or release.

## Integration

Keep each task reviewable and commit locally with the task-specific scope. Open separate product and CI PRs only after the corresponding evidence is complete. The product PR must not contain real notes or derived data. The CI PR must use only explicit selectors and synthetic fixtures. Do not merge either PR without owner approval.
