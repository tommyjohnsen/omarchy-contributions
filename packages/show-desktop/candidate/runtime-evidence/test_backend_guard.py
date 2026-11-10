from backend_guard import require_nested_wayland
valid=[{"name":"WAYLAND-1","hardwareDetails":{"backend":"wayland"}}]
assert require_nested_wayland(valid)["nested_only"] is True
invalid=[[],[{"name":"DP-1","hardwareDetails":{"backend":"drm"}}],
 [{"name":"WAYLAND-1","hardwareDetails":{"backend":"drm"}}],
 [{"name":"HEADLESS-1","hardwareDetails":{"backend":"headless"}}],
 [{"name":"WAYLAND-1"}],valid+[{"name":"DP-1","hardwareDetails":{"backend":"drm"}}]]
for monitors in invalid:
 try: require_nested_wayland(monitors)
 except AssertionError: pass
 else: raise AssertionError("Invalid backend accepted: "+repr(monitors))
print("PASS: nested Wayland accepted; empty/fake DRM/headless/missing/mixed outputs rejected without launching a compositor")
