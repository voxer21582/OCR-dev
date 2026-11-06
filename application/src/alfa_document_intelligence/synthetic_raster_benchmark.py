"""Render synthetic PDFs into bounded degraded PNG fixtures without Python packages.

Poppler is an explicit external renderer. The generated images remain synthetic;
they are not camera photographs, production scans, or OCR performance evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import struct
import subprocess
import tempfile
import zlib
from pathlib import Path
from typing import Any

from .benchmark_manifest import validate_manifest
from .synthetic_visual_benchmark import LABEL_VERSION, build_visual_corpus

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_DIMENSION = 12_000
MAX_PIXELS = 50_000_000


def decode_rgb_png(data: bytes) -> tuple[int, int, bytes]:
    """Decode non-interlaced 8-bit RGB/RGBA PNGs, validating chunk CRCs."""
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("renderer output is not a PNG")
    offset = len(PNG_SIGNATURE)
    width = height = bit_depth = color_type = interlace = None
    compressed = bytearray()
    seen_end = False
    while offset < len(data):
        if offset + 12 > len(data):
            raise ValueError("truncated PNG chunk")
        length = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4:offset + 8]
        end = offset + 12 + length
        if end > len(data):
            raise ValueError("truncated PNG data")
        payload = data[offset + 8:offset + 8 + length]
        expected_crc = struct.unpack_from(">I", data, offset + 8 + length)[0]
        if zlib.crc32(kind + payload) & 0xFFFFFFFF != expected_crc:
            raise ValueError("PNG chunk checksum mismatch")
        if kind == b"IHDR":
            if width is not None or length != 13:
                raise ValueError("invalid PNG header")
            width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
            if compression != 0 or filtering != 0:
                raise ValueError("unsupported PNG compression or filter method")
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            seen_end = True
            if length != 0:
                raise ValueError("invalid PNG end chunk")
            break
        offset = end
    if not seen_end or width is None or height is None:
        raise ValueError("PNG is missing required chunks")
    if not (0 < width <= MAX_DIMENSION and 0 < height <= MAX_DIMENSION and width * height <= MAX_PIXELS):
        raise ValueError("PNG dimensions exceed configured bounds")
    if bit_depth != 8 or color_type not in (2, 6) or interlace != 0:
        raise ValueError("only non-interlaced 8-bit RGB/RGBA PNGs are supported")
    channels = 3 if color_type == 2 else 4
    stride = width * channels
    expected_size = height * (stride + 1)
    try:
        inflater = zlib.decompressobj()
        raw = inflater.decompress(compressed, expected_size + 1)
        if inflater.unconsumed_tail or inflater.unused_data or not inflater.eof:
            raise ValueError("PNG compressed data exceeds declared dimensions or has trailing data")
        raw += inflater.flush()
    except zlib.error as exc:
        raise ValueError("invalid PNG compressed data") from exc
    if len(raw) != expected_size:
        raise ValueError("PNG decompressed size does not match dimensions")

    pixels = bytearray(height * stride)
    previous = bytearray(stride)
    source_offset = 0
    for y in range(height):
        filter_type = raw[source_offset]
        source_offset += 1
        encoded = raw[source_offset:source_offset + stride]
        source_offset += stride
        row = bytearray(stride)
        for x, value in enumerate(encoded):
            left = row[x - channels] if x >= channels else 0
            above = previous[x]
            upper_left = previous[x - channels] if x >= channels else 0
            if filter_type == 0:
                predictor = 0
            elif filter_type == 1:
                predictor = left
            elif filter_type == 2:
                predictor = above
            elif filter_type == 3:
                predictor = (left + above) // 2
            elif filter_type == 4:
                p = left + above - upper_left
                pa, pb, pc = abs(p - left), abs(p - above), abs(p - upper_left)
                predictor = left if pa <= pb and pa <= pc else above if pb <= pc else upper_left
            else:
                raise ValueError("unsupported PNG row filter")
            row[x] = (value + predictor) & 0xFF
        start = y * stride
        pixels[start:start + stride] = row
        previous = row

    if channels == 3:
        return width, height, bytes(pixels)
    rgb = bytearray(width * height * 3)
    for source in range(0, len(pixels), 4):
        alpha = pixels[source + 3]
        target = source // 4 * 3
        for channel in range(3):
            rgb[target + channel] = (pixels[source + channel] * alpha + 255 * (255 - alpha) + 127) // 255
    return width, height, bytes(rgb)


def encode_rgb_png(width: int, height: int, rgb: bytes) -> bytes:
    if not (0 < width <= MAX_DIMENSION and 0 < height <= MAX_DIMENSION and width * height <= MAX_PIXELS):
        raise ValueError("PNG dimensions exceed configured bounds")
    if len(rgb) != width * height * 3:
        raise ValueError("RGB byte count does not match dimensions")

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

    scanlines = b"".join(b"\x00" + rgb[y * width * 3:(y + 1) * width * 3] for y in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return PNG_SIGNATURE + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(scanlines, 9)) + chunk(b"IEND", b"")


def degrade_rgb(width: int, height: int, rgb: bytes, *, downsample: int, noise: int, seed: str) -> bytes:
    """Create deterministic grayscale, low-resolution and noisy scan-like pixels."""
    if not 1 <= downsample <= 6:
        raise ValueError("downsample must be between 1 and 6")
    if not 0 <= noise <= 24:
        raise ValueError("noise must be between 0 and 24")
    if len(rgb) != width * height * 3:
        raise ValueError("RGB byte count does not match dimensions")
    small_width = max(1, (width + downsample - 1) // downsample)
    small_height = max(1, (height + downsample - 1) // downsample)
    small = bytearray(small_width * small_height)
    for y in range(small_height):
        source_y = min(height - 1, y * downsample)
        for x in range(small_width):
            source = (source_y * width + min(width - 1, x * downsample)) * 3
            small[y * small_width + x] = (77 * rgb[source] + 150 * rgb[source + 1] + 29 * rgb[source + 2]) >> 8
    rng = random.Random(seed)
    if noise:
        for index, value in enumerate(small):
            small[index] = max(0, min(255, value + rng.randint(-noise, noise)))
    expanded_rows = []
    for y in range(small_height):
        row = b"".join(bytes((value, value, value)) * downsample for value in small[y * small_width:(y + 1) * small_width])
        row = row[:width * 3]
        expanded_rows.extend([row] * downsample)
    return b"".join(expanded_rows[:height])


def _renderer_version(executable: str) -> str:
    result = subprocess.run([executable, "-v"], capture_output=True, text=True, timeout=10, check=False)
    if result.returncode != 0:
        raise RuntimeError("PDF renderer version check failed")
    return (result.stdout or result.stderr).splitlines()[0].strip()


def build_raster_corpus(
    output_dir: Path,
    *,
    renderer: str = "pdftoppm",
    dpi: int = 150,
    downsample: int = 2,
    noise: int = 3,
) -> dict[str, Any]:
    """Build hash-linked grayscale PNG fixtures from generated PDFs via Poppler."""
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError("output directory must be empty")
    if not 72 <= dpi <= 300:
        raise ValueError("dpi must be between 72 and 300")
    if not 1 <= downsample <= 6 or not 0 <= noise <= 24:
        raise ValueError("degradation parameters are out of range")
    resolved_renderer = shutil.which(renderer) if not Path(renderer).is_absolute() else renderer
    if not resolved_renderer:
        raise FileNotFoundError("Poppler pdftoppm is required; no download or installation is performed")
    renderer_version = _renderer_version(resolved_renderer)
    output_dir.mkdir(parents=True, exist_ok=True)
    documents_dir = output_dir / "documents"
    documents_dir.mkdir()
    with tempfile.TemporaryDirectory(prefix="alfa-synthetic-raster-") as temporary:
        source_dir = Path(temporary) / "source"
        source = build_visual_corpus(source_dir)
        source_labels = [json.loads(line) for line in (source_dir / "labels.jsonl").read_text(encoding="utf-8").splitlines()]
        label_by_id = {row["case_id"]: row for row in source_labels}
        records = []
        labels = []
        source_hashes = {}
        for record in source["manifest"]["records"]:
            case_id = record["case_id"]
            source_hashes[case_id] = record["sha256"]
            pdf = source_dir / "documents" / f"{case_id}.pdf"
            prefix = Path(temporary) / case_id
            process = subprocess.run(
                [resolved_renderer, "-f", "1", "-singlefile", "-png", "-r", str(dpi), str(pdf), str(prefix)],
                capture_output=True, text=True, timeout=30, check=False,
            )
            if process.returncode != 0:
                raise RuntimeError("PDF renderer failed on a synthetic fixture")
            rendered = Path(str(prefix) + ".png")
            width, height, rgb = decode_rgb_png(rendered.read_bytes())
            degraded = degrade_rgb(width, height, rgb, downsample=downsample, noise=noise, seed=case_id)
            png = encode_rgb_png(width, height, degraded)
            digest = hashlib.sha256(png).hexdigest()
            image_name = f"{case_id}.png"
            (documents_dir / image_name).write_bytes(png)
            updated = dict(record)
            updated.update({
                "case_id": case_id + "-raster",
                "sha256": digest,
                "label_version": LABEL_VERSION.replace("visual", "raster"),
            })
            updated["group_keys"] = list(record["group_keys"])
            labels.append({
                **label_by_id[case_id],
                "case_id": updated["case_id"],
                "evidence": {
                    field: [{**ref, "source_sha256": digest} for ref in refs]
                    for field, refs in label_by_id[case_id]["evidence"].items()
                },
            })
            records.append(updated)
    manifest = {"manifest_version": "1", "records": records}
    validation = validate_manifest(manifest)
    (output_dir / "labels.jsonl").write_text("".join(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n" for row in labels), encoding="utf-8")
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    (output_dir / "generation.json").write_text(json.dumps({
        "generator": "synthetic-raster-v1",
        "renderer": renderer_version,
        "render_settings": {"dpi": dpi, "downsample": downsample, "noise": noise},
        "source_pdf_sha256_by_case": source_hashes,
    }, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "cases": len(records),
        "split_counts": validation["split_counts"],
        "renderer": renderer_version,
        "render_settings": {"dpi": dpi, "downsample": downsample, "noise": noise},
        "manifest": manifest,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--renderer", default="pdftoppm")
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--downsample", type=int, default=2)
    parser.add_argument("--noise", type=int, default=3)
    args = parser.parse_args()
    try:
        result = build_raster_corpus(args.output_dir, renderer=args.renderer, dpi=args.dpi, downsample=args.downsample, noise=args.noise)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        parser.error(str(exc))
    print(json.dumps({key: value for key, value in result.items() if key != "manifest"}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
