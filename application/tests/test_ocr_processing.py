import base64
import dataclasses
import json
import unittest
from unittest.mock import patch

from alfa_document_intelligence.ocr_processing import OCRJobProtocolError, OCRProcessLimits, encode_frame, decode_frame

LIMITS = dict(job_timeout_seconds=1, cleanup_grace_seconds=1, child_memory_limit_bytes=134217728, max_input_frame_bytes=1, max_status_frame_bytes=1, max_result_frame_bytes=1, max_aggregate_result_bytes=1, max_page_output_bytes=1, max_ipc_messages=1)

def wire(value):
    return json.dumps(value, separators=(',', ':'), ensure_ascii=False).encode()

def message(kind):
    common = {'v': 1, 'kind': kind}
    if kind == 'start':
        return dict(common, generation_id='g', documents=[dict(document_id='d', record={'document_id':'d'}, source_bytes_b64='YQ==')], decode_limits=dict.fromkeys(('max_pages','max_dimension_px','max_page_pixels','max_total_pixels','pdf_render_dpi','max_source_bytes'), 1), catalog_json=None, catalog_version=None, catalog_sha256=None)
    if kind == 'status':
        return dict(common, job_id='j', generation_id='g', phase='queued', completed_documents=0, total_documents=1, current_page=0, total_pages=1, error_code=None)
    if kind == 'result': return dict(common, job_id='j', document_id='d', record={})
    if kind == 'complete': return dict(common, job_id='j', document_count=1, result_sha256='a'*64)
    return dict(common, job_id='j', error_code='ERROR_1')

class OCRProcessLimitsTests(unittest.TestCase):
    def test_required_immutable_and_platform(self):
        for name in LIMITS:
            with self.subTest(name=name), self.assertRaises(TypeError): OCRProcessLimits(**{k:v for k,v in LIMITS.items() if k != name})
        obj = OCRProcessLimits(**LIMITS)
        with self.assertRaises(dataclasses.FrozenInstanceError): obj.max_ipc_messages = 2
        with patch('alfa_document_intelligence.ocr_processing.os.name', 'other'):
            with self.assertRaises(OCRJobProtocolError): OCRProcessLimits(**LIMITS)
        for platform in ('nt', 'posix'):
            with patch('alfa_document_intelligence.ocr_processing.os.name', platform): OCRProcessLimits(**LIMITS)

    def test_all_boundaries(self):
        bounds = [(0,3600), (0,30), (134217727,2147483647)] + [(0,2147483647)]*5 + [(0,1000000)]
        for (name, base), (below, upper) in zip(LIMITS.items(), bounds):
            for value in (below, upper+1, 10**400, True, float('nan'), float('inf'), '1'):
                with self.subTest(name=name, value=value), self.assertRaises(OCRJobProtocolError): OCRProcessLimits(**dict(LIMITS, **{name:value}))
            OCRProcessLimits(**dict(LIMITS, **{name:upper}))
            OCRProcessLimits(**dict(LIMITS, **{name:base}))

class OCRFrameProtocolTests(unittest.TestCase):
    def assert_bad(self, obj, kind='status', cap=4096):
        with self.assertRaises(OCRJobProtocolError) as err: decode_frame(wire(obj), max_bytes=cap, expected_kind=kind)
        self.assertNotIn('SENSITIVE_TEST_PAYLOAD', str(err.exception))
    def test_all_kinds_and_determinism(self):
        for kind in ('start','status','result','complete','error'):
            obj=message(kind); data=encode_frame(obj,max_bytes=4096)
            self.assertEqual(data, json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode())
            self.assertEqual(decode_frame(data,max_bytes=4096,expected_kind=kind),obj)
            self.assertEqual(data,encode_frame(obj,max_bytes=4096))
    def test_byte_and_parser_boundaries(self):
        data=wire(message('error'))
        self.assertEqual(decode_frame(data,max_bytes=len(data),expected_kind='error'),message('error'))
        with patch('alfa_document_intelligence.ocr_processing.json.loads', side_effect=AssertionError('parsed')):
            with self.assertRaises(OCRJobProtocolError): decode_frame(data,max_bytes=len(data)-1,expected_kind='error')
        for cap in (0,True,2147483648,'1'):
            with self.assertRaises(OCRJobProtocolError): decode_frame(data,max_bytes=cap,expected_kind='error')
            with self.assertRaises(OCRJobProtocolError): encode_frame(message('error'),max_bytes=cap)
        with self.assertRaises(OCRJobProtocolError): encode_frame(message('error'),max_bytes=len(encode_frame(message('error'),max_bytes=4096))-1)
    def test_malformed_wire(self):
        for raw in (b'',b'\xff',b'{',b'[]',b'{"v":1,"v":1}',b'{"v":NaN}',b'{"v":Infinity}',b'{"v":-Infinity}',b'"x"',b'null',b'{}x'):
            with self.subTest(raw=raw), self.assertRaises(OCRJobProtocolError): decode_frame(raw,max_bytes=4096,expected_kind='status')
        for raw in ('x',bytearray(b'{}'),None):
            with self.assertRaises(OCRJobProtocolError): decode_frame(raw,max_bytes=4096,expected_kind='status')
        for kind in ([],None,'other'):
            with self.assertRaises(OCRJobProtocolError): decode_frame(b'{}',max_bytes=4096,expected_kind=kind)
    def test_schema_rejections_decoder_and_encoder(self):
        samples=[]
        for kind in ('start','status','result','complete','error'):
            obj=message(kind); samples += [(dict(obj, extra=1),kind), ({k:v for k,v in obj.items() if k!='v'},kind), (dict(obj,v=True),kind), (dict(obj,kind=[]),kind)]
        obj=message('status')
        for key,value in [('phase',[]),('phase','wrong'),('completed_documents',True),('completed_documents',2),('current_page',2),('job_id',''),('generation_id','x'*65),('error_code','bad-code')]: samples.append((dict(obj,**{key:value}),'status'))
        for key,value in [('document_count',0),('result_sha256','A'*64)]: samples.append((dict(message('complete'),**{key:value}),'complete'))
        samples += [(dict(message('error'),error_code='SENSITIVE_TEST_PAYLOAD!'),'error'),(dict(message('result'),record=[]),'result')]
        for obj,kind in samples:
            with self.subTest(obj=obj):
                self.assert_bad(obj,kind)
                with self.assertRaises(OCRJobProtocolError): encode_frame(obj,max_bytes=4096)
    def test_start_validation(self):
        obj=message('start')
        variants=[dict(obj,documents=[]),dict(obj,documents=obj['documents']*2),dict(obj,catalog_json='{}'),dict(obj,catalog_json='{}',catalog_version='v',catalog_sha256='A'*64)]
        for source in ('', 'YQ', 'YQ===', 'YR==', '!!==', base64.b64encode(b'ab').decode()):
            entry=dict(obj['documents'][0],source_bytes_b64=source); variants.append(dict(obj,documents=[entry]))
        variants.append(dict(obj,documents=[dict(obj['documents'][0],record={'document_id':'other'})]))
        variants.append(dict(obj,decode_limits=dict(obj['decode_limits'],max_pages=True)))
        for variant in variants:
            self.assert_bad(variant,'start')
            with self.assertRaises(OCRJobProtocolError): encode_frame(variant,max_bytes=4096)
        valid=dict(obj,catalog_json='{}',catalog_version='v',catalog_sha256='a'*64)
        self.assertEqual(decode_frame(wire(valid),max_bytes=4096,expected_kind='start'),valid)
        huge=dict(valid,catalog_json='é'*32769)
        self.assert_bad(huge,'start',100000)
    def test_tree_limits(self):
        obj=message('result'); nested=None
        for _ in range(33): nested=[nested]
        cases=[dict(obj,record={'x':nested}),dict(obj,record={'x':'\ud800'}),dict(obj,record={'x':2**63}),dict(obj,record={'x':float('nan')}),dict(obj,record={'x'*257:1}),dict(obj,record={'x':[None]*100001})]
        for case in cases:
            with self.assertRaises(OCRJobProtocolError): encode_frame(case,max_bytes=1000000)
        for case in (cases[0],cases[2],cases[4],cases[5]): self.assert_bad(case,'result',1000000)
        cycle=[]; cycle.append(cycle)
        with self.assertRaises(OCRJobProtocolError): encode_frame(dict(obj,record={'x':cycle}),max_bytes=4096)
        with self.assertRaises(OCRJobProtocolError): decode_frame(b'{"v":1,"kind":"result","job_id":"j","document_id":"d","record":{"x":"\\ud800"}}',max_bytes=4096,expected_kind='result')

    def test_encoder_rejects_before_serialization_and_mapping_exhaustion(self):
        from collections.abc import Mapping
        class BoundedMapping(Mapping):
            def __iter__(self):
                for i in range(1000):
                    if i > 64: raise AssertionError('mapping exhausted')
                    yield str(i)
            def __len__(self): return 1000
            def __getitem__(self, key): return 1
        with self.assertRaises(OCRJobProtocolError): encode_frame(BoundedMapping(), max_bytes=16)
        obj=message('result'); obj['record']={'x':'\x01'*50}
        with patch('alfa_document_intelligence.ocr_processing.json.JSONEncoder.iterencode', side_effect=AssertionError('serializer reached')):
            with self.assertRaises(OCRJobProtocolError): encode_frame(obj,max_bytes=150)
        obj['record']={'x':'é'*50}
        with patch('alfa_document_intelligence.ocr_processing.json.JSONEncoder.iterencode', side_effect=AssertionError('serializer reached')):
            with self.assertRaises(OCRJobProtocolError): encode_frame(obj,max_bytes=150)

    def test_exact_wire_and_independent_decoder_boundaries(self):
        obj=message('error'); raw=wire(obj)
        encoded=encode_frame(obj,max_bytes=4096)
        self.assertEqual(encode_frame(obj,max_bytes=len(encoded)),encoded)
        with self.assertRaises(OCRJobProtocolError): encode_frame(obj,max_bytes=len(encoded)-1)
        with self.assertRaises(OCRJobProtocolError): decode_frame(raw,max_bytes=4096,expected_kind='status')
        for number in (b'NaN',b'Infinity',b'-Infinity'):
            payload=b'{"v":1,"kind":"result","job_id":"j","document_id":"d","record":{"x":'+number+b'}}'
            with self.assertRaises(OCRJobProtocolError): decode_frame(payload,max_bytes=4096,expected_kind='result')
        start=message('start')
        for data,good in ((b'a',True),(b'ab',False)):
            entry=dict(start['documents'][0],source_bytes_b64=base64.b64encode(data).decode())
            candidate=dict(start,documents=[entry])
            if good: self.assertEqual(decode_frame(wire(candidate),max_bytes=4096,expected_kind='start'),candidate)
            else: self.assert_bad(candidate,'start')
        start=dict(start,catalog_json='é'*32768,catalog_version='v',catalog_sha256='a'*64)
        self.assertEqual(decode_frame(wire(start),max_bytes=100000,expected_kind='start'),start)
        self.assert_bad(dict(start,catalog_json='é'*32769),'start',100000)

    def test_exact_tree_boundaries(self):
        obj=message('result'); value=None
        # root=0, record=1, first nested value=2
        for _ in range(30): value=[value]
        obj['record']={'x':value}
        self.assertEqual(decode_frame(encode_frame(obj,max_bytes=4096),max_bytes=4096,expected_kind='result'),obj)
        obj['record']={'x':[None]*99993} # root 5 + record 1 + list 99993 = 99999
        obj['record']['y']=None # 100000 total
        raw=encode_frame(obj,max_bytes=600000)
        self.assertEqual(decode_frame(raw,max_bytes=600000,expected_kind='result'),obj)
        obj['record']['z']=None
        with self.assertRaises(OCRJobProtocolError): encode_frame(obj,max_bytes=600000)
        self.assert_bad(obj,'result',600000)
