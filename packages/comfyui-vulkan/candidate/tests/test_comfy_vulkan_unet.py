"""SPDX-License-Identifier: MIT"""
import copy
import os
from pathlib import Path
import sys
import time

import argparse

parser = argparse.ArgumentParser(description="Compare a small real ComfyUI UNet on CPU and Vulkan; no model downloads.")
parser.add_argument("--comfyui-root", type=Path, default=Path.cwd(), help="Path to the patched ComfyUI checkout")
parser.add_argument("--default-device", type=int)
parser.add_argument("--attention", choices=("pytorch", "default"), default="pytorch")
options = parser.parse_args()
root = options.comfyui_root.resolve()
if not (root / "comfy" / "model_management.py").is_file():
    parser.error("--comfyui-root must point to the patched ComfyUI checkout")
os.environ.setdefault("TORCHVULKAN_STRICT", "1")
sys.path.insert(0, str(root))
sys.argv = [sys.argv[0], "--vulkan", "--disable-dynamic-vram", "--disable-async-offload", "--disable-pinned-memory", "--disable-xformers"]
if options.attention == "pytorch":
    sys.argv.append("--use-pytorch-cross-attention")
if options.default_device is not None:
    sys.argv += ["--default-device", str(options.default_device)]

import comfy.options
comfy.options.enable_args_parsing()
import torch
import torchvulkan
import importlib.util
staged_file = Path(__file__).resolve().parents[1] / "src/comfy/model_management.py"
spec = importlib.util.spec_from_file_location("comfy.model_management", staged_file)
model_management = importlib.util.module_from_spec(spec)
sys.modules["comfy.model_management"] = model_management
spec.loader.exec_module(model_management)
import comfy
comfy.model_management = model_management
from comfy.ldm.modules.diffusionmodules.openaimodel import UNetModel
from comfy.ldm.modules import attention
print("Selected attention:", attention.optimized_attention.__name__, flush=True)

assert os.environ.get("TORCHVULKAN_STRICT") == "1"
assert model_management.get_torch_device().type == "vulkan"
properties = torchvulkan.get_device_properties()
assert model_management.should_use_bf16() == properties.has_bf16
assert model_management.supports_fp64() == properties.has_fp64
assert model_management.should_use_fp16() == properties.has_fp16
torch.manual_seed(11)
torch.set_num_threads(4)

model = UNetModel(
    image_size=8, in_channels=4, out_channels=4, model_channels=32,
    num_res_blocks=1, channel_mult=(1,),
    num_heads=4, use_spatial_transformer=True, context_dim=32,
    transformer_depth=[1], transformer_depth_output=[1, 1],
    transformer_depth_middle=1, dtype=torch.float32, device="cpu",
).eval()

with torch.no_grad():
    for name, parameter in model.named_parameters():
        if name.endswith("bias"):
            parameter.zero_()
        elif parameter.ndim == 1:
            parameter.fill_(1)
        else:
            parameter.normal_(std=0.02)

    x = torch.randn(1, 4, 8, 8)
    timestep = torch.tensor([1.0])
    context = torch.randn(1, 4, 32)
    reference = model(x, timestep, context)
    gpu_model = copy.deepcopy(model).to("vulkan")
    start = time.monotonic()
    output = gpu_model(x.to("vulkan"), timestep.to("vulkan"), context.to("vulkan"))
    model_management.synchronize()
    actual = output.cpu()
    torch.testing.assert_close(actual, reference, rtol=0.002, atol=0.0002)
    assert torch.isfinite(actual).all()
    assert output.device.type == "vulkan"
    print(f"PASS actual ComfyUI UNet: {tuple(output.shape)}, max error {(actual-reference).abs().max().item():.8f}, {time.monotonic()-start:.3f}s", flush=True)
    print("Vulkan memory:", model_management.get_total_memory(), model_management.get_free_memory(), flush=True)

    if properties.has_fp16:
        half_model = model.half()
        half_reference = half_model(x.half(), timestep.half(), context.half())
        half_gpu = gpu_model.half()
        half_output = half_gpu(x.half().to("vulkan"), timestep.half().to("vulkan"), context.half().to("vulkan"))
        model_management.synchronize()
        torch.testing.assert_close(half_output.cpu(), half_reference, rtol=0.04, atol=0.04)
        assert torch.isfinite(half_output.cpu()).all()
        print("PASS actual ComfyUI FP16 UNet", flush=True)

model_management.soft_empty_cache()
print("ComfyUI Vulkan integration checks passed without downloaded models or CPU operator fallback.", flush=True)
