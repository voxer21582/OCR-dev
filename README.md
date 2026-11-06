# OCR2 contracts

This repository currently contains a small, synthetic-testable slice of OCR2: versioned taxonomy catalog validation and updates, hash-bound taxonomy bindings, and an engine-neutral OCR page/result contract. It does not contain the full application or an operational OCR engine.

## Continuous integration

The GitHub Actions workflow [OCR2 synthetic taxonomy](.github/workflows/ocr2-synthetic-taxonomy.yml) runs on pushes, pull requests, and manual dispatch. It uses Ubuntu 24.04 with CPython 3.13, installs the hash-locked JSON Schema dependency closure from `requirements/ci-taxonomy-cp313-ubuntu-24_04.lock`, and runs all 22 tests in the taxonomy registry and binding modules. The `main` branch requires a pull request and a successful **Taxonomy registry and binding** check before merge.

To reproduce the workflow on Ubuntu 24.04 x86-64 with Python 3.13, install the locked dependencies and run the same two modules:

```sh
python -m pip install --disable-pip-version-check --no-input \
  --only-binary=:all: --require-hashes \
  -r requirements/ci-taxonomy-cp313-ubuntu-24_04.lock

PYTHONPATH=src:tests python -B -m unittest -v \
  test_taxonomy_registry \
  test_taxonomy_binding
```

The test modules build synthetic catalogs and values only. They do not require sample documents, OCR output, network access, or an OCR model. The workflow currently selects the taxonomy registry and binding modules; it does not yet run the separate OCR contract tests. The expanded CI is tracked separately in issue #17.

The [OCR observation contract](docs/ocr/observation-contract.md) defines a passive, typed boundary for future engine integration. It does not implement or activate OCR, rendering, document import, or a Windows runtime.

## Data and scope

Do not add company documents, personal data, OCR text, credentials, or derived sensitive values to this public repository or its CI. No OCR engine, model, document ingestion, or external document service runs in this workflow. The workflow has read-only repository permissions and references GitHub Actions by full commit SHA.

The current CI result covers only the taxonomy registry and binding test modules. It is not a full application test suite and does not establish OCR accuracy, Windows runtime readiness, real-document safety, pilot usefulness, or release readiness.

Project tracking: [OCR2 — Gestione e controllo](https://github.com/users/voxer21582/projects/1).
