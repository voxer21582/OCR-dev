# Public migration manifest: document-intelligence to OCR-dev

Date: 2026-11-07

## Scope

Selective migration proposal into `application/` on public repository `voxer21582/OCR-dev`. The private source repository remains untouched. No files from the legacy OCR project, real documents, OCR outputs, model files, or credentials are included. The nested app path avoids collisions with OCR-dev's taxonomy package.

Source: private OCR2 Document Intelligence checkout, HEAD `e89305f19e4562d2026d252fdd2cf669fd154e3d`.
Target: `voxer21582/OCR-dev`, branch `codex/unify-document-intelligence`, base `main` `b9f1e021a4fc720a3388849b1d0b2b31586e7b85`.

The CSV records every tracked source file as included, excluded, or transformed, lists every untracked source file individually, and identifies both manifest artifacts. The manifest cannot hash itself; the final commit ID is the integrity reference for those two files. Five untracked local files are listed individually and excluded because they are uncommitted and unreviewed. Concurrent changes in the private source checkout remain untouched and are not included. Open OCR-dev PRs remain untouched.

## Inventory

```text
source tracked files=130
source untracked files=5
exclude=54
include=73
new=4
transform=9
```

## File-by-file decisions

The manifest also records the existing OCR-dev README transformation.

See [the CSV manifest](2026-11-07-document-intelligence-public-migration.csv).

## Outstanding publication gates

- Independent security/privacy/content review of every included file.
- Reconcile any collisions or duplicated governance with the root repository.
- Confirm the manifest and final diff before publishing the branch/PR.
- The existing required CI executes only taxonomy tests; it does not validate the application.


## Independent review

An independent code review returned READY for publication of this initial migration slice at application tree commit `f76b4e1`. The reviewer confirmed the file manifest, synthetic-only content scope, absence of secret/email/user-path matches, no binary model/document artifacts, clean relative documentation links, and unchanged root required workflow. Per-file `review_status` values stating “pending” describe manifest assembly time and are superseded by this review record. This does not complete repository unification: concurrent private-source changes remain preserved and unported.

## Incremental follow-up — 2026-11-08 (PR #43)

This supplemental CSV records the 13 application/documentation/test paths in PR #43. The source reference is the OCR2 Document Intelligence checkout at HEAD `e89305f19e4562d2026d252fdd2cf669fd154e3d` plus a dirty working-tree snapshot recorded on 2026-11-08; source file hashes are raw per-file hashes at that snapshot. The public target is PR #43 at code snapshot `651b8b39e7203ba763c5c9b1319e1601ce2ef880`, based on PR #41 (`64bd4f4444bfc8c6f9c2a0358b13f857961fbb8e`); `main` remains at `86c9398905fb4baf4a54b58b303ddf8325c4e768`. Hashes in the CSV refer to that target snapshot; this manifest-only follow-up does not alter those files. The repository license is MIT, as previously approved by the owner; this tranche adds no external dependency or third-party code.

The supplement is limited to files in this tranche. Modified source files are marked `transformed` because only reviewed deltas were selected; the remaining dirty source changes are excluded. Two generated target files have no private-source counterpart. The source checkout was not modified. At inventory time it had 51 tracked modifications and 84 untracked paths; 42 changed paths had an existing public counterpart. None of those other changes is included here.

The PR diff contains no new dependency, model, real document, raw OCR, or binary fixture. A targeted credential-marker scan found no matches. This is not an exhaustive DLP or legal audit. The workflow update is separate in PR #44 and is not a migrated source workflow.

See [the supplemental file-level manifest](2026-11-08-pr43-follow-up.csv). Review statuses apply to the exact target files described; the updated state report and this supplement still require independent documentation review.
