# R1 source preflight — publication manifest

Prepared: 2026-11-12  
Base: public `main` at `4a2206a6b6c53f784277a45e195552dc33e66ed5`  
Related issue: [#22](https://github.com/voxer21582/OCR-dev/issues/22)

## Included files

| File | Owner | Provenance | Review | Reason |
| --- | --- | --- | --- | --- |
| `application/src/alfa_document_intelligence/source_preflight.py` | OCR2 coordinator | New standard-library code implementing issue #22; reuses the existing signature classifier in `ingestion.py`; no previous-project code or artifacts | Independent review pending | Immutable record contains only SHA-256, byte count and recognized kind; input is bounded bytes, no file access or decoding |
| `application/tests/test_source_preflight.py` | OCR2 coordinator | New synthetic-only unittest cases | Independent review pending | Covers supported signatures, declared-extension mismatch, immutability, error codes, limits and non-echoing failures |
| `application/INGESTION.md` | OCR2 coordinator | Existing public application documentation plus this additive section | Independent review pending | Documents the minimal preflight boundary and what it does not prove |
| `docs/agent-work/2026-11-12-r1-source-preflight-manifest.md` | OCR2 coordinator | Authored for this candidate | Self-description; independent review pending | Records provenance, exact verification scope and exclusions |

## Verification performed

- RED: `python -B -m unittest -v test_source_preflight` failed because the candidate module was absent.
- GREEN: the same explicit command passed 5 synthetic unittest methods against the isolated candidate.
- Existing ingestion regression: from `application/`, `$env:PYTHONPATH = "src;tests"; python -B -m unittest -v test_ingestion` passed 33 tests.
- No network, filesystem input, decoder, OCR, model, new dependency, real document, R7/R8 module, or Windows configuration was used.
- GitHub Actions does not yet select `test_source_preflight`; a separate CI PR is required by #22.
- This candidate is not independently reviewed, merged, or accepted as complete R1.

## Deferred or excluded

- `application/CURRENT_STATE.md` is excluded because active PRs #104, #106 and #110 also change it; update it after ownership is reconciled.
- The new test selector is excluded from this product change and requires a separate explicit CI PR.
- No claim is made about document validity, decodability, import UI, persistence, OCR, or full R1 acceptance.
- R7/R8 files, workflows and stop/no-retry tests are untouched.
