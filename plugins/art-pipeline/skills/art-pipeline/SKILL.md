---
name: art-pipeline
description: Make game art by code - models, animation, VFX, SFX, music, textures, sprites and UI art - from a one-line prompt to the engine - brief and style bible, real-world reference and a spec a human approves before anything is made, concept sheets, Blender-as-a-Python-module models, review sheets, rig and keyframed clips, engine import - with a visual check after every stage that a Stop-hook gate enforces. Use when asked to design, model, rig, animate or import a character, creature, prop or set piece, when adding art to a project that has none, or when a model "passes validation" and nobody has looked at it yet. Not for hand-editing an existing asset in a DCC app, or for UI art.
---

# Art pipeline: prompt to engine, and look at it every time

Project-agnostic: work only in the project that is open. Never fetch, clone or attach another
repository for examples; everything this pipeline needs is in this skill's `references/` and
`scripts/`.

**Rule one: reference and a human-approved spec come first.** No art asset of any kind (model,
animation, VFX, SFX, music, texture, sprite, UI art) is made or changed until a human has approved
a spec that names real-world reference for it. What looks human, or right, is found in reference,
never reasoned out: a session once spent its whole budget tuning one musket aim by argument, and
the drill manual that shows the pose was never opened. The plugin's PreToolUse hook enforces this:
writes to art paths and runs of build commands are refused until an approval covers them, one of
its reference images has been opened this session, and its build budget is not spent.

**Rule two: look at it.** Nothing made by code is done until someone has opened a picture of it
beside its reference and concept and written down what they saw. A validator that passes says the numbers are legal
(closed mesh, under budget, right height). It cannot say the hat looks like a hat. The
`art-pipeline` plugin's Stop hook enforces this: a session cannot end while a model it changed has
no review sheet newer than the model, opened in this session, with a written verdict.

This page is the front door. Each stage has its own skill that works alone (map below); this page
holds the two rules every stage obeys. Unattended runs (no human to approve) are in `art-brief-spec`.

## The stage map

```
0 protect → 1 brief + style bible → 2 reference + concept + spec → HUMAN APPROVES
          → 4 model → LOOK → 5 rig + pose test → LOOK → 6 clips → FRAME SHEETS (Unity + Blender) → LOOK
          → 7 engine import → FRAME SHEETS again → LOOK in engine → 8 commit
```

Stage 3 (asset data) is part of stage 2: reference, concept and spec go to the human together.

| Stages | Skill | Use it for |
|---|---|---|
| 0 to 3, 8 | `../art-brief-spec/SKILL.md` | protect the work, brief, reference, spec and approval, build budget, docs agree, commit; unattended runs |
| 4 | `../model-build/SKILL.md` | Blender as a Python module, blueprints, the review sheet, the look |
| 5, 6 | `../rig-and-clips/SKILL.md` | rig, pose test, clips from reference, the mandatory frame sheets |
| 7 | `../engine-import/SKILL.md` | the Unity importer pattern, generated animator, the check in the engine |

Helpers any stage calls:

| Skill | Use it for |
|---|---|
| `../frame-sheet-compare/SKILL.md` | the same clip rendered in Unity and Blender under one camera, then compared |
| `../angle-review-sheets/SKILL.md` | review sheets from fixed angles |
| `../reviewer-agent/SKILL.md` | a fresh-context `art-reviewer` agent judges a sheet and its verdict is recorded |

## Where to start

1. Read the project's own art docs, scale doc and any existing forge, then extend them.
2. No approved spec for the asset yet: `art-brief-spec`.
3. Spec approved, nothing built: `model-build`, then `rig-and-clips`, then `engine-import`.
4. Something made and not yet looked at: open the sheet, or hand it to `reviewer-agent`.
5. Engine work you cannot run here is UNTESTED, said plainly, with the exact menu item or command
   the user runs and what they should see.

Per-project settings (`model_globs`, `anim_globs`, `exclude`, `review_dir`, `doc_check`) live in
`.art-pipeline.json` at the repo root.

## Delegating

Concept and model work splits cleanly per asset: one worker per asset family, each with a saved
brief in the repo (so a worker cut off by a usage limit can be resumed) and its own paths. Workers
look at their own sheets; the coordinator looks again before committing. Build and review two
reference assets (say a humanoid and a quadruped) to a high bar before fanning out, so later
workers copy a bar instead of guessing. Never more than two
workers at once on one checkout, and each stages only its own paths.

