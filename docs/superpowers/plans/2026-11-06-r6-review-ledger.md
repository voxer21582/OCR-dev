# R6 In-Memory Review Ledger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an immutable in-memory review ledger for one taxonomy-bound field candidate, preserving corrections and reporting stale results.

**Architecture:** A pure Python module validates and fingerprints the R4 candidate, appends immutable review events using an expected revision, and compares the present candidate/taxonomy/revision with a derived result snapshot. Persistence and UI remain separate.

**Tech Stack:** Python 3.13, standard library, existing R4 candidate and taxonomy binding contracts, `unittest`.

**Spec:** `docs/superpowers/specs/2026-11-06-r6-review-ledger-design.md`

## Global Constraints

- Use only synthetic taxonomy, candidate, page, and review values.
- Add no dependency and perform no disk, network, OCR, Windows, or Google operation.
- Preserve R7/R8/#8 stop/no-retry and keep durable persistence out of scope.
- Do not interpret review as fiscal, payment, reimbursement, or accounting approval.
- Add the new test module to CI only in a separate PR using an explicit allowlist entry.

## Review Focus

- A corrected value must append and retain earlier history rather than mutate the R4 candidate.
- A stale expected revision must be rejected without changing the ledger.
- Candidate or taxonomy changes must make the review stale.
- Changed page observations or provenance must make the review stale.
- A downstream result stamped with an earlier review revision must not be reported current.
- Invalid event shape, actor/reason identity, or non-UTC timestamp must fail with sanitized codes.
- The immutable append function is not an atomic concurrency primitive; any concurrent caller/store must serialize or compare-and-swap.

---

### Task 1: Implement and test the review ledger contract

**Files:**
- Create: `src/alfa_document_intelligence/review_contracts.py`
- Test: `tests/test_review_contracts.py`
- Create: `docs/ocr/review-ledger-contract.md`
- Modify: `README.md`
- Create: `docs/agent-work/issue-34-publication-manifest.md`

**Interfaces:**
- `ReviewAction`: `CONFIRM`, `CORRECT`, `REJECT`, `DEFER`.
- `ReviewStatus`: `UNREVIEWED`, `CURRENT`, `STALE`.
- `ReviewEvent`: immutable action, revision, candidate/taxonomy identity, opaque actor/reason codes, UTC time, and optional selection/correction.
- `ReviewLedger`: immutable subject/candidate/taxonomy identity, original `FieldCandidate` snapshot, and ordered event tuple.
- `start_review_ledger(subject_id, candidate, binding, page_results) -> ReviewLedger`.
- `append_review_event(ledger, candidate, binding, page_results, *, expected_revision, action, reviewer_id, reason_code, occurred_at_utc, selected_alternative_index=None, corrected_value=None) -> ReviewLedger`.
- `review_status(ledger, candidate, binding, page_results) -> ReviewStatus`.
- `derived_result_is_current(ledger, candidate, binding, page_results, *, candidate_sha256, taxonomy_sha256, review_revision) -> bool`.

- [ ] Write synthetic tests for append-only correction, action-shape rules, revision conflicts, candidate/taxonomy staleness, derived-result freshness, sanitized errors, and input immutability.
- [ ] Attempt the focused module. If local `jsonschema` is unavailable, record the import limitation and use only the existing locked GitHub runner; do not install locally.
- [ ] Implement the minimal immutable model and pure functions required by the tests.
- [ ] Run the focused test module with the locked GitHub runner and the existing explicit allowlist.
- [ ] Independently review the feature diff, update docs/manifest hashes, and prepare a feature PR based on the R5 CI PR. Keep issue #34 open.

### Task 2: Extend CI separately

**Files:**
- Separate branch/PR modifying only the existing workflow, README test command/count, and the R6 CI manifest.

- [ ] Add exactly `test_review_contracts` to the allowlist, without discovery or globs.
- [ ] Preserve the required check, triggers, SHA pins, read-only permissions, runner, timeout, and hash lock.
- [ ] Verify push and pull-request runs execute the selected tests; report the result as a contract check, not R6 or product acceptance.
