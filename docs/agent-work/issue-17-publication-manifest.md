# Issue #17 publication manifest

**Prepared:** 2026-11-06

**Base:** `main` at `b9f1e021a4fc720a3388849b1d0b2b31586e7b85`

**Candidate branch:** `codex/r2-ocr-observation-contract`

**Owner:** `voxerino` (OCR2 owner)

**Purpose:** publish a passive OCR observation contract and synthetic tests. This manifest does not accept OCR, a runtime, A4, or the complete R2 requirement.

## Included files

| File | SHA-256 | Provenance | Review | Reason |
| --- | --- | --- | --- | --- |
| `src/alfa_document_intelligence/ocr_contracts.py` | `24895FBCAECFBDF7ADFE3A209BF0F963FB5BE87AFCAA44A7186402AEE294F93F` | Authored for OCR2 from the accepted R2 product criteria; no code copied from another OCR project | Independent review READY (2026-11-06) | Adds only validated, engine-neutral values and a protocol; no engine or file access |
| `tests/test_ocr_contracts.py` | `E2B5D164679327407E693FA35BC8AF8B12E01FF83C354C9A770C50A6C0526B4D` | New synthetic fixtures authored for this contract | Independent review READY (2026-11-06) | Exercises provenance, geometry, uncertainty, state consistency, and identity checks. Dedicated bow-tie regression expects `ocr_region_invalid`. |
| `docs/ocr/observation-contract.md` | `413C557217F6B5F228617E60F8C25AA767C9452A9BAA05F3D4475E4EFBB920B9` | Authored for this public contract | Independent review READY (2026-11-06) | States API meaning and limits without claiming an operational engine; documents the self-intersection counterexample and stable error code. |
| `README.md` | `1B1E427D3CDD15AD5A2D0FC5EF8CD16C6F7E090051D9C61BD15579859BC4AE38` | Existing public README with a scope update and contract link | Independent review READY (2026-11-06) | Keeps the repository description accurate and discloses that current CI does not yet run the new test module |
| `docs/superpowers/specs/2026-11-06-r2-ocr-observation-contract-design.md` | `E18B5E207BB083A682C6CF62CAD03F3C5D8686E02BF4C7CE6FA5D39B9E6C8600` | Design derived from R2 acceptance criteria | Independent review READY (2026-11-06) | Records the engine-neutral design, concrete polygon self-intersection case, and deferred choices |
| `docs/superpowers/plans/2026-11-06-r2-ocr-observation-contract.md` | `34F28BC8602293CFDDD10B53753192DA182D53A2FB0EFFF7788B11E963E121A5` | Execution plan for issue #17 | Independent review READY (2026-11-06) | Records files, tests, CI separation, non-goals, and prohibits discovery in favor of an explicit test allowlist |

The manifest does not include itself in the file-hash table. Record its own SHA-256 and the final review evidence in the PR after the content is frozen.

## Exclusions

- OCR application code, engines, models, runtime bundles, page renderers, and dependency changes.
- Data from the original OCR project, real or derived documents, OCR output, personal data, credentials, private dossiers, and temporary wheel artifacts.
- GitHub Actions workflow changes; these are prepared in a separate PR as required by the issue scope.
- R7/R8 implementation or tests, issue #8, Windows configuration, and Google deployment.
- The ignored `.superpowers/sdd/` task ledger; it is local execution bookkeeping, not a product artifact.

## Verification status

- The new contract test module passed 14 tests on Windows CPython 3.13.15 (`python -B -m unittest -v test_ocr_contracts`).
- A fresh combined 36-test Windows run is not yet available: the task-scoped Python environment lacks `jsonschema`; network DNS blocked PyPI access in the restricted shell, and the hash-locked Linux dependency file cannot be applied to Windows wheels. No dependency was added to the repository. GitHub Actions on Ubuntu remains the intended combined verification environment.
- `py_compile` on the production module and test module passed. `git diff --check` passed with Git line-ending warnings only.
- Independent reviewer `review_r2_final` re-reviewed the final six-file manifest and scope on 2026-11-06: READY. Review confirmed the allowlist, no-discovery boundary, concrete self-intersection case, stable error-code assertion, and no blocked/runtime/real-data paths. Reviewer did not run tests.
- The existing GitHub check still runs only the 22 taxonomy tests; workflow expansion is a separate PR. With the dedicated regression test, the explicit CI suite will contain 36 tests (22 taxonomy + 14 OCR contract).
- No OCR, model, runtime, native Windows, real-data, A4, R7, R8, or full-application test was run.

This heuristic manifest and test result are not a DLP guarantee, OCR accuracy evaluation, runtime acceptance, or product release.
