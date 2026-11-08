# Document-family record binding: publication manifest

Date: 2026-11-08. Base: canonical `main` at `0a2fba0731e230f385e305826b66e4ce17df854d`, after the owner-approved merges of PRs [#47](https://github.com/voxer21582/OCR-dev/pull/47) and [#46](https://github.com/voxer21582/OCR-dev/pull/46). This slice was initially developed on catalog commit `51925e7e1cedc1a2c639627e074b58d100efb921`, then rebased without source/test changes onto the merged base. Related migration: [#42](https://github.com/voxer21582/OCR-dev/issues/42).

This candidate binds custom document families and fields to self-verifying definitions in the record. Schema 0.1.0 records remain supported without conversion; 0.2.0 records require embedded catalog snapshots. Selecting a family, observing a candidate, or assigning a custom field never establishes fiscal validity or administrative approval.

## File-level scope

| Included file | Owner and provenance | Reason |
| --- | --- | --- |
| `application/src/alfa_document_intelligence/contracts.py` | OCR2 coordinator; assigned catalog-only hunks from the current Document Intelligence development checkout, plus scoped binding corrections | Verify snapshots, custom family references, field declarations and typed values |
| `application/src/alfa_document_intelligence/schemas/document.schema.json` | OCR2 coordinator; assigned catalog-only schema delta from the same source | Versioned structural contract and snapshot definitions |
| `application/tests/test_document_contract.py` | OCR2 coordinator; nine assigned synthetic catalog tests, one updated schema assertion, and three new synthetic boundary regressions | Legacy compatibility, binding and type checks |
| `application/CURRENT_STATE.md` | OCR2 coordinator; current verification results | State evidence and acceptance limits |
| `docs/application/document-family-record-manifest.md` | OCR2 coordinator; this migration inventory | Explain provenance, publication scope and exclusions |

The handoff assigns these changes in the isolated canonical branch; it does not assert a retrospective release by every historical contributor. The upstream development source is the current OCR2 Document Intelligence project, not the previous OCR project. Its baseline is `b144750b0945e8aea403b04d3f651f7b931b3a47`; source checkout HEAD was `df6f14a14d29f7d8cc792e1de62f42e42e895a2e` with concurrent changes preserved. Raw source pins checked before extraction:

- contracts: `7bb5ad5b4e856580e5b65085b7051f018c1272ad7f9571b2b99bff7ae0eb025a`
- schema: `183406a0b529e699338dde38f5f943a2cfabd4352f8fd821f47bbf164b5496ab`
- tests: `3bbdf8f9ec5ea5ea54a1cfe9d2cbf45d6682d08a9af93bf4e8ea1f238cb8bc43`

Only selected hunks are migrated, not those complete mixed files or their private Git history. No dependency or license change. No company documents, real OCR, personal paths, raw diagnostics, model artifacts or credentials are included.

## Verification and limits

The 13-module synthetic application allowlist passes 195 tests locally, including 28 document-contract tests and 41 catalog tests. Before migration, the updated 25-test contract module reported seven failures and three absent-schema-key errors. After migration, two further binding gaps were reproduced and corrected: direct selected custom-family candidates lacked snapshot enforcement, and legacy records could declare empty snapshots contrary to their schema. Legacy schema versions are compared without assuming hashable input.

The existing public workflow already selects `test_document_contract` and, following PR #47, `test_document_family_catalog`; the import extension reaches only the catalog and OCR contract dataclasses, not an OCR engine. No workflow changes are included. Base `main` passed 22 taxonomy and 183 application tests in [run 42519804658](https://github.com/voxer21582/OCR-dev/actions/runs/42519804658). Local success is not a claim of a GitHub run for this new branch or product acceptance.

Independent read-only review returned **READY**: 69 targeted contract/catalog tests and 35 additional synthetic probes passed, including valid v1/v2 snapshots, non-mutation, malformed shapes, altered hashes, duplicates and alternative amounts. The reviewer inspected the 195-test run evidence and the final publication scope. This is an agent review, not a formal GitHub approval. JSON Schema validation with a schema engine was not executed locally because `jsonschema` is absent in that environment; schema checks here are static/structural. No dependency was installed.

Final reviewed source SHA-256 (LF-normalized content):

- contracts: `71b6fcb7d5ee9a63d2683e22176923608d23d60d94e28cad3e5df6278a98477e`
- schema: `d3ffc32dba068d1f8fddffdbab449e3ccaf10d40f4335c87b22e0d7e99400013`
- tests: `5f5130569a1e7271a628af0a3c83879e1a22d185e126c1d2cfbcde24aeffee40`

Excluded: generic geometry/confidence hardening, pipeline/semantic integration, UI and launcher, archive migration or restore, R7/R8, native Windows probes, runtime/model installation, installer builds, and operational release. The custom field `required` metadata is retained; enforcing missing required fields during document validation is a separate integration task. No record store is modified by this contribution.
