# Issue #28 publication manifest — R4 field candidate contract

**Prepared:** 2026-11-06
**Base:** PR #19 branch `codex/ci-r2-explicit-tests` at `60bb627c443ce513c26c89c0ccd3a26941701e53`
**Candidate branch:** `codex/r4-field-candidate-contract`
**Owner:** `voxerino`
**Issue:** https://github.com/voxer21582/OCR-dev/issues/28

## Included files

| File | SHA-256 | Owner / provenance | Review | Reason |
| --- | --- | --- | --- | --- |
| `src/alfa_document_intelligence/extraction_contracts.py` | `9755E36003C0B6AB6F599F551EAA9DADC2560A12CCC549AF4F35165B58A272FD` | `voxerino`; new OCR2 contract using existing R2 page results and R3 taxonomy binding; no copied OCR implementation | Independent review READY (2026-11-06) | Adds only immutable field candidate records and validation |
| `tests/test_extraction_contracts.py` | `5F72B77B96B42AA5FFF8EB84501159C064A4EFD3FCDF4FCFFB4D9FCBBA403E64` | `voxerino`; synthetic page results, catalog values, and strings | Independent review READY (2026-11-06) | Covers states, taxonomy identity, observation references, manual-only fields, malformed identities, and immutability |
| `docs/ocr/field-candidate-contract.md` | `57566F82DD9C3B8EFD418EC060DEC1BD82B9A3879373B9A312BEFE461E245FEA` | `voxerino`; written from issue #28 and approved high-level OCR2 goal | Independent review READY (2026-11-06) | Documents API meaning and limitations |
| `README.md` | `9735AD482141AA8BD2A907ECACE4292A57D2982BC33A9ABA16F9FF3E718CC9D0` | `voxerino`; existing README, limited scope/link update | Independent review READY (2026-11-06) | Discloses the new contract and that its tests are not yet in CI |
| `docs/superpowers/specs/2026-11-06-r4-field-candidate-contract-design.md` | `D60D39955A3A4C9F38CF7F8C55F7A86231C26CDAF1D290EB1552E98513E4B6B5` | `voxerino`; technical choices derived from issue #28, R2/R3 interfaces, and product goal | Independent review READY (2026-11-06) | Records approach, constraints, and explicit non-goals |
| `docs/superpowers/plans/2026-11-06-r4-field-candidate-contract.md` | `5E95ED1EE982BD33CEC3BF67C270B0997A74AA9DCE4E91621FFB7943CFCF600D` | `voxerino`; execution plan for issue #28 | Independent review READY (2026-11-06) | Defines implementation, test, and separate CI tasks |

This manifest does not include itself in the file-hash table.

## Exclusions

- OCR engines, models, decoders, extraction algorithms, locale-specific normalization, fiscal interpretation, UI, document persistence, Windows runtime, and installation.
- Real or derived documents, real OCR output, personal data, credentials, private dossiers, temporary artifacts, and code/configuration from the previous OCR project.
- CI workflow changes; those belong to a separate PR after this feature branch is available.
- R7/R8, issue #8, Windows configuration, Google deployment, and A4/A5 pilot operations.

## Verification state at manifest preparation

- TDD RED observed before implementation: `test_extraction_contracts` failed to import the not-yet-created production module.
- `py_compile` for the new module and test file: passed.
- `git diff --check`: passed.
- A post-implementation local test run is unavailable because this isolated Python 3.13.15 environment has no `jsonschema` dependency. No dependency was installed. GitHub Actions with the existing hash-locked Ubuntu environment is the intended integration check; the feature PR's existing workflow allowlist does not yet include this test module.
- Local test module contains 15 explicit test cases; Actions must execute the module via a separate CI PR before R4 verification is complete.
- Independent static review: READY on the exact current feature diff after reconciling the interface and malformed-identity coverage.
- No R4 end-to-end extraction, real-document accuracy, A4/A5, R6, or full-product acceptance is claimed.
