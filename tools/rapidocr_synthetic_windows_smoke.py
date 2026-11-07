"""One-run Windows-only RapidOCR smoke on seven generated synthetic pages."""
from __future__ import annotations

import contextlib
import hashlib
import importlib.metadata
import io
import json
import os
import platform
from pathlib import Path
import re
import sys
import tempfile
import time
from collections.abc import Mapping, Sequence
from typing import TypeVar

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


EXPECTED_CASE_IDS = (
    "invoice-it",
    "fiscal-receipt-it",
    "parking-receipt-it",
    "hotel-invoice-en",
    "hotel-receipt-en",
    "pos-payment-slip",
    "invoice-en",
)
EXPECTED_MODEL_HASHES = {
    "PP-OCRv6_det_small.onnx": "090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f",
    "PP-OCRv6_rec_small.onnx": "6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884",
    "ch_ppocr_mobile_v2.0_cls_mobile.onnx": "e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c",
}
_NON_ALNUM = re.compile(r"[^A-Z0-9]+")
_WORD = re.compile(r"[A-Z0-9]+")
_Item = TypeVar("_Item")


def normalize_text(value: str) -> str:
    return _NON_ALNUM.sub("", value.upper())


def edit_distance(left: Sequence[_Item], right: Sequence[_Item]) -> int:
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for row, left_char in enumerate(left, start=1):
        current = [row]
        for column, right_char in enumerate(right, start=1):
            current.append(min(
                current[-1] + 1,
                previous[column] + 1,
                previous[column - 1] + (left_char != right_char),
            ))
        previous = current
    return previous[-1]


def aggregate_metrics(
    gold_by_case: Mapping[str, str],
    observed_by_case: Mapping[str, str],
) -> dict[str, int | float]:
    """Return aggregate-only CER/WER counters, never the underlying strings."""
    if set(gold_by_case) != set(observed_by_case) or len(gold_by_case) != 7:
        raise ValueError("case identities must match exactly seven synthetic pages")
    character_errors = character_count = word_errors = word_count = recognized_cases = 0
    for case_id in sorted(gold_by_case):
        reference = normalize_text(gold_by_case[case_id])
        observed = normalize_text(observed_by_case[case_id])
        reference_words = _WORD.findall(gold_by_case[case_id].upper())
        observed_words = _WORD.findall(observed_by_case[case_id].upper())
        character_errors += edit_distance(reference, observed)
        character_count += len(reference)
        word_errors += edit_distance(reference_words, observed_words)
        word_count += len(reference_words)
        recognized_cases += bool(observed)
    return {
        "case_count": len(gold_by_case),
        "recognized_case_count": recognized_cases,
        "character_errors": character_errors,
        "character_count": character_count,
        "character_error_rate": round(character_errors / character_count, 6),
        "word_errors": word_errors,
        "word_count": word_count,
        "word_error_rate": round(word_errors / word_count, 6),
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_bundled_models(package_root: Path) -> dict[str, str]:
    """Require the two reviewed PP-OCRv6 small ONNX models in the wheel."""
    actual: dict[str, str] = {}
    for filename, expected_hash in EXPECTED_MODEL_HASHES.items():
        candidates = tuple(package_root.rglob(filename))
        if len(candidates) != 1 or not candidates[0].is_file():
            raise RuntimeError("reviewed bundled model file is missing or ambiguous")
        digest = _sha256_file(candidates[0])
        if digest != expected_hash:
            raise RuntimeError("reviewed bundled model hash did not match")
        actual[filename] = digest
    return actual


def _verify_engine_config(engine: object) -> None:
    config = getattr(engine, "cfg", None)
    if config is None:
        raise RuntimeError("RapidOCR did not expose the configured inference contract")
    for stage in ("Det", "Rec"):
        section = getattr(config, stage, None)
        if section is None or any((
            str(getattr(section, "engine_type", "")) != "onnxruntime",
            str(getattr(section, "lang_type", "")) != "it",
            str(getattr(section, "model_type", "")) != "small",
            str(getattr(section, "ocr_version", "")) != "PP-OCRv6",
        )):
            raise RuntimeError("RapidOCR model selection did not match the approved candidate")
    if bool(getattr(config.Global, "use_cls", True)):
        raise RuntimeError("unexpected text-line classifier configuration")


def _expected_text() -> dict[str, str]:
    from tools.generate_synthetic_ocr_pages import SYNTHETIC_PAGES

    return {case_id: "\n".join(lines) for case_id, lines in SYNTHETIC_PAGES}


def run_smoke() -> dict[str, object]:
    if os.name != "nt" or sys.version_info[:2] != (3, 13):
        raise RuntimeError("this smoke is restricted to Windows CPython 3.13")

    from PIL import ImageFont
    from rapidocr import RapidOCR
    import rapidocr
    import onnxruntime
    from tools.generate_synthetic_ocr_pages import generate_pages

    if not callable(getattr(ImageFont, "load_default", None)):
        raise RuntimeError("Pillow sized default-font API is unavailable")
    rapidocr_version = importlib.metadata.version("rapidocr")
    onnxruntime_version = importlib.metadata.version("onnxruntime")
    pillow_version = importlib.metadata.version("Pillow")
    if (rapidocr_version, onnxruntime_version, pillow_version) != ("3.10.0", "1.31.1", "12.1.0"):
        raise RuntimeError("installed OCR dependency versions did not match the reviewed lock")
    if "CPUExecutionProvider" not in onnxruntime.get_available_providers():
        raise RuntimeError("ONNX Runtime CPU provider is unavailable")
    package_root = Path(rapidocr.__file__).resolve().parent
    model_root = package_root / "models"
    model_hashes = verify_bundled_models(model_root)
    engine = RapidOCR(params={
        "Global.use_cls": False,
        "Global.log_level": "critical",
        "Global.model_root_dir": str(model_root),
        "Det.engine_type": "onnxruntime",
        "Det.lang_type": "it",
        "Det.model_type": "small",
        "Det.ocr_version": "PP-OCRv6",
        "Rec.engine_type": "onnxruntime",
        "Rec.lang_type": "it",
        "Rec.model_type": "small",
        "Rec.ocr_version": "PP-OCRv6",
    })
    _verify_engine_config(engine)

    runner_temp = os.environ.get("RUNNER_TEMP")
    if not runner_temp:
        raise RuntimeError("runner temporary directory is unavailable")
    output: dict[str, str] = {}
    total_bytes = 0
    start = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="ocr2-rapidocr-synthetic-", dir=runner_temp) as work_dir:
        pages = generate_pages(Path(work_dir) / "pages")
        if tuple(path.stem for path in pages) != EXPECTED_CASE_IDS:
            raise RuntimeError("synthetic fixture set did not match the approved seven pages")
        input_digest = hashlib.sha256()
        for page_path in pages:
            page_bytes = page_path.stat().st_size
            if page_bytes <= 0 or page_bytes > 8 * 1024 * 1024:
                raise RuntimeError("synthetic page exceeded the local smoke byte bounds")
            total_bytes += page_bytes
            input_digest.update(page_path.stem.encode("ascii"))
            input_digest.update(bytes.fromhex(_sha256_file(page_path)))
            result = engine(str(page_path))
            if not hasattr(result, "txts"):
                raise RuntimeError("RapidOCR did not return the expected result contract")
            texts = getattr(result, "txts", None)
            if texts is None:
                output[page_path.stem] = ""
            elif isinstance(texts, Sequence) and not isinstance(texts, (str, bytes)) and all(
                isinstance(text, str) for text in texts
            ):
                output[page_path.stem] = "\n".join(texts)
            else:
                raise RuntimeError("RapidOCR returned an unsupported result contract")
    elapsed = round(time.perf_counter() - start, 3)
    metrics = aggregate_metrics(_expected_text(), output)
    return {
        "scope": "seven-authored-synthetic-pages-only",
        "candidate": "PP-OCRv6-small-onnxruntime-cpu",
        "classifier": "bundled-and-hash-verified-but-disabled",
        "case_count": metrics["case_count"],
        "recognized_case_count": metrics["recognized_case_count"],
        "character_errors": metrics["character_errors"],
        "character_count": metrics["character_count"],
        "character_error_rate": metrics["character_error_rate"],
        "word_errors": metrics["word_errors"],
        "word_count": metrics["word_count"],
        "word_error_rate": metrics["word_error_rate"],
        "input_bytes": total_bytes,
        "synthetic_inputs_sha256": input_digest.hexdigest(),
        "model_sha256": model_hashes,
        "python_version": platform.python_version(),
        "rapidocr_version": rapidocr_version,
        "onnxruntime_version": onnxruntime.__version__,
        "pillow_version": pillow_version,
        "elapsed_seconds": elapsed,
        "limit": "aggregate synthetic feasibility evidence only; no OCR text, images, or per-case values are emitted",
    }


def main() -> int:
    captured_output = io.StringIO()
    try:
        with contextlib.redirect_stdout(captured_output), contextlib.redirect_stderr(captured_output):
            report = run_smoke()
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__}, sort_keys=True))
        return 1
    print(json.dumps({"status": "completed", **report}, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
