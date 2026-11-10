"""Reject any monitor set that does not prove a nested Wayland output."""
def require_nested_wayland(monitors):
    observations = [
        {"name": m.get("name"), "backend": m.get("hardwareDetails", {}).get("backend")}
        for m in monitors
    ]
    nested = bool(observations) and all(
        isinstance(m["name"], str) and m["name"].startswith("WAYLAND-")
        and not m["name"].startswith("HEADLESS-") and m["backend"] == "wayland"
        for m in observations
    )
    if not nested:
        raise AssertionError("Expected only nested Wayland outputs: " + repr(observations))
    return {"nested_only": nested, "monitor_observations": observations}
