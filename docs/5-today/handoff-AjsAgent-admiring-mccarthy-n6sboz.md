# Handoff: AjsAgent/admiring-mccarthy-n6sboz

## What the work is for
Split the `art-pipeline` skill into separate skills that each work alone, and make every review a fresh-context reviewer agent's verdict. The direction is in `docs/NEXT-SESSION.md`. aj approved the plan with: A keep `art-pipeline` as a front door, B a `--reviewer` flag, C `engine-import` as a generalised pattern.

## Where it stands
- The default branch is `AjsAgent/standalone`. It already has `frame-sheet-compare` as its own skill (PR #7).
- This branch adds the merged `angle-review-sheets` skill and the proposal page `docs/plans/split-art-pipeline-proposal.html`.
- Done: `art-brief-spec` (#9, commit `1822c6a`), `model-build` (#10) and `engine-import` (#12) (both inside autosave commits, so no separate commit), `rig-and-clips` (#11, commit `1d71ec5`). Six broken links were fixed in `7714249`.
- Done for #13: `agents/art-reviewer.md`, a copy of the house-rules `reviewer` tuned for art, and the `reviewer-agent` skill text that spawns it. It has not been spawned yet, because plugin agents load at session start.
- Was blocked, now done: the `--reviewer` flag on `review.py record`, `clip` and `frames`, its gate rule in `artlib.py` and its `verify.py` checks. The design-loop hook closes code edits until aj types `Build plan approved: reviewer-agent` from inside this repo.
- Done for #14 (docs part): `art-pipeline` is a ~60-line front door; `stages.md` and `tooling-and-traps.md` are deleted. `verify.py` 109 of 109 after it. 
- #13 code is built: `--reviewer` on `record`, `clip`, `frames`, the gate rule (`opened_problem` in `artlib.py`) and checks 110 to 113. `verify.py`: all 113 checks passed. Plugin version 0.11.0. Decision in `docs/6-decisions/Decisions.md`.
- Agent trial done (new session): `art-pipeline:art-reviewer` in sheet mode on `skills/model-build/examples/wizard-review.png`, given no objectives. It marked `O1: NOT SEEN`, listed 8 mismatches in the `<path>: <problem>. <fix>.` shape, gave a `seen:` paragraph and ended `VERDICT: fail`. It put the hat taste question as lettered options with a suggestion. It broke "output, nothing more" by adding an opening paragraph and `Commands run`, `Files written` and `Could not do` blocks. The mismatches were not checked by me against the image.

## The next step
When #13 lands, do #14, then run `verify.py`, quote the result and push. aj has also been asked whether to move the scratch clone `/home/user/plunderspell` to `/home/user/_to_delete/`, because the Stop gate flags an approval file that clone's checkout wrote.

## What is unverified
- `verify.py` passes 113 of 113 on the finished split. The `[reviewed by NAME]` status line and the `clip` `--reviewer` path were never run; `art-pipeline:art-reviewer` has never been spawned (new session needed).
- The `engine-import` C# template was never compiled: no Unity, `dotnet`, `mcs` or `csc` is on this machine, and a compile against hand-written stubs would prove nothing.
- `--reviewer` is an honesty claim the gate cannot prove; the recorded sheet hash ties the verdict to one image.
- No Blender-to-Unity import code is on this repo's branches. A code search of `Ajw2003/PlunderSpell` (attached read-only) found `ArtBibleModelImporter.cs`, `GroundsImportSettings.cs` and `CastleMeshImportSettings.cs` under `Assets/_Project/Scripts/Editor/`. All three files were fetched in full through the GitHub contents API (483, 85 and 32 lines) and skimmed for structure; they have not been studied line by line. All three are Unity `AssetPostprocessor` classes tied to PlunderSpell's own folders and namespace (`Assets/Models/ArtBible/`, `Plunderspell.EditorTools`): rig type per model, URP materials from baked maps, read/write meshes, axis conversion. An engine-import skill would need these generalised, because the `art-pipeline` skill says to stay project-agnostic and never attach another repository for examples. The local clone of that repo was still downloading (2.9 GB so far) and is not needed for the plan.
- The older `verify.py` failures on aj's Windows machine (16 checks) are unconfirmed on this machine.

## The issue numbers
Parent #8. Children: #9 art-brief-spec, #10 model-build, #11 rig-and-clips, #12 engine-import, #13 reviewer-agent and flag, #14 front door, version and changelog.
