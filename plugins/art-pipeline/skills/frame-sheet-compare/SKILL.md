---
name: frame-sheet-compare
description: Render every animation clip as frame sheets twice - in Unity on the model as the game plays it, and in Blender on the model's own armature - from one shared camera, light and sampling file, then score each row with a silhouette overlay so the two are a controlled comparison. Use when a clip, controller or clip import setting changed and must be checked in engine (the art-pipeline Stop gate asks for these sheets), when asked whether Unity plays what Blender shows, or to compare animations across engines; not for judging a single model's look.
---

# Frame-sheet compare (Unity against Blender)

A clip can pass every check and still play wrong in game: another rest pose turns every prop, a
retarget bends an arm, an import setting drops a key. This skill draws the same clip file in Unity and
in Blender from the same camera at the same keys, lays the two side by side and scores how far apart
they are, so a difference means the engine changed the motion, not that the cameras differ.

## What you get

| Path (under `--out`) | What it is |
|---|---|
| `raw/<name>.png`, `raw/<name>.json` | Unlabelled sheet and its layout: rest pose on top, a row per clip, five moments, a three-quarter front and a side view |
| `<name>.png` | The labelled sheet |
| `<name>_rest.json` | Blender only: every bone's rest orientation in the clip file against the model's |
| `compare_<unity>_<n>.png` | Each row three times: Unity, Blender, and both silhouettes over each other (red only Unity, cyan only Blender) |
| `compare_<unity>.json` | The score of every cell and row |

## Steps

Scripts are in `scripts/` next to this file. Needs a running Unity Editor with the Unity CLI, and Blender
(`blender` on PATH, or `pip install bpy`), numpy and Pillow.

```bash
# 1. Unity, Edit mode only (never Play): a prefab, a model file or a folder of prefabs, optionally =<controller or clip file>
bash scripts/unity_frame_sheets.sh --project <Unity project> --out <dir> [--gap Hand.L Hand.R] [--dir <prop bone>] <entry> [...]
# 2. Blender: the clip file's actions on the model's armature, matched to the Unity sheet
blender -b --factory-startup -P scripts/blender_frame_sheets.py -- --model <model> --clips <clip file.fbx> \
     --out <dir> --name <name> --match <dir>/raw/<unity name>.json [--gap Hand.L Hand.R] [--dir <prop bone>]
# 3. Label, then compare
python scripts/frame_sheet_pages.py label <dir>
python scripts/frame_sheet_pages.py compare <dir> <unity name> <name>_blender [--min-overlap 0.95] [--tolerance-px 2]
# optional
python scripts/frame_sheet_pages.py pages <dir>    # overview pages for many models
python scripts/frame_sheet_pages.py probes <dir>   # bone gap and prop direction, Unity beside Blender
```

Pass absolute paths to Blender. `compare` prints a `RESULT` line per row and overall, and exits 1 on a fail.

4. **Look.** Open both sheets and the compare pages with Read. A score is evidence, not a verdict.
5. **Record it** when the art-pipeline gate is on (`review.py frames ... --unity-sheet --blender-sheet --rest-pose`,
   see the art-pipeline skill). A matched pair that fails means the engine does not play what Blender shows:
   find out why before judging the motion itself.

## Why the comparison is controlled

- **One camera file.** Both renderers read `scripts/frame_camera.txt`: cell size, field of view, pitch, the two
  yaws, framing, background, ambient and two directional lights. Change it there, never in a renderer.
- **`--match`.** Blender takes the Unity sheet's framing height, row order and loop flags.
- **Whole keys.** Both sample every moment on a whole key; between keys each engine interpolates its own way.
- **Same look.** Blender uses EEVEE, the Standard view transform, suns at Unity's intensity with no shadows, and the
  ambient as the world colour. Metals still shine in Unity (it reflects its sky); silhouettes are what is scored.
- **Score.** Each cell scores the share of each silhouette within 2 px of the other (the lower of the two). Matched
  sheets of one clip file score 0.99; a limb, prop or body elsewhere scores well under 0.95 and fails the row.

## Traps, each of which cost a session

- **URP portrait field of view.** URP applies the field of view across the width of a portrait target, so a
  240x320 cell drew the model at three quarters size. The cell is rendered square and its middle cut out.
- **Humanoid sampling.** Use `AnimationMode.SampleAnimationClip`; plain `SampleAnimation` and a PlayableGraph leave
  the pose frozen in a preview scene.
- **`SkinnedMeshRenderer.forceMatrixRecalculationPerRender`** is set, or every render in one Editor frame shows the
  first pose.
- **5-second Unity CLI calls.** The renderer does one entry per call and resumes. A "Main thread operation timed
  out" is a busy Editor: run that entry again.
- **Dark armour.** The silhouette threshold is 6 grey levels from the background; 18 lost black armour.
- **Rest pose.** `<name>_rest.json` lists bones more than 5 degrees off the model's rest. A clip exported on another
  rest pose turns every prop on those bones by the difference while the bone names still match; re-export it.
