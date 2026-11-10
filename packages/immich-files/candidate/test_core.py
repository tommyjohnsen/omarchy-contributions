import base64,errno,hashlib,os,subprocess,tempfile,time,unittest
from pathlib import Path
from immich_files import API,Cache,Filesystem,Response,CHUNK,asset_id,safe_name
A='11111111-1111-4111-8111-111111111111';B='22222222-2222-4222-8222-222222222222';C='33333333-3333-4333-8333-333333333333'
class FakeAPI:
 def __init__(self):self.downloads=0;self.bytes_sent=0;self.searches=[];self.mode=None
 def data_for(self,id):return b'a'*40 if id==A else b'b'*40
 def row(self,id=A,data=None):
  data=data if data is not None else self.data_for(id)
  return {'id':id,'originalFileName':'photo.jpg','fileCreatedAt':'2025-01-01T00:00:00.000Z','checksum':base64.b64encode(hashlib.sha1(data).digest()).decode(),'exifInfo':{'fileSizeInByte':len(data)}}
 def size(self,row,deadline=None):return row['exifInfo']['fileSizeInByte']
 def albums(self):return [(C,'../album<img>')]
 def search(self,filters,cursor=None):
  self.searches.append((filters,cursor));return [self.row(B if cursor else A)],None if cursor else 'next-token'
 def download(self,row,start,end,deadline):
  self.downloads+=1;data=self.data_for(row['id']);body=data[start:end+1]
  if self.mode=='timeout':raise OSError(errno.ETIMEDOUT,'fixture timeout')
  status=206;content_range=f'bytes {start}-{end}/{len(data)}'
  if self.mode=='ignore':status=200;body=data
  if self.mode=='bad-range':content_range='bytes 9-20/99'
  if self.mode=='truncated':body=body[:-1]
  if self.mode=='oversized':body+=b'x'
  self.bytes_sent+=len(body)
  return Response(status,{'content-range':content_range},body)

class CoreTests(unittest.TestCase):
 def cache(self,cap=64,api=None):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
  api=api or FakeAPI();c=Cache(Path(tmp.name)/'objects',api,cap=cap,reserve=0)
  return api,c
 def test_lazy_listing_and_cursor(self):
  api,c=self.cache();fs=Filesystem(api,c)
  self.assertEqual([x[0] for x in fs.listing(1)],['Albums','Favorites','Recent']);self.assertEqual(api.searches,[])
  rows=fs.listing(2);self.assertEqual(api.downloads,0);self.assertEqual(len(api.searches),1)
  fs.listing(next(i for n,i in rows if n=='Next page'));self.assertEqual(api.searches[-1][1],'next-token');self.assertEqual(api.downloads,0)
 def test_cache_cap_and_reuse(self):
  api,c=self.cache();self.assertEqual(c.read(api.row(),0,10),b'a'*10)
  self.assertEqual(c.read(api.row(),0,10),b'a'*10);self.assertEqual(api.downloads,1)
  self.assertEqual(c.read(api.row(B),0,10),b'b'*10);self.assertEqual(sum(s.st_size for _,s in c.owned()),40)
 def test_sniff_fetches_one_bounded_chunk(self):
  class Big(FakeAPI):
   def data_for(self,id):return b'X'*(CHUNK*2+19)
  api,c=self.cache(cap=CHUNK*2,api=Big());row=api.row()
  self.assertEqual(c.read(row,0,4096),b'X'*4096)
  self.assertEqual(api.bytes_sent,CHUNK);self.assertEqual(api.downloads,1)
  self.assertEqual(c.read(row,CHUNK-3,8),b'X'*8);self.assertEqual(api.downloads,2)
 def test_invalid_ranges_and_failures_leave_no_partial(self):
  class Big(FakeAPI):
   def data_for(self,id):return b'X'*(CHUNK+1)
  for mode in ['ignore','bad-range','truncated','oversized','timeout']:
   with self.subTest(mode=mode):
    api,c=self.cache(cap=CHUNK*2,api=Big());api.mode=mode
    with self.assertRaises(OSError):c.read(api.row(),0,4096)
    self.assertFalse(any(p.name.endswith(('.bin','.part'))for p in c.path.iterdir()))
 def test_symlink_not_followed(self):
  api,c=self.cache();outside=c.path.parent/'private';outside.write_bytes(b'private')
  (c.path/c.key(api.row(),0)).symlink_to(outside)
  with self.assertRaises(PermissionError):c.read(api.row(),0,10)
  self.assertEqual(outside.read_bytes(),b'private')
 def test_free_space_and_unknown_files(self):
  api,c=self.cache();c.reserve=c.free()+1
  with self.assertRaises(OSError)as e:c.read(api.row(),0,10)
  self.assertEqual(e.exception.errno,errno.ENOSPC);self.assertEqual(api.downloads,0)
  c.reserve=0;(c.path/'do-not-delete').write_bytes(b'z'*64)
  with self.assertRaises(OSError):c.read(api.row(),0,10)
  self.assertEqual((c.path/'do-not-delete').read_bytes(),b'z'*64)
 def test_startup_cap_and_abandoned_parts(self):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);p=Path(tmp.name)/'cache';p.mkdir()
  api=FakeAPI();fingerprint=hashlib.sha256((api.row()['checksum']+'|').encode()).hexdigest()[:16]
  name=A+'-'+fingerprint+'-0000000000000000.bin'
  (p/name).write_bytes(b'x'*80);(p/(name+'.0123456789ab.part')).write_bytes(b'x'*10)
  (p/'unrelated.txt').write_bytes(b'ok')
  c=Cache(p,api,cap=64,reserve=0)
  self.assertLessEqual(c.usage(),64);self.assertEqual((p/'unrelated.txt').read_bytes(),b'ok')
  self.assertFalse(any(x.name.endswith('.part')for x in p.iterdir()))
 def test_invalid_names_and_paths(self):
  for value in ['../secret','00000000-0000-0000-0000-000000000000']:
   with self.assertRaises(ValueError):asset_id(value)
  self.assertNotIn('/',safe_name('../a/b\x00'));self.assertNotIn('\\',safe_name('..\\file'))
 def test_transport_guards_and_timeout(self):
  captured={}
  def runner(args,**kw):
   captured.update(args=args,kw=kw)
   return subprocess.CompletedProcess(args,0,b'HTTP/1.1 302 Found\r\nLocation: http://evil.invalid\r\n\r\n',b'')
  api=API('public-test-key',runner)
  with self.assertRaises(OSError):api.request('GET','/albums')
  self.assertNotIn('public-test-key',' '.join(captured['args']))
  self.assertNotIn('--location',captured['args']);self.assertIn('--max-time',captured['args']);self.assertIn('--max-filesize',captured['args'])
  self.assertIn('--noproxy',captured['args']);self.assertEqual(captured['args'][1],'--disable')
  self.assertIn(b'public-test-key',captured['kw']['input']);self.assertLessEqual(captured['kw']['timeout'],22)
  with self.assertRaises(PermissionError):api.request('DELETE','/assets/'+A+'/original')
  with self.assertRaises(PermissionError):api.request('GET','//evil.invalid/path')
  def timeout(*a,**kw):raise subprocess.TimeoutExpired(a,kw['timeout'])
  with self.assertRaises(OSError)as e:API('public-test-key',timeout).request('GET','/albums')
  self.assertEqual(e.exception.errno,errno.ETIMEDOUT)
 def test_api_rejects_ignored_large_range_body(self):
  def runner(args,**kw):return subprocess.CompletedProcess(args,0,b'HTTP/1.1 200 OK\r\n\r\n'+b'x'*(CHUNK+1),b'')
  with self.assertRaises(OSError):API('public-test-key',runner).request('GET','/assets/'+A+'/original',byte_range=(0,CHUNK-1))

if __name__=='__main__':unittest.main()
