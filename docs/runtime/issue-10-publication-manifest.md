# Issue #10 publication manifest

**Prepared:** 2026-11-12

**Base:** CI candidate `codex/ci-remove-store-dependent-selectors` at `c49fe79dbb783ba5258f8e0635e94680f4cb76da`, stacked on protected `main` at `4271447da4505571ca9087264e18c4a15592b1c8`.

**Scope:** public, documentation-only proposal for [issue #10](https://github.com/voxer21582/OCR-dev/issues/10). The issue remains open. This proposal does not authorize opening documents, starting the pilot, changing Windows, installing/downloading packages or models, or touching the application archive.

## Included content

| File | SHA-256 | Owner | Provenance | Review and inclusion reason |
| --- | --- | --- | --- | --- |
| `docs/runtime/issue-10-pilot-protocol-proposal.md` | `161AE115652E814E2A159FBE66736E7DF9E8C8BC92AAF63A44A8CFF01D7A4704` | `voxerino` (project owner; author confirmed in this chat) | Authored for public OCR2 from issue #10, the owner's recorded choices for local use, real expense documents, batch size, source of truth and retention, and the accepted issue #9 runtime direction. No private files, code, data, OCR output, or hardware identifiers were copied. | Independent review pending. Included to turn known requirements into a reviewable local-pilot proposal while keeping unresolved choices and runtime/product gates visible. |

## Excluded content

- Expense notes, receipts, file names, local paths, OCR text, extracted values, hashes of real documents, and all other real or derived user data.
- Local ECC plans, test logs, private environment inventories, model/runtime artifacts, dependency locks, installer files, and temporary outputs.
- Application source, tests, workflows, and any R7/R8, archive, restore, export, deletion, backup, or lifecycle implementation.
- The current local CycloneDX draft and detailed package/binary inventories; their provenance, schema validation, completeness and redistribution review remain open.

## Verification and controls

- `git diff --check`: passed for the working tree before adding this manifest; repeat against the complete staged diff before publication.
- No functional tests apply to this document-only proposal. No documents, OCR, browser, installer, runtime, archive, or Windows settings were accessed or tested.
- The branch is based on the reviewed CI candidate that excludes the approved store-dependent selectors. Opening a PR from this branch is expected to run the existing explicit synthetic allowlist only; no workflow or required check is changed here.
- The independent reviewer must examine the exact proposal and this manifest before the branch is published. Recompute both content hashes after final edits.
- A public-content review cannot verify privacy or deletion behavior of the application. The protocol explicitly keeps those product checks blocked until R7/R8 are formally cleared.

The proposal is a plan, not an accepted pilot, quality result, runtime qualification, or product release.
