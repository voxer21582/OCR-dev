# Expense Case Deletion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the owner explicitly delete one persisted expense case without accidental or stale-confirmation deletion.

**Architecture:** Add a GET confirmation page and a POST route in the existing local WSGI app. The POST validates origin and exact typed case ID, then supplies the expected case revision and non-active processing states to `LocalDocumentStore.delete_case` for atomic checks in its existing transaction.

**Tech Stack:** Python 3.13 standard library WSGI and `unittest`; existing encrypted local document store.

**Spec:** `docs/superpowers/specs/2026-11-12-expense-case-deletion-design.md`

## Global Constraints

- No new dependencies, schema changes, external requests, real documents, or real-case deletion.
- Preserve encrypted-at-rest storage, loopback/same-origin protections, no-store responses, and existing store sharing/retention semantics.
- Keep OCR and R7/R8 untouched; test only the synthetic case-intake module.
- Do not export or render OCR/financial values on the confirmation page.

## Review Focus

- Wrong or missing typed case ID must not delete the case: test `test_delete_case_requires_exact_typed_confirmation`.
- Stale case revision must not delete a changed case: test `test_delete_case_rejects_stale_revision`.
- Queued or active OCR must not be deleted: test `test_delete_case_rejects_active_processing`.
- Cross-origin POST must be rejected before consuming the request: test `test_delete_case_rejects_wrong_origin_without_mutation`.
- Missing case IDs must return a generic not-found result without exposing stored fields: test `test_delete_case_missing_id_is_not_found`.
- A valid confirmation removes only the case and documents owned solely by it: test `test_delete_case_removes_case_and_unshared_documents`.

---

### Task 1: Add route contract tests

**Files:**
- Modify: `application/tests/test_expense_case_intake_routes.py`
- Consume: current `LocalDocumentStore.delete_case` and `case_revision` behavior.
- Produce: observable test cases for side-effect-free confirmation, confirmation validation, rejected requests, and successful deletion.

- [x] **Step 1: Write failing tests first**

  Add tests for all six behaviors in Review Focus. Assert the case is absent after valid confirmation, its unshared synthetic documents are removed, and the case remains intact after every rejected request. Use the real store and the existing synthetic protector.

- [x] **Step 2: Run the route module and verify expected failures**

  Run from `application/`: `$env:PYTHONPATH='src;tests'; & 'C:\Users\voxer\AppData\Local\Programs\Python\Python313\python.exe' -B -m unittest -v test_expense_case_intake_routes`

  Expected: the new cases fail because `/cases/{id}/delete` is not implemented; existing route tests pass.

### Task 2: Implement the two-step deletion flow

**Files:**
- Modify: `application/src/alfa_document_intelligence/local_intake_app.py`
- Modify: `application/src/alfa_document_intelligence/local_document_store.py`
- Test: `application/tests/test_expense_case_intake_routes.py`

- [x] **Step 1: Implement atomic store guards, the confirmation renderer, and route**

  Add optional expected-revision and rejected-processing-state parameters to `LocalDocumentStore.delete_case`; check them inside its existing transaction without changing default behavior or ownership/retention semantics. Register `/cases/{case_id}/delete`. GET renders only the case ID, document count, permanence notice, and a form with hidden current revision plus a field requiring the exact case ID. POST rejects wrong origin before reading the body; requires exactly `_case_revision` and `_confirmation`; then calls `archive_store.delete_case` with atomic guards. Return generic, no-store responses and never expose source names, hashes, OCR, or field values.

- [x] **Step 2: Link deletion from the case intake page**

  Add a visible “Elimina fascicolo” link to its confirmation page. Do not add deletion to archive-wide controls or to the case list.

- [x] **Step 3: Run the targeted route tests**

  Run from `application/`: `$env:PYTHONPATH='src;tests'; & 'C:\Users\voxer\AppData\Local\Programs\Python\Python313\python.exe' -B -m unittest -v test_expense_case_intake_routes`

  Expected: all 16 route tests pass; only synthetic fixtures and temporary test stores are used.

### Task 3: Review and record the candidate

**Files:**
- Update: `docs/superpowers/plans/2026-11-12-expense-case-deletion.md`
- Review: the complete diff in this branch.

- [x] **Step 1: Check whitespace and scope**

  Run `git diff --check`; inspect `git diff --stat` and verify only the five planned application, test, design, and plan files changed.

- [ ] **Step 2: Review deletion semantics**

  Confirm no real archive was opened or changed, no deletion is executed outside synthetic test stores, and existing store retention rules are unchanged. Report that the branch is based on PR #106 and that public Actions do not yet run the new route tests.

- [ ] **Step 3: Commit the candidate locally for immutable review**

  Commit only the five planned files with a message such as `Add explicit local expense case deletion`. The commit remains local; a fresh reviewer then reviews the exact commit range before any publication decision.
