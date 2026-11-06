# Issue #31 publication manifest — R5 structural validation

Status: prepared for review; not a publication authorization by itself.

| Path | Owner | Provenance | SHA-256 | Review | Decision |
|---|---|---|---|---|---|
| `src/alfa_document_intelligence/validation_contracts.py` | voxerino | New OCR2 contract in this branch, using repository R4 and taxonomy APIs | `4348650e839fc74672c69940b4fa69a06483040095fcf66eae5d861582e905b8` | Independent review READY | Include if accepted |
| `tests/test_validation_contracts.py` | voxerino | New tests using synthetic catalog, candidate, page, and region values | `900b307948f99a07c1a57c8a6533b15e3d0b762fc0d7a4882c840cfb7b3f9027` | Independent review READY; local execution blocked by missing `jsonschema` | Include if accepted |
| `docs/ocr/validation-contract.md` | voxerino | New contract documentation derived from the R5 design | `376d20d3fa7fd27a1dd3c51674fe4089acd9fc11ec740fefcebc2d59fdb650f6` | Independent review READY | Include if accepted |
| `README.md` | voxerino | Scoped addition describing R5 and accurately stating its tests are not yet in CI | `56fecfe41f7e3917ba379787161b0f9de839c67da6144d12f97bcfc16be2dc82` | Independent review READY after overview fix | Include if accepted |
| `docs/superpowers/specs/2026-11-06-r5-structural-validation-design.md` | voxerino | R5 design for this issue | `5324e7b03e4997fcd0a61ccce283619d97247a5fef8ab8fa6ded751e43786d7a` | Independent review READY | Include if accepted |
| `docs/superpowers/plans/2026-11-06-r5-structural-validation.md` | voxerino | Implementation plan with verified R5/CI outcomes | `7d97f781cfb994811b1ccd7e6425d00c76c224e93707efb834c2fd1b9c4a0e5b` | Independent review READY | Include if accepted |
| `docs/agent-work/issue-31-publication-manifest.md` | voxerino | This release manifest | not listed (self-reference; included in the commit) | Independent review READY | Include if accepted |

Excluded: all real documents, OCR outputs, local environments, caches, run logs,
credentials, and files from the former OCR project. No such material is required
or included by this feature. Generated Python bytecode is temporary and must be
removed before publication.

Evidence: independent review READY; `py_compile` and diff checks passed. The
existing 52-test check passed on feature PR #32. The separate explicit CI PR
#33 passed 66 synthetic tests (`OK`) on both the push run
https://github.com/voxer21582/OCR-dev/actions/runs/42217768551 and pull-request
run https://github.com/voxer21582/OCR-dev/actions/runs/42217818022. Local test
execution could not import `jsonschema` because it is unavailable in this
worktree; no dependency was installed. This is an environment limitation, not
a test failure or a local pass.
