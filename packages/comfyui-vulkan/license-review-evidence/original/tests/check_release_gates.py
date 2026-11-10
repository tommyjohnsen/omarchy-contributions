"""Isolated negative/startup tests; no server, model files, or live edits."""
import argparse
import builtins
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

parser = argparse.ArgumentParser()
parser.add_argument('mode', choices=('missing_dependency', 'unavailable_device', 'no_cuda_boot', 'invalid_device', 'xformers_installed', 'explicit_async'))
parser.add_argument('--comfyui-root', type=Path, required=True)
parser.add_argument('--candidate-file', type=Path)
args = parser.parse_args()
sys.path.insert(0, str(args.comfyui_root.resolve()))
import comfy.options
comfy.options.enable_args_parsing()
root = Path(__file__).resolve().parents[1]
sys.argv = [sys.argv[0], '--vulkan']
if args.mode == 'explicit_async':
    sys.argv += ['--async-offload', '2', '--force-non-blocking']
if args.mode == 'invalid_device':
    sys.argv += ['--default-device', '999999']

spec = importlib.util.spec_from_file_location('comfy.cli_args', root / 'src/comfy/cli_args.py')
cli = importlib.util.module_from_spec(spec)
sys.modules['comfy.cli_args'] = cli
spec.loader.exec_module(cli)
import comfy
comfy.cli_args = cli

if args.mode == 'missing_dependency':
    original_import = builtins.__import__
    def import_without_vulkan(name, *positional, **keyword):
        if name == 'torchvulkan':
            raise ImportError('Simulated absent optional dependency')
        return original_import(name, *positional, **keyword)
    builtins.__import__ = import_without_vulkan
elif args.mode == 'unavailable_device':
    sys.modules['torchvulkan'] = SimpleNamespace(is_available=lambda: False)
else:
    import torch
    def no_cuda(name):
        def blocked(*positional, **keyword):
            raise AssertionError('Vulkan path called CUDA execution API: ' + name)
        return blocked
    for name in ('current_device', 'get_device_properties', 'get_device_name', 'memory_stats',
                 'mem_get_info', 'synchronize', 'empty_cache', 'current_stream', 'set_device'):
        setattr(torch.cuda, name, no_cuda(name))

if args.mode == 'xformers_installed':
    import types
    xf = types.ModuleType('xformers')
    xf.__path__ = []
    xf._has_cpp_library = True
    xf.ops = types.ModuleType('xformers.ops')
    xf.version = SimpleNamespace(__version__='mock-review-only')
    sys.modules['xformers'] = xf
    sys.modules['xformers.ops'] = xf.ops

spec = importlib.util.spec_from_file_location('comfy.model_management', args.candidate_file or root / 'src/comfy/model_management.py')
mm = importlib.util.module_from_spec(spec)
sys.modules['comfy.model_management'] = mm
try:
    spec.loader.exec_module(mm)
    comfy.model_management = mm
except Exception as error:
    message = str(error)
    expected = {'missing_dependency': '--vulkan requires torchvulkan',
                'unavailable_device': 'no usable Vulkan device'}
    if args.mode in expected:
        assert isinstance(error, RuntimeError), (type(error).__name__, message)
        assert expected[args.mode] in message, message
        print(json.dumps({'mode': args.mode, 'result': 'expected RuntimeError', 'message': message}))
    elif args.mode == 'invalid_device':
        assert isinstance(error, RuntimeError), type(error).__name__
        assert '--default-device must select an available Vulkan device' in message, message
        print(json.dumps({'mode': args.mode, 'result': 'rejected', 'exception': type(error).__name__, 'message': message}))
    else:
        raise
else:
    assert args.mode in ('no_cuda_boot', 'xformers_installed', 'explicit_async'), 'Expected startup failure was not raised'
    if args.mode == 'xformers_installed':
        assert mm.xformers_enabled() is False, 'Vulkan must not select xformers'
        print(json.dumps({'mode':args.mode,'vulkan_selected':mm.vulkan_enabled,'xformers_enabled':mm.xformers_enabled(), 'result':'BUG' if mm.xformers_enabled() else 'safe'}))
        raise SystemExit(0)
    device = mm.get_torch_device()
    assert device.type == 'vulkan'
    assert mm.NUM_STREAMS == 0
    assert mm.device_supports_non_blocking(device) is False
    mm.synchronize()
    mm.soft_empty_cache()
    print(json.dumps({'mode': args.mode, 'device': str(device),
                      'device_name': mm.get_torch_device_name(device),
                      'total_memory': mm.get_total_memory(device),
                      'free_memory': mm.get_free_memory(device),
                      'known_reusable_cache': mm.get_free_memory(device, True)[1],
                      'async_streams': mm.NUM_STREAMS,
                      'disable_pinned_memory': mm.DISABLE_PINNED_MEMORY,
                      'dynamic_vram_cli_enabled': cli.enables_dynamic_vram(),
                      'fp16': mm.should_use_fp16(device), 'bf16': mm.should_use_bf16(device)}))
