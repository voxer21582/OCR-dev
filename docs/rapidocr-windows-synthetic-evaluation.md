# One-run RapidOCR Windows synthetic evaluation

Status: scoped implementation for an owner-authorized, single GitHub-hosted Windows run. This is an evaluation harness, not an OCR2 runtime choice or release.

## Scope and observable result

- One push to branch `codex/rapidocr-windows-smoke-20261107` triggers one `windows-2025` job. The evaluation workflow has no pull-request, schedule, or manual-dispatch trigger. Do not reuse or update that branch after the authorized run.
- It generates exactly seven authored synthetic pages in a runner temporary directory using Pillow's embedded, sized default font. It never reads a user file, repository sample document, document archive, or real OCR.
- It evaluates the RapidOCR 3.10.0 PP-OCRv6 small detector/recognizer through ONNX Runtime CPU. The wheel also contains its legacy text-line orientation classifier; that third model is hash-verified but explicitly disabled and never invoked. The runner verifies every bundled ONNX model SHA-256 before inference.
- It reports only aggregate CER/WER counters, total synthetic bytes, a combined synthetic-input digest, model hashes, package versions, and elapsed time. It does not print OCR text, emit per-case results, upload artifacts, or persist images or raw recognition output. The job summary contains the same aggregate JSON; GitHub retains ordinary workflow logs and summaries.
- The report measures only this generated fixture set. It does not establish representative accuracy, application integration, Windows Home support, accessibility, usability, or production suitability, and it does not enable OCR in the application.

## Runner and workflow effects

`OCR-dev` was verified public with protected `main` at `b9f1e021a4fc720a3388849b1d0b2b31586e7b85`. GitHub documents standard `windows-2025` runners as free and unlimited for public repositories. This workflow uses only `contents: read`, checkout and setup-python Actions pinned to full commit SHAs, and no secrets, cache, artifacts, self-hosted/larger runner, or paid service.

The one branch push also triggers the pre-existing `OCR2 synthetic taxonomy` workflow because that workflow listens to pushes on all branches. Opening a PR then triggers that existing taxonomy workflow and any applicable GitHub CodeQL checks; the new evaluation workflow has no PR trigger. `main`'s required check `Taxonomy registry and binding` is unchanged. No branch protection or Actions settings are changed by this PR.

## Hash-locked temporary dependency closure

The two lock files are specific to CPython 3.13 / Windows x64, and are not product runtime locks. PyPI JSON metadata and selected artifact SHA-256 values were checked directly. The normal wheel closure uses exact pins and hashes. The Windows-only `humanfriendly` dependency `pyreadline3==3.5.6` is pinned to its universal wheel. The only source distribution is `antlr4-python3-runtime==4.9.3`, required by OmegaConf 2.3.0. Its sdist hash is fixed and it is built with network-isolated pip build isolation disabled, after installing separately hash-locked setuptools, wheel, and packaging build tools. All other runtime inputs are selected as compatible wheels for Windows CPython 3.13 or universal pure-Python wheels.

| Component | Pin | License/provenance reviewed |
|---|---:|---|
| RapidOCR | 3.10.0 | Apache-2.0; package wheel SHA-256 is in the runtime lock; wheel bundles models and code. |
| ONNX Runtime | 1.31.1 | MIT; exact Windows CPython 3.13 wheel hash is locked. |
| PP-OCRv6 small detector/recognizer | bundled in RapidOCR wheel | RapidOCR's pinned model notice records Apache-2.0, attribution, source and hashes `090f04…1e1ff94f` and `6f3272…b3c14884`; the script checks full hashes before inference. |
| pyclipper, six | 1.4.0, 1.17.0 | MIT. |
| OpenCV headless | 4.12.0.88 | Apache-2.0. |
| NumPy | 2.2.6 | BSD-3-Clause; package license file also lists bundled third-party notices. |
| Shapely | 2.1.2 | BSD-3-Clause. |
| PyYAML, Pillow | 6.0.3, 12.1.0 | MIT; Pillow's license is MIT-CMU. |
| tqdm | 4.67.1 | MPL-2.0 AND MIT; Windows color support uses Colorama 0.4.6 (BSD-3-Clause). |
| OmegaConf, ANTLR runtime | 2.3.0, 4.9.3 | OmegaConf BSD-3-Clause; ANTLR BSD. The ANTLR source archive is hash-locked and built only in the disposable runner with separately pinned tools. |
| Requests, urllib3, certifi, charset-normalizer, idna | 2.32.5, 2.6.2, 2025.11.12, 3.4.4, 3.11 | Apache-2.0, MIT, MPL-2.0, MIT, BSD-3-Clause respectively. |
| colorlog, coloredlogs, humanfriendly | 6.10.1, 15.0.1, 10.0 | MIT. |
| pyreadline3 | 3.5.6 | BSD; Windows-only transitive dependency of humanfriendly; PyPI metadata has no provenance attestation, so only the exact wheel hash and upstream BSD license notice were verified. |
| flatbuffers, protobuf | 25.9.23, 6.33.5 | Apache-2.0 and BSD-3-Clause respectively. |
| sympy, mpmath | 1.14.0, 1.3.0 | BSD. |
| setuptools, wheel, packaging | 80.9.0, 0.45.1, 25.0 | MIT, MIT, Apache-2.0/BSD-2-Clause. Build tools are runner-only. |

This is a bounded metadata/license-notice review for the one evaluation, not a legal opinion or a production redistribution review. The dependency artifacts are fetched from PyPI over verified TLS only during the approved runner job. No dependency is installed or downloaded locally.

## Reproduction and gate

The workflow has a CPython 3.13 minor selector with its resolved patch recorded in aggregate output, exact explicit test-module list, pinned Actions, hash-required package installs, package-consistency check, and aggregate-only smoke command. The generator and metrics contract tests can run locally with the Python standard library; the optional Pillow image-rendering test is skipped where Pillow is absent. Native inference is intentionally not run locally.

No retry is authorized after a hash/provenance mismatch, unexpected network/model acquisition, non-synthetic input, raw text emission, or uncertain cleanup. A successful run is one feasibility observation only. It neither selects RapidOCR for product use nor closes any OCR2 acceptance gate.

## Primary sources reviewed

- [GitHub standard hosted runner pricing](https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/choose-the-runner-for-a-job)
- [RapidOCR 3.10.0 installation guide](https://rapidai.github.io/RapidOCRDocs/main/install_usage/rapidocr/install/)
- [RapidOCR 3.10.0 model registry](https://github.com/RapidAI/RapidOCR/blob/v3.10.0/python/rapidocr/default_models.yaml)
- [RapidOCR model license and attribution notice at commit `4a3070f`](https://github.com/RapidAI/RapidOCR/blob/4a3070f304467e6d426e78a82afea5cb1181f305/python/MODEL_LICENSES.md)
- [RapidOCR 3.10.0 PyPI files and metadata](https://pypi.org/project/rapidocr/3.10.0/)
- [ONNX Runtime 1.31.1 PyPI files and metadata](https://pypi.org/project/onnxruntime/1.31.1/)
- [pyreadline3 3.5.6 PyPI metadata and wheel hash](https://pypi.org/pypi/pyreadline3/3.5.6/json)
- [pyreadline3 upstream BSD license notice](https://github.com/pyreadline3/pyreadline3/blob/master/LICENSE.md)
- [PyPI JSON metadata](https://pypi.org/pypi/rapidocr/3.10.0/json)
