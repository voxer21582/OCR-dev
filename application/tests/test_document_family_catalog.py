import hashlib
import itertools
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import alfa_document_intelligence.document_family_catalog as catalog_module
from alfa_document_intelligence.document_family_catalog import (
    MAX_FAMILIES,
    MAX_PROPOSALS,
    DocumentFamilyCatalogError,
    DocumentFamilyCatalogStore,
    build_custom_family_proposals,
    catalog_from_snapshots,
    load_custom_family_catalog,
    validate_family_snapshot,
)
from alfa_document_intelligence.ocr_adapter import OCRPageResult, OCRToken


SOURCE = "a" * 64
POLYGON = ((0.1, 0.2), (0.8, 0.2), (0.8, 0.4), (0.1, 0.4))


def catalog_payload():
    return {
        "catalog_version": "1",
        "families": [{
            "id": "custom_taxi_receipt",
            "label": "Ricevuta taxi",
            "title_cues": ["RICEVUTA TAXI"],
            "fields": [{
                "id": "pickup_city",
                "label": "Città di partenza",
                "aliases": ["Partenza"],
            }],
        }],
    }


def dense_catalog_payload(family_count=1, filler="x"):
    return {
        "catalog_version": "1",
        "families": [{
            "id": f"custom_dense{family}", "label": f"Family {family}",
            "title_cues": [f"SYNTHETIC FAMILY {family}"],
            "fields": [{
                "id": f"field_{field}", "label": f"Field {field}",
                "aliases": [f"f{field:02d}a{alias:02d}" + filler * 74 for alias in range(12)],
            } for field in range(20)],
        } for family in range(family_count)],
    }


class CustomDocumentFamilyCatalogTests(unittest.TestCase):
    def test_large_valid_catalog_snapshots_remain_valid_and_reconstructable(self):
        for filler in ("x", "é", "漢", '"', "\\"):
            with self.subTest(filler=filler):
                raw = json.dumps(dense_catalog_payload(filler=filler), ensure_ascii=False,
                                 separators=(",", ":"))
                self.assertLess(len(raw.encode("utf-8")), catalog_module.MAX_CATALOG_BYTES)
                catalog = load_custom_family_catalog(raw)
                snapshot = catalog.snapshot_for("custom_dense0")

                self.assertEqual(validate_family_snapshot(snapshot), [])
                reopened = catalog_from_snapshots([snapshot])

                self.assertEqual(reopened.sha256, catalog.sha256)
                self.assertEqual(reopened.snapshot_for("custom_dense0"), snapshot)

    def test_large_valid_catalog_can_be_saved_and_reopened(self):
        raw = json.dumps(dense_catalog_payload(3), separators=(",", ":"))
        self.assertLess(len(raw.encode("utf-8")), catalog_module.MAX_CATALOG_BYTES)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "families.json"
            store = DocumentFamilyCatalogStore(path)
            saved = store.save(raw)

            reopened = store.load()

            self.assertLessEqual(path.stat().st_size, catalog_module.MAX_CATALOG_BYTES)
            self.assertEqual(reopened.sha256, saved.sha256)
            self.assertEqual(json.loads(reopened.as_json()), json.loads(raw))

    def test_catalog_rejects_surrogate_unicode_as_domain_validation_error(self):
        payload = catalog_payload()
        payload["families"][0]["fields"][0]["label"] = "\ud800"

        with self.assertRaisesRegex(DocumentFamilyCatalogError, "Unicode"):
            load_custom_family_catalog(json.dumps(payload))

    def test_catalog_accepts_escaped_surrogate_pair_as_non_bmp_text(self):
        payload = catalog_payload()
        payload["families"][0]["fields"][0]["label"] = "Negozio \U0001f600"

        catalog = load_custom_family_catalog(json.dumps(payload))

        self.assertEqual(catalog.families[0].fields[0]["label"], "Negozio \U0001f600")

    def test_loaded_catalog_field_definitions_are_immutable(self):
        catalog = load_custom_family_catalog(json.dumps(catalog_payload(), ensure_ascii=False))
        original_catalog_hash = catalog.sha256
        original_snapshot = catalog.snapshot_for("custom_taxi_receipt")

        with self.assertRaises(TypeError):
            catalog.families[0].fields[0]["label"] = "changed after hashing"

        self.assertEqual(catalog.sha256, original_catalog_hash)
        self.assertEqual(catalog.snapshot_for("custom_taxi_receipt"), original_snapshot)

    def test_proposals_reject_invalid_source_hash_before_emitting_evidence(self):
        catalog = load_custom_family_catalog(json.dumps(catalog_payload(), ensure_ascii=False))
        page = OCRPageResult(
            "not-a-sha256", 1, "synthetic-ocr", "fixture-1", "it",
            (OCRToken("title", "RICEVUTA TAXI", POLYGON),),
        )

        with self.assertRaisesRegex(DocumentFamilyCatalogError, "source_sha256"):
            build_custom_family_proposals((page,), catalog)

    def test_proposals_reject_invalid_unicode_in_ocr_evidence(self):
        catalog = load_custom_family_catalog(json.dumps(catalog_payload(), ensure_ascii=False))
        invalid_pages = (
            OCRPageResult(
                SOURCE, 1, "synthetic-ocr", "fixture-1", "it",
                (OCRToken("title\ud800", "RICEVUTA TAXI", POLYGON),),
            ),
            OCRPageResult(
                SOURCE, 1, "synthetic-ocr", "fixture-1", "it",
                (OCRToken("title", "RICEVUTA TAXI\ud800", POLYGON),),
            ),
            OCRPageResult(
                SOURCE, 1, "synthetic-ocr\ud800", "fixture-1", "it",
                (OCRToken("title", "RICEVUTA TAXI", POLYGON),),
            ),
            OCRPageResult(
                SOURCE, 1, "synthetic-ocr", "fixture-1\ud800", "it",
                (OCRToken("title", "RICEVUTA TAXI", POLYGON),),
            ),
        )
        for page in invalid_pages:
            with self.subTest(page=page), self.assertRaisesRegex(
                DocumentFamilyCatalogError, "Unicode"
            ):
                build_custom_family_proposals((page,), catalog)

    def test_proposals_bound_ocr_engine_provenance_metadata(self):
        catalog = load_custom_family_catalog(json.dumps(catalog_payload(), ensure_ascii=False))
        oversized_pages = (
            OCRPageResult(
                SOURCE, 1, "e" * 129, "fixture-1", "it",
                (OCRToken("title", "RICEVUTA TAXI", POLYGON),),
            ),
            OCRPageResult(
                SOURCE, 1, "synthetic-ocr", "v" * 129, "it",
                (OCRToken("title", "RICEVUTA TAXI", POLYGON),),
            ),
        )
        for page in oversized_pages:
            with self.subTest(page_number=page.page_number), self.assertRaisesRegex(
                DocumentFamilyCatalogError, "128-character limit"
            ):
                build_custom_family_proposals((page,), catalog)

    def test_proposals_reject_malformed_polygon_and_token_before_evidence_creation(self):
        catalog = load_custom_family_catalog(json.dumps(catalog_payload(), ensure_ascii=False))
        bad_polygons = (
            ((0.1, 0.2), (1.1, 0.2), (0.8, 0.4)),
            ((0.1, 0.2), (float("nan"), 0.2), (0.8, 0.4)),
            ((0.1, 0.2), (0.8, 0.2)),
        )
        for index, polygon in enumerate(bad_polygons):
            page = OCRPageResult(
                SOURCE, 1, "synthetic-ocr", "fixture-1", "it",
                (OCRToken(f"title-{index}", "RICEVUTA TAXI", polygon),),
            )
            with self.subTest(polygon=polygon), self.assertRaisesRegex(
                DocumentFamilyCatalogError, "polygon"
            ):
                build_custom_family_proposals((page,), catalog)

        invalid_token = OCRToken("", "RICEVUTA TAXI", POLYGON)
        page = OCRPageResult(
            SOURCE, 1, "synthetic-ocr", "fixture-1", "it", (invalid_token,),
        )
        with self.assertRaisesRegex(DocumentFamilyCatalogError, "token_id"):
            build_custom_family_proposals((page,), catalog)

        for confidence in (float("nan"), -0.1, 1.1, True):
            invalid_confidence = OCRToken(
                f"confidence-{confidence}", "RICEVUTA TAXI", POLYGON, confidence,
            )
            page = OCRPageResult(
                SOURCE, 1, "synthetic-ocr", "fixture-1", "it", (invalid_confidence,),
            )
            with self.subTest(confidence=confidence), self.assertRaisesRegex(
                DocumentFamilyCatalogError, "confidence"
            ):
                build_custom_family_proposals((page,), catalog)

    def test_proposals_reject_zero_area_polygon_before_emitting_evidence(self):
        catalog = load_custom_family_catalog(json.dumps(catalog_payload(), ensure_ascii=False))
        zero_area_polygons = (
            ((0.1, 0.1), (0.4, 0.4), (0.7, 0.7)),
            ((0.1, 0.1), (0.4, 0.1), (0.7, 0.1), (0.4, 0.1)),
        )

        for index, polygon in enumerate(zero_area_polygons):
            page = OCRPageResult(
                SOURCE, 1, "synthetic-ocr", "fixture-1", "it",
                (OCRToken(f"zero-area-{index}", "RICEVUTA TAXI", polygon),),
            )
            with self.subTest(polygon=polygon), self.assertRaisesRegex(
                DocumentFamilyCatalogError, "non-zero area"
            ):
                build_custom_family_proposals((page,), catalog)

    def test_proposals_reject_self_intersecting_polygon_with_nonzero_signed_area(self):
        catalog = load_custom_family_catalog(json.dumps(catalog_payload(), ensure_ascii=False))
        invalid_polygons = (
            # The edges cross, but the shoelace sum is non-zero; an area-only check accepts it.
            ((0.1, 0.1), (0.9, 0.9), (0.1, 0.9), (0.8, 0.1)),
            # Adjacent collinear edges backtrack and overlap while the polygon still has area.
            ((0.1, 0.1), (0.8, 0.1), (0.4, 0.1), (0.4, 0.8), (0.1, 0.8)),
            # Non-adjacent edges touch at a vertex that is not repeated in the vertex list.
            ((0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.5, 0.1), (0.1, 0.9)),
            # Non-adjacent collinear edges overlap while the polygon still has area.
            ((0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.6, 0.1), (0.4, 0.1), (0.1, 0.9)),
        )
        for index, polygon in enumerate(invalid_polygons):
            page = OCRPageResult(
                SOURCE, 1, "synthetic-ocr", "fixture-1", "it",
                (OCRToken(f"crossing-region-{index}", "RICEVUTA TAXI", polygon),),
            )
            with self.subTest(polygon=polygon), self.assertRaisesRegex(
                DocumentFamilyCatalogError, "must be simple"
            ):
                build_custom_family_proposals((page,), catalog)

    def test_proposals_reject_duplicate_token_ids_and_boolean_polygon_coordinates(self):
        catalog = load_custom_family_catalog(json.dumps(catalog_payload(), ensure_ascii=False))
        duplicate_ids = OCRPageResult(
            SOURCE, 1, "synthetic-ocr", "fixture-1", "it",
            (
                OCRToken("same-id", "RICEVUTA TAXI", POLYGON),
                OCRToken("same-id", "RICEVUTA TAXI", POLYGON),
            ),
        )
        with self.assertRaisesRegex(DocumentFamilyCatalogError, "unique"):
            build_custom_family_proposals((duplicate_ids,), catalog)

        invalid_coordinate = OCRToken(
            "boolean-coordinate", "RICEVUTA TAXI",
            ((False, 0.1), (0.8, 0.1), (0.8, 0.4)),
        )
        page = OCRPageResult(
            SOURCE, 1, "synthetic-ocr", "fixture-1", "it", (invalid_coordinate,),
        )
        with self.assertRaisesRegex(DocumentFamilyCatalogError, "coordinates"):
            build_custom_family_proposals((page,), catalog)

    def test_proposals_accept_explicitly_closed_positive_area_polygon(self):
        catalog = load_custom_family_catalog(json.dumps(catalog_payload(), ensure_ascii=False))
        closed_polygon = POLYGON + (POLYGON[0],)
        page = OCRPageResult(
            SOURCE, 1, "synthetic-ocr", "fixture-1", "it",
            (OCRToken("closed-region", "RICEVUTA TAXI", closed_polygon),),
        )

        proposals = build_custom_family_proposals((page,), catalog)

        self.assertEqual(proposals["document_family_candidates"]["status"], "uncertain")

    def test_proposals_accept_simple_concave_polygon(self):
        catalog = load_custom_family_catalog(json.dumps(catalog_payload(), ensure_ascii=False))
        concave_polygon = (
            (0.1, 0.1), (0.8, 0.1), (0.45, 0.35), (0.8, 0.8), (0.1, 0.8),
        )
        page = OCRPageResult(
            SOURCE, 1, "synthetic-ocr", "fixture-1", "it",
            (OCRToken("concave-region", "RICEVUTA TAXI", concave_polygon),),
        )

        proposals = build_custom_family_proposals((page,), catalog)

        self.assertEqual(proposals["document_family_candidates"]["status"], "uncertain")

    def test_proposals_bound_total_polygon_intersection_work(self):
        catalog = load_custom_family_catalog(json.dumps(catalog_payload(), ensure_ascii=False))
        page = OCRPageResult(
            SOURCE, 1, "synthetic-ocr", "fixture-1", "it",
            (OCRToken("bounded-geometry", "RICEVUTA TAXI", POLYGON),),
        )

        with patch.object(catalog_module, "MAX_OCR_POLYGON_EDGE_CHECKS_PER_DOCUMENT", 1):
            with self.assertRaisesRegex(DocumentFamilyCatalogError, "complexity limit"):
                build_custom_family_proposals((page,), catalog)

    def test_proposals_reject_integer_overflow_in_confidence_and_polygon_coordinates(self):
        catalog = load_custom_family_catalog(json.dumps(catalog_payload(), ensure_ascii=False))
        enormous_integer = 10**1000
        invalid_values = (
            (
                OCRToken(
                    "huge-coordinate", "RICEVUTA TAXI",
                    ((enormous_integer, 0), (1, 0), (1, 1)),
                ),
                "coordinates",
            ),
            (
                OCRToken("huge-confidence", "RICEVUTA TAXI", POLYGON, enormous_integer),
                "confidence",
            ),
        )

        for token, message in invalid_values:
            page = OCRPageResult(SOURCE, 1, "synthetic-ocr", "fixture-1", "it", (token,))
            with self.subTest(message=message), self.assertRaisesRegex(
                DocumentFamilyCatalogError, message
            ):
                build_custom_family_proposals((page,), catalog)

    def test_proposals_reject_numeric_subclasses_before_custom_comparison(self):
        class HostileInteger(int):
            def __ge__(self, other):
                raise RuntimeError("custom comparison must not run")

        catalog = load_custom_family_catalog(json.dumps(catalog_payload(), ensure_ascii=False))
        coordinate_token = OCRToken(
            "hostile-coordinate", "RICEVUTA TAXI",
            ((HostileInteger(0), 0), (1, 0), (1, 1)),
        )
        coordinate_page = OCRPageResult(
            SOURCE, 1, "synthetic-ocr", "fixture-1", "it", (coordinate_token,),
        )
        with self.assertRaisesRegex(DocumentFamilyCatalogError, "coordinates"):
            build_custom_family_proposals((coordinate_page,), catalog)

        confidence_token = OCRToken(
            "hostile-confidence", "RICEVUTA TAXI", POLYGON, HostileInteger(1),
        )
        confidence_page = OCRPageResult(
            SOURCE, 1, "synthetic-ocr", "fixture-1", "it", (confidence_token,),
        )
        with self.assertRaisesRegex(DocumentFamilyCatalogError, "confidence"):
            build_custom_family_proposals((confidence_page,), catalog)

    def test_proposals_reject_mixed_source_and_duplicate_page_numbers(self):
        catalog = load_custom_family_catalog(json.dumps(catalog_payload(), ensure_ascii=False))
        token = OCRToken("title", "RICEVUTA TAXI", POLYGON)
        pages = (
            OCRPageResult(SOURCE, 1, "synthetic-ocr", "fixture-1", "it", (token,)),
            OCRPageResult("b" * 64, 2, "synthetic-ocr", "fixture-1", "it", (token,)),
        )
        with self.assertRaisesRegex(DocumentFamilyCatalogError, "same source"):
            build_custom_family_proposals(pages, catalog)

        duplicate_pages = (
            pages[0],
            OCRPageResult(SOURCE, 1, "synthetic-ocr", "fixture-1", "it", (token,)),
        )
        with self.assertRaisesRegex(DocumentFamilyCatalogError, "unique"):
            build_custom_family_proposals(duplicate_pages, catalog)

    def test_page_iterable_is_consumed_only_to_the_page_limit_plus_one(self):
        catalog = load_custom_family_catalog(json.dumps(catalog_payload(), ensure_ascii=False))
        consumed = []

        def pages():
            for number in itertools.count(1):
                consumed.append(number)
                yield OCRPageResult(SOURCE, number, "synthetic-ocr", "fixture-1", "it", ())

        with self.assertRaisesRegex(DocumentFamilyCatalogError, "page limit"):
            build_custom_family_proposals(pages(), catalog)
        self.assertEqual(len(consumed), 101)

    def test_catalog_is_bounded_and_snapshot_has_canonical_sha256(self):
        raw = json.dumps(catalog_payload(), ensure_ascii=False)

        catalog = load_custom_family_catalog(raw)

        canonical = json.dumps(
            catalog_payload(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        self.assertEqual(catalog.sha256, hashlib.sha256(canonical).hexdigest())
        self.assertEqual(catalog.snapshot_for("custom_taxi_receipt")["family"]["label"], "Ricevuta taxi")

    def test_snapshot_rejects_noncanonical_family_even_when_hash_matches_raw_shape(self):
        catalog = load_custom_family_catalog(json.dumps(catalog_payload(), ensure_ascii=False))
        snapshot = catalog.snapshot_for("custom_taxi_receipt")
        snapshot["family"]["label"] = " Ricevuta   taxi "
        encoded = json.dumps(
            snapshot["family"], ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        snapshot["family_sha256"] = hashlib.sha256(encoded).hexdigest()

        issues = validate_family_snapshot(snapshot)

        self.assertTrue(issues)

    def test_snapshot_rejects_oversized_family_before_serializing_it(self):
        catalog = load_custom_family_catalog(json.dumps(catalog_payload(), ensure_ascii=False))
        snapshot = catalog.snapshot_for("custom_taxi_receipt")
        snapshot["family"]["label"] = "x" * (catalog_module.MAX_CATALOG_BYTES * 2)

        with patch.object(catalog_module, "_canonical_json", side_effect=AssertionError("serialized")):
            issues = validate_family_snapshot(snapshot)

        self.assertTrue(issues)

    def test_catalog_rejects_colliding_synthesized_custom_field_names(self):
        payload = {
            "catalog_version": "1",
            "families": [
                {
                    "id": "custom_aa", "label": "Famiglia A", "title_cues": ["A"],
                    "fields": [{"id": "bb_cc", "label": "Campo A", "aliases": ["Campo A"]}],
                },
                {
                    "id": "custom_aa_bb", "label": "Famiglia B", "title_cues": ["B"],
                    "fields": [{"id": "cc", "label": "Campo B", "aliases": ["Campo B"]}],
                },
            ],
        }

        with self.assertRaises(DocumentFamilyCatalogError):
            load_custom_family_catalog(json.dumps(payload, ensure_ascii=False))

    def test_family_cue_proposal_limit_is_enforced_before_more_evidence_is_built(self):
        catalog = load_custom_family_catalog(json.dumps(catalog_payload(), ensure_ascii=False))
        page = OCRPageResult(
            SOURCE, 1, "synthetic-ocr", "fixture-1", "it",
            tuple(
                OCRToken(f"title-{index}", "RICEVUTA TAXI", POLYGON)
                for index in range(MAX_PROPOSALS + 1)
            ),
        )
        with patch.object(catalog_module, "_evidence", wraps=catalog_module._evidence) as make_evidence:
            with self.assertRaises(DocumentFamilyCatalogError):
                build_custom_family_proposals((page,), catalog)

        self.assertEqual(make_evidence.call_count, MAX_PROPOSALS)

    def test_rejects_builtin_collision_duplicate_cues_and_executable_rules(self):
        payload = catalog_payload()
        payload["families"][0]["id"] = "invoice"
        with self.assertRaises(DocumentFamilyCatalogError):
            load_custom_family_catalog(json.dumps(payload))

    def test_catalog_v1_preserves_text_field_snapshot_shape_and_hash(self):
        catalog = load_custom_family_catalog(json.dumps(catalog_payload(), ensure_ascii=False))

        snapshot = catalog.snapshot_for("custom_taxi_receipt")

        self.assertEqual(catalog.version, "1")
        self.assertEqual(set(snapshot["family"]["fields"][0]), {"id", "label", "aliases"})
        self.assertEqual(snapshot["catalog_version"], "1")

    def test_catalog_v1_rejects_typed_fields(self):
        payload = catalog_payload()
        payload["families"][0]["fields"][0]["type"] = "date"

        with self.assertRaises(DocumentFamilyCatalogError):
            load_custom_family_catalog(json.dumps(payload, ensure_ascii=False))

    def test_catalog_v2_accepts_only_the_fixed_custom_field_types(self):
        payload = catalog_payload()
        payload["catalog_version"] = "2"
        payload["families"][0]["fields"][0]["type"] = "identifier"

        catalog = load_custom_family_catalog(json.dumps(payload, ensure_ascii=False))
        snapshot = catalog.snapshot_for("custom_taxi_receipt")

        self.assertEqual(catalog.version, "2")
        self.assertEqual(snapshot["catalog_version"], "2")
        self.assertEqual(snapshot["family"]["fields"][0]["type"], "identifier")

        payload["families"][0]["fields"][0]["type"] = "regex"
        with self.assertRaises(DocumentFamilyCatalogError):
            load_custom_family_catalog(json.dumps(payload, ensure_ascii=False))

    def test_catalog_v2_required_flag_is_boolean_and_true_only_in_snapshot(self):
        payload = catalog_payload()
        payload["catalog_version"] = "2"
        payload["families"][0]["fields"][0]["required"] = True
        required = load_custom_family_catalog(json.dumps(payload, ensure_ascii=False))
        required_field = required.snapshot_for("custom_taxi_receipt")["family"]["fields"][0]
        self.assertIs(required_field["required"], True)

        payload["families"][0]["fields"][0]["required"] = False
        optional = load_custom_family_catalog(json.dumps(payload, ensure_ascii=False))
        optional_field = optional.snapshot_for("custom_taxi_receipt")["family"]["fields"][0]
        self.assertNotIn("required", optional_field)
        self.assertEqual(optional_field, {
            "id": "pickup_city", "label": "Città di partenza", "aliases": ["Partenza"],
        })
        self.assertEqual(
            optional.snapshot_for("custom_taxi_receipt")["family_sha256"],
            "845485ea279a557cfe35798b0f4e1f59c0dd948fe9c67a142c4ddc1d12168adf",
        )

    def test_catalog_v2_rejects_non_boolean_required_values(self):
        for invalid in ("true", 1, None):
            payload = catalog_payload()
            payload["catalog_version"] = "2"
            payload["families"][0]["fields"][0]["required"] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(DocumentFamilyCatalogError):
                load_custom_family_catalog(json.dumps(payload, ensure_ascii=False))

    def test_catalog_v1_rejects_required_flag(self):
        payload = catalog_payload()
        payload["families"][0]["fields"][0]["required"] = True

        with self.assertRaises(DocumentFamilyCatalogError):
            load_custom_family_catalog(json.dumps(payload, ensure_ascii=False))

    def test_custom_date_amount_and_identifier_proposals_are_typed_but_uncertain(self):
        payload = {
            "catalog_version": "2",
            "families": [{
                "id": "custom_taxi_receipt", "label": "Ricevuta taxi",
                "title_cues": ["RICEVUTA TAXI"],
                "fields": [
                    {"id": "trip_date", "label": "Data corsa", "aliases": ["Data"], "type": "date"},
                    {"id": "fare", "label": "Tariffa", "aliases": ["Importo"], "type": "amount"},
                    {"id": "reference", "label": "Riferimento", "aliases": ["Codice"], "type": "identifier"},
                ],
            }],
        }
        catalog = load_custom_family_catalog(json.dumps(payload, ensure_ascii=False))
        page = OCRPageResult(
            SOURCE, 1, "synthetic-ocr", "fixture-1", "it",
            (
                OCRToken("date", "Data: 02/03/2026", POLYGON),
                OCRToken("amount", "Importo: 1.234,50", POLYGON),
                OCRToken("identifier", "Codice: 000123", POLYGON),
            ),
        )

        proposals = build_custom_family_proposals((page,), catalog)

        date_candidate = proposals["custom_taxi_receipt_trip_date"]
        self.assertEqual(date_candidate["status"], "uncertain")
        self.assertEqual(
            {item["value"] for item in date_candidate["alternatives"]},
            {"2026-03-02", "2026-02-03"},
        )
        self.assertTrue(all(item["evidence"][0]["source_sha256"] == SOURCE for item in date_candidate["alternatives"]))
        self.assertTrue(all("normalization" in item for item in date_candidate["alternatives"]))

        amount_candidate = proposals["custom_taxi_receipt_fare"]
        self.assertEqual(amount_candidate["status"], "uncertain")
        self.assertEqual(amount_candidate["alternatives"][0]["value"], "1234.50")
        self.assertEqual(amount_candidate["alternatives"][0]["normalization"]["original_literal"], "1.234,50")

        identifier_candidate = proposals["custom_taxi_receipt_reference"]
        self.assertEqual(identifier_candidate["alternatives"][0]["value"], "000123")

    def test_invalid_typed_literals_are_unreadable_with_source_evidence(self):
        payload = {
            "catalog_version": "2",
            "families": [{
                "id": "custom_taxi_receipt", "label": "Ricevuta taxi",
                "title_cues": ["RICEVUTA TAXI"],
                "fields": [
                    {"id": "trip_date", "label": "Data corsa", "aliases": ["Data"], "type": "date"},
                    {"id": "fare", "label": "Tariffa", "aliases": ["Importo"], "type": "amount"},
                ],
            }],
        }
        catalog = load_custom_family_catalog(json.dumps(payload, ensure_ascii=False))
        page = OCRPageResult(
            SOURCE, 1, "synthetic-ocr", "fixture-1", "it",
            (
                OCRToken("bad-date", "Data: 31/02/2026", POLYGON),
                OCRToken("mixed-separator-date", "Data: 02/03-2026", POLYGON),
                OCRToken("bad-amount", "Importo: 12,5", POLYGON),
            ),
        )

        proposals = build_custom_family_proposals((page,), catalog)

        for name in ("custom_taxi_receipt_trip_date", "custom_taxi_receipt_fare"):
            candidate = proposals[name]
            self.assertEqual(candidate["status"], "unreadable")
            self.assertIsNone(candidate["value"])
            self.assertEqual(candidate["evidence"][0]["source_sha256"], SOURCE)

    def test_reconstructed_snapshots_reject_mixed_catalog_versions(self):
        v1 = load_custom_family_catalog(json.dumps(catalog_payload(), ensure_ascii=False))
        v2_payload = catalog_payload()
        v2_payload["catalog_version"] = "2"
        v2_payload["families"][0]["id"] = "custom_hotel_receipt"
        v2 = load_custom_family_catalog(json.dumps(v2_payload, ensure_ascii=False))

        with self.assertRaises(DocumentFamilyCatalogError):
            catalog_from_snapshots((
                v1.snapshot_for("custom_taxi_receipt"),
                v2.snapshot_for("custom_hotel_receipt"),
            ))

        payload = catalog_payload()
        payload["families"][0]["title_cues"].append("ricevuta taxi")
        with self.assertRaises(DocumentFamilyCatalogError):
            load_custom_family_catalog(json.dumps(payload))

        payload = catalog_payload()
        payload["families"][0]["rules"] = {"python": "unsafe"}
        with self.assertRaises(DocumentFamilyCatalogError):
            load_custom_family_catalog(json.dumps(payload))

    def test_snapshot_reconstruction_bounds_input_before_materializing_catalog(self):
        catalog = load_custom_family_catalog(json.dumps(catalog_payload(), ensure_ascii=False))
        snapshot = catalog.snapshot_for("custom_taxi_receipt")
        consumed = 0

        def many_snapshots():
            nonlocal consumed
            for _ in range(MAX_FAMILIES + 20):
                consumed += 1
                yield snapshot

        with self.assertRaisesRegex(DocumentFamilyCatalogError, "25-family limit"):
            catalog_from_snapshots(many_snapshots())

        self.assertEqual(consumed, MAX_FAMILIES + 1)

    def test_custom_title_and_field_proposals_are_uncertain_and_evidence_bound(self):
        catalog = load_custom_family_catalog(json.dumps(catalog_payload(), ensure_ascii=False))
        page = OCRPageResult(
            SOURCE, 1, "synthetic-ocr", "fixture-1", "it",
            (
                OCRToken("title", "RICEVUTA TAXI", POLYGON),
                OCRToken("pickup", "Partenza: Milano", POLYGON),
            ),
        )

        proposals = build_custom_family_proposals((page,), catalog)

        family = proposals["document_family_candidates"]
        self.assertEqual(family["status"], "uncertain")
        self.assertEqual(family["alternatives"][0]["value"], "custom_taxi_receipt")
        self.assertEqual(family["alternatives"][0]["evidence"][0]["source_sha256"], SOURCE)
        self.assertEqual(family["alternatives"][0]["evidence"][0]["token_ids"], ["title"])

        field = proposals["custom_taxi_receipt_pickup_city"]
        self.assertEqual(field["status"], "uncertain")
        self.assertEqual(field["alternatives"][0]["value"], "Milano")
        self.assertEqual(field["alternatives"][0]["evidence"][0]["token_ids"], ["pickup"])
        self.assertEqual(field["alternatives"][0]["evidence"][0]["literal"], "Partenza: Milano")

    def test_required_field_is_absent_only_after_exact_family_title_cue(self):
        payload = {
            "catalog_version": "2",
            "families": [{
                "id": "custom_taxi_receipt", "label": "Ricevuta taxi",
                "title_cues": ["RICEVUTA TAXI"],
                "fields": [{
                    "id": "pickup_city", "label": "Città di partenza",
                    "aliases": ["Partenza"], "required": True,
                }],
            }],
        }
        catalog = load_custom_family_catalog(json.dumps(payload, ensure_ascii=False))
        page_with_cue = OCRPageResult(
            SOURCE, 1, "synthetic-ocr", "fixture-1", "it",
            (OCRToken("title", "RICEVUTA TAXI", POLYGON),),
        )
        page_without_cue = OCRPageResult(
            SOURCE, 1, "synthetic-ocr", "fixture-1", "it",
            (OCRToken("other-title", "RICEVUTA TAXI!", POLYGON),),
        )

        with_cue = build_custom_family_proposals((page_with_cue,), catalog)
        without_cue = build_custom_family_proposals((page_without_cue,), catalog)

        self.assertEqual(with_cue["custom_taxi_receipt_pickup_city"], {
            "value": None, "status": "absent", "evidence": [], "alternatives": [],
        })
        self.assertNotIn("custom_taxi_receipt_pickup_city", without_cue)

    def test_matching_required_alias_is_not_reported_as_absent(self):
        payload = {
            "catalog_version": "2",
            "families": [{
                "id": "custom_taxi_receipt", "label": "Ricevuta taxi",
                "title_cues": ["RICEVUTA TAXI"],
                "fields": [{
                    "id": "pickup_city", "label": "Città di partenza",
                    "aliases": ["Partenza"], "required": True,
                }],
            }],
        }
        catalog = load_custom_family_catalog(json.dumps(payload, ensure_ascii=False))
        page = OCRPageResult(
            SOURCE, 1, "synthetic-ocr", "fixture-1", "it",
            (
                OCRToken("title", "RICEVUTA TAXI", POLYGON),
                OCRToken("pickup", "Partenza: Milano", POLYGON),
            ),
        )

        proposals = build_custom_family_proposals((page,), catalog)

        candidate = proposals["custom_taxi_receipt_pickup_city"]
        self.assertEqual(candidate["status"], "uncertain")
        self.assertEqual(candidate["alternatives"][0]["value"], "Milano")

    def test_title_cues_are_literal_and_field_values_stay_as_observed_text(self):
        catalog = load_custom_family_catalog(json.dumps(catalog_payload(), ensure_ascii=False))
        page = OCRPageResult(
            SOURCE, 1, "synthetic-ocr", "fixture-1", "it",
            (
                OCRToken("no-regex", "RICEVUTA TAXI!", POLYGON),
                OCRToken("field", "Partenza: 01/02/2026", POLYGON),
            ),
        )

        proposals = build_custom_family_proposals((page,), catalog)

        self.assertNotIn("document_family_candidates", proposals)
        field = proposals["custom_taxi_receipt_pickup_city"]
        self.assertEqual(field["alternatives"][0]["value"], "01/02/2026")
        self.assertNotIn("normalization", field["alternatives"][0])

    def test_catalog_store_atomic_save_rejects_invalid_edits_without_losing_previous_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            store = DocumentFamilyCatalogStore(Path(directory) / "families.json")
            saved = store.save(json.dumps(catalog_payload(), ensure_ascii=False))

            with self.assertRaises(DocumentFamilyCatalogError):
                store.save('{"catalog_version":"1","families":[{"rules":"executable"}]}')

            self.assertEqual(store.load().sha256, saved.sha256)

    def test_catalog_store_round_trips_v2_field_types(self):
        payload = catalog_payload()
        payload["catalog_version"] = "2"
        payload["families"][0]["fields"][0]["type"] = "identifier"
        with tempfile.TemporaryDirectory() as directory:
            store = DocumentFamilyCatalogStore(Path(directory) / "families.json")

            saved = store.save(json.dumps(payload, ensure_ascii=False))
            reopened = store.load()

            self.assertEqual(reopened.version, "2")
            self.assertEqual(reopened.sha256, saved.sha256)
            self.assertEqual(
                reopened.snapshot_for("custom_taxi_receipt")["family"]["fields"][0]["type"],
                "identifier",
            )


if __name__ == "__main__":
    unittest.main()
