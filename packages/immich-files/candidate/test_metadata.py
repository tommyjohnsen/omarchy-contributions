"""Malformed-record isolation and versioned size-cache identity fixtures."""
from pathlib import Path
import errno,json,subprocess,tempfile,time,unittest,os
import trio
from immich_files import API,Cache,Filesystem
from test_core import FakeAPI,A,B
class MetadataTests(unittest.TestCase):
 def api(self,body):
  def runner(args,**kwargs):return subprocess.CompletedProcess(args,0,b'HTTP/1.1 200 OK\r\n\r\n'+json.dumps(body).encode(),b'')
  return API('public-fixture-key',runner)
 def test_bad_asset_records_do_not_hide_good_rows(self):
  api=self.api({'assets':{'items':[None,{}, {'id':A.replace('-4111-','-7111-')},{'id':A,'_size':999}], 'nextCursor':None}})
  rows,cursor=api.search({});self.assertEqual([r['id'] for r in rows],[A]);self.assertNotIn('_size',rows[0]);self.assertEqual(api.invalid_rows,3)
 def test_bad_album_records_do_not_hide_good_rows(self):
  api=self.api([None,{}, {'id':A,'albumName':None},{'id':A,'albumName':'Valid'}]);self.assertEqual(api.albums(),[(A,'Valid')]);self.assertEqual(api.invalid_rows,3)
 def test_unexpected_response_shapes_are_eio_not_missing_directory(self):
  for body in [[],{}, {'assets':{}},{'assets':{'items':None}}]:
   with self.subTest(body=body):
    with self.assertRaises(OSError) as error:self.api(body).search({})
    self.assertEqual(error.exception.errno,errno.EIO)
 def test_boolean_metadata_size_is_not_accepted_as_one_byte(self):
  calls=[]
  def runner(args,**kwargs):calls.append(args);return subprocess.CompletedProcess(args,0,b'HTTP/1.1 200 OK\r\nContent-Length: 40\r\n\r\n',b'')
  api=API('public-fixture-key',runner);self.assertEqual(api.size({'id':A,'exifInfo':{'fileSizeInByte':True}}),40);self.assertEqual(len(calls),1)
 def test_known_size_survives_metadata_refresh_only_for_same_content_identity(self):
  class RefreshAPI(FakeAPI):
   changed=False
   def search(self,filters,cursor=None):return [self.row(A,b'new-content' if self.changed else None)],None
  with tempfile.TemporaryDirectory() as d:
   api=RefreshAPI();fs=Filesystem(api,Cache(Path(d)/'cache',api,cap=64,reserve=0))
   inode=fs.listing(2)[0][1];fs.nodes[inode].row['_size']=40
   fs.nodes[2].loaded=time.monotonic()-61;fs.listing(2)
   self.assertEqual(fs.nodes[inode].row['_size'],40)
   api.changed=True;fs.nodes[2].loaded=time.monotonic()-61;fs.listing(2)
   new_inode=fs.listing(2)[0][1]
   self.assertNotEqual(new_inode,inode)
   self.assertNotIn('_size',fs.nodes[new_inode].row)
 def test_same_length_replacement_has_new_inode_and_invalidates_kernel_cache(self):
  class MutableAPI(FakeAPI):
   changed=False
   def data_for(self,id):return b'z'*40 if self.changed else b'a'*40
  async def check():
   with tempfile.TemporaryDirectory() as directory:
    api=MutableAPI();fs=Filesystem(api,Cache(Path(directory)/'cache',api,cap=1024,reserve=0))
    old_inode=next(i for n,i in fs.listing(2) if fs.nodes[i].kind=='file');old=await fs.open(old_inode,os.O_RDONLY)
    self.assertFalse(old.keep_cache);self.assertEqual(await fs.read(old.fh,0,40),b'a'*40)
    api.changed=True;fs.nodes[2].loaded=time.monotonic()-61
    new_inode=next(i for n,i in fs.listing(2) if fs.nodes[i].kind=='file');self.assertNotEqual(new_inode,old_inode)
    new=await fs.open(new_inode,os.O_RDONLY);self.assertFalse(new.keep_cache)
    self.assertEqual(await fs.read(new.fh,0,40),b'z'*40)
  trio.run(check)
if __name__=='__main__':unittest.main()
