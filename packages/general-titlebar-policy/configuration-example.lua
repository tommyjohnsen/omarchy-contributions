-- Explicit overrides, not automatic detection of client-side controls.
-- Unknown apps retain Omarchy controls by default. Add an exact class only
-- after checking its actual controls, preferences, window types and version.
-- For example: o.native_window_controls = { ['verified-app-id'] = true }
if o.native_window_controls == nil then o.native_window_controls = {} end
local controls = type(o.native_window_controls) == 'table' and o.native_window_controls or {}
if hl.plugin.hyprbars then
  for class, enabled in pairs(controls) do
    if type(class) == 'string' and class ~= '' and enabled == true then
      -- Escape only RE2 metacharacters. Preserve UTF-8 bytes and literal spaces;
      -- escaping each non-word byte can corrupt a non-ASCII application ID.
      local escaped = class:gsub('[\\.^$|?*+()%[%]{}]', '\\%0')
      o.window('^' .. escaped .. '$', { ['hyprbars:no_bar'] = true })
    end
  end
end
