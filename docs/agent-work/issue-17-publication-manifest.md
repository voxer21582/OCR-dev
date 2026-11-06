# Issue #17 publication manifest

**Prepared:** 2026-11-06

**Base:** `main` at `b9f1e021a4fc720a3388849b1d0b2b31586e7b85`

**Candidate branch:** `codex/r2-ocr-observation-contract`

**Owner:** `voxerino` (OCR2 owner)

**Purpose:** publish a passive OCR observation contract and synthetic tests. This manifest does not accept OCR, a runtime, A4, or the complete R2 requirement.

## Included files

| File | SHA-256 | Provenance | Review | Reason |
| --- | --- | --- | --- | --- |
| `src/alfa_document_intelligence/ocr_contracts.py` | `0FC7B465E89627393D23147DDD1BA79CB70427D809C4E8338326E2DE371BE563` | Authored for OCR2 from the accepted R2 product criteria; no code copied from another OCR project | Independent review READY (2026-11-06, commit `dc94b3e`) | Adds validated engine-neutral values and protocol; caps region polygons at 256 vertices before quadratic geometry checks; no engine or file access |
| `tests/test_ocr_contracts.py` | `EE1BF6F87947AE1987E89701050E8F1E372E33355362647A6D113817EA442716` | New synthetic fixtures authored for this contract | Independent review READY (2026-11-06, commit `dc94b3e`) | 15 synthetic contract tests, including bow-tie rejection and the 257-vertex resource-bound regression |
| `docs/ocr/observation-contract.md` | `FC5D3B5689802E951F4F0367CEE86FC2D5125C5EB0D86473D63E6515D3299C25` | Authored for this public contract | Independent review READY (2026-11-06, commit `dc94b3e`) | Documents both the bow-tie counterexample and the 256-vertex bound with stable error behavior |
| `README.md` | `1B1E427D3CDD15AD5A2D0FC5EF8CD16C6F7E090051D9C61BD15579859BC4AE38` | Existing public README with a scope update and contract link | Independent review READY (2026-11-06) | Keeps the repository description accurate and discloses that current CI does not yet run the new test module |
| `docs/superpowers/specs/2026-11-06-r2-ocr-observation-contract-design.md` | `3FAE1D82A179C15A6FA43E91339F4E495D9377C3632E90717CED400203EA27AA` | Design derived from R2 acceptance criteria | Independent review READY (2026-11-06, commit `dc94b3e`) | Records the engine-neutral design, self-intersection case, 256-vertex bound, and deferred choices |
| `docs/superpowers/plans/2026-11-06-r2-ocr-observation-contract.md` | `AF67BA9F7D51835F783B2A7A5B9A2D10F904A91EBCF20B9AAA8E578F30474739` | Execution plan for issue #17 | Independent review READY (2026-11-06, commit `dc94b3e`) | Records files, tests, CI separation, resource-bound criterion, non-goals, and explicit test allowlist |

The manifest does not include itself in the file-hash table. Record its own SHA-256 and the final review evidence in the PR after the content is frozen.

## Exclusions

- OCR application code, engines, models, runtime bundles, page renderers, and dependency changes.
- Data from the original OCR project, real or derived documents, OCR output, personal data, credentials, private dossiers, and temporary wheel artifacts.
- GitHub Actions workflow changes; these are prepared in a separate PR as required by the issue scope.
- R7/R8 implementation or tests, issue #8, Windows configuration, and Google deployment.
- The ignored `.superpowers/sdd/` task ledger; it is local execution bookkeeping, not a product artifact.

## Verification status

- The contract test module passes 15 tests on Windows CPython 3.13 (`python -B -m unittest -v test_ocr_contracts`). The new 257-vertex regression failed before the implementation change with `OCRContractError not raised` and passes after the early 256-vertex guard.
- A fresh combined 37-test Windows run is not available: the task-scoped Python environment lacks `jsonschema`; the hash-locked Linux dependency file cannot be applied to Windows wheels. No dependency was added to the repository. GitHub Actions on Ubuntu is the designated combined verification environment.
- `py_compile` on the production module and test module passed. `git diff --check` passed with Git line-ending warnings only.
- A fresh independent review of the exact six-file update at commit `dc94b3e` is READY; the reviewer verified the early cap, 257-vertex regression, stable error, all six hashes, and no unrelated or blocked paths.
- The required check on PR #18 passed the unchanged 22-test taxonomy allowlist on push and pull_request: [push run 42208058773](https://github.com/voxer21582/OCR-dev/actions/runs/42208058773), [pull_request run 42208067113](https://github.com/voxer21582/OCR-dev/actions/runs/42208067113). These runs do not execute the R2 test module.
- The prior CI PR runs of 36 tests used the old base `c51bc96`; they do not include the new 257-vertex regression. The CI branch is being synchronized to commit `dc94b3e` and must pass 37 explicit tests before its evidence is current.
- No OCR, model, runtime, native Windows, real-data, A4, R7, R8, or full-application test was run.

This manifest records an additional resource-boundary correction requested by independent review. The final state is pending fresh independent review and GitHub Actions rerun. This heuristic manifest and test result are not a DLP guarantee, OCR accuracy evaluation, runtime acceptance, or product release.
