# Issue #17 CI expansion manifest

**Prepared:** 2026-11-06
**Base:** `codex/r2-ocr-observation-contract` at `d666463` (R2 PR #18)
**Branch:** `codex/ci-r2-explicit-tests`
**Owner:** `voxerino`
**Scope:** Add the R2 passive observation-contract tests to the existing synthetic CI.

## Exact change

- `.github/workflows/ocr2-synthetic-taxonomy.yml`: add only the explicit module `test_ocr_contracts` after the two existing modules. No discovery, globs, extra jobs, actions, dependencies, secrets, permissions, triggers, or runner changes.
- `README.md`: describe the resulting 37-test allowlist and its limits.
- This manifest records scope and evidence; it contains no runtime or document data.

## Preserved CI contract

- Required check name: `Taxonomy registry and binding` (unchanged).
- Triggers: push to branches, pull request, and manual dispatch (unchanged).
- Runner: standard `ubuntu-24.04`; Python `3.13.18` (unchanged).
- Permissions: `contents: read` at workflow and job level (unchanged).
- Dependencies: existing hash-locked Ubuntu CPython 3.13 lock file (unchanged).
- Actions: existing full-SHA pins (unchanged).
- Explicit tests only: `test_taxonomy_registry`, `test_taxonomy_binding`, `test_ocr_contracts`.
- Expected scope: 19 + 3 + 15 = 37 tests, all synthetic. No OCR engine, models, real documents, Windows runtime, R7/R8, or issue #8 test path is selected.

## Dependency and review

This PR is intentionally stacked on PR #18 so the `test_ocr_contracts` module and implementation are present in its base. Its diff against that base contains only the workflow and this documentation update. Do not retarget it to `main` until the R2 base has been integrated; no merge is requested here.

## Verification record

- Local `test_ocr_contracts`: 15 passed on Windows CPython 3.13; the new 257-vertex guard regression passed after first observing the expected RED failure.
- Existing remote check on PR #18: passed on both push and pull_request; each run executes the current 22-test allowlist.
- The initial GitHub Actions verification passed both events with 36 tests on the older base `c51bc96`: [push run 42188279476](https://github.com/voxer21582/OCR-dev/actions/runs/42188279476) and [pull request run 42188329769](https://github.com/voxer21582/OCR-dev/actions/runs/42188329769). A later run on head `23ff40c` also passed 36 tests because GitHub held the PR base at `c51bc96`; these historical runs do not execute the new 257-vertex regression.
- This CI branch now includes PR #18 through base `d666463`; a new push/PR run must report 37 tests before the CI change is considered verified.
- The combined 37-test suite was not run in the restricted local environment because the locked dependency closure is Ubuntu-specific and `jsonschema` is absent there. GitHub Actions on Ubuntu is the designated compatible runner for this combined allowlist.

This CI result is limited to synthetic contract coverage and is not product acceptance.
