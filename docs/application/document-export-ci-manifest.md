# Synthetic application contracts — CI manifest

**Prepared:** 2026-11-10
**Candidate branch:** `codex/ci-document-export-20261110`
**Base:** cached `origin/main` snapshot `90ae4f9111af5ddad9272ffc20a96acb5311a2f5`; refresh remote main before publication.

## Included change

| File | SHA-256 | Provenance and review |
| --- | --- | --- |
| `.github/workflows/ocr2-synthetic-taxonomy.yml` | `A18AF97538B0423409FF2C1C60B0222042318A21448BE31AF8DFE38D94F7689F` | Existing workflow with two explicit synthetic-contract modules appended: review ledger and document export. No action, trigger, permission, runner, lock, or required-check change. |

The selectors run the already-present test files `application/tests/test_document_export.py` (SHA-256 `498A181DDFB9E531DE566A0112520F4F93A371E9D5B79E7F0E167F8C2AAE69F2`) and `application/tests/test_review_ledger.py` (SHA-256 `9B9AF2E5F6B6922D3ADEC1D384E786D69871EFC96DBC4F3753CDA34325C6EB37`); neither test file is changed by this CI-only candidate.

## Test scope and evidence

From `application/` on 2026-11-10, PowerShell command `$env:PYTHONPATH='src;tests'; python -B -m unittest -v test_document_export` passed all seven export tests. The in-memory synthetic fixtures verify complete-record JSON round-trip without source bytes, contract rejection, schema-required-property rejection, CSV candidate projection, formula-like literal handling, and document identity when there are no fields.

On 2026-11-10, PowerShell command `$env:PYTHONPATH='src;tests'; python -B -m unittest -v test_review_ledger` passed all 15 review-ledger tests. Tests read only the checked-in synthetic invoice fixture and exercise in-memory event, hash-chain, evidence-binding, and overlay contracts. Independent static review found no persistence/archive, network, native Windows, OCR runtime/model, or R7/R8 flow in the selected test path.

On 2026-11-10, after both selectors were added, the full explicitly allowlisted application command from `.github/workflows/ocr2-synthetic-taxonomy.yml` passed **301 tests** locally on Windows with CPython 3.13.15. The existing environment was used with no dependency installation. This is a local result, not a hosted Ubuntu Actions result, and does not replace the required PR check.

The two root taxonomy selectors were attempted locally with `python -B -m unittest -v test_taxonomy_registry test_taxonomy_binding`, but collection stopped with `ModuleNotFoundError: No module named 'jsonschema'` in the current system interpreter. No package was installed. The existing hosted workflow installs its hash-locked CI dependency before these selectors; their result on this candidate remains pending the required Actions run.

The test import path requires the existing `jsonschema` runtime already installed by the workflow's hash-locked dependency file. The export selector does not import or invoke the persistent archive, WSGI app, document decoder, OCR engine/model, Windows APIs, or network services. Its fixture includes a formula-like URL under the reserved `.invalid` domain only as literal data; the test does not make a request. The review-ledger selector imports schema/catalog contracts, but exercises only synthetic in-memory review operations. Compatibility on Ubuntu 24.04 / CPython 3.13.18 remains unverified until the existing Actions workflow runs for the candidate.

## Workflow effects and preserved controls

- The repository's existing workflow remains the only workflow used. Its `push`, `pull_request`, and `workflow_dispatch` triggers are unchanged.
- Required check remains `Taxonomy registry and binding`.
- `ubuntu-24.04`, CPython `3.13.18`, full-SHA-pinned Actions, `contents: read`, and hash-locked binary-only dependencies are unchanged.
- The explicit allowlist is extended by two selectors only; no test discovery or additional dependency installation is introduced.
- A candidate PR will invoke the existing workflow. No remote run has occurred for this local branch, and no PR, merge, release, or product acceptance is claimed here.

## Deliberately excluded

The eight synthetic archive/UI tests passed locally in this session, but are not added to this workflow change. They instantiate `LocalDocumentStore`; on Windows its constructor calls the ordinary fixed-drive/reparse-point path guard. That local run did not create junctions or exercise the separate R7 probe scenario, but the overlap warrants a dedicated scope audit before scheduling those tests. Their local result is not counted as Actions evidence or as R7/R8 acceptance.

## Acceptance criteria

1. Independent review confirms both selected suites use only synthetic fixtures/in-memory contracts and do not import or invoke blocked R7/R8 functionality.
2. The explicitly allowlisted application suites pass locally; the complete required check, including the root taxonomy selectors, passes on the candidate PR. Its Actions log shows both `test_document_export` and `test_review_ledger` completed.
3. The required-check name, permissions, triggers, runner, pinned actions, and dependency lock remain unchanged.

A passing Actions run would verify only these synthetic review-ledger and export contracts on the hosted Linux runner. It would not establish archive persistence, live-browser downloads, OCR operation, Windows behavior, or full product acceptance.
