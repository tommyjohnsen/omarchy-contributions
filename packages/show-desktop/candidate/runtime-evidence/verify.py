#!/usr/bin/env python3
"""Run only against a disposable nested compositor; never source user config."""
from pathlib import Path
import os,json,time,subprocess,shutil,tempfile,hashlib,argparse,datetime,signal
from backend_guard import require_nested_wayland
root=Path(__file__).resolve().parent
candidate=root/'show-desktop.lua'
parser=argparse.ArgumentParser()
parser.add_argument('--hyprland', default='Hyprland', help='Explicit compositor binary; default installed Hyprland')
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
results={'candidate_sha256':hashlib.sha256(candidate.read_bytes()).hexdigest(),'candidate':'immutable V6 post-hide focus/spawn gate','script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'raw_json_transformations':[],'run_started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'parent_ipc_mutation_performed':False,'physical_keyboard_test':False,'nested_runtime_only':True,'cases':[]}
processes=[]; compositor=None; private_process_groups=[]
try:
 with tempfile.TemporaryDirectory(prefix='s',dir='/tmp') as tmp:
  scratch=Path(tmp); bin_dir=scratch/'bin';bin_dir.mkdir()
  test_source=scratch/'policy.lua';test_source.write_bytes(candidate.read_bytes())
  config=scratch/'hyprland.lua';config.write_text('''hl.monitor({output="",mode="1280x800@60",position="0x0",scale=1})
hl.config({general={gaps_in=0,gaps_out=0,border_size=2},animations={enabled=false},input={follow_mouse=0},misc={disable_hyprland_logo=true,disable_splash_rendering=true}})
hl.window_rule({name="isolated-test-float",match={class=".*"},float=true,size={500,300},center=true})
o={}
o.show_desktop = dofile("'''+str(test_source)+'''")
''')
  env=dict(parent_env,XDG_RUNTIME_DIR=str(scratch),AQ_BACKEND='wayland',WAYLAND_DISPLAY=parent_display,HYPRLAND_NO_SD_NOTIFY='1',HYPRLAND_NO_SD_VARS='1',LIBGL_ALWAYS_SOFTWARE='1',PATH=str(bin_dir)+':'+parent_env['PATH'])
  for key in ['HYPRLAND_INSTANCE_SIGNATURE','AQ_BACKEND','AQ_DRM_DEVICES','WLR_BACKENDS','HYPRLAND_HEADLESS_ONLY','LIBSEAT_BACKEND','SEATD_SOCK','DBUS_SYSTEM_BUS_ADDRESS','NOTIFY_SOCKET','LISTEN_FDS','LISTEN_PID']:env.pop(key,None)
  env['AQ_BACKEND']='wayland'
  with (root/'compositor.log').open('w') as log:
   compositor=subprocess.Popen([compositor_binary,'--config',str(config)],env=env,stdout=log,stderr=log,start_new_session=True)
   private_process_groups.append(compositor.pid)
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
    proc=subprocess.Popen(['foot','-c','/dev/null','--app-id='+app,'--title=Isolated native policy '+letter,'-o','colors-dark.background='+color,'-o','colors-light.background='+color,'sleep','150'],env=env,stdout=log,stderr=log,start_new_session=True);processes.append(proc);private_process_groups.append(proc.pid)
    wait(lambda:window(app),'foot '+letter);w=window(app)
    ctl('dispatch','hl.dsp.window.resize({window="address:'+w['address']+'",x=500,y=300,relative=false})')
    ctl('dispatch','hl.dsp.window.move({window="address:'+w['address']+'",x=100,y=100,relative=false})')
    return w
   wait(lambda:bool(json.loads(ctl('monitors','-j'))),'nested IPC/monitor ready')
   results.update(require_nested_wayland(json.loads(ctl('monitors','-j'))))
   def calls():return calls_file.read_text().splitlines() if calls_file.exists() else []
   def status():
    raw=ctl('repl','local s=__native_policy.status();print(s.queued,s.tracked,s.cooling)').strip()
    return tuple(int(x) for x in raw.split())
   a=spawn('a','992222');b=spawn('b','224499')
   addresses=[a['address'],b['address']]
   def live():return {w['address']:w for w in clients() if w['address'] in addresses}
   def own_tags(w):return [tag for tag in w.get('tags',[]) if tag.rstrip('*').startswith('tommy-show-desktop-')]
   noop=ctl('repl','local r=hl.dispatch(hl.dsp.window.tag({window=hl.get_window("address:'+a['address']+'"),tag="-not-present-synthetic-tag"}));print(tostring(r.ok),tostring(r.error))').strip()
   assert noop.split()[0]=='true',noop
   results['cases'].append({'case':'real missing-tag removal is successful no-op','pass':True,'result':noop})
   ctl('eval','__restore_events={};hl.on("window.move_to_workspace",function(w,ws) if ws.id==1 then local n=0;for _,tag in ipairs(w.tags or {}) do if tag:match("^tommy%-show%-desktop%-%d+") then n=n+1 end end;table.insert(__restore_events,n) end end)')
   for back_and_forth in [False,True]:
    flag='true' if back_and_forth else 'false'
    ctl('eval','hl.config({binds={workspace_back_and_forth='+flag+'}});hl.dispatch(hl.dsp.focus({workspace="2"}));hl.dispatch(hl.dsp.focus({window=hl.get_window("address:'+a['address']+'")}))')
    assert json.loads(ctl('activeworkspace','-j'))['id']==1
    before={a:{k:w[k] for k in ('at','size')} for a,w in live().items()}
    outcome=ctl('repl','local action,count=o.show_desktop.toggle(1);print(action,count)').strip().split()
    assert outcome==['hidden','2'],outcome
    hidden=live();assert len(hidden)==2
    assert all(w['workspace']['name']=='special:minimized' and own_tags(w) for w in hidden.values())
    active=json.loads(ctl('activeworkspace','-j'))['id']
    focused_after_hide=json.loads(ctl('activewindow','-j'))
    focus_subset={key:focused_after_hide.get(key) for key in ('address','class','workspace','mapped')}
    fresh=spawn('fresh-'+flag,'773399')
    fresh_workspace=fresh.get('workspace',{})
    results['cases'].append({'case':'post-hide activewindow and new actual native Wayland client placement','workspace_back_and_forth':back_and_forth,'active_workspace_after_hide':active,'active_window_after_hide':focus_subset,'new_client_workspace':fresh_workspace,'new_client_stayed_on_origin':fresh_workspace.get('id')==1,'confirmed_focus_defect':fresh_workspace.get('id')!=1})
    restored=ctl('repl','local action,count=o.show_desktop.toggle(1);print(action,count)').strip().split()
    first_restore=restored[:]
    assert active==1,active
    assert restored==['restored','2'],restored
    ctl('dispatch','hl.dsp.window.close({window="address:'+fresh['address']+'"})')
    wait(lambda:not window('codex-native-policy-test-fresh-'+flag),'fresh client closed')
    windows=live();assert all(w['workspace']['id']==1 and not own_tags(w) for w in windows.values())
    assert all(all(w[k]==before[address][k] for k in ('at','size')) for address,w in windows.items())
    nested=ctl('repl','print(table.concat(__restore_events,","))').strip();assert all(x=='0' for x in nested.split(',')),nested
    results['cases'].append({'case':'actual V6 hides/restores two windows; synchronous callback tag removals and repeated no-op removals succeed','pass':True,'workspace_back_and_forth':back_and_forth,'active_workspace_after_hide':active,'hide_result':outcome,'restore_result':restored,'restore_observer_marker_counts':nested,'floating_geometry_preserved':True,'manual_workspace_recreation_required':first_restore!=['restored','2']})
   for label,expression in [('intentional-error','error("synthetic-eval-failure")'),('nil-controller','o.show_desktop=nil;o.show_desktop.toggle(1)')]:
    response=subprocess.run([real_ctl,'eval',expression],env=env,capture_output=True,text=True,timeout=8)
    results['cases'].append({'case':'hyprctl eval '+label,'exit_code':response.returncode,'stdout':response.stdout.strip(),'stderr':response.stderr.strip(),'measurement_only':True})
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
 for pgid in private_process_groups:
  try:os.killpg(pgid,signal.SIGTERM)
  except ProcessLookupError:pass
 time.sleep(.05)
 for pgid in private_process_groups:
  try:os.killpg(pgid,signal.SIGKILL)
  except ProcessLookupError:pass
 after={w['address']:w for w in json.loads(call(parent_env,'clients','-j'))}
 changed=[]
 for address,old in original_geometry.items():
  live=after.get(address)
  if live and any(live.get(k)!=old[k] for k in ('at','size','fullscreen')): changed.append(address)
 results['missing_original_parent_windows']=[a for a in original_geometry if a not in after]
 results['parent_geometry_unchanged']=not changed and not results['missing_original_parent_windows']
 results['parent_focus_restored']=json.loads(call(parent_env,'activewindow','-j')).get('address')==original_focus
 raw=json.dumps(results,indent=2)+'\n'
 (root/'raw-results.json').write_text(raw)
 (root/'results.json').write_text(raw)
 print(json.dumps({k:v for k,v in results.items() if k!='nested_version'},indent=2))
 if results.get('error'):raise SystemExit(1)
