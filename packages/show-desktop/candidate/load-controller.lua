-- Configuration example: load after Omarchy defaults, once per config load.
-- Copy show-desktop.lua into ~/.config/hypr/ before enabling the bar button.
o.show_desktop = dofile(os.getenv("HOME") .. "/.config/hypr/show-desktop.lua")
