local rules={}
local function run(registry, plugin)
  rules={}
  hl={plugin={hyprbars=plugin and {} or nil}}
  o={native_window_controls=registry,window=function(match,rule)rules[match]=rule end}
  dofile('configuration-example.lua')
  return rules
end
local function count(t)local n=0;for _ in pairs(t)do n=n+1 end;return n end
local current=run(nil,true)
assert(count(current)==0,'Safe default keeps controls for every unknown app')
current=run({chatgpt=true,['brave-origin']=true},true)
assert(count(current)==2 and current['^chatgpt$'] and current['^brave-origin$'])
local ids={'org.gnome.Foo','App + (Tools) [x] {y} \\ ^ $ | ? * .','Café.App','literal space'}
local registry={['disabled.app']=false,['truthy.string']='yes',[1]='chatgpt',['']=true,['brave-grok.com__-Default']=false}
for _,id in ipairs(ids)do registry[id]=true end
current=run(registry,true)
assert(count(current)==#ids,'Only exact true, nonempty string entries may hide the bar')
assert(not current['^disabled\\.app$'] and not current['^brave-grok\\.com__-Default$'])
assert(current['^Café\\.App$'],'UTF8 bytes must remain literal')
assert(count(run(registry,false))==0,'No plugin means no hide rules')
assert(count(run(false,true))==0 and count(run('invalid registry',true))==0,'Malformed registry must retain controls safely')
print('PASS: exact true only, malformed keys/registry ignored, no-plugin guard, exact rule count, UTF8 and regex escaping')
