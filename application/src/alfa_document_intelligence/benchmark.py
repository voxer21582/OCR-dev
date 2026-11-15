from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

# Canonical field names used in scoring. Labels may contain additional fields;
# these are included in per-field metrics as well.
STANDARD_FIELDS = (
    "issue_date", "total_amount", "merchant_name", "currency",
    "issuer_role", "payer_role", "supplier_role", "customer_role",
    "payment_recipient_role", "tax_identifier_role", "subtotal",
    "taxable_base", "vat_rate", "vat_amount", "payment_amount",
)
GROUPS = {
    "dates": ("issue_date",),
    "amounts": ("total_amount", "subtotal", "taxable_base", "vat_amount", "payment_amount"),
    "merchant": ("merchant_name",),
    "currency": ("currency",),
    "fiscal_and_payment_roles": ("issuer_role", "payer_role", "supplier_role", "customer_role", "payment_recipient_role", "tax_identifier_role"),
    "vat": ("taxable_base", "vat_rate", "vat_amount"),
}
STATUSES = {"observed", "uncertain", "unreadable", "absent", "not_applicable", "rejected"}
REVIEW_STATUSES = {"uncertain", "unreadable", "rejected"}
SPLITS = {"development", "regression", "independent_frozen"}


def load_rows(path: Path) -> list[dict[str, Any]]:
    """Read JSONL without echoing document data or malformed source lines."""
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path.name}:{line_no}: invalid JSON") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path.name}:{line_no}: expected object")
        rows.append(row)
    return rows


def _percentile_nearest_rank(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(fraction * len(ordered)) - 1)
    return ordered[index]



def _wilson_interval(successes: int, trials: int, z: float = 1.959963984540054) -> list[float] | None:
    """Return a two-sided 95% Wilson score interval for a binomial rate."""
    if trials <= 0:
        return None
    proportion = successes / trials
    z_squared = z * z
    denominator = 1 + z_squared / trials
    center = (proportion + z_squared / (2 * trials)) / denominator
    margin = z * math.sqrt(proportion * (1 - proportion) / trials + z_squared / (4 * trials * trials)) / denominator
    return [max(0.0, center - margin), min(1.0, center + margin)]
def _valid_duration(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def _evidence_entries(value: Any, name: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{name}: evidence must be a list of objects")
    for item in value:
        page = item.get("page_number")
        if not isinstance(page, int) or isinstance(page, bool) or page < 1:
            raise ValueError(f"{name}: evidence page_number must be a positive integer")
        region = item.get("region")
        if region is not None:
            polygon = region.get("polygon") if isinstance(region, dict) else None
            if not isinstance(polygon, list) or len(polygon) < 3:
                raise ValueError(f"{name}: region polygon must contain at least three points")
            for point in polygon:
                if not isinstance(point, list) or len(point) != 2 or any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) or not 0 <= v <= 1 for v in point):
                    raise ValueError(f"{name}: region coordinates must be finite normalized pairs")
    return value


def _region_iou(left: dict[str, Any], right: dict[str, Any]) -> float | None:
    left_region, right_region = left.get("region"), right.get("region")
    if left_region is None or right_region is None:
        return None
    def bounds(region: dict[str, Any]) -> tuple[float, float, float, float]:
        points = region["polygon"]
        xs, ys = [point[0] for point in points], [point[1] for point in points]
        return min(xs), min(ys), max(xs), max(ys)
    ax1, ay1, ax2, ay2 = bounds(left_region)
    bx1, by1, bx2, by2 = bounds(right_region)
    intersection = max(0.0, min(ax2, bx2) - max(ax1, bx1)) * max(0.0, min(ay2, by2) - max(ay1, by1))
    area_a, area_b = (ax2 - ax1) * (ay2 - ay1), (bx2 - bx1) * (by2 - by1)
    union = area_a + area_b - intersection
    return intersection / union if union else 0.0


def _evidence_matches(gold: dict[str, Any], candidate: dict[str, Any], threshold: float) -> bool:
    if gold["page_number"] != candidate["page_number"]:
        return False
    overlap = _region_iou(gold, candidate)
    return overlap is None or overlap >= threshold


def evaluate(labels: list[dict[str, Any]], predictions: list[dict[str, Any]], split: str, run_metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Calculate field quality, review, reliability, latency, and run-resource metrics.

    Evidence precision and recall cover field/case pairs with nonempty labeled
    evidence only; predicted references for other pairs are counted separately,
    not assumed incorrect. Matching is greedy, one-to-one, on the same page;
    when both regions exist it uses bounding-box IoU >= 0.5, otherwise page
    equality suffices. Alternative evidence is not included. A label-evidence
    key absent from the global union of standard and input field names is not
    scored. These metrics do not establish source-hash or value accuracy.
    """
    if split not in SPLITS:
        raise ValueError("unsupported benchmark split")

    def index(rows: list[dict[str, Any]], name: str) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            case_id = row.get("case_id")
            if not isinstance(case_id, str) or not case_id:
                raise ValueError(f"{name}: case_id required")
            if case_id in result:
                raise ValueError(f"{name}: duplicate case_id")
            if row.get("split") != split:
                raise ValueError(f"{name}: split mismatch")
            fields = row.get("fields")
            if not isinstance(fields, dict):
                raise ValueError(f"{name}: fields must be an object")
            result[case_id] = row
        return result

    truth, output = index(labels, "labels"), index(predictions, "predictions")
    if truth.keys() != output.keys():
        raise ValueError("label/prediction case_id sets differ")

    all_field_names = set(STANDARD_FIELDS)
    for rows in (truth.values(), output.values()):
        for row in rows:
            if any(not isinstance(name, str) or not name for name in row["fields"]):
                raise ValueError("fields: names must be non-empty strings")
            all_field_names.update(row["fields"])
    field_names = sorted(all_field_names)
    field_counts: dict[str, list[int]] = {field: [0, 0] for field in field_names}
    candidate_recall_field_counts: dict[str, list[int]] = {field: [0, 0] for field in field_names}
    candidate_recall_family_counts: dict[str, dict[str, list[int]]] = defaultdict(lambda: {field: [0, 0] for field in field_names})
    alternative_precision_field_counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    alternative_precision_family_counts: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    unsupported_value_field_counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    unsupported_value_family_counts: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    false_confirmed_field_counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    false_confirmed_family_counts: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    group_counts = {name: [0, 0] for name in GROUPS}
    family_counts: dict[str, dict[str, list[int]]] = defaultdict(lambda: {field: [0, 0] for field in field_names})
    observed = false_confirmed = reviewed_fields = reviewed_cases = predicted_field_decisions = 0
    failed_cases = 0
    gold_evidence_count = predicted_evidence_count = matched_evidence_count = 0
    unassessable_predicted_evidence_count = 0
    confirmed_fields = confirmed_fields_with_evidence = 0
    runtimes: list[float] = []
    review_times: list[float] = []

    for case_id, label in truth.items():
        pred = output[case_id]
        gold_fields, pred_fields = label["fields"], pred["fields"]
        family = label.get("document_family", "unknown")
        if not isinstance(family, str) or not family:
            family = "unknown"
        processing_status = pred.get("processing_status", "success")
        if processing_status not in {"success", "failed"}:
            raise ValueError("predictions: processing_status must be success or failed")
        failed_cases += int(processing_status == "failed")
        needs_review = pred.get("review_required", False)
        if not isinstance(needs_review, bool):
            raise ValueError("predictions: review_required must be boolean")

        for field in field_names:
            gold_present = field in gold_fields
            prediction_present = field in pred_fields
            expected = gold_fields.get(field)
            candidate = pred_fields.get(field, {"status": "absent", "value": None})
            if not isinstance(candidate, dict):
                raise ValueError("predictions: field candidate must be an object")
            if prediction_present:
                predicted_field_decisions += 1
            status = candidate.get("status", "absent")
            if status not in STATUSES:
                raise ValueError("predictions: unsupported field status")
            value = candidate.get("value")
            if status == "observed" and value is None:
                raise ValueError("predictions: observed candidate requires a value")
            if status in {"absent", "not_applicable", "unreadable"} and value is not None:
                raise ValueError("predictions: null required for absent, not_applicable, or unreadable status")
            alternatives = candidate.get("alternatives", [])
            if not isinstance(alternatives, list):
                raise ValueError("predictions: alternatives must be a list")
            alternative_values = []
            recall_values = [value] if status in {"observed", "uncertain"} and value is not None else []
            emitted_values = list(recall_values)
            for alternative in alternatives:
                if not isinstance(alternative, dict):
                    raise ValueError("predictions: each alternative must be an object")
                alternative_status = alternative.get("status")
                if alternative_status not in {"observed", "uncertain", "unreadable", "rejected"}:
                    raise ValueError("predictions: unsupported alternative status")
                alternative_value = alternative.get("value")
                if alternative_status == "observed" and alternative_value is None:
                    raise ValueError("predictions: observed alternative requires a value")
                if alternative_status == "unreadable" and alternative_value is not None:
                    raise ValueError("predictions: unreadable alternative requires a null value")
                if alternative_value is not None:
                    alternative_values.append(alternative_value)
                    if alternative_status in {"observed", "uncertain"}:
                        recall_values.append(alternative_value)
                        emitted_values.append(alternative_value)
            for emitted_value in emitted_values:
                unsupported = int(not gold_present or expected is None or emitted_value != expected)
                unsupported_value_field_counts[field][0] += unsupported
                unsupported_value_field_counts[field][1] += 1
                unsupported_value_family_counts[family][field][0] += unsupported
                unsupported_value_family_counts[family][field][1] += 1
            if alternative_values:
                matching_alternatives = (
                    sum(candidate_value == expected for candidate_value in alternative_values)
                    if gold_present and expected is not None else 0
                )
                alternative_precision_field_counts[field][0] += matching_alternatives
                alternative_precision_field_counts[field][1] += len(alternative_values)
                alternative_precision_family_counts[family][field][0] += matching_alternatives
                alternative_precision_family_counts[family][field][1] += len(alternative_values)
            if gold_present and expected is not None:
                candidate_hit = int(expected in recall_values)
                candidate_recall_field_counts[field][0] += candidate_hit
                candidate_recall_field_counts[field][1] += 1
                candidate_recall_family_counts[family][field][0] += candidate_hit
                candidate_recall_family_counts[family][field][1] += 1

            if processing_status == "failed" and status == "observed":
                raise ValueError("predictions: failed cases cannot contain observed values")
            if status == "observed":
                observed += 1
                confirmed_fields += 1
                refs = _evidence_entries(candidate.get("evidence", []), "predictions")
                confirmed_fields_with_evidence += int(bool(refs))
                incorrect_confirmation = int(not gold_present or expected is None or value != expected)
                false_confirmed += incorrect_confirmation
                false_confirmed_field_counts[field][0] += incorrect_confirmation
                false_confirmed_field_counts[field][1] += 1
                false_confirmed_family_counts[family][field][0] += incorrect_confirmation
                false_confirmed_family_counts[family][field][1] += 1
            if status in REVIEW_STATUSES:
                needs_review = True
                reviewed_fields += 1

            if gold_present and expected is not None:
                correct = value == expected and status == "observed"
                field_counts[field][1] += 1
                field_counts[field][0] += int(correct)
                family_counts[family][field][1] += 1
                family_counts[family][field][0] += int(correct)
                for group, members in GROUPS.items():
                    if field in members:
                        group_counts[group][1] += 1
                        group_counts[group][0] += int(correct)

        if needs_review:
            reviewed_cases += 1

        gold_evidence = label.get("evidence", {})
        if not isinstance(gold_evidence, dict):
            raise ValueError("labels: evidence must map field names to evidence lists")
        # Validate even keys omitted from scoring so malformed annotations are
        # not silently accepted; historical matching scope stays unchanged.
        for refs in gold_evidence.values():
            _evidence_entries(refs, "labels")
        for field in field_names:
            gold_refs = _evidence_entries(gold_evidence.get(field, []), "labels")
            candidate = pred_fields.get(field, {})
            predicted_refs = _evidence_entries(candidate.get("evidence", []), "predictions") if isinstance(candidate, dict) else []
            if not gold_refs:
                unassessable_predicted_evidence_count += len(predicted_refs)
                continue
            gold_evidence_count += len(gold_refs)
            predicted_evidence_count += len(predicted_refs)
            unmatched = list(predicted_refs)
            for gold_ref in gold_refs:
                match_index = next((i for i, item in enumerate(unmatched) if _evidence_matches(gold_ref, item, 0.5)), None)
                if match_index is not None:
                    matched_evidence_count += 1
                    unmatched.pop(match_index)

        runtime = pred.get("processing_ms")
        if _valid_duration(runtime):
            runtimes.append(float(runtime))
        elif runtime is not None:
            raise ValueError("predictions: processing_ms must be a finite non-negative number")
        review_time = pred.get("review_seconds")
        if review_time is not None:
            if not _valid_duration(review_time):
                raise ValueError("predictions: review_seconds must be a finite non-negative number")
            if not needs_review:
                raise ValueError("predictions: review_seconds supplied for a document not requiring review")
            review_times.append(float(review_time))

    metadata = run_metadata or {}
    if not isinstance(metadata, dict):
        raise ValueError("run_metadata must be an object")
    for key in ("wall_clock_ms", "cpu_seconds", "peak_memory_mb"):
        value = metadata.get(key)
        if value is not None and not _valid_duration(value):
            raise ValueError(f"run_metadata: {key} must be a finite non-negative number")

    def metric(pair: list[int]) -> dict[str, Any]:
        return {"correct": pair[0], "labeled": pair[1], "accuracy": pair[0] / pair[1] if pair[1] else None, "confidence_interval_95_wilson": _wilson_interval(pair[0], pair[1])}

    def candidate_metric(pair: list[int]) -> dict[str, Any]:
        return {
            "matched": pair[0],
            "labeled_values": pair[1],
            "recall": pair[0] / pair[1] if pair[1] else None,
            "confidence_interval_95_wilson": _wilson_interval(pair[0], pair[1]),
        }

    def alternative_metric(pair: list[int]) -> dict[str, Any]:
        return {
            "matching_alternatives": pair[0],
            "emitted_alternatives": pair[1],
            "precision": pair[0] / pair[1] if pair[1] else None,
            "confidence_interval_95_wilson": _wilson_interval(pair[0], pair[1]),
        }

    def unsupported_metric(pair: list[int]) -> dict[str, Any]:
        return {
            "unsupported_values": pair[0],
            "emitted_values": pair[1],
            "rate": pair[0] / pair[1] if pair[1] else None,
            "confidence_interval_95_wilson": _wilson_interval(pair[0], pair[1]),
        }

    return {
        "split": split,
        "cases": len(truth),
        "field_accuracy": {field: metric(count) for field, count in field_counts.items()},
        "candidate_recall": candidate_metric([
            sum(pair[0] for pair in candidate_recall_field_counts.values()),
            sum(pair[1] for pair in candidate_recall_field_counts.values()),
        ]),
        "candidate_recall_by_field": {
            field: candidate_metric(count)
            for field, count in candidate_recall_field_counts.items() if count[1]
        },
        "candidate_recall_by_family": {
            family: {
                field: candidate_metric(count)
                for field, count in fields.items() if count[1]
            }
            for family, fields in sorted(candidate_recall_family_counts.items())
        },
        "alternative_precision": alternative_metric([
            sum(pair[0] for pair in alternative_precision_field_counts.values()),
            sum(pair[1] for pair in alternative_precision_field_counts.values()),
        ]),
        "alternative_precision_by_field": {
            field: alternative_metric(count)
            for field, count in sorted(alternative_precision_field_counts.items())
        },
        "alternative_precision_by_family": {
            family: {
                field: alternative_metric(count)
                for field, count in sorted(fields.items())
            }
            for family, fields in sorted(alternative_precision_family_counts.items())
        },
        "unsupported_value": unsupported_metric([
            sum(pair[0] for pair in unsupported_value_field_counts.values()),
            sum(pair[1] for pair in unsupported_value_field_counts.values()),
        ]),
        "unsupported_value_by_field": {
            field: unsupported_metric(count)
            for field, count in sorted(unsupported_value_field_counts.items())
        },
        "unsupported_value_by_family": {
            family: {
                field: unsupported_metric(count)
                for field, count in sorted(fields.items())
            }
            for family, fields in sorted(unsupported_value_family_counts.items())
        },
        "group_accuracy": {group: metric(count) for group, count in group_counts.items()},
        "field_accuracy_by_family": {
            family: {field: metric(count) for field, count in counts.items() if count[1]}
            for family, counts in sorted(family_counts.items())
        },
        "false_confirmed": {
            "count": false_confirmed,
            "observed_predictions": observed,
            "rate": false_confirmed / observed if observed else None,
            "confidence_interval_95_wilson": _wilson_interval(false_confirmed, observed),
        },
        "false_confirmed_by_field": {
            field: {
                "false_confirmed": count[0],
                "observed_predictions": count[1],
                "rate": count[0] / count[1] if count[1] else None,
                "confidence_interval_95_wilson": _wilson_interval(count[0], count[1]),
            }
            for field, count in sorted(false_confirmed_field_counts.items())
        },
        "false_confirmed_by_family": {
            family: {
                field: {
                    "false_confirmed": count[0],
                    "observed_predictions": count[1],
                    "rate": count[0] / count[1] if count[1] else None,
                    "confidence_interval_95_wilson": _wilson_interval(count[0], count[1]),
                }
                for field, count in sorted(fields.items())
            }
            for family, fields in sorted(false_confirmed_family_counts.items())
        },
        "review": {
            "documents_requiring_review": reviewed_cases,
            "documents": len(truth),
            "document_rate": reviewed_cases / len(truth) if truth else None,
            "document_rate_confidence_interval_95_wilson": _wilson_interval(reviewed_cases, len(truth)),
            "fields_requiring_review": reviewed_fields,
            "field_slots": predicted_field_decisions,
            "field_rate": reviewed_fields / predicted_field_decisions if predicted_field_decisions else None,
            "field_rate_confidence_interval_95_wilson": _wilson_interval(reviewed_fields, predicted_field_decisions),
        },
        "evidence_coverage": {
            "confirmed_fields": confirmed_fields,
            "confirmed_fields_with_evidence": confirmed_fields_with_evidence,
            "confirmed_fields_without_evidence": confirmed_fields - confirmed_fields_with_evidence,
            "rate": confirmed_fields_with_evidence / confirmed_fields if confirmed_fields else None,
            "confidence_interval_95_wilson": _wilson_interval(confirmed_fields_with_evidence, confirmed_fields),
        },
        "evidence_localization": {
            "matched_references": matched_evidence_count,
            "labeled_references": gold_evidence_count,
            "predicted_references": predicted_evidence_count,
            "unassessable_predicted_references": unassessable_predicted_evidence_count,
            "precision_scope": "field_cases_with_labeled_evidence",
            "recall": matched_evidence_count / gold_evidence_count if gold_evidence_count else None,
            "precision": matched_evidence_count / predicted_evidence_count if predicted_evidence_count else None,
            "region_iou_threshold": 0.5,
        },
        "reliability": {
            "failed_documents": failed_cases,
            "documents": len(truth),
            "failure_rate": failed_cases / len(truth) if truth else None,
            "failure_rate_confidence_interval_95_wilson": _wilson_interval(failed_cases, len(truth)),
        },
        "throughput_documents_per_second": (
            len(truth) * 1000 / metadata["wall_clock_ms"]
            if metadata.get("wall_clock_ms", 0) > 0 else None
        ),
        "resources": {
            "wall_clock_ms": metadata.get("wall_clock_ms"),
            "cpu_seconds": metadata.get("cpu_seconds"),
            "peak_memory_mb": metadata.get("peak_memory_mb"),
        },
        "processing_ms": {
            "samples": len(runtimes),
            "median": statistics.median(runtimes) if runtimes else None,
            "p95": _percentile_nearest_rank(runtimes, .95),
        },
        "review_seconds": {
            "samples": len(review_times),
            "median": statistics.median(review_times) if review_times else None,
            "p95": _percentile_nearest_rank(review_times, .95),
        },
    }


def attach_review_times(predictions: list[dict[str, Any]], path: Path) -> list[dict[str, Any]]:
    """Join a private local CSV of completed review durations to prediction rows."""
    durations: dict[str, float] = {}
    try:
        with path.open("r", encoding="utf-8", newline="") as source:
            reader = csv.DictReader(source, strict=True)
            if reader.fieldnames != ["case_id", "review_seconds"]:
                raise ValueError("review timing CSV must have case_id,review_seconds headers")
            for row in reader:
                if None in row or set(row) != {"case_id", "review_seconds"}:
                    raise ValueError("review timing CSV row has unexpected columns")
                case_id, raw_duration = row.get("case_id"), row.get("review_seconds")
                if not isinstance(case_id, str) or not case_id.strip():
                    raise ValueError("review timing CSV has an empty case_id")
                if case_id in durations:
                    raise ValueError("review timing CSV has duplicate case IDs")
                try:
                    duration = float(raw_duration)
                except (TypeError, ValueError) as exc:
                    raise ValueError("review timing CSV has an invalid duration") from exc
                if not _valid_duration(duration):
                    raise ValueError("review timing CSV has an invalid duration")
                durations[case_id] = duration
    except (csv.Error, UnicodeError) as exc:
        raise ValueError("review timing CSV is malformed") from exc

    indexed: dict[str, dict[str, Any]] = {}
    for prediction in predictions:
        case_id = prediction.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("predictions: case_id required")
        if case_id in indexed:
            raise ValueError("predictions: duplicate case_id")
        indexed[case_id] = prediction
    if any(case_id not in indexed for case_id in durations):
        raise ValueError("review timing CSV contains IDs absent from predictions")

    result = []
    for prediction in predictions:
        case_id = prediction["case_id"]
        if case_id not in durations:
            result.append(prediction)
            continue
        if "review_seconds" in prediction:
            raise ValueError("prediction already contains review_seconds")
        result.append({**prediction, "review_seconds": durations[case_id]})
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate synthetic or approved offline benchmark JSONL files")
    parser.add_argument("--labels", required=True, type=Path)
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--split", required=True, choices=tuple(sorted(SPLITS)))
    parser.add_argument("--run-metadata", type=Path, help="Optional JSON object with wall_clock_ms, cpu_seconds, and peak_memory_mb")
    parser.add_argument("--review-times-csv", type=Path, help="Optional local CSV exported by the browser app with case_id and review_seconds")
    args = parser.parse_args()
    try:
        metadata = json.loads(args.run_metadata.read_text(encoding="utf-8")) if args.run_metadata else None
        predictions = load_rows(args.predictions)
        if args.review_times_csv:
            predictions = attach_review_times(predictions, args.review_times_csv)
        result = evaluate(load_rows(args.labels), predictions, args.split, metadata)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
