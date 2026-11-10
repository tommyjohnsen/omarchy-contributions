"""Exercise title serialization through Lua and inspect all untrusted QML sinks."""
from pathlib import Path
import json
import re
import shlex
import subprocess

source = r'''
local binds={}
local title=[[<img src="https://example.invalid/never-load"> ' $(touch /tmp/never-run) `id` & backslash\]] .. "\n\tend"
hl={unbind=function()end,bind=function(k,cb)binds[k]=cb end,on=function()end,
 get_windows=function()return{
 {address='0xaaa',mapped=true,workspace={name='1'},focus_history_id=0,title=title,class='unsafe<class>'},
 {address='0xbbb',mapped=true,workspace={name='2'},focus_history_id=1,title='safe',class='safe'}
 }end,
 exec_cmd=function(command)io.write(command)end}
dofile('candidate/altswitch.lua')
binds['ALT + TAB']()
'''
command = subprocess.check_output(['lua', '-'], input=source, text=True)
# Parse syntax only: never execute the captured shell command.
args = shlex.split(command)
assert args[:4] == ['omarchy-shell', '-q', 'altswitch', 'show']
assert len(args) == 5, 'Window text escaped its single shell argument'
payload = json.loads(args[4])
title = payload['windows'][0]['title']
assert title.startswith('<img src="https://example.invalid/never-load">')
assert "' $(touch /tmp/never-run) `id` & backslash\\\n\tend" in title
qml = Path('candidate/AltSwitch.qml').read_text()
for sink in ('modelData.workspace', 'root.friendlyAppName(modelData.appClass)', 'modelData.title'):
    offset = qml.index('text: ' + sink)
    block = qml[qml.rfind('Text {', 0, offset):offset]
    assert 'textFormat: Text.PlainText' in block, sink
lua = Path('candidate/altswitch.lua').read_text()
assert 'diagnostics' not in lua, 'Local debug counters must not leak into upstream candidate'
assert 'SUPER +' not in lua, 'Personal Command remapping must not replace upstream ALT defaults'
print('PASS: JSON/title round trip, shell argument isolation, three PlainText sinks, no debug or personal bindings')
