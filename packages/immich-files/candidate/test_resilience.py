"""Read-only availability regressions; no real server or stored credential."""
from pathlib import Path
import errno,tempfile,unittest,threading,time
from unittest.mock import patch
import pyfuse3,trio
from immich_files import Cache,Filesystem
from test_core import FakeAPI,A,B
class ResilienceTests(unittest.TestCase):
 def test_low_space_allows_metadata_but_content_reads_still_fail_closed(self):
  class LowSpace(Cache):
   def free(self):return 0
  with tempfile.TemporaryDirectory() as directory:
   api=FakeAPI();cache=LowSpace(Path(directory)/'cache',api,cap=64,reserve=1)
   fs=Filesystem(api,cache)
   self.assertTrue(fs.listing(1));self.assertEqual(api.downloads,0)
   with self.assertRaises(OSError) as error:cache.read(api.row(),0,10)
   self.assertEqual(error.exception.errno,errno.ENOSPC);self.assertEqual(api.downloads,0)
 def test_one_unstatable_original_does_not_hide_other_directory_entries(self):
  class MissingSize(FakeAPI):
   def search(self,filters,cursor=None):return [self.row(A),self.row(B)],None
   def size(self,row,deadline=None):
    if row['id']==A:raise OSError(errno.ENOENT,'fixture missing original')
    return super().size(row)
  with tempfile.TemporaryDirectory() as directory:
   api=MissingSize();cache=Cache(Path(directory)/'cache',api,cap=64,reserve=0);fs=Filesystem(api,cache)
   replied=[]
   def reply(token,name,attrs,offset):replied.append(name.decode());return True
   async def scenario():await fs.readdir(await fs.opendir(2),0,object())
   with patch.object(pyfuse3,'readdir_reply',reply):trio.run(scenario)
   self.assertEqual(len(replied),1);self.assertIn(B,replied[0]);self.assertEqual(api.downloads,0)
 def test_directory_timeout_is_not_swallowed_as_an_unavailable_single_asset(self):
  class Timeout(FakeAPI):
   def search(self,filters,cursor=None):return [self.row(A)],None
   def size(self,row,deadline=None):raise OSError(errno.ETIMEDOUT,'fixture deadline')
  with tempfile.TemporaryDirectory() as directory:
   api=Timeout();cache=Cache(Path(directory)/'cache',api,cap=64,reserve=0);fs=Filesystem(api,cache)
   async def scenario():
    with self.assertRaises(pyfuse3.FUSEError) as error:await fs.readdir(await fs.opendir(2),0,object())
    self.assertEqual(error.exception.errno,errno.ETIMEDOUT)
   with patch.object(pyfuse3,'readdir_reply',return_value=True):trio.run(scenario)
 def test_whole_directory_page_has_a_deadline_over_slow_size_lookups(self):
  finished=threading.Event()
  class Slow(FakeAPI):
   def search(self,filters,cursor=None):return [self.row(A)],None
   def size(self,row,deadline=None):
    try:time.sleep(.15);return super().size(row)
    finally:finished.set()
  with tempfile.TemporaryDirectory() as directory:
   api=Slow();cache=Cache(Path(directory)/'cache',api,cap=64,reserve=0);fs=Filesystem(api,cache)
   async def scenario():
    start=trio.current_time()
    with self.assertRaises(pyfuse3.FUSEError) as error:await fs.readdir(await fs.opendir(2),0,object())
    self.assertEqual(error.exception.errno,errno.ETIMEDOUT)
    self.assertLess(trio.current_time()-start,.12)
   with patch('immich_files.DIRECTORY_TIMEOUT',.03),patch.object(pyfuse3,'readdir_reply',return_value=True):trio.run(scenario)
   self.assertTrue(finished.wait(1),'Abandoned fixture worker did not finish')
 def test_external_cancellation_propagates_and_does_not_become_eio(self):
  finished=threading.Event()
  class Slow(FakeAPI):
   def search(self,filters,cursor=None):return [self.row(A)],None
   def size(self,row,deadline=None):
    try:time.sleep(.15);return super().size(row)
    finally:finished.set()
  with tempfile.TemporaryDirectory() as directory:
   api=Slow();cache=Cache(Path(directory)/'cache',api,cap=64,reserve=0);fs=Filesystem(api,cache)
   async def scenario():
    with trio.move_on_after(.03) as scope:await fs.readdir(await fs.opendir(2),0,object())
    self.assertTrue(scope.cancelled_caught,'Cancellation was converted or swallowed')
   with patch.object(pyfuse3,'readdir_reply',return_value=True):trio.run(scenario)
   self.assertTrue(finished.wait(1),'Cancelled fixture worker did not finish')
 def test_page_queue_timeout_keeps_thread_limit_and_recovers_after_workers_finish(self):
  lock=threading.Lock();activity={'active':0,'maximum':0}
  class Slow(FakeAPI):
   def search(self,filters,cursor=None):return [self.row(A)],None
   def size(self,row,deadline=None):
    with lock:
     activity['active']+=1;activity['maximum']=max(activity['maximum'],activity['active'])
    try:time.sleep(.15);return super().size(row)
    finally:
     with lock:activity['active']-=1
  with tempfile.TemporaryDirectory() as directory:
   api=Slow();cache=Cache(Path(directory)/'cache',api,cap=64,reserve=0);fs=Filesystem(api,cache);errors=[]
   async def request():
    try:await fs.readdir(await fs.opendir(2),0,object())
    except pyfuse3.FUSEError as error:errors.append(error.errno)
   async def scenario():
    async with trio.open_nursery() as nursery:
     for _ in range(3):nursery.start_soon(request)
    self.assertEqual(errors,[errno.ETIMEDOUT]*3)
    await trio.sleep(.2)
    self.assertEqual(fs.limiter.borrowed_tokens,0)
    self.assertLessEqual(activity['maximum'],2);self.assertEqual(activity['active'],0)
    # The same filesystem remains usable after the abandoned workers finish.
    self.assertTrue(await fs.worker(fs.listing,1))
   with patch('immich_files.DIRECTORY_TIMEOUT',.03),patch.object(pyfuse3,'readdir_reply',return_value=True):trio.run(scenario)
if __name__=='__main__':unittest.main()
