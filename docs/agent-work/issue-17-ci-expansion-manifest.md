# Issue #17 CI expansion manifest

**Prepared:** 2026-11-06
**Base:** `codex/r2-ocr-observation-contract` at `c51bc96` (R2 PR #18)
**Branch:** `codex/ci-r2-explicit-tests`
**Owner:** `voxerino`
**Scope:** Add the R2 passive observation-contract tests to the existing synthetic CI.

## Exact change

- `.github/workflows/ocr2-synthetic-taxonomy.yml`: add only the explicit module `test_ocr_contracts` after the two existing modules. No discovery, globs, extra jobs, actions, dependencies, secrets, permissions, triggers, or runner changes.
- `README.md`: describe the resulting 36-test allowlist and its limits.
- This manifest records scope and evidence; it contains no runtime or document data.

## Preserved CI contract

- Required check name: `Taxonomy registry and binding` (unchanged).
- Triggers: push to branches, pull request, and manual dispatch (unchanged).
- Runner: standard `ubuntu-24.04`; Python `3.13.18` (unchanged).
- Permissions: `contents: read` at workflow and job level (unchanged).
- Dependencies: existing hash-locked Ubuntu CPython 3.13 lock file (unchanged).
- Actions: existing full-SHA pins (unchanged).
- Explicit tests only: `test_taxonomy_registry`, `test_taxonomy_binding`, `test_ocr_contracts`.
- Expected scope: 19 + 3 + 14 = 36 tests, all synthetic. No OCR engine, models, real documents, Windows runtime, R7/R8, or issue #8 test path is selected.

## Dependency and review

This PR is intentionally stacked on PR #18 so the `test_ocr_contracts` module and implementation are present in its base. Its diff against that base contains only the workflow and this documentation update. Do not retarget it to `main` until the R2 base has been integrated; no merge is requested here.

## Verification record

- Local `test_ocr_contracts`: 14 passed on Windows CPython 3.13.15.
- Existing remote check on PR #18: passed on both push and pull_request; each run executes the current 22-test allowlist.
- CI run for this PR: pending until pushed and evaluated by GitHub Actions.
- The combined 36-test suite was not run in the restricted local environment because the locked dependency closure is Ubuntu-specific and PyPI DNS was unavailable. GitHub Actions is the designated compatible runner for this combined allowlist.

This CI result is limited to synthetic contract coverage and is not product acceptance.
