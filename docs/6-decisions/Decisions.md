# Decisions

## 2026-11-24: reviewer verdicts need no Read, but still need an unchanged sheet

- **Decision:** `review.py record`, `clip` and `frames` get an optional `--reviewer NAME`. A record that carries a reviewer name does not need the sheet to have been opened (Read) in the current session. Every other gate check stays: pass verdict, record newer than the change, sheet exists, and the sheet's current sha256 equals the one recorded.
- **Why:** aj approved choice B on the proposal page `docs/plans/split-art-pipeline-proposal.html`, so a fresh-context reviewer agent's verdict can stand in for the maker's own look.
- **Limit:** the flag is an honesty claim the gate cannot prove. The recorded hash only ties the verdict to one image.
- **Approved:** `Build plan approved: reviewer-agent`, typed by aj on 2026-11-24.
