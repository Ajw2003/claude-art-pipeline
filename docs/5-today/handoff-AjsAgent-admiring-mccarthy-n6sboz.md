# Handoff: AjsAgent/admiring-mccarthy-n6sboz

## What the work is for
Split the `art-pipeline` skill into separate skills that each work alone, and make every review a fresh-context reviewer agent's verdict. The direction is in `docs/NEXT-SESSION.md`.

## Where it stands
- The default branch is `AjsAgent/standalone`. It already has `frame-sheet-compare` as its own skill (PR #7).
- This branch adds the merged `angle-review-sheets` skill and the proposal page `docs/plans/split-art-pipeline-proposal.html`.
- Nothing has been moved out of `skills/art-pipeline/` yet. Only two files point at skill folders (`scripts/artlib.py` and `scripts/verify.py`), and both already point at `frame-sheet-compare`.

## The next step
Wait for aj's approval and three answers on the proposal page: A (keep `art-pipeline` as a front door), B (how the Stop gate counts a reviewer agent's look), C (where the Blender-to-Unity import work lives). Then move files one skill per commit, running `verify.py` after each.

## What is unverified
- `verify.py` has not been run on this branch.
- No Blender-to-Unity import code is on this repo's branches. A code search of `Ajw2003/PlunderSpell` (attached read-only) found `ArtBibleModelImporter.cs`, `GroundsImportSettings.cs` and `CastleMeshImportSettings.cs` under `Assets/_Project/Scripts/Editor/`. Their contents have not been read, and the local clone of that repo had not finished.
- The older `verify.py` failures on aj's Windows machine (16 checks) are unconfirmed on this machine.

## The issue numbers
None created yet. The plan is over three steps, so parent and child issues are needed before source files are edited.
