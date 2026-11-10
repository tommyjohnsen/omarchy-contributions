"""Source-level regression fixtures for independently confirmed review findings.
SPDX-License-Identifier: MIT
"""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'src/comfy/model_management.py'
TREE = ast.parse(SOURCE.read_text())

def functions(names, scope):
    nodes = [n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name in names]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), 'exec'), scope)
    return scope

class ReviewRegressions(unittest.TestCase):
    def test_unflagged_vulkan_device_name(self):
        scope = functions({'get_torch_device_name'}, {'vulkan_enabled': False})
        self.assertEqual(scope['get_torch_device_name'](SimpleNamespace(type='vulkan')), 'vulkan')

    def test_fp64_capability_matches_device(self):
        torch = SimpleNamespace(float32='f32', float16='f16', bfloat16='bf16', float64='f64')
        for capable in (False, True):
            scope = functions({'supports_dtype', 'supports_cast'}, {
                'torch': torch, 'vulkan_enabled': True, 'is_device_cpu': lambda _: False, 'is_device_vulkan': lambda _: True,
                'torchvulkan': SimpleNamespace(get_device_properties=lambda _: SimpleNamespace(has_fp16=True, has_bf16=False, has_fp64=capable))})
            self.assertEqual(scope['supports_dtype']('device', 'f64'), capable)
            self.assertEqual(scope['supports_cast']('device', 'f64'), capable)

    def test_explicit_async_offload_keeps_vulkan_synchronization(self):
        lines = SOURCE.read_text().splitlines()
        start = lines.index('STREAMS = {}') + 1
        end = lines.index('def current_stream(device):')
        nodes = [n for n in TREE.body if start <= n.lineno <= end]
        calls = []
        scope = {'args': SimpleNamespace(async_offload=2, disable_async_offload=False),
                 'vulkan_enabled': True, 'is_nvidia': lambda: False, 'is_amd': lambda: False,
                 'logging': SimpleNamespace(info=lambda _: None), 'synchronize': lambda: calls.append(1)}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), 'exec'), scope)
        functions({'sync_all_offload_streams'}, scope)
        self.assertEqual(scope['NUM_STREAMS'], 0)
        scope['sync_all_offload_streams']()
        self.assertEqual(calls, [1])

    def test_retained_arena_does_not_repeat_empty_cache(self):
        trims = []
        scope = functions({'free_memory'}, {
            'cleanup_models_gc': lambda: None, 'detail': lambda *a: None,
            'current_loaded_models': [], 'vram_state': 'normal',
            'VRAMState': SimpleNamespace(HIGH_VRAM='high'),
            'get_free_memory': lambda *a, **kw: (1000, 800),
            'is_device_vulkan': lambda _: True, 'vulkan_cached_memory': lambda _: 0,
            'soft_empty_cache': lambda: trims.append(1)})
        scope['free_memory'](0, SimpleNamespace(type='vulkan'))
        scope['free_memory'](0, SimpleNamespace(type='vulkan'))
        self.assertEqual(trims, [])

    def test_none_device_rejects_unsupported_bf16_and_fp8(self):
        torch = SimpleNamespace(float32='f32', float16='f16', bfloat16='bf16', float64='f64', float8_e4m3fn='fp8a', float8_e5m2='fp8b')
        scope = functions({'supports_dtype', 'supports_cast', 'pick_weight_dtype'}, {
            'torch': torch, 'vulkan_enabled': True, 'is_device_cpu': lambda _: False,
            'is_device_vulkan': lambda d: d is not None,
            'dtype_size': lambda _: 4,
            'torchvulkan': SimpleNamespace(get_device_properties=lambda _: SimpleNamespace(has_fp16=True, has_bf16=False, has_fp64=False))})
        for dtype in ('bf16', 'fp8a', 'fp8b'):
            self.assertFalse(scope['supports_dtype'](None, dtype))
            self.assertFalse(scope['supports_cast'](None, dtype))
            self.assertEqual(scope['pick_weight_dtype'](dtype, 'f32'), 'f32')

    def test_enumeration_includes_all_vulkan_devices(self):
        current = ('vulkan', 1)
        scope = functions({'get_all_torch_devices'}, {
            'cpu_state': 'gpu', 'CPUState': SimpleNamespace(GPU='gpu'), 'vulkan_enabled': True,
            'torch': SimpleNamespace(device=lambda kind,index: (kind,index)),
            'torchvulkan': SimpleNamespace(device_count=lambda: 2), 'get_torch_device': lambda: current})
        self.assertEqual(scope['get_all_torch_devices'](), [('vulkan',0),('vulkan',1)])
        self.assertEqual(scope['get_all_torch_devices'](exclude_current=True), [('vulkan',0)])

    def test_windows_cuda_visibility_is_unchanged_for_vulkan(self):
        tree = ast.parse((SOURCE.parents[1]/'main.py').read_text())
        matches=[n for n in ast.walk(tree) if isinstance(n,ast.If) and 'os.name' in ast.unparse(n.test) and 'CUDA_VISIBLE_DEVICES' in ast.unparse(n.test)]
        self.assertEqual(len(matches),1)
        for vulkan in (False,True):
            environment={}
            scope={'os': SimpleNamespace(name='nt',environ=environment),
                   'args': SimpleNamespace(vulkan=vulkan,cuda_device=None,default_device=None),
                   'logging': SimpleNamespace(warning=lambda _:None)}
            exec(compile(ast.Module(body=matches,type_ignores=[]),str(SOURCE.parents[1]/'main.py'),'exec'),scope)
            self.assertEqual(environment, {} if vulkan else {'CUDA_VISIBLE_DEVICES':'0'})

if __name__ == '__main__':
    unittest.main()
