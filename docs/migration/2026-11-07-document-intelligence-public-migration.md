# Public migration manifest: document-intelligence to OCR-dev

Date: 2026-11-07

## Scope

Selective migration proposal into `application/` on public repository `voxer21582/OCR-dev`. The private source repository remains untouched. No files from the legacy OCR project, real documents, OCR outputs, model files, or credentials are included. The nested app path avoids collisions with OCR-dev's taxonomy package.

Source: `voxer21582/document-intelligence`, branch `codex/persistent-archive-ui`, HEAD `e89305f19e4562d2026d252fdd2cf669fd154e3d`.
Target: `voxer21582/OCR-dev`, branch `codex/unify-document-intelligence`, base `main` `b9f1e021a4fc720a3388849b1d0b2b31586e7b85`.

The CSV records every tracked source file as included, excluded, or transformed, lists every untracked source file individually, and identifies both manifest artifacts. The manifest cannot hash itself; the final commit ID is the integrity reference for those two files. Five untracked local files are listed individually and excluded because they are uncommitted and unreviewed. Open private PRs #131–#141 and open OCR-dev PRs remain untouched; proposed changes from those PRs are not included.

## Inventory

```text
source tracked files=130
source untracked files=5
exclude=54
include=76
new=4
transform=6
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

An independent code review returned READY for publication of this initial migration slice at application tree commit `f76b4e1`. The reviewer confirmed the file manifest, synthetic-only content scope, absence of secret/email/user-path matches, no binary model/document artifacts, clean relative documentation links, and unchanged root required workflow. Per-file `review_status` values stating “pending” describe manifest assembly time and are superseded by this review record. This does not complete repository unification: private repository PRs #131–#141 remain preserved and unported.
