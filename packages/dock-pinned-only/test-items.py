#!/usr/bin/env python3
"""Exercise the patched real items binding with desktop-entry/toplevel fixtures."""
from pathlib import Path
import os, shutil, subprocess, tempfile
base=Path(__file__).resolve().parent
stock=Path('/usr/share/omarchy/shell/plugins/dock')
with tempfile.TemporaryDirectory(prefix='dock-items-fixture-') as directory:
    root=Path(directory);target=root/'shell/plugins/dock';target.mkdir(parents=True)
    shutil.copy2(stock/'Dock.qml',target/'Dock.qml')
    subprocess.run(['git','apply',str(base/'pinned-only.patch')],cwd=root,check=True)
    text=(target/'Dock.qml').read_text()
    start=text.index('  readonly property var items: {')+len('  readonly property var items: {')
    end=text.index('\n  readonly property var itemsByKey:',start)
    body=text[start:end].rstrip();assert body.endswith('}')
    body=body[:-1] # Outer property braces become the fixture function body.
    shutil.copy2(stock/'DockModel.js',root/'DockModel.js')
    shell='''import QtQuick
import Quickshell
import "DockModel.js" as DockModel
ShellRoot {
 function items(config, defaultConfig, pins) {
  const known = { "pinned": {id:"pinned"}, "other": {id:"other"} }
  const DesktopEntries = {applications:{values:[]}, byId:function(id){return known[id] || null}}
  const Hyprland = {toplevels:{values:[
    {wayland:{appId:"pinned"},workspace:{id:1,name:"1"},address:"1"},
    {wayland:{appId:"other"},workspace:{id:1,name:"1"},address:"2"},
    {wayland:{appId:"different.appid"},workspace:{id:1,name:"1"},address:"3"},
    {wayland:{appId:"unknown"},workspace:{name:"special:minimized"},address:"4"}
  ]}}
  const root = {dockConfig:config || {}, pendingPins:pins, order:[],
   entryForAppId:function(id){return id==="different.appid" ? known.pinned : known[id] || null}}
  const dockConfig = root.dockConfig
  const defaultDockConfig = defaultConfig || {}
  BODY
 }
 Timer { interval:20; running:true
  onTriggered: {
   function check(ok, label) { if (!ok) throw Error(label) }
   try {
    const unset=items({pinned:["pinned.desktop"]})
    check(unset.map(x=>x.key).join(",")==="pinned,other,unknown", "default includes normal and minimized unpinned windows")
    check(unset[0].windows.length===2, "desktop identity joins differing appId")
    const enabled=items({pinned:["pinned.desktop"],pinnedOnly:true})
    check(enabled.length===1 && enabled[0].key==="pinned" && enabled[0].windows.length===2, "pinned-only filters unpinned windows")
    check(items(undefined,{pinned:["pinned"]}).length===3,"absent config falls back safely")
    check(items(null,{pinned:["pinned"]}).length===3,"null public config resolves to actual empty fallback")
    check(items({pinned:[],pinnedOnly:true}).length===0,"empty pins do not throw")
    check(items({pinned:["pinned"],pinnedOnly:"true"}).length===3,"only boolean true enables")
    const changed=items({pinned:["other"],pinnedOnly:true})
    check(changed.length===1 && changed[0].key==="other", "updated config uses new pins")
    const pending=items({pinned:["pinned"],pinnedOnly:true},{},["other"])
    check(pending.length===1 && pending[0].key==="other", "pending pins take precedence")
    console.log("PASS: eight real-binding dock items behavior checks");Qt.exit(0)
   } catch(error) { console.error("FAIL: "+error.message);Qt.exit(1) }
  }
 }
}
'''.replace('BODY',body)
    (root/'shell.qml').write_text(shell);(root/'runtime').mkdir(mode=0o700)
    env=os.environ.copy()
    for key in ('DISPLAY','WAYLAND_DISPLAY'):env.pop(key,None)
    env.update(QT_QPA_PLATFORM='offscreen',QT_QPA_PLATFORMTHEME='generic',QT_QUICK_CONTROLS_STYLE='Basic',XDG_RUNTIME_DIR=str(root/'runtime'),XDG_CACHE_HOME=str(root/'cache'),XDG_STATE_HOME=str(root/'state'),DBUS_SESSION_BUS_ADDRESS='unix:path='+str(root/'runtime'/'no-session-bus'))
    result=subprocess.run(['quickshell','--no-color','-p',str(root)],env=env,capture_output=True,text=True,timeout=10)
    combined=result.stdout+result.stderr
    assert result.returncode==0 and 'PASS: eight real-binding' in combined,combined
    print('Eight actual patched Dock.qml items-binding behavior checks pass in Qt JS')
