"""SIGSTOP a generated-data FUSE daemon; helper responsiveness remains bounded."""
import errno,json,os,signal,subprocess,sys,tempfile,time,shutil
from pathlib import Path
import mount_support
from unittest.mock import patch
base=Path(tempfile.mkdtemp(prefix='immich-hung-fixture-',dir='/tmp'));point=base/'mount'
child=subprocess.Popen([sys.executable,str(Path(__file__).with_name('fixture_mount.py')),str(base)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
try:
 for _ in range(100):
  if child.poll() is not None:raise RuntimeError(child.stderr.read().decode())
  if mount_support.mount_record(point):break
  time.sleep(.05)
 assert mount_support.mount_record(point);assert list(point.iterdir())
 child.send_signal(signal.SIGSTOP);time.sleep(.05)
 alias=base/'Pictures';alias.symlink_to(base,target_is_directory=True)
 start=time.monotonic()
 with patch.object(mount_support.Path,'iterdir',side_effect=AssertionError('helper may not list hung leaf')):
  try:mount_support.prepare_mountpoint(alias/'mount',active=lambda:True,probe_timeout=.15)
  except OSError as error:assert error.errno==errno.ETIMEDOUT
  else:raise AssertionError('Hung own mount unexpectedly accepted')
 elapsed=time.monotonic()-start;assert elapsed<1.5;assert mount_support.mount_record(point)[1]=='Immich'
 print(json.dumps({'generated_fuse_daemon_suspended':True,'probe_timeout_returned':True,'mount_left_untouched':True,'parent_symlink_resolved':True,'no_helper_leaf_listing':True,'seconds':round(elapsed,3)}))
finally:
 if child.poll() is None:child.send_signal(signal.SIGCONT)
 if mount_support.mount_record(point):subprocess.run(['fusermount3','-u',str(point)],capture_output=True,timeout=10)
 try:child.wait(timeout=3)
 except subprocess.TimeoutExpired:child.kill();child.wait(timeout=3)
 shutil.rmtree(base)
