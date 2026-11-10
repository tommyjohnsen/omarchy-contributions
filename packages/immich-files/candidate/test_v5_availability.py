"""Availability regression fixtures for actual Claude V4 findings."""
from pathlib import Path
import errno,os,tempfile,threading,time,unittest
from unittest.mock import patch
import pyfuse3,trio
from immich_files import Cache,Filesystem
from test_core import FakeAPI,A,B
class Availability(unittest.TestCase):
 def test_directory_handle_keeps_snapshot_across_refresh(self):
  class Mutable(FakeAPI):
   changed=False
   def search(self,*a,**k):return [self.row(B if self.changed else A)],None
  async def scenario():
   with tempfile.TemporaryDirectory() as d:
    api=Mutable();fs=Filesystem(api,Cache(Path(d)/'cache',api,cap=1024,reserve=0));handle=await fs.opendir(2)
    api.changed=True;fs.nodes[2].loaded=0;fs.listing(2)
    rows=[]
    with patch.object(pyfuse3,'readdir_reply',side_effect=lambda token,name,*args:rows.append(name.decode()) or True):await fs.readdir(handle,0,object())
    self.assertEqual(len(rows),1);self.assertIn(A,rows[0]);self.assertNotIn(B,rows[0])
    await fs.releasedir(handle);self.assertNotIn(handle,fs.directory_handles)
  trio.run(scenario)
 def test_transient_and_auth_failures_propagate_instead_of_hiding_files(self):
  for failure in [errno.EIO,errno.EACCES,errno.EHOSTUNREACH]:
   class Broken(FakeAPI):
    def search(self,*a,**k):return [self.row(A)],None
    def size(self,row,deadline=None):raise OSError(failure,'public fixture')
   async def scenario():
    with tempfile.TemporaryDirectory() as d:
     api=Broken();fs=Filesystem(api,Cache(Path(d)/'cache',api,cap=1024,reserve=0));handle=await fs.opendir(2)
     with self.assertRaises(pyfuse3.FUSEError) as error:await fs.readdir(handle,0,object())
     self.assertEqual(error.exception.errno,failure)
   trio.run(scenario)
 def test_slow_content_reads_leave_metadata_capacity(self):
  started=threading.Event()
  class SlowCache:
   def read(self,row,off,size,deadline):started.set();time.sleep(.2);return b'x'
  async def scenario():
   with tempfile.TemporaryDirectory() as d:
    fs=Filesystem(FakeAPI(),SlowCache());fs.handles[1]=fs.api.row()
    async with trio.open_nursery() as nursery:
     nursery.start_soon(fs.read,1,0,1);nursery.start_soon(fs.read,1,0,1)
     while not started.is_set():await trio.sleep(.001)
     start=trio.current_time();attr=await fs.getattr(1)
     self.assertEqual(attr.st_ino,1);self.assertLess(trio.current_time()-start,.1)
  trio.run(scenario)
 def test_slow_search_does_not_hold_structural_lock(self):
  started=threading.Event()
  class Slow(FakeAPI):
   def search(self,*a,**k):started.set();time.sleep(.15);return super().search(*a,**k)
  async def scenario():
   with tempfile.TemporaryDirectory() as d:
    api=Slow();fs=Filesystem(api,Cache(Path(d)/'cache',api,cap=1024,reserve=0))
    async with trio.open_nursery() as nursery:
     nursery.start_soon(fs.worker,fs.listing,2)
     while not started.is_set():await trio.sleep(.001)
     start=trio.current_time();self.assertTrue(await fs.worker(fs.listing,1));self.assertLess(trio.current_time()-start,.1)
  trio.run(scenario)
if __name__=='__main__':unittest.main()
