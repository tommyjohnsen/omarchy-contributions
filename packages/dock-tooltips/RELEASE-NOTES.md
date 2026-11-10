# Dock tooltip fixes

The patch renders bounded app labels as plain text, retains valid UTF-16 at truncation, wraps long words and updates popup positions when dock geometry changes. Claude Code, Grok Build and Google Gemini independently reported no blocking findings on the exact reviewed patch. Codex implemented, tested and consolidated the corrections; original Omarchy authors retain credit.

Actual Qt fixtures cover the shared tooltip, positive/negative test exits, long-word layout, truncation and geometry changes. Full patched DockWindow interaction, all layer-shell edges, press/menu/drag behavior, live delegate removal and upstream integration remain checks before merge. Reviewers suggested additional hardening; these suggestions are not treated as confirmed blockers. Coordinate existing upstream dock work.

Production source bytes match REVIEW-PROVENANCE.json. These notes are supplemental packaging. Static reviews are not human release approval. Nothing has been pushed or published.
