"""SIGKILL/remount generated FUSE only; no keyring, real service or server."""
import json,os,signal,subprocess,sys,tempfile,time,shutil
from pathlib import Path
from mount_support import mount_record
base=Path(tempfile.mkdtemp(prefix='immich-stale-fixture-',dir='/tmp'));point=base/'mount';children=[]
def start():
 child=subprocess.Popen([sys.executable,str(Path(__file__).with_name('fixture_mount.py')),str(base)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE);children.append(child)
 for _ in range(100):
  if child.poll() is not None:raise RuntimeError(child.stderr.read().decode())
  if mount_record(point):
   try:
    assert sorted(p.name for p in point.iterdir())==['Albums','Favorites','Recent'];return child
   except OSError:pass
  time.sleep(.05)
 raise AssertionError('Fixture mount did not become ready')
try:
 first=start();first.kill();first.wait(timeout=3)
 assert mount_record(point)[1]=='Immich'
 try:list(point.iterdir())
 except OSError:pass
 else:raise AssertionError('Killed fixture unexpectedly still usable')
 second=start();assert second.poll() is None
 print(json.dumps({'generated_fuse_sigkill':True,'dead_own_mount_recovered':True,'remounted_listing_matches':True}))
finally:
 if mount_record(point):subprocess.run(['fusermount3','-u',str(point)],capture_output=True,timeout=10)
 for child in children:
  if child.poll() is None:child.terminate()
  try:child.wait(timeout=3)
  except subprocess.TimeoutExpired:child.kill();child.wait(timeout=2)
 shutil.rmtree(base)
