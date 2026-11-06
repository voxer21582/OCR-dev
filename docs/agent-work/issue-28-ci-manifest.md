# Issue #28 CI expansion manifest — R4 candidate tests

**Prepared:** 2026-11-06
**Base:** feature PR #29 branch `codex/r4-field-candidate-contract` at `86175d61c8c3a473b8ea08611efef647d4798c03`
**Candidate branch:** `codex/ci-r4-explicit-tests`
**Owner:** `voxerino`
**Scope:** add only the explicitly named R4 test module to the existing synthetic workflow.

## Included files

| File | SHA-256 | Owner / provenance | Review | Reason |
| --- | --- | --- | --- | --- |
| `.github/workflows/ocr2-synthetic-taxonomy.yml` | `8BEFA90818F52D9FA715D0CE419A74AC27AC2810D45ED7B404ABD6552852335A` | `voxerino`; existing workflow with one explicit module added | Independent review READY (2026-11-06) | Include the synthetic R4 contract tests without discovery |
| `README.md` | `485A5526FC2222831194A37D69D7FB90C8BE18593A0EFE0486E90B6A44A4A0A8` | `voxerino`; existing README, test command and count update | Independent review READY (2026-11-06) | Keep public workflow instructions accurate |

This manifest does not include itself in the file-hash table. Hashes and review result must be recorded after the diff is frozen.

## Exact test allowlist

- `test_taxonomy_registry` — 19 tests.
- `test_taxonomy_binding` — 3 tests.
- `test_ocr_contracts` — 15 tests.
- `test_extraction_contracts` — 15 tests.

Expected total: 52 synthetic tests. No discovery, glob, or implicit test collection is used.

## Preserved controls

- Required check remains `Taxonomy registry and binding`.
- Existing push, pull-request, and manual triggers remain unchanged.
- Existing full-SHA action references, `contents: read`, Ubuntu 24.04 runner, CPython 3.13.18, timeout, and hash-locked dependency closure remain unchanged.
- No dependency, secret, runner, workflow, permission, branch protection, or security setting is added or changed beyond the single explicit test command argument.

## Scope exclusions and verification limits

- No R7/R8 or issue #8 tests; no real document, OCR output, model, runtime, network service, or paid runner.
- R4 local test execution is unavailable in the isolated Python 3.13.15 environment because `jsonschema` is absent; no package was installed. PR #29's current green check only executes the existing 37-test allowlist.
- Independent review of the exact workflow/README/manifest diff: READY. The reviewer verified test count, unchanged workflow controls, and both listed SHA-256 values.
- GitHub Actions on head `f3235154133bf29bee1d64dbcaecc6f503238baa` passed all 52 tests on both events: [push run 42214402336](https://github.com/voxer21582/OCR-dev/actions/runs/42214402336) and [pull_request run 42214503080](https://github.com/voxer21582/OCR-dev/actions/runs/42214503080). Both logs report `Ran 52 tests` and both required checks concluded SUCCESS.
- Even a green 52-test run verifies only named synthetic contracts. It does not establish OCR accuracy, R4 real-document coverage, Windows runtime readiness, A4/A5, or application acceptance.
