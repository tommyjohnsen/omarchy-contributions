# Dock revision/context package v2

Separate candidate revisions only; provider-frozen original inputs and live files are unchanged.

Claude Code (`claude-opus-5-5`) returned static `insufficient_evidence` reviews for the tooltip and pinned-only patches. The new `baseline-context.json` supplies small hashed unchanged source excerpts showing the config fallback, pins array scope/normalization, tooltip imports and Slot properties, popup placement functions and PlainText tooltip dependency. These address missing context, not new claimed bug fixes.

## Confirmed tooltip fixes

- A QML assertion thrown from a signal callback logs but leaves the process alive. The fixture now exits 1 on failure and 0 on success; both paths passed an offscreen bounded process check.
- UTF-16 slicing can leave a high surrogate at the truncation boundary. Claude suggested `Array.from`, but running that exact proposed expression in the installed Qt JS engine still produced a lone high surrogate. The candidate `tooltip.patch` instead preserves the bounded 120-code-unit limit and strips a trailing high surrogate. The exact patched return expression passed a Qt JS boundary fixture.

`test-offscreen.py` runs the real shared PanelToolTip with no visible window and no live session connection, then extracts and tests the actual candidate return expression. This is not a full patched DockWindow integration test. `test-items.py` applies the original pinned-only patch to the actual installed Dock.qml and executes its real items binding with the actual DockModel.js under controlled desktop-entry/toplevel fixtures. Eight cases (nine assertions) pass: defaults, resolved differing appId, opt-in filtering, absent config fallback, strict boolean opt-in, config changes and pending pin precedence. This does not prove QML reactive updates or real docking on every orientation.

Pinned-only intentionally hides unpinned running/minimized items when explicitly enabled. Upstream should confirm that product behavior and document how users restore unpinned apps. Existing defaults remain unchanged.

## Still gated

Rebase against upstream HEAD and run its repository tests; agree on settings/translations; coordinate PR #16219; verify live name resolution, all dock edges and bounds, press/menu visibility, removal of a hovered delegate and live config reactivity. Claude's static reviews do not approve this revision or release. Preserve Omarchy MIT authorship/notices and record reviewer contributions separately. No code was installed or published.

Google Gemini via Antigravity selected CLI model `gemini-3.8-flash-high` also reviewed the original pinned-only patch. Its two alleged high blockers are contradicted by unchanged baseline context and fixtures; its raw-config-pin fallback proposal was not adopted because it skips ID normalization and pending pin precedence. See `gemini-review-triage.json`. This does not turn its review into approval.

Google Gemini's original-tooltip review alleges empty fallback names and blank containers. Unchanged AppLibrary → AppSearch context shows a nonempty resolved entry ID fallback; DockModel slots require truthy keys. Those are therefore missing-context concerns, not demonstrated current-baseline bugs. Actual hover-delay behavior and complete DockWindow interaction remain untested; the offscreen test only checks the delay property. See `gemini-tooltip-review-triage.json`.
