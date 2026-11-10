# Omarchy contributions

Reviewed source, opt-in configuration examples, patches and technical evidence published by [Tommy Johnsen](https://github.com/tommyjohnsen).

This is an experimental source collection, not an official Omarchy distribution or an automatic installer. Packages target the upstream revisions documented in their own files. Read each package's prerequisites and evidence limits before use. This initial release preserves the reviewed snapshots; it does not promise that they match the latest personal configuration on the author's laptop.

## Packages

| Package | Purpose |
| --- | --- |
| [window-switcher](packages/window-switcher/CONTRIBUTING-NOTES.md) | Focus and raise the selected window; plain-text application labels. |
| [general-titlebar-policy](packages/general-titlebar-policy/README.md) | Conservative opt-in registry: retain desktop controls unless usable native controls have been verified. No automatic control detection. |
| [dock-pinned-only](packages/dock-pinned-only/README.md) | Optional dock filtering while preserving pin order. |
| [macos-screenshots](packages/macos-screenshots/RELEASE-NOTES.md) | Optional Command+Shift+3/4 screenshot bindings. |
| [dock-tooltips](packages/dock-tooltips/README.md) | Plain-text, bounded, wrapping tooltips and geometry updates. |
| [omarchy-native-integration](packages/omarchy-native-integration/README.md) | Bounded native-minimize integration using Omarchy's stock helper. |
| [show-desktop](packages/show-desktop/RELEASE-NOTES.md) | Show-desktop controller and bar widget with reviewed evidence. |
| [native-minimize](packages/native-minimize/RELEASE-NOTES.md) | Hyprland minimize-notification patch and isolated protocol evidence. |
| [comfyui-vulkan](packages/comfyui-vulkan/RELEASE-NOTES.md) | Experimental ComfyUI Vulkan backend integration patch and evidence. |
| [torchvulkan-memory](packages/torchvulkan-memory/README.md) | Allocator-owned reserved and reusable-bin counters. |
| [immich-files](packages/immich-files/RELEASE-NOTES.md) | Experimental read-only Immich file integration reference. |

Each package includes REVIEW-PROVENANCE.json, license notices, and scope-specific notes. Some contain a candidate/ subdirectory holding the reviewed sources. Patches require their documented upstream bases and dependencies. There is intentionally no run-everything installation command.

## Authorship and independent review

Original upstream authors retain their copyright and credit. Tommy Johnsen is the human project owner. Codex assisted with implementation, verification, corrections, annotations and packaging. Claude Code, Grok Build and Google Gemini provided independent static review assistance on the exact snapshots or explicitly composed baseline/delta scopes recorded in each package.

Captured metadata reports Claude's model as claude-opus-5-5 and Grok's as grok-4.7-build. The Google CLI selected gemini-3.8-flash-high; its responses did not independently attest the underlying model identity. These labels reproduce captured metadata, not a new verification of provider model names.

Codex consolidated the annotations and review records. These are actual recorded contributions, not signatures or endorsements by the providers. Reviewers did not run the tests. Tests and runtime observations are credited to their recorded executors; static review does not replace broader integration testing. Raw private CLI logs and prompts are not distributed here.

## Licenses

The root README, release notes, publication manifest and VERIFY.py are covered by LICENSE-PACKAGING.MIT. This repository has multiple licenses. Do not apply one blanket license to all packages. New standalone code uses MIT where stated. Upstream-derived code retains its existing MIT, BSD-3-Clause, GPL-3.0 or AGPLv3 notices as documented within its package. The ComfyUI patch retains GPL-3.0; Immich schema excerpts retain their included AGPLv3 notices. Follow the local license files and per-file notices when redistributing or extracting code.

## Release provenance

Version v0.1.0 is an experimental source-and-patch prerelease. The human owner authorized publication on November 10, 2026. Historical staging notes and review records intentionally remain unchanged, including their earlier unpublished/approval-false fields. PUBLICATION.json records this later publication authorization separately; it does not retroactively alter review evidence.

Before packaging, 391 staged-file digest checks and 42 captured review-response identity checks passed. No new full runtime suite was run solely for packaging. SHA256SUMS lists the distributed package files. VERIFY.py checks those checksums without installing or executing any package. Packaging documentation is supplemental and is not claimed to have received the earlier three-provider code reviews.

Nextcloud and the historical floating-window workaround are excluded. Later lock/fullscreen work and Meetmate are outside this reviewed batch. Upstream PRs and maintainer acceptance are separate from publication of this collection.
