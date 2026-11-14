# PaddleOCR 3.7.0 / PP-OCRv6 medium — candidate feasibility

**Assessment date:** 2026-11-09

**Status:** documentary candidate only; A4 remains open. This document does not select or accept an OCR runtime.

## Scope and authorization

The owner authorized documentary investigation of **PaddleOCR 3.7.0 + PaddlePaddle CPU 3.2.0 + PP-OCRv6 medium**, with Italian and English as the candidate languages. The authorization covers source review only. It does not authorize artifact or model acquisition, installation, package resolution, local or hosted inference, Windows configuration, OCR activation, a pilot, or release. No software, wheel, model, or sample was downloaded or installed for this assessment.

The candidate is evaluated against the existing Windows 11 A4 acceptance plan. It is not evidence that OCR2 works on Windows. The earlier RapidOCR adapter/factory work is a separate integration direction already present in OCR2. This assessment neither replaces it nor proves that the two runtime paths can be combined; the product owner must select the implementation direction before either is made the accepted Windows runtime.

## Findings from official sources

| Area | Documented fact | What it does not establish |
| --- | --- | --- |
| Release identity | PaddleOCR tag `v3.7.0` resolves to release commit `b03f464`; that release introduces PP-OCRv6 and describes medium as 34.5 million parameters. | OCR2 compatibility or repeatable inference on the target PC. |
| Language | PaddleOCR’s PP-OCRv6 language table lists `it` and `en`; the release describes a 50-language model. The documentation source is a rolling `main` page, checked on 2026-11-09, not a version-pinned manual. | Accuracy for OCR2’s supported document families, financial fields, or the owner’s documents. |
| Python declaration | The v3.7.0 project metadata declares Python `>=3.8`, lists Python 3.13, and requires `paddlex[ocr-core]>=3.7.0,<3.8.0`, PyYAML, requests, aiohttp, and typing-extensions. | Availability and compatibility of the complete transitive Windows dependency closure. The declarations are not a tested Windows 11 install result. |
| PaddlePaddle wheel | PyPI lists `paddlepaddle-3.2.0-cp313-cp313-win_amd64.whl` at 101.7 MB with SHA-256 `5f59640901b44c99f1b03ec89f1785a66b04867d16f6d764908534dc07149418`. PyPI marks that file as lacking provenance / not published with Trusted Publishing. | That this package was downloaded, installed, or tested; a checksum supports byte integrity only when the expected digest is trusted. |
| Model sizes | PaddleX 3.7 model tables list PP-OCRv6 medium detection at 59.4 MB and recognition at 73.3 MB. The two listed weights total about 132.7 MB before dictionaries/configuration and any other pipeline models. | Installed footprint, peak disk use, RAM use, startup time, latency, or suitability for the target PC. The published performance figures are not Windows CPU results for OCR2. |
| Source-code licensing | PaddleOCR v3.7.0 and PaddleX `release/3.7` identify their repository source as Apache-2.0. | Licensing or redistribution rights for every model weight, dictionary, runtime binary, or transitive dependency in a future installer. |

Sources:

- [PaddleOCR v3.7.0 release](https://github.com/PaddlePaddle/PaddleOCR/releases/tag/v3.7.0)
- [PaddleOCR v3.7.0 package metadata](https://github.com/PaddlePaddle/PaddleOCR/blob/v3.7.0/pyproject.toml)
- [PP-OCRv6 language mapping and usage](https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html) (rolling upstream documentation, checked 2026-11-09)
- [PaddleX 3.7 text-detection models](https://paddlepaddle.github.io/PaddleX/3.7/en/module_usage/tutorials/ocr_modules/text_detection.html)
- [PaddleX 3.7 text-recognition models](https://paddlepaddle.github.io/PaddleX/3.7/en/module_usage/tutorials/ocr_modules/text_recognition.html)
- [PaddlePaddle 3.2.0 CPython 3.13 Windows x64 wheel and checksum](https://pypi.org/project/paddlepaddle/3.2.0/)
- [PaddleOCR v3.7.0 source license](https://github.com/PaddlePaddle/PaddleOCR/blob/v3.7.0/LICENSE)
- [PaddleX 3.7 source license](https://github.com/PaddlePaddle/PaddleX/blob/release/3.7/LICENSE)

## Assessment

**Potential fit:** official metadata and a matching CPython 3.13/Windows x64 PaddlePaddle wheel make the tuple plausible enough for further feasibility work. The documented Italian and English language identifiers match the language requirement. The medium model’s listed weights are materially larger than a small local adapter, and upstream describes this tier as server-oriented; that is a reason to measure it, not proof it cannot run on the target PC.

**Main risks and gaps:**

1. The exact Windows dependency closure, native DLL inventory, support baseline, and installer footprint are not known. The upstream dependency declarations are ranges, so a reproducible OCR2 lock would need every resolved wheel pinned and hash-verified.
2. No official, artifact-specific redistribution conclusion has been recorded for the detection and recognition weights, dictionaries, or all package dependencies. Repository Apache-2.0 notices do not close this gap.
3. The official CPython 3.13 wheel is listed, but package metadata alone does not prove the whole stack works together on Windows 11. The PyPI entry also reports no publishing provenance for this wheel.
4. Offline initialization, implicit model acquisition, CPU provider behavior, error handling, cancellation, resource bounds, memory, latency, and application-worker isolation have not been demonstrated.
5. Official benchmark claims do not represent OCR2 performance, invoices/receipts, or this Windows host. No real or synthetic OCR inference was run here.
6. OCR2 already has an optional RapidOCR-oriented adapter/factory. A Paddle-backed engine may need a different adapter or a separately approved integration; no code change is proposed by this document.

## Recommended next steps

1. Keep A4 open and OCR disabled. Decide whether PaddleOCR is the sole candidate for a bounded artifact/licensing plan or whether RapidOCR remains in the comparison. Do not treat this document as the selection.
2. Before acquisition, prepare a separately reviewed component inventory: exact package versions and hashes, source/tag revisions, model file identities and hashes, model and dictionary terms, dependency notices, and redistribution conclusions.
3. If and when artifact acquisition and testing are separately authorized, first resolve the complete dependency set in a disposable environment; then prepare a Windows 11 synthetic-only plan for installation, CPU inference, offline behavior, resource measurements, and cleanup. Use no real documents in GitHub CI.
4. Link any future result to the exact application commit and the frozen runtime tuple. Keep native Windows evidence separate from the existing taxonomy and application synthetic CI results.

## Provenance and verification record

- Prepared for OCR2 issue [#9](https://github.com/voxer21582/OCR-dev/issues/9) from the official sources linked above and the owner-authorized documentary scope.
- No code, package, model, dataset, output, configuration, or evidence from the previous OCR project was reused.
- No local checkout of the application, Windows settings, OCR2 workflow, or remote runtime configuration was changed.
- This document is not a dependency/license approval, candidate-selection decision, execution plan, runtime test, or A4 acceptance evidence.
