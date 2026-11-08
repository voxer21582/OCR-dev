# Bounded OCR protocol: publication manifest

Date: 2026-11-08. Related migration: #42. Accepted base: `1f4e835999b50cd73d8d4d337a975946609137a6`. This is Task 1 of the owner-approved background OCR design/plan: explicit limits and pure JSON framing, without a worker implementation.

## Exact scope and provenance

| File | Owner / provenance | Inclusion |
| --- | --- | --- |
| `application/src/alfa_document_intelligence/ocr_processing.py` | Assigned implementation agent; newly authored from the reviewed Task 1 contract | Frozen explicit limits and bounded encode/decode functions |
| `application/tests/test_ocr_processing.py` | Same assigned implementation agent; new primitive synthetic fixtures | Independent encoder/decoder and limit-boundary checks |
| `application/CURRENT_STATE.md` | Coordinator; observed local and remote evidence | Distinguish accepted main, this candidate and unverified worker responsibilities |
| `docs/application/bounded-ocr-protocol-manifest.md` | Coordinator; this inventory | Provenance, reproduction, scope and exclusions |

The implementation agent did not read or copy the original untracked worker module or its tests. Those files remain read-only, and their historical authorship/deltas were not attested by the handoff. The scoped assignment covers only new files in the isolated destination. The coordinator's approved-requirement and compatibility analysis informed an independently reviewed internal contract; source hashes were not treated as proof of authorship or publication rights. No previous OCR project code, private history or source files are transferred.

No dependencies, model artifacts or third-party code are added. The new implementation uses the Python standard library. Existing project licensing is unchanged. Only these four files are proposed; local plans, raw logs, workspace paths, session metadata and original checkouts are excluded. All fixtures are invented JSON values, bytes and numeric limits, without documents or OCR text.

## Contract and limits

`OCRProcessLimits` is frozen and requires nine explicit positive settings; it supplies no production defaults. It rejects invalid/nonfinite/boolean limits and unsupported platform names. This validates configuration only: it does not apply memory limits, start a process or prove Windows behavior.

The v1 internal protocol contains start, status, result, complete and error envelopes. Encoding validates a bounded mapping/tree and counts escaped UTF-8 bytes before serialization. Decoding checks the byte cap before UTF-8/JSON parsing and rejects malformed data, duplicate keys, nonfinite numbers, invalid types/keys/version/kind, excessive nesting/entries and invalid envelope shapes. Failures return no partial object and use a generic payload-free protocol error. Encoder and decoder tests are independent; malformed decoder inputs are constructed directly.

Limits include depth32, at most100000 aggregate collection entries, 64-bit signed-magnitude integer bounds, and an explicit per-call frame byte cap. Constructor ceilings are validation bounds, not recommended allocations. Start sources use canonical strict base64, with decoded bytes bounded by the smaller of the frame cap, the declared source cap and25MiB; the entire frame must also fit. Catalog JSON is bounded to64KiB. Tests use small configured source caps and modest synthetic values rather than allocating maximum-size frames.

Catalog version/hash tuples and terminal digests are checked for shape only. Reconstructing and verifying the catalog, source records, aggregate digest and complete result set are future worker duties. Safe identifier/code generation is a trusted-caller responsibility: syntax alone cannot establish that supplied values lack sensitive text or paths. No browser endpoint or disclosure is introduced. Post-parse depth checks do not prove that every allocation was prevented before parsing, and these functions do not guarantee protection from all host resource exhaustion.

## Observed verification

From `application/`:

```text
PYTHONPATH=src:tests python -B -m unittest -v test_ocr_processing.OCRProcessLimitsTests test_ocr_processing.OCRFrameProtocolTests
```

Use `;` on Windows. Initial RED failed because the new module was absent. The first implementation passed8 tests. Independent review then found whole-string/mapping allocations could occur before byte-budget rejection and requested exact-boundary coverage.

The correction's retained RED reproduced eager mapping exhaustion. Escaped/multibyte serializer regressions were added in the same method but were not independently observed failing in that RED, so no such reproduction is claimed. After the bounded encoding correction and all test additions, the final authorized run passed **11 tests, OK**. Exact/over boundaries, hand-built malformed decoder input, strict base64, catalog byte caps and serialization-entry checks are included. Raw commands, output, exit codes and final hashes are retained locally. Static parsing and whitespace checks passed.

Independent final code review is READY after inspecting the correction, test evidence, hashes and import scope. This is an agent review, not formal GitHub approval. Refreshing the base to the accepted catalog main left the two reviewed source/test files byte-identical. Remote CI results are not inferred from this local run; a separate CI-only PR must select the two classes explicitly.

## Exclusions and acceptance

No worker manager, multiprocessing, dynamic callable loading, process limits attachment, OCR engine/model, native decoder, session publication, UI, archive, installer, deployment or release. R7/R8 stop/no-retry remains unchanged. No existing callers invoke these new functions. This accepts only a proposed pure protocol prerequisite, not background OCR, complete application security or Windows/product readiness. Publication review and owner-approved merge remain separate steps.
