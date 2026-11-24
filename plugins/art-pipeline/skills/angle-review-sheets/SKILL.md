---
name: angle-review-sheets
description: Render animation review sheets for characters in Blender-as-a-Python-module - every frame of every clip from front, three-quarter, side and top-down angles, one video per clip, banded JPEG strips, and a review page with Approved/Revise buttons and a "what to revise" box per character. Runs all characters one after another with failures isolated. Use when animations have been added or changed and someone must look at them (stage 6 of the art-pipeline), when asked for "sheets of every frame", angle sheets, or a review page for clips; not for judging a single model's concept or silhouette.
---

# Angle review sheets

Animation bugs hide in single views: a halberd sweeps out of frame, a body lies flat, a turn that is really
the game agent rotating the whole body shows as nothing. This skill draws every frame of every clip on the
character's own model from four angles, so a person can read the motion and say Approved or Revise.

## What you get

For each character, under the output folder:

| Path | What it is |
|---|---|
| `<Character>.json` | Index: each clip's frame count, video path and strip paths |
| `videos/<Character>/NN_<clip>.mp4` | The four views as a 2 x 2 looping video with a frame-number bar |
| `strips/<Character>/NN_<clip>_<k>.jpg` | Frames in bands of 3 columns x 8 rows. Four pictures per frame (front, three-quarter, side, top), a big frame number in each corner. Read each column top to bottom, then the next column to the right |
| `review.html` | One card per character: Approved / Revise, a notes box, the videos and strips |
| `run-summary.txt`, `logs/` | Written by the all-characters runner |

## Steps

1. **Write the config** (`references/config.md`): where the model .blend of each character lives, which FBX clip
   files it plays, and optionally the game-side turns. Keep it in the project, next to the clips.
2. **Install the tools once** (`../model-build/scripts/setup_bpy.sh`, or `pip install bpy pillow`; `ffmpeg` on PATH).
3. **Test on two or three characters with a few clips first.** Use `--only <clip> ...` on `angle_sheets.py`.
   Look at a strip and a video before committing to the long run. Check: numbers readable, order right,
   whole body in frame in every view, the top view actually turns on turn clips.
4. **Run everything with the runner**, in a Terminal the owner can watch:
   `python run_all.py --config angle-review.json --out <dir>`. Each character is its own process; a failure
   is logged as FAIL and the next one starts. Add `--skip-done` to resume.
5. **Open the page and look.** `run_all.py` rebuilds `review.html`. To view it off the machine publish it
   (with `strips/` and `videos/`) as a private artifact; a plain HTML file opened without its folders shows
   broken pictures. Never judge from the numbers alone: look at the pictures of each character.
6. **Record the verdicts.** The page keeps answers in the browser and has Copy results. Paste them back, fix
   the Revise items, re-render only those characters (`run_all.py --only Name`).

## Rules this skill exists to keep

- One process per character; the runner never lets one failure stop the rest.
- Per-clip adaptive framing (a measuring pass over every frame first), so long weapons and lying bodies fit.
- Animation is shown in place, as authored; clips that rely on the game agent turning the body need
  `agent_yaw_file` or their top-down view will look frozen.
- Big readable frame numbers and the column-by-column order; these were each reported as unreadable once.
- Look at the output before saying it is fine. See `references/traps.md` for what went wrong the first time.
