import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from alfa_document_intelligence import taxonomy_registry as taxonomy


class TaxonomyRegistryTests(unittest.TestCase):
    def test_builtin_catalog_is_versioned_and_hash_bound(self):
        document = taxonomy.default_catalog()
        canonical, digest = taxonomy.validate_catalog(document)
        self.assertEqual(document["version"], 1)
        self.assertEqual(document["schema_version"], taxonomy.CATALOG_SCHEMA_VERSION)
        self.assertEqual(canonical, taxonomy.canonical_json(document))
        self.assertEqual(digest, taxonomy.catalog_sha256(document))
        self.assertEqual(
            {item["id"] for item in document["types"]},
            {"invoice", "expense_report", "fiscal_receipt", "parking_receipt",
             "hotel_document", "pos_slip", "other", "unknown"},
        )

    def test_default_and_new_store_stay_v1_until_v2_is_requested(self):
        default = taxonomy.default_catalog()
        self.assertEqual(default["schema_version"], "1.0.0")
        self.assertEqual(
            taxonomy.catalog_sha256(default),
            "44322abad12f348a9f69c4987e4011f9f53fb8d5538922a89c477a9e1a28834b",
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = taxonomy.TaxonomyStore(root)
            self.assertEqual(store.get_current()[0]["schema_version"], "1.0.0")

            new_v2_root = root / "new-v2"
            new_v2_root.mkdir()
            requested_v2 = taxonomy.TaxonomyStore(new_v2_root, initial_generation="2.0.0")
            self.assertEqual(requested_v2.get_current()[0]["schema_version"], "2.0.0")

            reopened_with_v2_request = taxonomy.TaxonomyStore(root, initial_generation="2.0.0")
            self.assertEqual(reopened_with_v2_request.get_current()[0]["schema_version"], "1.0.0")

    def test_catalog_validation_dispatches_on_schema_generation_not_revision(self):
        v1 = taxonomy.default_catalog()
        v1["version"] = 17
        taxonomy.validate_catalog(v1)

        v2 = taxonomy.default_catalog_v2()
        v2["version"] = 1
        taxonomy.validate_catalog(v2)

        unknown = copy.deepcopy(v2)
        unknown["schema_version"] = "9.0.0"
        with self.assertRaises(taxonomy.TaxonomyError):
            taxonomy.validate_catalog(unknown)

    def test_v2_catalog_adds_only_invoice_subtotal_to_invoice(self):
        v1 = taxonomy.default_catalog()
        v2 = taxonomy.default_catalog_v2()
        self.assertEqual(v2["schema_version"], "2.0.0")
        self.assertEqual(v2["version"], 1)
        v2_types = {item["id"]: copy.deepcopy(item) for item in v2["types"]}
        subtotal = next(field for field in v2_types["invoice"]["fields"]
                        if field["id"] == "invoice_subtotal")
        self.assertEqual(subtotal["value_kind"], "money")
        self.assertEqual(subtotal["extraction_mode"], "built_in")
        v2_types["invoice"]["fields"] = [
            field for field in v2_types["invoice"]["fields"]
            if field["id"] != "invoice_subtotal"
        ]
        self.assertEqual(v2_types, {item["id"]: item for item in v1["types"]})
        taxonomy.validate_catalog(v2)

    def test_v1_to_v2_upgrade_appends_one_revision_and_preserves_history(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = taxonomy.TaxonomyStore(temporary)
            initial, initial_hash = store.get_current()
            self.assertEqual(initial["schema_version"], "1.0.0")
            self.assertEqual(initial_hash,
                             "44322abad12f348a9f69c4987e4011f9f53fb8d5538922a89c477a9e1a28834b")

            edited = copy.deepcopy(initial)
            edited["version"] += 1
            invoice = next(item for item in edited["types"] if item["id"] == "invoice")
            invoice["label"] = "Fattura modificata"
            next(field for field in invoice["fields"] if field["id"] == "total_amount")["required"] = True
            next(item for item in edited["types"] if item["id"] == "hotel_document")["enabled"] = False
            edited["types"].append({
                "id": "custom_membership_card", "label": "Tessera", "enabled": True,
                "role": "custom_manual", "extraction_mode": "manual_only",
                "fields": [{
                    "id": "custom_member_code", "label": "Codice socio", "value_kind": "identifier",
                    "required": False, "review_only": True, "extraction_mode": "manual_only",
                }],
            })
            saved_v1, saved_v1_hash = store.save_catalog(
                edited, expected_version=initial["version"], expected_sha256=initial_hash,
            )
            historical = {
                version: (taxonomy.canonical_json(store.get_version(version)[0]),
                          store.get_version(version)[1])
                for version in (initial["version"], saved_v1["version"])
            }

            upgraded, upgraded_hash = store.upgrade_to_v2(
                expected_version=saved_v1["version"], expected_sha256=saved_v1_hash,
            )
            self.assertEqual(upgraded["version"], saved_v1["version"] + 1)
            self.assertEqual(upgraded["schema_version"], "2.0.0")
            upgraded_invoice = next(item for item in upgraded["types"] if item["id"] == "invoice")
            self.assertEqual(sum(field["id"] == "invoice_subtotal" for field in upgraded_invoice["fields"]), 1)
            self.assertEqual(upgraded_invoice["label"], "Fattura modificata")
            self.assertTrue(next(field for field in upgraded_invoice["fields"]
                                 if field["id"] == "total_amount")["required"])
            self.assertFalse(next(item for item in upgraded["types"]
                                  if item["id"] == "hotel_document")["enabled"])
            self.assertEqual(next(item for item in upgraded["types"]
                                  if item["id"] == "custom_membership_card"),
                             next(item for item in saved_v1["types"]
                                  if item["id"] == "custom_membership_card"))
            self.assertEqual(store.get_current(), (upgraded, upgraded_hash))

            reopened = taxonomy.TaxonomyStore(temporary)
            for version, expected_snapshot in historical.items():
                historical_document, historical_hash = reopened.get_version(version)
                self.assertEqual(taxonomy.canonical_json(historical_document), expected_snapshot[0])
                self.assertEqual(historical_hash, expected_snapshot[1])
            self.assertEqual(reopened.get_version(upgraded["version"]), (upgraded, upgraded_hash))

    def test_stale_v2_upgrade_preserves_current_catalog_and_history(self):
        with tempfile.TemporaryDirectory() as temporary:
            first = taxonomy.TaxonomyStore(temporary)
            stale = taxonomy.TaxonomyStore(temporary)
            old, old_hash = first.get_current()
            history_before = first.get_version(old["version"])
            first.upgrade_to_v2(expected_version=old["version"], expected_sha256=old_hash)
            current_after_first = first.get_current()
            with self.assertRaises(taxonomy.TaxonomyConflict):
                stale.upgrade_to_v2(expected_version=old["version"], expected_sha256=old_hash)
            self.assertEqual(first.get_current(), current_after_first)
            self.assertEqual(first.get_version(old["version"]), history_before)
            self.assertEqual(first.get_version(current_after_first[0]["version"]), current_after_first)

    def test_v2_upgrade_transaction_failure_rolls_back_current_and_history(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = taxonomy.TaxonomyStore(temporary)
            before_current = store.get_current()
            before_history = store.get_version(before_current[0]["version"])
            store._before_commit = lambda: (_ for _ in ()).throw(RuntimeError("injected upgrade failure"))
            with self.assertRaises(taxonomy.TaxonomyError):
                store.upgrade_to_v2(
                    expected_version=before_current[0]["version"],
                    expected_sha256=before_current[1],
                )
            self.assertEqual(store.get_current(), before_current)
            self.assertEqual(store.get_version(before_current[0]["version"]), before_history)
            self.assertIsNone(store.get_version(before_current[0]["version"] + 1))

            reopened = taxonomy.TaxonomyStore(temporary)
            self.assertEqual(reopened.get_current(), before_current)
            self.assertIsNone(reopened.get_version(before_current[0]["version"] + 1))

    def test_custom_definitions_are_forced_manual_only(self):
        document = taxonomy.default_catalog()
        custom_type = {
            "id": "custom_membership_card", "label": "Tessera", "enabled": True,
            "role": "custom_manual", "extraction_mode": "manual_only",
            "fields": [{
                "id": "custom_member_code", "label": "Codice socio", "value_kind": "identifier",
                "required": False, "review_only": True, "extraction_mode": "manual_only",
            }],
        }
        document["types"].append(custom_type)
        _canonical, _digest = taxonomy.validate_catalog(document)
        self.assertTrue(taxonomy.is_manual_only_type(custom_type))

    def test_rejects_unsafe_unknown_duplicate_and_overlimit_entries(self):
        cases = []
        extra = taxonomy.default_catalog()
        extra["execute"] = "never"
        cases.append(extra)
        duplicate = taxonomy.default_catalog()
        duplicate["types"].append(copy.deepcopy(duplicate["types"][0]))
        cases.append(duplicate)
        executable = taxonomy.default_catalog()
        executable["types"][0]["regex"] = "invoice"
        cases.append(executable)
        long_label = taxonomy.default_catalog()
        long_label["types"][0]["label"] = "x" * (taxonomy.MAX_LABEL_LENGTH + 1)
        cases.append(long_label)
        for document in cases:
            with self.subTest(document=document):
                with self.assertRaises(taxonomy.TaxonomyError):
                    taxonomy.validate_catalog(document)

    def test_builtin_identity_and_pos_role_cannot_be_changed(self):
        for mutate in (
            lambda item: item.update(id="custom_pos_slip"),
            lambda item: item.update(role="fiscal_document"),
            lambda item: item.update(label="Fattura fiscale"),
            lambda item: item.update(extraction_mode="manual_only"),
        ):
            document = taxonomy.default_catalog()
            pos = next(item for item in document["types"] if item["id"] == "pos_slip")
            mutate(pos)
            with self.subTest(pos=pos):
                with self.assertRaises(taxonomy.TaxonomyError):
                    taxonomy.validate_catalog(document)

    def test_catalog_hash_and_schema_fail_closed(self):
        document = taxonomy.default_catalog()
        canonical, digest = taxonomy.validate_catalog(document)
        self.assertLessEqual(len(canonical.encode("utf-8")), taxonomy.MAX_CATALOG_BYTES)
        self.assertEqual(digest, taxonomy.catalog_sha256(document))
        broken = copy.deepcopy(document)
        broken["schema_version"] = "2.0.0"
        with self.assertRaises(taxonomy.TaxonomyError):
            taxonomy.validate_catalog(broken)
        broken = copy.deepcopy(document)
        broken["version"] = 0
        with self.assertRaises(taxonomy.TaxonomyError):
            taxonomy.validate_catalog(broken)

    def test_exact_id_and_version_bounds(self):
        document = taxonomy.default_catalog()
        custom_type_id = "custom_" + "a" * (taxonomy.MAX_ID_LENGTH - len("custom_"))
        custom_field_id = "custom_" + "b" * (taxonomy.MAX_ID_LENGTH - len("custom_"))
        document["types"].append({
            "id": custom_type_id, "label": "Tipo", "enabled": True,
            "role": "custom_manual", "extraction_mode": "manual_only",
            "fields": [{
                "id": custom_field_id, "label": "Campo", "value_kind": "text",
                "required": False, "review_only": True, "extraction_mode": "manual_only",
            }],
        })
        document["version"] = taxonomy.MAX_CATALOG_VERSION
        taxonomy.validate_catalog(document)

        for path in ("type", "field"):
            overlong = copy.deepcopy(document)
            custom = overlong["types"][-1]
            if path == "type":
                custom["id"] += "a"
            else:
                custom["fields"][0]["id"] += "b"
            with self.subTest(path=path):
                with self.assertRaises(taxonomy.TaxonomyError):
                    taxonomy.validate_catalog(overlong)

        over_version = copy.deepcopy(document)
        over_version["version"] = taxonomy.MAX_CATALOG_VERSION + 1
        with self.assertRaises(taxonomy.TaxonomyError):
            taxonomy.validate_catalog(over_version)

    def test_exact_and_over_catalog_byte_limit(self):
        target = taxonomy.MAX_CATALOG_BYTES
        document = taxonomy.default_catalog()
        custom_types = []

        def encoded_size(value):
            return len(json.dumps(
                value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
            ).encode("utf-8"))

        while True:
            if not custom_types or len(custom_types[-1]["fields"]) == taxonomy.MAX_FIELDS_PER_TYPE:
                custom_type = {
                    "id": f"custom_padding_{len(custom_types):02d}", "label": "x", "enabled": True,
                    "role": "custom_manual", "extraction_mode": "manual_only", "fields": [],
                }
                document["types"].append(custom_type)
                custom_types.append(custom_type)
            item = custom_types[-1]
            item["fields"].append({
                "id": f"custom_field_{len(item['fields']):03d}", "label": "x", "value_kind": "text",
                "required": False, "review_only": True, "extraction_mode": "manual_only",
            })
            if encoded_size(document) > target:
                item["fields"].pop()
                if not item["fields"]:
                    custom_types.pop()
                    document["types"].pop()
                break

        needed = target - encoded_size(document)
        labels = [item for custom_type in custom_types for item in [custom_type, *custom_type["fields"]]]
        for item in labels:
            extra = min(needed, taxonomy.MAX_LABEL_LENGTH - len(item["label"]))
            if extra > 0:
                item["label"] += "x" * extra
                needed -= extra
            if needed == 0:
                break
        self.assertEqual(needed, 0)
        self.assertEqual(encoded_size(document), target)
        taxonomy.validate_catalog(document)

        over_limit = copy.deepcopy(document)
        free_label = next(
            field for item in over_limit["types"] if item["id"].startswith("custom_")
            for field in item["fields"] if len(field["label"]) < taxonomy.MAX_LABEL_LENGTH
        )
        free_label["label"] += "x"
        with self.assertRaises(taxonomy.TaxonomyError) as caught:
            taxonomy.validate_catalog(over_limit)
        self.assertEqual(caught.exception.code, "taxonomy_catalog_too_large")

    def test_catalog_size_and_collection_bounds(self):
        document = taxonomy.default_catalog()
        custom = {
            "id": "custom_max_fields", "label": "x" * taxonomy.MAX_LABEL_LENGTH,
            "enabled": True, "role": "custom_manual", "extraction_mode": "manual_only",
            "fields": [{
                "id": f"custom_field_{index:03d}", "label": "f" * taxonomy.MAX_LABEL_LENGTH,
                "value_kind": "text", "required": False, "review_only": True,
                "extraction_mode": "manual_only",
            } for index in range(taxonomy.MAX_FIELDS_PER_TYPE)],
        }
        document["types"].append(custom)
        self.assertLessEqual(len(taxonomy.canonical_json(document).encode("utf-8")), taxonomy.MAX_CATALOG_BYTES)
        taxonomy.validate_catalog(document)

        too_many_fields = copy.deepcopy(document)
        too_many_fields["types"][-1]["fields"].append(
            copy.deepcopy(too_many_fields["types"][-1]["fields"][0])
        )
        with self.assertRaises(taxonomy.TaxonomyError):
            taxonomy.validate_catalog(too_many_fields)

        too_many_types = taxonomy.default_catalog()
        for index in range(taxonomy.MAX_TYPES - len(too_many_types["types"])):
            too_many_types["types"].append({
                "id": f"custom_type_{index:02d}", "label": "Tipo", "enabled": True,
                "role": "custom_manual", "extraction_mode": "manual_only",
                "fields": [{
                    "id": f"custom_field_{index:02d}", "label": "Campo", "value_kind": "text",
                    "required": False, "review_only": True, "extraction_mode": "manual_only",
                }],
            })
        taxonomy.validate_catalog(too_many_types)
        too_many_types["types"].append(copy.deepcopy(too_many_types["types"][-1]))
        with self.assertRaises(taxonomy.TaxonomyError):
            taxonomy.validate_catalog(too_many_types)

        too_large = taxonomy.default_catalog()
        too_large["types"].append({
            "id": "custom_large", "label": "Large", "enabled": True,
            "role": "custom_manual", "extraction_mode": "manual_only",
            "fields": [{
                "id": f"custom_field_{index:03d}", "label": "x" * 80, "value_kind": "text",
                "required": False, "review_only": True, "extraction_mode": "manual_only",
            } for index in range(128)],
        })
        too_large["types"].extend(copy.deepcopy(too_large["types"][-1:]) * 2)
        with self.assertRaises(taxonomy.TaxonomyError) as caught:
            taxonomy.validate_catalog(too_large)
        self.assertEqual(caught.exception.code, "taxonomy_catalog_too_large")

    def test_catalog_update_is_immutable_and_rejects_stale_writer(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = taxonomy.TaxonomyStore(temporary)
            original, original_hash = store.get_current()
            updated = copy.deepcopy(original)
            updated["version"] += 1
            next(item for item in updated["types"] if item["id"] == "invoice")["label"] = "Fattura documento"
            saved, saved_hash = store.save_catalog(
                updated, expected_version=original["version"], expected_sha256=original_hash,
            )
            self.assertEqual(saved["version"], original["version"] + 1)
            self.assertEqual(store.get_version(original["version"]), (original, original_hash))
            self.assertEqual(store.get_current(), (saved, saved_hash))
            with self.assertRaises(taxonomy.TaxonomyConflict):
                store.save_catalog(updated, expected_version=original["version"], expected_sha256=original_hash)
            self.assertEqual(store.get_current(), (saved, saved_hash))

    def test_invalid_update_preserves_current_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = taxonomy.TaxonomyStore(temporary)
            current = store.get_current()
            invalid = copy.deepcopy(current[0])
            invalid["version"] += 1
            invalid["execute"] = "no"
            with self.assertRaises(taxonomy.TaxonomyError):
                store.save_catalog(invalid, expected_version=current[0]["version"], expected_sha256=current[1])
            self.assertEqual(store.get_current(), current)
            self.assertIsNone(store.get_version(current[0]["version"] + 1))

    def test_transaction_failure_rolls_back_and_preserves_current(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = taxonomy.TaxonomyStore(temporary)
            current = store.get_current()
            updated = copy.deepcopy(current[0])
            updated["version"] += 1
            next(item for item in updated["types"] if item["id"] == "invoice")["label"] = "Fattura nuova"
            store._before_commit = lambda: (_ for _ in ()).throw(RuntimeError("injected"))
            with self.assertRaises(taxonomy.TaxonomyError):
                store.save_catalog(updated, expected_version=current[0]["version"], expected_sha256=current[1])
            reopened = taxonomy.TaxonomyStore(temporary)
            self.assertEqual(reopened.get_current(), current)
            self.assertIsNone(reopened.get_version(current[0]["version"] + 1))

    def test_corrupt_catalog_fails_closed_without_repair(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = taxonomy.TaxonomyStore(temporary)
            db_path = Path(temporary) / taxonomy.DATABASE_NAME
            connection = sqlite3.connect(db_path)
            try:
                connection.execute("UPDATE taxonomy_versions SET catalog_sha256=? WHERE version=1", ("0" * 64,))
                connection.commit()
            finally:
                connection.close()
            before = db_path.read_bytes()
            with self.assertRaises(taxonomy.TaxonomyError) as caught:
                taxonomy.TaxonomyStore(temporary)
            self.assertEqual(caught.exception.code, "taxonomy_catalog_corrupt")
            self.assertEqual(db_path.read_bytes(), before)

    def test_huge_persisted_current_version_fails_closed_without_large_range(self):
        with tempfile.TemporaryDirectory() as temporary:
            taxonomy.TaxonomyStore(temporary)
            db_path = Path(temporary) / taxonomy.DATABASE_NAME
            connection = sqlite3.connect(db_path)
            try:
                connection.execute(
                    "UPDATE taxonomy_metadata SET value=? WHERE key='current_version'",
                    (str(taxonomy.MAX_CATALOG_VERSION + 1),),
                )
                connection.commit()
            finally:
                connection.close()
            before = db_path.read_bytes()
            with self.assertRaises(taxonomy.TaxonomyError) as caught:
                taxonomy.TaxonomyStore(temporary)
            self.assertEqual(caught.exception.code, "taxonomy_store_corrupt")
            self.assertEqual(db_path.read_bytes(), before)

if __name__ == "__main__":
    unittest.main()
