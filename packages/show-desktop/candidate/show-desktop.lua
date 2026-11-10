-- Exact Hyprland action contract returns {ok=false}, rather than throwing,
-- for many compositor errors. Preserve markers by turning it into a failure.
local function dispatch(action)
  local result = hl.dispatch(action)
  if type(result) == 'table' and result.ok == false then
    error('Show desktop compositor action failed')
  end
  return result
end
-- Show desktop on the current workspace, without touching already-hidden apps.
-- Window tags survive config reloads and let the dock restore individual apps.
local M = {}
local function tagged(w, name)
  for _, tag in ipairs(w.tags or {}) do
    if tag == name or tag == name .. '*' then return true end
  end
  return false
end
local function tag(w, name, add)
  dispatch(hl.dsp.window.tag({window=w, tag=(add and '+' or '-') .. name}))
end
local function minimized(w)
  return w.workspace and w.workspace.name == 'special:minimized'
end
-- Moving a member out of the hidden workspace means the user/dock restored
-- or relocated it. Drop ownership immediately, before any later re-minimize.
local function on_workspace_change(w, workspace)
  if not w or not workspace or workspace.name == 'special:minimized' then return end
  for _, old in ipairs(w.tags or {}) do
    local bare = old:gsub('%*$', '')
    if bare:match('^tommy%-show%-desktop%-%d+$') or
       bare:match('^tommy%-show%-desktop%-%d+%-focus$') then
      tag(w, bare, false)
    end
  end
end
M.workspace_subscription = hl.on('window.move_to_workspace', on_workspace_change)

-- An explicit target comes from the clicked bar's monitor, not global focus.
-- Invalid IDs do nothing; never create/switch to an arbitrary workspace here.
function M.toggle(target_id)
  if target_id ~= nil and (type(target_id) ~= 'number' or target_id < 1 or target_id % 1 ~= 0) then return end
  local workspace
  if target_id ~= nil then workspace = hl.get_workspace(target_id)
  else workspace = hl.get_active_workspace() end
  if not workspace or not workspace.id or workspace.id < 1 then return end
  local id = workspace.id
  local marker = 'tommy-show-desktop-' .. id
  local focus_marker = marker .. '-focus'
  local windows = hl.get_windows()
  local pending = {}
  for _, w in ipairs(windows) do
    if tagged(w, marker) then
      if w.mapped and minimized(w) then
        pending[#pending+1] = w
      else
        -- A dock-restored or manually moved window is no longer ours to restore.
        tag(w, marker, false)
        tag(w, focus_marker, false)
      end
    end
  end
  if #pending > 0 then
    local focus
    local restored = 0
    for _, w in ipairs(pending) do
      local was_focused = tagged(w, focus_marker)
      -- Keep our markers until the restore dispatch succeeds, so an exception
      -- does not silently discard the only persisted restore information.
      dispatch(hl.dsp.window.move({window=w, workspace=tostring(id), follow=false}))
      tag(w, marker, false)
      tag(w, focus_marker, false)
      tag(w, 'omarchy-minimized-from-' .. id, false)
      restored = restored + 1
      if was_focused or not focus then focus = w end
    end
    if focus then
      dispatch(hl.dsp.focus({window=focus}))
      dispatch(hl.dsp.window.bring_to_top())
    end
    return 'restored', restored
  end
  local active = hl.get_active_window()
  local targets = {}
  for _, w in ipairs(windows) do
    if w.mapped and not w.hidden and w.workspace and w.workspace.id == id then
      targets[#targets+1] = w
    end
  end
  for _, w in ipairs(targets) do
    -- Claude Code review: stale ownership from a previous workspace must not
    -- pull a newly hidden window back there. Clear old markers before adding
    -- current markers; window tag arrays may be snapshots, including '*' tags.
    for _, old in ipairs(w.tags or {}) do
      local bare = old:gsub('%*$', '')
      if bare:match('^omarchy%-minimized%-from%-%d+$')
        or bare:match('^tommy%-show%-desktop%-%d+$')
        or bare:match('^tommy%-show%-desktop%-%d+%-focus$') then
        tag(w, bare, false)
      end
    end
    tag(w, marker, true)
    if active and active.address == w.address then tag(w, focus_marker, true) end
    tag(w, 'omarchy-minimized-from-' .. id, true)
    dispatch(hl.dsp.window.move({window=w, workspace='special:minimized', follow=false}))
  end
  -- Leave focus on the visible desktop so new windows open here normally.
  -- Focusing an already-active workspace can invoke workspace_back_and_forth.
  local current = hl.get_active_workspace()
  if not current or current.id ~= id then
    dispatch(hl.dsp.focus({workspace=tostring(id)}))
  end
  return 'hidden', #targets
end
return M
