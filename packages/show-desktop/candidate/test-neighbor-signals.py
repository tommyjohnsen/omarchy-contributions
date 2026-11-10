#!/usr/bin/env python3
"""Load the exact observed-neighbor Instantiator in an isolated actual Qt engine."""
from pathlib import Path
import os,subprocess,tempfile
source=Path(__file__).with_name('BarWidget.qml').read_text()
start=source.index('  Instantiator {');opening=source.index('{',start);depth=1;end=opening+1
while depth:
 if source[end]=='{':depth+=1
 elif source[end]=='}':depth-=1
 end+=1
block=source[start:end]
qml='''import QtQuick
import QtQml.Models
import Quickshell
ShellRoot {
 id:root
 property int updates:0
 property Item watched:Item { x:10; width:20 }
 property var observedNeighbors:[watched]
 function resizeGap() { updates++ }
'''+block+'''
 Timer { interval:30; running:true; onTriggered:{
  const before=root.updates
  root.watched.x+=10
  root.watched.width+=10
  Qt.callLater(function(){
   if(root.updates < before+2){console.error("FAIL signal updates");Qt.exit(1);return}
   root.observedNeighbors=[]
   Qt.callLater(function(){console.log("PASS actual observed neighbor connections and removal");Qt.exit(0)})
  })
 }}
}
'''
with tempfile.TemporaryDirectory(prefix='showdesktop-signals-') as directory:
 root=Path(directory);(root/'shell.qml').write_text(qml);(root/'runtime').mkdir(mode=0o700)
 env=os.environ.copy()
 for key in ('DISPLAY','WAYLAND_DISPLAY'):env.pop(key,None)
 env.update(QT_QPA_PLATFORM='offscreen',QT_QPA_PLATFORMTHEME='generic',XDG_RUNTIME_DIR=str(root/'runtime'),XDG_CACHE_HOME=str(root/'cache'),XDG_STATE_HOME=str(root/'state'),DBUS_SESSION_BUS_ADDRESS='unix:path='+str(root/'runtime'/'no-bus'))
 result=subprocess.run(['quickshell','--no-color','-p',str(root)],env=env,capture_output=True,text=True,timeout=10)
 output=result.stdout+result.stderr
 assert result.returncode==0 and 'PASS actual observed neighbor connections and removal' in output,output
 print('Actual Qt observed-neighbor signal and removal fixture passed')
