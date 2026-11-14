# Expense statement reconciliation design

Date: 2026-11-11
Status: proposed implementation design for the owner-directed local workflow

## Intent

Let the owner review one final expense statement together with up to 100 supporting documents. OCR2 processes documents on the Windows PC, proposes evidence-backed matches between statement lines and supporting documents, and leaves every match and discrepancy for human review. This is a local productivity workflow, not a fiscal, reimbursement, or payment approval.

## What exists today

- The loopback intake app accepts one selected expense statement and multiple independent supporting documents, and binds them into an in-memory bundle.
- The intake form currently permits at most 20 uploaded files and 100 MiB per request. ZIP ingestion exists, but the request and all materialized documents are held in memory; this is not verified for a 100-document workload.
- The bundle reports exact source duplicates but does not reconcile statement lines with receipts.
- The record contract has evidence-backed field proposals and source hashes, but does not yet define expense statement line items or cross-document reconciliation decisions.
- On Windows, the launcher opens the encrypted local document archive. Individual documents are saved to it explicitly; current bundle relationships are not a durable batch-case workflow.
- OCR is opt-in. Windows runtime and real-document quality remain unaccepted; no production OCR outcome is inferred from synthetic CI.

## Goals

1. Create one durable local case for one final expense statement and up to 100 supporting documents.
2. Accept documents in bounded chunks while preserving a single case identity, source order, upload progress, retry-safe chunk identity, and cancellation that never silently deletes already accepted documents. Source records, reference bindings, and the chunk ledger commit in one SQLite transaction.
3. Process locally with the configured OCR worker, keep source SHA-256 and page/region evidence for every extracted value, and retain alternatives/uncertainty.
4. Present an evidence-led reconciliation table linking each statement line to zero, one, or multiple candidate supporting documents.
5. Detect exact duplicate sources and suggest possible duplicate expense claims without deleting or silently merging records.
6. Require a human decision for each suggested match, conflict, missing receipt, duplicate, or exclusion.
7. Save the case and review decisions in the existing encrypted local store, reopen and resume it, search/manage it, export a review report, and delete it only through an explicit owner action.
8. Keep all real files and extracted values on the local PC. No document, OCR text, note line, or derived sensitive value goes to ChatGPT, GitHub, CI, telemetry, or a third-party OCR service.

## Non-goals

- Automatic fiscal or legal classification, reimbursement approval, payment, accounting posting, or tax advice.
- Using real notes as benchmark/training data or putting them into public repository artifacts.
- Replacing the separate A4 PaddleOCR/medium research direction or changing the selected RapidOCR direction.
- Removing R7/R8 blocks, retrying their stopped checks, or changing Windows security configuration.
- Assuming that a green CI run or a correctly matched sample proves product-wide OCR acceptance.

## Approaches considered

### A. One case with bounded upload and sequential OCR chunks — recommended

Create a case from one expense statement, then add supporting documents in chunks whose byte, file, page, and decoded-image limits are explicit. Process chunks sequentially through the existing isolated worker, persist validated results and case bindings after each accepted chunk, then reconcile the complete case. This matches the owner's one-final-note workflow and contains memory use. It requires versioned case storage and a recovery model.

### B. One ZIP or one multipart request containing all documents

This is superficially simple and resembles current intake, but retains unbounded-in-practice request buffering and does not provide safe progress/resume. It is rejected for 100-document use.

### C. Global document inbox followed by manual association

This decouples intake from statements and may fit multiple simultaneous reports, but adds queue/search/association complexity beyond the stated workflow. Keep as a possible later extension if the owner needs multi-report allocation.

## Chosen behavior and reversible technical decisions

- A case has exactly one final expense statement and up to 100 supporting documents. If the count is exceeded, stop before accepting the excess and explain the limit.
- Every OCR processing run includes the mandatory statement plus all currently included supporting attachments. The statement cannot be excluded while its case is open.
- Upload occurs in bounded chunks. Source byte limits are checked before committing a chunk. Cumulative page and exact raster-pixel limits are counted as each page is decoded, before it reaches the OCR adapter; this also handles PDFs whose page count is not available from ingestion metadata. If either case-wide processing budget is exceeded, the whole current processing chunk fails without publishing partial OCR output, while its accepted encrypted source files remain available. The UI offers an explicit, reversible include/exclude action with a reason, retaining the source and event history until explicit case deletion. Earlier committed chunks remain intact and the next resumable position is reported.
- Before each chunk transaction, the app checks free space on the local archive volume without changing Windows settings. It requires at least two times the incoming chunk bytes plus a 64 MiB reserve; otherwise it leaves the case unchanged and asks the owner to retry with a smaller chunk or free local disk space.
- The statement is uploaded/selected first and establishes the case. Later chunks add supporting documents; replacing the statement starts a new case rather than mutating the old case's identity.
- OCR and semantic proposals run on this PC only. OCR remains opt-in; a case can be created/reviewed without enabling OCR. Before processing real documents, the UI clearly states local storage, current OCR engine, and retention behavior.
- The case uses the existing encrypted local archive/protector. Source documents and extracted records remain until explicit case deletion. Deleting a case atomically removes its case binding, review ledger entries, and source documents not referenced by any other retained case; shared-document ownership must be checked before deletion.
- First-pass cumulative caps are: at most 100 attachments plus one statement; at most 2,525 MiB of retained source bytes (101 documents × the existing 25 MiB per-document maximum, including excluded-but-retained attachments); at most 500 decoded pages, 2,000,000,000 decoded pixels, and 256 MiB stored OCR output per case. The last three caps include the mandatory statement and every currently included attachment, and exclude attachments explicitly excluded from processing. Existing per-request bounds remain 20 parts / 100 MiB. Each OCR worker frame remains within the existing 64 MiB input, 16 MiB result-frame, and 64 MiB aggregate-result bounds. These are explicit local engineering limits, not claims of measured performance. The UI reports which bound was reached and never truncates input.
- Reconciliation is a separate, versioned record bound to the statement hash and attachment hashes. A revision invalidates stale suggestions and marks affected decisions for review rather than silently carrying them forward.
- Reconciliation is computed after the owner seals the document list for processing. Review events bind the sealed case revision, statement-line evidence digest, and each selected attachment's document ID and source hash. If any source or the sealed list changes, previous decisions remain in history but are marked stale and cannot count as current confirmations.
- Each statement line and receipt candidate preserves literal values, normalized candidate values, uncertainty, and source hash/page/region. Matching uses deterministic, explainable signals (amount/currency, date, merchant, and optional description) and emits ranked suggestions with reasons, not a hidden probability presented as truth.
- Review outcomes are `unreviewed`, `confirmed`, `rejected`, `ambiguous`, `missing_support`, `possible_duplicate`, and `excluded_with_reason`. Human correction is append-only and source-bound. No state is called approved or paid.
- Attachment inclusion/exclusion is also append-only and source-bound. Excluding an attachment removes it from OCR/reconciliation inputs but retains its encrypted source; including it again creates a later event. Either action advances the case revision and makes derived OCR/reconciliation state stale until reprocessed.
- Export is an owner-initiated local file action. It includes the selected statement lines, confirmed/unresolved match states, source evidence references, and discrepancies. It does not send data to a service. Export format/version and overwrite behavior are explicit.
- The new case/reconciliation screens and exports do not populate the existing `/chatgpt` manual-copy handoff. That separately governed route is outside this feature's scope; a reconciliation case, its OCR, or its derived values cannot be copied there by this feature.
- CI remains synthetic-only. Real documents are used only when the owner operates the local Windows app; no real text, hashes, names, screenshots, or derived values are committed or uploaded.

## Acceptance criteria

1. A local case can contain one statement plus 100 supporting documents submitted over multiple bounded chunks within the cumulative limits above; the UI displays accepted, pending, processed, and failed counts without file contents in progress/status endpoints.
2. Restarting the app reopens the encrypted case, its source bindings, processing state, review history, and unresolved work; each chunk's document records, case references, and idempotency digest commit atomically, so interruption cannot partially accept or duplicate a chunk.
3. Each OCR or extracted field shown in the review UI resolves to the exact source hash and page/region; unreadable or uncertain inputs remain visibly unresolved.
4. The reconciliation screen compares structured statement lines with evidence-backed supporting-document proposals and lists unmatched statement lines, unused receipts, duplicate hashes, conflicting amounts/currencies/dates, and ambiguous matches.
5. A suggested match never becomes confirmed without a human action. Review events are append-only and bound to the exact case revision, statement-line evidence digest, candidate document IDs and source hashes; changed sources leave old events visible as stale history and invalidate current decisions.
6. Explicit deletion removes the case and only its unshared files/records; canceling a chunk, closing the browser, or a worker failure never silently deletes prior accepted case data.
7. Source-byte caps reject before chunk commit. The page cap counts each decoded page, including PDF pages with unknown ingestion-time count; the pixel cap counts `width_px * height_px` once for each page before OCR adapter invocation. If either cap is exceeded, no OCR output from that processing chunk is committed, sources remain stored, and the owner can explicitly exclude or re-include an attachment with a reason. Such actions are append-only, revision-bound, and invalidate derived state.
8. Local exports contain no OCR value lacking its source evidence, distinguish confirmed human review from machine proposals, and are generated only on explicit request.
9. Automated tests use synthetic fixtures only and explicitly selected modules. They cover chunk boundaries/resume, storage transactions, matching outcomes, changed-source invalidation, deletion/reference integrity, and export redaction. No R7/R8 tests are added.
10. A Windows real-document demonstration is separately reported with owner-selected notes, local-only handling, aggregate test record, and human comparison to the final statement. No private source or extracted values enter the record shared with GitHub.

## Dependencies and restrictions

- Depends on the accepted encrypted local store, versioned document records, evidence-bound review ledger, and optional isolated OCR job manager.
- Runtime, licenses, package/model provenance, Windows resource behavior, native OCR accuracy, installer acceptance, and performance at 100 documents remain open gates. Do not claim that this design resolves them.
- Do not install dependencies or models, modify Windows configuration, deploy Google services, or use a paid service.
- Preserve all R7/R8 stop/no-retry controls and existing main protection/required CI check.
- GitHub CI continues to use synthetic fixtures only; no real expense note is uploaded to GitHub or any external service.
