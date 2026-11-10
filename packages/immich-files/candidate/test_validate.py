"""Real API transport validation uses eligible rows and strict single-byte Range."""
import json,subprocess,unittest
from immich_files import API
from connect_immich_files import validate
from test_core import A,B,C
class ValidateTests(unittest.TestCase):
 def api(self,status=206,content_range='bytes 0-0/1'):
  self.originals=[]
  def runner(args,**kwargs):
   lines=kwargs['input'].decode().splitlines();url=json.loads(next(line.split(' = ',1)[1] for line in lines if line.startswith('url = ')))
   if url.endswith('/albums'):body=[]
   elif url.endswith('/search/metadata'):body={'assets':{'items':[{'id':A,'isOffline':True},{'id':C,'isTrashed':True},{'id':B,'exifInfo':{'fileSizeInByte':1}}],'nextCursor':None}}
   else:
    self.originals.append(url)
    return subprocess.CompletedProcess(args,0,f'HTTP/1.1 {status} Fixture\r\nContent-Range: {content_range}\r\n\r\n'.encode()+b'x',b'')
   return subprocess.CompletedProcess(args,0,b'HTTP/1.1 200 OK\r\n\r\n'+json.dumps(body).encode(),b'')
  return API('public-fixture-key',runner)
 def test_offline_and_trashed_assets_are_skipped_before_original_probe(self):
  self.assertEqual(validate(self.api()),0);self.assertEqual(len(self.originals),1);self.assertIn(B,self.originals[0]);self.assertNotIn(A,self.originals[0])
 def test_ignored_or_incorrect_range_is_not_accepted(self):
  for status,content_range in [(200,'bytes 0-0/1'),(206,'bytes 0-0/999')]:
   with self.subTest(status=status,range=content_range):
    with self.assertRaises(RuntimeError):validate(self.api(status,content_range))
 def test_zero_byte_asset_is_skipped_without_invalid_range(self):
  class ZeroAPI:
   def albums(self,deadline=None):return []
   def search(self,filters,deadline=None):return [{'id':A},{'id':B}],None
   def size(self,row,deadline=None):return 0 if row['id']==A else 1
   def request(self,method,path,**kwargs):
    self.path=path
    return type('Response',(),{'status':206,'headers':{'content-range':'bytes 0-0/1'},'body':b'x'})()
  api=ZeroAPI();self.assertEqual(validate(api),0);self.assertIn(B,api.path)
if __name__=='__main__':unittest.main()
