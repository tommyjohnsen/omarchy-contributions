#!/usr/bin/env python3
"""Run real shared tooltip and Unicode-expression checks without a visible UI."""
from pathlib import Path
import os, shutil, subprocess, tempfile,hashlib,json
base=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='dock-qml-fixture-') as directory:
    root=Path(directory)
    context=json.loads((base/'baseline-context.json').read_text())
    dock=Path('/usr/share/omarchy/shell/plugins/dock/DockWindow.qml')
    ui=Path('/usr/share/omarchy/shell/Ui/PanelToolTip.qml')
    for name,path in [('DockWindow.qml',dock),('PanelToolTip.qml',ui)]:
        assert hashlib.sha256(path.read_bytes()).hexdigest()==context[name]['sha256'],name+' differs from reviewed baseline'
    (root/'shell/plugins/dock').mkdir(parents=True)
    (root/'shell/Ui').mkdir(parents=True)
    shutil.copy2(dock,root/'shell/plugins/dock/DockWindow.qml')
    shutil.copy2(ui,root/'shell/Ui/PanelToolTip.qml')
    subprocess.run(['git','apply',str(base/'tooltip.patch')],cwd=root,check=True)
    (root/'Ui').mkdir()
    for entry in Path('/usr/share/omarchy/shell/Ui').iterdir():
        if entry.name=='PanelToolTip.qml':shutil.copy2(root/'shell/Ui/PanelToolTip.qml',root/'Ui/PanelToolTip.qml')
        else:(root/'Ui'/entry.name).symlink_to(entry,target_is_directory=entry.is_dir())
    (root/'Commons').symlink_to('/usr/share/omarchy/shell/Commons',target_is_directory=True)
    (root/'runtime').mkdir(mode=0o700)
    env=os.environ.copy()
    for key in ('DISPLAY','WAYLAND_DISPLAY'):
        env.pop(key,None)
    env.update(QT_QPA_PLATFORM='offscreen',QT_QPA_PLATFORMTHEME='generic',
               QT_QUICK_CONTROLS_STYLE='Basic',XDG_RUNTIME_DIR=str(root/'runtime'),
               XDG_CACHE_HOME=str(root/'cache'),XDG_STATE_HOME=str(root/'state'),
               DBUS_SESSION_BUS_ADDRESS='unix:path='+str(root/'runtime'/'no-session-bus'))
    shutil.copy2(base/'plaintext-tooltip-fixture.qml',root/'shell.qml')
    for negative,expected in [(False,0),(True,1)]:
        env['FIXTURE_FORCE_FAILURE']='1' if negative else '0'
        result=subprocess.run(['quickshell','--no-color','-p',str(root)],env=env,
                              capture_output=True,text=True,timeout=10)
        combined=result.stdout+result.stderr
        assert result.returncode==expected,combined
        assert ('FAIL: intentional negative fixture' if negative else 'PASS: markup-shaped app names') in combined,combined
        print(('negative' if negative else 'positive')+' tooltip fixture exits '+str(expected))
    # Exercise the exact candidate patch return expression in Qt's JS engine.
    expression=next(line[1:].strip() for line in (base/'tooltip.patch').read_text().splitlines()
                    if line.startswith('+') and 'return String' in line)
    shell='''import QtQuick
import Quickshell
ShellRoot {
 function truncate(name) { EXPRESSION }
 Timer {
  interval: 20; running: true
  onTriggered: {
   const emoji = "\\uD83D\\uDE00"
   const output = truncate("a".repeat(119) + emoji + "trailing")
   if (output !== "a".repeat(119) || output.length > 120 || /[\\uD800-\\uDBFF]$/.test(output)) {
     console.error("FAIL: Unicode boundary"); Qt.exit(1); return
   }
   console.log("PASS: Unicode boundary retained"); Qt.exit(0)
  }
 }
}
'''.replace('EXPRESSION',expression)
    (root/'shell.qml').write_text(shell)
    result=subprocess.run(['quickshell','--no-color','-p',str(root)],env=env,
                          capture_output=True,text=True,timeout=10)
    combined=result.stdout+result.stderr
    assert result.returncode==0 and 'PASS: Unicode boundary retained' in combined,combined
    print('Qt JS candidate Unicode boundary expression passes')
