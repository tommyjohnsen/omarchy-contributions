"""Real child-process transport limits and configuration boundary fixtures."""
import errno,os,subprocess,sys,time,unittest
import bounded_curl
from immich_files import API,server_origin
class HardLimits(unittest.TestCase):
 def child(self,code,**kwargs):
  return bounded_curl.run([sys.executable,'-c',code],input=b'public-fixture-key',timeout=.3,env=os.environ.copy(),output_limit=1024,**kwargs)
 def test_stdout_hard_limit(self):
  with self.assertRaises(OSError) as caught:self.child('import os;os.write(1,b"a"*10000)')
  self.assertEqual(caught.exception.errno,errno.EOVERFLOW)
 def test_stderr_hard_limit(self):
  with self.assertRaises(OSError) as caught:self.child('import os;os.write(2,b"a"*10000)',stderr_limit=1024)
  self.assertEqual(caught.exception.errno,errno.EOVERFLOW)
 def test_blocked_child_total_deadline(self):
  start=time.monotonic()
  with self.assertRaises(subprocess.TimeoutExpired):self.child('import time;time.sleep(10)')
  self.assertLess(time.monotonic()-start,2)
 def test_input_private_diagnostics_discarded(self):
  result=self.child('import sys;data=sys.stdin.buffer.read();sys.stderr.buffer.write(data);sys.stdout.buffer.write(b"ok")')
  self.assertEqual(result.stdout,b'ok');self.assertEqual(result.stderr,b'');self.assertNotIn('public-fixture-key',str(result.args))
 def test_https_origin_only(self):
  for value in ['http://example.invalid','https://u:p@example.invalid','https://example.invalid/path','https://example.invalid?key=x','https://example.invalid#x','https://example.invalid\n','https://example.invalid:0','https://example.invalid:broken']:
   with self.subTest(value=value),self.assertRaises(ValueError):server_origin(value)
  self.assertEqual(server_origin('https://example.invalid:443/'),'https://example.invalid:443')
 def test_zero_byte_metadata(self):
  api=API('public-fixture-key',lambda *a,**kw: (_ for _ in ()).throw(AssertionError('unexpected network')))
  self.assertEqual(api.size({'id':'11111111-1111-4111-8111-111111111111','exifInfo':{'fileSizeInByte':0}}),0)
if __name__=='__main__':unittest.main()
