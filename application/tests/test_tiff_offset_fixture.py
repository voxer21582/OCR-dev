import io, struct, zipfile, hashlib, unittest
from alfa_document_intelligence.ingestion import inventory_stream, IngestionLimits, UploadRejected
from alfa_document_intelligence.image_safety import inspect_image_header, ImageHeaderError

LIMIT = 1024 * 1024

def fixture(endian='<', first=8, second=LIMIT+2):
    tags = [(256,4,2),(257,4,2),(258,3,8),(259,3,1),(262,3,1),
            (273,4,0),(277,3,1),(278,4,2),(279,4,4)]
    end = second + 2 + 12*len(tags) + 4
    pixel1, pixel2 = end, end+4
    data = bytearray(end+8)
    data[:8] = (b'II' if endian=='<' else b'MM') + struct.pack(endian+'HI',42,first)
    for pos, nxt, pixel in ((first,second,pixel1),(second,0,pixel2)):
        struct.pack_into(endian+'H',data,pos,len(tags))
        for i,(tag,typ,val) in enumerate(tags):
            if tag == 273: val = pixel
            entry=pos+2+i*12
            struct.pack_into(endian+'HHI',data,entry,tag,typ,1)
            struct.pack_into(endian+('H' if typ==3 else 'I'),data,entry+8,val)
        struct.pack_into(endian+'I',data,pos+2+12*len(tags),nxt)
    data[pixel1:pixel1+4]=b'\x00\x55\xaa\xff'
    data[pixel2:pixel2+4]=b'\xff\xaa\x55\x00'
    return bytes(data)

def verify(data, endian, first, second):
    assert data[:2] == (b'II' if endian=='<' else b'MM')
    assert struct.unpack_from(endian+'HI',data,2)==(42,first)
    spans=[]
    for pos,nxt,pixels in ((first,second,b'\x00\x55\xaa\xff'),(second,0,b'\xff\xaa\x55\x00')):
        count=struct.unpack_from(endian+'H',data,pos)[0]; assert count==9
        tags={}
        for i in range(count):
            p=pos+2+i*12; tag,typ,n=struct.unpack_from(endian+'HHI',data,p)
            assert n==1 and typ in (3,4) and tag not in tags
            tags[tag]=(typ,struct.unpack_from(endian+('H' if typ==3 else 'I'),data,p+8)[0])
        assert list(tags)==[256,257,258,259,262,273,277,278,279]
        assert [tags[t] for t in (256,257,258,259,262,277,278,279)]==[(4,2),(4,2),(3,8),(3,1),(3,1),(3,1),(4,2),(4,4)]
        off=tags[273][1]; assert off+4<=len(data) and data[off:off+4]==pixels
        spans.extend([(pos,pos+2+12*count+4),(off,off+4)])
        assert struct.unpack_from(endian+'I',data,pos+2+12*count)[0]==nxt
    assert all(a[1]<=b[0] or b[1]<=a[0] for i,a in enumerate(spans) for b in spans[i+1:])

class NonSeekable:
    def __init__(self,data): self.data=io.BytesIO(data)
    def read(self,n=-1): return self.data.read(n)

def zipped(data):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_STORED) as z: z.writestr('page.tif',data)
    return out.getvalue()

class TiffOffsetFixtureTests(unittest.TestCase):
    def test_sparse_direct_and_zip(self):
        for endian in ('<','>'):
            data=fixture(endian); verify(data,endian,8,LIMIT+2)
            for payload,name in ((data,'page.tif'),(zipped(data),'pages.zip')):
                with self.subTest(endian=endian,name=name):
                    result=inventory_stream(NonSeekable(payload),name)
                    doc=result.documents[0]
                    self.assertEqual((doc.width_px,doc.height_px,doc.page_count),(2,2,2))
                    self.assertEqual(doc.sha256,hashlib.sha256(data).hexdigest())
    def test_sparse_budget_exact_and_over(self):
        data=fixture(); need=8+2*(2+9*12+4)
        self.assertEqual(inventory_stream(io.BytesIO(data),'x.tif',IngestionLimits(max_image_header_bytes=need)).source.page_count,2)
        with self.assertRaises(UploadRejected): inventory_stream(io.BytesIO(data),'x.tif',IngestionLimits(max_image_header_bytes=need-1))
    def test_duplicate_dimensions_rejected_in_both_apis(self):
        for endian in ('<','>'):
            for tag in (256,257):
                data=bytearray(fixture(endian,8,256)); struct.pack_into(endian+'H',data,8+2+2*12,tag)
                with self.subTest(endian=endian,tag=tag):
                    with self.assertRaises(UploadRejected): inventory_stream(io.BytesIO(data),'x.tif')
                    with self.assertRaises(ImageHeaderError): inspect_image_header(bytes(data),'tiff',max_header_bytes=LIMIT,max_dimension=12000,max_pixels=50000000,max_tiff_pages=100)
    def test_old_bytes_api_retains_prefix_limit(self):
        with self.assertRaises(ImageHeaderError): inspect_image_header(fixture()[:LIMIT],'tiff',max_header_bytes=LIMIT,max_dimension=12000,max_pixels=50000000,max_tiff_pages=100)

class TiffBoundaryTests(unittest.TestCase):
    def inventory(self, data, limits=IngestionLimits()):
        return inventory_stream(NonSeekable(data), 'x.tif', limits)

    def test_first_ifd_beyond_prefix(self):
        data=fixture('<',LIMIT+2,LIMIT+128)
        verify(data,'<',LIMIT+2,LIMIT+128)
        self.assertEqual(self.inventory(data).source.page_count,2)

    def test_invalid_offsets_cycles_counts_and_dimensions(self):
        from test_ingestion import make_tiff
        original=fixture('<',8,256)
        cases=[]
        for offset in (len(original)+1,len(original)-1,8):
            data=bytearray(original); struct.pack_into('<I',data,8+2+9*12,offset); cases.append(data)
        data=bytearray(original); struct.pack_into('<I',data,256+2+9*12,8); cases.append(data)
        data=bytearray(original); struct.pack_into('<H',data,8,65535); cases.append(data)
        data=bytearray(original); struct.pack_into('<I',data,256+2+8,12001); cases.append(data)
        for data in cases:
            with self.subTest(data=data[8:16]):
                with self.assertRaises(UploadRejected): self.inventory(data)
        self.assertEqual(self.inventory(make_tiff([(2,2)]*100)).source.page_count,100)
        with self.assertRaises(UploadRejected): self.inventory(make_tiff([(2,2)]*101))
        for endian in ('little','big'):
            for short in (True,False):
                self.assertEqual(self.inventory(make_tiff([(2,3)],endian,short)).source.height_px,3)
        with self.assertRaises(UploadRejected): self.inventory(b'II+\x00'+b'\x00'*12)

    def test_zip_crc_size_and_existing_limits(self):
        data=fixture('<',8,256)
        archive=bytearray(zipped(data)); payload=archive.find(data); self.assertGreater(payload,0)
        archive[payload+40] ^= 1
        with self.assertRaises(UploadRejected): inventory_stream(NonSeekable(archive),'x.zip')
        archive=bytearray(zipped(data)); central=archive.find(b'PK\x01\x02'); self.assertGreater(central,0)
        struct.pack_into('<I',archive,central+24,len(data)+1)
        with self.assertRaises(UploadRejected): inventory_stream(NonSeekable(archive),'x.zip')
        with self.assertRaises(UploadRejected): inventory_stream(NonSeekable(zipped(data)),'x.zip',IngestionLimits(max_archive_uncompressed_bytes=len(data)-1))
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z: z.writestr('x.tif',fixture())
        with self.assertRaises(UploadRejected): inventory_stream(NonSeekable(out.getvalue()),'x.zip')

class TiffReviewTests(unittest.TestCase):
    def test_overlapping_directory_reads_are_charged_twice(self):
        # First IFD's next pointer is also the second IFD count (34).
        data=bytearray(34+2+34*12+4)
        data[:8]=b'II'+struct.pack('<HI',42,8)
        struct.pack_into('<H',data,8,2)
        struct.pack_into('<HHII',data,10,256,4,1,2)
        struct.pack_into('<HHII',data,22,257,4,1,2)
        struct.pack_into('<I',data,34,34)
        struct.pack_into('<HHII',data,36+12,256,4,1,2)
        struct.pack_into('<HHII',data,36+24,257,4,1,2)
        budget=8+(2+28)+(2+34*12+4)
        self.assertEqual(inventory_stream(io.BytesIO(data),'x.tif',IngestionLimits(max_image_header_bytes=budget)).source.page_count,2)
        with self.assertRaises(UploadRejected): inventory_stream(io.BytesIO(data),'x.tif',IngestionLimits(max_image_header_bytes=budget-1))

    def test_duplicate_different_values_both_orders(self):
        for endian in ('<','>'):
            for tag in (256,257):
                for first,second in ((2,12001),(12001,2)):
                    data=bytearray(fixture(endian,8,256))
                    original=8+2+(0 if tag==256 else 12)
                    duplicate=8+2+2*12
                    struct.pack_into(endian+'I',data,original+8,first)
                    struct.pack_into(endian+'HHII',data,duplicate,tag,4,1,second)
                    with self.subTest(endian=endian,tag=tag,values=(first,second)):
                        with self.assertRaisesRegex(UploadRejected,'duplicate TIFF'):
                            inventory_stream(io.BytesIO(data),'x.tif')
                        with self.assertRaisesRegex(ImageHeaderError,'duplicate TIFF'):
                            inspect_image_header(bytes(data),'tiff',max_header_bytes=LIMIT,max_dimension=12000,max_pixels=50000000,max_tiff_pages=100)

    def test_zip_actual_bytes_rejected_before_write_and_resources_closed(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from alfa_document_intelligence import ingestion
        class Snapshot(io.BytesIO):
            instances=[]
            def __init__(self): super().__init__(); self.writes=[]; self.was_closed=False; self.instances.append(self)
            def write(self, value): self.writes.append(bytes(value)); return super().write(value)
            def close(self): self.was_closed=True; super().close()
        class Input(io.BytesIO):
            def __init__(self,data): super().__init__(data); self.was_closed=False
            def close(self): self.was_closed=True; super().close()
        class Archive:
            def __init__(self, infos, inputs): self.infos=infos; self.inputs=iter(inputs); self.was_closed=False
            def __enter__(self): return self
            def __exit__(self,*args): self.was_closed=True
            def infolist(self): return self.infos
            def open(self,info,mode): return next(self.inputs)
        def info(name,size):
            return SimpleNamespace(filename=name,file_size=size,compress_size=size,flag_bits=0,external_attr=0,is_dir=lambda:False)
        # Synthetic streaming source ignores its claimed size, exposing checks
        # ZipExtFile would normally apply itself. Both payloads are non-TIFF.
        for total,items,streams,expected in (
            (100,[info('a.pdf',4)],[b'%PDFx'],[[]]),
            (10,[info('a.pdf',5),info('b.pdf',5)],[b'%PDF-',b'%PDF-x'],[[b'%PDF-'],[]]),
        ):
            Snapshot.instances.clear(); inputs=[Input(x) for x in streams]; arc=Archive(items,inputs)
            with self.subTest(total=total):
                with patch.object(ingestion.zipfile,'ZipFile',return_value=arc), patch.object(ingestion.io,'BytesIO',Snapshot):
                    with self.assertRaises(UploadRejected): ingestion._inventory_archive(object(),IngestionLimits(max_archive_uncompressed_bytes=total))
                self.assertEqual([s.writes for s in Snapshot.instances],expected)
                self.assertTrue(all(s.was_closed for s in Snapshot.instances))
                self.assertTrue(all(s.was_closed for s in inputs))
                self.assertTrue(arc.was_closed)
