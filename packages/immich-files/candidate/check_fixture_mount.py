# Codex: despite the historical filename, this mounts public fixture data only.
from pathlib import Path
import os,subprocess,time,json,tempfile,errno,sys
base=Path(tempfile.mkdtemp(prefix='immich-fixture-',dir='/tmp'))
point=base/'mount'
p=subprocess.Popen([sys.executable,str(Path(__file__).with_name('fixture_mount.py')),str(base)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
try:
 for _ in range(50):
  if point.exists() and os.path.ismount(point):break
  if p.poll() is not None:raise RuntimeError(p.stderr.read())
  time.sleep(.1)
 assert os.path.ismount(point),'Fixture did not mount'
 assert sorted(x.name for x in point.iterdir())==['Albums','Favorites','Recent']
 rows=list((point/'Recent').iterdir())
 counts=json.loads((base/'counts.json').read_text());assert counts['downloads']==0
 first=next(x for x in rows if x.name!='Next page')
 assert first.read_bytes()==b'a'*40
 assert first.read_bytes()==b'a'*40
 counts=json.loads((base/'counts.json').read_text());assert counts['downloads']==1
 rejected=[]
 for action in [lambda:first.write_bytes(b'bad'),lambda:(point/'new').mkdir(),lambda:first.unlink()]:
  try:action()
  except OSError as e:
   assert e.errno in (errno.EROFS,errno.EACCES);rejected.append(True)
  else:raise AssertionError('Mutation unexpectedly succeeded')
 next_rows=list((point/'Recent'/'Next page').iterdir());assert next_rows
 assert json.loads((base/'counts.json').read_text())['downloads']==1
 print(json.dumps({'real_fuse_mount':True,'listing_downloads':0,'read_data_matches':True,'cached_second_read':True,'mutations_rejected':len(rejected),'cursor_page_browsing':True}))
finally:
 if point.exists() and os.path.ismount(point):subprocess.run(['fusermount3','-u',str(point)],capture_output=True)
 try:p.wait(timeout=5)
 except subprocess.TimeoutExpired:p.terminate();p.wait(timeout=3)
 stderr=p.stderr.read()
 if stderr:print(stderr[:1200])
 import shutil;shutil.rmtree(base)
