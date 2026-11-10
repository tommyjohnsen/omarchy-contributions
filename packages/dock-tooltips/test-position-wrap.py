#!/usr/bin/env python3
"""Real Qt binding/wrap regressions without a visible desktop surface."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,tempfile
base=Path(__file__).resolve().parent
stock=Path('/usr/share/omarchy/shell/plugins/dock/DockWindow.qml')
old_ui=Path('/usr/share/omarchy/shell/Ui/PanelToolTip.qml')
context=json.loads((base/'baseline-context.json').read_text())
for name,path in [('DockWindow.qml',stock),('PanelToolTip.qml',old_ui)]:
 assert hashlib.sha256(path.read_bytes()).hexdigest()==context[name]['sha256'],name+' baseline changed'
def function(source,name):
 start=source.index('  function '+name+'(');brace=source.index('{',start);depth=1;index=brace+1
 while depth:
  if source[index]=='{':depth+=1
  if source[index]=='}':depth-=1
  index+=1
 return source[start:index]
with tempfile.TemporaryDirectory(prefix='dock-binding-fixture-') as directory:
 root=Path(directory);(root/'shell/plugins/dock').mkdir(parents=True);(root/'shell/Ui').mkdir(parents=True)
 shutil.copy2(stock,root/'shell/plugins/dock/DockWindow.qml');shutil.copy2(old_ui,root/'shell/Ui/PanelToolTip.qml')
 subprocess.run(['git','apply',str(base/'tooltip.patch')],cwd=root,check=True)
 (root/'Ui').mkdir()
 for entry in Path('/usr/share/omarchy/shell/Ui').iterdir():
  if entry.name=='PanelToolTip.qml':shutil.copy2(root/'shell/Ui/PanelToolTip.qml',root/'Ui/PanelToolTip.qml')
  else:(root/'Ui'/entry.name).symlink_to(entry,target_is_directory=entry.is_dir())
 (root/'Commons').symlink_to('/usr/share/omarchy/shell/Commons',target_is_directory=True)
 (root/'runtime').mkdir(mode=0o700)
 env=os.environ.copy()
 for key in ('DISPLAY','WAYLAND_DISPLAY'):env.pop(key,None)
 env.update(QT_QPA_PLATFORM='offscreen',QT_QPA_PLATFORMTHEME='generic',QT_QUICK_CONTROLS_STYLE='Basic',XDG_RUNTIME_DIR=str(root/'runtime'),XDG_CACHE_HOME=str(root/'cache'),XDG_STATE_HOME=str(root/'state'),DBUS_SESSION_BUS_ADDRESS='unix:path='+str(root/'runtime'/'no-session-bus'))
 def run(source,marker):
  (root/'shell.qml').write_text(source)
  result=subprocess.run(['quickshell','--no-color','-p',str(root)],env=env,capture_output=True,text=True,timeout=10)
  combined=result.stdout+result.stderr
  assert result.returncode==0 and marker in combined,combined
 # Test the exact popup helper functions and actual added x/y expressions.
 candidate=(root/'shell/plugins/dock/DockWindow.qml').read_text()
 block=candidate[candidate.index('    PanelToolTip {'):candidate.index('    // Running apps are drawn')]
 x=next(line.strip()[2:].strip() for line in block.splitlines() if line.strip().startswith('x:'))
 y=next(line.strip()[2:].strip() for line in block.splitlines() if line.strip().startswith('y:'))
 qml='''import QtQuick
import Quickshell
ShellRoot {
 Item { id: window; width:500; height:160
  property string position:"bottom"; property real gap:4
  property alias contentItem:scene
  Item { id:scene; anchors.fill:parent
   Item { id:body; x:50; y:120; width:400; height:40
    Item { id:appSlot; x:20; y:0; width:24; height:40 }
   }
   Item { id:oldTip; width:100; height:20; x:window.popupX(appSlot,oldTip); y:window.popupY(appSlot,oldTip) }
   Item { id:appNameTip; width:100; height:20; x:EXPR_X
    y:EXPR_Y }
  }
  FUNCTIONS
 }
 Timer { interval:30; running:true; repeat:true; property int phase:0
  onTriggered: {
   function check(ok,name) { if(!ok) throw Error(name) }
   try {
    if(phase===0) { appSlot.x=200 }
    if(phase===1) {
     const expected=window.popupX(appSlot,appNameTip)
     check(appNameTip.x===expected,"new horizontal position updates")
     check(oldTip.x!==expected,"old mapToItem-only binding reproduces stale position")
     body.x=80
    }
    if(phase===2) {
     check(appNameTip.x===window.popupX(appSlot,appNameTip),"parent translation updates")
     window.position="left";body.width=40;body.height=120;body.y=20;appSlot.x=0;appSlot.y=30
    }
    if(phase===3) { appSlot.y=90 }
    if(phase===4) {
     const expected=window.popupY(appSlot,appNameTip)
     check(appNameTip.y===expected,"new vertical position updates")
     check(oldTip.y!==expected,"old vertical binding reproduces stale position")
     console.log("PASS: horizontal vertical and parent-move position bindings");Qt.exit(0)
    }
    phase++
   } catch(error) {console.error("FAIL: "+error.message);Qt.exit(1)}
  }
 }
}
'''.replace('EXPR_X',x).replace('EXPR_Y',y).replace('FUNCTIONS',function(stock.read_text(),'popupX')+'\n'+function(stock.read_text(),'popupY'))
 run(qml,'PASS: horizontal vertical and parent-move')
 original=old_ui.read_text().replace('import QtQuick\n','import QtQuick\nimport qs.Ui\n')
 (root/'OriginalTooltip.qml').write_text(original)
 run('''import QtQuick
import Quickshell
import qs.Ui as Ui
ShellRoot {
 OriginalTooltip { id:oldTip; width:100; text:"a".repeat(120); visible:false }
 Ui.PanelToolTip { id:newTip; width:100; text:"a".repeat(120); visible:false }
 OriginalTooltip { id:oldShort; text:"File Manager"; visible:false }
 Ui.PanelToolTip { id:newShort; text:"File Manager"; visible:false }
 Timer { interval:300; running:true
  onTriggered: {
   if(oldTip.contentItem.paintedWidth<=oldTip.contentItem.width || newTip.contentItem.paintedWidth>newTip.contentItem.width+1) {
    console.error("FAIL: word-wrap bounds",oldTip.contentItem.paintedWidth,oldTip.contentItem.width,newTip.contentItem.paintedWidth,newTip.contentItem.width);Qt.exit(1);return
   }
   if (oldShort.width!==newShort.width || oldShort.contentItem.paintedHeight!==newShort.contentItem.paintedHeight) {
    console.error("FAIL: uncapped short tooltip geometry changed");Qt.exit(1);return
   }
   console.log("PASS: long unbroken tooltip stays inside capped width");Qt.exit(0)
  }
 }
}
''','PASS: long unbroken tooltip')
 print('Actual Qt regressions passed: stale position reproduced/fixed; long unbroken text bounded')
