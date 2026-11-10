-- Optional macOS migration preset, not a replacement for upstream defaults.
-- Codex: physical number keys avoid shifted-symbol ambiguity on common layouts.
-- These replace moving windows to workspaces 3 and 4; document that tradeoff.
o.rebind("SUPER + SHIFT + code:12", "Screenshot full screen", "omarchy capture screenshot fullscreen save")
o.rebind("SUPER + SHIFT + code:13", "Screenshot selected area", "omarchy capture screenshot region save")
