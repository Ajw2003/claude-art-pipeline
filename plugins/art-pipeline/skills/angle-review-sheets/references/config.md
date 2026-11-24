# angle-review.json

All paths are relative to the folder the config file is in.

```json
{
  "model_glob": "Characters/*/{character}/{character}.blend",
  "clips_dir": "Animations",
  "base_clips": ["Humanoid_Base.fbx"],
  "agent_yaw_file": "angle_agent_yaw.py",
  "characters": {
    "Musketeer": { "clips": ["Musketeer_Attacks.fbx"] },
    "Ophan": { "clips": ["Ophan_Generic.fbx"], "no_base": true },
    "PalaceGuard": { "clips": [] }
  }
}
```

- `model_glob`: where a character's .blend is; `{character}` is replaced by its name; `*` matches folders.
  The .blend must hold exactly one armature (the one posed) and its meshes.
- `clips_dir`: folder of animation FBX files. Each FBX holds an armature with the same bone names as the model
  and one or more actions (clips). Clip names are the part of the action name after the last `|`.
- `base_clips`: files every character plays (idle, walk...). A character with `"no_base": true` skips them.
- `agent_yaw_file` (optional): a Python file defining `AGENT_YAW = {clip_name: fn}` where `fn(seconds)` returns
  degrees of yaw to add to the whole body. For clips that only start a turn while the game's agent finishes it.
- `characters`: the order here is the order of the run and of the page.

## Bone names the script relies on

`Hips` (camera follows it; falls back to the first root bone), `UpperLeg.L` and `LowerLeg.L` (size ratio between
the clip rig and the model; falls back to every shared bone for a rig without legs), `Foot.L` (which way the
model faces; falls back to -Y). Rename in the script if your rig differs.

## Checking a run

`RESULT <Character>: N frames, M clips, M videos -> <out>` is the success line; the runner marks a character PASS
only when that line is present and the exit code is 0.
