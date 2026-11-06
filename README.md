# OCR2 Document Intelligence

This public repository is the shared OCR2 workspace. It contains versioned taxonomy contracts at the root and the Document Intelligence application under `application/`. The application directory contains source, synthetic fixtures/tests, and technical documentation. The required root CI check currently runs only taxonomy registry and binding tests; application tests are not yet included in that check.

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

The selected modules build synthetic catalogs and use temporary SQLite directories where persistence is needed. They do not require sample documents, OCR output, network access, or an OCR model. The same command selects 19 registry tests and 3 binding tests; it does not validate the application in `application/`.

## Data and scope

Do not add company documents, personal data, OCR text, credentials, or derived sensitive values to this public repository or its CI. The taxonomy workflow does not run OCR or external document services. Application OCR is disabled by default and is outside this workflow. The workflow has read-only repository permissions and references GitHub Actions by full commit SHA.

This CI result covers only the taxonomy registry and binding test modules. It is not a full application test suite and does not establish OCR accuracy, Windows runtime readiness, real-document safety, pilot usefulness, or release readiness.

Project tracking: [OCR2 — Gestione e controllo](https://github.com/users/voxer21582/projects/1).