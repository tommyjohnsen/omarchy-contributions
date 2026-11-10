#!/usr/bin/env python3
"""Execute the actual geometry helper in Qt JS, without a visible desktop UI."""
from pathlib import Path
import os,shutil,subprocess,tempfile
base=Path(__file__).resolve().parent
shell='''import QtQuick
import Quickshell
import "GapModel.js" as GapModel
ShellRoot {
 Timer { interval:20; running:true
  onTriggered: {
   function check(ok,name) { if (!ok) throw Error(name) }
   function data(extra) {
    let c={compact:36,margin:4,vertical:false,barSize:32,ownRegion:"left",workspaceRegion:"left",clockRegion:"center",ownStart:149,workspaceEnd:140.5,clockStart:1144,surfaceWidth:1512}
    for (let key in extra) c[key]=extra[key]
    return c
   }
   try {
    check(GapModel.widthFor(data({}))===991,"supported fill uses its own left edge")
    for(let width of [36,128,512,1000,100000]) {
     check(GapModel.widthFor(data({clockRegion:"left",clockStart:149+width+16}))===36,"same-row clock is a constant compact fallback")
    }
    check(GapModel.widthFor(data({ownRegion:"center"}))===36,"other placements stay compact")
    check(GapModel.widthFor(data({ownStart:120}))===36,"button before desktops does not oscillate")
    check(GapModel.widthFor(data({clockStart:100}))===1,"independent boundary before button uses floor")
    check(GapModel.widthFor(data({clockStart:100000}))===1359,"width is capped by surface")
    check(GapModel.widthFor(data({clockStart:NaN}))===36,"missing neighbor is safe")
    check(GapModel.widthFor(data({vertical:true}))===32,"vertical bar stays compact")
    check(GapModel.widthFor(data({surfaceWidth:160}))===7,"very small space never overflows")
    check(GapModel.widthFor(data({leftFollower:true}))===36,"left followers force compact")
    check(GapModel.widthFor(data({independentStart:700}))===547,"earlier center or right module bounds fill")
    check(GapModel.widthFor(data({surfaceWidth:149}))===1,"zero available pixels retain minimum clickable width")
    check(GapModel.widthFor(data({clockStart:180}))===27,"narrow supported gap stops before clock")
    check(GapModel.widthFor(data({independentStart:165}))===12,"narrow earlier module bounds fill")
    let propertyCases=0
    for (let surface of [300,640,1512,3000])
     for (let own of [0,0.25,149,149.75,surface/2,surface-20])
      for (let margin of [0,0.5,4,7.25])
       for (let gap of [1,1.01,1.75,5,27,35.9,36,100])
        for (let compact of [1,36,100]) {
         const boundary=own+margin+gap
         if(Math.min(boundary,surface)-own-margin < 1) continue
         const context=data({surfaceWidth:surface,ownStart:own,workspaceEnd:own-1,
          clockStart:boundary+10,independentStart:boundary,margin:margin,compact:compact})
         const width=GapModel.widthFor(context)
         check(Number.isInteger(width) && width>=1,"supported fill is positive integer")
         check(own+width <= boundary-margin+1e-9,"supported fill must not overlap next module")
         check(own+width <= surface-margin+1e-9,"supported fill remains inside surface")
         propertyCases++
        }
    check(propertyCases>=1500 && propertyCases<3000,"bounded exhaustive case count")
    console.log("PASS: "+propertyCases+" supported non-overlap property cases")
    console.log("PASS: fourteen geometry case groups including five coupled-width probes");Qt.exit(0)
   } catch(error) { console.error("FAIL: "+error.message);Qt.exit(1) }
  }
 }
}
'''
with tempfile.TemporaryDirectory(prefix='showdesktop-gap-fixture-') as directory:
 root=Path(directory);shutil.copy2(base/'GapModel.js',root/'GapModel.js');(root/'shell.qml').write_text(shell);(root/'runtime').mkdir(mode=0o700)
 env=os.environ.copy()
 for key in ('DISPLAY','WAYLAND_DISPLAY'):env.pop(key,None)
 env.update(QT_QPA_PLATFORM='offscreen',QT_QPA_PLATFORMTHEME='generic',QT_QUICK_CONTROLS_STYLE='Basic',XDG_RUNTIME_DIR=str(root/'runtime'),XDG_CACHE_HOME=str(root/'cache'),XDG_STATE_HOME=str(root/'state'),DBUS_SESSION_BUS_ADDRESS='unix:path='+str(root/'runtime'/'no-session-bus'))
 result=subprocess.run(['quickshell','--no-color','-p',str(root)],env=env,capture_output=True,text=True,timeout=10)
 combined=result.stdout+result.stderr
 assert result.returncode==0 and 'PASS: fourteen geometry case groups' in combined,combined
 print('Actual Qt JS gap model passed fourteen groups, five same-row probes and bounded non-overlap property sweep')
 print(next(line for line in combined.splitlines() if 'supported non-overlap property cases' in line))
