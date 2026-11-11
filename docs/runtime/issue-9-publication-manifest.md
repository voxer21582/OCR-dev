# Issue #9 acceptance-plan refresh manifest

**Prepared:** 2026-11-11

**Base:** `main` at `90ae4f9111af5ddad9272ffc20a96acb5311a2f5`

**Candidate branch:** `codex/issue-9-runtime-plan-refresh`
**Scope:** documentation-only refresh for [issue #9](https://github.com/voxer21582/OCR-dev/issues/9). This manifest and the plan do not mark the issue complete or accept gate A4.

## Included content

| File | SHA-256 of canonical Git content (LF) | Owner | Provenance and reason |
| --- | --- | --- | --- |
| `docs/runtime/windows11-acceptance-plan.md` | `F3DA57C444862831E6284FDF6CB5E1488B2408DAEB618B220362062E862C3129` | OCR2 development coordinator | Current public plan refreshed against the selectively migrated application and owner-approved evaluation direction recorded on [issue #9](https://github.com/voxer21582/OCR-dev/issues/9#issuecomment-6718473055). It records upstream model URLs and hashes, the versioned license ledger and remaining clearance, plus runtime metadata with explicit non-verification limits. No code, runtime, model, local Windows identifier, test output, private dossier, or previous-project artifact is copied. |

## Control record

This manifest is publication control metadata and is not part of the content-file hash above. Record the manifest's own SHA-256 in the pull request description or review evidence after its final edit.

## Excluded material

- Application source, dependency locks, runtime bundles, native binaries, and model files: outside this plan refresh.
- Local ECC dossiers, run logs, device identifiers, benchmark material, and prior-project artifacts: excluded.
- Real or derived documents, OCR text, personal data, credentials, and confidential values: excluded; none was used.
- R7/R8 implementation, tests, workflows, branch protection, and Project governance: excluded and unchanged.

## Review and verification boundary

- Independent read-only review of the model references, corrected versioned license-ledger path, and runtime-metadata addition returned READY on 2026-11-11; no runtime or functional tests were run.
- `git diff --check` is required before publication. No functional tests apply to this documentation-only change; no runtime or Windows operation is performed.
- Automated secret/DLP scanning is not included. The review is scoped to the listed files and is not a guarantee that all sensitive content can be detected.
- The existing taxonomy and application CI do not validate Windows runtime acceptance.

The candidate remains a planning deliverable. Exact runtime/model artifacts, license closure, native Windows 11 evidence, install/update/rollback, and authorized technical/security sign-offs remain open. A4 remains open.
