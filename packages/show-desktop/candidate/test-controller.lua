-- Behavioral fixtures only: these do not replace actual compositor/QML tests.
local source = arg[1] or 'show-desktop.lua'
local cases = 0
local windows, active_id, active_window, fail_address, fail_result_address, back_and_forth, dynamic_tags, event_handlers
local workspaces = {[1]={id=1},[11]={id=11}}
local function clone(t) local n={};for k,v in pairs(t) do n[k]=v end;return n end
local function has(w,t)
  for _,v in ipairs(w.tags) do if v:gsub('%*$', '')==t then return true end end
  return false
end
local function window(address,id,tags)
  return {address=address,mapped=true,hidden=false,workspace=id=='min' and {name='special:minimized'} or workspaces[id],tags=tags or {},size={x=800,y=600},at={x=120,y=80}}
end
local function marker(id) return 'tommy-show-desktop-'..id end
local function reset()
  active_id=1; fail_address=nil; fail_result_address=nil; back_and_forth=false; dynamic_tags=false; event_handlers={}
  windows={window('main',1),window('second',1),window('monitor2',11),window('oldmin','min')}
  active_window=windows[1]
end
local function tag(args)
  local w=args.window;local action=args.tag:sub(1,1);local name=args.tag:sub(2);local out={}
  for _,old in ipairs(w.tags) do if old:gsub('%*$', '')~=name then out[#out+1]=old end end
  if action=='+' then out[#out+1]=name..(dynamic_tags and '*' or '') end;w.tags=out
end
local function move(args)
  if args.window.address==fail_address then error('fixture restore dispatch failure') end
  if args.window.address==fail_result_address then return {ok=false,error='fixture result failure'} end
  args.window.workspace=args.workspace=='special:minimized' and {name='special:minimized'} or workspaces[tonumber(args.workspace)]
  if event_handlers['window.move_to_workspace'] then event_handlers['window.move_to_workspace'](args.window,args.window.workspace) end
end
hl={
 on=function(name,callback) event_handlers[name]=callback;return {remove=function()event_handlers[name]=nil end} end,
 get_active_workspace=function() return workspaces[active_id] end,
 get_workspace=function(id) return workspaces[id] end,
 get_windows=function() return clone(windows) end,
 get_active_window=function() return active_window end,
 dispatch=function(action) return action() end,
 dsp={window={tag=function(a)return function()tag(a)end end,
 move=function(a)return function()return move(a)end end,
 bring_to_top=function()return function()end end},
 focus=function(a)return function()if a.window then active_window=a.window;active_id=a.window.workspace.id else local target=tonumber(a.workspace);active_id=(back_and_forth and target==active_id) and 11 or target end end end}
}
local function check(name,fn)
 reset();fn(dofile(source));cases=cases+1;print('PASS '..name)
end
check('hide/restore preserves unrelated workspaces, old minimization and geometry',function(m)
 local a,b,c,d=table.unpack(windows)
 local kind,n=m.toggle();assert(kind=='hidden' and n==2)
 assert(a.workspace.name=='special:minimized' and b.workspace.name=='special:minimized')
 assert(c.workspace.id==11 and d.workspace.name=='special:minimized')
 kind,n=m.toggle();assert(kind=='restored' and n==2)
 assert(a.workspace.id==1 and b.workspace.id==1 and active_window==a)
 assert(a.size.x==800 and a.size.y==600 and a.at.x==120 and a.at.y==80)
 assert(not has(a,marker(1)) and not has(a,marker(1)..'-focus'))
 assert(not has(a,'omarchy-minimized-from-1'),'Bulk restore clears its now-unused origin tag')
end)
check('clicked secondary monitor controls its workspace rather than global focus',function(m)
 local a,c=windows[1],windows[3]
 local kind,n=m.toggle(11);assert(kind=='hidden' and n==1)
 assert(a.workspace.id==1 and c.workspace.name=='special:minimized')
 kind,n=m.toggle(11);assert(kind=='restored' and n==1 and c.workspace.id==11)
end)
check('rejects noninteger, missing and nonpositive target workspaces',function(m)
 for _,id in ipairs({0,-1,1.5,'11',999})do assert(m.toggle(id)==nil)end
 assert(windows[1].workspace.id==1 and windows[3].workspace.id==11)
end)
check('reload while hidden retains restore state in window tags',function(m)
 m.toggle();m=dofile(source);local kind,n=m.toggle();assert(kind=='restored' and n==2)
 assert(windows[1].workspace.id==1 and windows[2].workspace.id==1)
end)
check('manual partial restore and move are respected; their markers are cleared',function(m)
 local a,b=windows[1],windows[2];m.toggle();a.workspace=workspaces[11]
 local kind,n=m.toggle(1);assert(kind=='restored' and n==1)
 assert(a.workspace.id==11 and b.workspace.id==1 and not has(a,marker(1)))
end)
check('all manually restored windows do not cause a wasted next click',function(m)
 m.toggle();windows[1].workspace=workspaces[1];windows[2].workspace=workspaces[1]
 local new=window('new',1);windows[#windows+1]=new
 local kind,n=m.toggle();assert(kind=='hidden' and n==3 and new.workspace.name=='special:minimized')
end)
check('closed windows are ignored and newly opened windows are not mistaken for hidden ones',function(m)
 m.toggle();windows[1].mapped=false;windows[2].mapped=false
 local new=window('new',1);windows[#windows+1]=new
 local kind,n=m.toggle();assert(kind=='hidden' and n==1 and new.workspace.name=='special:minimized')
end)
check('new window remains visible when the original hidden set is restored',function(m)
 m.toggle();local new=window('new',1);windows[#windows+1]=new
 local kind,n=m.toggle();assert(kind=='restored' and n==2 and new.workspace.id==1)
end)
check('failed restore keeps marker for a later retry',function(m)
 m.toggle();fail_address='main';assert(not pcall(m.toggle))
 assert(has(windows[1],marker(1)) and windows[1].workspace.name=='special:minimized')
 fail_address=nil;local kind,n=m.toggle();assert(kind=='restored' and n==2)
end)
check('re-hide on a different workspace replaces old ownership and focus markers',function(m)
 local a,b=windows[1],windows[2]
 m.toggle(1);a.workspace=workspaces[11]
 m.toggle(11)
 assert(not has(a,marker(1)) and not has(a,marker(1)..'-focus'))
 m.toggle(1);assert(a.workspace.name=='special:minimized' and b.workspace.id==1)
 local kind,n=m.toggle(11);assert(kind=='restored' and n==2 and a.workspace.id==11)
end)
check('dynamic star-suffixed tags restore and clear cross-workspace ownership',function(m)
 dynamic_tags=true
 local a=windows[1]
 m.toggle(1);assert(has(a,marker(1)) and a.tags[1]:sub(-1)=='*')
 a.workspace=workspaces[11];m.toggle(11);assert(not has(a,marker(1)))
 m.toggle(1);assert(a.workspace.name=='special:minimized')
 m.toggle(11);assert(a.workspace.id==11 and not has(a,marker(11)))
end)
check('non-first restore failure has documented partial restore and retry state',function(m)
 local a,b=windows[1],windows[2]
 m.toggle();fail_address='second';assert(not pcall(m.toggle))
 assert(a.workspace.id==1 and not has(a,marker(1)))
 assert(b.workspace.name=='special:minimized' and has(b,marker(1)))
 fail_address=nil;local kind,n=m.toggle();assert(kind=='restored' and n==1 and b.workspace.id==1)
 -- Original focus is not promised after a partial exception; retry uses pending set.
end)
check('dock restore then explicit minimize is no longer owned by the old group',function(m)
 local a,b=windows[1],windows[2]
 m.toggle(1)
 hl.dispatch(hl.dsp.window.move({window=a,workspace='1',follow=false}))
 assert(not has(a,marker(1)))
 hl.dispatch(hl.dsp.window.move({window=a,workspace='special:minimized',follow=false}))
 local kind,n=m.toggle(1)
 assert(kind=='restored' and n==1 and b.workspace.id==1)
 assert(a.workspace.name=='special:minimized','Explicit user minimization must remain')
end)
check('returned compositor failure preserves pending restore ownership',function(m)
 m.toggle();fail_result_address='main'
 assert(not pcall(function()m.toggle()end))
 assert(has(windows[1],marker(1)) and windows[1].workspace.name=='special:minimized')
 fail_result_address=nil;local kind,n=m.toggle();assert(kind=='restored' and n==2)
end)
check('hide does not refocus current workspace when back-and-forth is enabled',function(m)
 back_and_forth=true
 local kind,n=m.toggle(1);assert(kind=='hidden' and n==2 and active_id==1)
 kind,n=m.toggle(1);assert(kind=='restored' and n==2 and active_id==1)
end)
print('PASS '..cases..' lifecycle behavior fixtures')
