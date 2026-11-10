# SPDX-License-Identifier: MIT
"""Program-wide implicit GPU usage must not be mistaken for reusable cache."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'src/comfy/model_management.py'

class VulkanMemoryAccounting(unittest.TestCase):
    def setUp(self):
        self.device = SimpleNamespace(type='vulkan')
        # 2 GiB available; estimated program usage includes implicit non-cache memory.
        # Only explicit reusable-buffer bytes may augment the driver budget.
        self.backend = SimpleNamespace(
            mem_get_info=lambda _: (2 << 30, 8 << 30),
            get_device_properties=lambda _: SimpleNamespace(total_memory=8 << 30),
            memory_allocated=lambda _: 1 << 30,
            memory_reserved=lambda _: 6 << 30,
            memory_stats=lambda _: {},
        )
        scope = dict(torchvulkan=self.backend, vulkan_enabled=True,
                     directml_enabled=False, get_torch_device=lambda: self.device,
                     vulkan_cached_memory=None,
                     comfy=SimpleNamespace(system_memory=SimpleNamespace(virtual_memory_available=lambda: 16 << 30),
                                           memory_management=SimpleNamespace(RAM_CACHE_HEADROOM=0)))
        tree = ast.parse(SOURCE.read_text())
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                     and n.name in ('get_free_memory', 'get_total_memory')]
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(SOURCE), 'exec'), scope)
        self.scope = scope
        self.free = scope['get_free_memory']
        self.total = scope['get_total_memory']

    def test_implicit_program_usage_is_not_reusable_cache(self):
        self.assertEqual(self.free(self.device, True), (2 << 30, 0))
        self.assertEqual(self.free(), 2 << 30)

    def test_owned_allocation_is_not_implicit_usage(self):
        self.assertEqual(self.total(self.device, True), (8 << 30, 1 << 30))

    def test_explicit_reusable_cache_augments_available_budget(self):
        self.scope['vulkan_cached_memory'] = lambda _: 1 << 29
        self.assertEqual(self.free(self.device, True), ((2 << 30) + (1 << 29), 1 << 29))

    def test_managed_memory_counts_active_and_known_cache_only(self):
        self.scope['vulkan_cached_memory'] = lambda _: 1 << 29
        self.assertEqual(self.total(self.device, True), (8 << 30, (1 << 30) + (1 << 29)))

    def test_unsupported_allocator_unused_space_is_never_counted(self):
        self.scope['vulkan_cached_memory'] = lambda _: 0
        self.backend.memory_stats = lambda _: {"allocator_unused_bytes.all.current": 1 << 29}
        self.assertEqual(self.free(self.device, True), (2 << 30, 0))
        self.assertEqual(self.total(self.device, True), (8 << 30, 1 << 30))

    def test_host_tight_budget_caps_gpu_and_cached_availability(self):
        self.scope['vulkan_cached_memory'] = lambda _: 1 << 29
        self.scope['comfy'].system_memory.virtual_memory_available = lambda: 3 << 30
        self.assertEqual(self.free(self.device, True), (1 << 30, 1 << 29))
        self.scope['comfy'].system_memory.virtual_memory_available = lambda: 1 << 30
        self.assertEqual(self.free(self.device, True), (0, 0))

    def test_existing_ram_headroom_is_respected(self):
        self.scope['comfy'].memory_management.RAM_CACHE_HEADROOM = 8 << 30
        self.scope['comfy'].system_memory.virtual_memory_available = lambda: 5 << 30
        self.assertEqual(self.free(self.device), 1 << 30)

    def test_total_samples_allocated_after_cache_flush(self):
        active=[1 << 30]
        self.backend.memory_allocated=lambda _: active[0]
        def cache_flush(_):
            active[0]=0
            return 1 << 29
        self.scope['vulkan_cached_memory']=cache_flush
        self.assertEqual(self.total(self.device, True), (8 << 30, 1 << 29))

if __name__ == '__main__':
    unittest.main()
