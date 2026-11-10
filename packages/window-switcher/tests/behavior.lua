-- Contract fixture, not evidence of physical binding/z-order behavior.
local binds, options, commands, actions, input_hook = {}, {}, {}, {}, nil
local raw = {
 {address='0xaaa',mapped=true,workspace={name='1',special=false},focus_history_id=0,title='Current',class='app-a'},
 {address='0xbbb',mapped=true,workspace={name='2',special=false},focus_history_id=1,title='Next',class='app-b'},
 {address='0xccc',mapped=true,workspace={name='3',special=false},focus_history_id=2,title='Oldest',class='app-c'},
 {address='0xfff',mapped=true,workspace={name='special:scratch',special=true},focus_history_id=3,title='Scratchpad',class='excluded'},
}
local alive={true,true,true,true}
local windows={}
for i,fields in ipairs(raw) do
  -- Exact0.57 LuaWindow.cpp returns nil for an expired object's properties.
  windows[i]=setmetatable({}, {__index=function(_,key) if alive[i] then return fields[key] end end})
end
local focused, redirect_focus = windows[1], false
hl={
 unbind=function(k)assert(k=='ALT + TAB' or k=='ALT + SHIFT + TAB')end,
 bind=function(k,cb,o)binds[k]=cb;options[k]=o end,
 on=function(event,cb)assert(event=="input.keyboard.key");input_hook=cb end,
 get_windows=function()return windows end,
 get_window=function(selector)for i,w in ipairs(windows)do if alive[i] and selector=='address:'..w.address then return w end end end,
 exec_cmd=function(c)commands[#commands+1]=c end,
 dispatch=function(fn)fn()end,
 dsp={
  focus=function(t)return function()actions[#actions+1]={'focus',t.window};focused=redirect_focus and windows[3] or t.window end end,
  window={alter_zorder=function(t)
   assert(t.mode=='top' and t.window,'Raise must name its selected window')
   return function()actions[#actions+1]={'raise',t.window}end
  end},
 },
}
local function execute_last()
 local c=commands[#commands]
 local body=c:match("^hyprctl eval '(.*)'$")
 assert(body,'One deferred hyprctl eval expected')
 assert(not body:find("'",1,true),'Generated script needs only double quotes')
 assert(load(body))()
end
dofile('candidate/altswitch.lua')
assert(not binds['Alt_L'] and not binds['Alt_R'],'Do not replace baseline raw modifier release')
assert(options['ALT + ESCAPE'].non_consuming,'Preserve upstream cancel semantics')
local function release(code) input_hook(code,0,0) end
release(64);release(108)
assert(#commands==0,'Idle release must do nothing')
binds['ALT + TAB']();assert(commands[1]:find('altswitch show',1,true));assert(not commands[1]:find('Scratchpad',1,true));assert(#actions==0)
local idle_count=#commands;release(133);assert(#commands==idle_count,'Command release must not commit default ALT switch')
release(64);execute_last()
assert(actions[1][1]=='focus' and actions[1][2]==windows[2])
assert(actions[2][1]=='raise' and actions[2][2]==windows[2])
local count=#commands;release(108);assert(#commands==count,'Double release must not recommit')
binds['ALT + SHIFT + TAB']();release(108);execute_last()
assert(actions[#actions][2]==windows[3],'Reverse over three windows must choose the oldest, not forward target')
binds['ALT + TAB']();binds['ALT + ESCAPE']();count=#commands;release(64);assert(#commands==count)
-- Closing while selected makes the expired address nil; cancel, no activation.
binds['ALT + TAB']();alive[2]=false;release(64)
assert(commands[#commands]:find('altswitch hide',1,true),'Closed selection must tear down immediately')
alive[2]=true
-- Closing after address snapshot but before deferred IPC must not raise another app.
binds['ALT + TAB']();release(64);alive[2]=false;count=#actions;execute_last();assert(#actions==count)
alive[2]=true
-- A focus listener redirecting focus cannot redirect the explicit raise target.
redirect_focus=true;binds['ALT + TAB']();release(64);execute_last()
assert(focused==windows[3] and actions[#actions][2]==windows[2],'Raise must target selection, not whatever focus became')
print('PASS: three-window reverse, safe closed selection/deferred close, one evaluation, explicit raise target, idle/double release and cancel')
