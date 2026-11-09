"""Synthetic contracts for catalog aliases ending in delimiters."""
from copy import deepcopy
import hashlib
import json
import unittest
from alfa_document_intelligence.analysis_pipeline import analyze_ocr_results
from alfa_document_intelligence.contracts import validate_document_record
from alfa_document_intelligence.semantic_proposals import propose_common_fields
from test_catalog_pipeline import _catalog, _document, _family, _page, POLYGON, SOURCE_HASH


def family(family_id, fields):
    result = _family(family_id)
    result['title_cues'] = ['TITLE ' + family_id]
    result['fields'] = [dict(id=name, label=name, aliases=aliases) for name, aliases in fields]
    return result


class CatalogAliasDelimiterTests(unittest.TestCase):
    def test_delimited_alias_evidence_and_snapshot(self):
        for version in ('1', '2'):
            for delimiter in (':', '='):
                with self.subTest(version=version, delimiter=delimiter):
                    catalog = _catalog(family('custom_date', [('date', ['Data' + delimiter])]), version=version)
                    doc = _document()
                    original = deepcopy(doc)
                    page = _page('Data' + delimiter + ' Roma')
                    result = analyze_ocr_results(doc, [page], custom_family_catalog=catalog).document
                    self.assertEqual(doc, original)
                    candidate = result['fields']['custom_date_date']
                    self.assertIsNone(candidate['value'])
                    self.assertEqual(candidate['status'], 'uncertain')
                    self.assertEqual([a['value'] for a in candidate['alternatives']], ['Roma'])
                    evidence = candidate['alternatives'][0]['evidence'][0]
                    self.assertEqual(candidate['evidence'], [evidence])
                    self.assertEqual(evidence['source_sha256'], SOURCE_HASH)
                    self.assertEqual(evidence['page_number'], 1)
                    self.assertEqual(evidence['token_ids'], ['token-0'])
                    self.assertEqual(evidence['literal'], page.tokens[0].text)
                    self.assertEqual(evidence['region']['polygon'], [list(p) for p in POLYGON])
                    self.assertEqual(result['document_family_definitions'], [catalog.snapshot_for('custom_date')])
                    snapshot = result['document_family_definitions'][0]
                    canonical = json.dumps(snapshot['family'], ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
                    self.assertEqual(snapshot['family_sha256'], hashlib.sha256(canonical).hexdigest())
                    self.assertEqual(validate_document_record(result), [])

    def test_delimited_alias_whitespace_case_and_snapshot_hash(self):
        for version in ('1', '2'):
            for alias, text in [('Data :', 'data : Roma'), ('Data =', 'DATA = Roma')]:
                with self.subTest(version=version, alias=alias):
                    catalog = _catalog(family('custom_date', [('date', [alias])]), version=version)
                    snapshot = deepcopy(catalog.snapshot_for('custom_date'))
                    result = analyze_ocr_results(_document(), [_page(text)], custom_family_catalog=catalog).document
                    self.assertEqual(result['fields']['custom_date_date']['alternatives'][0]['value'], 'Roma')
                    self.assertEqual(result['document_family_definitions'], [snapshot])
                    canonical = json.dumps(snapshot['family'], ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
                    self.assertEqual(snapshot['family_sha256'], hashlib.sha256(canonical).hexdigest())
                    self.assertEqual(catalog.snapshot_for('custom_date'), snapshot)

    def test_legacy_ambiguity_without_new_match_is_preserved(self):
        catalog = _catalog(family('custom_alpha', [('date', ['Data'])]), family('custom_beta', [('date', ['Data'])]))
        result = propose_common_fields([_page('Data: Roma')], custom_family_catalog=catalog)
        for name in ('custom_alpha_date', 'custom_beta_date'):
            self.assertEqual(result[name]['alternatives'][0]['value'], 'Roma')

    def test_two_distinct_keys_in_one_token_suppress_ambiguous_new_match(self):
        catalog = _catalog(family('custom_alpha', [('first', ['Data:'])]), family('custom_beta', [('second', ['Data: Roma'])]))
        result = propose_common_fields([_page('Data: Roma=Milano')], custom_family_catalog=catalog)
        self.assertNotIn('custom_alpha_first', result)
        self.assertNotIn('custom_beta_second', result)

    def test_delimiter_must_match_exactly_and_not_repeat(self):
        for alias, text in [('Data:', 'Data= Roma'), ('Data=', 'Data: Roma'), ('Data:', 'Data:: Roma'), ('Data=', 'Data== Roma')]:
            with self.subTest(alias=alias, text=text):
                catalog = _catalog(family('custom_date', [('date', [alias])]))
                self.assertNotIn('custom_date_date', propose_common_fields([_page(text)], custom_family_catalog=catalog))

    def test_existing_cross_delimiter_matches_take_legacy_precedence(self):
        for alias, text in [('Data:', 'Data:=foo'), ('Data=', 'Data=:foo')]:
            with self.subTest(alias=alias, text=text):
                catalog = _catalog(family('custom_date', [('date', [alias])]))
                result = propose_common_fields([_page(text)], custom_family_catalog=catalog)
                self.assertEqual(result['custom_date_date']['alternatives'][0]['value'], 'foo')

    def test_legacy_long_alias_and_new_delimited_alias_collision(self):
        catalog = _catalog(family('custom_alpha', [('legacy', ['Data: foo']), ('new', ['Data:'])]))
        result = propose_common_fields([_page('Data: foo=bar')], custom_family_catalog=catalog)
        self.assertNotIn('custom_alpha_legacy', result)
        self.assertNotIn('custom_alpha_new', result)

    def test_plain_alias_legacy_and_same_field_deduplication(self):
        plain = _catalog(family('custom_date', [('date', ['Data'])]))
        combined = _catalog(family('custom_date', [('date', ['Data', 'Data:'])]))
        for text in ('Data: Roma', 'Data= Roma'):
            with self.subTest(text=text):
                before = propose_common_fields([_page(text)], custom_family_catalog=plain)
                after = propose_common_fields([_page(text)], custom_family_catalog=combined)
                self.assertEqual(before['custom_date_date'], after['custom_date_date'])
                self.assertEqual(len(after['custom_date_date']['alternatives']), 1)

    def test_plain_and_delimited_collision_suppresses_both(self):
        for same_family in (True, False):
            with self.subTest(same_family=same_family):
                if same_family:
                    definitions = [family('custom_alpha', [('plain', ['Data']), ('punct', ['Data:'])])]
                    names = ('custom_alpha_plain', 'custom_alpha_punct')
                else:
                    definitions = [family('custom_alpha', [('plain', ['Data'])]), family('custom_beta', [('punct', ['Data:'])])]
                    names = ('custom_alpha_plain', 'custom_beta_punct')
                catalog = _catalog(*definitions)
                result = propose_common_fields([_page('Data: Roma')], custom_family_catalog=catalog)
                for name in names:
                    self.assertNotIn(name, result)
                legacy = propose_common_fields([_page('Data= Roma')], custom_family_catalog=catalog)
                self.assertEqual(legacy[names[0]]['alternatives'][0]['value'], 'Roma')
                self.assertNotIn(names[1], legacy)

    def test_two_delimited_aliases_across_families_suppress_both(self):
        catalog = _catalog(family('custom_alpha', [('date', ['Data:'])]), family('custom_beta', [('date', ['Data:'])]))
        result = propose_common_fields([_page('Data: Roma')], custom_family_catalog=catalog)
        self.assertNotIn('custom_alpha_date', result)
        self.assertNotIn('custom_beta_date', result)
