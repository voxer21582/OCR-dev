# Optional RapidOCR factory and RGB bridge: publication manifest

Date: 2026-11-08. Base: canonical main `0a2fba0731e230f385e305826b66e4ce17df854d`. Related migration: #42. This reviewed six-file source candidate is not an operational OCR runtime or an approved binary distribution. Publication is limited to these manifest files under the owner's existing source-migration mandate; the coordination handoffs themselves grant no publication authority.

## Scope and provenance

The coordinator received a new ownership assignment for the small factory module and seven direct synthetic tests in an isolated canonical branch. The source is the current OCR2 Document Intelligence development checkout, HEAD `df6f14a14d29f7d8cc792e1de62f42e42e895a2e`, not the previous OCR project. Original files and concurrent changes remain untouched. The prior owner decision already selects an optional RapidOCR path with OCR disabled by default; no engine decision is requested or inferred again.

| Candidate file | Owner / origin | Reason |
| --- | --- | --- |
| `application/src/alfa_document_intelligence/rapidocr_runtime_factory.py` | Coordinator; exact assigned current OCR2 factory | Deferred package loading, exact version, local model path/hash checks and multilingual parameters |
| `application/tests/test_rapidocr_runtime_factory.py` | Coordinator; seven selected tests from the assigned source | Construction/configuration failures without loading a real vendor runtime |
| `application/src/alfa_document_intelligence/rapidocr_adapter.py` | Coordinator; separate RGB-only handoff and compatibility adaptation | Explicit RGB input and buffer lifetime in the default path, preserving injected decoders |
| `application/tests/test_rapidocr_adapter.py` | Coordinator; focused synthetic RGB regressions | Distinct channel bytes and buffer lifetime, default version guard and unchanged callback contract |
| `application/CURRENT_STATE.md` | Coordinator; current preparation evidence | Distinguish local factory construction from operational acceptance |
| `docs/application/optional-runtime-factory-manifest.md` | Coordinator; this scoped inventory | Provenance, limits and excluded dependencies |

Pinned source factory SHA-256: `993a8bd58534ea654e6bcc54092460b6c67c34285581a591e53e20f3026b8f8d`; pinned source test file: `adf037560b03200775088d0ea11a3eadaf6d74a7b924d25df19f8e3f244e3305`. Destination factory is byte-identical. Destination seven-test file SHA-256: `8937a9ce82623484dd928d9983cfe361eafcf7ba3d6e50216a4897683045c14c` (raw preparation bytes).

No private Git history, personal path, company document, real OCR, package binary or model is included. Model hashes are configuration identifiers from the approved current-project design; they do not establish redistributability of a runtime payload. No new dependency or license is introduced by installation.

The subsequent RGB-only handoff pins source adapter `a9d0c566c56e5d27ad1b03644b07711434d7b0626716c2445950cbb3767254f2` and source test `45fb4d1b777b127fd2f3dd8095185c1bcac327f990c751db918b3eb9a0e69247`. Only the explicit RGB helper, default call lifetime and necessary imports were adapted; the public `image_decoder` keyword and single-object callback result remain supported. The source `image_builder` API rename and unrelated output/geometry changes were excluded.

## Verification

Before migration the direct module could not import the missing factory. After adding the assigned module, the explicit command `PYTHONPATH=src:tests python -B -m unittest -q test_rapidocr_runtime_factory test_rapidocr_adapter` from `application/` passed **16 tests**: seven factory and nine adapter (use `;` on Windows). Factory tests replace package-version lookup, vendor import and model manifest with fake objects and known synthetic bytes. No inference, model download or vendor package import was performed. AST parsing and whitespace checks passed. Independent read-only review returned READY for this bounded local preparation and independently passed the same 16 tests. This does not approve public delivery or runtime activation.

Three focused RGB test methods then reproduced four failing subcases before the bridge correction. The corrected scope passes **19 targeted tests** (seven factory + twelve adapter), preserving all nine previous adapter tests. It verifies different RGB channel bytes, dimensions, stride, buffer validity during the synchronous call and later release; it also verifies the unchanged single-object callback path, including tuples and legacy/custom version labels. The minimum version applies only to the default RawMemoryImage path. Vendor and NumPy modules are fake objects in these checks. The complete explicit 14-module local application allowlist passes **193 tests**. Independent read-only review of the expanded factory/RGB candidate returned READY, independently passed the 19 targeted tests and inspected the full allowlist evidence. This agent review is not a formal GitHub approval.

Final RGB source/test hashes (LF): adapter `e0e5a319d5aad553e8dc938d194a6dd2b9dce99b302db7b5056a69c6ddd38e48`; adapter test `8bce0ed383af4c3b679cec4ab382e232367ff7eb1155e53074878312349c65ed`.

## Dependencies and exclusions

The eighth source test, `test_worker_trusted_import_reference_resolves_factory_without_invoking_it`, and its `ocr_processing` import are deliberately pending worker integration. They are not claimed as passing or replaced by the seven direct tests.

The base adapter accepted the factory's constructor call, but passed a NumPy RGB array to the engine. Read-only inspection of the existing local RapidOCR 3.10.0 `load_image.py` confirms that arrays pass through while explicit RGB memory is converted to BGR. This candidate now uses the explicit RGB path by default and retains the buffer through the synchronous engine call, while injected `image_decoder` callbacks remain unchanged. Synthetic byte checks establish this adapter protocol, not actual vendor inference or OCR quality. Native runtime verification remains separate.

The factory does not itself isolate or time-limit execution, verify installed package-code integrity, or prevent model-file changes between hash verification and engine opening. It must be used only within a reviewed trusted local runtime and bounded worker. No worker, launcher, UI, archive, R7/R8, Windows configuration or runtime acceptance change is included. No CI module selection, merge, release or installation is performed by this candidate.
