# RapidOCR 3.10.0 candidate: upstream source evidence

**Reviewed:** 2026-11-12
**Status:** partial source review; not a legal opinion, redistribution approval, or runtime acceptance
**Related:** [issue #9](https://github.com/voxer21582/OCR-dev/issues/9)

## Scope

This note records public, upstream evidence for the already selected evaluation direction: RapidOCR 3.10.0, PP-OCRv6 multilingual small detection and recognition, and ONNX Runtime CPU 1.31.1. It does not select a different runtime, acquire artifacts, or change the product's disabled-by-default OCR setting.

## Facts verified from upstream sources

| Item | Versioned source evidence | What it establishes | What it does not establish |
| --- | --- | --- | --- |
| RapidOCR source | [`RapidOCR` v3.10.0 `LICENSE`](https://github.com/RapidAI/RapidOCR/blob/v3.10.0/LICENSE) declares Apache License 2.0; [v3.10.0 release](https://github.com/RapidAI/RapidOCR/releases/tag/v3.10.0) identifies the tagged release commit `bd941da`. | The upstream source repository's declared license and version identity. | License closure for the exact Python wheel, its transitive dependencies, or every bundled file. |
| PP-OCRv6 multilingual detector | [`default_models.yaml` at v3.10.0](https://github.com/RapidAI/RapidOCR/blob/v3.10.0/python/rapidocr/default_models.yaml) maps `multi_PP-OCRv6_det_small` to the ONNX file and SHA-256 `090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f`. | A versioned upstream model route and integrity value that match the candidate factory's detector pin. | Ownership, licensing or redistribution rights for the model file. A hash proves identity, not permission. |
| PP-OCRv6 multilingual recognizer | The same versioned [`default_models.yaml`](https://github.com/RapidAI/RapidOCR/blob/v3.10.0/python/rapidocr/default_models.yaml) maps `multi_PP-OCRv6_rec_small` to the ONNX file and SHA-256 `6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884`. | A versioned upstream model route and integrity value that match the candidate factory's recognizer pin. | Ownership, licensing or redistribution rights for the model file. A hash proves identity, not permission. |
| Language route | The same file lists `en` and `it` in the PP-OCRv6 multilingual supported-language set and maps the `small` detector and recognizer to multilingual model keys. | Upstream routing metadata for Italian and English in this candidate. | Recognition quality or acceptance for OCR2 documents. |
| ONNX Runtime | [`onnxruntime` v1.31.1 `LICENSE`](https://github.com/microsoft/onnxruntime/blob/v1.31.1/LICENSE) declares MIT; the exact tag also publishes [`ThirdPartyNotices.txt`](https://github.com/microsoft/onnxruntime/blob/v1.31.1/ThirdPartyNotices.txt). The [v1.31.1 release](https://github.com/microsoft/onnxruntime/releases/tag/v1.31.1) identifies commit `6af1a93`. | The upstream version and top-level license, and the existence of a release-specific third-party notices file. | Compliance of the exact Windows wheel/native DLL inventory or satisfaction of each notice obligation in the final installer. |
| Local ONNX model loading | In the v3.10.0 [`ONNX Runtime session`](https://github.com/RapidAI/RapidOCR/blob/v3.10.0/python/rapidocr/inference_engine/onnxruntime/main.py), a supplied `model_path` is validated and passed to `InferenceSession`; the model downloader is called only when `model_path` is `None`. | OCR2's explicit detector and recognizer paths avoid RapidOCR's default model-download branch, provided those paths remain set and the files pass verification. | That no other package code or dependency can access the network, or that all runtime paths have been exercised. |
| Recognition character metadata | The v3.10.0 [`TextRecognizer`](https://github.com/RapidAI/RapidOCR/blob/v3.10.0/python/rapidocr/ch_ppocr_rec/main.py) first reads a `character` key from ONNX metadata; otherwise it asks the model resolver for a dictionary URL and downloads a missing file when a URL is available. The v3.10.0 [`ONNX small multilingual route`](https://github.com/RapidAI/RapidOCR/blob/v3.10.0/python/rapidocr/default_models.yaml) declares a model URL and hash but no `dict_url`; the [`resolver`](https://github.com/RapidAI/RapidOCR/blob/v3.10.0/python/rapidocr/inference_engine/base.py) indexes that key directly. | The candidate must expose the embedded character list, or OCR2 must explicitly supply a verified local dictionary. With this exact route, absence of embedded metadata appears to fail during dictionary lookup rather than silently fetch a default dictionary. | The upstream source review itself did not inspect the exact candidate model metadata or exercise this failure path. A separate, read-only inspection of the exact hash-pinned local recognizer is recorded below; no model inference was performed as part of that inspection. |
| Exact local recognizer artifact | In the already-existing local demo environment, the PP-OCRv6 recognizer file was read-only SHA-256 checked (`6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884`, 21,234,383 bytes). A bounded Python standard-library protobuf scan of only top-level `ModelProto.metadata_props` found the `character` key and 18,708 newline-delimited entries. The environment's installed distribution metadata reports RapidOCR 3.10.0 and ONNX Runtime 1.31.1. | The exact pinned local model has the metadata RapidOCR 3.10.0 reads before attempting dictionary resolution; a separate dictionary is not required for this artifact. | It does not validate the characters' linguistic quality, installer contents, license completeness, or absence of network access. No model text, document, OCR output, or local path was published. |
| Model packaging behavior | RapidOCR's [installation guide](https://github.com/RapidAI/RapidOCRDocs/blob/main/docs/install_usage/rapidocr/install.en.md), consulted 2026-11-12, says the `rapidocr` wheel includes three models. Its [model list](https://github.com/RapidAI/RapidOCRDocs/blob/main/docs/model_list.md) says model routes can resolve hosted assets. The installed package inspected below also contains three ONNX artifacts and a model-specific license notice. | The existing local installation's observed model set and the documentation's default-routing warning. | The original wheel archive identity, the final OCR2 installer contents, whether every bundled model is loaded, or whether OCR2 is network-free. The documentation pages are on `main`, not a version-pinned documentation tag. |

## Installed-package license and asset observations

These observations come from the already-existing local demo environment; no package or model was acquired for this review.

The existing demo environment is CPython 3.13.15, Windows 11 x64 (`AMD64`). PyPI's release metadata identifies the candidate archive files and expected SHA-256 values below. These are index metadata only: neither wheel archive was downloaded or compared with these digests, so they do not establish the identity of the installed distributions.

| Distribution | Candidate wheel from PyPI | Expected SHA-256 from PyPI metadata | Scope |
| --- | --- | --- | --- |
| RapidOCR 3.10.0 | [`rapidocr-3.10.0-py3-none-any.whl`](https://pypi.org/pypi/rapidocr/3.10.0/json) (27,288,134 bytes) | `2fc34e26cd0f48514804a94f8832283039c7334076bff60768b1fed9ad068050` | Universal wheel filename; digest is an expected archive identity from PyPI JSON, not locally verified. |
| ONNX Runtime 1.31.1 | [`onnxruntime-1.31.1-cp313-cp313-win_amd64.whl`](https://pypi.org/project/onnxruntime/1.31.1/#files) | `0558f29d5f6ac09957390c9c5495931485ee8ae7f0ce781ccee86a0ae5c2348b` | Filename matches CPython 3.13 Windows AMD64; PyPI lists the file without provenance. Digest is not locally verified. |

These two records do not constitute the candidate's complete dependency lock: the transitive dependency closure, platform-specific wheel selection for every dependency, and hashes for each selected artifact still need to be captured and reviewed before a reproducible package can be claimed.

| Distribution | Installed metadata and files observed | What remains unproven |
| --- | --- | --- |
| RapidOCR 3.10.0 | `importlib.metadata` reports `License-Expression: Apache-2.0`, `License-File: LICENSE` and `MODEL_LICENSES.md`, and 187 files recorded for the installed distribution. The installed `MODEL_LICENSES.md` (SHA-256 `C5FD0E8603D3DF743355B546121E6FE0F4EF8FF455C5A85C1681FD3AE520E153`) separates source-code and model copyrights, states Apache-2.0 for its listed models, and includes the three ONNX filenames and expected hashes below. The installed source license file SHA-256 is `3E0AF25FDD06AA9586AE97ADB00EA927EBE5A3805AC77D2D3A81CE5F55693333`. | These installed files do not identify the original wheel archive hash or prove that the final OCR2 installer retains all required notices. The notice's attribution and redistribution conditions still need an independent licensing review. |
| ONNX Runtime 1.31.1 | Installed metadata reports `MIT License`, 629 files recorded, and both `LICENSE` (SHA-256 `C250D6278F0B47A6439FB7592B08B58A55EB9F535AA49A1DB63211C3F982B674`) and `ThirdPartyNotices.txt` (SHA-256 `C53A76501EF60DB6F865F20599F220761201AC4057683ACEFDAB37D861B86622`, 344,457 bytes). | Presence and hashes do not validate every notice entry against the final packaged native DLLs or prove installer compliance. |

The three `.onnx` files present in that installation were hashed locally and match both the v3.10.0 model registry and the installed model notice:

| Artifact | Bytes | SHA-256 | Candidate use |
| --- | ---: | --- | --- |
| `PP-OCRv6_det_small.onnx` | 9,929,594 | `090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f` | Detector, used by the candidate |
| `PP-OCRv6_rec_small.onnx` | 21,234,383 | `6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884` | Recognizer, used by the candidate |
| `ch_ppocr_mobile_v2.0_cls_mobile.onnx` | 585,532 | `e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c` | Classifier artifact present in the package; OCR2's candidate factory disables it |

The model notice attributes upstream model weights to Baidu and/or PaddleOCR rights holders and points to upstream model records. This is provenance and license evidence from the installed distribution, not legal advice or permission for OCR2 redistribution. The installed distribution's complete `RECORD` file, original wheel hash, transitive package/license closure, and the exact OCR2 installer file set have not been audited.

## Reconciliation with the OCR2 candidate

The current candidate factory pins and hashes two local PP-OCRv6 small ONNX files, passes their explicit local paths to RapidOCR, sets the local model root, and disables the classifier. Its synthetic factory tests exercise those parameters with fake models. The source confirms that explicit ONNX paths bypass the default model-download branch. The factory does not set `Rec.rec_keys_path`, so startup relies on the recognizer's embedded `character` metadata. A read-only, standard-library protobuf inspection of the already-present local recognizer confirmed that key in the artifact whose SHA-256 matches the candidate pin; installed package metadata also matched RapidOCR 3.10.0 and ONNX Runtime 1.31.1. The separate successful one-page synthetic smoke noted on [issue #9](https://github.com/voxer21582/OCR-dev/issues/9) is evidence that the candidate initialized and inferred in that one run; neither that smoke nor metadata inspection captured network events or guarantees offline behavior. These observations also do not prove installer contents, complete license closure, or OCR quality on the user's notes.

The upstream packaging note means the runtime package's *entire distributed contents* must be inventoried. Reviewing only the two model files that OCR2 explicitly uses is insufficient if the installer includes the unmodified wheel and its additional bundled content. Keep every artifact hash-bound to the exact candidate tuple.

## Remaining gate work

1. Capture and verify the original Windows wheel archive hash and the complete hash-bound dependency closure for the candidate; the installed demo environment does not establish those archive identities.
2. Reconcile the exact installer file set against every included dependency, native binary, data file, bundled model, license and notice. Include bundled-but-unused artifacts unless the final package demonstrably omits them.
3. Produce and validate a CycloneDX SBOM for the exact package candidate; the previously prepared local draft was not schema-validated and is not evidence of a complete installer SBOM.
4. Obtain independent licensing review for the complete, hash-bound bundle before any redistribution or release claim.
5. Keep the recognizer metadata observation tied to its exact hash; if the selected artifact changes, repeat the metadata gate under an approved procedure. Separately verify offline behavior using an approved bounded plan; source configuration, explicit local model paths, and one local artifact inspection do not prove that the full runtime makes no network requests.

Until those steps are complete, the RapidOCR candidate remains an evaluation direction, not a redistributable product tuple. No model or package was downloaded or installed for this note, and no real documents were accessed.

