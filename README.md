# OCR2 contracts

This repository currently contains a small, synthetic-testable slice of OCR2: versioned taxonomy catalog validation and updates, hash-bound taxonomy bindings, an engine-neutral OCR page/result contract, and an in-memory signature-only source preflight. It does not contain the full application or an operational OCR engine.

## Continuous integration

The GitHub Actions workflow [OCR2 synthetic taxonomy](.github/workflows/ocr2-synthetic-taxonomy.yml) runs on pushes, pull requests, and manual dispatch. It uses Ubuntu 24.04 with CPython 3.13, installs the hash-locked JSON Schema dependency closure from `requirements/ci-taxonomy-cp313-ubuntu-24_04.lock`, and runs an explicit allowlist of 36 synthetic tests: 19 taxonomy registry, 3 taxonomy binding, and 14 OCR observation contract tests. It does not discover tests automatically. The `main` branch requires a pull request and a successful **Taxonomy registry and binding** check before merge.

To reproduce the workflow on Ubuntu 24.04 x86-64 with Python 3.13, install the locked dependencies and run the same three modules:

```sh
python -m pip install --disable-pip-version-check --no-input \
  --only-binary=:all: --require-hashes \
  -r requirements/ci-taxonomy-cp313-ubuntu-24_04.lock

PYTHONPATH=src:tests python -B -m unittest -v \
  test_taxonomy_registry \
  test_taxonomy_binding \
  test_ocr_contracts
```

The CI test modules build synthetic catalogs and values only. They do not require sample documents, OCR output, network access, or an OCR model. The workflow selects only the taxonomy registry, taxonomy binding, and OCR observation contract modules; it does not discover tests automatically. The new source preflight test module is run locally and awaits its own explicit CI change. The OCR contract tests are passive and synthetic; they do not activate an engine or load documents.

The [OCR observation contract](docs/ocr/observation-contract.md) defines a passive, typed boundary for future engine integration. It does not implement or activate OCR, rendering, document import, or a Windows runtime.

The [source preflight contract](docs/ocr/source-preflight.md) fingerprints in-memory bytes and recognizes a small set of leading signatures. It does not open files, validate document internals, enumerate pages, decode, or render.

The first R1 preflight tranche is tracked in [issue #22](https://github.com/voxer21582/OCR-dev/issues/22); its separate test module is not yet in the Actions allowlist.

## Data and scope

Do not add company documents, personal data, OCR text, credentials, or derived sensitive values to this public repository or its CI. No OCR engine, model, document ingestion, or external document service runs in this workflow. The workflow has read-only repository permissions and references GitHub Actions by full commit SHA.

The workflow is scoped to these 36 synthetic tests in three explicitly named modules; source preflight tests are not yet included. A successful run is not a full application test suite and does not establish OCR accuracy, document decoder compatibility, Windows runtime readiness, real-document safety, pilot usefulness, or release readiness.

Project tracking: [OCR2 — Gestione e controllo](https://github.com/users/voxer21582/projects/1).
