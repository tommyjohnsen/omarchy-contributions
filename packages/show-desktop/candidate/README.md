# Show desktop v7: experimental Omarchy bar plugin

New standalone code is MIT; LICENSE included. Frozen review snapshots and live configuration remain unchanged. This is a version-coupled experimental reference, not a stable generic plugin or human-approved release.

Load show-desktop.lua through load-controller.lua after Omarchy defaults. Install BarWidget.qml, GapModel.js and manifest.json as a user bar plugin. Merge bar-fragment.json into existing configuration: workspace numbers then the dark-red label-free button in the left section, clock independently in center/right. Clicking toggles that monitor's current normal-workspace windows; apps already minimized are excluded. When switching to another monitor's target, global focus can follow that target. Tiled restoration reinserts windows using compositor ordering and does not preserve the tiling layout.

## Fill and controller contract

Fill supports only the independent-anchor order. A later visible left-section sibling forces compact mode; every visible center/right host bounds the fill. Missing/reordered/unsupported neighbors use compact fallback, vertical bars use bar-size width, and extremely narrow geometry retains a one-pixel floor. The supported fill path shrinks to available room even when less than compact width; if the boundary is already before the button, a one-pixel floor remains. Unsupported compact placements retain normal fixed-widget limitations. Neighbor/ancestor geometry and surface width signals update immediately; a two-second fallback discovers private pool membership changes. Private host access is coupled to the supplied baseline; no stable upstream fill API is claimed.

The controller persists ownership tags across config reload. Dock/manual restoration clears ownership synchronously when a window leaves special:minimized, so a subsequent explicit minimize is not accidentally restored with the old group. Returned compositor action failures preserve retry information. Closed/new windows and cross-workspace stale ownership are handled. Partial compositor failure can degrade focus restoration. If tags/controller state are lost, manual movement from special:minimized may be required.

V6 introduced skipping the final focus dispatch when the target workspace is already active: actual V5 nested testing proved redundant focus invokes workspace_back_and_forth and can strand the hidden set on a destroyed workspace. The change preserves deliberate focusing when targeting a different active monitor workspace. The misplaced target-ID comment is corrected.

## Validation actually executed

- Fifteen Lua lifecycle fixture cases pass, including back-and-forth focus, returned failure tables, dock restore/re-minimize and partial restore.
- Fourteen geometry groups pass in actual offscreen Qt JS, including five same-row feedback probes, collisions and minimum/surface bounds.
- The exact Connections/Instantiator fragment loads in actual offscreen Qt, reacts to x/width and removes delegates.
- Separate installed nested-compositor evidence verifies eval/userdata selectors, synchronous events after workspace assignment and listener reset on config reload. Actual V5 controller tests verified two-window restore, nested callback dispatch/no-op tag removal and nonzero eval-error exit behavior; V5 back-and-forth failure is retained honestly as regression evidence.

No full live bar V7/multi-monitor click, fullscreen/maximized/pinned/grouped windows, z-order under concurrent new windows, monitor hotplug/scaling, keyboard/screen-reader interaction or Portal behavior is implied. Floating geometry fixtures do not prove tiled layout preservation. Earlier local six-window geometry testing applied to earlier live code. Prior V6 nested tests passed on installed nested Hyprland: real two-window hide/restore with back-and-forth both false and true, nested tag cleanup, geometry preservation and a synthetic second monitor. Explicit secondary targeting changes focus to that monitor and leaves primary windows unaffected. This is not a physical secondary-bar click test.

## Review evidence and integrity

Claude Code and Grok Build actual V4 reviews identified fill collisions/minimum width; Claude's V5 review found contradictory metadata and requested API/runtime evidence. Gemini's V4 assertions that eval/userdata selectors/reload cleanup were unsupported were disproven by exact source and actual runtime; those unsafe speculative API rewrites were not adopted. Codex implemented the supported corrections and ran the stated fixtures. Exact V7 provider review and human release approval remain pending.

baseline-context.json and controller-api-context.json retain unchanged baseline contracts; controller-api-followup.json supplies selector/action-result/eval/reload/event details. nested-api-evidence.json records the separate API harness. manifest-sha256.json covers exactly shipped nonmanifest files, excluding itself and NEXT-REVIEW-SOURCE.json to avoid recursive hashes; the outer selection hashes the integrity manifest too.

V7 corrects supported narrow-gap collisions (27px of room produces27px rather than36px) and immediately recomputes on orientation/bar-size changes. The exact handlers and actual geometry helper pass an offscreen Qt test that flips orientation/size while position is unchanged. Fresh actual focus/spawn-client verification is complete. The reviewer's claim that V6 raw results omit a harness field was disproven by the existing exact artifacts; measured JSON is not edited to satisfy that claim.

A bounded exhaustive sweep executes the actual GapModel in Qt JS over2,304 supported combinations of surface width, fractional position, margin, available gap and compact size. It checks the external non-overlap requirement: positive integer width and right edge no farther than the independent neighbor/surface boundary after margin when at least one pixel is available. The deliberate below-one-pixel floor and unsupported layout scope are not conflated with that guarantee.

Fresh exact-controller runtime evidence is embedded under runtime-evidence/: with back-and-forth false and true, activewindow is empty after hide, active workspace remains1, and a newly spawned native Foot client lands on1. Thus the alleged focus-on-special defect is disproven for these tested paths; no speculative monitor-focus API was added. Raw and public results are byte-identical and include verifier/controller hashes captured at run start. RUN_IDENTITY.json preserves the historical missing-field dispute and its limits. This source controller is unchanged from V6; V7 changes only geometry/signals.
