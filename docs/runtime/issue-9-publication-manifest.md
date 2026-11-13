# Issue #9 acceptance-plan refresh manifest

**Prepared:** 2026-11-13

**Base:** `main` at `4a2206a6b6c53f784277a45e195552dc33e66ed5`

**Candidate branch:** `codex/issue-9-runtime-plan-refresh`
**Scope:** documentation-only refresh for [issue #9](https://github.com/voxer21582/OCR-dev/issues/9). This manifest and the plan do not mark the issue complete or accept gate A4.

## Included content

| File | SHA-256 of canonical Git content (LF) | Owner | Provenance and reason |
| --- | --- | --- | --- |
| `docs/runtime/windows11-acceptance-plan.md` | 3A60AA889E5B5CFD2387A34F9181707B615D8C57709D09B2F5A299BC1F409E34 | OCR2 development coordinator | Current public plan refreshed against the selectively migrated application and owner-approved evaluation direction recorded on [issue #9](https://github.com/voxer21582/OCR-dev/issues/9#issuecomment-6718473055). It records upstream model references and runtime metadata, plus the separately authorized one-off synthetic smoke summary from [issue #9](https://github.com/voxer21582/OCR-dev/issues/9#issuecomment-6818743640), with explicit non-acceptance limits. No code, runtime, model, local Windows identifier, private log, test output, dossier, or previous-project artifact is copied. |

## Control record

This manifest is publication control metadata and is not part of the content-file hash above. Record the manifest's own SHA-256 in the pull request description or review evidence after its final edit.

## Excluded material

- Application source, dependency locks, runtime bundles, native binaries, and model files: outside this plan refresh.
- Local ECC dossiers, run logs, device identifiers, benchmark material, and prior-project artifacts: excluded.
- Real or derived documents, OCR text, personal data, credentials, and confidential values: excluded; none was used.
- R7/R8 implementation, tests, workflows, branch protection, and Project governance: excluded and unchanged.

## Review and verification boundary

- Independent read-only review of the retained model references, corrected versioned license-ledger path, and runtime-metadata addition returned READY on 2026-11-11. The smoke summary is copied from the independently reviewed #107 candidate; this combined document still needs a fresh read-only review. No runtime or functional tests were run.
- `git diff --check` is required before publication. No functional tests apply to this documentation-only change; no runtime or Windows operation is performed.
- Automated secret/DLP scanning is not included. The review is scoped to the listed files and is not a guarantee that all sensitive content can be detected.
- The existing taxonomy and application CI do not validate Windows runtime acceptance.

The candidate remains a planning deliverable. Exact runtime/model artifacts, license closure, native Windows 11 evidence, install/update/rollback, and authorized technical/security sign-offs remain open. A4 remains open.
