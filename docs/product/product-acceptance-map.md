# OCR2 product acceptance map

Status: working baseline derived from the approved product objective. It is a
traceability aid, not product acceptance or a replacement for GitHub Projects.
The outcome column reflects approved scope; detailed verification proposals are
not new acceptance gates unless separately approved. Snapshot date: 2026-11-06.

## Scope authority

The approved outcomes in this map are derived from the user's persistent OCR2
goal supplied in this Codex conversation on 2026-11-06 (beginning “Realizzare
OCR2 come applicazione Windows completa di Document Intelligence”). That goal
explicitly lists the named import formats and evaluation of other compatible
formats, OCR and page provenance,
extensible engines, configurable classification, structured extraction,
validation and uncertainty, human review, persistence/search/document
management, documented export, error handling, performance, security,
installation, and updates. This conversation-level goal is the authority for
scope for this evidence map. A fuller product acceptance draft exists in
[`OBIETTIVO_PRODOTTO.md` in PR #14](https://github.com/voxer21582/OCR-dev/pull/14);
it is open and unmerged. This map is only an evidence/status overlay, not a
second specification or an acceptance of draft-only decisions. The verification
details below are proposals unless explicitly required by the conversation-level
goal or by an accepted project contract.

## Status meanings

- **Contract only:** a typed contract or synthetic tests exist; no application
  behavior is accepted by that evidence alone.
- **Not implemented here:** this public checkout has no corresponding runtime
  or application component.
- **Blocked/gated:** an existing decision or stop rule prevents the work.
- **Not verified:** implementation may exist elsewhere, but this repository
  contains no evidence that verifies it.

## End-to-end capabilities

| Capability | Approved outcome and proposed verification | Evidence in this checkout | Status / dependency |
|---|---|---|---|
| Import PDF, PNG, JPEG, WebP, and multipage TIFF | **Approved outcome:** import the named formats. **Open exploration:** evaluate other compatible formats during development; this does not itself promise support for every evaluated format. **Proposed verification:** preserve page order/source identity and report corrupt or unsupported input clearly. File/page limits are open technical values to set after runtime measurement, not an approved gate in this map. | No importer, renderer, or application entrypoint is present. | **Not implemented here.** Needs authorized app workspace. |
| OCR with page provenance | **Approved outcome:** recognize text, manage pages/provenance, and keep an architecture extensible to multiple OCR engines without calling unintegrated engines operational. **Proposed verification:** retain source hash, page number, geometry, engine/runtime identity, error/cancellation/partial-page state; measure accuracy separately. Real sample use requires its own data authorization. | [OCR observation contract](../ocr/observation-contract.md), `ocr_contracts.py`, and synthetic tests define typed output/provenance values. No engine or importer is integrated. | **Contract only.** Runtime/model choice and licensing remain under A4. |
| Extensible OCR engines | **Approved outcome:** architecture can accommodate multiple engines, with operational claims limited to integrated engines. **Proposed verification:** test adapter substitutability with synthetic/fake implementations; the objective does not require a second operational engine. | The OCR contract declares an engine-neutral protocol boundary only. | **Contract only.** A4 selection and runtime verification are prerequisites. |
| Document classification and taxonomy | **Approved outcome:** classify documents using supported, configurable types. **Proposed verification:** bind classifications and downstream results to a versioned taxonomy snapshot and expose uncertainty where classification is not decisive. Catalog editing UX is not specified by this objective. | Taxonomy catalog registry and binding contracts exist with synthetic tests. No classifier or application catalog-management UI is present. | **Contract only.** Classification behavior remains unimplemented. |
| Structured extraction | **Approved outcome:** extract structured information including relevant dates, amounts, identifiers, and other fields for supported document types. **Proposed verification:** preserve literal/normalized values, alternatives, uncertainty, and source/taxonomy provenance; evaluate accuracy only on an explicitly approved set. | [Field candidate contract](../ocr/field-candidate-contract.md) binds candidates and evidence. No extraction algorithm or accuracy evaluation is present. | **Contract only.** Do not infer extraction from candidate types. |
| Validation and missing information | **Approved outcome:** validate data, represent uncertainty, and identify missing information. **Proposed verification:** cover required-field gaps and conflicts; add semantic/cross-field checks only when their rules are defined for a supported type. | [Structural validation contract](../ocr/validation-contract.md) reports structural gaps, states, and duplicate candidates. | **Contract only.** Date, amount, identifier, fiscal, and cross-field rules are not implemented here. |
| Human review and correction | **Approved outcome:** display and manually review/correct results, preserving history and invalidating stale derived results. **Proposed verification:** source/page/region, alternatives and reasons are visible; keyboard flows and a synthetic browser walkthrough cover confirm/correct/reject/defer. | In-memory ledger contract and 19 synthetic tests are in draft/open PR #35; the explicit workflow change is draft/open PR #36. GitHub Actions run [42231487111](https://github.com/voxer21582/OCR-dev/actions/runs/42231487111) passed the full 85-test allowlist on push, and PR checks passed. Issue #34 remains open. No application screen or browser walkthrough exists in this checkout. | **Contract only; synthetic CI verified.** An authorized application workspace and user-facing walkthrough are outstanding. Durable restart behavior belongs to R7. |
| Persistent document management | **Approved outcome:** save, reopen, and manage documents across application restarts. **Proposed hardening questions:** backup/restore, concurrent writes, migration, and corruption recovery must be derived from the selected storage design before becoming acceptance gates. | No case database, document library, search, or persistence adapter is present in this checkout. | **Blocked/gated.** R7 stop/no-retry remains in force; do not start storage probes or tests without the required owner/evidence handoff. |
| Search and reopen | **Approved outcome:** search and reopen managed documents. **Open detail:** searchable fields, matching behavior, and filters should follow the actual user workflow; this map does not assume full-text search or a particular index design. | No search or reopen implementation is present. | **Blocked/gated** with durable case management under R7. |
| Export | **Approved outcome:** export data in useful, documented formats. **Open detail:** choose formats and representation of missing/uncertain fields with the application workflow; no specific format is imposed here. | No exporter or export schema is present. | **Not implemented here.** |
| Error handling, security, and privacy | **Approved outcome:** handle errors and meet the product's security needs. **Proposed verification:** cover invalid input, engine failure, stale state, and storage errors; define data flow, logging, temporary-file, and retention controls against an approved threat model. This map does not assume local-only processing. | Typed contracts use stable, sanitized error codes; synthetic tests cover some malformed values. No running app, storage boundary, threat-model verification, or real-file test exists here. | **Contract only / not verified end to end.** No real documents or secrets belong in public CI. |
| Performance and reliability | **Approved outcome:** deliver adequate performance and reliable behavior. **Proposed verification:** measure representative workloads and set latency/memory targets from actual runtime and user workflow before treating numeric thresholds as gates. | OCR region polygons are capped at 256 vertices to bound geometry checks; this is not an application performance benchmark. | **Not verified.** No numeric performance target is approved in this map. |
| Windows installation and updates | **Approved outcome:** make installation and updates verifiable for the Windows application. **Proposed verification:** test a clean install and supported upgrade on the selected Windows 11 runtime. Rollback, uninstall, and retention policies remain open until the installer/storage design is known. | No packaging, installer, updater, or Windows runtime artifact is in this checkout. | **Not implemented/verified here.** R1 Windows acceptance and runtime gates apply. |

## Cross-cutting acceptance rules

1. A green CI run proves only the explicitly named synthetic tests listed in the
   workflow at that revision. It does not prove OCR accuracy, application
   integration, Windows readiness, or product acceptance.
2. A contract is not an operational feature until an application component
   invokes it and the end-to-end acceptance evidence above exists.
3. Keep A4 runtime/model selection and A5 pilot decisions explicit. Do not
   substitute local synthetic fixtures for those gates.
4. Preserve R7/R8 and issue #8 stop/no-retry restrictions. Ownership or passing
   CI does not authorize resuming blocked persistence work.
5. Mark a capability accepted only after the evidence for that row is attached
   to its existing GitHub issue/PR and the owner accepts it. This map does not
   close or duplicate issues.

## Current verified boundary

This checkout is a public synthetic-testable contracts slice, not the complete
OCR2 application. It contains taxonomy, OCR value/provenance, extraction,
structural validation, and in-memory review contracts. It has no file importer,
operational OCR engine, UI, persistent case library, search, export, installer,
or updater. The R6 CI branch configures an explicit 85-test allowlist; run
42231487111 passed on push and the pull-request check passed. Local execution of
the R6 module stopped before discovery because the required `jsonschema` package
is unavailable in the current runtime; no package was installed. These GitHub
runs verify the listed synthetic contracts only, not the application UI or
overall product acceptance.
