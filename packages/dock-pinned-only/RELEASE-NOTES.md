# Pinned-only dock option

Opt-in `pinnedOnly` filters running applications while preserving normalized pins and pending pin order. The default behavior stays unchanged. The exact patch and baseline context were reviewed by Claude Code, Grok Build and Google Gemini; their no-blocking-findings verdicts are static assessments.

Codex implemented and tested the change against the actual dock items binding (eight cases, nine assertions). A supplemental offscreen check also passed six dependency-tracking cases with the actual patched binding (eight Qt change signals), using stubbed source objects. Full live dock interaction, settings/translations, all dock orientations, and rebase against the intended upstream branch remain integration checks. Confirm how users restore unpinned minimized applications before selecting this behavior. Coordinate existing upstream dock work rather than opening a duplicate contribution.

Original upstream authors retain credit. Actual provider identities and source/request/response hashes are recorded in `REVIEW-PROVENANCE.json`. Codex consolidated these records. No provider edited this release note or granted human release approval. Nothing has been pushed or published.
