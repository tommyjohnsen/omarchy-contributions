"""Kernel/FUSE enumeration resumes after deadline-limited short directory replies."""
from pathlib import Path
import json,os,shutil,subprocess,sys,tempfile,time
base=Path(tempfile.mkdtemp(prefix='immich-slow-fixture-'));point=base/'mount'
p=subprocess.Popen([sys.executable,str(Path(__file__).with_name('fixture_slow_mount.py')),str(base)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
try:
 for _ in range(60):
  if point.exists() and os.path.ismount(point):break
  if p.poll() is not None:raise RuntimeError(p.stderr.read())
  time.sleep(.05)
 assert os.path.ismount(point),'slow fixture did not mount'
 start=time.monotonic()
 names=os.listdir(point/'Recent')
 elapsed=time.monotonic()-start
 assert len(names)==3,names
 calls=json.loads((base/'readdir-calls.json').read_text())['calls']
 assert calls>=2,'Expected the kernel to resume a partial directory response'
 assert elapsed<2,elapsed
 print(json.dumps({'real_fuse_partial_readdir':True,'listed_files':len(names),'readdir_calls':calls,'seconds':round(elapsed,3)}))
finally:
 if point.exists() and os.path.ismount(point):subprocess.run(['fusermount3','-u',str(point)],capture_output=True)
 try:p.wait(timeout=5)
 except subprocess.TimeoutExpired:p.terminate();p.wait(timeout=3)
 errors=p.stderr.read()
 if errors:print(errors[:1000])
 shutil.rmtree(base)
