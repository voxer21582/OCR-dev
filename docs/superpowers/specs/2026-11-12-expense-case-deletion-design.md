# Per-case deletion design

## Intent

Honor the owner's retention choice (“keep until explicit deletion”) by allowing one expense case to be deliberately removed from the encrypted local archive. The current store already implements case deletion and preserves independently retained or still-shared documents; the missing piece is a safe UI path.

## Scope and constraints

- Add a side-effect-free confirmation page and a same-origin POST action for one case.
- Require the current case revision and the exact opaque case ID typed by the owner before deletion.
- Refuse deletion while processing is queued or active; do not alter the archive on refusal.
- Reuse `LocalDocumentStore.delete_case`; keep its existing ownership, sharing, and retention behavior unchanged. Add optional expected-revision and processing-state guards checked inside the same SQLite transaction, while preserving existing behavior for callers that omit them.
- Do not display OCR or financial values on the confirmation page.
- Do not delete any real case in this work; verify only with synthetic test fixtures.
- Preserve loopback, same-origin, no-store, encrypted-at-rest, and R7/R8 constraints.

## Approaches

1. **Single-click delete from the intake page:** shortest UI, but too easy to remove a persistent case accidentally.
2. **Two-step confirmation page with typed case ID (selected):** explicit, revision-bound, and requires no dependency or change to the store's deletion semantics.
3. **Archive-wide purge control:** does not satisfy per-case retention and risks deleting unrelated cases.

## Behavior

The intake page links to `/cases/{case_id}/delete`. GET renders the case ID, the number of documents, the permanence warning, and a form requiring the exact case ID. POST checks same-origin and confirmation equality, then passes the expected revision and active processing states to the store so those guards are enforced atomically with deletion. Success shows a generic completion message and a link to the case list; invalid, stale, active, and missing cases fail without exposing document names or values.

## Acceptance evidence

- Synthetic WSGI tests prove confirmation is required, wrong origin/stale revision/active processing do not delete, valid confirmation removes the case and its unshared case-owned documents, and existing store retention rules remain in force.
- Optional store guards are checked in the deletion transaction; unguarded existing callers retain their prior behavior.
- Only the targeted case-intake route tests run; no real documents, OCR runtime, or R7/R8 modules are involved.

## Calls left to the implementer

Use the existing WSGI/HTML patterns and stdlib `unittest`; do not add dependencies or change archive schema.
