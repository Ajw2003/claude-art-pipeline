# The stages, in full

Paths below are the defaults; a project that already has its own layout keeps it and says so in
its brief. Every stage's outputs are committed, sheets and renders included: they are the record of
what was looked at.

## 0. Protect the work

Long Blender runs and multi-worker batches get cut off (usage limits, a reclaimed container).
Commit on your own branch after every asset, or run an autosave that commits and pushes only the
paths this run writes, every few minutes. Never a broad `git add -A`: another worker may be writing
elsewhere in the same checkout.

## 1. Brief and style bible

Before anything is drawn. Copy `../../art-brief-spec/references/style-bible-template.md` to `docs/art/BRIEF.md` and fill it in
from the project's pitch, mood board and scale doc. If the project has no scale doc, write one
first: one standard figure (a 1.80 m human is a good default) that every room, door, prop and
creature is measured against.

**Gate:** the user approves the brief. Register, palette and scale are theirs.

## 2. Reference, concept and spec, then the human approves

**Reference first.** Before drawing or building anything, find real-world reference for the asset
and save it under `docs/art/reference/<id>/`: photographs or museum pieces for a prop, period
plates or photographs for a costume, a motion-capture take or video frames for an animation, a
field recording for a sound. Write where each came from and what to take from it in the spec. The
pipeline's own concept sheets and renders are never reference. If the reference cannot be fetched
from this machine, ask the human for it or for the host to be allowed; do not reason out what it
would show.

**The spec** (`docs/art/specs/<id>.json`, from `../../art-brief-spec/references/spec-template.md`) covers one item or a batch of
items, and for each part of each item names the reference, the key poses taken from it, what the
human will check, every path the work writes, and the build budget. `approve.py check <id>`
validates it, writes the review sheet the human reviews (the same layout every time), and prints
the AskUserQuestion to send. The human's "Approve" is the only thing that writes
`docs/art/approvals/<id>.json`; the hooks refuse every write to an art path and every build command
until that record covers the item, one of the item's reference images has been opened in the
session, and its budget is not spent. Editing the spec or a reference after
approval voids it.

**Concept sheets**, where they help the human decide, go with the spec. One sheet per asset, drawn
by code so it can be regenerated:

- SVG from a shared sheet template (frame, grid, ground line, title block, palette strip), rendered
  to PNG with headless Chromium (Playwright `page.screenshot` of the SVG at 2×); or Pillow plates.
- Characters: front and side orthographic views at one scale, the reference human beside them, a
  metre ladder, callouts naming parts and materials. Props: a hero ¾ view, front and side, a scale
  bar, grab points. Set pieces: elevation or section plus a plan on the grid cell.
- A palette strip of the asset's own materials, hex labelled.

When the design is the user's to choose (a player character, a new faction), draw the options as
plates and set them side by side on a proposal page (an HTML artifact). Record the choice in a plan
and a dated decision entry, with the rejected options, so nobody proposes them again.

**Gate:** the human approves the spec (and its reference and concept) through the approval
question. Before asking, open every PNG: on scale against the ladder and the human; no label overlapping a drawing
or another label; colours only from the entry's materials; every number on the sheet equals the
spec. Fix the generator, never the SVG by hand; re-render; look again.

## 3. Asset data

One structured entry per asset in the project's own data (separate from the approval spec, which
says what to make and from what; this says how the project builds it) (JSON is simplest), the single source the model, the engine and the
docs are generated from: slug, name, height or W×D×H, triangle and texture budget, materials
(name, hex, roughness and wear notes), build bullets with real sizes ("Hat: cone 0.55 m tall,
brim 0.40 m dia, tip bends back 30°"), and for characters the rig, the clip list and anything
detachable. A validator script checks counts, required fields and scale rules, and refuses to write
anything until the whole set passes.

**Gate:** the sheet and the JSON agree. A worker who writes the spec after drawing can contradict
the drawing.

## 4. Model

A blueprint per asset, in code: a list of parts (lathe, loft, sweep, tube, prism, box…) each with
a material family and, for rigged assets, a bone. The forge builds the mesh, bevels, unwraps, bakes
one texture set, and exports FBX (engine axes), glTF and `.blend`. A validator checks: closed and
manifold, consistent winding, UVs in 0–1, one material slot, identity transforms, grounded, under
the triangle budget, the height or bbox within tolerance of the spec, and (rigged) every vertex
weighted, at most 4 influences, weights summing to 1.

Then the review sheet: the concept on the left; three-quarter, front (beside the reference human),
side and wireframe renders on the right; a caption with triangles against budget, size against
spec, bones. `scripts/render_views.py` and `scripts/review_sheet.py` make one for any model when
the project has no renderer of its own.

**Gate:** open the sheet. Silhouette and proportion against the concept; colours; key details
present; the caption's numbers. At least one improvement pass. A real conflict between the spec's
size line and its build notes is recorded as an override with the reason; the model is never
shrunk to pass.

## 5. Rig and pose

A figure library gives bones the engine's standard rig expects (Unity Humanoid names with `.L`/`.R`
suffixes), heat weighting with per-part rules (rigid props, a skirt that hands weight to the thighs,
parts limited to named bones), and extra bones for anything that must come off or swing (a hat, a
lantern ring). The review sheet adds a posed three-quarter and front view: an arm raised, the head
turned, a knee lifted.

**Gate:** the posed views bend without tearing, nothing passes through the body, props follow the
hands.

## 6. Clips

Motion comes from reference, never from reasoning about what a body would do:

- **Best: a motion-capture take**, retargeted. The CMU Graphics Lab Motion Capture Database is free
  to use; Blender imports BVH (`bpy.ops.import_anim.bvh`). Retarget each bone's turn from its own
  rest, so models of other proportions keep their own posture.
- **Otherwise: key poses taken from reference frames** (video or period plates), one key per frame
  the spec's `key_poses` names, compared side by side with that frame. The timing comes from the
  video, not from a guess.
- If a pose will not come right within the build budget, stop and ask: the usual cause is missing
  or wrong reference, or a model whose props cannot do the action. Tuning a solver by argument is
  how one session spent its whole budget on a single musket aim.

Clips are built by code on one shared reference skeleton, so one clip retargets to every humanoid:

- named poses (bone rotations), clips as timed pose keys with easing, anticipation and overshoot,
  each pose taken from a reference frame;
- locomotion from a parametric gait (stride, cadence, bob) matched to the in-game speed, so feet do
  not slide; in place, no root motion, when the engine moves the body;
- foot IK to the floor while grounded; events (footstep, hit, release) at normalized times;
- export per family (base, weapon, signature) as animation-only FBX; re-import to verify every take
  and frame count; write a manifest with loop flags, events and metrics.

Review per clip: frame sheets of every clip in Unity and in Blender with the rest-pose comparison
(SKILL.md, "Frame sheets"; the Stop gate requires them), 8 stills on the actual target model with
the matching reference frames beside them, a foot-contact trace for locomotion, an MP4.

**Gate:** both frame sheets opened and recorded with `review.py frames`, no rest-pose mismatch,
props held as designed in every clip (a weapon on a hand bone follows an empty-handed swing),
each key pose matches its reference frame side by side, feet do not slide (metric under
1 cm), nothing below the floor, the pose reads as the action at a glance, and a one-shot ends where the next state expects it (a death ends lying still).

## 7. Engine

Everything set in code, nothing in the Inspector:

- an import postprocessor: rig type and bone map by path, loop flags per clip, materials built from
  the baked maps, data textures imported linear;
- an editor menu that generates the animator (blend trees by speed, layers with masks) and installs
  the model on the prefab;
- a runtime driver that only sets animator parameters, reading what the body is doing; on a
  networked game, anything the movement does not show (crouch, cast) is synced by the owner;
- tests: classification, loop flags against the manifest, driver parameters from inputs.

**Gate:** frame sheets of the prefab with the controller the game uses, rendered again after any
import or controller change, and a capture in the engine. If this machine cannot run the engine, the work is labelled
UNTESTED and the user gets the exact menu item and what they should see.

## 8. Docs agree, then commit

Update the project's docs in the tier that changed (state, today, the system doc for the asset
family, the scale doc's roster). Then run the project's doc-drift check: a small script that
compares the docs with the data and code (every asset in the spec appears in the roster doc at the
same size; every roster entry still exists; every path a doc names exists) and fails on any
difference. If the project has none, write one; wire it into CI. Docs that describe art drift the
moment a roster changes.

Rebuild the batch twice (the second run meets the state the first left), commit every output,
push.
