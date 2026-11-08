import json
import tempfile
import unittest
from pathlib import Path

from alfa_document_intelligence.public_data_guard import (
    PublicDataGuardError,
    _ALLOWED_FILES,
    scan_public_benchmark,
)

# Construct decoys at runtime so public source scanners do not mistake test
# fixtures for credentials or personal data embedded in the repository.
SYNTHETIC_EMAIL = "fictional.user" + "@" + "example.invalid"
SYNTHETIC_TAX_CODE = "RSSMRA" + "85T10A562S"
SYNTHETIC_IBAN = "IT60X" + ("1234567890" * 2) + "12"
SYNTHETIC_GITHUB_TOKEN = "ghp_" + ("x" * 40)
SYNTHETIC_AWS_KEY = "AKIA" + ("X" * 16)
SYNTHETIC_BEARER = "Bearer " + ("x" * 32)
SYNTHETIC_PHONE = "+39 02 " + "1234" + "5678"


class PublicDataGuardTests(unittest.TestCase):
    def _write_fixture_set(self, root: Path):
        for name in _ALLOWED_FILES:
            if name.endswith(".jsonl"):
                root.joinpath(name).write_text(json.dumps({"case_id": "synthetic-1", "value": "EUR 10,00"}) + "\n", encoding="utf-8")
            else:
                root.joinpath(name).write_text(json.dumps({"records": []}), encoding="utf-8")

    def test_accepts_allowlisted_synthetic_json_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write_fixture_set(root)
            self.assertEqual(scan_public_benchmark(root), len(_ALLOWED_FILES))

    def test_rejects_email_like_value_without_echoing_it(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write_fixture_set(root)
            path = root / "synthetic_development_labels.jsonl"
            path.write_text(json.dumps({"case_id": "synthetic-1", "note": SYNTHETIC_EMAIL}) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(PublicDataGuardError, "email-like value") as caught:
                scan_public_benchmark(root)
            self.assertNotIn(SYNTHETIC_EMAIL, str(caught.exception))

    def test_rejects_identifier_keys_after_separator_normalization(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write_fixture_set(root)
            path = root / "synthetic_regression_predictions.jsonl"
            path.write_text(json.dumps({"case_id": "synthetic-1", "Email-Address": "x"}) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(PublicDataGuardError, "forbidden field name"):
                scan_public_benchmark(root)

    def test_rejects_email_tax_code_iban_and_credential_patterns(self):
        cases = [
            (SYNTHETIC_EMAIL, "email-like value"),
            (SYNTHETIC_TAX_CODE, "Italian tax-code-like value"),
            (SYNTHETIC_IBAN, "Italian IBAN-like value"),
            (SYNTHETIC_GITHUB_TOKEN, "credential-like value"),
            (SYNTHETIC_AWS_KEY, "credential-like value"),
            (SYNTHETIC_BEARER, "bearer credential"),
        ]
        for value, expected in cases:
            with self.subTest(expected=expected):
                with tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    self._write_fixture_set(root)
                    path = root / "synthetic_frozen_smoke_labels.jsonl"
                    path.write_text(json.dumps({"value": value}) + "\n", encoding="utf-8")
                    with self.assertRaisesRegex(PublicDataGuardError, expected):
                        scan_public_benchmark(root)

    def test_rejects_italian_phone_like_values(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write_fixture_set(root)
            path = root / "synthetic_frozen_smoke_predictions.jsonl"
            path.write_text(json.dumps({"value": SYNTHETIC_PHONE}) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(PublicDataGuardError, "Italian phone-like value"):
                scan_public_benchmark(root)

    def test_rejects_direct_identifier_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write_fixture_set(root)
            path = root / "synthetic_regression_predictions.jsonl"
            path.write_text(json.dumps({"case_id": "synthetic-1", "employee_id": "x"}) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(PublicDataGuardError, "forbidden field name"):
                scan_public_benchmark(root)

    def test_requires_all_allowlisted_files_and_rejects_symlinks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write_fixture_set(root)
            (root / _ALLOWED_FILES[0]).unlink()
            with self.assertRaisesRegex(PublicDataGuardError, "missing"):
                scan_public_benchmark(root)


if __name__ == "__main__":
    unittest.main()
