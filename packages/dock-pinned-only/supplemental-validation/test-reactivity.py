from pathlib import Path
import tempfile,shutil,subprocess,os,json,hashlib
pkg=Path(__file__).resolve().parent.parent;stock=Path('/usr/share/omarchy/shell/plugins/dock');evidence=pkg/'supplemental-validation';evidence.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='dock-reactivity-') as d:
 p=Path(d);target=p/'shell/plugins/dock';target.mkdir(parents=True);shutil.copy2(stock/'Dock.qml',target/'Dock.qml');subprocess.run(['git','apply',str(pkg/'pinned-only.patch')],cwd=p,check=True)
 source=(target/'Dock.qml').read_text();start=source.index('  readonly property var items: {');end=source.index('\n  readonly property var itemsByKey:',start);binding=source[start:end];shutil.copy2(stock/'DockModel.js',p/'DockModel.js')
 qml='''import QtQuick
import Quickshell
import "DockModel.js" as DockModel
ShellRoot {
 id: root
 property var dockConfig: ({pinned:["pinned"],pinnedOnly:false})
 property var defaultDockConfig: ({})
 property var pendingPins: null
 property var order: []
 property int changes: 0
 property var entries: ({pinned:{id:"pinned"},other:{id:"other"}})
 function entryForAppId(id) {return entries[id] || null}
 QtObject {id: desktopEntries; property var applications: ({values:[]}); function byId(id){return root.entries[id] || null}}
 QtObject {id: hyprland; property var toplevels: ({values:[{wayland:{appId:"pinned"},workspace:{id:1,name:"1"},address:"1"},{wayland:{appId:"other"},workspace:{id:1,name:"1"},address:"2"}]})}
 BINDING
 onItemsChanged: changes++
 Timer {interval:30;running:true;repeat:true;property int step:0
 onTriggered:{
  try {
   function check(ok,msg){if(!ok)throw Error(msg)}
   if(step===0){check(root.items.length===2,"default");root.dockConfig={pinned:["pinned"],pinnedOnly:true}}
   else if(step===1){check(root.items.length===1&&root.items[0].key==="pinned","pinnedOnly reactive");root.pendingPins=["other"]}
   else if(step===2){check(root.items.length===1&&root.items[0].key==="other","pendingPins reactive");root.pendingPins=null;root.dockConfig={pinned:["other"],pinnedOnly:true}}
   else if(step===3){check(root.items.length===1&&root.items[0].key==="other","changed pins reactive");hyprland.toplevels={values:[]}}
   else if(step===4){check(root.items.length===1&&root.items[0].windows.length===0,"toplevels reactive");root.dockConfig={pinned:[],pinnedOnly:false};hyprland.toplevels={values:[{wayland:{appId:"pinned"},workspace:{id:2,name:"2"},address:"3"}]}}
   else {check(root.items.length===1&&root.items[0].key==="pinned","unpinned restored reactive");check(root.changes>=5,"binding signals");console.log("PASS: six reactive dock binding checks; signals="+root.changes);Qt.exit(0)}
   step++
  }catch(e){console.error("FAIL: "+e.message);Qt.exit(1)}
 }
 }
}
'''.replace('BINDING',binding.replace('DesktopEntries.','desktopEntries.').replace('Hyprland.','hyprland.'))
 (p/'shell.qml').write_text(qml);(p/'runtime').mkdir(mode=0o700);env=os.environ.copy()
 for k in ['DISPLAY','WAYLAND_DISPLAY']:env.pop(k,None)
 env.update(QT_QPA_PLATFORM='offscreen',QT_QPA_PLATFORMTHEME='generic',QT_QUICK_CONTROLS_STYLE='Basic',XDG_RUNTIME_DIR=str(p/'runtime'),XDG_CACHE_HOME=str(p/'cache'),XDG_STATE_HOME=str(p/'state'),DBUS_SESSION_BUS_ADDRESS='unix:path='+str(p/'runtime/no-session-bus'))
 result=subprocess.run(['quickshell','--no-color','-p',str(p)],env=env,capture_output=True,text=True,timeout=10);out=result.stdout+result.stderr
 assert result.returncode==0 and 'PASS: six reactive' in out,out
 print(out[-1200:]);(evidence/'reactivity-result.json').write_text(json.dumps({'passed':True,'cases':6,'scope':'actual patched items binding, real Qt dependency tracking, stubbed DesktopEntries and Hyprland sources; no live dock/session interaction','patch_sha256':hashlib.sha256((pkg/'pinned-only.patch').read_bytes()).hexdigest(),'binding_sha256':hashlib.sha256(binding.encode()).hexdigest()},indent=2)+'\n')
