# OCR2 contracts

This repository currently contains a synthetic-testable slice of OCR2: versioned taxonomy catalog validation and updates, hash-bound taxonomy bindings, an engine-neutral OCR page/result contract, taxonomy-bound structured field candidates, structural validation of candidate states, and an in-memory human review ledger. It does not contain the full application or an operational OCR engine.

## Continuous integration

The GitHub Actions workflow [OCR2 synthetic taxonomy](.github/workflows/ocr2-synthetic-taxonomy.yml) runs on pushes, pull requests, and manual dispatch. It uses Ubuntu 24.04 with CPython 3.13, installs the hash-locked JSON Schema dependency closure from `requirements/ci-taxonomy-cp313-ubuntu-24_04.lock`, and runs an explicit allowlist of 85 synthetic tests: 19 taxonomy registry, 3 taxonomy binding, 15 OCR observation contract, 15 structured extraction contract, 14 structural validation contract, and 19 review ledger contract tests. It does not discover tests automatically. The `main` branch requires a pull request and a successful **Taxonomy registry and binding** check before merge.

To reproduce the workflow on Ubuntu 24.04 x86-64 with Python 3.13, install the locked dependencies and run the same six modules:

```sh
python -m pip install --disable-pip-version-check --no-input \
  --only-binary=:all: --require-hashes \
  -r requirements/ci-taxonomy-cp313-ubuntu-24_04.lock

PYTHONPATH=src:tests python -B -m unittest -v \
  test_taxonomy_registry \
  test_taxonomy_binding \
  test_ocr_contracts \
  test_extraction_contracts \
  test_validation_contracts \
  test_review_contracts
```

The test modules use synthetic catalogs, values, page bytes, geometry, and review events. They do not require sample documents, real OCR output, network access, or an OCR model. The workflow selects only the taxonomy registry, taxonomy binding, OCR observation, structured extraction, structural validation, and review ledger contract modules. These tests are passive and synthetic; they do not activate an engine or load documents.

The [OCR observation contract](docs/ocr/observation-contract.md) defines a passive, typed boundary for future engine integration. It does not implement or activate OCR, rendering, document import, or a Windows runtime.

The [field candidate contract](docs/ocr/field-candidate-contract.md) connects proposed structured values to the exact taxonomy snapshot and OCR page observations while preserving uncertainty and literal text. It does not perform extraction, normalization, fiscal interpretation, persistence, or human review.

The [structural validation contract](docs/ocr/validation-contract.md) reports required-field gaps, candidate states, and duplicate-candidate conflicts against the exact taxonomy snapshot. It does not interpret values or accept them.

The [review ledger contract](docs/ocr/review-ledger-contract.md) records immutable, in-memory human review events for an exact candidate/taxonomy snapshot and flags stale results. It does not provide a review UI or persistence; durable history belongs to the separate R7 storage work. Its 19 synthetic tests are included in the workflow's explicit allowlist.

## Data and scope

Do not add company documents, personal data, OCR text, credentials, or derived sensitive values to this public repository or its CI. No OCR engine, model, document ingestion, or external document service runs in this workflow. The workflow has read-only repository permissions and references GitHub Actions by full commit SHA.

The workflow is scoped to these 85 synthetic tests in six explicitly named modules. A successful run is not a full application test suite and does not establish OCR accuracy, Windows runtime readiness, real-document safety, pilot usefulness, or release readiness.

Project tracking: [OCR2 — Gestione e controllo](https://github.com/users/voxer21582/projects/1).
