-- SPDX-License-Identifier: MIT
-- Copyright (c) 2026 Tommy Johnsen
-- Desktop policy only: the compositor must already emit window.minimize.
-- Never load the build-specific compatibility bridge beside a patched core.
-- Omarchy's helper supports numbered floating workspaces; false requests and
-- overflow may be ignored. This module does not implement restore policy.

local MAX_TRACKED = 32
local DRAIN_MS = 100
local COOLDOWN_MS = 1000
local tracked, tracked_count, queue = {}, 0, {}
local drain_timer
local schedule_drain

local function window_address(window)
  local kind = type(window)
  if kind ~= 'userdata' and kind ~= 'table' then return nil end
  if window.mapped ~= true then return nil end
  local workspace = window.workspace
  local id = workspace and workspace.id
  if type(id) ~= 'number' or id < 1 or id % 1 ~= 0 then return nil end
  local address = window.address
  if type(address) ~= 'string' or #address < 3 or #address > 18 then return nil end
  if not address:match('^0x[%da-fA-F]+$') then return nil end
  return address
end

local function eligible_address(window)
  -- Current Hyprland expired properties return nil. Also fail closed if a
  -- future binding throws, so one dead handle cannot strand the bounded queue.
  local ok, address = pcall(window_address, window)
  return ok and address or nil
end

local function forget(record)
  if tracked[record.address] == record then
    tracked[record.address] = nil
    tracked_count = tracked_count - 1
  end
end

local function drain()
  drain_timer = nil
  -- Skipping invalid entries is bounded by MAX_TRACKED. At most one helper
  -- is launched in this callback, even if many queued targets have vanished.
  while #queue > 0 do
    local record = table.remove(queue, 1)
    if tracked[record.address] == record then
      if eligible_address(record.window) == record.address then
        -- Set cooldown before spawning: even synchronous test/re-entry cannot
        -- enqueue another request for this address. HL timers use steady time.
        record.window = nil
        record.timer = hl.timer(function()
          record.timer = nil
          forget(record)
        end, { type = 'oneshot', timeout = COOLDOWN_MS })
        -- GNU timeout owns a process group; bound stock helper/socket stalls.
        -- Deliberately omit --foreground so ordinary child processes are covered.
        local ok = pcall(hl.exec_cmd, '/usr/bin/timeout --signal=TERM --kill-after=1s 5s omarchy-hyprland-window-minimize ' .. record.address)
        if not ok then print('Native minimize helper dispatch failed') end
        break
      end
      forget(record)
    end
  end
  if #queue > 0 then schedule_drain() end
end

schedule_drain = function()
  if not drain_timer then
    drain_timer = hl.timer(drain, { type = 'oneshot', timeout = DRAIN_MS })
  end
end

local function minimize(window, requested)
  if requested ~= true then return end
  local address = eligible_address(window)
  if not address or tracked[address] or tracked_count >= MAX_TRACKED then return end
  -- A stored HL.Window userdata contains a weak window reference, not a strong
  -- ownership claim. Re-read it at drain time instead of using a reused address.
  local record = { address = address, window = window }
  tracked[address] = record
  tracked_count = tracked_count + 1
  queue[#queue + 1] = record
  schedule_drain()
end

hl.on('window.minimize', minimize)
return {
  handle = minimize,
  status = function()
    return { queued = #queue, tracked = tracked_count, cooling = tracked_count - #queue }
  end,
}
