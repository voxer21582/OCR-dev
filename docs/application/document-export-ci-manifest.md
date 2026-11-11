# Synthetic application contracts — CI manifest

**Prepared:** 2026-11-10
**Candidate branch:** `codex/ci-document-export-20261110`
**Base:** cached `origin/main` snapshot `90ae4f9111af5ddad9272ffc20a96acb5311a2f5`; refresh remote main before publication.

## Included change

| File | SHA-256 | Provenance and review |
| --- | --- | --- |
| `.github/workflows/ocr2-synthetic-taxonomy.yml` | `250AA08E9817A55A862CE7C85F66574B5C26B99D0A2FB85F820A71E8F19232D2` | Existing workflow with five explicit synthetic-contract modules added in this candidate: review ledger, multipage TIFF processing, synthetic OCR metrics, security gate, and document export. No action, trigger, permission, runner, lock, or required-check change. |

The selectors run the already-present test files `application/tests/test_document_export.py` (SHA-256 `498A181DDFB9E531DE566A0112520F4F93A371E9D5B79E7F0E167F8C2AAE69F2`), `application/tests/test_review_ledger.py` (SHA-256 `9B9AF2E5F6B6922D3ADEC1D384E786D69871EFC96DBC4F3753CDA34325C6EB37`), `application/tests/test_multipage_tiff_processing_contract.py` (SHA-256 `1B00381D967938BECCC7E24C12B9DB6ED8F05ECD31EB8C3C47E32F34D740141A`), `application/tests/test_synthetic_ocr_metrics.py` (SHA-256 `361FA5329917C49DA9A908D94209C79DE02421156FE5FF9930D2FBF1A11CB51A`), and `application/tests/test_security_gate.py` (SHA-256 `7DFCD127251FA22EDA5606517035A7772AAF9BE8ACF02EBAA041C2B24017611E`); no test file is changed by this CI-only candidate.

## Test scope and evidence

From `application/` on 2026-11-10, PowerShell command `$env:PYTHONPATH='src;tests'; python -B -m unittest -v test_document_export` passed all seven export tests. The in-memory synthetic fixtures verify complete-record JSON round-trip without source bytes, contract rejection, schema-required-property rejection, CSV candidate projection, formula-like literal handling, and document identity when there are no fields.

On 2026-11-10, PowerShell command `$env:PYTHONPATH='src;tests'; python -B -m unittest -v test_review_ledger` passed all 15 review-ledger tests. Tests read only the checked-in synthetic invoice fixture and exercise in-memory event, hash-chain, evidence-binding, and overlay contracts. Independent static review found no persistence/archive, network, native Windows, OCR runtime/model, or R7/R8 flow in the selected test path.

On 2026-11-10, PowerShell command `$env:PYTHONPATH='src;tests'; python -B -m unittest -v test_multipage_tiff_processing_contract test_synthetic_ocr_metrics` passed five tests. The TIFF integration test generates in-memory TIFF bytes but injects a fake decoder and fake OCR engine, so it tests orchestration and evidence binding only. The metrics tests use synthetic OCR tokens and gold strings; they validate deterministic reporting logic, not the accuracy of any OCR model. Independent static review found neither path invokes persistence/archive, network, Windows APIs, native decoders, runtime/model, or R7/R8 behavior.

On 2026-11-10, PowerShell command `$env:PYTHONPATH='src;tests'; python -B -m unittest -v test_security_gate` passed all nine tests. The tests use synthetic PDF/ZIP data, temporary paths, and a `FakeScanner`. They validate that incomplete, malformed, unavailable, or malicious scanner receipts fail closed and that only the exact inventoried bytes can clear the gate. They do not validate a real scanner, malware detection, scanner integration, or product security clearance. The path checks use normal `pathlib` behavior on temporary test files; no reparse-point/junction probe was performed.

On 2026-11-10, after the five selectors in this candidate were added, the full explicitly allowlisted application command from `.github/workflows/ocr2-synthetic-taxonomy.yml` passed **315 tests** locally on Windows with CPython 3.13.15. The existing environment was used with no dependency installation. This is a local result, not a hosted Ubuntu Actions result, and does not replace the required PR check.

Reverification on 2026-11-11 used the exact application selector list from the workflow and CPython 3.13.15: **315 tests passed** (`Ran 315 tests in 0.874s`, `OK`). The workflow SHA-256 remained `250AA08E9817A55A862CE7C85F66574B5C26B99D0A2FB85F820A71E8F19232D2`. The two root taxonomy selectors were not part of this run: `jsonschema` is absent from the selected system interpreter, and no package was installed. This is still local evidence only; no new hosted Actions run is claimed.

The two root taxonomy selectors were attempted locally with `python -B -m unittest -v test_taxonomy_registry test_taxonomy_binding`, but collection stopped with `ModuleNotFoundError: No module named 'jsonschema'` in the current system interpreter. No package was installed. The existing hosted workflow installs its hash-locked CI dependency before these selectors; their result on this candidate remains pending the required Actions run.

The export test import path requires the existing `jsonschema` runtime installed by the workflow's hash-locked dependency file. The export selector does not invoke the persistent archive, WSGI app, OCR engine/model, Windows APIs, or network services. Its fixture includes a formula-like URL under the reserved `.invalid` domain only as literal data; the test makes no request. The review-ledger selector imports schema/catalog contracts but exercises only synthetic in-memory review operations. The TIFF selector imports decoder contracts, but its tested call supplies a fake decoder and fake engine. The metrics selector processes only generated token/gold data. The security-gate selector uses a fake scanner and temporary test paths; it is a gate-contract test, not malware-detection evidence. Compatibility on Ubuntu 24.04 / CPython 3.13.18 remains unverified until the existing Actions workflow runs for the candidate.

## Workflow effects and preserved controls

- The repository's existing workflow remains the only workflow used. Its `push`, `pull_request`, and `workflow_dispatch` triggers are unchanged.
- Required check remains `Taxonomy registry and binding`.
- `ubuntu-24.04`, CPython `3.13.18`, full-SHA-pinned Actions, `contents: read`, and hash-locked binary-only dependencies are unchanged.
- The explicit allowlist is extended by five selectors only; no test discovery or additional dependency installation is introduced.
- A candidate PR will invoke the existing workflow. No remote run has occurred for this local branch, and no PR, merge, release, or product acceptance is claimed here.

## Deliberately excluded

The eight synthetic archive/UI tests passed locally in this session, but are not added to this workflow change. They instantiate `LocalDocumentStore`; on Windows its constructor calls the ordinary fixed-drive/reparse-point path guard. That local run did not create junctions or exercise the separate R7 probe scenario, but the overlap warrants a dedicated scope audit before scheduling those tests. Their local result is not counted as Actions evidence or as R7/R8 acceptance.

## Acceptance criteria

1. Independent review confirms the five added selectors use only synthetic fixtures/fakes and do not exercise blocked R7/R8 functionality.
2. The explicitly allowlisted application suites pass locally; the complete required check, including the root taxonomy selectors, passes on the candidate PR. Its Actions log shows all five newly selected modules completed.
3. The required-check name, permissions, triggers, runner, pinned actions, and dependency lock remain unchanged.

A passing Actions run would verify only synthetic serializer/export, review-ledger, multipage orchestration, metrics, and fake-scanner gate contracts on the hosted Linux runner. It would not establish archive persistence, live-browser behavior, real TIFF decoding, OCR model accuracy, real malware detection, Windows behavior, or full product acceptance.
