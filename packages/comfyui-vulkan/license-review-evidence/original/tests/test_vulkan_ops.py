import json
import time

import torch
import torch.nn.functional as F
import torchvulkan


torch.manual_seed(7)
assert torchvulkan.is_available(), "No Vulkan GPU is available"
print(json.dumps(torchvulkan.get_device_properties()._asdict()), flush=True)
print("Strict CPU fallback disabled:", __import__("os").environ.get("TORCHVULKAN_STRICT"), flush=True)


def compare(name, operation, inputs, dtype=torch.float32):
    inputs = [x.to(dtype) for x in inputs]
    reference = operation(*inputs)
    start = time.monotonic()
    actual = operation(*(x.to("vulkan") for x in inputs))
    assert actual.device.type == "vulkan", actual.device
    torchvulkan.synchronize()
    actual_cpu = actual.cpu()
    torch.testing.assert_close(actual_cpu, reference, rtol=0.03 if dtype == torch.float16 else 0.001, atol=0.03 if dtype == torch.float16 else 0.001)
    print(f"PASS {name}: {tuple(actual.shape)}, {dtype}, {time.monotonic() - start:.3f}s", flush=True)


compare("matrix multiplication and activation", lambda a, b: (a @ b).relu(), [torch.randn(64, 128), torch.randn(128, 64)])
compare("convolution", F.conv2d, [torch.randn(1, 4, 16, 16), torch.randn(8, 4, 3, 3)])
compare("group normalization", lambda x: F.group_norm(x, 2), [torch.randn(1, 4, 16, 16)])
compare("attention", F.scaled_dot_product_attention, [torch.randn(1, 2, 16, 32) for _ in range(3)])
compare("half precision matrix multiplication", lambda a, b: a @ b, [torch.randn(64, 128), torch.randn(128, 64)], torch.float16)
print("All Vulkan inference-operation checks passed.", flush=True)
