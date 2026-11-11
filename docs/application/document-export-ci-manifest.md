# Synthetic application contracts — CI manifest

**Prepared:** 2026-11-10; evidence updated 2026-11-11
**Candidate branch:** `codex/ci-document-export-20261110`
**Base:** cached `origin/main` snapshot `90ae4f9111af5ddad9272ffc20a96acb5311a2f5`; refresh remote main before publication.

## Included change

| File | SHA-256 | Provenance and review |
| --- | --- | --- |
| `.github/workflows/ocr2-synthetic-taxonomy.yml` | `156C27D7FD93063485A432A9F580711492895BBBA3A3F804560A87AF139CCFF8` | Existing workflow with seven explicit synthetic-contract selectors added in this candidate: review ledger, multipage TIFF processing, synthetic OCR metrics, security gate, document export, expense-report bundles, and source-bound expense-report intake. No action, trigger, permission, runner, lock, or required-check change. |

The selectors run the already-present test files `application/tests/test_document_export.py` (SHA-256 `498A181DDFB9E531DE566A0112520F4F93A371E9D5B79E7F0E167F8C2AAE69F2`), `application/tests/test_review_ledger.py` (SHA-256 `9B9AF2E5F6B6922D3ADEC1D384E786D69871EFC96DBC4F3753CDA34325C6EB37`), `application/tests/test_multipage_tiff_processing_contract.py` (SHA-256 `1B00381D967938BECCC7E24C12B9DB6ED8F05ECD31EB8C3C47E32F34D740141A`), `application/tests/test_synthetic_ocr_metrics.py` (SHA-256 `361FA5329917C49DA9A908D94209C79DE02421156FE5FF9930D2FBF1A11CB51A`), `application/tests/test_security_gate.py` (SHA-256 `7DFCD127251FA22EDA5606517035A7772AAF9BE8ACF02EBAA041C2B24017611E`), `application/tests/test_expense_reports.py` (SHA-256 `8CE1CD6ABEDD45717DD58EEC63D33C2D86FC43C0A1F600E5C018E88F878E6F35`), and `application/tests/test_expense_report_intake_session.py` (SHA-256 `8FABDE0DE0BCFA6D377D83F8BB0572E93D6340A1B25C0BA334D547557B3F1E02`). Both expense-report test files change only their test runner from `pytest` to standard-library `unittest`; their eleven existing tests remain explicitly selected across two modules.

## Test scope and evidence

From `application/` on 2026-11-10, PowerShell command `$env:PYTHONPATH='src;tests'; python -B -m unittest -v test_document_export` passed all seven export tests. The in-memory synthetic fixtures verify complete-record JSON round-trip without source bytes, contract rejection, schema-required-property rejection, CSV candidate projection, formula-like literal handling, and document identity when there are no fields.

On 2026-11-10, PowerShell command `$env:PYTHONPATH='src;tests'; python -B -m unittest -v test_review_ledger` passed all 15 review-ledger tests. Tests read only the checked-in synthetic invoice fixture and exercise in-memory event, hash-chain, evidence-binding, and overlay contracts. Independent static review found no persistence/archive, network, native Windows, OCR runtime/model, or R7/R8 flow in the selected test path.

On 2026-11-10, PowerShell command `$env:PYTHONPATH='src;tests'; python -B -m unittest -v test_multipage_tiff_processing_contract test_synthetic_ocr_metrics` passed five tests. The TIFF integration test generates in-memory TIFF bytes but injects a fake decoder and fake OCR engine, so it tests orchestration and evidence binding only. The metrics tests use synthetic OCR tokens and gold strings; they validate deterministic reporting logic, not the accuracy of any OCR model. Independent static review found neither path invokes persistence/archive, network, Windows APIs, native decoders, runtime/model, or R7/R8 behavior.

On 2026-11-10, PowerShell command `$env:PYTHONPATH='src;tests'; python -B -m unittest -v test_security_gate` passed all nine tests. The tests use synthetic PDF/ZIP data, temporary paths, and a `FakeScanner`. They validate that incomplete, malformed, unavailable, or malicious scanner receipts fail closed and that only the exact inventoried bytes can clear the gate. They do not validate a real scanner, malware detection, scanner integration, or product security clearance. The path checks use normal `pathlib` behavior on temporary test files; no reparse-point/junction probe was performed.

On 2026-11-10, after the five selectors in this candidate were added, the full explicitly allowlisted application command from `.github/workflows/ocr2-synthetic-taxonomy.yml` passed **315 tests** locally on Windows with CPython 3.13.15. The existing environment was used with no dependency installation. This is a local result, not a hosted Ubuntu Actions result, and does not replace the required PR check.

Reverification on 2026-11-11 used the exact application selector list from the workflow and CPython 3.13.15: **315 tests passed** (`Ran 315 tests in 0.874s`, `OK`). The workflow SHA-256 remained `250AA08E9817A55A862CE7C85F66574B5C26B99D0A2FB85F820A71E8F19232D2`. The two root taxonomy selectors were not part of this local run: `jsonschema` is absent from the selected system interpreter, and no package was installed.

On 2026-11-11, PR [#101](https://github.com/voxer21582/OCR-dev/pull/101), head `837743f47f8f02b85b7ba3869ba42d84b0d3c10b`, completed the existing hosted workflow successfully in [Actions run 42977830932](https://github.com/voxer21582/OCR-dev/actions/runs/42977830932). Its log reports **22 taxonomy tests and 315 application tests passed** on Ubuntu 24.04 / CPython 3.13.18. The required check `Taxonomy registry and binding` is green. CodeQL's Python and Actions analyses also completed successfully, and the [CodeQL run](https://github.com/voxer21582/OCR-dev/runs/130381155128) reports no new alerts. This verifies the candidate branch and its explicit selectors on hosted CI; PR #101 remains a draft and has not been merged.

The two expense-report selectors are new candidate additions, not yet verified by a local or hosted run. The bundle tests use the checked-in `synthetic_invoice.json` fixture and in-memory document objects. The intake tests construct a tiny ZIP in `BytesIO` containing synthetic PDF-signature payloads, materialize its members in memory, and verify explicit note selection plus source-hash binding. The tested import path uses the bounded ZIP inventory/materialization contract; it does not call a PDF decoder, OCR, persistent archive, UI, network, or Windows APIs, and does not enter the R7 junction/restore probe. Both test files were converted to `unittest` because the workflow intentionally does not install `pytest`; its existing hash-locked JSON Schema dependency remains sufficient. The current local Python lacks `jsonschema`, so no package was installed and neither selector has been run locally. Hosted CI on the candidate will be the first execution after these additions.

The two root taxonomy selectors were attempted locally with `python -B -m unittest -v test_taxonomy_registry test_taxonomy_binding`, but collection stopped with `ModuleNotFoundError: No module named 'jsonschema'` in the current system interpreter. No package was installed. The existing hosted workflow installs its hash-locked CI dependency before these selectors; the PR #101 hosted result above verifies them on the candidate.

The export test import path requires the existing `jsonschema` runtime installed by the workflow's hash-locked dependency file. The export selector does not invoke the persistent archive, WSGI app, OCR engine/model, Windows APIs, or network services. Its fixture includes a formula-like URL under the reserved `.invalid` domain only as literal data; the test makes no request. The review-ledger selector imports schema/catalog contracts but exercises only synthetic in-memory review operations. The TIFF selector imports decoder contracts, but its tested call supplies a fake decoder and fake engine. The metrics selector processes only generated token/gold data. The security-gate selector uses a fake scanner and temporary test paths; it is a gate-contract test, not malware-detection evidence. Ubuntu 24.04 / CPython 3.13.18 compatibility is verified for the candidate by Actions run 42977830932.

## Workflow effects and preserved controls

- The repository's existing workflow remains the only workflow used. Its `push`, `pull_request`, and `workflow_dispatch` triggers are unchanged.
- Required check remains `Taxonomy registry and binding`.
- `ubuntu-24.04`, CPython `3.13.18`, full-SHA-pinned Actions, `contents: read`, and hash-locked binary-only dependencies are unchanged.
- The explicit allowlist is extended by seven selectors only; no test discovery or additional dependency installation is introduced.
- PR #101 invoked the existing workflow and its required check passed. The PR remains draft and unmerged; no release or full-product acceptance is claimed.

## Deliberately excluded

The eight synthetic archive/UI tests passed locally in this session, but are not added to this workflow change. They instantiate `LocalDocumentStore`; on Windows its constructor calls the ordinary fixed-drive/reparse-point path guard. That local run did not create junctions or exercise the separate R7 probe scenario, but the overlap warrants a dedicated scope audit before scheduling those tests. Their local result is not counted as Actions evidence or as R7/R8 acceptance.

## Acceptance criteria

1. Coordinator static review and independent review must confirm the seven added selectors use only synthetic fixtures/fakes and do not exercise blocked R7/R8 functionality. The independent review did not execute tests; the hosted run for both expense-report selectors remains pending.
2. The explicitly allowlisted application suites pass locally where existing dependencies are available; the complete required check, including root taxonomy selectors, passes on the candidate PR. Its Actions log must show all seven newly selected modules completed.
3. The required-check name, permissions, triggers, runner, pinned actions, and dependency lock remain unchanged.

The independent review and hosted Actions run above apply to the previous PR #101 head and the five selectors then present. Independent review and hosted results for the two later expense-report selectors are pending for the current candidate revision. Integration into `main` and product-level acceptance remain pending; CI covers only the named synthetic contract suites.

A passing Actions run would verify only synthetic serializer/export, review-ledger, multipage orchestration, metrics, fake-scanner gate contracts, in-memory expense-bundle construction, and source binding through synthetic ZIP inventory/materialization on the hosted Linux runner. The intake selector checks only bounded inventory/materialization and header recognition for PDF-signature bytes; it does not decode PDF content. These checks would not establish archive persistence, live-browser behavior, real TIFF or PDF decoding, OCR model accuracy, real malware detection, Windows behavior, or full product acceptance.
