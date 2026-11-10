# Bounded native-minimize policy

The new MIT Lua handler delegates true minimize requests to Omarchy's stock helper. It limits tracked windows to 32, paces helper launches at 100 ms, coalesces each address for 1 s and bounds ordinary helper process groups with timeout. All three external reviewers reported no blocking static findings on the exact production digest. Codex implemented, tested and consolidated the work. Hyprland's upstream core patch and API excerpts retain their separate BSD license and original authorship.

Clarification to the reviewed README: requests during tracking/cooldown are dropped, not delayed; another request is required later. The approximately 60 blocked-helper bound assumes no repeated config reloads and the documented process-group/kernel behavior. Load once per Lua configuration.

Actual isolated tests cover real GTK transport, reload cleanup, queue/coalescing and timeout behavior. A later supplementary run also used the actual installed Omarchy helper: floating-workspace minimize/tagging, exact dock restore, and tiled-mode no-op passed. The supplemental run performed no parent IPC writes and preserved geometry; nested-window focus changed naturally.

Native protocol floods, unusual helper overlap and supported-version expansion remain explicit limits. No live plugin or compositor installation has occurred. Static reviews are not human release approval; nothing has been pushed or published.
