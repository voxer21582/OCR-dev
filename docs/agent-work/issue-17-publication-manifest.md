# Issue #17 publication manifest

**Prepared:** 2026-11-06

**Base:** `main` at `b9f1e021a4fc720a3388849b1d0b2b31586e7b85`

**Candidate branch:** `codex/r2-ocr-observation-contract`

**Owner:** `voxerino` (OCR2 owner)

**Purpose:** publish a passive OCR observation contract and synthetic tests. This manifest does not accept OCR, a runtime, A4, or the complete R2 requirement.

## Included files

| File | SHA-256 | Provenance | Review | Reason |
| --- | --- | --- | --- | --- |
| `src/alfa_document_intelligence/ocr_contracts.py` | `0FC7B465E89627393D23147DDD1BA79CB70427D809C4E8338326E2DE371BE563` | Authored for OCR2 from the accepted R2 product criteria; no code copied from another OCR project | Fresh independent review pending | Adds validated engine-neutral values and protocol; caps region polygons at 256 vertices before quadratic geometry checks; no engine or file access |
| `tests/test_ocr_contracts.py` | `EE1BF6F87947AE1987E89701050E8F1E372E33355362647A6D113817EA442716` | New synthetic fixtures authored for this contract | Fresh independent review pending | 15 synthetic contract tests, including bow-tie rejection and the 257-vertex resource-bound regression |
| `docs/ocr/observation-contract.md` | `FC5D3B5689802E951F4F0367CEE86FC2D5125C5EB0D86473D63E6515D3299C25` | Authored for this public contract | Fresh independent review pending | Documents both the bow-tie counterexample and the 256-vertex bound with stable error behavior |
| `README.md` | `1B1E427D3CDD15AD5A2D0FC5EF8CD16C6F7E090051D9C61BD15579859BC4AE38` | Existing public README with a scope update and contract link | Independent review READY (2026-11-06) | Keeps the repository description accurate and discloses that current CI does not yet run the new test module |
| `docs/superpowers/specs/2026-11-06-r2-ocr-observation-contract-design.md` | `3FAE1D82A179C15A6FA43E91339F4E495D9377C3632E90717CED400203EA27AA` | Design derived from R2 acceptance criteria | Fresh independent review pending | Records the engine-neutral design, self-intersection case, 256-vertex bound, and deferred choices |
| `docs/superpowers/plans/2026-11-06-r2-ocr-observation-contract.md` | `AF67BA9F7D51835F783B2A7A5B9A2D10F904A91EBCF20B9AAA8E578F30474739` | Execution plan for issue #17 | Fresh independent review pending | Records files, tests, CI separation, resource-bound criterion, non-goals, and explicit test allowlist |

The manifest does not include itself in the file-hash table. Record its own SHA-256 and the final review evidence in the PR after the content is frozen.

## Exclusions

- OCR application code, engines, models, runtime bundles, page renderers, and dependency changes.
- Data from the original OCR project, real or derived documents, OCR output, personal data, credentials, private dossiers, and temporary wheel artifacts.
- GitHub Actions workflow changes; these are prepared in a separate PR as required by the issue scope.
- R7/R8 implementation or tests, issue #8, Windows configuration, and Google deployment.
- The ignored `.superpowers/sdd/` task ledger; it is local execution bookkeeping, not a product artifact.

## Verification status

- The contract test module passes 15 tests on Windows CPython 3.13 (`python -B -m unittest -v test_ocr_contracts`). The new 257-vertex regression failed before the implementation change with `OCRContractError not raised` and passes after the early 256-vertex guard.
- A fresh combined 36-test Windows run is not yet available: the task-scoped Python environment lacks `jsonschema`; network DNS blocked PyPI access in the restricted shell, and the hash-locked Linux dependency file cannot be applied to Windows wheels. No dependency was added to the repository. GitHub Actions on Ubuntu remains the intended combined verification environment.
- `py_compile` on the production module and test module passed. `git diff --check` passed with Git line-ending warnings only.
- The earlier independent READY applied to the prior six-file manifest and did not cover the 256-vertex bound. Fresh independent review is pending for the updated files.
- The separate CI PR has an explicit allowlist and currently records 36 tests; it must be updated and rerun after this added regression so the expected total is 37 (22 taxonomy + 15 OCR contract).
- No OCR, model, runtime, native Windows, real-data, A4, R7, R8, or full-application test was run.

This manifest records an additional resource-boundary correction requested by independent review. The final state is pending fresh independent review and GitHub Actions rerun. This heuristic manifest and test result are not a DLP guarantee, OCR accuracy evaluation, runtime acceptance, or product release.
