# Local technical evidence: native minimize notification patch

The unchanged core patch and corrected exact harness are under candidate/. Strict render-only Wayland passed; historical X11 evidence has the weaker scope explicitly recorded by the reviewed audit limits. The newer strict X11 attempt is incomplete and does not count as a pass.

UPSTREAM-COMPATIBILITY.json records a read-only current-HEAD comparison. Current HEAD differs from the tested revision; the affected function is identical and the patch applies in an isolated check. No port, build or runtime test against that HEAD was performed.

Hyprland upstream communications remain human-only. This folder contains a local patch and technical evidence, with no PR body or publishing action. Independent static reviews are advisory and do not authorize a release.

Upstream BSD3 notices and the full new-harness MIT body are included separately. This packaging does not relicense upstream code or change reviewed source bytes.
