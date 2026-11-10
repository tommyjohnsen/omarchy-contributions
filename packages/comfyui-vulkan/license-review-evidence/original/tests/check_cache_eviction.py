"""Exercise actual GPU buffers with ComfyUI's real eviction loop and tiny model stubs."""
import argparse,importlib.util,json,sys,gc
from pathlib import Path
from types import SimpleNamespace
p=argparse.ArgumentParser();p.add_argument('--comfyui-root',type=Path,required=True);a=p.parse_args()
sys.path.insert(0,str(a.comfyui_root.resolve()))
import comfy.options
comfy.options.enable_args_parsing()
sys.argv=[sys.argv[0],'--vulkan','--disable-dynamic-vram','--disable-async-offload','--disable-pinned-memory','--disable-xformers','--use-pytorch-cross-attention']
source=Path(__file__).resolve().parents[1]/'src/comfy/model_management.py'
spec=importlib.util.spec_from_file_location('comfy.model_management',source);mm=importlib.util.module_from_spec(spec);sys.modules['comfy.model_management']=mm;spec.loader.exec_module(mm)
import comfy
comfy.model_management=mm
import torch,torchvulkan
D=mm.get_torch_device();N=32*1024*1024
mm.soft_empty_cache();gc.collect()
def sample():
 return dict(allocated=torchvulkan.memory_allocated(),allocator_reserved=torchvulkan.memory_reserved(),cached=torchvulkan.memory_cached() if hasattr(torchvulkan,'memory_cached') else 0,allocator_unused=torchvulkan.memory_stats().get('allocator_unused_bytes.all.current',0),free_budget=torchvulkan.mem_get_info()[0],reported_available=mm.get_free_memory(D))
samples={'baseline':sample()}
unload_cache_samples=[]
class TinyModel:
 def __init__(self):
  self.device=D;self.tensor=torch.empty(N//4,device=D,dtype=torch.float32)
  self.model=SimpleNamespace(is_dynamic=lambda:False,model=SimpleNamespace())
  self.currently_used=True
 def is_dead(self):return False
 def model_offloaded_memory(self):return 0
 def model_memory(self):return N
 def model_unload(self,amount):
  del self.tensor;gc.collect();torchvulkan.synchronize();unload_cache_samples.append(sample());return True
models=[TinyModel(),TinyModel()];torchvulkan.synchronize();samples['two_models']=sample()
# Need only8MiB more; one32MiB model would suffice if cached memory were counted/released.
required=mm.get_free_memory(D)+8*1024*1024
mm.cleanup_models_gc=lambda:None
mm.current_loaded_models=models.copy();mm.DISABLE_SMART_MEMORY=False
unloaded=mm.free_memory(required,D)
samples['after_eviction_and_cache_release']=sample()
second=mm.free_memory(required,D)
samples['after_repeat_eviction']=sample()
assert unload_cache_samples and unload_cache_samples[0]['cached']>=N, unload_cache_samples
assert len(unloaded)==1, len(unloaded)
print(json.dumps({'buffer_bytes_per_model':N,'required_additional_bytes':8*1024*1024,'model_count':2,'first_unloaded_models':len(unloaded),'second_unloaded_models':len(second),'remaining_models':len(mm.current_loaded_models),'samples':samples,'cache_before_trim':unload_cache_samples,'scope':'real Vulkan buffers and real free_memory loop; model objects are minimal stubs, not trained models'}))
for model in mm.current_loaded_models:
 del model.tensor
mm.current_loaded_models=[];gc.collect();mm.soft_empty_cache()
