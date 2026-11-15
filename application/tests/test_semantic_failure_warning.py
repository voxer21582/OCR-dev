import json
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

from alfa_document_intelligence.review_ui import _render_record, create_review_app


FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_invoice.json"
OVERFLOW_CODES = (
    "semantic_proposal_field_limit",
    "semantic_proposal_catalog_limit",
    "semantic_proposal_family_limit",
)
UNKNOWN_CODES = (None, "semantic_extraction_failed", "unrecognized_synthetic_code", '<script>alert("synthetic")</script>')


class TextExtractor(HTMLParser):
    """Extract document text, excluding script/style; does not evaluate CSS visibility."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ignored = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.ignored += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.ignored:
            self.ignored -= 1

    def handle_data(self, data):
        if not self.ignored:
            self.parts.append(data)


def document_text(html):
    parser = TextExtractor()
    parser.feed(html)
    return re.sub(r"\s+", " ", " ".join(parser.parts)).lower()


class SemanticFailureWarningTests(unittest.TestCase):
    def render(self, status, code=None):
        record = json.loads(FIXTURE.read_text(encoding="utf-8"))
        record["processing"]["semantic_extraction"] = {"status": status}
        if code is not None:
            record["processing"]["semantic_extraction"]["error_code"] = code
        record["fields"]["merchant_name"]["value"] = "<img src=x onerror=alert(1)>"
        html = _render_record(record, has_source=False, key="synthetic")
        return html, document_text(html)

    def assert_failure_warning(self, text):
        self.assertIn("estrazione automatica non completata", text)
        self.assertRegex(text, r"verific\w*\s+manual\w*|verific\w*\s+manualmente")

    def test_known_overflows_explain_limit(self):
        for code in OVERFLOW_CODES:
            with self.subTest(code=code):
                _, text = self.render("failed", code)
                self.assert_failure_warning(text)
                self.assertRegex(text, r"limite.{0,100}raggiunt|raggiunt.{0,100}limite")

    def test_unknown_and_missing_codes_have_generic_warning(self):
        for code in UNKNOWN_CODES:
            with self.subTest(code=code):
                _, text = self.render("failed", code)
                self.assert_failure_warning(text)

    def test_unknown_codes_are_not_reflected(self):
        for code in UNKNOWN_CODES[1:]:
            with self.subTest(code=code):
                html, text = self.render("failed", code)
                self.assertNotIn(code, html)
                self.assertNotIn(code, text)

    def test_existing_fields_and_escaping_are_preserved(self):
        html, text = self.render("failed", OVERFLOW_CODES[0])
        self.assertNotIn("nessun campo estratto", text)
        self.assertIn("merchant_name", html)
        self.assertIn("&lt;img", html)
        self.assertNotIn("<img", html)

    def test_nonfailed_stages_have_no_failure_warning(self):
        for status in ("completed", "not_started", "in_progress", "skipped"):
            with self.subTest(status=status):
                _, text = self.render(status)
                self.assertNotIn("estrazione automatica non completata", text)

    def test_malformed_semantic_stage_shows_unknown_manual_review_warning(self):
        malformed_stages = (
            ["synthetic malformed stage"],
            {},
            {"status": "unsupported_synthetic_status"},
            {"status": ["failed"]},
        )
        for stage in malformed_stages:
            with self.subTest(stage=stage):
                record = json.loads(FIXTURE.read_text(encoding="utf-8"))
                record["processing"]["semantic_extraction"] = stage
                app = create_review_app({record["document_id"]: record})
                captured = {}

                def start_response(status, headers):
                    captured["status"] = status

                body = b"".join(app({
                    "REQUEST_METHOD": "GET",
                    "PATH_INFO": "/reviews/" + record["document_id"],
                    "QUERY_STRING": "",
                }, start_response))
                text = document_text(body.decode("utf-8"))

                self.assertEqual(captured["status"], "200 OK")
                self.assertIn("stato estrazione automatica non disponibile", text)
                self.assertIn("verifica manuale", text)


if __name__ == "__main__":
    unittest.main()
