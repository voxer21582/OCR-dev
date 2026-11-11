# Expense reconciliation candidate evidence

Date: 2026-11-12

State: published for review in open draft PR #106; not merged or product-accepted.

## Implemented in the isolated branch

- One encrypted local case binds one final expense statement and up to 100 supporting documents. Attachments are uploaded in bounded batches of at most 20, with the existing per-request byte limit and resumable chunk identity.
- OCR is explicit and local. The default CLI engine remains `disabled`; case processing requires an explicit `--ocr-engine rapidocr-v6` selection.
- OCR tokens produce versioned (0.3.0) statement-line proposals with source hash, page, region, token IDs, producer, literal text, and uncertainty. Unsupported or ambiguous values remain unresolved.
- Deterministic reconciliation compares statement lines against included supporting records. An uncertain receipt alternative may be shown as a possible match, never as a confirmed match. Each human choice is append-only and bound to the current reconciliation revision and source hashes. The revision also binds a digest of immutable upload-chunk and attachment-inclusion history (excluding review events), so exclude/reinclude/reprocess cannot reactivate an earlier confirmation.
- The OCR line extractor leaves merchant absent unless a future evidence-backed extractor can determine it. Amount/currency/date conflict and possible-duplicate signals still work with merchant absent as weaker evidence; a known merchant disagreement suppresses those weaker signals. All remain review prompts, not decisions.
- The local review screen displays statement lines, source-page links, candidate signals, conflicts, unmatched receipts, duplicate sources, and review status. Attachment inclusion/exclusion requires a reason and retains event history. Stale OCR results cannot be reconciled after source membership changes.
- A user-initiated JSON download keeps machine suggestions, human review state, and evidence references in distinct fields. The preview and download routes are local case-bound routes; they do not link to or populate `/chatgpt`.

## Verification evidence

Run from `application/` in PowerShell:

```powershell
$env:PYTHONPATH = 'src;tests'
python -m unittest -q test_expense_line_extraction test_expense_reconciliation test_expense_reconciliation_ui test_expense_case_store test_expense_case_intake_routes test_expense_case_processing test_local_document_store test_local_intake_app test_ocr_processing test_ocr_job_ui test_ocr_launcher_contract test_public_data_guard test_document_processing test_document_contract test_catalog_pipeline test_analysis_pipeline test_semantic_proposals test_document_validation
python -m compileall -q src tests
git -C .. diff --check
```

Result on 2026-11-11: **263 synthetic unittest cases passed** across the 18 explicitly selected modules after the independent-review corrections for stale review projection, missing-merchant integration, and JSON-safe date-conflict evidence; `python -m compileall -q src tests` and `git -C .. diff --check` also passed. These are local results, not a GitHub Actions run. `pytest` was not installed, so only the explicitly selected unittest modules ran. Some launcher tests print the loopback address and temporary sandbox archive path; those outputs were not added to the repository.

The tests cover extraction-to-reconciliation paths for amount/currency/date conflicts and possible duplicate statement lines when merchant is absent, JSON serialization of a date-conflict result without merchant evidence, and the WSGI reconciliation page, all review outcomes, idempotent review replay, stale revision and source-binding rejection, local source-page route membership, HTML escaping, append-only attachment inclusion history, explicit JSON download, separation from the ChatGPT handoff, and exclusion/reinclusion after a human confirmation without restoring that old decision. Page rendering is mocked in the route test; native PDF/image decoding and browser visual/accessibility behavior are not proven.

## Privacy and acceptance limits

- No real expense document was selected, read, processed, or attached during this implementation. No real filename, OCR value, source hash, screenshot, or derived value was committed or sent to GitHub, CI, ChatGPT, or any external service.
- Automated tests use synthetic records and fake OCR adapters only. They do not measure real OCR accuracy.
- Windows runtime/model availability, install/upgrade behavior, CPU/memory use, 100-document performance, and a real-note comparison on the reference PC remain unverified.
- This candidate is not a fiscal review, reimbursement decision, payment authorization, or accounting posting. Every suggested match needs human review.
- Do not use this candidate for a live expense report until the owner verifies the local OCR runtime and compares its output with a real final note inside the local app.
- The branch `codex/expense-reconciliation` is public and reviewable in [PR #106](https://github.com/voxer21582/OCR-dev/pull/106); it has not been merged. Its latest GitHub Actions run passed 279 pre-existing synthetic contracts, but the explicit selector did not include these expense-case modules. The separate [PR #105](https://github.com/voxer21582/OCR-dev/pull/105) worker-test CI currently fails two Linux startup tests; its required check has not been established green. R7/R8 and their stop/no-retry restrictions were not touched.
