# Screenshot preset baseline context

Claude Code's static `insufficient_evidence` review found no demonstrated defect. This package supplies minimal hashed unchanged implementation excerpts and actual installed CLI help instead of asking a no-tools reviewer to infer missing contracts.

- `o.rebind` calls `hl.unbind(keys)` then `o.bind` with the same key string.
- Omarchy default workspace-move bindings use `SUPER + SHIFT + code:<workspace+9>`, exactly matching code:12/13 for workspaces 3/4. The replacement does not rely on matching a different keysym spelling.
- The installed CLI explicitly accepts `[fullscreen|region] [save]`; its wrapper invokes omasnap with `--save` and `--notify`.
- The user's local configuration loaded these strings without errors and listed the two replacement bindings. This is historical configuration evidence, not a new hardware test by this review task.

Opt-in tradeoff: enabling the preset replaces moving windows to workspaces 3 and 4 through these chords. The default shortcuts return when the snippet is removed and Hyprland configuration reloads. Do not change the global defaults for existing users.

Still pending: actual keys on other layouts, region cancel behavior, and double reload/idempotence against the target current upstream branch. No live binding was changed or screenshot taken by this context task. It is not release approval.
