# SPDX-License-Identifier: MIT
"""Independent runtime checks of actual reviewer capability claims."""
import argparse,importlib.util,sys,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--comfyui-root',type=Path,required=True);p.add_argument('--cpu',action='store_true');a=p.parse_args()
sys.path.insert(0,str(a.comfyui_root.resolve()))
import comfy.options
comfy.options.enable_args_parsing()
sys.argv=[sys.argv[0], '--cpu' if a.cpu else '--vulkan']
package=Path(__file__).resolve().parents[1]
for name in ('cli_args','model_management'):
 full='comfy.'+name;spec=importlib.util.spec_from_file_location(full,package/'src/comfy'/str(name+'.py'));mod=importlib.util.module_from_spec(spec);sys.modules[full]=mod;spec.loader.exec_module(mod)
 import comfy
 setattr(comfy,name,mod)
mm=mod
import torch
if a.cpu:
 d=torch.device('vulkan')
 result=mm.supports_dtype(d,torch.float16)
 assert mm.get_torch_device_name(d)=='vulkan'
 print(json.dumps({'no_vulkan_flag':True,'device':str(d),'supports_dtype':result}))
else:
 import torchvulkan
 d=mm.get_torch_device();props=torchvulkan.get_device_properties()
 assert torchvulkan.get_device_properties(None)==torchvulkan.get_device_properties(d)
 assert mm.should_use_fp16()==props.has_fp16
 assert mm.should_use_bf16()==props.has_bf16
 assert mm.supports_fp64()==props.has_fp64
 assert mm.supports_dtype(d,torch.float32) is True
 assert mm.supports_cast(d,torch.float32) is True
 assert mm.supports_dtype(None,torch.bfloat16)==props.has_bf16
 assert mm.supports_cast(None,torch.bfloat16)==props.has_bf16
 assert mm.supports_dtype(None,torch.float64)==props.has_fp64
 assert not mm.supports_cast(None,torch.float8_e4m3fn)
 assert not mm.supports_cast(None,torch.float8_e5m2)

 def blocked(*args,**kwargs):raise AssertionError('Pinned-memory path reached CUDA cudart')
 torch.cuda.cudart=blocked
 print(json.dumps({'cached_api_available':mm.vulkan_cached_memory is not None,'known_allocator_available':mm.get_free_memory(d,True)[1],'default_device_argument_defined':hasattr(sys.modules['comfy.cli_args'].args,'default_device'),'no_arg_fp16':mm.should_use_fp16(),'no_arg_bf16':mm.should_use_bf16(),'no_arg_fp64':mm.supports_fp64(),'current_device':str(d),'properties_none_equal_current':torchvulkan.get_device_properties(None)==torchvulkan.get_device_properties(d),'float32_supports_dtype':mm.supports_dtype(d,torch.float32),'float32_supports_cast':mm.supports_cast(d,torch.float32),'disable_pinned_memory_flag':mm.DISABLE_PINNED_MEMORY,'max_pinned_memory':mm.MAX_PINNED_MEMORY,'pin_memory_cpu_tensor_result':mm.pin_memory(torch.empty(1024)),'pinned_hostbuf_size':mm.pinned_hostbuf_size(1024)}))
