"""Explicit bounded host-pressure observation; not run on import.
SPDX-License-Identifier: GPL-3.0-only
"""

def main():
    import ctypes as c, json,gc,time,statistics
    from pathlib import Path
    V=c.CDLL('libvulkan.so.1')
    class App(c.Structure):_fields_=[('sType',c.c_uint32),('next',c.c_void_p),('appname',c.c_char_p),('appversion',c.c_uint32),('engine',c.c_char_p),('engversion',c.c_uint32),('api',c.c_uint32)]
    class Create(c.Structure):_fields_=[('sType',c.c_uint32),('next',c.c_void_p),('flags',c.c_uint32),('app',c.POINTER(App)),('layersN',c.c_uint32),('layers',c.c_void_p),('extN',c.c_uint32),('ext',c.c_void_p)]
    a=App(sType=0,appname=b'local-budget-probe',api=1<<22);ci=Create(sType=1,app=c.pointer(a));instance=c.c_void_p()
    V.vkCreateInstance.argtypes=[c.POINTER(Create),c.c_void_p,c.POINTER(c.c_void_p)];assert V.vkCreateInstance(c.byref(ci),None,c.byref(instance))==0
    V.vkEnumeratePhysicalDevices.argtypes=[c.c_void_p,c.POINTER(c.c_uint32),c.c_void_p];n=c.c_uint32();assert V.vkEnumeratePhysicalDevices(instance,c.byref(n),None)==0
    array=(c.c_void_p*n.value)();assert V.vkEnumeratePhysicalDevices(instance,c.byref(n),array)==0
    V.vkGetPhysicalDeviceProperties.argtypes=[c.c_void_p,c.c_void_p];observed=[]
    for device in array:
     props=c.create_string_buffer(4096);V.vkGetPhysicalDeviceProperties(device,props)
     observed.append({'name':props.raw[20:276].split(b'\0')[0].decode(),'device_type':int.from_bytes(props.raw[16:20],'little'),'type_names':{'1':'INTEGRATED_GPU','2':'DISCRETE_GPU','4':'CPU'}})
    V.vkDestroyInstance.argtypes=[c.c_void_p,c.c_void_p];V.vkDestroyInstance(instance,None)
    import torch,torchvulkan
    assert torchvulkan.is_available()
    def sample():
     values={x.split(':')[0]:int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith(('MemTotal:','MemAvailable:'))}
     values['vulkan_free'],values['vulkan_total']=torchvulkan.mem_get_info();return values
    result={'physical_devices':observed,'before':[sample() for _ in range(5)]}
    if result['before'][0]['MemAvailable']>2*1024**3:
     size=128*1024**2
     buffer=bytearray(size)
     for i in range(0,len(buffer),4096):buffer[i]=1
     result['cpu_touched_bytes']=size;result['during_cpu_allocation']=[sample() for _ in range(5)]
     del buffer;gc.collect();result['after_release']=[sample() for _ in range(5)]
    else:result['allocation_probe']='skipped:host-available guard'
    print(json.dumps(result,indent=2))

if __name__ == "__main__":
    main()
