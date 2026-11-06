# Issue #22 — R1 stream-test CI manifest

**Prepared:** 2026-11-06  
**Base:** `codex/r1-stream-preflight` at `7f3f936cd077eca927889b0cb836c9afe66e6340`  
**Candidate branch:** `codex/ci-r1-stream-tests`  
**Purpose:** CI-only follow-up for the synthetic stream tests introduced by the base PR. This branch changes no application code or tests.

## Included files

| File | SHA-256 | Provenance and reason |
| --- | --- | --- |
| `.github/workflows/ocr2-synthetic-taxonomy.yml` | `7eb2a1e0120af6928d15c4bacd8c0c7d1b6054b6b7ab50eeaf99c2f2571283f0` | Existing workflow; adds only the explicit `test_source_stream` module. |
| `README.md` | `28801ab12d76d0dd50e0918305e1471c8aaa5cc05f170bb14cde103529c8d9ae` | Updates exact test count, module list and local reproduction command. |

The manifest is control metadata and is not self-hashed. Independent review of the exact diff is READY; it verified both listed hashes, scope, explicit test count, and preserved workflow invariants.

## Preserved workflow invariants

- Required check name remains `Taxonomy registry and binding`.
- `push`, `pull_request`, and `workflow_dispatch` triggers remain unchanged.
- Existing full-SHA action pins, `contents: read`, Ubuntu 24.04 runner, CPython 3.13.18, ten-minute timeout and hash-locked dependencies remain unchanged.
- No discovery, glob, additional workflow/action/dependency/secret, permission or protection change.
- Explicit allowlist gains only `test_source_stream`; expected suite is 52 synthetic tests (19 registry + 3 binding + 14 OCR contract + 7 byte source + 9 stream source).

## Scope exclusions

No R7/R8 or issue #8 tests, real documents, OCR output, credentials, model, decoder, path-opening behavior, install, Windows configuration, or paid runner is added or invoked. CI success does not establish complete R1 or product acceptance.

## Verification

Independent review is READY. The base feature worktree previously reported 30 passing synthetic tests, including all nine stream tests. This CI-only change has no GitHub Actions run record yet; remote checks must be read back after publication. Local tests were not rerun because only workflow documentation/configuration changed.
