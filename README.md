# OCR2 Document Intelligence

This public repository is the shared OCR2 workspace. It contains versioned taxonomy contracts at the root and the selectively migrated Document Intelligence application under `application/`. The required CI check runs the taxonomy tests and an explicit list of synthetic application tests. This repository does not yet contain all locally developed application features.

## Continuous integration

The GitHub Actions workflow [OCR2 synthetic taxonomy](.github/workflows/ocr2-synthetic-taxonomy.yml) runs on pushes, pull requests, and manual dispatch. It uses the standard Ubuntu 24.04 runner with CPython 3.13.18 and the hash-locked JSON Schema dependency closure from `requirements/ci-taxonomy-cp313-ubuntu-24_04.lock`. The `main` branch requires a pull request and a successful **Taxonomy registry and binding** check before merge.

Verified on 2026-11-08 at `main` commit `0a2fba0731e230f385e305826b66e4ce17df854d`: [Actions run 42519804658](https://github.com/voxer21582/OCR-dev/actions/runs/42519804658) passed **205 synthetic tests**: 22 taxonomy tests and 183 application tests from the 13 explicitly listed modules. The workflow uses no automatic test discovery. The application coverage includes ingestion and evidence contracts, semantic proposals and validation, loopback request protection, manual source-region review, the configurable document-family catalog, and the RapidOCR adapter contract with an injected synthetic engine.

To reproduce the taxonomy portion on Ubuntu 24.04 x86-64 with Python 3.13, install the locked dependencies and run these two modules:

```sh
python -m pip install --disable-pip-version-check --no-input \
  --only-binary=:all: --require-hashes \
  -r requirements/ci-taxonomy-cp313-ubuntu-24_04.lock

PYTHONPATH=src:tests python -B -m unittest -v \
  test_taxonomy_registry \
  test_taxonomy_binding
```

This first command selects 19 registry tests and 3 binding tests. To reproduce the application portion, run from `application/` in an existing approved Python environment:

```sh
PYTHONPATH=src:tests python -B -m unittest -v \
  test_public_data_guard test_contract_baseline test_document_contract \
  test_document_decoder_contract test_ingestion test_ocr_adapter \
  test_semantic_proposals test_analysis_pipeline test_document_validation \
  test_loopback_csrf test_manual_region_review test_rapidocr_adapter \
  test_document_family_catalog
```

On Windows PowerShell, set `$env:PYTHONPATH='src;tests'` first and invoke the same `python -B -m unittest` module list. These tests use synthetic inputs and isolated temporary files where required. They do not invoke an installed OCR engine, download models or transmit documents.

The configurable document-family catalog and its separate CI extension were integrated through [PR #46](https://github.com/voxer21582/OCR-dev/pull/46) and [PR #47](https://github.com/voxer21582/OCR-dev/pull/47). The catalog's 41 synthetic tests are included in the `main` result above; this library coverage does not establish its UI or archive integration.

## Data and scope

Do not add company documents, personal data, OCR text, credentials, or derived sensitive values to this public repository or its CI. The workflow does not run native OCR or external document services. The public launcher leaves OCR disabled; configuring a real runtime and its background processing remains separate application work. The workflow has read-only repository permissions and references GitHub Actions by full commit SHA.

This CI result covers only the named synthetic contract modules. It is not a full application test suite and does not establish OCR accuracy, Windows runtime readiness, real-document safety, pilot usefulness, or release readiness. For implementation evidence and limitations, see [application current state](application/CURRENT_STATE.md); remaining migration work is tracked in [issue #42](https://github.com/voxer21582/OCR-dev/issues/42).

Project tracking: [OCR2 — Gestione e controllo](https://github.com/users/voxer21582/projects/1).

Windows runtime acceptance planning: [Windows 11 acceptance plan](docs/runtime/windows11-acceptance-plan.md). This is a planning document; it does not establish that an OCR runtime, model, or application has been accepted.
