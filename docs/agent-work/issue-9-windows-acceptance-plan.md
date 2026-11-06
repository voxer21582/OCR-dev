# Issue #9 — Windows 11 runtime acceptance plan (proposal)

**Status:** Draft for owner review; no engine, model, or packaging decision made.
**Prepared:** 2026-11-06
**Repository base:** `main` at `b9f1e021a4fc720a3388849b1d0b2b31586e7b85`
**Related issue:** [#9 — Complete the Windows 11 runtime acceptance plan](https://github.com/voxer21582/OCR-dev/issues/9)

## Purpose and boundary

This plan defines evidence required before OCR2 can claim a usable, supportable local OCR runtime on Windows 11. It separates decisions from tests and implementation. It does not select or install an engine, download models, modify Windows, run native tests, or accept a pilot. Protected `main` currently contains taxonomy schemas, binding/registry code, and synthetic tests. The engine-neutral OCR observation contract is in open PR #18. The bytes-only source-signature preflight is in open PR #23; PR #25 extends it with bounded caller-owned streams and corrects the PDF header-offset boundary. Neither preflight validates or decodes document contents. None of these branches implements an operational OCR engine.

The product target remains a local Document Intelligence application. Any component selected for this acceptance plan must run without uploading user documents or OCR output to an external service. The proposed engine-neutral OCR result contract in PR #18 requires integration to preserve source hash, page provenance, engine/model identity, text regions, and uncertainty.

## Evidence-based candidate comparison

These are candidates for evaluation, not selected dependencies.

| Candidate | Evidence and fit | Constraints to resolve before selection |
| --- | --- | --- |
| Tesseract 5 + a named trained-data set | The upstream engine is Apache-2.0. Its input documentation describes image formats supplied through Leptonica, including PNG, JPEG, TIFF, WebP, BMP and PNM. Its documentation says PDF is not a supported input, so PDF page rendering would be a separate component. `tessdata_fast` identifies its model files as Apache-2.0 and documents speed/accuracy trade-offs. | Evaluate the exact Windows binary, language files, transitive native libraries, signatures and per-file hashes. Select supported languages and a renderer; do not infer PDF support from the OCR engine. Confirm acceptance quality on an approved synthetic corpus. |
| PaddleOCR 3.x + named model artifacts | The upstream project declares Apache-2.0 for its code and describes OCR and document-layout pipelines. | The Python/runtime closure and model files must be separately pinned and audited; the repository license alone does not establish each downloaded artifact’s license or provenance. Estimate package/model size, CPU/RAM use, offline behavior and Windows support before selection. |
| Windows `Windows.Media.Ocr` API | Microsoft documents an OCR API returning text, lines, words and geometry. | Microsoft states that desktop apps need package identity (MSIX) to use this namespace. Choosing it therefore couples OCR selection to a packaging decision. Confirm available languages and behavior on each supported Windows image before considering it further. |

No runtime installer, package, model, or model card was downloaded or executed for this comparison. Candidate versions and artifacts remain unpinned.

## Acceptance stages and required evidence

### Gate 0 — Owner decisions before runtime work

Record explicit decisions for:

1. Packaging model: packaged/MSIX versus unpackaged desktop. This determines whether `Windows.Media.Ocr` can remain a candidate.
2. Engine shortlist and intended first engine. Keep the public result contract independent of that choice.
3. Initial languages and document classes, and the exact file formats/pages supported in the first usable release.
4. Accuracy thresholds and evaluation corpus policy. Use synthetic/authorized fixtures only; no real or company documents enter public CI.
5. Installation/update channel and whether network access is permitted only during install or never during operation.
6. Maximum file bytes, page count, memory, startup, and processing-time thresholds. These require a declared reference machine/runner and are not inferred from the current developer PC.

Until these are recorded, engine/runtime acceptance remains **blocked on owner decision**; the rest of this plan can be prepared without selecting a candidate.

### Gate 1 — Supply-chain and license record

For each exact runtime, native library, renderer, Python package and model artifact, retain:

- Publisher and canonical source URL; exact version/release and retrieval date.
- SHA-256; signature and verified signer where the distribution provides one.
- License for code, native dependencies, model weights, and separately sourced model data; required notices and redistribution conditions.
- Dependency lock/SBOM and platform/Python/architecture compatibility.
- A reproducible acquisition procedure and an offline verification procedure.

Acceptance: a clean reviewer can reconcile every installed file to this record. No unsigned or hash-mismatched artifact is executed. An upstream repository license is not treated as proof for every bundled model or third-party file.

### Gate 2 — Installation, update and recovery

Run only in an explicitly authorized disposable Windows 11 test environment after Gate 0. Record Windows edition/version/build, x64 architecture, package identity, privilege level and clean-image state without recording device identifiers.

Synthetic acceptance cases:

- Fresh install as a standard user where supported; record every elevation requirement.
- Verify installed versions, files, hashes/signatures and model availability.
- Successful offline application launch and OCR after install; confirm no document/model upload or unexpected network request.
- Interrupted install/update, missing model, corrupt package, insufficient disk space and locked-file recovery.
- Upgrade from the declared previous version; rollback to a known-good version; uninstall behavior and user-data retention/deletion.

Acceptance: each case has a reproducible procedure, expected result, logs with secrets and user content excluded, cleanup evidence, and an independent review. Do not run these cases on the developer’s everyday Windows environment without a separate authorization and plan.

### Gate 3 — Engine, format and result behavior

Use a versioned synthetic corpus with known text and expected page geometry. Report per-format and per-language results separately.

Required tests:

- Supported image formats and multi-page TIFF; PDF as text-based, scanned, mixed, rotated, encrypted, malformed, oversized and zero-page input.
- Page order/count, orientation, Unicode/Italian accents, mixed language, decimal/date/identifier strings, line breaks and region geometry.
- Blank pages, low-quality synthetic scans, unsupported languages and missing/corrupt models.
- Invalid/maliciously structured inputs: bounded resource use, stable errors, cancellation and no partial-result corruption.
- Result provenance: source SHA-256, page number, exact engine/model version, normalized text regions, confidence semantics, and clear distinction between unknown, missing, rejected and corrected values.

Acceptance: compute CER/WER and field-level precision/recall against the approved synthetic corpus; compare each candidate under the same settings. Thresholds remain **TBD by owner** until target document classes and quality requirements are agreed. A test passing does not establish quality for real documents or a pilot.

### Gate 4 — Security, privacy, performance and signoff

- Verify local-only behavior with network observation in the disposable environment; document every permitted connection, if any.
- Verify temporary files, logs, crash reports and database contents do not retain document text beyond the approved retention policy.
- Test size/page bounds, cancellation, error recovery, least privilege and data deletion.
- Measure cold/warm startup, throughput per page, peak memory and disk footprint on the declared reference environment; compare to owner-approved budgets.
- Review the final license/SBOM, test records, known limitations and recovery instructions independently.

Acceptance: explicit owner signoff for supported formats/languages, quality thresholds, install/update policy, retention behavior, supported Windows baseline and release limitations. No signoff is implied by green CI or a merged PR.

## CI plan

- Keep synthetic contract tests in the existing explicit GitHub Actions allowlist; do not discover test modules automatically.
- Add platform-independent tests for adapters, provenance mapping, bounds, errors and deterministic normalization only when the corresponding feature is authorized and present.
- Treat native Windows install/runtime checks as a separate workflow proposal. Before enabling it, confirm runner availability/cost, trigger effects, least permissions, and that it uses only synthetic fixtures. Do not add or require a Windows check before those conditions are reviewed.
- Keep native-runtime readiness separate from the required `Taxonomy registry and binding` check until an approved governance change says otherwise.

## Current status and next action

- **Verified:** protected `main` is at `b9f1e021a4fc720a3388849b1d0b2b31586e7b85` and its current tree contains taxonomy schemas, registry/binding code, and their synthetic tests. OCR observation contract PR #18, bytes-only source preflight PR #23, and stream extension PR #25 are open and unmerged. None is an operational OCR engine or full application.
- **Verified by official documentation:** Tesseract does not read PDF input directly; `Windows.Media.Ocr` requires package identity for desktop use; Tesseract and PaddleOCR repositories report Apache-2.0 for their code; Tesseract’s `tessdata_fast` repository reports Apache-2.0 for its model set.
- **Not verified:** candidate binaries or models, exact dependency closure, license obligations for selected artifacts, Windows installation/update, OCR quality, offline/network behavior, performance, security, and product acceptance.
- **Next:** owner records Gate 0 decisions. Then prepare an artifact-specific license/provenance manifest and a disposable Windows execution packet for review; seek separate authorization before downloads, installations, or native tests.

## Primary references

- Tesseract engine, license and dependency notice: <https://github.com/tesseract-ocr/tesseract>
- Tesseract input formats, including PDF limitation: <https://github.com/tesseract-ocr/tessdoc/blob/main/InputFormats.md>
- Tesseract trained-data sets and trade-offs: <https://github.com/tesseract-ocr/tessdoc/blob/main/Data-Files.md>
- `tessdata_fast` repository and model-set license: <https://github.com/tesseract-ocr/tessdata_fast>
- PaddleOCR project and license: <https://github.com/PaddlePaddle/PaddleOCR>
- Microsoft `Windows.Media.Ocr` package-identity requirement: <https://learn.microsoft.com/en-us/uwp/api/windows.media.ocr?view=winrt-26100>
