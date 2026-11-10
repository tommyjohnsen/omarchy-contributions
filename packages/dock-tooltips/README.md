# Dock tooltips v3: contribution patch and Qt regressions

Patch to existing MIT-licensed Omarchy dock/shared tooltip code; preserve upstream authors/notices. New standalone fixtures are MIT under LICENSE. Frozen final-review v2 and installed files are unchanged. Coordinate the feature with upstream PR #16219 rather than duplicate its work.

## Changes after actual provider review

- Map-to-item geometry does not by itself track a moved slot/parent. Position bindings now explicitly depend on slot/body x/y and tooltip visibility, so both horizontal and vertical labels re-position after reorder/parent movement and on show. Actual Qt fixtures reproduce the old stale bindings and pass with the candidate expressions.
- The shared PanelToolTip uses WrapAtWordBoundaryOrAnywhere so a capped tooltip's long unbroken word does not overflow its background. An actual old/new shared-component fixture demonstrates overflow before the change and bounded text afterward; uncapped short-name geometry is unchanged.
- Retains PlainText rendering, a 120-code-unit bound with trailing-high-surrogate guard, and the existing 400ms delay. Fallback names include entry.id and item key even without AppLibrary. Control characters are normalized, leading/trailing whitespace removed and empty tooltips suppressed.

## Validation actually executed

Both fixture runners pin installed source hashes before applying the actual two-file patch in a temporary tree. `test-offscreen.py` checks real patched shared-tooltip plain-text/delay state, positive exit0/injected failure exit1, and the exact candidate Unicode-return expression in Qt JS. `test-position-wrap.py` verifies horizontal/vertical/parent-move geometry with the exact baseline popup functions and candidate x/y bindings, plus actual patched/old shared tooltip long-word rendering and unchanged short-tooltip geometry. All passed without a visible UI or changing installed files.

This is not a live full DockWindow integration test. Real hover-delay timing, press/menu/drag/autohide interaction, all four edges and layer-surface clipping, and removing a hovered delegate remain runtime checks. Supplied hashed context includes contentShown/menuOpen, popupRoom, Slot fields, style scaling and popup functions so no-tools reviewers need not assume those APIs are missing. Rebase and run Omarchy's required upstream suite before proposing merge.

Claude Code, Grok Build and Google Gemini reviewed earlier frozen bytes. Their raw responses are private audit artifacts; exact request/response hashes appear in review-triage.json. Codex validated findings, implemented v3 and ran fixtures. No provider has reviewed these v3 bytes and no release approval is claimed.
