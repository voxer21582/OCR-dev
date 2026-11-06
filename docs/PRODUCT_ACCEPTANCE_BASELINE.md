# OCR2 product acceptance baseline

**Status:** Draft baseline from the owner's product objective, 2026-11-06. This document makes the requested product scope traceable; it does not claim that the application exists or is accepted.

## Evidence boundary

The current public repository README describes a synthetic-testable taxonomy slice and explicitly says that it does not contain the full application. Its CI covers 22 taxonomy registry and binding tests only. This baseline therefore uses the owner's product objective as the source for application requirements. No code, configuration, model, or output from the excluded original checkout is used as evidence here.

Acceptance states below describe the evidence present in this repository snapshot. “Missing” means the application capability is not demonstrated here; it does not claim the capability is absent from every private or local checkout.

## Functional requirements

| ID | Required outcome | Acceptance evidence | Current state |
| --- | --- | --- | --- |
| FR-01 | Import PDF, PNG, JPEG, WebP, multipage TIFF, and additional formats only after support is assessed. Preserve the exact source while its case exists, until explicit user deletion (the owner's selected retention rule), and report unsupported, malformed, or truncated files without silent success. | Synthetic fixtures for every claimed format; format-specific page/frame counts; rejection tests for malformed and mismatched inputs; import result linked to a stable document ID; deletion evidence confirms removal under the approved retention rule. | Missing from this public repository. |
| FR-02 | Run an OCR engine through a replaceable adapter. Results identify page, text, geometry when available, confidence when provided, and engine/version/model provenance. | Adapter contract tests; synthetic OCR fixtures; an end-to-end run for each engine claimed as supported. A placeholder adapter is not an operational engine. | Missing. No OCR engine or model is included or claimed operational. |
| FR-03 | Classify documents using supported, configurable document types and a versioned taxonomy. | Taxonomy schema/validation tests; saved classification refers to the exact taxonomy version and hash; unknown or disabled types fail visibly. | Partial foundation: taxonomy registry and binding contracts are present; document workflow integration is not demonstrated. |
| FR-04 | Extract typed fields relevant to the selected document type, including dates, amounts, identifiers, and other configured fields. Retain provenance for each value. | Synthetic field fixtures with source page/region or OCR span; type/normalization tests; corrections and missing values represented without fabricated data. | Missing. |
| FR-05 | Validate extracted values, surface missing information and uncertainty, and avoid silently presenting uncertain values as verified. | Rule tests for valid, invalid, absent, and uncertain values; UI or API result exposes validation state and reason. | Missing. |
| FR-06 | Let a user inspect the source and results, correct fields, and distinguish machine output from human edits. | Synthetic review flow covers field correction, save, reopen, and retained provenance/audit metadata. | Missing. |
| FR-07 | Persist cases so they can be reopened, searched, and managed. A taxonomy snapshot bound to a case is immutable; changing it requires an explicit migration or rebind operation. | Storage tests for create/update/reopen/search; recovery and conflict tests; snapshot version/hash survives backup and restore; documented storage boundary and access behavior. | Partial foundation: taxonomy catalog and snapshot-binding modules are present; case-store integration is missing. |
| FR-08 | Export documented structured results in formats useful to downstream users. | Synthetic export round-trip tests; documented field meanings, provenance, encoding, and behavior for missing/uncertain fields. | Missing. |
| FR-09 | Handle failures without silent data loss; expose actionable, sanitized errors and recoverable state. | Failure-injection tests for import, OCR, persistence, and export; no raw document text or secrets in diagnostics. | Missing beyond taxonomy-layer sanitized errors. |

## Quality and operating requirements

| ID | Required outcome | Acceptance evidence | Current state |
| --- | --- | --- | --- |
| QR-01 | Run as a Windows 11 application on explicitly supported architectures and configurations. | Clean-machine install and launch evidence on each declared Windows target; import/review/save/reopen/export smoke flow; version/build recorded. | Not verified by the public taxonomy CI. Exact supported Windows editions/builds remain to be defined from product evidence. |
| QR-02 | Proposed default pending owner decision: process documents locally; any remote engine must be separately configured and make the transmission boundary explicit. Document bytes, OCR text, and derived sensitive values must not enter project telemetry. | Data-flow review, synthetic network-boundary tests, log inspection, and explicit evidence for any remote engine path. | Not implemented or accepted. Local-only versus optional remote OCR remains a product decision that materially affects architecture and privacy. |
| QR-03 | Make performance claims measurable against representative, synthetic inputs. | Reproducible benchmarks state hardware, formats, page counts, engine/model versions, and latency/memory results. | No product thresholds or benchmark evidence in this repository. |
| QR-04 | Make dependencies and licenses reviewable and keep installation/update behavior supportable. | Dependency lock and license inventory; installer and update tests; rollback/recovery evidence; no unverified engine/model artifacts. | Only the taxonomy CI dependency closure is documented. Application packaging and update policy are missing. |
| QR-05 | Use a modular architecture that permits additional OCR engines without claiming unintegrated engines as available. | Architecture tests enforce the adapter contract; capability listing is generated from installed and verified adapters. | Not implemented in this repository. |

## Acceptance gates

The product is not accepted until evidence covers the integrated workflow, not just individual modules:

1. Import each declared format and preserve source identity.
2. OCR all supported pages and retain engine/model provenance.
3. Classify and extract fields with validation and uncertainty states.
4. Review and correct results, then save, close, reopen, and search the case.
5. Export results with documented provenance and missing-value semantics.
6. Verify errors, privacy boundaries, performance, Windows installation, and update/rollback behavior.
7. Complete independent code/security review and owner acceptance of the resulting evidence.

The existing taxonomy CI is useful component evidence only. Its 22 passing tests do not satisfy these integrated acceptance gates.

## Recommended implementation order

This is a dependency proposal, not a live GitHub schedule. Issue status, ownership, dates, and PR state must be refreshed from GitHub before assigning work.

| Phase | Deliverable | Depends on | Evidence to advance |
| --- | --- | --- | --- |
| P0 | Finish the taxonomy snapshot-binding guard and integrate it through the required GitHub check. | A branchable, independent checkout and review/CI through the public repository. | Reviewed diff, required check green, and an owner-approved merge; this proves only the taxonomy contract. This proposal does not authorize a merge. |
| P1 | Define and implement bounded file intake and page decoding for the formats claimed in FR-01. | Decoder choices, dependency/license review, and synthetic fixtures. | Per-format page/frame decode, malformed/truncated rejection, source hash and provenance tests. |
| P2 | Resolve the approved Windows runtime and first OCR engine/model combination. | Owner decisions for the runtime/engine gates; license, provenance, hardware, and offline requirements. | Approved configuration and evidence plan. No model download or native run is implied by this document. |
| P3 | Integrate the selected engine behind the adapter contract and produce page-level results with provenance. | P1 decoded pages and P2 approved engine/runtime. | Synthetic contract tests plus an authorized end-to-end run for the engine actually named as supported. |
| P4 | Connect taxonomy classification, structured extraction, validation, missing-value and uncertainty states. | Versioned case/result model and P3 provenance-bearing OCR output. | Synthetic extraction and validation fixtures with field-level source references. |
| P5 | Deliver case persistence, reopen, search, and manual review/correction. | Approved storage boundary, immutable taxonomy snapshots, migration/recovery contract, and applicable test authority. | Save/reopen/search/review flow and failure-recovery evidence. Do not bypass any existing stop/no-retry condition. |
| P6 | Deliver documented exports, error recovery, and user-visible operational diagnostics. | P4 field model and P5 accepted case workflow. | Round-trip export tests, failure-injection evidence, and sanitized diagnostics. |
| P7 | Verify performance, security, Windows installation, and update/rollback; obtain product acceptance. | Integrated P1–P6 workflow and approved target hardware/Windows scope. | Reproducible benchmarks, security and license reviews, clean-machine installation evidence, and owner sign-off. |

At this baseline revision, P0's guard is locally implemented and reviewed but not integrated into GitHub; it still needs the required CI check and an owner-approved merge. Later phases remain unimplemented or subject to their stated prerequisites.

## Decisions still requiring product evidence or owner choice

- Whether OCR is strictly local or may use explicitly selected remote services. Recommendation: keep document data local by default; treat any remote engine as a separately approved capability.
- Which Windows 11 editions/builds and CPU architectures are supported for release.
- Which OCR engine/model and language set will be the first operational combination; licenses, provenance, offline use, accuracy, and hardware requirements must be verified before selection.
- Which document types and fields form the first accepted product scope. The taxonomy is versioned and extensible, but that does not itself define the launch set.
- Whether case storage is local-only or supports a shared/remote store, including backup and access-control expectations.
- Which export formats are required by the owner. JSON plus CSV are reversible candidates, not yet an approved product requirement.
- Numerical acceptance targets for page throughput, latency, memory, and maximum supported file size/page count.
- Installer/update channel and the acceptance process for production releases.

Until these decisions are supported by approved evidence, related acceptance states remain open. This baseline does not authorize real-document pilots, remote document processing, model downloads, Windows configuration changes, deployment, or release.
