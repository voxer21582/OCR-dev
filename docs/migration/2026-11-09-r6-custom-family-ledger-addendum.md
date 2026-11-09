# R6 custom-family review-ledger migration addendum

## Scope

Migrate the reviewed custom-family snapshot binding for manual document-family review into the canonical public repository. This is a narrow application-code tranche under `application/`; it does not claim R6 or product acceptance.

## Source and ownership

- Source repository: `https://github.com/voxer21582/document-intelligence`.
- Source branch: `codex/custom-family-ledger-fix-20261109`.
- Source feature commit: `1f8f423c76f3e831d1ebe3319215ae322f2d52d4` (parent `3b7d6325a374d2168d3c6ebaa65252407efa5a73`).
- The project owner assigned this chat scoped ownership of `review_ledger.py` and `test_review_ledger.py` on 2026-11-09, then granted the additional `document.schema.json`, `contracts.py`, `local_intake_app.py`, and related synthetic-test scope for R6 (#34) and migration (#42). Concurrent branches remain untouched.
- The source feature diff received an independent READY review for the ledger-only behavior. The full canonical migration diff and manifest received a separate independent READY review on 2026-11-09; GitHub formal approval and merge remain pending.

## File manifest

| Canonical file | Final SHA-256 | Canonical base blob SHA-1 | Provenance, owner, review | Decision |
| --- | --- | --- | --- | --- |
| `application/src/alfa_document_intelligence/review_ledger.py` | `eaab8a3687e752f5221c8a99ad8c425c491a1dfde885b6b9906bfc6d4deae436` | `ea9c260b750ab1bb9f5cf02fdeaa6737373b3674` | Source SHA-256 `EAAB8A3687E752F5221C8A99AD8C425C491A1DFDE885B6B9906BFC6D4DEAE436`, captured from authorized source worktree; exact source-base blob matches canonical main. | Include; event hash covers custom-family snapshot. |
| `application/src/alfa_document_intelligence/schemas/document.schema.json` | `777e31b8631199fbe1ad8d2b6bcd803b2cd182dfee43bf6c845673db579cfb65` | `7dc68c6a8e0daaa1a45e2151a4fc7706813c245a` | Canonical file modified under owner grant; full-diff review READY 2026-11-09. | Include; type snapshot and restrict its event/action context. |
| `application/src/alfa_document_intelligence/local_intake_app.py` | `3e6e51866cc6086d33408e18c5942eb5039c24a9b45c237506e38c13bf797ab1` | `c439eb0fb3153016a2bf793b736f1ce062507407` | Canonical file modified under owner grant; full-diff review READY 2026-11-09. | Include; allow custom-family review only with valid snapshot and observed evidence-bound alternative, using the catalog label. |
| `application/tests/test_review_ledger.py` | `68b09135211a464b9eea9b5ead72a4c6621657cc3fa6ea13c501bc53cd570383` | `e1e1e81b57eabb30a50ebf24e29ba2b582271e4f` | Source SHA-256 `3F16A429BA870A86F6587633DD3F6ED2E3847610ABCB8FF86F40AE09361BAA79`, captured from authorized source worktree; migrated and extended with synthetic tests. Full-diff review READY 2026-11-09. | Include; verify valid, missing, altered, and misplaced snapshots. |
| `application/tests/test_document_contract.py` | `8a32c59ed03c3c2e746931b6218cd8b1a0358ed3219c039fd931426e66a1f8ff` | `eb484ed384d072739d6e24f0579284e9377311fd` | Synthetic contract test authored in canonical clone under owner grant; full-diff review READY 2026-11-09. | Include; assert schema reference and allowed event context. |
| `application/tests/test_local_intake_app.py` | `c4a893a45e1b80d5dba67edc6994a0b75df614d1de56bc7d511a16d14487efcb` | `ee6a9b8d5e1d92af8170d37d05852d5accb21b02` | Synthetic route/UI test authored in canonical clone under owner grant; full-diff review READY 2026-11-09. | Include; prove valid selection and reject a family absent from snapshots. |
| `application/DATA_SCHEMA.md` | `c3c54daa2516c5b7e5a065110b74f15410fc6f62beecae7b9c6a6d4cc698424f` | `2a91c2a57f73d77883b9a1b8b2f31c90d9b46d3e` | Canonical documentation updated from the current schema, without historical status copied. | Include; document 0.1.0/0.2.0 behavior and binding. |
| `application/CURRENT_STATE.md` | `746c766b64bd1a34e1039bd6cc9687143518ac469090cdb664bd57d8eca1a024` | `9bd72365c6633a78d40038eb45299405b9a40649` | Canonical status updated with dated local and GitHub run results and limits. | Include; mark this tranche candidate, not accepted. |
| `docs/migration/2026-11-09-r6-custom-family-ledger-addendum.md` | Part of its own containing commit | New file | Migration manifest authored in canonical clone. | Include; record file provenance, hashes, scope and exclusions. |

Canonical base: `OCR-dev/main` at `90ae4f9111af5ddad9272ffc20a96acb5311a2f5`. The two migrated-file base blobs match the corresponding blobs at source parent `3b7d6325a374d2168d3c6ebaa65252407efa5a73`. Schema and UI are new canonical edits under the subsequent owner grant; they were not copied from the source checkout. `contracts.py` is unchanged because the canonical base already validates schema 0.2.0 snapshots.

The source-file SHA-256 values above were recorded from the authorized source worktree before migration. The independent reviewer confirmed that they match the prior provenance record and are internally consistent with the migrated ledger, but could not recompute the source-file hashes from commit `1f8f423c76f3e831d1ebe3319215ae322f2d52d4` because that source commit is not present in this canonical clone.

## Review, verification, and limits

- Independent reviews: the original source diff was READY for ledger-only behavior. A separate review of this complete canonical migration diff (all 9 paths, including schema, UI, tests and manifest) returned READY on 2026-11-09. It found no blocking correctness or security issue; GitHub formal approval and merge remain separate and pending. The PR #94 Actions run `42603058089` passed Analyze (actions), Analyze (python), CodeQL, and both required-check runs.
- Source test command: `PYTHONPATH=src;tests python -B -m unittest -q test_review_ledger` — 19 synthetic tests passed on the source branch.
- Canonical test commands: `PYTHONPATH=application\\src;application\\tests python -B -m unittest -q test_document_contract test_review_ledger` — 48 synthetic tests passed; direct calls to the built-in and custom-family UI regressions passed. The two new regressions were first run RED. `py_compile`, schema JSON parsing/reference checks, and `git diff --check` passed. No `pytest` installation was attempted.
- The canonical record contract already supports schema `0.2.0`; `contracts.py` required no change. Formal JSON Schema meta-validation remains unavailable because the validator is not installed and dependency installation is outside this change.
- No dependencies, models, workflow, permissions, or secrets are added or changed.
- The current canonical workflow does not explicitly select either `test_review_ledger` or `test_local_intake_app`; a separate CI change is required for those two test modules. Open PRs #36 and #88 already modify the workflow, so this feature PR leaves it unchanged and the handoff is being coordinated separately.
- No real documents, OCR output, R7/R8, Windows-native tests, UI walkthrough, persistent-store behavior, or administrative decisions are included.

## Exclusions

The source repository's `CURRENT_STATE.md` is not copied: the canonical repository maintains its own status history. `contracts.py` is unchanged because its existing 0.2.0 checks already validate the embedded family definitions. No other source files or previous OCR-project artifacts are included.
