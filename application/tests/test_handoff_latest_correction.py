"""Synthetic regression for superseded manual handoff values."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from alfa_document_intelligence.chatgpt_handoff import ChatGPTHandoffError, build_chatgpt_handoff_prompt
from alfa_document_intelligence.expense_reports import build_expense_report_bundle
from alfa_document_intelligence.review_ledger import ReviewRejected, append_review_event, verify_review_ledger


class HandoffLatestCorrectionTests(unittest.TestCase):
    def setUp(self):
        fixture = Path(__file__).parent / 'fixtures' / 'synthetic_invoice.json'
        self.record = json.loads(fixture.read_text(encoding='utf-8'))
        self.record['document_id'] = 'synthetic-note'
        self.record['document_family'] = 'expense_report'
        for action in ('queued', 'opened'):
            self.record = append_review_event(self.record, actor_id='synthetic-reviewer', action=action, timestamp='2026-10-15T10:00:00Z')

    def edit(self, record, field, value, status, minute, action='field_corrected'):
        candidate = copy.deepcopy(record['fields'][field])
        candidate.update(value=value, status=status, alternatives=[])
        if 'normalization' in candidate:
            candidate['normalization']['normalized_value'] = value
        return append_review_event(record, actor_id='synthetic-reviewer', action=action,
            timestamp=f'2026-10-15T10:{minute:02d}:00Z', field_name=field,
            reason_code='synthetic_review', candidate=candidate)

    def payload(self, record):
        verify_review_ledger(record)
        documents = {'synthetic-note': record}
        bundle = build_expense_report_bundle('synthetic-report', 'synthetic-note', [], documents)
        prompt = build_chatgpt_handoff_prompt(bundle, documents)
        return prompt, json.loads(prompt.split('DATI CONFERMATI:', 1)[1])[0]['verified_fields']

    def test_latest_non_observed_correction_removes_previous_value(self):
        for status in ('absent', 'uncertain', 'unreadable', 'rejected', 'not_applicable'):
            with self.subTest(status=status):
                record = self.edit(self.record, 'currency', 'SYNTHETIC-OLD', 'observed', 1)
                record = self.edit(record, 'total_amount', '42.00', 'observed', 2)
                value = 'SYNTHETIC-UNCERTAIN' if status == 'uncertain' else None
                record = self.edit(record, 'currency', value, status, 3)
                prompt, fields = self.payload(record)
                self.assertEqual(fields['total_amount']['value'], '42.00')
                self.assertNotIn('currency', fields)
                self.assertNotIn('SYNTHETIC-OLD', prompt)

    def test_later_observed_alternative_restores_only_latest_value(self):
        record = self.edit(self.record, 'currency', 'SYNTHETIC-OLD', 'observed', 1)
        record = self.edit(record, 'total_amount', '42.00', 'observed', 2)
        record = self.edit(record, 'currency', None, 'absent', 3)
        record = self.edit(record, 'currency', 'SYNTHETIC-NEW', 'observed', 4, 'alternative_selected')
        prompt, fields = self.payload(record)
        self.assertEqual(fields['currency']['value'], 'SYNTHETIC-NEW')
        self.assertEqual(fields['total_amount']['value'], '42.00')
        self.assertNotIn('SYNTHETIC-OLD', prompt)

    def test_last_confirmed_field_removed_requires_new_confirmation(self):
        record = self.edit(self.record, 'currency', 'SYNTHETIC-OLD', 'observed', 1)
        record = self.edit(record, 'currency', None, 'absent', 2)
        verify_review_ledger(record)
        documents = {'synthetic-note': record}
        bundle = build_expense_report_bundle('synthetic-report', 'synthetic-note', [], documents)
        with self.assertRaises(ChatGPTHandoffError):
            build_chatgpt_handoff_prompt(bundle, documents)

    def test_latest_event_wins_with_equal_timestamps(self):
        record = self.edit(self.record, 'currency', 'SYNTHETIC-OLD', 'observed', 1)
        record = self.edit(record, 'total_amount', '42.00', 'observed', 1)
        record = self.edit(record, 'currency', None, 'absent', 1)
        prompt, fields = self.payload(record)
        self.assertEqual(fields['total_amount']['value'], '42.00')
        self.assertNotIn('currency', fields)
        self.assertNotIn('SYNTHETIC-OLD', prompt)

    def test_flagged_event_does_not_revoke_confirmation(self):
        record = self.edit(self.record, 'currency', 'SYNTHETIC-CONFIRMED', 'observed', 1)
        record = append_review_event(record, actor_id='synthetic-reviewer', action='flagged',
            timestamp='2026-10-15T10:02:00Z', field_name='currency', reason_code='synthetic_check')
        self.assertEqual(record['review']['status'], 'blocked')
        prompt, fields = self.payload(record)
        self.assertEqual(fields['currency']['value'], 'SYNTHETIC-CONFIRMED')
        self.assertIn('Non approvare', prompt)

    def test_tampered_ledger_rejected_before_field_serialization(self):
        record = self.edit(self.record, 'currency', 'SYNTHETIC-CONFIRMED', 'observed', 1)
        documents = {'synthetic-note': record}
        bundle = build_expense_report_bundle('synthetic-report', 'synthetic-note', [], documents)
        record['review']['events'][-1]['candidate']['value'] = 'SYNTHETIC-TAMPERED'
        with patch('alfa_document_intelligence.chatgpt_handoff._human_confirmed_fields') as collect:
            with self.assertRaises(ValueError) as caught:
                build_chatgpt_handoff_prompt(bundle, documents)
            self.assertIsInstance(caught.exception.__cause__, ReviewRejected)
            collect.assert_not_called()


    def test_unreviewed_observed_ocr_field_is_excluded(self):
        record = self.edit(self.record, 'total_amount', '42.00', 'observed', 1)
        self.assertEqual(record['fields']['currency']['status'], 'observed')
        _, fields = self.payload(record)
        self.assertEqual(fields['total_amount']['value'], '42.00')
        self.assertNotIn('currency', fields)

    def test_latest_observed_correction_uses_its_evidence_page(self):
        record = copy.deepcopy(self.record)
        record['source']['page_count'] = 2
        record['pages'].append({**record['pages'][0], 'page_number': 2})
        record = self.edit(record, 'currency', 'SYNTHETIC-OLD', 'observed', 1)
        candidate = copy.deepcopy(record['fields']['currency'])
        candidate['value'] = 'SYNTHETIC-NEW'
        candidate['evidence'][0]['page_number'] = 2
        record = append_review_event(record, actor_id='synthetic-reviewer', action='field_corrected',
            timestamp='2026-10-15T10:02:00Z', field_name='currency', reason_code='synthetic_review', candidate=candidate)
        _, fields = self.payload(record)
        self.assertEqual(fields['currency'], {'value': 'SYNTHETIC-NEW', 'evidence_pages': [2]})

    def test_revocation_is_confined_to_field_and_document(self):
        note = self.edit(self.record, 'currency', 'SYNTHETIC-NOTE-OLD', 'observed', 1)
        note = self.edit(note, 'total_amount', '42.00', 'observed', 2)
        note = self.edit(note, 'currency', None, 'absent', 3)
        attachment = copy.deepcopy(self.record)
        attachment['document_id'] = 'synthetic-attachment'
        attachment['document_family'] = 'invoice'
        attachment = self.edit(attachment, 'currency', 'SYNTHETIC-ATTACHMENT', 'observed', 1)
        documents = {'synthetic-note': note, 'synthetic-attachment': attachment}
        bundle = build_expense_report_bundle('synthetic-report', 'synthetic-note', ['synthetic-attachment'], documents)
        prompt = build_chatgpt_handoff_prompt(bundle, documents)
        sources = json.loads(prompt.split('DATI CONFERMATI:', 1)[1])
        self.assertEqual(sources[0]['verified_fields']['total_amount']['value'], '42.00')
        self.assertEqual(sources[1]['verified_fields']['currency']['value'], 'SYNTHETIC-ATTACHMENT')
        self.assertNotIn('currency', sources[0]['verified_fields'])
        self.assertNotIn('SYNTHETIC-NOTE-OLD', prompt)
