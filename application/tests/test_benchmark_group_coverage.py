"""Synthetic coverage and privacy checks for benchmark manifest validation."""

import copy
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from alfa_document_intelligence.benchmark_manifest import main, validate_manifest


def _manifest(groups):
    splits = ("development", "regression", "independent_frozen", "independent_frozen")
    return {
        "manifest_version": "1",
        "records": [
            {
                "case_id": f"synthetic-{index}",
                "sha256": hashlib.sha256(f"document-{index}".encode()).hexdigest(),
                "split": split,
                "document_family": "invoice",
                "language": "it",
                "label_version": "synthetic-1",
                "group_keys": keys,
            }
            for index, (split, keys) in enumerate(zip(splits, groups))
        ],
    }


def _key(index):
    return hashlib.sha256(f"synthetic-group-{index}".encode()).hexdigest()


class GroupKeyCoverageTests(unittest.TestCase):
    def test_coverage_counts_records_not_individual_keys(self):
        cases = (
            ([[], [], [], []], 0, 4),
            ([[_key(0), _key(1)], [], [_key(2)], []], 2, 2),
            ([[_key(0)], [_key(1)], [_key(2)], [_key(3)]], 4, 0),
        )
        for groups, with_keys, without_keys in cases:
            with self.subTest(with_keys=with_keys):
                result = validate_manifest(_manifest(groups))
                self.assertEqual(result["records"], 4)
                self.assertEqual(result["split_counts"], {
                    "development": 1, "regression": 1, "independent_frozen": 2,
                })
                self.assertEqual(result["group_key_coverage"], {
                    "records_with_keys": with_keys,
                    "records_without_keys": without_keys,
                    "interpretation": "provided_keys_only",
                })
                for key in (key for keys in groups for key in keys):
                    self.assertNotIn(key, json.dumps(result))

    def test_frozen_digest_is_deterministic_and_pinnable(self):
        manifest = _manifest([[_key(0)], [], [_key(2)], [_key(3)]])
        frozen = sorted(
            (row for row in manifest["records"] if row["split"] == "independent_frozen"),
            key=lambda row: row["case_id"],
        )
        expected = hashlib.sha256(json.dumps(
            frozen, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest()
        original = validate_manifest(manifest, expected)
        reordered = copy.deepcopy(manifest)
        reordered["records"].reverse()
        self.assertEqual(original["frozen_manifest_sha256"], expected)
        self.assertEqual(validate_manifest(reordered, expected)["frozen_manifest_sha256"], expected)

    def test_same_group_across_splits_is_rejected_without_leaking_key(self):
        key = _key(0)
        with self.assertRaisesRegex(ValueError, "cross benchmark splits") as error:
            validate_manifest(_manifest([[key], [key], [], []]))
        self.assertNotIn(key, str(error.exception))

    def test_cli_reports_coverage_without_group_keys(self):
        key = _key(0)
        manifest = _manifest([[key], [], [], []])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            output = io.StringIO()
            with patch("sys.argv", ["benchmark_manifest", "--manifest", str(path)]), patch("sys.stdout", output):
                main()
        result = json.loads(output.getvalue())
        self.assertEqual(result["group_key_coverage"], {
            "records_with_keys": 1,
            "records_without_keys": 3,
            "interpretation": "provided_keys_only",
        })
        self.assertNotIn(key, output.getvalue())


if __name__ == "__main__":
    unittest.main()
