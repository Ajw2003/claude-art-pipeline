---
name: rig-and-clips
description: Rig a finished model with an engine-standard skeleton and skin weights, test it in a pose, then make animation clips from real motion reference (a retargeted mocap take or key poses taken from reference frames), export them, and check every clip on frame sheets. Use when asked to rig, skin, pose or animate a character or creature, when a clip, controller or clip import setting changed, or when an animation looks wrong in the game but passed its checks.
---

# Rig and clips

Needs a reviewed model (the model-build skill) and an approved spec whose animation part names
real reference (the art-brief-spec skill). Motion comes from reference, never from reasoning about
what a body would do.

## Stage 5: rig and pose

A figure library gives bones the engine's standard rig expects (Unity Humanoid names with `.L`/`.R`
suffixes), heat weighting with per-part rules (rigid props, a skirt that hands weight to the thighs,
parts limited to named bones), and extra bones for anything that must come off or swing (a hat, a
lantern ring). The review sheet adds a posed three-quarter and front view: an arm raised, the head
turned, a knee lifted.

**Gate:** the posed views bend without tearing, nothing passes through the body, props follow the
hands. Open the sheet, write what you saw, and record it with `review.py record` (model-build skill).

Rigging notes:

- Name bones for the engine's humanoid standard, with Blender `.L`/`.R` suffixes; keep one
  explicit map from engine bone names to yours, shared by the forge and the engine importer, and
  test that they match.
- Bind pose: A-pose with the arms where the blueprint put them; the engine's importer enforces a
  T-pose for the avatar.
- Heat weighting, then rules per part: rigid props, parts limited to named bones, a skirt rule that
  hands weight to the thighs below the hip (without it a lifted knee goes through a robe).
- A thing that must come off later (a hat, a helmet, a lantern) gets its own rigid bone.
- One material slot means per-player colour needs a baked dye mask (white where dyed), imported
  linear.

## Stage 6: clips

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

Clip notes:

- Author on one reference skeleton; retarget to each model the way the engine will (Humanoid), and
  review on the real model, not the reference.
- Gaits are parameters (speed, cycle, duty, stride, bob, lean, arm swing), solved with foot IK, so
  the stride matches the in-game speed and the foot-slide metric proves it.
- A clip that must play over another (casting while walking) is authored for an upper-body mask and
  reviewed both alone and over locomotion.
- Export animation-only FBX per family, re-import to check every take, and write a manifest the
  engine importer and its tests read (loop flags, events, lengths).

Review per clip: frame sheets of every clip (below), 8 stills on the actual target model with the
matching reference frames beside them, a foot-contact trace for locomotion, an MP4.

**Gate:** both frame sheets opened and recorded with `review.py frames`, no rest-pose mismatch,
props held as designed in every clip (a weapon on a hand bone follows an empty-handed swing),
each key pose matches its reference frame side by side, feet do not slide (metric under
1 cm), nothing below the floor, the pose reads as the action at a glance, and a one-shot ends where
the next state expects it (a death ends lying still).

## Frame sheets: every clip, in Unity and in Blender (mandatory)

Any step that makes or changes a clip, a controller or a clip's import settings ends with **frame
sheets of every clip, rendered twice**: once in the engine on the model as the game uses it, once in
Blender on the model's own armature. Each sheet has the rest pose on top and a row per clip at five
evenly spaced moments, from a three-quarter front view and a side view. The Stop gate refuses to
pass while a changed clip file (`*.anim`, `*.bvh`, `*@*.fbx`, an FBX under an `animations/`,
`anims/` or `clips/` folder), controller (`*.controller`, `*.overrideController`) or its `.meta` has
no record pointing at both sheets, both newer than the change and both opened with Read this
session.

Render and compare them with the **frame-sheet-compare** skill (`../frame-sheet-compare/SKILL.md`):
`unity_frame_sheets.sh`, then `blender_frame_sheets.py --match` (which also writes `<name>_rest.json`),
then `frame_sheet_pages.py label` and `compare`. That skill holds the renderers, the shared camera
file and the renderer traps. Render the clip file on its own skeleton too (enter the clip file
itself as a Unity entry): the sheets differ where the engine changes the motion. Then open both
sheets, and record the look:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/review.py" frames --covers <clip files and controllers> \
    --unity-sheet <png> --blender-sheet <png> --rest-pose <out>/<name>_rest.json \
    --verdict pass --seen "<what you saw in both, at least 40 characters>"
```

**The rest poses must match.** `blender_frame_sheets.py` compares every bone's rest orientation in
the clip file with the model's. A clip exported on another rest pose plays with every prop on those
bones turned by the difference; the bone names still match, so the engine imports it without a
word. The record is refused, and the stop blocked, while the comparison lists a bone more than 5
degrees off, unless `--rest-ok` says why the difference does no harm. Fix it by re-exporting the
clips on the model's own rest pose.

A project without Unity or Blender sets `"anim_globs": []` in `.art-pipeline.json` and says so; the
gate is then off for clips.

## Traps that already cost a day

- **A clip file exported on another rest pose imports without a word.** The bone names match, so
  the engine accepts it, and every prop on a bone whose rest differs is turned by the difference
  (one boss's greatsword: 65 degrees). `blender_frame_sheets.py` compares the rest poses.
- **Shared clips made empty-handed swing every held prop.** A weapon parented to a hand bone goes
  wherever the hand goes; idle, walk and run need an arms layer that holds the carry pose.
- **Edit-mode clip sampling in Unity:** `AnimationMode.SampleAnimationClip`, not
  `clip.SampleAnimation` or a PlayableGraph (both leave a preview-scene pose frozen), and
  `forceMatrixRecalculationPerRender` on every skinned mesh, or each render in one call shows the
  first pose.

## Worked example

`examples/anim-review/`: the frame-sheet review that made the step mandatory. Weapons on 14 enemies
followed an empty-handed arm swing, and one boss's clip file had been exported on another rest pose
(hands 79 and 85 degrees off), so his greatsword was 65 degrees off in game. Every one of those
clips had passed its checks. Start with its `report.md`.
