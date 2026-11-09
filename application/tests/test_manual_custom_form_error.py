import copy
import io
import json
import re
import unittest
from html.parser import HTMLParser
from unittest.mock import patch
from urllib.parse import urlencode

from alfa_document_intelligence.document_family_catalog import load_custom_family_catalog
from alfa_document_intelligence.local_intake_app import create_expense_report_app


class _Forms(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms = []
        self.current = None
        self.select = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form':
            self.current = {'action': attrs.get('action'), 'values': {}}
            self.forms.append(self.current)
        elif self.current is not None and tag == 'input' and 'name' in attrs:
            self.current['values'][attrs['name']] = attrs.get('value', '')
        elif self.current is not None and tag == 'select':
            self.select = attrs.get('name')
        elif self.current is not None and tag == 'option' and self.select and 'selected' in attrs:
            self.current['values'][self.select] = attrs.get('value', '')

    def handle_endtag(self, tag):
        if tag == 'form':
            self.current = None
        elif tag == 'select':
            self.select = None


class ManualCustomFormErrorTests(unittest.TestCase):
    def test_invalid_amount_preserves_form_without_mutating_review_and_can_be_corrected(self):
        catalog = load_custom_family_catalog(json.dumps({
            'catalog_version': '2', 'families': [{
                'id': 'custom_taxi_receipt', 'label': 'Ricevuta taxi',
                'title_cues': ['RICEVUTA TAXI'],
                'fields': [{'id': 'fare', 'label': 'Tariffa', 'aliases': ['Importo'], 'type': 'amount'}],
            }],
        }))

        def processor(record, _source):
            record['pages'] = [{'page_number': 1}, {'page_number': 2}]
            record['schema_version'] = '0.2.0'
            record['document_family_definitions'] = [catalog.snapshot_for('custom_taxi_receipt')]
            return record

        app = create_expense_report_app(document_processor=processor)

        def invoke(method, path, body=b'', content_type='', origin='http://127.0.0.1:8080'):
            response = {}
            environ = {'REQUEST_METHOD': method, 'PATH_INFO': path, 'HTTP_HOST': '127.0.0.1:8080',
                       'HTTP_ORIGIN': origin, 'CONTENT_LENGTH': str(len(body)) if body else '',
                       'CONTENT_TYPE': content_type, 'wsgi.input': io.BytesIO(body)}
            payload = b''.join(app(environ, lambda status, headers: response.update(status=status, headers=dict(headers))))
            return response, payload.decode('utf-8', errors='replace')

        boundary = 'synthetic-custom-error'
        upload = (f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="receipt.pdf"\r\n'
                  'Content-Type: application/pdf\r\n\r\n').encode() + b'%PDF-1.7\nsynthetic source\n' + f'\r\n--{boundary}--\r\n'.encode()
        response, _ = invoke('POST', '/upload', upload, f'multipart/form-data; boundary={boundary}')
        self.assertEqual(response['status'], '200 OK')
        response, _ = invoke('POST', '/assign-note', b'note_document_id=doc-001', 'application/x-www-form-urlencoded')
        self.assertEqual(response['status'], '200 OK')
        response, page = invoke('GET', '/reviews/doc-001')
        self.assertEqual(response['status'], '200 OK')
        token = re.search(r'name="_ocr2_csrf" value="([A-Za-z0-9_-]+)"', page).group(1)
        with patch('alfa_document_intelligence.local_intake_app._source_page_png', return_value=b'synthetic-preview'):
            response, _ = invoke('GET', '/reviews/doc-001/pages/2.png')
        self.assertEqual(response['status'], '200 OK')

        cells = dict(zip(app.__code__.co_freevars, app.__closure__))
        state = cells['state'].cell_contents
        before_record = copy.deepcopy(state.intake.documents['doc-001'])
        before_seconds = copy.deepcopy(state.review_seconds)
        before_activity = state.last_activity
        action = '/reviews/doc-001/fields/custom_taxi_receipt_fare'
        values = {'_ocr2_csrf': token, 'value': '12,50', 'region_page': '2',
                  'region_x0': '0.1', 'region_y0': '0.2', 'region_x1': '0.7', 'region_y1': '0.4',
                  'review_seconds': '0'}

        def submit(data, origin='null'):
            return invoke('POST', action, urlencode(data).encode(), 'application/x-www-form-urlencoded', origin)

        response, page = submit(values)
        self.assertEqual(response['status'], '400 Bad Request')
        self.assertIn('formato', page.lower())
        self.assertIn('1234.50', page)
        self.assertIn('document.addEventListener("visibilitychange",tick)', page)
        self.assertIn('data-region-selection', page)
        self.assertIn('restoreSelection()', page)
        forms = _Forms()
        forms.feed(page)
        restored = next(form['values'] for form in forms.forms if form['action'] == action)
        for name in ('value', 'region_page', 'region_x0', 'region_y0', 'region_x1', 'region_y1'):
            self.assertEqual(restored.get(name), values[name], name)
        self.assertEqual(state.intake.documents['doc-001'], before_record)
        self.assertEqual(state.review_seconds, before_seconds)
        self.assertEqual(state.last_activity, before_activity)

        attack = dict(values, value='12,50"><script>alert(1)</script>')
        response, page = submit(attack)
        self.assertEqual(response['status'], '400 Bad Request')
        self.assertNotIn('<script>alert(1)</script>', page)
        forms = _Forms()
        forms.feed(page)
        restored = next(form['values'] for form in forms.forms if form['action'] == action)
        self.assertEqual(restored.get('value'), attack['value'])
        self.assertEqual(state.intake.documents['doc-001'], before_record)
        self.assertEqual(state.review_seconds, before_seconds)
        self.assertEqual(state.last_activity, before_activity)

        response, _ = submit(dict(values, value='12.50'), origin='http://evil.example')
        self.assertEqual(response['status'], '403 Forbidden')
        response, _ = submit(dict(values, value='12.50', _ocr2_csrf='wrong'))
        self.assertEqual(response['status'], '403 Forbidden')
        self.assertEqual(state.intake.documents['doc-001'], before_record)
        response, page = submit(dict(values, value='12.50'))
        self.assertEqual(response['status'], '200 OK')
        self.assertIn('12.50', page)
        self.assertNotEqual(state.intake.documents['doc-001'], before_record)


if __name__ == '__main__':
    unittest.main()
