#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Execute exact orientation handlers and geometry helper in offscreen Qt."""
from pathlib import Path
import os,re,shutil,subprocess,tempfile
base=Path(__file__).resolve().parent;source=(base/'BarWidget.qml').read_text()
handlers='\n'.join(re.findall(r'^  on(?:Vertical|BarSize)Changed:.*$',source,re.M));assert handlers.count('resizeGap()')==2
qml='''import QtQuick
import Quickshell
import "GapModel.js" as GapModel
ShellRoot {
 id:root
 property bool vertical:false
 property real barSize:32
 property real gapWidth:991
 function resizeGap(){ gapWidth=GapModel.widthFor({vertical:vertical,barSize:barSize,compact:36,ownRegion:"left",workspaceRegion:"left",clockRegion:"center",ownStart:149,workspaceEnd:140.5,clockStart:1144,surfaceWidth:1512}) }
'''+handlers+'''
 Timer { interval:20; running:true; onTriggered:{
  root.vertical=true
  if(root.gapWidth!==32){console.error("FAIL vertical immediate update");Qt.exit(1);return}
  root.barSize=48
  if(root.gapWidth!==48){console.error("FAIL bar size immediate update");Qt.exit(1);return}
  root.vertical=false
  if(root.gapWidth!==991){console.error("FAIL horizontal immediate update");Qt.exit(1);return}
  console.log("PASS orientation/size immediate handlers without position changes");Qt.exit(0)
 }}
}
'''
with tempfile.TemporaryDirectory(prefix='showdesktop-orientation-') as directory:
 root=Path(directory);(root/'shell.qml').write_text(qml);shutil.copy2(base/'GapModel.js',root/'GapModel.js');(root/'runtime').mkdir(mode=0o700)
 env=os.environ.copy()
 for key in ('DISPLAY','WAYLAND_DISPLAY'):env.pop(key,None)
 env.update(QT_QPA_PLATFORM='offscreen',QT_QPA_PLATFORMTHEME='generic',XDG_RUNTIME_DIR=str(root/'runtime'),XDG_CACHE_HOME=str(root/'cache'),XDG_STATE_HOME=str(root/'state'),DBUS_SESSION_BUS_ADDRESS='unix:path='+str(root/'runtime'/'no-bus'))
 result=subprocess.run(['quickshell','--no-color','-p',str(root)],env=env,capture_output=True,text=True,timeout=10);output=result.stdout+result.stderr
 assert result.returncode==0 and 'PASS orientation/size immediate handlers' in output,output
 print('Actual Qt orientation and bar-size handlers passed without position changes')
