# OCR2 Document Intelligence

This public repository is the shared OCR2 workspace. It contains versioned taxonomy contracts at the root and the selectively migrated Document Intelligence application under `application/`. The required CI check runs the taxonomy tests and an explicit list of synthetic application tests. This repository does not yet contain all locally developed application features.

## Continuous integration

The GitHub Actions workflow [OCR2 synthetic taxonomy](.github/workflows/ocr2-synthetic-taxonomy.yml) runs on pushes, pull requests and manual dispatch, with read-only permissions and actions pinned by commit SHA. It has two jobs:

- **Taxonomy registry and binding** (Ubuntu 24.04, CPython 3.13.18): the required check for `main`. It installs the hash-locked `requirements/ci-*-cp313-ubuntu-24_04.lock` files, runs the taxonomy tests, then runs **every** module in `application/tests` with pytest.
- **Windows application contracts** (windows-2025, CPython 3.13.18): the same modules on Windows, from `requirements/ci-tests-cp313-win-amd64.lock`, so that the DPAPI archive, the launcher and Windows paths run for real (DEC-011).

Modules are listed explicitly, without discovery; `application/tests/test_ci_workflow.py` fails if a module is missing from either job. Every test uses synthetic inputs only, generated in the repository; no test runs native OCR, downloads a model or transmits a document.

To run the same suite locally on Windows, from `application/` in an environment built from the approved locks:

```powershell
$env:PYTHONPATH='src;tests'
python -B -m pytest -q -rs -p no:cacheprovider tests
```

A passing run covers only these synthetic contracts. It does not establish OCR accuracy on real documents, installer or Windows acceptance, or product completion: see [`docs/STATUS.md`](docs/STATUS.md) and [`docs/plan.md`](docs/plan.md).

## Data and scope

Do not add company documents, personal data, OCR text, credentials, or derived sensitive values to this public repository or its CI. The workflow does not run native OCR or external document services. The public launcher leaves OCR disabled; configuring a real runtime and its background processing remains separate application work. The workflow has read-only repository permissions and references GitHub Actions by full commit SHA.

This CI result covers only the named synthetic contract modules. It is not a full application test suite and does not establish OCR accuracy, Windows runtime readiness, real-document safety, pilot usefulness, or release readiness. For implementation evidence and limitations, see [application current state](application/CURRENT_STATE.md); remaining migration work is tracked in [issue #42](https://github.com/voxer21582/OCR-dev/issues/42).

Project tracking: [OCR2 — Gestione e controllo](https://github.com/users/voxer21582/projects/1).

Windows runtime acceptance planning: [Windows 11 acceptance plan](docs/runtime/windows11-acceptance-plan.md). This is a planning document; it does not establish that an OCR runtime, model, or application has been accepted.
