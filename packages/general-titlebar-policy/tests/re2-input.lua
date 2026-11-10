local ids={'org.gnome.Foo','App + (Tools) [x] {y} \\ ^ $ | ? * .','Café.App','literal space'}
local registry={};for _,id in ipairs(ids)do registry[id]=true end
hl={plugin={hyprbars={}}};o={native_window_controls=registry,window=function(pattern)
 for _,id in ipairs(ids)do
  local escaped=id:gsub('[\\.^$|?*+()%[%]{}]','\\%0')
  if pattern=='^'..escaped..'$' then io.write(id,'\t',pattern,'\n');return end
 end
 error('Unexpected rule')
end}
dofile('configuration-example.lua')
