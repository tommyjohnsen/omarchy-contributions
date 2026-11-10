"""Measured native minimize transport in an isolated nested compositor.
SPDX-License-Identifier: MIT
"""
from pathlib import Path
import json,os,subprocess,tempfile,time,shutil,argparse,hashlib,socket,threading
def validate_nested_outputs(monitors):
 if not monitors:
  raise AssertionError('No actual nested output')
 for monitor in monitors:
  backend=monitor.get('hardwareDetails',{}).get('backend')
  name=str(monitor.get('name',''))
  if backend != 'wayland' or not name.startswith(('WAYLAND-','WL-')):
   raise AssertionError('Expected only actual Wayland nested outputs')
 return [{'name':m['name'],'backend':m['hardwareDetails']['backend'],'width':m.get('width'),'height':m.get('height')} for m in monitors]

root=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--check-negative-fixture',action='store_true');parser.add_argument('--expect-premap',type=int,choices=(0,1),default=0);parser.add_argument('--tag',default='guarded-v4');parser.add_argument('--binary',type=Path,default=root.parent/'build/Hyprland');parser.add_argument('--premap-client',type=Path,default=root.parent/'premap-client');test_args=parser.parse_args();assert all(c.isalnum() or c in '-_' for c in test_args.tag), 'Unsafe result tag';binary=test_args.binary.resolve();probe=test_args.premap_client.resolve();prefix=test_args.tag+'-premap-'+str(test_args.expect_premap)
if test_args.check_negative_fixture:
 fixtures=[[],[{'name':'DP-1','hardwareDetails':{'backend':'drm'}}],[{'name':'WAYLAND-1','hardwareDetails':{'backend':'drm'}}],[{'name':'DP-1','hardwareDetails':{'backend':'wayland'}}]]
 rejected=0
 for fixture in fixtures:
  try:validate_nested_outputs(fixture)
  except AssertionError:rejected+=1
 assert rejected==len(fixtures)
 assert validate_nested_outputs([{'name':'WAYLAND-1','hardwareDetails':{'backend':'wayland'}}])
 print(json.dumps({'result':'passed','rejected_negative_fixtures':rejected,'real_drm_started':False}))
 raise SystemExit(0)
# Refuse startup unless only render nodes (no KMS/input/seat broker) are visible.
drm_dir=Path('/dev/dri')
drm_nodes=sorted(x.name for x in drm_dir.iterdir()) if drm_dir.exists() else []
private_devices={'drm_nodes':drm_nodes,'input_visible':Path('/dev/input').exists(),
 'system_bus_socket_visible':Path('/run/dbus/system_bus_socket').exists(),
 'seatd_socket_visible':Path('/run/seatd.sock').exists()}
assert drm_nodes and all(x.startswith('renderD') and x[7:].isdigit() for x in drm_nodes), 'Only DRM render nodes may be visible'
assert not any(private_devices[x] for x in ('input_visible','system_bus_socket_visible','seatd_socket_visible')), 'KMS/input/seat broker exclusion missing'
runtime=Path(tempfile.mkdtemp(prefix='hn-'));runtime.chmod(0o700)
config=root/(prefix+'-nested-test.lua')
config.write_text('''hl.config({ animations = { enabled = false }, debug = { disable_logs = false } })
_G.native_minimize_events = {}
hl.on("window.minimize", function(w, minimized)
  table.insert(native_minimize_events, { class = w.class, minimized = minimized, mapped = w.mapped, address = w.address })
end)
''')
client=root/(prefix+'-nested-client.py')
client.write_text('''import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk,Gio,GLib
app=Gtk.Application(application_id="org.example.NativeMinimizeProbe", flags=Gio.ApplicationFlags.NON_UNIQUE)
def activate(app):
 w=Gtk.ApplicationWindow(application=app,title="Native minimize transport probe")
 w.set_default_size(320,200)
 w.show_all()
 def minimize():
  print("REQUEST_MINIMIZE",flush=True);w.iconify();return False
 def maximize():
  print("REQUEST_MAXIMIZE_WITHOUT_MINIMIZE",flush=True);w.maximize();return False
 GLib.timeout_add(650,minimize)
 GLib.timeout_add(1300,maximize)
 GLib.timeout_add(1750,lambda:(w.fullscreen(),False)[1])
 GLib.timeout_add(2450,lambda:(app.quit(),False)[1])
app.connect("activate",activate)
app.run([])
''')
env=os.environ.copy()
parent_name = env.get('WAYLAND_DISPLAY')
assert parent_name, 'No parent Wayland socket available for nested backend'
parent_socket = Path(parent_name) if parent_name.startswith('/') else Path(env['XDG_RUNTIME_DIR']) / parent_name
assert parent_socket.is_socket(), parent_socket
for key in ('WAYLAND_DISPLAY','DISPLAY','HYPRLAND_INSTANCE_SIGNATURE','NOTIFY_SOCKET','LISTEN_FDS','LISTEN_PID'):
 env.pop(key,None)
env.pop('HYPRLAND_HEADLESS_ONLY',None)
for selector in ('AQ_BACKEND','AQ_DRM_DEVICES','WLR_BACKENDS','LIBSEAT_BACKEND','SEATD_SOCK','DBUS_SYSTEM_BUS_ADDRESS'):env.pop(selector,None)
env.update(WAYLAND_DISPLAY=str(parent_socket),XDG_RUNTIME_DIR=str(runtime),XDG_CONFIG_HOME=str(runtime/'config'),XDG_CACHE_HOME=str(runtime/'cache'),XDG_DATA_HOME=str(runtime/'data'),HYPRLAND_NO_SD_VARS='1',HYPRLAND_NO_SD_NOTIFY='1',HYPRLAND_NO_SD_TARGET='1',LIBGL_ALWAYS_SOFTWARE='1',WLR_RENDERER_ALLOW_SOFTWARE='1',AQ_RENDERER_ALLOW_SOFTWARE='1',NO_AT_BRIDGE='1',GTK_USE_PORTAL='0')
proc=None
try:
 with (root/(prefix+'-nested-compositor.log')).open('w') as log:
  proc=subprocess.Popen([str(binary),'--config',str(config)],env=env,stdout=log,stderr=subprocess.STDOUT)
  deadline=time.monotonic()+35;signature=None
  while time.monotonic()<deadline:
   for p in (runtime/'hypr').glob('*') if (runtime/'hypr').exists() else []:
    if (p/'.socket.sock').exists():signature=p.name;break
   if signature:break
   if proc.poll() is not None:raise RuntimeError('Nested compositor exited before IPC was ready')
   time.sleep(.2)
  if not signature:raise RuntimeError('Nested compositor IPC readiness timed out')
  env['HYPRLAND_INSTANCE_SIGNATURE']=signature
  def ctl(*args):
   return subprocess.check_output(['/usr/bin/hyprctl','--instance',signature,*args],env=env,text=True,timeout=10).strip()
  errors=ctl('configerrors');assert not errors,errors
  plugins=ctl('plugin','list');assert plugins.strip() in ('', 'no plugins loaded'),plugins
  monitors=json.loads(ctl('monitors','-j'))
  monitor_observations=validate_nested_outputs(monitors)
  # Select the isolated compositor's own Wayland socket.
  sockets=[p.name for p in runtime.glob('wayland-*') if p.is_socket()]
  assert len(sockets)==1,sockets
  env.update(WAYLAND_DISPLAY=sockets[0],GDK_BACKEND='wayland',WAYLAND_DEBUG='client')
  ipc=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
  ipc.connect(str(runtime/'hypr'/signature/'.socket2.sock'))
  ipc.settimeout(.2)
  def drain_ipc():
   chunks=[]
   while True:
    try:
     data=ipc.recv(65536)
     if not data:break
     chunks.append(data)
    except socket.timeout:break
   return b''.join(chunks).decode().splitlines()
  drain_ipc()
  def run_client(command, stdout, wire, timeout):
   child=subprocess.Popen(command,env=env,stdout=stdout,stderr=subprocess.PIPE,text=True)
   def filter_wire():
    for line in child.stderr:
     if any(request in line for request in ('.set_minimized(','.set_maximized(','.set_fullscreen(')):
      wire.write(line)
   reader=threading.Thread(target=filter_wire,daemon=True);reader.start()
   try:returncode=child.wait(timeout=timeout)
   except subprocess.TimeoutExpired:
    child.kill();child.wait();raise
   finally:reader.join(timeout=2)
   assert not reader.is_alive(),'Wire reader did not finish'
   return returncode
  with (root/(prefix+'-premap-client.wire.log')).open('w') as wire:
   raw_code=run_client([str(probe)],subprocess.DEVNULL,wire,10)
  assert raw_code==0,raw_code
  premap=ctl('repl','print(#native_minimize_events); for _,e in ipairs(native_minimize_events) do print(e.class,tostring(e.minimized),tostring(e.mapped),e.address) end')
  premap_count=int(premap.splitlines()[0])
  premap_ipc=[x for x in drain_ipc() if x.startswith('minimized>>')]
  # A historical guard-less build may have Lua only, before Socket2 parity.
  if test_args.expect_premap == 0:assert not premap_ipc,premap_ipc
  assert premap_count==test_args.expect_premap,premap
  premap_requests=(root/(prefix+'-premap-client.wire.log')).read_text().count('.set_minimized(')
  assert premap_requests==1
  ctl('eval','_G.native_minimize_events = {}')
  with (root/(prefix+'-nested-client.stdout.log')).open('w') as out,(root/(prefix+'-nested-client.wire.log')).open('w') as wire:
   result_code=run_client(['/usr/bin/python',str(client)],out,wire,15)
  assert result_code==0,result_code
  received=ctl('repl','print(#native_minimize_events); for _,e in ipairs(native_minimize_events) do print(e.class,tostring(e.minimized),tostring(e.mapped),e.address) end')
  wire=(root/(prefix+'-nested-client.wire.log')).read_text()
  minimize_requests=sum('.set_minimized(' in line for line in wire.splitlines())
  assert minimize_requests==1,minimize_requests
  assert received.splitlines()[0]=='1',received
  assert received.splitlines()[1].split('\t')[1:3]==['true','true'],received
  mapped_ipc=[x for x in drain_ipc() if x.startswith('minimized>>')]
  assert len(mapped_ipc)==1,mapped_ipc
  expected_address=received.splitlines()[1].split('\t')[-1].removeprefix('0x')
  assert mapped_ipc[0]=='minimized>>'+expected_address+',1',mapped_ipc
  ipc.close()
  assert '.set_maximized(' in wire,'No separate maximize control request found'
  assert '.set_fullscreen(' in wire,'No separate fullscreen control request found'
  parsed_events=[line.split('\t') for line in received.splitlines()[1:]]
  data={'result':'passed','xdg_set_minimized_requests':minimize_requests,
        'lua_minimize_events':int(received.splitlines()[0]),'state':parsed_events[0][1]=='true',
        'separate_maximize_request_did_not_emit_minimize':'.set_maximized(' in wire and len(parsed_events)==1,
        'separate_fullscreen_request_did_not_emit_minimize':'.set_fullscreen(' in wire and len(parsed_events)==1,
        'plugin_list_output':plugins,'monitor_observations':monitor_observations,
        'observed_wayland_output':any(str(m['name']).startswith(('WL-','WAYLAND-')) for m in monitor_observations),
        'observed_headless_output':any(str(m['name']).startswith('HEADLESS-') for m in monitor_observations),
        'output_inference_basis':'strict actual hardwareDetails.backend=wayland and WAYLAND-/WL- name assertions',
        'private_device_visibility':private_devices,
        'backend_selector_environment':{name:env.get(name) for name in ('AQ_BACKEND','AQ_DRM_DEVICES','WLR_BACKENDS')},
        'headless_only_env_present':'HYPRLAND_HEADLESS_ONLY' in env,
        'observer_config_sha256':hashlib.sha256(config.read_bytes()).hexdigest(),
        'observer_config_external_loads':any(x in config.read_text() for x in ('dofile(', 'require(', 'hl.plugin')),
        'source_revision':'acc1aa0bfd4bd575dcb0f76c35ccf12b660a1ab9','received':received,
        'binary':'build/Hyprland','binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
        'premap_minimize_requests':premap_requests,'premap_events':premap_count,'premap_received':premap,
        'premap_socket2_minimize_events':len(premap_ipc),'mapped_socket2_minimize_events':len(mapped_ipc),
        'socket2_event':mapped_ipc[0]}
  (root/(prefix+'-result.json')).write_text(json.dumps(data,indent=2)+'\n');print(json.dumps(data))
  ctl('dispatch','hl.dsp.exit()')
finally:
 if proc and proc.poll() is None:
  proc.terminate()
  try:proc.wait(timeout=8)
  except subprocess.TimeoutExpired:proc.kill();proc.wait()
 shutil.rmtree(runtime)
