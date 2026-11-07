# OCR2 taxonomy contracts

This repository currently contains a small, synthetic-testable slice of OCR2: versioned taxonomy catalog validation and updates, plus hash-bound taxonomy bindings. It does not contain the full application.

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

The taxonomy test modules build synthetic catalogs and use temporary SQLite directories where persistence is needed. They do not require sample documents, OCR output, network access, or an OCR model. The same command selects 19 registry tests and 3 binding tests in this repository snapshot.

## Data and scope

Do not add company documents, personal data, OCR text, credentials, or derived sensitive values to this public repository or its CI. The taxonomy workflow runs no OCR engine or model. The separate one-time Windows evaluation uses only generated synthetic pages and emits aggregate metrics and hashes. Both workflows use read-only repository permissions and Actions pinned to full commit SHAs.

This CI result covers only the taxonomy registry and binding test modules. It is not a full application test suite and does not establish OCR accuracy, Windows runtime readiness, real-document safety, pilot usefulness, or release readiness.

Project tracking: [OCR2 — Gestione e controllo](https://github.com/users/voxer21582/projects/1).

## One-time synthetic Windows OCR evaluation

This branch adds a separate, one-push-only evaluation of RapidOCR 3.10.0 with ONNX Runtime on seven generated synthetic pages. It is restricted to the branch `codex/rapidocr-windows-smoke-20261107`, uses a standard `windows-2025` runner, and reports aggregate metrics and hashes only. It does not upload images or OCR text and does not enable or select OCR in the application. The evaluation does not run on `main`, pull requests, schedules, or manual dispatches. See [the scope, dependency/license inventory, and limitations](docs/rapidocr-windows-synthetic-evaluation.md).
