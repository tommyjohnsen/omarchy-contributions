"""Generated-data FUSE fixture with deliberately slow metadata-size lookups."""
import sys,time,json
from pathlib import Path
import pyfuse3,trio,immich_files
from immich_files import Filesystem,Cache
from test_core import FakeAPI,A,B,C
base=Path(sys.argv[1]);base.mkdir(parents=True,exist_ok=True)
class SlowAPI(FakeAPI):
 def row(self,*args,**kwargs):
  row=super().row(*args,**kwargs);row.pop('exifInfo',None);return row
 def search(self,filters,cursor=None):return [self.row(A),self.row(B),self.row(C)],None
 def size(self,row,deadline=None):
  if '_size' not in row:
   time.sleep(.035);row['_size']=len(self.data_for(row['id']))
  return row['_size']
api=SlowAPI();point=base/'mount';point.mkdir(mode=0o700)
class StatsFilesystem(Filesystem):
 async def readdir(self,*args):
  self.calls=getattr(self,'calls',0)+1
  try:return await super().readdir(*args)
  finally:(base/'readdir-calls.json').write_text(json.dumps({'calls':self.calls}))
immich_files.DIRECTORY_TIMEOUT=.05
filesystem=StatsFilesystem(api,Cache(base/'cache',api,cap=1024*1024,reserve=0))
pyfuse3.init(filesystem,str(point),set(pyfuse3.default_options)|{'fsname=ImmichSlowFixture','ro','nodev','nosuid','noexec'})
try:trio.run(pyfuse3.main)
finally:pyfuse3.close(unmount=True)
