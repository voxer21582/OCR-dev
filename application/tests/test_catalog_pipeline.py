"""Synthetic catalog propagation contracts; no runtime or native decoder calls."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from alfa_document_intelligence.analysis_pipeline import AnalysisPipelineError, analyze_ocr_results
from alfa_document_intelligence.contracts import validate_document_record
from alfa_document_intelligence.document_family_catalog import (
    DocumentFamilyCatalogError,
    load_custom_family_catalog,
)
from alfa_document_intelligence.document_validation import validate_document_consistency
from alfa_document_intelligence.ocr_adapter import OCRPageResult, OCRToken
from alfa_document_intelligence.semantic_proposals import SemanticProposalError, propose_common_fields


POLYGON = ((0.1, 0.1), (0.8, 0.1), (0.8, 0.2), (0.1, 0.2))
SOURCE_HASH = "a" * 64
FAMILY_ID = "custom_taxi_receipt"
FIELD_NAME = FAMILY_ID + "_pickup_city"


def _family(family_id=FAMILY_ID, *, alias="Partenza", required=False):
    field = {"id": "pickup_city", "label": "Citta di partenza", "aliases": [alias]}
    if required:
        field["required"] = True
    return {
        "id": family_id,
        "label": "Ricevuta taxi",
        "title_cues": ["RICEVUTA TAXI"],
        "fields": [field],
    }


def _catalog(*families, version="1"):
    return load_custom_family_catalog(json.dumps({
        "catalog_version": version,
        "families": list(families),
    }, ensure_ascii=False))


def _page(*texts, source_hash=SOURCE_HASH, page_number=1):
    return OCRPageResult(
        source_hash, page_number, "synthetic-ocr", "test-1", "it+en",
        tuple(OCRToken(f"token-{index}", text, POLYGON) for index, text in enumerate(texts)),
    )


def _document():
    path = Path(__file__).parent / "fixtures" / "synthetic_invoice.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["document_family"] = "unknown"
    document["fields"] = {}
    document["processing"]["ocr"]["status"] = "completed"
    return document


class CatalogSemanticProposalTests(unittest.TestCase):
    def test_literal_custom_aliases_keep_uncertain_alternatives_and_evidence(self):
        catalog = _catalog(_family())
        page = _page("RICEVUTA TAXI", "Partenza: Milano", "Partenza: Roma")
        fields = propose_common_fields([page], custom_family_catalog=catalog)
        candidate = fields[FIELD_NAME]
        self.assertIsNone(candidate["value"])
        self.assertEqual(candidate["status"], "uncertain")
        self.assertEqual([item["value"] for item in candidate["alternatives"]], ["Milano", "Roma"])
        for index, alternative in enumerate(candidate["alternatives"], 1):
            evidence = alternative["evidence"][0]
            self.assertEqual(evidence, candidate["evidence"][index - 1])
            self.assertEqual(evidence["source_sha256"], SOURCE_HASH)
            self.assertEqual(evidence["page_number"], 1)
            self.assertEqual(evidence["token_ids"], [f"token-{index}"])
            self.assertEqual(evidence["literal"], page.tokens[index].text)
            self.assertEqual(evidence["region"]["polygon"], [list(point) for point in POLYGON])
            self.assertEqual(evidence["producer"], {
                "stage": "ocr", "name": "synthetic-ocr", "version": "test-1",
            })
        literal_catalog = _catalog(_family(alias="Partenza [A+]"))
        for texts, expected in (
            (("Partenza [A+]: Milano",), "Milano"),
            (("Partenza AAAAA: Milano",), None),
            (("Partenza [A+]:", "Milano"), None),
        ):
            with self.subTest(texts=texts):
                result = propose_common_fields([_page(*texts)], custom_family_catalog=literal_catalog)
                if expected is None:
                    self.assertNotIn(FIELD_NAME, result)
                else:
                    self.assertEqual(result[FIELD_NAME]["alternatives"][0]["value"], expected)

    def test_builtin_and_custom_family_cues_preserve_both_alternatives(self):
        fields = propose_common_fields(
            [_page("INVOICE", "RICEVUTA TAXI")], custom_family_catalog=_catalog(_family())
        )
        candidate = fields["document_family_candidates"]
        self.assertIsNone(candidate["value"])
        self.assertEqual(candidate["status"], "uncertain")
        alternatives = candidate["alternatives"]
        self.assertEqual([item["value"] for item in alternatives], ["invoice", FAMILY_ID])
        self.assertEqual(alternatives[0]["normalization"]["original_literal"], "INVOICE")
        self.assertEqual([item["literal"] for item in candidate["evidence"]], ["INVOICE", "RICEVUTA TAXI"])
        for alternative, evidence in zip(alternatives, candidate["evidence"]):
            self.assertEqual(alternative["status"], "observed")
            self.assertEqual(alternative["evidence"], [evidence])
        self.assertNotIn("document_family", fields)
        self.assertNotIn("fiscal_document_state", fields)

    def test_combined_family_candidate_limit(self):
        catalog = _catalog(_family())
        with self.subTest(combined_count=100):
            result = propose_common_fields(
                [_page(*(["INVOICE"] * 99 + ["RICEVUTA TAXI"]))], custom_family_catalog=catalog
            )
            self.assertEqual(len(result["document_family_candidates"]["alternatives"]), 100)
        with self.subTest(combined_count=101):
            with self.assertRaises(SemanticProposalError):
                propose_common_fields(
                    [_page(*(["INVOICE"] * 100 + ["RICEVUTA TAXI"]))], custom_family_catalog=catalog
                )

    def test_catalog_proposal_failure_is_wrapped(self):
        with patch(
            "alfa_document_intelligence.semantic_proposals.build_custom_family_proposals",
            side_effect=DocumentFamilyCatalogError("synthetic internal detail"),
            create=True,
        ):
            with self.assertRaises(SemanticProposalError) as caught:
                propose_common_fields([_page("RICEVUTA TAXI")], custom_family_catalog=_catalog(_family()))
        self.assertNotIn("synthetic internal detail", str(caught.exception))

class CatalogAnalysisPipelineTests(unittest.TestCase):
    def test_custom_snapshot_and_fields_are_bound_to_exact_catalog(self):
        for version in ('1', '2'):
            with self.subTest(version=version):
                catalog = _catalog(_family(required=version == '2'), version=version)
                document = _document(); original = deepcopy(document)
                result = analyze_ocr_results(document, [_page('RICEVUTA TAXI', 'Partenza: Roma')], custom_family_catalog=catalog).document
                self.assertEqual(document, original)
                for key in ('document_family', 'fiscal_document_state'):
                    self.assertEqual(result[key], original[key])
                self.assertEqual(result['processing']['administrative_verification'], original['processing']['administrative_verification'])
                self.assertEqual(result['document_family_definitions'], [catalog.snapshot_for(FAMILY_ID)])
                snapshot = result['document_family_definitions'][0]
                canonical = json.dumps(snapshot['family'], ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
                self.assertEqual(snapshot['family_sha256'], hashlib.sha256(canonical).hexdigest())
                self.assertEqual(result['fields'][FIELD_NAME]['status'], 'uncertain')
                self.assertEqual(validate_document_record(result), [])
    def test_stored_snapshot_is_reused_without_live_catalog(self):
        catalog = _catalog(_family())
        first = analyze_ocr_results(_document(), [_page('RICEVUTA TAXI')], custom_family_catalog=catalog).document
        original = deepcopy(first)
        second = analyze_ocr_results(first, [_page('Partenza: Roma')]).document
        self.assertEqual(second['document_family_definitions'], original['document_family_definitions'])
        self.assertEqual(second['fields'][FIELD_NAME]['alternatives'][0]['value'], 'Roma')
        second['document_family_definitions'][0]['family']['label'] = 'changed'
        self.assertEqual(first, original)
    def test_changed_definition_or_version_is_rejected(self):
        original_catalog = _catalog(_family())
        first = analyze_ocr_results(_document(), [_page('RICEVUTA TAXI')], custom_family_catalog=original_catalog).document
        original = deepcopy(first)
        changed_label = _family(); changed_label['label'] = 'Changed'
        changed_cue = _family(); changed_cue['title_cues'] = ['NEW TITLE']
        changed_field = _family(alias='Arrivo')
        same_v2 = _catalog(_family(), version='2')
        self.assertEqual(original_catalog.snapshot_for(FAMILY_ID)['family_sha256'], same_v2.snapshot_for(FAMILY_ID)['family_sha256'])
        for name, catalog in (('label', _catalog(changed_label)), ('cue', _catalog(changed_cue)), ('field', _catalog(changed_field)), ('version', same_v2)):
            with self.subTest(change=name):
                with self.assertRaises(AnalysisPipelineError):
                    analyze_ocr_results(first, [_page('Partenza: Roma')], custom_family_catalog=catalog)
                self.assertEqual(first, original)
        analyze_ocr_results(first, [_page('Partenza: Roma')], custom_family_catalog=original_catalog)
    def test_only_exact_field_owner_is_snapshotted(self):
        a = _family('custom_aa', alias='Other'); a['title_cues'] = ['OTHER TITLE']
        b = _family('custom_aa_b', alias='Partenza'); b['title_cues'] = ['UNMATCHED TITLE']
        result = analyze_ocr_results(_document(), [_page('Partenza: Roma')], custom_family_catalog=_catalog(a, b)).document
        self.assertEqual([s['family']['id'] for s in result['document_family_definitions']], ['custom_aa_b'])
    def test_existing_fields_and_snapshots_are_preserved(self):
        catalog = _catalog(_family())
        for status in ('observed', 'uncertain'):
            with self.subTest(status=status):
                first = analyze_ocr_results(_document(), [_page('RICEVUTA TAXI', 'Partenza: Roma', 'INVOICE', 'Totale EUR 12,34')], custom_family_catalog=catalog).document
                for name in (FIELD_NAME, 'total_amount', 'document_family_candidates'):
                    candidate = first['fields'][name]
                    if status == 'observed':
                        candidate['value'] = candidate['alternatives'][0]['value']
                        candidate['status'] = 'observed'
                        candidate['alternatives'] = []
                before = deepcopy(first)
                result = analyze_ocr_results(first, [_page('RICEVUTA TAXI', 'Partenza: Milano', 'INVOICE', 'Totale EUR 99,99')], custom_family_catalog=catalog)
                self.assertEqual(first, before)
                self.assertEqual(result.document['fields'], before['fields'])
                self.assertEqual(result.document['document_family_definitions'], before['document_family_definitions'])
                self.assertTrue({FIELD_NAME, 'total_amount', 'document_family_candidates'} <= result.unapplied_proposals.keys())
    def test_no_custom_match_keeps_legacy_schema(self):
        for catalog in (None, _catalog(), _catalog(_family())):
            result = analyze_ocr_results(_document(), [_page('Nothing relevant')], custom_family_catalog=catalog).document
            self.assertEqual(result['schema_version'], '0.3.0')
            self.assertNotIn('document_family_definitions', result)
            self.assertEqual(result['validation_findings'], [])
    def test_incompatible_or_invalid_snapshots_fail_closed(self):
        first = analyze_ocr_results(_document(), [_page('RICEVUTA TAXI')], custom_family_catalog=_catalog(_family())).document
        other = _family('custom_other'); other['title_cues'] = ['OTHER TITLE']
        mixed = deepcopy(first)
        mixed['document_family_definitions'].append(_catalog(other, version='2').snapshot_for('custom_other'))
        broken = deepcopy(first); broken['document_family_definitions'][0]['family_sha256'] = '0' * 64
        for name, document in (('tampered hash', broken), ('mixed stored versions', mixed)):
            with self.subTest(case=name):
                before = deepcopy(document)
                with self.assertRaises(AnalysisPipelineError): analyze_ocr_results(document, [_page('x')])
                self.assertEqual(document, before)
        before = deepcopy(first)
        with self.assertRaises(AnalysisPipelineError):
            analyze_ocr_results(first, [_page('OTHER TITLE')], custom_family_catalog=_catalog(other, version='2'))
        self.assertEqual(first, before)

class RequiredCustomFieldValidationTests(unittest.TestCase):
    def test_missing_or_absent_required_field_is_indeterminate_without_evidence(self):
        result = analyze_ocr_results(_document(), [_page('RICEVUTA TAXI', 'RICEVUTA TAXI')], custom_family_catalog=_catalog(_family(required=True), version='2')).document
        finding = result['validation_findings'][0]
        self.assertEqual((finding['rule_id'], finding['outcome'], finding['severity'], finding['message_code'], finding['field_names'], finding['evidence']), ('required-custom-field', 'indeterminate', 'warning', 'required_custom_field_missing', [FIELD_NAME], []))
        del result['fields'][FIELD_NAME]
        self.assertEqual(validate_document_consistency(result), [finding])
    def test_uncertain_and_unreadable_required_fields_keep_deduplicated_evidence(self):
        result = analyze_ocr_results(_document(), [_page('RICEVUTA TAXI', 'Partenza: Roma')], custom_family_catalog=_catalog(_family(required=True), version='2')).document
        finding = result['validation_findings'][0]
        self.assertEqual(finding['message_code'], 'required_custom_field_requires_review')
        self.assertEqual(len(finding['evidence']), 1)
        self.assertEqual(finding['evidence'][0]['source_sha256'], SOURCE_HASH)
        self.assertEqual(finding['evidence'][0]['page_number'], 1)
        self.assertEqual(finding['evidence'][0]['token_ids'], ['token-1'])
        candidate = result['fields'][FIELD_NAME]
        candidate['status'] = 'unreadable'; candidate['value'] = None
        finding = validate_document_consistency(result)[0]
        self.assertEqual(finding['message_code'], 'required_custom_field_requires_review')
        self.assertEqual(len(finding['evidence']), 1)
    def test_observed_optional_and_unmatched_fields_have_no_required_finding(self):
        result = analyze_ocr_results(_document(), [_page('Partenza: Roma')], custom_family_catalog=_catalog(_family(required=True), version='2')).document
        self.assertEqual(validate_document_consistency(result), [])
        optional = _family(); optional['fields'].append({'id': 'driver', 'label': 'Driver', 'aliases': ['Driver']})
        result = analyze_ocr_results(_document(), [_page('RICEVUTA TAXI')], custom_family_catalog=_catalog(optional, version='2')).document
        self.assertEqual(validate_document_consistency(result), [])
        other = _family('custom_other', required=True); other['title_cues'] = ['OTHER TITLE']; other['fields'][0]['aliases'] = ['Elsewhere']
        result = analyze_ocr_results(_document(), [_page('RICEVUTA TAXI')], custom_family_catalog=_catalog(_family(), other, version='2')).document
        self.assertEqual(validate_document_consistency(result), [])
        result = analyze_ocr_results(_document(), [_page('RICEVUTA TAXI', 'Partenza: Roma')], custom_family_catalog=_catalog(_family(required=True), version='2')).document
        candidate = result['fields'][FIELD_NAME]
        candidate['status'] = 'observed'; candidate['value'] = 'Roma'; candidate['alternatives'] = []
        original = deepcopy(result)
        self.assertEqual(validate_document_consistency(result), [])
        self.assertEqual(result, original)
    def test_custom_family_does_not_receive_builtin_tax_or_hotel_rules(self):
        family = _family()
        family['fields'].extend([
            {'id': 'stay_date', 'label': 'Date', 'aliases': ['Date'], 'type': 'date'},
            {'id': 'fare', 'label': 'Fare', 'aliases': ['Fare'], 'type': 'amount'},
        ])
        catalog = _catalog(family, version='2')
        result = analyze_ocr_results(_document(), [_page('RICEVUTA TAXI', 'Date: 2026-03-02', 'Fare: 1234.50')], custom_family_catalog=catalog).document
        result['document_family'] = FAMILY_ID
        evidence = deepcopy(result['fields']['document_family_candidates']['evidence'])
        for name, value in (('check_in_date', '2026-10-14'), ('check_out_date', '2026-10-12'), ('taxable_base', '100.00'), ('vat_amount', '23.00'), ('total_amount', '100.00')):
            result['fields'][name] = {'value': value, 'status': 'observed', 'alternatives': [], 'evidence': deepcopy(evidence)}
        self.assertIn(FAMILY_ID + '_stay_date', result['fields'])
        self.assertIn(FAMILY_ID + '_fare', result['fields'])
        before = deepcopy(result)
        self.assertEqual(validate_document_consistency(result), [])
        self.assertEqual(result, before)



class CatalogDocumentProcessingTests(unittest.TestCase):
    def _run(self, texts, *, catalog=None, page_count=1, document=None, progress=None):
        from alfa_document_intelligence.document_processing import process_document_record
        from alfa_document_intelligence.document_decoder import DecodedPage
        from alfa_document_intelligence.ocr_adapter import RasterPage
        data = b'synthetic document'
        doc = deepcopy(document) if document is not None else _document()
        digest = hashlib.sha256(data).hexdigest()
        doc['source']['sha256'] = digest; doc['source']['page_count'] = page_count
        for evidence in doc['fiscal_document_state'].get('evidence', []): evidence['source_sha256'] = digest
        doc['processing']['ocr']['status'] = 'not_started'
        original = deepcopy(doc)
        class Adapter:
            name = 'synthetic'; version = '1'
            def recognize(self, page, languages):
                return [OCRToken(f'token-{i}', text, POLYGON) for i, text in enumerate(texts)]
        def decoder(data, media_kind, *, source_sha256, limits):
            for number in range(1, page_count + 1):
                yield DecodedPage(RasterPage(number, 100, 80, b'pixels'), page_count)
        kwargs = {'decoder': decoder, 'progress_callback': progress}
        if catalog is not None: kwargs['custom_family_catalog'] = catalog
        result = process_document_record(doc, data, Adapter(), **kwargs)
        self.assertEqual(doc, original)
        return result
    def test_catalog_reaches_semantics_and_required_validation(self):
        result = self._run(['RICEVUTA TAXI'], catalog=_catalog(_family(required=True), version='2'))
        self.assertEqual(result['schema_version'], '0.3.0')
        self.assertEqual(result['fields'][FIELD_NAME]['status'], 'absent')
        self.assertEqual(result['validation_findings'][0]['message_code'], 'required_custom_field_missing')
        present = self._run(['RICEVUTA TAXI', 'Partenza: Roma'], catalog=_catalog(_family(required=True), version='2'))
        self.assertEqual(present['fields'][FIELD_NAME]['status'], 'uncertain')
        self.assertEqual(present['fields'][FIELD_NAME]['evidence'][0]['source_sha256'], present['source']['sha256'])
    def test_catalog_and_progress_callback_coexist(self):
        progress = []
        result = self._run(['RICEVUTA TAXI', 'Partenza: Roma'], catalog=_catalog(_family()), page_count=2, progress=lambda *x: progress.append(x))
        self.assertEqual(progress, [(1, 2), (2, 2)])
        self.assertEqual(result['fields'][FIELD_NAME]['status'], 'uncertain')
        self.assertEqual(result['document_family_definitions'], [_catalog(_family()).snapshot_for(FAMILY_ID)])
    def test_omitted_catalog_preserves_processing_behavior(self):
        result = self._run(['RICEVUTA TAXI'])
        self.assertEqual(result['schema_version'], '0.3.0')
        self.assertNotIn('document_family_definitions', result)
        self.assertEqual(result['processing']['semantic_extraction']['status'], 'completed')
    def test_catalog_conflict_returns_semantic_failure_copy(self):
        catalog = _catalog(_family()); doc = _document(); doc['schema_version'] = '0.2.0'; doc['document_family_definitions'] = [catalog.snapshot_for(FAMILY_ID)]
        result = self._run(['RICEVUTA TAXI'], document=doc, catalog=_catalog(_family(), version='2'))
        self.assertEqual(result['processing']['ocr']['status'], 'completed')
        self.assertEqual(result['processing']['semantic_extraction']['error_code'], 'semantic_extraction_failed')
        self.assertEqual(result['fields'], doc['fields'])
        self.assertEqual(result['document_family_definitions'], doc['document_family_definitions'])
