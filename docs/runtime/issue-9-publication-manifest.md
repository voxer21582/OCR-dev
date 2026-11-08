# Issue #9 publication manifest

**Prepared:** 2026-11-05

**Base:** `main` at `b9f1e021a4fc720a3388849b1d0b2b31586e7b85`

**Candidate branch:** `codex/issue-9-win11-acceptance-plan`
**Scope:** documentation-only update for [issue #9](https://github.com/voxer21582/OCR-dev/issues/9). This manifest does not mark the issue complete or accept gate A4.

## Included content files

| File | SHA-256 | Owner | Provenance | Review and inclusion reason |
| --- | --- | --- | --- | --- |
| `README.md` | `FF76FE58A6B9867A0134A5A0728E6AF2018B3EACD770291D037DE2A035ADE90F` | OCR2 development coordinator | Current public `main` plus a link to the new acceptance plan | Independent review PASS on the exact README change. Included so repository users can find the plan and understand its limited status. |
| `docs/runtime/windows11-acceptance-plan.md` | `86DAC2C7E72C35DD99961D6F5FEBC30984075FDDB379CCB260C985B5C37FF73F` | OCR2 development coordinator | Authored for this issue from the accepted OCR2 A4 criteria and the current public repository boundary; no code, model, configuration, test output, or private dossier was copied | Independent review PASS on the exact file. Included as a public, actionable checklist that states current gaps and authorization boundaries. |

## Control record

This manifest is publication control metadata and is not part of the two content-file hashes above. The independent reviewer must inspect this manifest with the final diff before the branch is published. Record the manifest's own SHA-256 in the pull request description or review evidence after its final edit.

## Excluded material

- OCR2 application source, dependency locks, runtime bundles, native binaries, and model files: outside issue scope and not present in the new public checkout.
- Local ECC dossiers, run logs, Windows observations, benchmark material, and prior-project artifacts: excluded; no local evidence bundle is being published.
- Real or derived documents, OCR text, personal data, credentials, and confidential values: excluded; none was intentionally used in these files.
- R7/R8 implementation, tests, workflows, branch protection, and Project governance: excluded and unchanged.

## Review and verification boundary

- Independent review of the README and plan: PASS, read-only; no product tests or runtime operations were performed.
- The complete staged diff passed `git diff --cached --check`; independent review evidence is tracked separately and must cover this manifest before publication. No functional tests are applicable to this documentation-only change.
- Automated secret/DLP scanning: not run. The review was scoped to the exact two content files; it is not a guarantee that all sensitive content can be detected.
- The existing taxonomy CI may run after a pull request is opened. It uses the repository's pinned Actions and synthetic taxonomy tests; it does not validate Windows runtime acceptance.

The candidate remains a planning deliverable. Runtime/model selection, license closure, native Windows 11 evidence, and authorized technical/security sign-offs remain open.
