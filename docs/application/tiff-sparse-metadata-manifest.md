# Bounded Classic TIFF metadata inspection

Date: 2026-11-09. Public base `58b3cd9b6c6044cfc507977c866153175beee1c8`, related to #42. This is inventory work towards multipage TIFF support, not an operational OCR acceptance.

## Exact candidate scope

| File | Ownership and reason |
| --- | --- |
| `application/src/alfa_document_intelligence/image_safety.py` | Assigned implementer; bounded random-access Classic TIFF metadata inspection and duplicate dimension rejection |
| `application/src/alfa_document_intelligence/ingestion.py` | Same implementer; use bounded snapshots for direct uploads and ZIP members while preserving hash, size and CRC checks |
| `application/tests/test_tiff_offset_fixture.py` | Same implementer; new synthetic TIFF and ZIP boundary cases |
| `application/INGESTION.md` | Coordinator; changed metadata budget, ZIP buffering and limitations |
| `application/CURRENT_STATE.md` | Coordinator; local result and unverified boundaries |
| `docs/application/tiff-sparse-metadata-manifest.md` | Coordinator; this inventory |

The source and tests adapt the existing reviewed public application. No previous OCR project code or original checkout files were copied or changed. The isolated source destinations were assigned for this task; historical original-source ownership is not inferred. No new dependency, native decoder, model, external service or real document is included.

## Behavior and safety boundary

Inventory follows Classic TIFF IFD offsets beyond the first MiB of an immutable bounded snapshot, for direct uploads and ZIP members. The existing 1 MiB default becomes a cumulative per-document TIFF metadata-read budget, including repeated/overlapping reads. Bounds, page count, per-page dimensions, cycle detection and member/upload limits remain enforced. The bytes-prefix API retains prefix semantics. BigTIFF remains unsupported. Duplicate width or height tags are now rejected even when equal, a deliberate compatibility restriction for ambiguous TIFF metadata.

ZIP inventory snapshots one bounded member at a time for all supported member formats, not only TIFF. It preserves declared/actual size and aggregate checks, ratio checks, EOF/CRC and hashing/inspection on the same bytes. With defaults, payloads can include the upload snapshot up to 25 MiB plus one expanded member snapshot up to 25 MiB, a 64 KiB read chunk and up to 1 MiB non-TIFF raster header; Python buffer capacity and temporary copies add variable overhead. This describes inventory payloads only, not a precise RSS bound or materialization/batch memory. Non-TIFF members were previously streamed for hashing and reread for inspection; their buffering and classification timing therefore change.

## Observed verification

From `application/`, with `PYTHONPATH=src:tests` (`;` on Windows):

```text
python -B -m unittest -v test_tiff_offset_fixture.TiffOffsetFixtureTests test_tiff_offset_fixture.TiffBoundaryTests test_tiff_offset_fixture.TiffReviewTests test_ingestion.IngestionTests
```

The final selected synthetic run reports **43 tests, OK**. The test fixtures include two-page II/MM TIFF-shaped structures with invented pixel strips, linked delayed IFDs, and independent stdlib structural assertions. They do not demonstrate full TIFF conformance or actual rendering. Direct and ZIP cases, CRC/size, duplicate dimensions, overlapping metadata reads, page/dimension limits and malformed offsets are covered in the selected suite. RED evidence exists for delayed IFD, metadata budget and duplicate-dimension behavior. Additional review tests were written after the implementation; no retroactive RED is claimed. A first review-test run had an invalid synthetic PDF signature and was corrected before the final green run. Raw commands, outputs and hashes are retained locally.

Independent technical/security review is READY on the final source, tests and evidence; the reviewer did not rerun them. Publication and CI reviews are separate. The existing CI selects the ingestion module, but not the new TIFF test module; an explicit selector is required in a separate CI proposal. No remote result is claimed before reading its logs.

## Exclusions

No complete TIFF validator or raster decoder safety claim, native Windows test, OCR engine/model, real data, archive persistence, R7/R8 work, installer or release. Full UI/runtime acceptance remains open. Owner approval is required for merge.
