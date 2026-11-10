"""Bounded probes, accurate contract, actual umask and coroutine handle fixtures."""
from pathlib import Path
import errno,json,os,tempfile,threading,time,unittest,io
from unittest.mock import patch
import trio
import mount_support as support
from immich_files import Cache,Filesystem
from test_core import FakeAPI,A,B
class V6Tests(unittest.TestCase):
 def test_new_private_mount_under_umask022_is0700(self):
  with tempfile.TemporaryDirectory() as d,patch.object(support,'mount_record',return_value=None):
   previous=os.umask(0o022)
   try:point=Path(d)/'mount';self.assertFalse(support.prepare_mountpoint(point));self.assertEqual(point.stat().st_mode&0o777,0o700)
   finally:os.umask(previous)
 def test_actual_child_probe_timeout_is_bounded(self):
  with patch.object(support,'PROBE_CODE','import time;time.sleep(10)'):
   start=time.monotonic()
   with self.assertRaises(OSError) as error:support.probe_mount('/public-fixture',timeout=.05)
   self.assertEqual(error.exception.errno,errno.ETIMEDOUT);self.assertLess(time.monotonic()-start,1)
 def test_symlink_probe_is_refused_not_called_disconnected(self):
  with tempfile.TemporaryDirectory() as d:
   point=Path(d)/'alias';point.symlink_to(d,target_is_directory=True)
   with self.assertRaises(RuntimeError):support.probe_mount(point)
 def test_official_http_wrapper_is_assets_then_items(self):
  schema=json.loads(Path(__file__).with_name('openapi-v3.3.5-response-envelope.json').read_text())
  self.assertEqual(schema['response_200']['content']['application/json']['schema']['$ref'],'#/components/schemas/SearchResponseDto')
  self.assertEqual(schema['components']['SearchResponseDto']['properties']['assets']['$ref'],'#/components/schemas/SearchAssetResponseDto')
  self.assertEqual(schema['components']['SearchAssetResponseDto']['properties']['items']['type'],'array')
 def test_concurrent_coroutines_allocate_distinct_correct_file_handles(self):
  barrier=threading.Barrier(2)
  class ConcurrentAPI(FakeAPI):
   def search(self,*a,**k):return [self.row(A),self.row(B)],None
   def size(self,row,deadline=None):barrier.wait(timeout=2);return 40
  async def scenario():
   with tempfile.TemporaryDirectory() as d:
    api=ConcurrentAPI();fs=Filesystem(api,Cache(Path(d)/'cache',api,cap=1024,reserve=0));rows=fs.listing(2);opened={}
    async def op(inode):opened[fs.nodes[inode].row['id']]=await fs.open(inode,os.O_RDONLY)
    async with trio.open_nursery() as nursery:
     for _,inode in rows:nursery.start_soon(op,inode)
    self.assertEqual(len({value.fh for value in opened.values()}),2)
    for asset,handle in opened.items():self.assertEqual(fs.handles[handle.fh]['id'],asset)
  trio.run(scenario)
 def test_kernel_mountinfo_parsing_is_escaped_and_fail_closed(self):
  valid=rb'10 1 0:42 / /with\040space rw optional:unknown - fuse Immich rw'+b'\n'
  with patch('builtins.open',return_value=io.BytesIO(valid)):
   self.assertEqual(support.mount_record('/with space'),['fuse','Immich'])
  with patch('builtins.open',return_value=io.BytesIO(b'malformed\n')):
   with self.assertRaises(RuntimeError):support.mount_record('/fixture')
 def test_mountinfo_rawCR_in_source_and_path_is_preserved(self):
  value=b'10 1 0:42 / /raw\rpath rw - fuse source\rname rw\n'
  with patch('builtins.open',return_value=io.BytesIO(value)):
   self.assertEqual(support.mount_record('/raw\rpath'),['fuse','source\rname'])
 def test_mountinfo_empty_records_and_fields_are_refused(self):
  valid=b'10 1 0:42 / / rw - fuse Immich rw\n'
  for value in [valid+b'\n',valid.replace(b' rw -',b' rw  -')]:
   with patch('builtins.open',return_value=io.BytesIO(value)),self.assertRaises(RuntimeError):support.mount_record('/fixture')
 def test_mountinfo_VT_FF_85_are_literal_bytes(self):
  for byte in [11,12,0x85]:
   point=b'/raw'+bytes([byte])+b'path'
   with patch('builtins.open',return_value=io.BytesIO(b'10 1 0:42 / '+point+b' rw - fuse Immich rw\n')):
    self.assertEqual(support.mount_record(os.fsdecode(point)),['fuse','Immich'])
if __name__=='__main__':unittest.main()
