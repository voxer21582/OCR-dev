# Issue #22 — Bounded stream preflight manifest

**Prepared:** 2026-11-06
**Base:** `codex/ci-r1-source-test` at `31baef0deda91c753073c2efa5b8b3b3914b4968`
**Candidate branch:** `codex/r1-stream-preflight`
**Review:** independent final-diff review READY on the exact staged eight-file diff at base `31baef0deda91c753073c2efa5b8b3b3914b4968`; no actionable findings. The reviewer confirmed all seven content hashes, the bounds and error behavior, and the absence of out-of-scope changes.

The earlier `issue-22-publication-manifest.md` records the exact files as reviewed for PR #23; this manifest records only the R1 stream and boundary-correction changes in this follow-up.

## Included files changed in this follow-up

| File | SHA-256 | Owner | Provenance | Review and inclusion reason |
| --- | --- | --- | --- | --- |
| `README.md` | `76bf18459ddcc2b70f4713939dacae87522001beeebca5217bdaa7cf517cf293` | OCR2 coordinator | Existing public README, updated from the R1 byte-only candidate to reflect the stream API and exact 43-test current CI scope | READY; keeps the branch's explicit CI scope and limitations accurate. |
| `src/alfa_document_intelligence/source_intake.py` | `4b663f3689d7a2aa9023b6eefde1fb16b5b4eb57e8c5c98fb43a64f9563511ca` | OCR2 coordinator | Original standard-library extension of the R1 preflight already under review; no legacy OCR code copied | READY; adds bounded caller-owned stream reads and corrects PDF signature start-offset enforcement. |
| `tests/test_source_intake.py` | `18c7d03b62b3043c2bd401b28d95409dbed1bfd33b1d474149e50fa4988653ec` | OCR2 coordinator | Synthetic regression for the first disallowed PDF signature offset, derived from the documented contract | READY; prevents a false acceptance at offset 1024. |
| `tests/test_source_stream.py` | `9f3ba465df1826d0f4bd259bad96ec20ae0a3c8388c5f077a264b2c88a3db8dd` | OCR2 coordinator | Synthetic byte streams and controlled reader doubles authored for issue #22 | READY; verifies short reads, bounded size, digest identity, malformed stream results, closed/read failures and lifecycle. |
| `docs/ocr/source-preflight.md` | `b18a0aa72f50a2998475db6462083f978edcbd1e5ec0712e7152777acfed881f` | OCR2 coordinator | Public contract documentation updated for the implemented stream API and its limits | READY; documents caller ownership and no path opening. |
| `docs/superpowers/specs/2026-11-06-r1-source-preflight-design.md` | `c7be68e69f5d0e2e9e45fe66a70216227334407fff33fc47f6aababc63979250` | OCR2 coordinator | Existing R1 design extended with the bounded-stream and offset corrections | READY; records the reversible technical scope and decisions. |
| `docs/superpowers/plans/2026-11-06-r1-source-preflight.md` | `b73a1f4b62710906544dbf7e904bb3f0b578d0ffe8e59fc51c93f796bd961e67` | OCR2 coordinator | Existing R1 plan updated for stream implementation, verification and separate CI follow-up | READY; provides the execution record. |

The manifest itself is control metadata and is not self-hashed.

## Exclusions

- No real documents, OCR text, company/personal data, credentials, models, previous OCR project code/configuration, or local output artifacts.
- No path opening, file chooser, decoder, rendering, OCR, persistence, UI, network, installation, dependency, model, or Windows/Google configuration changes.
- No workflow or protection change; no R7/R8 or issue #8 files/tests/results.
- No claim of complete R1, actual format validity, page enumeration, runtime readiness, or A4 acceptance.

## Verification and limits

- `PYTHONPATH=src;tests python -B -m unittest -v test_source_intake test_source_stream test_ocr_contracts`: PASS, 30 tests (7 source-byte tests, 9 stream tests, 14 OCR contract tests); synthetic data only.
- Test-driven RED was observed for (a) a PDF signature beginning at offset 1024 and (b) `inspect_stream` absent from the prior base. The updated implementation then passed the complete 30-test command above.
- `git diff --check`: PASS.
- Local taxonomy registry/binding modules could not run because `jsonschema` is absent in the selected Python environment; no package was installed. The unchanged workflow on this candidate branch is expected to run 43 explicit tests; the new 9-test stream module requires a separate CI PR.
- The stream API consumes but does not close or rewind a caller-owned stream. It depends on `read(size)` respecting the requested size; a violating stream is rejected after the oversized chunk is returned. No path, actual document, decoder or runtime was exercised.
- Independent review is READY. GitHub Actions readback for this feature branch is pending; update the manifest if hashes or results change before publication.
