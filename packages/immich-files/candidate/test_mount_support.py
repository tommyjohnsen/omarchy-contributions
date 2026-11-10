"""No mount operations: identity, dead-mount, and foreign-mount boundary fixtures."""
import errno,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import mount_support as support
class MountSupportTests(unittest.TestCase):
 def test_owned_private_empty_directory(self):
  with tempfile.TemporaryDirectory() as base,patch.object(support,'mount_record',return_value=None):
   self.assertFalse(support.prepare_mountpoint(Path(base)/'mount'))
 def test_foreign_mount_not_touched(self):
  with patch.object(support,'mount_record',return_value=['fuse','Other']),patch.object(support.subprocess,'run') as run:
   with self.assertRaises(RuntimeError):support.prepare_mountpoint('/unused')
   run.assert_not_called()
 def test_symlink_and_nonempty_refused(self):
  with tempfile.TemporaryDirectory() as base,patch.object(support,'mount_record',return_value=None):
   point=Path(base)/'mount';point.symlink_to(base)
   with self.assertRaises(RuntimeError):support.prepare_mountpoint(point)
   point.unlink();point.mkdir(mode=0o700);(point/'data').write_bytes(b'public')
   with self.assertRaises(RuntimeError):support.prepare_mountpoint(point)
 def test_live_own_mount_not_unmounted(self):
  with tempfile.TemporaryDirectory() as base,patch.object(support,'mount_record',return_value=['fuse','Immich']),patch.object(support.subprocess,'run') as run:
   self.assertTrue(support.prepare_mountpoint(base));run.assert_not_called()
 def test_dead_active_mount_not_unmounted_by_helper(self):
  with tempfile.TemporaryDirectory() as base,patch.object(support,'mount_record',return_value=['fuse','Immich']),patch.object(support,'probe_mount',return_value=False),patch.object(support.subprocess,'run') as run:
   with self.assertRaises(support.DisconnectedMountActive):support.prepare_mountpoint(base,active=lambda:True)
   run.assert_not_called()
if __name__=='__main__':unittest.main()
