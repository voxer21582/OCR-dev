# Issue #10 publication manifest

**Prepared:** 2026-11-05

**Base:** `main` at `b9f1e021a4fc720a3388849b1d0b2b31586e7b85`

**Candidate branch:** `codex/issue-10-a5-decision-register`

**Scope:** blank, public-safe A5 decision template for [issue #10](https://github.com/voxer21582/OCR-dev/issues/10). It records no decision and authorizes no pilot.

## Included content files

| File | SHA-256 | Owner | Provenance | Review and inclusion reason |
| --- | --- | --- | --- | --- |
| `docs/pilot/a5-decision-register-template.md` | `FEB3967B95B37B0F8314EB1DB14455EDC11681382F08DA6F19A7F657964185F4` | OCR2 development coordinator | Authored for issue #10 from its public acceptance categories and the project's public data/safety boundary; no private targets, sample identities, source dossier, code, model, or runtime artifact copied | Independent review pending. Included as a blank owner-decision form that makes unresolved prerequisites explicit without deciding them. |

## Excluded material

- Actual sample documents, paths, identifiers, OCR text, labels, benchmark records, and derived outcomes.
- Private A5 targets, approval identities, budgets, and decision records.
- OCR2 application code, runtime/model artifacts, dependency files, and workflow changes.
- R7/R8 implementation, tests, Windows operations, and pilot execution.

## Verification and review boundary

- The candidate is documentation only; no tests, OCR, data access, or Windows operations are authorized or claimed.
- A simple credential-pattern scan and final staged-diff check are required before publication; neither is a DLP guarantee.
- The existing taxonomy CI may run on the branch push and PR. It does not verify A5 decisions or authorize the pilot.
- The manifest itself is control metadata; its final hash and the independent review verdict will be recorded in the PR description after final review.
