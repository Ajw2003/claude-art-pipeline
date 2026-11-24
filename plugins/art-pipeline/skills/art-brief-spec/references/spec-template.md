# Spec template: what a human approves before anything is made

A spec is one batch of work the human approves in one go: one asset, or several items together
(say four enemies of one Age), as long as every part of every item has its own reference. Save it
as `docs/art/specs/<id>.json`; the `id` is lowercase letters, digits, `-` or `_`, and equals the
file name.

`approve.py check <id>` lists every problem by item and part. When there are none, it writes the
review sheet `docs/art/specs/<id>.sheet.html` and prints the question to ask. The sheet is the
only thing the human reviews, and it always has the same layout: one card per item; inside it,
the parts in a fixed order (model, rig, texture, sprite, UI art, animation, VFX, sound, music);
for each part the reference shown large with one line on what to take from it, the key poses as
a strip, and at most three tick boxes. Commit the spec and the sheet.

```json
{
  "id": "powder-soldiers",
  "title": "Powder Age: Musketeer and Petardier",
  "iterations": 6,
  "items": [
    {
      "name": "Musketeer",
      "match": ["musketeer"],
      "paths": ["Tools/ArtForge/anim_forge/*", "Assets/Models/ArtBible/Animations/Musketeer*"],
      "parts": {
        "animation": {
          "references": [
            {"file": "docs/art/reference/powder-soldiers/de-gheyn-32.jpg",
             "source": "Jacob de Gheyn, Wapenhandelinghe (1607), plate 32, Wikimedia Commons",
             "shows": "barrel laid in the rest's fork, butt at the cheek"}
          ],
          "key_poses": [
            {"at": "1.2 s", "ref": "docs/art/reference/powder-soldiers/de-gheyn-32.jpg",
             "pose": "barrel in the fork, butt at the cheek"}
          ],
          "check": ["the 1.2 s frame matches plate 32 side by side"]
        },
        "sfx": {
          "references": [
            {"file": "docs/art/reference/powder-soldiers/matchlock.ogg",
             "source": "freesound.org/s/<id>, CC0", "shows": "a sharp crack with a long tail"}
          ],
          "duration_s": 1.4,
          "check": ["crack first, then the tail, like the recording"]
        }
      }
    },
    {
      "name": "Petardier",
      "paths": ["Assets/Models/ArtBible/Enemies/Powder/Petardier/*"],
      "parts": {
        "model": {
          "references": [
            {"file": "docs/art/reference/powder-soldiers/petard-engraving.jpg",
             "source": "Rijksmuseum open-access collection, public domain",
             "shows": "the bell-shaped petard on its plank"}
          ],
          "check": ["petard size against the 1.80 m figure"]
        }
      }
    }
  ]
}
```

## Fields

| Field | Where | Rule |
|---|---|---|
| `id` | spec | equals the file name |
| `title` | spec | 5-60 characters |
| `iterations` | spec | builds allowed **per item**, 1-20 (default 5); a re-approval starts them again |
| `items` | spec | at least one |
| `name` | item | 2-40 characters, unique in the spec |
| `paths` | item | globs of every file this item may write: generators, solvers and outputs |
| `match` | item | words that name the item in a build command (default: the name as a slug) |
| `parts` | item | one or more of `model`, `rig`, `texture`, `sprite`, `ui`, `animation`, `vfx`, `sfx`, `music`, `other` |
| `references` | part | at least one `{file, source, shows}`: a file under `docs/art/reference/`, where it came from (URL or citation), and what to take from it (10-120 characters). Visual parts need an image; `sfx` and `music` need an audio file. Video (`.mp4`, `.webm`) may sit beside them |
| `check` | part | 1-3 things the human compares with the reference, 10-100 characters each |
| `key_poses` | animation | each `{at, ref, pose}`: a time, one of the part's reference images, and the pose as it appears there (10-100 characters) |
| `duration_s` | sfx, music | length in seconds |

The length limits are fixed on purpose: every sheet reads the same way, and nothing on it is long.
The embedded reference must stay under 15 MB, so save reference at screen size, not print size.

## What counts as reference

Reference is real-world material made by someone else: a photograph, a period drill manual's
plate, a video frame, a motion-capture take, a field recording, a museum piece. It is never this
pipeline's own concept sheet or render. Prefer free sources: Wikimedia Commons, museum open-access
collections, the CMU Graphics Lab Motion Capture Database (free to use), Freesound (check each
licence). Record the licence in `source` when it is not public domain.

For motion, a mocap take or a video is the best reference; a still plate fixes the key poses. Save
the frames you take key poses from as images, so they show on the sheet and can be compared.

## What an approval unlocks

For each item, once the human approves and one of that item's reference images has been opened:
writes to the item's `paths`, and build commands naming one of its `match` words, until its
`iterations` are spent. Everything else that counts as art stays locked. Art a command makes
outside an approval is put back at once; a copy is kept in `.git/art-pipeline/quarantine/`.
