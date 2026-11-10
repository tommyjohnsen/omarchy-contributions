"""Read-only startup retries, buffered proc reads and bounded parent identity."""
from pathlib import Path
import errno,io,tempfile,time,unittest
from unittest.mock import patch
import connect_immich_files as helper
import mount_support as support
class ReadinessTests(unittest.TestCase):
 def test_transient_probes_retry_without_recovery_or_unmount(self):
  with patch.object(helper,'mount_record',return_value=['fuse','Immich']),patch.object(support,'probe_mount',side_effect=[False,OSError(errno.ENOTCONN,'public fixture'),OSError(errno.EIO,'public fixture'),True]) as probe,patch.object(helper.time,'sleep'),patch.object(helper,'prepare_mountpoint',side_effect=AssertionError('readiness must not recover')),patch.object(support.subprocess,'run',side_effect=AssertionError('readiness must not unmount')):
   helper.wait_until_ready(time.monotonic()+1);self.assertEqual(probe.call_count,4)
 def test_retry_deadline_returns_last_transient_error(self):
  start=time.monotonic()
  with patch.object(helper,'mount_record',return_value=['fuse','Immich']),patch.object(support,'probe_mount',side_effect=OSError(errno.ETIMEDOUT,'public fixture')):
   with self.assertRaises(OSError) as error:helper.wait_until_ready(start+.01)
   self.assertEqual(error.exception.errno,errno.ETIMEDOUT);self.assertLess(time.monotonic()-start,.2)
 def test_foreign_mount_is_refused_without_probe(self):
  with patch.object(helper,'mount_record',return_value=['fuse','Other']),patch.object(support,'probe_mount') as probe:
   with self.assertRaises(RuntimeError):helper.wait_until_ready(time.monotonic()+1)
   probe.assert_not_called()
 def test_parent_resolution_follows_parent_alias_not_leaf(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);real=root/'real';real.mkdir();alias=root/'Pictures';alias.symlink_to(real,target_is_directory=True)
   with patch.object(support.Path,'lstat',side_effect=AssertionError('parent helper must not touch leaf')):
    self.assertEqual(support.canonical_mount_path(alias/'not-created'),real/'not-created')
 def test_parent_resolution_timeout_is_bounded(self):
  start=time.monotonic()
  with patch.object(support,'RESOLVE_PARENT_CODE','import time;time.sleep(10)'):
   with self.assertRaises(OSError) as error:support.canonical_mount_path('/public-fixture',timeout=.05)
   self.assertEqual(error.exception.errno,errno.ETIMEDOUT);self.assertLess(time.monotonic()-start,1)
 def test_buffered_read_collects_short_seq_file_reads_until_eof(self):
  data=b'10 1 0:42 / /other rw - tmpfs source rw\n'+b'11 1 0:43 / /fixture rw - fuse Immich rw\n'
  class ShortRaw(io.RawIOBase):
   def __init__(self):self.position=0;self.calls=0;self.eof=False
   def readable(self):return True
   def readinto(self,view):
    self.calls+=1;part=data[self.position:self.position+7];view[:len(part)]=part;self.position+=len(part)
    if not part:self.eof=True
    return len(part)
  raw=ShortRaw()
  with patch('builtins.open',return_value=io.BufferedReader(raw)),patch.object(support,'canonical_mount_path',return_value=Path('/fixture')):
   self.assertEqual(support.mount_record('/fixture'),['fuse','Immich'])
  self.assertTrue(raw.eof);self.assertGreater(raw.calls,3)
if __name__=='__main__':unittest.main()
