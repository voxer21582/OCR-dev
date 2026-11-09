"""Bounded local catalog for user-defined document families.

Definitions are data only: title cues and field aliases are literal strings,
never regular expressions or executable rules. Custom field proposals remain
uncertain text and carry the OCR token as source evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import itertools
import json
import math
import os
import re
from typing import Any, Iterable
from pathlib import Path
import tempfile
from types import MappingProxyType
from typing import Mapping

from .ocr_adapter import (
    MAX_OCR_PAGES_PER_DOCUMENT,
    MAX_OCR_POLYGON_VERTICES,
    MAX_OCR_TOKEN_ID_CHARS,
    MAX_OCR_TOKEN_TEXT_CHARS,
    MAX_OCR_TOKENS_PER_DOCUMENT,
    MAX_OCR_TOKENS_PER_PAGE,
    OCRPageResult,
    OCRToken,
)

MAX_CATALOG_BYTES = 64 * 1024
MAX_FAMILIES = 25
MAX_TITLE_CUES = 12
MAX_FIELDS_PER_FAMILY = 20
MAX_ALIASES_PER_FIELD = 12
MAX_PROPOSALS = 100
MAX_OCR_POLYGON_EDGE_CHECKS_PER_DOCUMENT = 1_000_000
MAX_OCR_ENGINE_METADATA_CHARS = 128
_NUMERIC_DATE = re.compile(r"^(\d{1,2})([/. -])(\d{1,2})\2(\d{4})$")
_ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_AMOUNT_VALUE = re.compile(r"^[+-]?(?:(?:\d{1,3}(?:[., ]\d{3})+)|\d+)[.,]\d{2}$")
_DATE_IN_TEXT = re.compile(
    r"(?<!\d)(?:\d{4}-\d{2}-\d{2}|\d{1,2}([/. -])\d{1,2}\1\d{4})(?!\d)"
)
_AMOUNT_IN_TEXT = re.compile(
    r"(?<![\w])[-+]?(?:(?:\d{1,3}(?:[., ]\d{3})+)|\d+)[.,]\d{2}(?!\w)"
)
_FAMILY_ID = re.compile(r"^custom_[a-z][a-z0-9_]{1,24}$")
_FIELD_ID = re.compile(r"^[a-z][a-z0-9_]{1,20}$")
_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
_BUILTIN_FAMILY_IDS = {
    "invoice", "expense_report", "fiscal_receipt", "parking_receipt",
    "hotel_document", "pos_slip", "other", "unknown",
}


class DocumentFamilyCatalogError(ValueError):
    """Catalog input is malformed, ambiguous, or outside its fixed limits."""

class CatalogProposalLimitError(DocumentFamilyCatalogError):
    """Custom proposal review limit was exceeded."""



def _pairs_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DocumentFamilyCatalogError("catalog contains a duplicate JSON property")
        result[key] = value
    return result


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _json_value_within_catalog_limit(value: Any) -> bool:
    """Count actual JSON bytes with bounded traversal and scalar allocations."""
    remaining = MAX_CATALOG_BYTES

    def fits(item: Any, depth: int) -> bool:
        nonlocal remaining
        if depth > 64 or remaining <= 0:
            return False
        if type(item) is list:
            remaining -= 2 + max(0, len(item) - 1)
            return remaining >= 0 and all(fits(child, depth + 1) for child in item)
        if type(item) is dict:
            remaining -= 2 + max(0, len(item) - 1) + len(item)
            return remaining >= 0 and all(
                type(key) is str and fits(key, depth + 1) and fits(child, depth + 1)
                for key, child in item.items()
            )
        if type(item) is str:
            # JSON cannot occupy fewer bytes than its characters and quotes.
            # Check first so even a hostile string is never copied unboundedly.
            if len(item) + 2 > remaining:
                return False
        elif type(item) is int:
            if item.bit_length() > remaining * 4:
                return False
        elif item is not None and type(item) not in (bool, float):
            return False
        try:
            encoded = json.dumps(item, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (ValueError, UnicodeEncodeError):
            return False
        remaining -= len(encoded)
        return remaining >= 0

    return fits(value, 0)


def _require_utf8_text(value: str, *, field: str) -> None:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise DocumentFamilyCatalogError(f"{field} contains invalid Unicode") from exc


def _normalized_literal(value: Any, *, field: str, max_length: int = 80) -> str:
    if not isinstance(value, str):
        raise DocumentFamilyCatalogError(f"{field} must be text")
    normalized = " ".join(value.split())
    _require_utf8_text(normalized, field=field)
    if not normalized or len(normalized) > max_length or any(ord(char) < 32 for char in normalized):
        raise DocumentFamilyCatalogError(f"{field} is empty or outside its length limit")
    return normalized


@dataclass(frozen=True)
class CustomFamily:
    id: str
    label: str
    title_cues: tuple[str, ...]
    fields: tuple[Mapping[str, Any], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "title_cues": list(self.title_cues),
            "fields": [
                {
                    "id": field["id"], "label": field["label"],
                    "aliases": list(field["aliases"]),
                    **({"type": field["type"]} if field["type"] != "text" else {}),
                    **({"required": True} if field["required"] else {}),
                }
                for field in self.fields
            ],
        }


@dataclass(frozen=True)
class DocumentFamilyCatalog:
    version: str
    sha256: str
    families: tuple[CustomFamily, ...]

    def snapshot_for(self, family_id: str) -> dict[str, Any]:
        family = next((item for item in self.families if item.id == family_id), None)
        if family is None:
            raise DocumentFamilyCatalogError("family is not present in this catalog")
        return {
            "catalog_version": self.version,
            "family": family.as_dict(),
            "family_sha256": hashlib.sha256(_canonical_json(family.as_dict())).hexdigest(),
        }

    def as_json(self) -> str:
        payload = {
            "catalog_version": self.version,
            "families": [family.as_dict() for family in self.families],
        }
        formatted = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        if len(formatted.encode("utf-8")) <= MAX_CATALOG_BYTES:
            return formatted
        return _canonical_json(payload).decode("utf-8")


class DocumentFamilyCatalogStore:
    """Atomic local JSON persistence for a user-managed family catalog."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> DocumentFamilyCatalog:
        if self.path.is_symlink():
            raise DocumentFamilyCatalogError("catalog path must not be a symbolic link")
        try:
            with self.path.open("rb") as stream:
                raw = stream.read(MAX_CATALOG_BYTES + 1)
        except FileNotFoundError:
            return load_custom_family_catalog('{"catalog_version":"1","families":[]}')
        except OSError as exc:
            raise DocumentFamilyCatalogError("catalog could not be read") from exc
        return load_custom_family_catalog(raw)

    def save(self, raw: str | bytes) -> DocumentFamilyCatalog:
        catalog = load_custom_family_catalog(raw)
        parent = self.path.parent
        try:
            parent.mkdir(parents=True, exist_ok=True)
            if self.path.is_symlink():
                raise DocumentFamilyCatalogError("catalog path must not be a symbolic link")
            handle = tempfile.NamedTemporaryFile(
                mode="wb", prefix=".ocr2-family-catalog-", suffix=".tmp",
                dir=parent, delete=False,
            )
            temporary = Path(handle.name)
            try:
                with handle:
                    handle.write(catalog.as_json().encode("utf-8"))
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, self.path)
            finally:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
        except DocumentFamilyCatalogError:
            raise
        except OSError as exc:
            raise DocumentFamilyCatalogError("catalog could not be atomically saved") from exc
        return catalog


def load_custom_family_catalog(raw: str | bytes) -> DocumentFamilyCatalog:
    """Parse a strict JSON catalog under fixed byte and item-count limits."""
    if isinstance(raw, str):
        try:
            encoded = raw.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise DocumentFamilyCatalogError("catalog must be valid UTF-8") from exc
    elif isinstance(raw, bytes):
        encoded = raw
    else:
        raise DocumentFamilyCatalogError("catalog must be UTF-8 text")
    if len(encoded) > MAX_CATALOG_BYTES:
        raise DocumentFamilyCatalogError("catalog exceeds the 64 KiB limit")
    try:
        value = json.loads(encoded.decode("utf-8"), object_pairs_hook=_pairs_without_duplicates)
    except DocumentFamilyCatalogError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise DocumentFamilyCatalogError("catalog is not valid bounded UTF-8 JSON") from exc
    if not isinstance(value, dict) or set(value) != {"catalog_version", "families"}:
        raise DocumentFamilyCatalogError("catalog must contain only catalog_version and families")
    catalog_version = value["catalog_version"]
    if catalog_version not in ("1", "2") or not isinstance(value["families"], list):
        raise DocumentFamilyCatalogError("catalog version or families array is unsupported")
    if len(value["families"]) > MAX_FAMILIES:
        raise DocumentFamilyCatalogError("catalog exceeds the 25-family limit")

    families: list[CustomFamily] = []
    family_ids: set[str] = set()
    catalog_field_names: set[str] = set()
    all_title_cues: set[str] = set()
    for index, item in enumerate(value["families"]):
        prefix = f"families[{index}]"
        if not isinstance(item, dict) or set(item) != {"id", "label", "title_cues", "fields"}:
            raise DocumentFamilyCatalogError(f"{prefix} has unsupported properties")
        family_id = item["id"]
        if not isinstance(family_id, str) or not _FAMILY_ID.fullmatch(family_id) or family_id in _BUILTIN_FAMILY_IDS:
            raise DocumentFamilyCatalogError(f"{prefix}.id is not a valid custom family identifier")
        if family_id in family_ids:
            raise DocumentFamilyCatalogError("catalog contains a duplicate family identifier")
        family_ids.add(family_id)
        label = _normalized_literal(item["label"], field=f"{prefix}.label")
        cues = item["title_cues"]
        fields = item["fields"]
        if not isinstance(cues, list) or not 1 <= len(cues) <= MAX_TITLE_CUES:
            raise DocumentFamilyCatalogError(f"{prefix}.title_cues must contain 1 to 12 cues")
        if not isinstance(fields, list) or len(fields) > MAX_FIELDS_PER_FAMILY:
            raise DocumentFamilyCatalogError(f"{prefix}.fields exceeds the 20-field limit")
        normalized_cues = tuple(_normalized_literal(cue, field=f"{prefix}.title_cues") for cue in cues)
        folded_cues = [cue.casefold() for cue in normalized_cues]
        if len(set(folded_cues)) != len(folded_cues) or any(cue in all_title_cues for cue in folded_cues):
            raise DocumentFamilyCatalogError("catalog contains ambiguous or duplicate title cues")
        all_title_cues.update(folded_cues)
        normalized_fields: list[dict[str, Any]] = []
        field_ids: set[str] = set()
        aliases_seen: set[str] = set()
        for field_index, field in enumerate(fields):
            field_prefix = f"{prefix}.fields[{field_index}]"
            base_field_keys = {"id", "label", "aliases"}
            if not isinstance(field, dict) or not base_field_keys.issubset(field):
                raise DocumentFamilyCatalogError(f"{field_prefix} has unsupported properties")
            if catalog_version == "1" and set(field) != base_field_keys:
                raise DocumentFamilyCatalogError(f"{field_prefix} has unsupported properties")
            optional_field_keys = {"type", "required"}
            if catalog_version == "2" and (
                not set(field).issubset(base_field_keys | optional_field_keys)
                or not base_field_keys.issubset(field)
            ):
                raise DocumentFamilyCatalogError(f"{field_prefix} has unsupported properties")
            field_type = field.get("type", "text")
            if not isinstance(field_type, str) or field_type not in {"text", "identifier", "date", "amount"}:
                raise DocumentFamilyCatalogError(f"{field_prefix}.type is unsupported")
            required = field.get("required", False)
            if type(required) is not bool:
                raise DocumentFamilyCatalogError(f"{field_prefix}.required must be a boolean")
            field_id = field["id"]
            if not isinstance(field_id, str) or not _FIELD_ID.fullmatch(field_id) or field_id in field_ids:
                raise DocumentFamilyCatalogError(f"{field_prefix}.id is invalid or duplicated")
            synthesized_name = f"{family_id}_{field_id}"
            if synthesized_name in catalog_field_names:
                raise DocumentFamilyCatalogError("catalog contains colliding synthesized field names")
            catalog_field_names.add(synthesized_name)
            field_ids.add(field_id)
            field_label = _normalized_literal(field["label"], field=f"{field_prefix}.label")
            aliases = field["aliases"]
            if not isinstance(aliases, list) or not 1 <= len(aliases) <= MAX_ALIASES_PER_FIELD:
                raise DocumentFamilyCatalogError(f"{field_prefix}.aliases must contain 1 to 12 aliases")
            normalized_aliases = tuple(
                _normalized_literal(alias, field=f"{field_prefix}.aliases") for alias in aliases
            )
            folded_aliases = [alias.casefold() for alias in normalized_aliases]
            if len(set(folded_aliases)) != len(folded_aliases) or aliases_seen.intersection(folded_aliases):
                raise DocumentFamilyCatalogError("field aliases must be unique within a family")
            aliases_seen.update(folded_aliases)
            normalized_fields.append({
                "id": field_id, "label": field_label, "aliases": normalized_aliases,
                "type": field_type, "required": required,
            })
        families.append(CustomFamily(
            family_id,
            label,
            normalized_cues,
            tuple(MappingProxyType(field) for field in normalized_fields),
        ))

    normalized_catalog = {
        "catalog_version": catalog_version,
        "families": [family.as_dict() for family in families],
    }
    digest = hashlib.sha256(_canonical_json(normalized_catalog)).hexdigest()
    return DocumentFamilyCatalog(catalog_version, digest, tuple(families))


def validate_family_snapshot(snapshot: Any) -> list[str]:
    """Validate an immutable single-family definition stored with a record."""
    if not isinstance(snapshot, dict) or set(snapshot) != {
        "catalog_version", "family", "family_sha256"
    }:
        return ["document_family_definitions: invalid snapshot shape"]
    catalog_version = snapshot.get("catalog_version")
    if catalog_version not in ("1", "2"):
        return ["document_family_definitions.catalog_version: unsupported version"]
    family = snapshot.get("family")
    payload = {"catalog_version": catalog_version, "families": [family]}
    if not _json_value_within_catalog_limit(payload):
        return ["document_family_definitions.family: exceeds the catalog size limit"]
    try:
        parsed = load_custom_family_catalog(_canonical_json(payload))
    except (DocumentFamilyCatalogError, TypeError, ValueError):
        return ["document_family_definitions.family: invalid custom family"]
    if len(parsed.families) != 1:
        return ["document_family_definitions.family: invalid custom family"]
    normalized_family = parsed.families[0].as_dict()
    if family != normalized_family:
        return ["document_family_definitions.family: definition is not canonical"]
    expected = hashlib.sha256(_canonical_json(normalized_family)).hexdigest()
    if snapshot.get("family_sha256") != expected:
        return ["document_family_definitions.family_sha256: does not match family definition"]
    return []


def catalog_from_snapshots(snapshots: Iterable[dict[str, Any]]) -> DocumentFamilyCatalog:
    """Reconstruct a proposal catalog only from validated record snapshots."""
    families: list[dict[str, Any]] = []
    versions: set[str] = set()
    for snapshot in itertools.islice(snapshots, MAX_FAMILIES + 1):
        if len(families) == MAX_FAMILIES:
            raise DocumentFamilyCatalogError("stored family snapshots exceed the 25-family limit")
        issues = validate_family_snapshot(snapshot)
        if issues:
            raise DocumentFamilyCatalogError("invalid stored family snapshot")
        versions.add(snapshot["catalog_version"])
        families.append(snapshot["family"])
    if not families:
        raise DocumentFamilyCatalogError("no custom-family snapshots are available")
    if len(versions) != 1:
        raise DocumentFamilyCatalogError("stored family snapshots use mixed catalog versions")
    raw = _canonical_json({"catalog_version": next(iter(versions)), "families": families})
    return load_custom_family_catalog(raw)


def _evidence(page: OCRPageResult, token: OCRToken) -> dict[str, Any]:
    return {
        "source_sha256": page.source_sha256,
        "page_number": page.page_number,
        "region": {
            "coordinate_space": "normalized_page",
            "polygon": [[float(x), float(y)] for x, y in token.polygon],
        },
        "token_ids": [token.token_id],
        "literal": token.text.strip(),
        "producer": {"stage": "ocr", "name": page.engine_name, "version": page.engine_version},
    }


def _uncertain_candidate(proposals: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    evidence = [item_evidence for _, item_evidence in proposals]
    return {
        "value": None,
        "status": "uncertain",
        "alternatives": [
            {"value": value, "status": "observed", "evidence": [item_evidence]}
            for value, item_evidence in proposals
        ],
        "evidence": evidence,
    }


def _field_value(parts: tuple[tuple[str, str, str], ...], aliases: frozenset[str]) -> str | None:
    for prefix, _, value in parts:
        if prefix in aliases:
            return value if value else None
    return None


def _delimited_field_value(parts: tuple[tuple[str, str, str], ...], aliases: frozenset[str]) -> str | None:
    """Match a single trailing delimiter without changing legacy matching."""
    for prefix, separator, value in parts:
        if (not prefix or ":" in prefix or "=" in prefix
                or not value or value[0] in ":="):
            continue
        if prefix + separator in aliases or prefix + " " + separator in aliases:
            return value
    return None


def _typed_values(field_type: str, literal: str) -> list[tuple[str, str, str]]:
    """Return (value, normalization rule, original literal) candidates."""
    if field_type == "text":
        return [(literal, "", literal)]
    if field_type == "identifier":
        return [(literal, "preserve-identifier-literal", literal)]
    if field_type == "date":
        iso = _ISO_DATE.fullmatch(literal)
        if iso is not None:
            try:
                normalized = date(*(int(part) for part in iso.groups())).isoformat()
            except ValueError:
                return []
            return [(normalized, "date-iso8601", literal)]
        numeric = _NUMERIC_DATE.fullmatch(literal)
        if numeric is None:
            return []
        first, _, second, year = numeric.groups()
        first, second, year = int(first), int(second), int(year)
        proposals: list[tuple[str, str, str]] = []
        seen: set[str] = set()
        for rule_id, components in (
            ("date-dmy", (year, second, first)),
            ("date-mdy", (year, first, second)),
        ):
            try:
                normalized = date(*components).isoformat()
            except ValueError:
                continue
            if normalized not in seen:
                proposals.append((normalized, rule_id, literal))
                seen.add(normalized)
        return proposals
    if field_type == "amount" and _AMOUNT_VALUE.fullmatch(literal):
        sign = "-" if literal.startswith("-") else ""
        unsigned = literal.lstrip("+-")
        integer = re.sub(r"[., ]", "", unsigned[:-3])
        return [(f"{sign}{integer}.{unsigned[-2:]}", "decimal-separator-last", literal)]
    return []


def parse_typed_values_from_text(field_type: str, literal: str) -> list[tuple[str, str, str]]:
    """Parse supported typed literals embedded in one bounded OCR token."""
    if not isinstance(literal, str):
        return []
    if field_type == "date":
        matches = _DATE_IN_TEXT.finditer(literal)
    elif field_type == "amount":
        matches = _AMOUNT_IN_TEXT.finditer(literal)
    else:
        return []
    parsed: list[tuple[str, str, str]] = []
    for match in matches:
        parsed.extend(_typed_values(field_type, match.group(0)))
    return parsed


def _custom_field_candidate(
    proposals: list[tuple[str | None, dict[str, Any], str, str, str]],
) -> dict[str, Any]:
    evidence = [item_evidence for _, item_evidence, _, _, _ in proposals]
    alternatives: list[dict[str, Any]] = []
    for value, item_evidence, rule_id, literal, status in proposals:
        alternative: dict[str, Any] = {
            "value": value,
            "status": status,
            "evidence": [item_evidence],
        }
        if rule_id:
            alternative["normalization"] = {
                "rule_id": rule_id,
                "rule_version": "1",
                "original_literal": literal,
                "normalized_value": value,
            }
        alternatives.append(alternative)
    if all(item[4] == "unreadable" for item in proposals):
        return {"value": None, "status": "unreadable", "evidence": evidence, "alternatives": []}
    return {"value": None, "status": "uncertain", "evidence": evidence, "alternatives": alternatives}


def _polygon_has_nonzero_area(polygon: tuple[tuple[float, float], ...]) -> bool:
    """Reject zero-area or self-intersecting regions, accepting a closing vertex."""
    points = polygon[:-1] if len(polygon) > 3 and polygon[0] == polygon[-1] else polygon
    if len(points) < 3:
        return False
    if not _polygon_is_simple(points):
        return False
    twice_area = math.fsum(
        x1 * y2 - x2 * y1
        for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1])
    )
    return math.isfinite(twice_area) and twice_area != 0


def _polygon_is_simple(points: tuple[tuple[float, float], ...]) -> bool:
    """Return false for duplicate vertices or intersections between non-adjacent edges."""
    if len(set(points)) != len(points):
        return False

    def orientation(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def on_segment(
        a: tuple[float, float], b: tuple[float, float], p: tuple[float, float]
    ) -> bool:
        return (min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
                and min(a[1], b[1]) <= p[1] <= max(a[1], b[1]))

    def intersects(
        a: tuple[float, float], b: tuple[float, float],
        c: tuple[float, float], d: tuple[float, float],
    ) -> bool:
        abc, abd = orientation(a, b, c), orientation(a, b, d)
        cda, cdb = orientation(c, d, a), orientation(c, d, b)
        if ((abc > 0 > abd or abd > 0 > abc)
                and (cda > 0 > cdb or cdb > 0 > cda)):
            return True
        return ((abc == 0 and on_segment(a, b, c))
                or (abd == 0 and on_segment(a, b, d))
                or (cda == 0 and on_segment(c, d, a))
                or (cdb == 0 and on_segment(c, d, b)))

    count = len(points)
    for first in range(count):
        a, b = points[first], points[(first + 1) % count]
        for second in range(first + 2, count):
            # Consecutive edges share an endpoint by definition; the first and last do too.
            if first == 0 and second == count - 1:
                continue
            c, d = points[second], points[(second + 1) % count]
            if intersects(a, b, c, d):
                return False
    return True


def build_custom_family_proposals(
    pages: Iterable[OCRPageResult], catalog: DocumentFamilyCatalog
) -> dict[str, dict[str, Any]]:
    """Build uncertain family and configured text candidates from OCR tokens."""
    try:
        materialized = tuple(itertools.islice(iter(pages), MAX_OCR_PAGES_PER_DOCUMENT + 1))
    except TypeError as exc:
        raise DocumentFamilyCatalogError("pages must be an iterable of OCRPageResult values") from exc
    if not materialized:
        raise DocumentFamilyCatalogError("at least one OCR page is required")
    if len(materialized) > MAX_OCR_PAGES_PER_DOCUMENT:
        raise DocumentFamilyCatalogError("OCR page limit exceeded")
    if not isinstance(catalog, DocumentFamilyCatalog):
        raise DocumentFamilyCatalogError("catalog must be a validated DocumentFamilyCatalog")

    source_sha256: str | None = None
    seen_pages: set[int] = set()
    total_tokens = 0
    total_polygon_edge_checks = 0
    for page in materialized:
        if not isinstance(page, OCRPageResult):
            raise DocumentFamilyCatalogError("pages must contain OCRPageResult values")
        if not isinstance(page.source_sha256, str) or not _SHA256.fullmatch(page.source_sha256):
            raise DocumentFamilyCatalogError("page source_sha256 must be 64 hexadecimal characters")
        if source_sha256 is None:
            source_sha256 = page.source_sha256
        elif page.source_sha256 != source_sha256:
            raise DocumentFamilyCatalogError("all OCR pages must bind to the same source document")
        if (not isinstance(page.page_number, int) or isinstance(page.page_number, bool)
                or page.page_number < 1):
            raise DocumentFamilyCatalogError("page_number must be a positive integer")
        if page.page_number in seen_pages:
            raise DocumentFamilyCatalogError("page_number must be unique")
        seen_pages.add(page.page_number)
        if (not isinstance(page.engine_name, str) or not page.engine_name.strip()
                or not isinstance(page.engine_version, str) or not page.engine_version.strip()):
            raise DocumentFamilyCatalogError("OCR engine name and version are required for provenance")
        _require_utf8_text(page.engine_name, field="OCR engine name")
        _require_utf8_text(page.engine_version, field="OCR engine version")
        if (len(page.engine_name) > MAX_OCR_ENGINE_METADATA_CHARS
                or len(page.engine_version) > MAX_OCR_ENGINE_METADATA_CHARS):
            raise DocumentFamilyCatalogError("OCR engine provenance exceeds the 128-character limit")
        if not isinstance(page.tokens, tuple):
            raise DocumentFamilyCatalogError("OCR page tokens must be a bounded tuple")
        if len(page.tokens) > MAX_OCR_TOKENS_PER_PAGE:
            raise DocumentFamilyCatalogError("OCR token limit exceeded for page")
        total_tokens += len(page.tokens)
        if total_tokens > MAX_OCR_TOKENS_PER_DOCUMENT:
            raise DocumentFamilyCatalogError("OCR document token limit exceeded")
        token_ids: set[str] = set()
        for token in page.tokens:
            if not isinstance(token, OCRToken):
                raise DocumentFamilyCatalogError("pages must contain OCRToken values")
            if not isinstance(token.token_id, str) or not token.token_id.strip():
                raise DocumentFamilyCatalogError("OCR token_id is required")
            _require_utf8_text(token.token_id, field="OCR token_id")
            if len(token.token_id) > MAX_OCR_TOKEN_ID_CHARS:
                raise DocumentFamilyCatalogError("OCR token_id exceeds the configured character limit")
            if token.token_id in token_ids:
                raise DocumentFamilyCatalogError("OCR token_id must be unique within a page")
            token_ids.add(token.token_id)
            if not isinstance(token.text, str) or not token.text.strip():
                raise DocumentFamilyCatalogError("OCR token text must be non-empty")
            _require_utf8_text(token.text, field="OCR token text")
            if len(token.text) > MAX_OCR_TOKEN_TEXT_CHARS:
                raise DocumentFamilyCatalogError("OCR token text exceeds the configured character limit")
            if token.confidence is not None and (
                type(token.confidence) not in (int, float)
                or not 0 <= token.confidence <= 1
                or not math.isfinite(token.confidence)
            ):
                raise DocumentFamilyCatalogError("OCR token confidence must be finite and in [0, 1]")
            if not isinstance(token.polygon, tuple) or len(token.polygon) < 3:
                raise DocumentFamilyCatalogError("OCR token polygon must contain at least three points")
            if len(token.polygon) > MAX_OCR_POLYGON_VERTICES:
                raise DocumentFamilyCatalogError("OCR token polygon vertex limit exceeded")
            for point in token.polygon:
                if not isinstance(point, tuple) or len(point) != 2:
                    raise DocumentFamilyCatalogError("OCR token polygon points must be x,y tuples")
                for coordinate in point:
                    if (type(coordinate) not in (int, float)
                            or not 0 <= coordinate <= 1 or not math.isfinite(coordinate)):
                        raise DocumentFamilyCatalogError(
                            "OCR token polygon coordinates must be finite and normalized"
                        )
            points = token.polygon[:-1] if (
                len(token.polygon) > 3 and token.polygon[0] == token.polygon[-1]
            ) else token.polygon
            point_count = len(points)
            total_polygon_edge_checks += point_count * (point_count - 3) // 2
            if total_polygon_edge_checks > MAX_OCR_POLYGON_EDGE_CHECKS_PER_DOCUMENT:
                raise DocumentFamilyCatalogError("OCR polygon complexity limit exceeded")
            if not _polygon_has_nonzero_area(token.polygon):
                raise DocumentFamilyCatalogError(
                    "OCR token polygon must be simple and have non-zero area"
                )
    family_proposals: list[tuple[str, dict[str, Any]]] = []
    field_proposals: dict[str, list[tuple[str | None, dict[str, Any], str, str, str]]] = {}
    proposal_count = 0
    title_lookup = {
        cue.casefold(): family
        for family in catalog.families
        for cue in family.title_cues
    }
    field_specs = tuple(
        (family, field, frozenset(alias.casefold() for alias in field["aliases"]))
        for family in catalog.families for field in family.fields
    )
    for page in materialized:
        for token in page.tokens:
            folded = " ".join(token.text.split()).casefold()
            family = title_lookup.get(folded)
            if family is not None:
                if proposal_count >= MAX_PROPOSALS:
                    raise CatalogProposalLimitError("custom proposals exceed the review-safe limit")
                family_proposals.append((family.id, _evidence(page, token)))
                proposal_count += 1
            text = token.text.strip()
            parts = []
            for separator in (":", "="):
                prefix, found, value = text.partition(separator)
                if found:
                    parts.append((" ".join(prefix.split()).casefold(), separator, value.strip()))
            parts = tuple(parts)
            if not parts:
                continue
            matches = []
            has_new = False
            ambiguous = False
            for family, field, aliases in field_specs:
                value = _field_value(parts, aliases)
                is_new = False
                if value is None:
                    value = _delimited_field_value(parts, aliases)
                    is_new = value is not None
                if value is not None:
                    matches.append((family, field, value))
                    has_new = has_new or is_new
                    if has_new and len(matches) > 1:
                        ambiguous = True
                        break
            # A newly recognized alias must not cause a token to be assigned
            # to different fields, including via a pre-existing legacy match.
            if ambiguous:
                continue
            for family, field, value in matches:
                name = f"{family.id}_{field['id']}"
                typed = _typed_values(field["type"], value)
                new_proposal_count = len(typed) if typed else 1
                if proposal_count + new_proposal_count > MAX_PROPOSALS:
                    raise CatalogProposalLimitError("custom proposals exceed the review-safe limit")
                item_evidence = _evidence(page, token)
                if typed:
                    field_proposals.setdefault(name, []).extend(
                        (normalized, item_evidence, rule_id, original, "observed")
                        for normalized, rule_id, original in typed
                    )
                else:
                    field_proposals.setdefault(name, []).append(
                        (None, item_evidence, "", value, "unreadable")
                    )
                proposal_count += new_proposal_count
    result: dict[str, dict[str, Any]] = {}
    if family_proposals:
        result["document_family_candidates"] = _uncertain_candidate(family_proposals)
    result.update({name: _custom_field_candidate(items) for name, items in field_proposals.items()})
    active_family_ids = {family_id for family_id, _ in family_proposals}
    missing_required: list[str] = []
    for family in catalog.families:
        if family.id not in active_family_ids:
            continue
        for field in family.fields:
            field_name = f"{family.id}_{field['id']}"
            if field["required"] and field_name not in field_proposals:
                missing_required.append(field_name)
    if proposal_count + len(missing_required) > MAX_PROPOSALS:
        raise CatalogProposalLimitError("custom-field proposals exceed the review-safe limit")
    result.update({
        name: {"value": None, "status": "absent", "evidence": [], "alternatives": []}
        for name in missing_required
    })
    return result
