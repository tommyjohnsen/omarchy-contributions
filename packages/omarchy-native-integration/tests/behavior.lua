-- SPDX-License-Identifier: MIT
-- Copyright (c) 2026 Tommy Johnsen
-- Deterministic monotonic-timer contract tests; no compositor/process is run.
local function fixture()
  local now, serial, timers, calls = 0, 0, {}, {}
  local handler, module
  local fail_next = false
  local peak_tracked, peak_queued, peak_timers = 0, 0, 0
  local function check_bounds()
    if module then
      local s = module.status()
      assert(s.queued >= 0 and s.queued <= 32)
      assert(s.tracked >= s.queued and s.tracked <= 32)
      peak_tracked = math.max(peak_tracked, s.tracked)
      peak_queued = math.max(peak_queued, s.queued)
    end
    peak_timers = math.max(peak_timers, #timers)
    assert(#timers <= 33, 'At most 32 cooldowns plus one drain timer')
  end
  hl = {
    on = function(event, callback)
      assert(event == 'window.minimize'); handler = callback
    end,
    timer = function(callback, options)
      assert(options.type == 'oneshot' and options.timeout > 0)
      serial = serial + 1
      local timer = { due = now + options.timeout, callback = callback, order = serial }
      timers[#timers + 1] = timer
      return timer
    end,
    exec_cmd = function(command)
      assert(command:match('^/usr/bin/timeout %-%-signal=TERM %-%-kill%-after=1s 5s omarchy%-hyprland%-window%-minimize 0x[%da-fA-F]+$'), 'Every dispatch has fixed GNU timeout and one validated address')
      assert(not command:find('--foreground', 1, true))
      calls[#calls + 1] = { command = command, time = now }
      if fail_next then fail_next = false; error('test dispatch failure') end
    end,
  }
  module = dofile('native-minimize.lua')
  local function advance(amount)
    local target = now + amount
    while true do
      local selected
      for i, timer in ipairs(timers) do
        if timer.due <= target and (not selected or timer.due < timers[selected].due
          or (timer.due == timers[selected].due and timer.order < timers[selected].order)) then selected = i end
      end
      if not selected then break end
      local timer = table.remove(timers, selected)
      now = timer.due
      timer.callback()
      check_bounds()
    end
    now = target
    check_bounds()
  end
  local function send(window, requested)
    handler(window, requested)
    check_bounds()
  end
  return {
    send = send, advance = advance, calls = calls, status = module.status,
    timer_count = function() return #timers end,
    fail_next = function() fail_next = true end,
    peaks = function() return peak_tracked, peak_queued, peak_timers end,
  }
end
local function window(i)
  return { mapped = true, address = string.format('0x%x', i), workspace = { id = 1 } }
end

-- 1000 requests while the helper is hypothetically blocked still launch once.
local f, w = fixture(), window(1)
for _ = 1, 1000 do f.send(w, true) end
assert(f.status().queued == 1 and f.status().tracked == 1 and f.timer_count() == 1)
f.advance(99); assert(#f.calls == 0)
f.advance(1); assert(#f.calls == 1 and f.calls[1].time == 100)
for _ = 1, 1000 do f.send(w, true) end
f.advance(999); assert(#f.calls == 1)
f.send(w, false); assert(f.status().tracked == 1, 'False must not bypass cooldown')
f.advance(1); assert(f.status().tracked == 0)
f.send(w, true); f.advance(100); assert(#f.calls == 2 and f.calls[2].time == 1200)
f.advance(1000); assert(f.status().tracked == 0 and f.timer_count() == 0)

-- 64 unique windows admit at most32 total pending/cooling records.
f = fixture()
for i = 1, 64 do f.send(window(i), true) end
assert(f.status().queued == 32 and f.status().tracked == 32)
f.advance(3200); assert(#f.calls == 32 and f.status().queued == 0)
for i = 2, #f.calls do assert(f.calls[i].time - f.calls[i-1].time >= 100) end
f.advance(1000); assert(f.status().tracked == 0 and f.timer_count() == 0)
local tracked, queued, timer_peak = f.peaks()
assert(tracked == 32 and queued == 32 and timer_peak <= 33)

-- All enqueue guards reject without allocating a queue record or timer.
f = fixture()
f.send(nil, true); f.send(false, true); f.send(w, false); f.send(w, nil)
local invalid = {
  {mapped=false,address='0x1',workspace={id=1}},
  {mapped=true,address='0x1'},
  {mapped=true,address='0x1',workspace={}},
  {mapped=true,address='0x1',workspace={id=-1}},
  {mapped=true,address='0x1',workspace={id=0}},
  {mapped=true,address='0x1',workspace={id='1'}},
  {mapped=true,address='0x1',workspace={id=0/0}},
  {mapped=true,address=123,workspace={id=1}},
  {mapped=true,address='0x',workspace={id=1}},
  {mapped=true,address='0x'..string.rep('a',17),workspace={id=1}},
  {mapped=true,address='0x1\n',workspace={id=1}},
  {mapped=true,address='0x1; id',workspace={id=1}},
}
for _, bad in ipairs(invalid) do f.send(bad, true) end
assert(f.status().tracked == 0 and f.timer_count() == 0 and #f.calls == 0)

-- Targets are read again at drain: closed, moved special and expired are skipped.
f = fixture()
local closed, special = window(1), window(2)
local alive = true
local expired = setmetatable({}, {__index=function(_, key) if alive then return window(3)[key] end end})
local throwing = setmetatable({}, {__index=function() error('expired object') end})
f.send(closed, true); f.send(special, true); f.send(expired, true); f.send(throwing, true)
closed.mapped = false; special.workspace = {name='special:minimized'}; alive = false
f.advance(100)
assert(#f.calls == 0 and f.status().tracked == 0 and f.timer_count() == 0)

-- Invalid queued entries do not strand a later valid entry or consume extra slots.
f = fixture(); closed = window(1); f.send(closed, true); f.send(window(2), true)
closed.mapped = false; f.advance(100)
assert(#f.calls == 1 and f.calls[1].command == '/usr/bin/timeout --signal=TERM --kill-after=1s 5s omarchy-hyprland-window-minimize 0x2')
f.advance(1000); assert(f.status().tracked == 0)

-- A dispatch exception does not stop global draining; cooldown still cleans up.
f = fixture(); f.send(window(1), true); f.send(window(2), true); f.fail_next()
f.advance(200); assert(#f.calls == 2 and f.calls[2].time == 200)
f.advance(1000); assert(f.status().tracked == 0 and f.timer_count() == 0)
print('PASS: duplicate1000, distinct64/cap32, globally paced launches, cooldown/retry, guards, closed/special/expired skip, bounded cleanup, error continuation')
