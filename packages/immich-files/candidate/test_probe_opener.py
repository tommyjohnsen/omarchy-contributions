"""Optional desktop opening and bounded nonempty capability-probe fixtures."""
import errno,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import connect_immich_files as helper
from immich_files import PAGE
from test_core import A
class Probe:
 def __init__(self,count=4,nonempty=3):self.count=count;self.nonempty=nonempty;self.calls=[];self.ranges=[];self.deadlines=[]
 def albums(self,deadline=None):self.deadlines.append(deadline);return []
 def search(self,filters,deadline=None):self.deadlines.append(deadline);return [{'id':A,'position':i} for i in range(self.count)],None
 def size(self,row,deadline=None):self.deadlines.append(deadline);self.calls.append(row['position']);return int(row['position']==self.nonempty)
 def request(self,*args,**kwargs):self.deadlines.append(kwargs['deadline']);self.ranges.append(kwargs['byte_range']);return type('Response',(),{'status':206,'headers':{'content-range':'bytes 0-0/1'},'body':b'x'})()
class ProbeOpenerTests(unittest.TestCase):
 def test_three_zero_assets_do_not_hide_fourth_nonempty(self):
  api=Probe();self.assertEqual(helper.validate(api),0);self.assertEqual(api.calls,[0,1,2,3]);self.assertEqual(api.ranges,[(0,0)])
  self.assertEqual(len(set(api.deadlines)),1)
 def test_candidate_cap_remains_bounded(self):
  api=Probe(count=PAGE+5,nonempty=PAGE+1);helper.validate(api)
  self.assertEqual(len(api.calls),PAGE);self.assertFalse(api.ranges)
 def test_total_probe_budget_expires_before_per_asset_work(self):
  api=Probe()
  with patch.object(helper.time,'monotonic',side_effect=[0,26]),self.assertRaises(OSError) as error:helper.validate(api)
  self.assertEqual(error.exception.errno,errno.ETIMEDOUT);self.assertFalse(api.calls)
 def test_missing_desktop_opener_does_not_invalidate_connection(self):
  with patch.object(helper.shutil,'which',return_value=None),patch.object(helper.subprocess,'Popen') as popen:
   self.assertFalse(helper.open_folder(Path('/public-fixture')));popen.assert_not_called()
 def test_opener_process_failure_is_best_effort(self):
  with patch.object(helper.shutil,'which',return_value='/usr/bin/xdg-open'),patch.object(helper.subprocess,'Popen',side_effect=FileNotFoundError):
   self.assertFalse(helper.open_folder(Path('/public-fixture')))
if __name__=='__main__':unittest.main()
