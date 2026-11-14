# Import format evaluation: GIF and BMP (requirement IMP-5)

Status: **evaluation and recommendation**, no code changed. Decision D4 (owner, 2026-11-14): GIF is to be evaluated in addition to the five supported formats.

## Rule applied

A format is admitted only if (a) its decoder is licensed and hash-locked, (b) resource limits apply, (c) malformed-input tests exist, and (d) provenance is preserved (IMP-5).

## GIF

| Check | Finding |
|---|---|
| Decoder | Pillow 13.0.0 (MIT-CMU) decodes GIF; it is already in the Windows runtime lock and the CI decoder lock. No new dependency. |
| Limits | The existing decoder checks dimension, pixel and total-pixel limits per page and already runs in the bounded isolated worker. |
| Animation | Animated PNG and WebP are rejected today. The same policy fits GIF: accept a single-frame GIF, reject one with more than one image frame. |
| Header inspection | `image_safety.py` needs a GIF reader: signature `GIF87a`/`GIF89a`, logical screen width and height in bytes 6–9 (little endian). The logical screen can differ from the first frame, so the decoder must check the real frame size too. Counting frames needs a bounded walk of the block stream, like the TIFF directory walk. |
| Colour | Palette and transparency must be flattened to RGB on a white background; this must be recorded, because transparent text on a dark backdrop would otherwise be lost. |
| Real-world value | Low: scanners and phones do not produce GIF; mostly screenshots and web images. |
| Risk | Low to moderate: a second image decoder surface, mitigated by the isolated worker and the limits above. |

**Where the code lists formats (change list for GIF, about eight source files plus tests):** `ingestion.py` (signature, suffix list, accepted kinds), `image_safety.py` (header reader), `document_decoder.py` and `isolated_decoder.py` (accepted kinds, expected Pillow format, animation policy), `local_intake_app.py` (file-picker list and media-type map), `document_processing.py` and `expense_reports.py` (media-type maps), `review_ui.py` (preview extension and signature check), and the document schema media-type values.

**Recommendation:** admit **single-frame GIF** as a low-priority item in increment M4, after the five core formats are accepted. Acceptance: signature and extension mismatch rejected; animated GIF rejected with a stable code; oversize logical screen rejected before decoding; a synthetic GIF with text goes through OCR with correct provenance; truncated and corrupt GIFs fail closed.

## BMP

Pillow decodes BMP, the header carries width and height at fixed offsets, and BMP has no animation or multi-frame form. Same limits and isolation apply. Real-world value is low (some old scanner software), risk low. **Recommendation:** admit together with GIF in M4, with the same acceptance tests (signature `BM`, dimensions from the DIB header, truncated files rejected).

## Not recommended now

- **HEIC/HEIF** (phone photos): needs `libheif` through an extra package, with an LGPL library and patent considerations; revisit with the licence review (D2).
- **JPEG 2000**: needs an extra native library and has a long security-fix history; revisit later.
- **Office documents:** out of scope; the user exports to PDF.
