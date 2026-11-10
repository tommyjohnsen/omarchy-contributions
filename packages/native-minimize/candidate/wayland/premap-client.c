// SPDX-License-Identifier: MIT
#include <wayland-client.h>
#include "xdg-shell-client-protocol.h"
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static struct wl_compositor *compositor;
static struct xdg_wm_base *wm;
static void ping(void *data, struct xdg_wm_base *base, uint32_t serial) { xdg_wm_base_pong(base, serial); }
static const struct xdg_wm_base_listener wm_listener = { ping };
static void global(void *data, struct wl_registry *registry, uint32_t name, const char *interface, uint32_t version) {
    if (!strcmp(interface, "wl_compositor")) compositor = wl_registry_bind(registry, name, &wl_compositor_interface, version < 4 ? version : 4);
    else if (!strcmp(interface, "xdg_wm_base")) {
        wm = wl_registry_bind(registry, name, &xdg_wm_base_interface, 1);
        xdg_wm_base_add_listener(wm, &wm_listener, NULL);
    }
}
static void global_remove(void *data, struct wl_registry *registry, uint32_t name) {}
static const struct wl_registry_listener registry_listener = { global, global_remove };
static void configure(void *data, struct xdg_surface *surface, uint32_t serial) { xdg_surface_ack_configure(surface, serial); }
static const struct xdg_surface_listener surface_listener = { configure };
int main(void) {
    struct wl_display *display = wl_display_connect(NULL);
    if (!display) return 1;
    struct wl_registry *registry = wl_display_get_registry(display);
    wl_registry_add_listener(registry, &registry_listener, NULL);
    if (wl_display_roundtrip(display) < 0 || !compositor || !wm) return 2;
    struct wl_surface *surface = wl_compositor_create_surface(compositor);
    struct xdg_surface *role = xdg_wm_base_get_xdg_surface(wm, surface);
    xdg_surface_add_listener(role, &surface_listener, NULL);
    struct xdg_toplevel *top = xdg_surface_get_toplevel(role);
    xdg_toplevel_set_app_id(top, "native-premap-probe");
    xdg_toplevel_set_title(top, "Unmapped native minimize probe");
    wl_surface_commit(surface); // Initial configure only: no buffer is ever attached.
    if (wl_display_roundtrip(display) < 0) return 3;
    xdg_toplevel_set_minimized(top);
    if (wl_display_roundtrip(display) < 0) return 4;
    if (wl_display_roundtrip(display) < 0) return 5;
    xdg_toplevel_destroy(top);
    xdg_surface_destroy(role);
    wl_surface_destroy(surface);
    xdg_wm_base_destroy(wm);
    wl_compositor_destroy(compositor);
    wl_registry_destroy(registry);
    wl_display_disconnect(display);
    return 0;
}
