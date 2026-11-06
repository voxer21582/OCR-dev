# Issue #31 CI manifest — R5 explicit test selection

Status: prepared for independent review and GitHub Actions execution.

| Path | Owner | Provenance | SHA-256 | Review | Decision |
|---|---|---|---|---|---|
| `.github/workflows/ocr2-synthetic-taxonomy.yml` | voxerino | Existing OCR2 synthetic workflow; one explicit unittest module appended | `defaa232f19ada2dbba2daec4659150da957a4f07977772b3178616b944b3e93` | Independent review READY | Include if accepted |
| `README.md` | voxerino | Reproduction command, module list, count updated from 52 to 66; five modules stated consistently | `3bd7225179ead63f2009b219ac017d1218061e4c4617da9821426b9ca334dfd7` | Independent review READY after correction | Include if accepted |
| `docs/agent-work/issue-31-ci-manifest.md` | voxerino | This CI publication record | not listed (self-reference; included in the commit) | Independent review pending | Include if accepted |

## Allowlist

The workflow invokes exactly these modules, without discovery or globbing:

1. `test_taxonomy_registry` — 19 tests
2. `test_taxonomy_binding` — 3 tests
3. `test_ocr_contracts` — 15 tests
4. `test_extraction_contracts` — 15 tests
5. `test_validation_contracts` — 14 tests

Total: 66 synthetic tests. No test module for R7, R8, or issue #8 is selected.

## Preserved workflow controls

- Required check name remains `Taxonomy registry and binding`.
- Existing push, pull request, and manual triggers remain unchanged.
- Existing Ubuntu 24.04 runner, CPython 3.13.18, ten-minute timeout, and
  read-only `contents: read` permissions remain unchanged.
- Both existing GitHub Actions remain pinned to full commit SHAs.
- The existing JSON Schema dependency lock and hash-verifying binary-only pip
  install remain unchanged; no dependency is added.
- No skip condition, path filter, discovery, secret access, real document,
  OCR model, paid service, or paid runner is introduced.

## Required evidence before acceptance

Record the final hashes after review, the existing required-check result, and
the GitHub Actions run for both push and pull request. The R5 module has not
been executed locally in this worktree because `jsonschema` is unavailable;
no package was installed. Green 66-test CI runs will verify the selected
synthetic contracts only, not OCR accuracy or whole-product acceptance.
