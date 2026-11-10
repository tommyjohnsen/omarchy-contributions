# SPDX-License-Identifier: MIT
"""Import staged files through the real main.py sequence, without preloading torch/model management."""
import argparse,importlib.abc,importlib.util,sys,runpy,os,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--comfyui-root',type=Path,required=True);p.add_argument('--device',type=int,required=True);a=p.parse_args()
root=a.comfyui_root.resolve();package=Path(__file__).resolve().parents[1]
runtime=Path(__file__).resolve().parent/'runtime-real-cli'
for name in ('user','models','input','output','temp'):(runtime/name).mkdir(parents=True,exist_ok=True)
class StagedModules(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname in ('comfy.cli_args','comfy.model_management'):
   return importlib.util.spec_from_file_location(fullname,package/'src'/Path(*fullname.split('.')).with_suffix('.py'))
sys.meta_path.insert(0,StagedModules());sys.path.insert(0,str(root))
sys.argv=[str(root/'main.py'),'--vulkan','--default-device',str(a.device),'--offline','--quick-test-for-ci','--disable-all-custom-nodes','--disable-partner-nodes','--disable-assets','--base-directory',str(runtime),'--user-directory',str(runtime/'user'),'--models-directory',str(runtime/'models'),'--database-url','sqlite:///:memory:']
before=(os.environ.get('CUDA_VISIBLE_DEVICES'),os.environ.get('HIP_VISIBLE_DEVICES'))
try:
 runpy.run_path(str(package/'src/main.py'),run_name='__main__')
except SystemExit as error:
 if error.code not in (None,0):raise
 assert before==(os.environ.get('CUDA_VISIBLE_DEVICES'),os.environ.get('HIP_VISIBLE_DEVICES')),'Vulkan startup remapped CUDA/HIP devices'
 print(json.dumps({'ci_exit':0,'cuda_hip_environment_unchanged':True}))
