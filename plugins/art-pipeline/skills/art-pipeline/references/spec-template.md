# Asset spec template: what a human approves before anything is made

Save one spec per asset (or per tight family, such as one enemy's attack clips) as
`docs/art/specs/<id>.json`. The `id` is lowercase letters, digits, `-` or `_`, and equals the file
name. `approve.py check <id>` lists every missing field; nothing can be built until it passes and a
human approves it.

```json
{
  "id": "musketeer-aim",
  "kind": "animation",
  "summary": "Musketeer lays the musket in the rest's fork and brings the butt to the cheek",
  "references": [
    {
      "file": "docs/art/reference/musketeer-aim/de-gheyn-plate-32.jpg",
      "source": "Jacob de Gheyn, Wapenhandelinghe (1607), plate 32, Wikimedia Commons",
      "shows": "barrel resting in the fork, butt at the cheek, left hand on the rest below the fork"
    }
  ],
  "key_poses": [
    {"at": "0.0 s", "ref": "docs/art/reference/musketeer-aim/de-gheyn-plate-31.jpg",
     "pose": "musket shouldered, rest trailed in the left hand"},
    {"at": "1.2 s", "ref": "docs/art/reference/musketeer-aim/de-gheyn-plate-32.jpg",
     "pose": "barrel in the fork, butt at the cheek, eye along the barrel"}
  ],
  "acceptance": [
    "the final frame matches plate 32's silhouette when set side by side",
    "the barrel sits in the fork on every frame after 1.2 s"
  ],
  "paths": ["Tools/ArtForge/anim_forge/*", "Assets/Models/ArtBible/Animations/*"],
  "match": ["musketeer"],
  "iterations": 6
}
```

## Fields

| Field | Required | Rule |
|---|---|---|
| `id` | yes | equals the file name |
| `kind` | yes | `animation`, `model`, `rig`, `vfx`, `sfx`, `music`, `texture`, `sprite`, `ui` or `other` |
| `summary` | yes | at least 20 characters saying what is made |
| `references` | yes | at least one, each a file under `docs/art/reference/`, with `source` (a URL or a citation) and `shows` (what to take from it). Every kind except `sfx` and `music` needs at least one image |
| `acceptance` | yes | what the human will check against the reference, each line checkable by looking |
| `paths` | yes | globs of every file this work writes: generators, solvers and outputs. Only these become writable |
| `match` | no | words that name this asset in a build command (default: the id). A build command runs only if it contains one |
| `iterations` | no | how many build or render runs the human allows before it comes back to them (default 5, at most 20) |
| `key_poses` | animation | each `{at, ref, pose}`: a time, the reference file it is taken from, and the pose as seen there |
| `duration_s` | sfx, music | length in seconds |

## What counts as reference

Reference is real-world material made by someone else: a photograph, a period drill manual's
plate, a video frame, a motion-capture take, a field recording, a museum piece. It is never this
pipeline's own concept sheet or render. Prefer free sources: Wikimedia Commons, museum open-access
collections, the CMU Graphics Lab Motion Capture Database (free to use), Freesound (check each
licence). Record the licence in `source` when it is not public domain.

For motion, a mocap take or a video is the best reference; a still plate fixes the key poses. Save
the frames you take key poses from as images, so they can be opened and compared.
