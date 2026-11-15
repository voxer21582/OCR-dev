from __future__ import annotations

import copy
import unittest

from alfa_document_intelligence import taxonomy_registry
from alfa_document_intelligence.taxonomy_binding import (
    TaxonomyBindingError,
    bind_document_record,
    create_taxonomy_binding,
    validate_taxonomy_binding,
)


class TaxonomyBindingTests(unittest.TestCase):
    def test_binding_preserves_canonical_snapshot_and_is_defensive(self):
        catalog = taxonomy_registry.default_catalog()
        canonical, digest = taxonomy_registry.validate_catalog(catalog)
        before = copy.deepcopy(catalog)

        binding = create_taxonomy_binding(catalog, digest)
        snapshot, actual_digest = validate_taxonomy_binding(binding)

        self.assertEqual(catalog, before)
        self.assertEqual(snapshot, catalog)
        self.assertEqual(actual_digest, digest)
        self.assertEqual(binding["catalog_sha256"], digest)
        snapshot["types"][0]["label"] = "mutated caller copy"
        reopened_snapshot, reopened_digest = validate_taxonomy_binding(binding)
        self.assertEqual(reopened_digest, digest)
        self.assertEqual(reopened_snapshot, catalog)

        unbound_record = {"schema_version": "0.1.0"}
        bound_v1_record = bind_document_record(unbound_record, binding)
        self.assertEqual(bound_v1_record["schema_version"], "0.2.0")
        self.assertEqual(bound_v1_record["taxonomy_binding"], binding)
        self.assertEqual(unbound_record, {"schema_version": "0.1.0"})

        # Rebinding an identical valid snapshot is idempotent, but a bound
        # record must never be silently reassigned to another taxonomy.
        bound_v1_before_rebind = copy.deepcopy(bound_v1_record)
        self.assertEqual(bind_document_record(bound_v1_record, binding), bound_v1_record)
        self.assertEqual(bound_v1_record, bound_v1_before_rebind)
        changed_catalog = copy.deepcopy(catalog)
        changed_catalog["types"][0]["label"] += " changed"
        _canonical, changed_digest = taxonomy_registry.validate_catalog(changed_catalog)
        changed_binding = create_taxonomy_binding(changed_catalog, changed_digest)
        malformed_record = copy.deepcopy(bound_v1_record)
        malformed_record["taxonomy_binding"]["catalog_sha256"] = "0" * 64
        malformed_record_before_rebind = copy.deepcopy(malformed_record)
        for existing_record, requested_binding in (
            (bound_v1_record, changed_binding),
            (malformed_record, binding),
        ):
            with self.subTest(existing_record=existing_record, requested_binding=requested_binding):
                with self.assertRaises(TaxonomyBindingError):
                    bind_document_record(existing_record, requested_binding)
        self.assertEqual(bound_v1_record, bound_v1_before_rebind)
        self.assertEqual(malformed_record, malformed_record_before_rebind)
        self.assertEqual(unbound_record, {"schema_version": "0.1.0"})

        # Catalog schema generation is independent of its consecutive revision.
        # This v2 snapshot represents revision 2 after a synthetic v1 upgrade.
        catalog_v2 = taxonomy_registry.default_catalog_v2()
        catalog_v2["version"] = 2
        canonical_v2, digest_v2 = taxonomy_registry.validate_catalog(catalog_v2)
        binding_v2 = create_taxonomy_binding(catalog_v2, digest_v2)
        reopened_v2, reopened_v2_digest = validate_taxonomy_binding(binding_v2)

        self.assertEqual(binding_v2["schema_version"], binding["schema_version"])
        self.assertEqual(binding_v2["catalog_schema_version"], "2.0.0")
        self.assertEqual(binding_v2["catalog_version"], 2)
        self.assertEqual(binding_v2["snapshot"], catalog_v2)
        self.assertEqual(reopened_v2, catalog_v2)
        self.assertEqual(reopened_v2_digest, digest_v2)
        self.assertEqual(binding_v2["catalog_sha256"], digest_v2)
        self.assertEqual(canonical_v2.encode("utf-8"), taxonomy_registry.canonical_json(catalog_v2).encode("utf-8"))
        bound_v2_record = bind_document_record(unbound_record, binding_v2)
        self.assertEqual(bound_v2_record["schema_version"], "0.3.0")
        self.assertEqual(bound_v2_record["taxonomy_binding"], binding_v2)
        self.assertEqual(unbound_record, {"schema_version": "0.1.0"})

    def test_binding_rejects_digest_version_schema_and_unknown_key_mismatch(self):
        catalog = taxonomy_registry.default_catalog()
        _canonical, digest = taxonomy_registry.validate_catalog(catalog)
        binding = create_taxonomy_binding(catalog, digest)

        invalid_bindings = []
        for key, value in (
            ("catalog_sha256", "0" * 64),
            ("catalog_version", 2),
            ("catalog_schema_version", "999.0.0"),
            ("unexpected", True),
        ):
            invalid = copy.deepcopy(binding)
            invalid[key] = value
            invalid_bindings.append(invalid)

        for invalid in invalid_bindings:
            with self.subTest(binding=invalid):
                with self.assertRaises(TaxonomyBindingError):
                    validate_taxonomy_binding(invalid)

        catalog_v2 = taxonomy_registry.default_catalog_v2()
        _canonical, digest_v2 = taxonomy_registry.validate_catalog(catalog_v2)
        binding_v2 = create_taxonomy_binding(catalog_v2, digest_v2)
        invalid_v2_bindings = []
        for key, value in (
            ("catalog_sha256", "0" * 64),
            ("catalog_version", 2),
            ("catalog_schema_version", "3.0.0"),
            ("unexpected", True),
        ):
            invalid = copy.deepcopy(binding_v2)
            invalid[key] = value
            invalid_v2_bindings.append(invalid)
        unknown_generation = copy.deepcopy(binding_v2)
        unknown_generation["catalog_schema_version"] = "3.0.0"
        unknown_generation["snapshot"]["schema_version"] = "3.0.0"
        unknown_generation["catalog_sha256"] = taxonomy_registry.catalog_sha256(
            unknown_generation["snapshot"]
        )
        invalid_v2_bindings.append(unknown_generation)

        for invalid in invalid_v2_bindings:
            with self.subTest(v2_binding=invalid):
                with self.assertRaises(TaxonomyBindingError):
                    validate_taxonomy_binding(invalid)

    def test_binding_rejects_snapshot_over_catalog_limit(self):
        catalog = taxonomy_registry.default_catalog()
        for type_index in range(56):
            catalog["types"].append({
                "id": f"custom_type_{type_index:03d}", "label": "x" * 80,
                "enabled": True, "role": "custom_manual", "extraction_mode": "manual_only",
                "fields": [{
                    "id": f"custom_field_{field_index:03d}", "label": "y" * 80,
                    "value_kind": "text", "required": False,
                    "review_only": True, "extraction_mode": "manual_only",
                } for field_index in range(128)],
            })

        with self.assertRaises(TaxonomyBindingError):
            create_taxonomy_binding(catalog, "0" * 64)


if __name__ == "__main__":
    unittest.main()
