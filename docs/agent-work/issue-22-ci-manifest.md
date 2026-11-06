# Issue #22 — R1 CI change manifest

**Prepared:** 2026-11-06
**Base:** `codex/r1-source-preflight` at `6a355d2f09485137acb71dae8752e4e83a504890`
**Candidate branch:** `codex/ci-r1-source-test`
**Review:** independent workflow review READY on the exact staged three-file diff at base `6a355d2f09485137acb71dae8752e4e83a504890`; no findings. The reviewer verified the single-module workflow change, unchanged workflow invariants, accurate README count, and matching content hashes.

## Included files

| File | SHA-256 | Owner | Provenance | Review and inclusion reason |
| --- | --- | --- | --- | --- |
| `.github/workflows/ocr2-synthetic-taxonomy.yml` | `8e05c05872e6d2902bf8ed7616c91f25b7b88a1624a8a66548dd40621022f504` | OCR2 coordinator | Existing PR #19 workflow, changed by one explicit `test_source_intake` module entry | READY; extends the current required workflow to the new synthetic test module only. |
| `README.md` | `02ddaf1b37a29fc7257bf8842e9d89c8994ee7e372ebfca172416622c2ce8d7c` | OCR2 coordinator | Existing PR #23 README, updated to document the four-module CI scope and limits | READY; keeps test count and reproduction command accurate. |

The manifest itself is control metadata and is not self-hashed. The new test module is provided by base PR #23 and is not modified by this CI-only change.

## Workflow invariants

- Required check remains `Taxonomy registry and binding`.
- Existing `push`, `pull_request` and `workflow_dispatch` triggers are unchanged.
- Existing full-SHA action pins are unchanged.
- `contents: read` permissions are unchanged.
- `ubuntu-24.04`, CPython `3.13.18`, 10-minute timeout and the existing hash-locked dependency file are unchanged.
- No discovery, glob, new workflow, new action, dependency, secret, permission, protection, or paid runner is added.
- The explicit allowlist adds only `test_source_intake`, moving the expected suite from 36 to 42 synthetic tests.

## Verification and limits

- The source-preflight test module passed locally: 6 tests, synthetic bytes only.
- GitHub Actions passed the exact 42-test allowlist on both the branch push ([run 42195965443](https://github.com/voxer21582/OCR-dev/actions/runs/42195965443)) and pull request ([run 42196030057](https://github.com/voxer21582/OCR-dev/actions/runs/42196030057)). Both logs report `Ran 42 tests`; both include all six `test_source_intake` tests.
- Local taxonomy modules could not be run because `jsonschema` is absent from the selected environment; no dependency was installed. The GitHub runner uses the existing lock.
- The run links above use the workflow and test module hashes listed in this manifest. The recorded workflow runs predate this evidence-only manifest update; the workflow file and source/test code are unchanged. Independent workflow review is READY.
- The added module does not prove file validity, page count, decoding, OCR, Windows runtime behavior, or full R1/A4 acceptance.
