"""Required custom fields follow selected families in synthetic records."""
from copy import deepcopy
import unittest

from alfa_document_intelligence.analysis_pipeline import analyze_ocr_results
from alfa_document_intelligence.contracts import validate_document_record
from alfa_document_intelligence.document_validation import validate_document_consistency
from test_catalog_pipeline import FAMILY_ID, FIELD_NAME, _catalog, _document, _family, _page


class RequiredCustomSelectionTests(unittest.TestCase):
    def setUp(self):
        self.record = analyze_ocr_results(
            _document(), [_page('RICEVUTA TAXI')],
            custom_family_catalog=_catalog(_family(required=True), version='2'),
        ).document

    def check_findings(self, expected):
        self.assertEqual(validate_document_record(self.record), [])
        before = deepcopy(self.record)
        findings = validate_document_consistency(self.record)
        self.assertEqual(self.record, before)
        self.assertEqual([f['message_code'] for f in findings], expected)
        if expected:
            self.assertEqual(findings[0]['field_names'], [FIELD_NAME])
            self.assertEqual(findings[0]['severity'], 'warning')
            self.assertEqual(findings[0]['outcome'], 'indeterminate')
            self.assertEqual(findings[0]['evidence'], [])

    def test_root_custom_without_candidate_requires_missing_field(self):
        self.record['document_family'] = FAMILY_ID
        del self.record['fields']['document_family_candidates']
        self.check_findings(['required_custom_field_missing'])

    def test_observed_custom_candidate_requires_missing_field(self):
        candidate = self.record['fields']['document_family_candidates']
        candidate['value'] = FAMILY_ID
        candidate['status'] = 'observed'
        candidate['alternatives'] = []
        self.check_findings(['required_custom_field_missing'])

    def test_observed_required_field_removes_warning(self):
        self.record['document_family'] = FAMILY_ID
        candidate = self.record['fields']['document_family_candidates']
        candidate['value'] = FAMILY_ID
        candidate['status'] = 'observed'
        candidate['alternatives'] = []
        field = self.record['fields'][FIELD_NAME]
        field.update(value='Roma', status='observed', alternatives=[], evidence=deepcopy(candidate['evidence']))
        self.check_findings([])

    def test_builtin_without_custom_selection_has_no_warning(self):
        self.record['document_family'] = 'invoice'
        del self.record['fields']['document_family_candidates']
        self.check_findings([])

    def test_unknown_without_custom_selection_has_no_warning(self):
        del self.record['fields']['document_family_candidates']
        self.check_findings([])

    def test_non_observed_primary_custom_does_not_activate_family(self):
        candidate = self.record['fields']['document_family_candidates']
        for status in ('uncertain', 'rejected'):
            with self.subTest(status=status):
                candidate.update(value=FAMILY_ID, status=status, alternatives=[])
                self.check_findings([])

    def test_duplicate_custom_selections_produce_one_warning(self):
        self.record['document_family'] = FAMILY_ID
        candidate = self.record['fields']['document_family_candidates']
        candidate.update(value=FAMILY_ID, status='observed')
        self.check_findings(['required_custom_field_missing'])


if __name__ == '__main__':
    unittest.main()
