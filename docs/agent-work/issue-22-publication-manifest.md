# Issue #22 — Public publication manifest

**Prepared:** 2026-11-06
**Base:** `codex/ci-r2-explicit-tests` at `daec109699e454ee5de0b875459f509294b1e105`
**Candidate branch:** `codex/r1-source-preflight`
**Review:** independent final-diff review READY on the exact seven-file staged diff at base `daec109699e454ee5de0b875459f509294b1e105`; no actionable findings. The reviewer confirmed all six content-file hashes and absence of filesystem, decoder, OCR, real-data, R7/R8, dependency, workflow, protection or permission changes.

## Included files

| File | SHA-256 | Owner | Provenance | Review and inclusion reason |
| --- | --- | --- | --- | --- |
| `README.md` | `b88ca497070e8f74eb8d6a165060324c954125f0f90cdc37d92390e4bc85dee8` | OCR2 coordinator | Small update to the public README already in the CI/R2 PR base | READY; states the R1 preflight scope and that its tests are not yet in CI. |
| `src/alfa_document_intelligence/source_intake.py` | `07f05106efa8f6c6a7d48fcdd62eddf0c0d634912b5f165f982856e3ca97d3be` | OCR2 coordinator | New standard-library-only implementation derived from user-approved OCR2 product objective and issue #22; no legacy OCR source copied | READY; included as the in-memory signature and identity tranche. |
| `tests/test_source_intake.py` | `cf4bc97baa8815b14b6628cc88d11ebdba2c530ebf464bd6557a847c5ed5f261` | OCR2 coordinator | New synthetic byte fixtures derived from issue #22 | READY; included to verify the new contract without real documents. |
| `docs/ocr/source-preflight.md` | `aca1b8719c03953646bab482e2f46aefbbc68c0560a86abb9c6d1b0b6aadd86a` | OCR2 coordinator | New public contract documentation for the implementation in this change | READY; included to state limits and supported signatures precisely. |
| `docs/superpowers/specs/2026-11-06-r1-source-preflight-design.md` | `32217a0fc16b899d4b0c2a458f9bc62c9b3d03ebed43b61f7a3460a2a63155b5` | OCR2 coordinator | New design synthesized from the explicit R1 objective and issue #22 | READY; included for the durable scope and technical decisions. |
| `docs/superpowers/plans/2026-11-06-r1-source-preflight.md` | `7c04b110fa7c9d4bf10c6ac5e2b6ad83bade1f5f56271426cd2a7b9130ad650e` | OCR2 coordinator | New implementation plan for the reviewed design | READY; included for traceability and follow-on CI sequencing. |

The manifest itself is control metadata and is not self-hashed.

## Exclusions

- Any previous OCR project source, configuration, models, documents, real OCR, personal/company data, credentials, local runtime artifacts or output logs.
- File system, decoder, renderer, OCR, persistence, network, UI, installer or model integration.
- New dependencies and any changes to existing workflow, lockfile, permissions, triggers, required checks, branch protections, Google or Windows configuration.
- R7/R8 and issue #8 files, tests, fixtures or results.

## Verification and limits

- `PYTHONPATH=src;tests python -B -m unittest -v test_source_intake test_ocr_contracts`: PASS, 20 tests total (6 source preflight + 14 OCR contract). This does not exercise taxonomy modules locally because `jsonschema` is absent in the selected Python environment; no package was installed.
- `git diff --check`: PASS.
- PR #23 push run [42194762167](https://github.com/voxer21582/OCR-dev/actions/runs/42194762167) and pull-request run [42194847377](https://github.com/voxer21582/OCR-dev/actions/runs/42194847377) both passed the existing explicit 36-test allowlist. These runs do not include `test_source_intake`; that module remains scheduled for a separate CI PR.
- Synthetic signature matches do not establish actual PDF/image validity, decoding, page enumeration, multipage behavior, Windows runtime compatibility or full R1/A4 acceptance.
- Independent review is READY. The two PR #23 workflow runs above pass; this manifest must be updated if file hashes, review state, or CI results change before publication.
