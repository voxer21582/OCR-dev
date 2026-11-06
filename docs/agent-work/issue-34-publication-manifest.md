# Issue #34 publication manifest — R6 review ledger foundation

Status: independent code review READY; not a publication authorization by itself.

| Path | Owner | Provenance | SHA-256 | Review | Decision |
|---|---|---|---|---|---|
| `src/alfa_document_intelligence/review_contracts.py` | voxerino | New in-memory OCR2 review contract using R4 candidate and taxonomy APIs | `cd9986e1f6f443dd3d60ebbe12ec7363e775ec3ae80b6984f5ed7b0104f303b3` | Independent code review READY; behavior tests not run locally | Include if accepted |
| `tests/test_review_contracts.py` | voxerino | 19 synthetic tests with candidates, pages, taxonomy, and review events, including changed-evidence regression | `c0b698e099d83dc2c26912f42e6af8cd987836901f058aab051a88cbb462e57d` | Independent code review READY; local execution blocked before discovery by missing `jsonschema` | Include if accepted |
| `docs/ocr/review-ledger-contract.md` | voxerino | R6 technical contract documentation | `0a162a170da9be84e193bc72d392cc1427d71dd84b6cc5141c5eda8a84e41ab1` | Independent code review READY | Include if accepted |
| `README.md` | voxerino | R6 slice and current CI scope documented | `8f0ffc8eb08be57ae0924920e4acee1399164cc7faa6d5336def8ce7ded094f0` | Independent code review READY; count reflects 19 R6 tests, not yet in CI | Include if accepted |
| `docs/superpowers/specs/2026-11-06-r6-review-ledger-design.md` | voxerino | R6 review ledger design derived from product matrix and issue #34 | `4a9bac3201a3bcb1ea1e61e5c141cdb0bec4e10afa08eae9fb667f3bbe5bf5c2` | Independent code review READY | Include if accepted |
| `docs/superpowers/plans/2026-11-06-r6-review-ledger.md` | voxerino | R6 implementation plan | `92ed81c687094bd197d3c4aa4ec43699b514d99ab7012ab8b85b4f54df0e7e66` | Independent code review READY | Include if accepted |
| `docs/agent-work/issue-34-publication-manifest.md` | voxerino | This manifest | not listed (self-reference; included in the commit) | Independent code review READY for implementation scope; manifest hash is self-referential | Include if accepted |

Excluded: all real documents, OCR output, reviewer identities from the OS,
Windows settings, local caches/environments, secrets, and files from the former
OCR project. Public tests contain only synthetic values.

Evidence recorded: independent read-only code review READY; the six exact file
hashes above; `py_compile` passed; `git diff --check` passed; and the test
module contains 19 methods. The CI module allowlist has not yet been extended,
so these tests have not run on GitHub.

Evidence still required: execution of the new explicit synthetic test module on
the locked GitHub runner through a separate CI PR. The local `unittest` attempt
stopped during test-module import, before test discovery, because `jsonschema`
is unavailable in this worktree; `pytest` is also unavailable. No package was
installed. Syntax compilation and `git diff --check` pass locally, but they do
not verify behavior.

Scope limitation: this deliverable has no UI, on-disk history, restart behavior,
or product-level R6 acceptance. Issue #34 remains open until those criteria and
the user-facing walkthrough are completed.
