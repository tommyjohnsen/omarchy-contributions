#!/usr/bin/env python3
"""Run only against a disposable nested compositor; never source user config."""
from pathlib import Path
import os,json,time,subprocess,shutil,tempfile,shlex,hashlib,argparse,threading
root=Path(__file__).resolve().parent
candidate=root.parent/'native-minimize.lua'
parser=argparse.ArgumentParser()
parser.add_argument('--hyprland', default='Hyprland', help='Explicit compositor binary; provide guarded patched core for --native-gtk')
parser.add_argument('--native-gtk', action='store_true', help='Also verify actual Wayland GTK minimize through hl.on with patched core')
parser.add_argument('--restore-parent-focus', action='store_true', help='Explicitly allow focusing/raising original parent window after test; default only observes parent')
args=parser.parse_args()
compositor_binary=shutil.which(args.hyprland) or args.hyprland
parent_env=dict(os.environ)
real_ctl=shutil.which('hyprctl')
def call(env,*args):
 p=subprocess.run([real_ctl,*args],env=env,capture_output=True,text=True,timeout=8,check=True)
 if p.stdout.startswith('Err') or "Couldn't" in p.stdout: raise RuntimeError(p.stdout.strip())
 return p.stdout
parent_instances=json.loads(call(parent_env,'instances','-j'))
parent_signature=parent_env.get('HYPRLAND_INSTANCE_SIGNATURE') or parent_instances[0]['instance']
parent=next(x for x in parent_instances if x['instance']==parent_signature)
parent_display=str(Path(parent_env['XDG_RUNTIME_DIR'])/parent['wl_socket'])
before=json.loads(call(parent_env,'clients','-j'))
original_focus=json.loads(call(parent_env,'activewindow','-j')).get('address')
original_geometry={w['address']:{k:w.get(k) for k in ('at','size','fullscreen')} for w in before}
results={'candidate_sha256':hashlib.sha256(candidate.read_bytes()).hexdigest(),'candidate':'omarchy-native-integration-r4-context-only','parent_focus_restore_requested':args.restore_parent_focus,'parent_ipc_mutation_performed':False,'physical_keyboard_test':False,'nested_runtime_only':True,'cases':[]}
processes=[]; compositor=None
try:
 with tempfile.TemporaryDirectory(prefix='s',dir='/tmp') as tmp:
  scratch=Path(tmp); bin_dir=scratch/'bin';bin_dir.mkdir()
  test_source=scratch/'policy.lua';test_source.write_bytes(candidate.read_bytes())
  calls_file=scratch/'helper-calls'
  blocked=scratch/'blocked'; child_pids=scratch/'blocked-pids'
  helper=bin_dir/'omarchy-hyprland-window-minimize'
  helper.write_text("#!/bin/sh\nprintf '%s\\n' \"$1\" >> "+shlex.quote(str(calls_file))+"\nif [ -e "+shlex.quote(str(blocked))+" ]; then\n trap '' TERM\n sleep 120 &\n child=$!\n printf '%s %s\\n' \"$$\" \"$child\" > "+shlex.quote(str(child_pids))+"\n wait \"$child\"\nfi\n");helper.chmod(0o700)
  config=scratch/'hyprland.lua';config.write_text('''hl.monitor({output="",mode="1280x800@60",position="0x0",scale=1})
hl.config({general={gaps_in=0,gaps_out=0,border_size=2},animations={enabled=false},input={follow_mouse=0},misc={disable_hyprland_logo=true,disable_splash_rendering=true}})
hl.window_rule({name="isolated-test-float",match={class=".*"},float=true,size={500,300},center=true})
__observed = {}
hl.on("window.minimize", function(w, requested) table.insert(__observed, {mapped=w and w.mapped, requested=requested, address=w and w.address}) end)
__native_policy = dofile("'''+str(test_source)+'''")
''')
  env=dict(parent_env,XDG_RUNTIME_DIR=str(scratch),AQ_BACKEND='wayland',WAYLAND_DISPLAY=parent_display,HYPRLAND_NO_SD_NOTIFY='1',HYPRLAND_NO_SD_VARS='1',LIBGL_ALWAYS_SOFTWARE='1',PATH=str(bin_dir)+':'+parent_env['PATH'])
  env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
  with (root/'compositor.log').open('w') as log:
   compositor=subprocess.Popen([compositor_binary,'--config',str(config)],env=env,stdout=log,stderr=log)
   for _ in range(100):
    if compositor.poll() is not None: raise RuntimeError('Nested compositor exited early; inspect compositor.log')
    try: instances=json.loads(call(env,'instances','-j'))
    except Exception: instances=[]
    if instances:
     env['HYPRLAND_INSTANCE_SIGNATURE']=instances[0]['instance'];env['WAYLAND_DISPLAY']=instances[0]['wl_socket'];break
    time.sleep(.1)
   else: raise RuntimeError('Nested compositor did not create IPC')
   assert env['HYPRLAND_INSTANCE_SIGNATURE']!=parent_signature and env['XDG_RUNTIME_DIR']==str(scratch)
   def ctl(*args): return call(env,*args)
   def clients(): return json.loads(ctl('clients','-j'))
   def wait(predicate,label):
    for _ in range(80):
     try:
      if predicate():return
     except (subprocess.CalledProcessError, json.JSONDecodeError): pass
     time.sleep(.1)
    raise RuntimeError('Timeout: '+label)
   def window(app): return next((w for w in clients() if w['class']==app),None)
   def spawn(letter,color):
    app='codex-native-policy-test-'+letter
    proc=subprocess.Popen(['foot','-c','/dev/null','--app-id='+app,'--title=Isolated native policy '+letter,'-o','colors-dark.background='+color,'-o','colors-light.background='+color,'sleep','150'],env=env,stdout=log,stderr=log);processes.append(proc)
    wait(lambda:window(app),'foot '+letter);w=window(app)
    ctl('dispatch','hl.dsp.window.resize({window="address:'+w['address']+'",x=500,y=300,relative=false})')
    ctl('dispatch','hl.dsp.window.move({window="address:'+w['address']+'",x=100,y=100,relative=false})')
    return w
   wait(lambda:bool(json.loads(ctl('monitors','-j'))),'nested IPC/monitor ready')
   def calls():return calls_file.read_text().splitlines() if calls_file.exists() else []
   def status():
    raw=ctl('repl','local s=__native_policy.status();print(s.queued,s.tracked,s.cooling)').strip()
    return tuple(int(x) for x in raw.split())
   if args.native_gtk:
    gtk=scratch/'native-gtk.py'
    gtk.write_text("""import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,Gio,GLib
app=Gtk.Application(application_id='org.example.BoundedNativeMinimize',flags=Gio.ApplicationFlags.NON_UNIQUE)
def activate(app):
 w=Gtk.ApplicationWindow(application=app,title='Isolated native policy GTK probe')
 w.set_default_size(320,200);w.show_all()
 GLib.timeout_add(650,lambda:(w.iconify(),False)[1])
 GLib.timeout_add(1800,lambda:(app.quit(),False)[1])
app.connect('activate',activate);app.run([])
""")
    gtk_env=dict(env,GDK_BACKEND='wayland',WAYLAND_DEBUG='client',GTK_USE_PORTAL='0',NO_AT_BRIDGE='1')
    with (root/'gtk-wire.log').open('w') as wire:
     probe=subprocess.Popen(['/usr/bin/python3',str(gtk)],env=gtk_env,stdout=log,stderr=subprocess.PIPE,text=True);processes.append(probe)
     def filter_wire():
      for line in probe.stderr:
       if '.set_minimized(' in line:wire.write(line)
     reader=threading.Thread(target=filter_wire,daemon=True);reader.start()
     wait(lambda:len(calls())==1,'actual GTK protocol event reaches policy and helper')
     observed=ctl('repl','print(#__observed);local e=__observed[1];print(tostring(e.mapped),tostring(e.requested),e.address)').strip().split()
     assert observed==['1','true','true',calls()[0]], observed
     probe.wait(timeout=5);reader.join(timeout=2)
    wire_count=(root/'gtk-wire.log').read_text().count('.set_minimized(')
    assert wire_count==1,wire_count
    wait(lambda:status()==(0,0,0),'GTK event cooldown cleanup')
    results['cases'].append({'case':'actual Wayland GTK set_minimized -> guarded core -> hl.on -> unchanged bounded policy -> real stub helper','pass':True,'native_protocol_transport_test':True,'wire_minimize_requests':wire_count,'observed_callback_signature':'HL.Window(mapped=true), boolean true','helper_calls':len(calls()),'core_binary_sha256':hashlib.sha256(Path(compositor_binary).read_bytes()).hexdigest()})
    calls_file.write_text('')
   a=spawn('a','992222')
   expression='local w=hl.get_window("address:'+a['address']+'");for i=1,1000 do __native_policy.handle(w,true) end'
   ctl('eval',expression);wait(lambda:len(calls())==1,'coalesced helper')
   ctl('eval',expression);time.sleep(.3);assert len(calls())==1
   results['cases'].append({'case':'1000 repeated requests for actual mapped userdata plus cooldown burst launch one real helper process','pass':True,'requests_per_burst':1000,'helper_calls':len(calls()),'native_protocol_transport_test':False})
   wait(lambda:status()==(0,0,0),'monotonic cooldown cleanup')
   ctl('eval','__native_policy.handle(hl.get_window("address:'+a['address']+'"),true)')
   wait(lambda:len(calls())==2,'normal retry after cooldown')
   results['cases'].append({'case':'normal retry after1s HL timer cooldown','pass':True,'helper_calls':len(calls())})
   wait(lambda:status()==(0,0,0),'retry cleanup')
   b=spawn('b','224499');c=spawn('c','229944')
   code='for _,address in ipairs({"'+a['address']+'","'+b['address']+'","'+c['address']+'"}) do __native_policy.handle(hl.get_window("address:"..address),true) end'
   ctl('eval',code);wait(lambda:len(calls())==5,'three distinct FIFO helpers')
   assert calls()[-3:]==[a['address'],b['address'],c['address']]
   wait(lambda:status()==(0,0,0),'all cooldown records removed')
   results['cases'].append({'case':'three actual userdata windows drain FIFO via real HL timers; all records clean up','pass':True,'order_matches':True,'helper_calls':len(calls())})
   before_calls=len(calls());ctl('eval','__native_policy.handle(hl.get_window("address:'+b['address']+'"),true);hl.dispatch(hl.dsp.window.move({window="address:'+b['address']+'",workspace="special:fixture",follow=false}))')
   time.sleep(.25);assert len(calls())==before_calls and status()==(0,0,0)
   results['cases'].append({'case':'actual queued window moved special before drain is skipped','pass':True})
   ctl('eval','__native_policy.handle(hl.get_window("address:'+c['address']+'"),true);hl.dispatch(hl.dsp.window.close({window="address:'+c['address']+'"}))')
   time.sleep(.25);assert len(calls())==before_calls and status()==(0,0,0)
   results['cases'].append({'case':'actual queued window closes before drain: expired weak userdata skipped','pass':True})
   blocked.touch(); started=time.monotonic()
   ctl('eval','__native_policy.handle(hl.get_window("address:'+a['address']+'"),true)')
   wait(lambda:child_pids.exists(),'blocked helper parent and child started')
   parent_pid, child_pid = [int(x) for x in child_pids.read_text().split()]
   def running(pid):
    try:return Path('/proc/'+str(pid)+'/stat').read_text().split()[2] not in ('Z','X')
    except FileNotFoundError:return False
   assert running(parent_pid) and running(child_pid)
   wait(lambda:not running(parent_pid) and not running(child_pid),'timeout kills TERM-ignoring helper and child')
   elapsed=time.monotonic()-started
   assert 5.8 <= elapsed <= 8.0, elapsed
   blocked.unlink(); before_calls=len(calls())
   wait(lambda:status()==(0,0,0),'blocked helper record cleanup')
   results['cases'].append({'case':'fixed GNU timeout kills TERM-ignoring helper parent and blocked child in same process group','pass':True,'elapsed_seconds':round(elapsed,3),'parent_terminated':not running(parent_pid),'child_terminated':not running(child_pid),'native_protocol_transport_test':False})
   ctl('eval','__native_policy.handle(hl.get_window("address:'+a['address']+'"),true)');ctl('reload');time.sleep(.3)
   assert len(calls())==before_calls and status()==(0,0,0)
   results['cases'].append({'case':'config reload cancels old pending timer/state, no stale helper launched','pass':True})
   if args.native_gtk:
    before_calls=len(calls())
    with (root/'gtk-after-reload-wire.log').open('w') as wire:
     probe=subprocess.Popen(['/usr/bin/python3',str(gtk)],env=gtk_env,stdout=log,stderr=subprocess.PIPE,text=True);processes.append(probe)
     def filter_reload_wire():
      for line in probe.stderr:
       if '.set_minimized(' in line:wire.write(line)
     reader=threading.Thread(target=filter_reload_wire,daemon=True);reader.start()
     wait(lambda:len(calls())==before_calls+1,'actual native request after reload reaches exactly one handler')
     probe.wait(timeout=5);reader.join(timeout=2)
    assert len(calls())==before_calls+1
    assert ctl('repl','print(#__observed)').strip()=='1'
    assert (root/'gtk-after-reload-wire.log').read_text().count('.set_minimized(')==1
    wait(lambda:status()==(0,0,0),'post-reload native event cleanup')
    results['cases'].append({'case':'successful reload resets state/listeners; one actual new GTK minimize request launches exactly one helper and one observer callback','pass':True,'native_protocol_transport_test':True,'helper_calls_for_request':1,'observer_callbacks':1})
   results['config_errors']=ctl('configerrors').strip();assert not results['config_errors']
   results['nested_version']=json.loads(ctl('version','-j'))
   ctl('dispatch','hl.dsp.exit()')
   compositor.wait(timeout=5);compositor=None
except Exception as exc:
 results['error']=type(exc).__name__+': '+str(exc)
finally:
 for p in processes:
  if p.poll() is None:p.terminate()
 if compositor and compositor.poll() is None:
  compositor.terminate()
  try:compositor.wait(timeout=5)
  except subprocess.TimeoutExpired:compositor.kill();compositor.wait()
 after={w['address']:w for w in json.loads(call(parent_env,'clients','-j'))}
 changed=[]
 for address,old in original_geometry.items():
  live=after.get(address)
  if live and any(live.get(k)!=old[k] for k in ('at','size','fullscreen')): changed.append(address)
 results['parent_geometry_unchanged']=not changed
 if args.restore_parent_focus and original_focus and original_focus in after:
  results['parent_ipc_mutation_performed']=True
  call(parent_env,'eval','local w=hl.get_window("address:'+original_focus+'");if w and w.mapped then hl.dispatch(hl.dsp.focus({window=w}));hl.dispatch(hl.dsp.window.alter_zorder({mode="top",window=w})) end')
 results['parent_focus_restored']=json.loads(call(parent_env,'activewindow','-j')).get('address')==original_focus
 (root/'results.json').write_text(json.dumps(results,indent=2)+'\n')
 print(json.dumps({k:v for k,v in results.items() if k!='nested_version'},indent=2))
 if results.get('error'):raise SystemExit(1)
