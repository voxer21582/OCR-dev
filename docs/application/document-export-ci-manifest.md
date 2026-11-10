# Document export contracts — CI manifest

**Prepared:** 2026-11-10
**Candidate branch:** `codex/ci-document-export-20261110`
**Base:** cached `origin/main` snapshot `90ae4f9111af5ddad9272ffc20a96acb5311a2f5`; refresh remote main before publication.

## Included change

| File | SHA-256 | Provenance and review |
| --- | --- | --- |
| `.github/workflows/ocr2-synthetic-taxonomy.yml` | `1AF0AF986894EDCF0467448666982FDC34048170D3FD789623333E19183EB093` | Existing workflow with one explicit serializer-test module appended; no action, trigger, permission, runner, lock, or required-check change. Independent review READY on 2026-11-10. |

The selector runs the already-present public test file `application/tests/test_document_export.py` (SHA-256 `498A181DDFB9E531DE566A0112520F4F93A371E9D5B79E7F0E167F8C2AAE69F2`); it is not changed by this CI-only candidate. The independent reviewer checked both file hashes and the workflow/test scope, but did not rerun the seven local tests.

## Test scope and evidence

From `application/` on 2026-11-10, PowerShell command `$env:PYTHONPATH='src;tests'; python -B -m unittest -v test_document_export` passed all seven tests. The in-memory synthetic fixtures verify complete-record JSON round-trip without source bytes, contract rejection, schema-required-property rejection, CSV candidate projection, formula-like literal handling, and document identity when there are no fields.

The test import path requires the existing `jsonschema` runtime already installed by the workflow's hash-locked dependency file. The selector does not import or invoke the persistent archive, WSGI app, document decoder, OCR engine/model, Windows APIs, or network services. Its fixture includes a formula-like URL under the reserved `.invalid` domain only as literal data; the test does not make a request. The local pass is evidence for this module only; compatibility on Ubuntu 24.04 / CPython 3.13.18 remains unverified until the existing Actions workflow runs for the candidate.

## Workflow effects and preserved controls

- The repository's existing workflow remains the only workflow used. Its `push`, `pull_request`, and `workflow_dispatch` triggers are unchanged.
- Required check remains `Taxonomy registry and binding`.
- `ubuntu-24.04`, CPython `3.13.18`, full-SHA-pinned Actions, `contents: read`, and hash-locked binary-only dependencies are unchanged.
- The explicit allowlist is extended by this selector only; no test discovery or additional dependency installation is introduced.
- A candidate PR will invoke the existing workflow. No remote run has occurred for this local branch, and no PR, merge, release, or product acceptance is claimed here.

## Deliberately excluded

The eight synthetic archive/UI tests passed locally in this session, but are not added to this workflow change. They instantiate `LocalDocumentStore`; on Windows its constructor calls the ordinary fixed-drive/reparse-point path guard. That local run did not create junctions or exercise the separate R7 probe scenario, but the overlap warrants a dedicated scope audit before scheduling those tests. Their local result is not counted as Actions evidence or as R7/R8 acceptance.

## Acceptance criteria

1. Independent review confirms the selected tests remain serializer contracts over synthetic fixture data and do not import or invoke blocked R7/R8 functionality.
2. The existing required check passes on the candidate PR and its log shows `test_document_export` completed seven tests.
3. The required-check name, permissions, triggers, runner, pinned actions, and dependency lock remain unchanged.

A passing Actions run would verify only these synthetic export contracts on the hosted Linux runner. It would not establish archive persistence, live-browser downloads, OCR operation, Windows behavior, or full product acceptance.
