# Optional page progress: publication manifest

Date: 2026-11-08. Initial base: public `main` at `68fea56e51606f4efb122c5738dada7180a81aae`; refreshed onto accepted `595753c5f92ece72b3081c340f31ae90795585e5` without changing the callback source or tests. Related migration: #42. The existing owner-approved background-job design includes this small processor interface; this contribution does not include the worker itself.

## Scope and provenance

| File | Owner / provenance | Inclusion |
| --- | --- | --- |
| `application/src/alfa_document_intelligence/document_processing.py` | Coordinator; selected callback hunk from current OCR2 source | Three added lines: optional keyword-only callback and notification after each validated page |
| `application/tests/test_document_processing.py` | Coordinator; three assigned synthetic cases adapted to the public base, with independent-review timing coverage | New unittest class and class-local RGB8 fake; existing helpers and free-function tests unchanged |
| `application/CURRENT_STATE.md` | Coordinator; verified base and candidate evidence | Distinguish processor progress from background-job and product acceptance |
| `docs/application/document-processing-progress-manifest.md` | Coordinator; this inventory | Provenance, checks and exclusions |

Source lineage is the current OCR2 Document Intelligence development checkout at `df6f14a14d29f7d8cc792e1de62f42e42e895a2e`, with concurrent changes preserved, not the previous OCR project. Original files remain untouched. Source SHA-256 pins: processor `b0d73b9627b175a3ccfbff5a7d6e7c49fa557f65e5f540da05fc1581d120f9bd`; tests `f32b0087ebae58399a3f43a5ad9db302e028245e34fd69df18ea93ed5f1ce1c7`.

Only the callback and three test cases were selected. No private Git history, local paths, documents, OCR output, credentials, dependencies or models are included. The separate source changes to catalog propagation, decoder defaults and resource hardening are excluded.

## Contract and verification

The optional callback receives only `(completed_page_number, declared_page_count)`, after that page passes the existing OCR contract and is appended to the inventory. Existing callers and the public decoder default remain unchanged. Progress does not publish a partial record. A generic callback exception follows the existing `ocr_failed` path, returning an unprocessed copy with no new pages or extracted fields.

From `application/`, the explicit command is:

```text
PYTHONPATH=src:tests python -B -m unittest -v test_document_processing.DocumentProcessingProgressTests
```

Use `;` as the path separator on Windows. RED ran three tests: compatibility already passed, while two new API tests failed with the expected missing-keyword error. GREEN ran **3 tests successfully**. The cases cover ordered page counts, omitted callback, and callback failure without partial publication or input mutation. Whitespace checks passed.

Independent review identified a test gap: checking only final counts could miss callbacks emitted before validation or all at the end. The same success test now checks interleaved OCR/progress events and a rejected second page emitting no progress. Two temporary local mutations (early and delayed callback) each failed this strengthened test; restoring the byte-identical production implementation passed all three cases. No production change was needed for this finding.

Static import inspection confirms all selected calls use existing application modules and the standard library. Every case injects a fake decoder and fake engine/image converter; lazy PIL, PDFium and NumPy paths are not called. The synthetic PDF header is held in memory and is not decoded by a native engine. No model, vendor runtime, process or UI is started.

The four existing pytest-style free-function tests are **not executed by this unittest class** and are not claimed as verified. Independent final review is READY after inspecting the strengthened timing tests, mutation evidence, final diff and import closure. This is agent review, not formal GitHub approval. The three new cases require an explicit class selector in a separate CI change; no discovery or workflow edit is included here. Remote results must be read separately before claiming CI coverage.

## Exclusions

No worker manager, native process limits, launcher, UI, persistent archive, R7/R8, Windows configuration, runtime acceptance or operational release. No catalog propagation or decoder behavior change. This contribution supplies one prerequisite for background progress; it does not make the public application an operational background OCR demo.
