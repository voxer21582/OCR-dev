# Issue #9 acceptance-plan refresh manifest

**Prepared:** 2026-11-12

**Current main:** `4a2206a6b6c53f784277a45e195552dc33e66ed5`
**Parent:** PR #102, head `ef89abd9281a4da3a8d2fd31841b1b62c5f6ed94`

**Candidate branch:** `codex/r9-plan-smoke-reconciliation`
**Pull request target:** `codex/issue-9-runtime-plan-refresh` (PR #102)
**Scope:** documentation-only refresh for [issue #9](https://github.com/voxer21582/OCR-dev/issues/9). This manifest and the plan do not mark the issue complete or accept gate A4.

## Included content

| File | SHA-256 of canonical Git content (LF) | Owner | Provenance and reason |
| --- | --- | --- | --- |
| `docs/runtime/windows11-acceptance-plan.md` | `2B7BC9401A106CD4CFB8B790B4D8E4B80F6003D66A5D38DD12A010F59FA8F085` | OCR2 development coordinator | Current public plan from PR #102, updated on an isolated child branch to include the one authorized synthetic smoke summary recorded in [issue #9](https://github.com/voxer21582/OCR-dev/issues/9#issuecomment-6818743640), alongside the owner-approved evaluation direction. It preserves the upstream references and explicit non-acceptance limits. No code, runtime, model, local Windows identifier, raw test log, private dossier, or previous-project artifact is copied. |

## Control record

This manifest is publication control metadata and is not part of the content-file hash above. Record the manifest's own SHA-256 in the pull request description or review evidence after its final edit.

## Excluded material

- Application source, dependency locks, runtime bundles, native binaries, and model files: outside this plan refresh.
- Local ECC dossiers, run logs, device identifiers, benchmark material, and prior-project artifacts: excluded.
- Real or derived documents, OCR text, personal data, credentials, and confidential values: excluded; none was used.
- R7/R8 implementation, tests, workflows, branch protection, and Project governance: excluded and unchanged.

## Review and verification boundary

- Independent read-only review of the exact final plan and manifest returned READY on 2026-11-12; the reviewer verified the plan's canonical UTF-8/LF SHA-256 against this table and checked claims against the public issue #9 smoke summary. No runtime or functional tests were run by this documentation change.
- `git diff --check` is required before publication. No functional tests apply to this documentation-only change; no runtime or Windows operation is performed.
- The smoke metrics are copied only from the already-public owner summary in issue #9. The private detailed log, local inventory, raw output, documents, OCR text, and device identifiers remain excluded.
- Automated secret/DLP scanning is not included. The review is scoped to the listed files and is not a guarantee that all sensitive content can be detected.
- The existing taxonomy and application CI do not validate Windows runtime acceptance.

The candidate remains a planning deliverable. Exact runtime/model artifacts, license closure, native Windows 11 evidence, install/update/rollback, and authorized technical/security sign-offs remain open. A4 remains open.
