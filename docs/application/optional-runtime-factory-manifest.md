# Optional RapidOCR factory: local candidate manifest

Date: 2026-11-08. Base: canonical main `0a2fba0731e230f385e305826b66e4ce17df854d`. Related migration: #42. This is a bounded preparation candidate, not an operational OCR runtime or an approved distribution.

## Scope and provenance

The coordinator received a new ownership assignment for the small factory module and seven direct synthetic tests in an isolated canonical branch. The source is the current OCR2 Document Intelligence development checkout, HEAD `df6f14a14d29f7d8cc792e1de62f42e42e895a2e`, not the previous OCR project. Original files and concurrent changes remain untouched. The prior owner decision already selects an optional RapidOCR path with OCR disabled by default; no engine decision is requested or inferred again.

| Candidate file | Owner / origin | Reason |
| --- | --- | --- |
| `application/src/alfa_document_intelligence/rapidocr_runtime_factory.py` | Coordinator; exact assigned current OCR2 factory | Deferred package loading, exact version, local model path/hash checks and multilingual parameters |
| `application/tests/test_rapidocr_runtime_factory.py` | Coordinator; seven selected tests from the assigned source | Construction/configuration failures without loading a real vendor runtime |
| `application/CURRENT_STATE.md` | Coordinator; current preparation evidence | Distinguish local factory construction from operational acceptance |
| `docs/application/optional-runtime-factory-manifest.md` | Coordinator; this scoped inventory | Provenance, limits and excluded dependencies |

Pinned source factory SHA-256: `993a8bd58534ea654e6bcc54092460b6c67c34285581a591e53e20f3026b8f8d`; pinned source test file: `adf037560b03200775088d0ea11a3eadaf6d74a7b924d25df19f8e3f244e3305`. Destination factory is byte-identical. Destination seven-test file SHA-256: `8937a9ce82623484dd928d9983cfe361eafcf7ba3d6e50216a4897683045c14c` (raw preparation bytes).

No private Git history, personal path, company document, real OCR, package binary or model is included. Model hashes are configuration identifiers from the approved current-project design; they do not establish redistributability of a runtime payload. No new dependency or license is introduced by installation.

## Verification

Before migration the direct module could not import the missing factory. After adding the assigned module, the explicit command `PYTHONPATH=src:tests python -B -m unittest -q test_rapidocr_runtime_factory test_rapidocr_adapter` from `application/` passed **16 tests**: seven factory and nine adapter (use `;` on Windows). Factory tests replace package-version lookup, vendor import and model manifest with fake objects and known synthetic bytes. No inference, model download or vendor package import was performed. AST parsing and whitespace checks passed. Independent read-only review returned READY for this bounded local preparation and independently passed the same 16 tests. This does not approve public delivery or runtime activation.

## Dependencies and exclusions

The eighth source test, `test_worker_trusted_import_reference_resolves_factory_without_invoking_it`, and its `ocr_processing` import are deliberately pending worker integration. They are not claimed as passing or replaced by the seven direct tests.

The public adapter accepts the factory's constructor call, but its default image path is not equivalent to the source integration: public main passes a NumPy RGB array, whereas the source uses explicit `RawMemoryImage(pixel_format="RGB")` and retains its buffer. A read-only inspection of the existing local RapidOCR 3.10.0 `load_image.py` confirms that arrays are passed through while explicit RGB memory is converted to BGR. The factory tests never call recognition, and do not establish correct input-channel behavior. Reconciling that adapter boundary while preserving the public `image_decoder` injection interface is a separate assigned/reviewed dependency before launcher use.

The factory does not itself isolate or time-limit execution, verify installed package-code integrity, or prevent model-file changes between hash verification and engine opening. It must be used only within a reviewed trusted local runtime and bounded worker. No worker, launcher, UI, archive, R7/R8, Windows configuration or runtime acceptance change is included. No CI module selection, merge, release or installation is performed by this candidate.
