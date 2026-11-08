# Document Intelligence current state

Updated: 2026-11-08

## Verified

- The previously observed `main` snapshot `86c9398905fb4baf4a54b58b303ddf8325c4e768` contains the initial selective application snapshot under `application/` (PR #38), not the entire private application checkout.
- A follow-up local branch contains loopback request-security changes and a source-hash-bound human region review for absent fields. Region correction does not run OCR, write to the archive, or change R7/R8.
- On the isolated local clone, the explicit synthetic application test list including the optional RapidOCR adapter completed 142 tests; `py_compile` and `git diff --check` passed. Independent reviews marked the security code, manual-region UI after correction, RapidOCR adapter after raw-type validation fixes, and explicit CI test-list extensions READY.
- The feature, security, and workflow commits are recorded in `../docs/migration/2026-11-07-document-intelligence-public-migration.md`; status-documentation commits follow those changes.
- `rapidocr_adapter.py` defines a dependency-lazy adapter for an already-configured RapidOCR engine. It rejects boolean/text coordinates and confidence values before conversion. No RapidOCR package or model was installed or downloaded, and no engine/runtime result is claimed.

## Not verified / blocked

- The follow-up commits have not been pushed or run by GitHub Actions. This session could not reach GitHub, so no PR or Project update was made.
- No Windows installer, production OCR runtime/model, real-document behavior, or release is accepted by this state record.
- Public migration remains selective and incomplete. Further source files need provenance, privacy/licensing review, and an explicit migration decision.

## Next steps

1. Publish the reviewed commits as separate, reviewable PRs when GitHub access is available; verify their bases and triggered checks.
2. Merge only after required CI and owner approval, then record the merged commit and GitHub Actions evidence.
3. Continue the file-by-file migration without modifying the original checkout or resuming blocked R7/R8 work.
