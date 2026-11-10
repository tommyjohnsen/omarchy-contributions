"""Real, small-buffer API checks. Run against an isolated patched backend overlay.
SPDX-License-Identifier: MIT
"""
import gc,json,os,select,subprocess,sys,time,statistics
from pathlib import Path
import torch
import torchvulkan

N=32*1024*1024

def sample():
    cached=torchvulkan.memory_cached()
    return dict(allocated=torchvulkan.memory_allocated(),reserved=torchvulkan.memory_reserved(),cached=cached,driver_free=torchvulkan.mem_get_info()[0])

def peer_process():
    peer_tensor=torch.empty((2*N)//4,device='vulkan',dtype=torch.float32)
    peer_tensor.fill_(2)
    torchvulkan.synchronize()
    print(json.dumps(sample()),flush=True)
    sys.stdin.readline()
    del peer_tensor;gc.collect();torchvulkan.empty_cache()
    return
def run_checks():
    assert torchvulkan.is_available(), 'Vulkan unavailable'
    assert hasattr(torchvulkan, 'memory_cached'), 'Proposed memory_cached API missing'
    assert 'allocator_unused_bytes.all.current' not in torchvulkan.memory_stats(), 'Unproven arena capacity must not be exposed'
    torchvulkan.empty_cache();gc.collect()
    result={'before':sample()}
    tensor=torch.empty(N//4,device='vulkan',dtype=torch.float32)
    tensor.fill_(1);torchvulkan.synchronize()
    result['active32']=sample()
    assert result['active32']['allocated']>=N
    del tensor;gc.collect();torchvulkan.synchronize()
    result['cached32']=sample()
    assert result['cached32']['allocated']<=result['active32']['allocated']-N
    assert result['cached32']['cached']>=N

    available=None
    if sys.platform.startswith('linux'):
        lines=Path('/proc/meminfo').read_text().splitlines()
        available=next(int(x.split()[1])*1024 for x in lines if x.startswith('MemAvailable:'))
    if os.name != 'posix' or available is None or available<1536*1024*1024:
        result['peer']='skipped:POSIX/Linux available-memory guard'
    else:
        peer=None
        try:
            before=sample()
            peer=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--peer'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
            ready,_,_=select.select([peer.stdout],[],[],20)
            assert ready,'Peer startup timeout'
            line=peer.stdout.readline()
            assert line,'Peer exited before producing a memory sample'
            result['peer']=json.loads(line)
            result['during_peer']=sample()
            assert result['during_peer']['reserved']==before['reserved'],'Other process changed our allocator-reserved counter'
            assert result['during_peer']['cached']==before['cached'],'Other process changed our reusable buffer counter'
        finally:
            if peer:
                if peer.poll() is None:
                    peer.stdin.write('exit\n');peer.stdin.flush()
                    try:peer.wait(timeout=10)
                    except subprocess.TimeoutExpired:peer.kill();peer.wait()
                if peer.stdin:peer.stdin.close()
                if peer.stdout:peer.stdout.close()

    torchvulkan.empty_cache();gc.collect()
    result['after_empty_cache']=sample()
    assert result['after_empty_cache']['cached']==0
    for name,query in [('memory_cached',torchvulkan.memory_cached),('memory_stats',torchvulkan.memory_stats)]:
        batches=[]
        for _ in range(7):
            start=time.perf_counter_ns()
            for _ in range(10000):query()
            batches.append((time.perf_counter_ns()-start)/10000)
        result[name+'_idle_ns_per_call']={'median':statistics.median(batches),'min':min(batches),'max':max(batches),'batches':7,'calls_per_batch':10000}
    result['scope']='32MiB own buffer plus optional64MiB separate-process buffer; no model downloads'
    return result


def test_allocator_cache():
    import pytest
    if not torchvulkan.is_available():
        pytest.skip("No usable Vulkan device")
    run_checks()



if __name__ == "__main__":
    if "--peer" in sys.argv:
        peer_process()
    else:
        print(json.dumps(run_checks(), indent=2))
