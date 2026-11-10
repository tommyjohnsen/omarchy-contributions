-- Windows-style ALT+TAB for Hyprland: cycle every window on every workspace,
-- most recently used first. Hold ALT, tap TAB to move down the list, release
-- ALT to jump to the highlighted window. ALT+SHIFT+TAB moves back up, ESCAPE
-- cancels.
--
-- Load it from ~/.config/hypr/bindings.lua:
--
--   dofile(os.getenv("HOME") .. "/.config/omarchy/plugins/io.github.pablo-merino.altswitch/altswitch.lua")
--
-- This half owns all the state and all the keys. The list is drawn by the
-- companion shell plugin, which renders what it is told and nothing else.
--
-- Two details that make it behave like Windows rather than like `cyclenext`:
--   * The list is snapshotted when the switch starts and then frozen, so the
--     order cannot shuffle underneath you while you are tabbing through it.
--   * Selection is virtual. Focus moves once, on commit. Focusing on every tap
--     would drag you across workspaces on the way past.

local altswitch = { windows = {}, index = 1, active = false }

-- Single-quote a string for the shell. Omarchy's config helpers provide this,
-- but this file also has to work without them.
local function shell_quote(value)
  return "'" .. tostring(value):gsub("'", "'\\''") .. "'"
end

local function altswitch_send(method, argument)
  local command = "omarchy-shell -q altswitch " .. method
  if argument then
    command = command .. " " .. shell_quote(argument)
  end
  hl.exec_cmd(command)
end

-- Minimal JSON string escaping. Window titles are arbitrary text and routinely
-- contain quotes and backslashes.
local function altswitch_json_string(value)
  local escaped = tostring(value or "")
    :gsub("\\", "\\\\")
    :gsub('"', '\\"')
    :gsub("[%c]", function(control) return string.format("\\u%04x", control:byte()) end)
  return '"' .. escaped .. '"'
end

local function altswitch_payload()
  local rows = {}
  for _, window in ipairs(altswitch.windows) do
    rows[#rows + 1] = string.format(
      '{"title":%s,"appClass":%s,"workspace":%s}',
      altswitch_json_string(window.title),
      altswitch_json_string(window.class),
      altswitch_json_string(window.workspace and window.workspace.name or "")
    )
  end

  return string.format(
    '{"windows":[%s],"index":%d}',
    table.concat(rows, ","),
    altswitch.index - 1 -- the plugin indexes from zero
  )
end

local function altswitch_teardown()
  altswitch.active = false
  altswitch.windows = {}
  altswitch_send("hide")
end

local function altswitch_commit()
  if not altswitch.active then
    return -- nothing in flight; the Alt release fires on every switch-less tap
  end

  -- Resolve the selection before clearing the frozen list. In Hyprland0.57,
  -- expired window properties return nil; a closed selection cancels safely.
  local target = altswitch.windows[altswitch.index]
  local address = target and target.address

  altswitch_teardown()

  -- Dispatched out of process on purpose. Focusing directly from inside the key
  -- callback updates Hyprland's idea of the active window but does not settle
  -- until the next input event, so the switch looks like it did nothing until
  -- you tap a key again. Going through hyprctl runs the same dispatcher from
  -- outside the input callback, where it takes effect at once.
  if type(address) == "string" and address:match("^0x%x+$") then
    -- Both actions run in one compositor IPC evaluation, outside the input
    -- callback. Resolve the live selected target again, and raise that target
    -- explicitly; never raise a different window merely because focus changed.
    local activate = string.format(
      'local selected = hl.get_window("address:%s"); '
        .. 'if selected and selected.mapped then '
        .. 'hl.dispatch(hl.dsp.focus({ window = selected })); '
        .. 'if selected.mapped then '
        .. 'hl.dispatch(hl.dsp.window.alter_zorder({ mode = "top", window = selected })) '
        .. 'end end', address)
    hl.exec_cmd("hyprctl eval " .. shell_quote(activate))
  end
end

local function altswitch_snapshot()
  local windows = {}
  for _, window in ipairs(hl.get_windows()) do
    local workspace = window.workspace
    if window.mapped and workspace and not workspace.special then
      windows[#windows + 1] = window
    end
  end

  table.sort(windows, function(a, b) return a.focus_history_id < b.focus_history_id end)
  return windows
end

local function altswitch_step(delta)
  -- Already switching: just move the cursor, wrapping at both ends.
  if altswitch.active then
    altswitch.index = (altswitch.index - 1 + delta) % #altswitch.windows + 1
    altswitch_send("select", tostring(altswitch.index - 1))
    return
  end

  altswitch.windows = altswitch_snapshot()
  if #altswitch.windows < 2 then
    return
  end

  -- Entry 1 is the window you are already on, so one tap has to land on entry 2
  -- and one back-tap has to wrap to the oldest.
  altswitch.index = delta % #altswitch.windows + 1
  altswitch.active = true
  altswitch_send("show", altswitch_payload())
end

-- Self-heal hook for the panel. If the ALT release is ever missed, the panel
-- gives up on its own after a few seconds and calls this, so the two halves
-- cannot disagree about whether a switch is still in progress.
_G.__altswitch_cancel = altswitch_teardown

-- Omarchy binds ALT+TAB four times by default (cyclenext and bring_to_top, in
-- both directions), so both chords are cleared before rebinding.
hl.unbind("ALT + TAB")
hl.unbind("ALT + SHIFT + TAB")
hl.bind("ALT + TAB", function() altswitch_step(1) end, { description = "Switch window" })
hl.bind("ALT + SHIFT + TAB", function() altswitch_step(-1) end, { description = "Switch window (reverse)" })
hl.bind("ALT + ESCAPE", altswitch_teardown, { non_consuming = true, description = "Cancel window switch" })

-- Preserve upstream's raw Alt key-up path and default keycodes. Alternative
-- named modifier-release bindings are a separate optional experiment, not
-- required to fix activation/raising or plain-text rendering.
local ALT_KEYCODES = { [64] = true, [108] = true }

hl.on("input.keyboard.key", function(keycode, _, state)
  if state == 0 and altswitch.active and ALT_KEYCODES[keycode] then
    altswitch_commit()
  end
end)
