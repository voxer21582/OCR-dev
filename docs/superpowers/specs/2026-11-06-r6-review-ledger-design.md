# R6 In-Memory Review Ledger Design

## Intent

Provide an append-only, immutable foundation for human review of one R4 field candidate. Preserve prior corrections, bind each review to exact candidate and taxonomy identities, reject appends based on a stale snapshot, and let downstream work detect stale results.

## Goals and acceptance

- Represent neutral human actions: `confirm`, `correct`, `reject`, and `defer`; none means financial or accounting approval.
- Retain the original immutable `FieldCandidate` snapshot and every prior event when a new revision is added; require the expected current revision as a stale-snapshot precondition.
- Bind the ledger and each event to a deterministic fingerprint of the candidate and the taxonomy schema/version/hash.
- Preserve a synthetic corrected value in the event while retaining the original candidate unchanged.
- Report a review as stale when the current candidate or taxonomy differs from its bound identity.
- Let a derived result be considered current only when its candidate digest, taxonomy digest, and review revision match the present state.
- Keep values and events in memory only; do not write to disk, read the OS identity, or infer a reviewer.
- Use synthetic tests; do not exercise UI, persistence, OCR, Windows configuration, or Google services.

## Non-goals

- No review UI, browser/keyboard walkthrough, durable history, reopen-after-restart, database schema, search, export, multi-user permissions, free-text notes, or operating-system identity integration.
- No OCR, candidate extraction, fiscal semantics, payment approval, R7/R8, issue #8, A4/A5, or real-document evaluation.

## Approaches considered

1. **Mutate a `FieldCandidate` in place.** Rejected because the R4 candidate is frozen, its evidence identity must remain intact, and correction must not erase the original.
2. **Write review events to the document library now.** Rejected because durable case storage and recovery are R7 responsibilities and their work is blocked.
3. **Return a new immutable in-memory ledger for each append.** Chosen because it preserves history and makes stale-snapshot preconditions testable without touching persistence or blocked work.

## Technical choices

- Each ledger represents one caller-supplied opaque `subject_id` and one exact `FieldCandidate`.
- The ledger retains the original immutable candidate snapshot and a SHA-256 fingerprint of its deterministic serialization; the digest detects when a caller presents different candidate content.
- This pure function does not provide atomic compare-and-swap. A caller that can issue concurrent writes must serialize them or atomically compare-and-swap the returned ledger in its owning store.
- Each event records a UTC timestamp supplied by the caller, an opaque `reviewer_id` supplied by the caller, and a stable `reason_code`. The library does not read the Windows account or collect free-text notes.
- `confirm` may select one existing alternative, or confirm a candidate with no alternatives as an absence/unreadability observation. `correct` stores a non-empty manual value. `reject` and `defer` store neither a value nor an alternative index.
- A derived result carries the candidate digest, taxonomy digest, and review revision at which it was produced. It is current only if all three match the latest ledger state.
- Reopening within the same session means reconstructing a view from the in-memory ledger. Reopening after restart requires R7 persistence and is not accepted by this tranche.

## Remaining R6 work

The user-facing source/region/alternative view, correction controls, keyboard/browser walkthrough, durable history, and integration with case reopening remain open under issue #34. This contract alone does not satisfy R6 or the product goal.
