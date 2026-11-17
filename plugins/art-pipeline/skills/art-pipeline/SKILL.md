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

## The stages

Each stage ends at a gate: **open the image with the Read tool, compare, write what you saw.** A
fix is always followed by another look, never by the next stage.

```
0 protect → 1 brief + style bible → 2 reference + concept + spec → HUMAN APPROVES
          → 4 model → LOOK → 5 rig + pose test → LOOK → 6 clips → LOOK
          → 7 engine import → LOOK in engine → 8 commit
```

Stage 3 (the spec) is now part of stage 2: reference, concept and spec go to the human together.

| Stage | Produces | Gate (what to look for) |
|---|---|---|
| 0. Protect | an autosave or frequent commits on your own branch | — |
| 1. Brief + style bible | `docs/art/BRIEF.md` from `references/style-bible-template.md`: register, palette, scale, budgets, sheet conventions | the user approves it; nothing is drawn before |
| 2. Reference + concept + spec | real-world reference saved under `docs/art/reference/<id>/`; a concept sheet drawn by code where it helps; `docs/art/specs/<id>.json` from `references/spec-template.md` | `approve.py check <id>` passes, then **the human approves** through AskUserQuestion; nothing is built before |
| 3. Asset data | the project's own data entry per asset: dimensions, materials with hex, build bullets with real sizes, budget, rig and clip list | numbers on the sheet equal the numbers in the data and the approved spec |
| 4. Model | mesh, baked textures, FBX/glTF/.blend, built by a blueprint script; a validator | review sheet: concept left, renders right (¾, front, side, wireframe); silhouette, proportion, colour, budget on the caption |
| 5. Rig | armature with engine-standard bone names, skin weights, a test pose | posed views bend without tearing; props follow the hands; nothing below the floor |
| 6. Clips | motion from reference: a mocap take retargeted, or key poses taken from reference frames; in-place clips exported per family; metrics (foot slide, lowest point, events) | 8 stills per clip on the actual model beside the reference frames, plus an MP4; feet do not slide; each key pose matches its reference |
| 7. Engine | importer rules in code (rig type, loop flags, materials), a generated animator, a driver script | a screenshot or capture in the engine; the user checks what this machine cannot run |
| 8. Commit | everything above, including every sheet and render | `git status` clean; docs tier updated |

Full detail per stage, with commands: `references/stages.md`.

## How to work through it

1. **Read the project first.** Find its art docs, scale doc and any existing forge before writing
   one. Extend what is there; when nothing is, `references/stages.md` gives the shape.
2. **Find reference and get the spec approved before making anything.** Save real-world reference
   (photographs, period plates, video frames, mocap, recordings) under `docs/art/reference/<id>/`,
   write `docs/art/specs/<id>.json` from `references/spec-template.md`, then:

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/approve.py" check <id>
   ```

   One spec may hold several items (four enemies of one Age, say), each with its own reference
   for every part it makes: model, animation, texture, sound. The check names each missing piece
   by item and part. When it passes it writes the review sheet `docs/art/specs/<id>.sheet.html`,
   which shows every reference large in the same layout every time. Send the human that sheet
   (as a file or a published page) and commit it; never summarise it in its place. Then send the
   AskUserQuestion it prints, as printed and without `answers`: only the human's own "Approve"
   click writes the approval
   (`docs/art/approvals/<id>.json`, which you commit). A human at a terminal can instead run
   `approve.py grant <id>`. Approval files and `.art-pipeline.json` cannot be written by your tools.
   If the reference cannot be fetched (a blocked host), stop and ask the human for it; never
   substitute your own drawing or reasoning.
3. **Respect the build budget.** Each approved item allows `iterations` build or render runs
   (default 5), counted whatever tool makes its output files. Editing the code or data an asset is
   made from (`source_paths`) is not a build, and neither is a check; the hook says what each build
   was charged for. When they are spent the hook refuses more,
   and art any command makes outside an approval is put back straight away (a copy is kept in
   `.git/art-pipeline/quarantine/`). Do not look for another route: show the human
   the last render beside its reference and ask whether to accept it, add reference, or re-approve.
   A fix that needs more than the budget is a sign that the reference or the spec is wrong.
   **Run the project's check before every render you judge and before any movie or export.** Where
   the project lists `checks`, movies and exports (`gated_commands`) are refused until the item has
   a passing check newer than its last edit, and the stop is blocked while a changed item has none.
   A render from the side cannot show a prop inside the body; the check can. When you report to the
   human, quote the check's verdict, and never describe a render you have not checked as matching.
   Where the project sets `clip_review_views`, a movie or export also needs a clip review: render
   stills of every key pose from those views (always including top), put them beside the
   reference, open the sheet with Read, and record what you saw with `review.py clip`.
4. **Decisions that are the user's go to the user**, with a proposal page or a question: the look,
   anything that contradicts an approved plan (for example a death animation when the plan says the
   body vanishes). Defaults that are just craft, you choose and say so.
5. **Set up Blender as a Python module**: `sh scripts/setup_bpy.sh` (from this skill's folder).
   It finds a Python that matches a `bpy` wheel and installs it with Pillow. Cycles on CPU only:
   EEVEE and Workbench abort without a GPU. `references/tooling-and-traps.md` has the rest.
6. **Build by blueprint, never by hand-edit.** Fix the generator, not its output, so a rebuild
   keeps the fix. Every output is regenerable from a committed script and spec.
7. **Render and compose the review sheet** for every model you touch:

   ```bash
   python3.11 scripts/render_views.py <model.fbx|.glb|.blend> --out <dir>
   python3 scripts/review_sheet.py --concept <concept.png> --views <dir> --title "<Name>" --out <sheet.png>
   ```

   Projects with their own renderer use it instead; the gate only
   cares that a fresh sheet exists and was opened.
8. **Look.** Open the sheet with Read. Compare it with the concept, and write down what you saw:
   what matches, what does not, what you will change. Change, rebuild, re-render, look again. At
   least one improvement pass per asset; "it passed" is not a look.
9. **Record the look** so the gate can see it:

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/review.py" record --model <model path> --sheet <sheet.png> \
       --verdict pass --seen "<what you saw, at least 40 characters>"
   ```

   `--verdict waived` (with the reason in `--seen`) is for a model that genuinely cannot be
   rendered here; it is reported, never silent. `python "${CLAUDE_PLUGIN_ROOT}/scripts/review.py"
   status` lists what the gate will say before you stop.
10. **Keep the docs in step with the art.** Docs that describe art (a scale doc's roster, a brief's
   budgets, a tool's status line) drift the moment a roster changes. Give the project a drift check
   (a script comparing docs with the data and code, see `references/stages.md`, stage 8) and name it
   in `.art-pipeline.json` at the repo root, so the gate runs it before every stop that changed a
   model or a doc:

   ```json
   {"doc_check": "python3 tools/check_art_docs.py", "doc_check_paths": ["docs/**", "**/*.json"]}
   ```

   The same file can set `model_globs`, `exclude` and `review_dir` (default `docs/art/reviews`).
11. **Engine work you cannot run here is UNTESTED**, said plainly, with the exact menu item or
   command the user runs and what they should see.

## Delegating

Concept and model work splits cleanly per asset: one worker per asset family, each with a saved
brief in the repo (so a worker cut off by a usage limit can be resumed) and its own paths. Workers
look at their own sheets; the coordinator looks again before committing. Build and review two
reference assets (say a humanoid and a quadruped) to a high bar before fanning out, so later
workers copy a bar instead of guessing. Never more than two
workers at once on one checkout, and each stages only its own paths.

## References

- `references/stages.md`: each stage in full, inputs, outputs, commands, gates.
- `references/style-bible-template.md`: the brief a project fills in before anything is drawn.
- `references/spec-template.md`: the per-asset spec a human approves, and what counts as reference.
- `references/tooling-and-traps.md`: Blender as a module, the blueprint pattern, rigging,
  AnimForge-style clips, engine import, and the traps that already cost a day.
