import json,sys
from pathlib import Path
import pyfuse3,trio
from immich_files import Filesystem,Cache
from test_core import FakeAPI
import mount_support
base=Path(sys.argv[1]);base.mkdir(parents=True,exist_ok=True)
class StatsAPI(FakeAPI):
 def save(self):
  (base/'counts.json').write_text(json.dumps({'downloads':self.downloads,'searches':len(self.searches)}))
 def albums(self):
  out=super().albums();self.save();return out
 def search(self,*args,**kw):
  out=super().search(*args,**kw);self.save();return out
 def download(self,*args,**kw):
  out=super().download(*args,**kw);self.save();return out
api=StatsAPI();api.save()
point=base/'mount'
if mount_support.prepare_mountpoint(point,recover_while_active=True):raise RuntimeError('Fixture already mounted')
fs=Filesystem(api,Cache(base/'cache',api,cap=1024*1024,reserve=0))
pyfuse3.init(fs,str(point),set(pyfuse3.default_options)|{'fsname=Immich','ro','nodev','nosuid','noexec'})
try:trio.run(pyfuse3.main)
finally:pyfuse3.close(unmount=True)
