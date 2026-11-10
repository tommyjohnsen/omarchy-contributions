# Contribution notes

Pablo Merino and the upstream contributors created AltSwitch. Their MIT license and manifest authorship are preserved unchanged. Tommy Johnsen owns this proposed contribution; Codex assisted with implementation, source verification and tests. Claude Code, Grok Build and Google Gemini supplied independent static reviews. Exact production-file digests, actual reported model labels, selected Gemini CLI label and request/response digests are recorded in REVIEW-PROVENANCE.json. Private prompts, credentials and raw review logs are excluded.

The production change resolves the selected mapped window at activation time, focuses it and explicitly raises that same target in one deferred Hyprland evaluation. It also renders application-provided labels as plain text. Baseline ALT release, keyboard-focus and cancel behavior are preserved. It does not ship the separate personal Command-binding extensions.

Run `tests/run.sh` from any directory. It creates an isolated temporary candidate layout, runs behavioral checks and verifies hostile label serialization/plain-text sinks. Actual prior nested Hyprland 0.57.1 tests validated focus and visible stacking, including a closed-target race. Physical ALT/AltGr, Hyprland 0.56 runtime, and broader grouped/fullscreen/multi-monitor combinations remain unverified. These are evidence limits, not claims of failures.

The three reviews reported no blocking findings on the exact production hashes. That is static review assistance, not model approval or release approval. The added provenance documents, test wrapper and tests are supplemental release material; production hashes are unchanged. No push, commit or publication is authorized by this document.
