# Stages 0, 1, 2, 3 and 8, in full

Paths below are the defaults; a project that already has its own layout keeps it and says so in
its brief. Every stage's outputs are committed, sheets and renders included: they are the record of
what was looked at.

## 0. Protect the work

Long Blender runs and multi-worker batches get cut off (usage limits, a reclaimed container).
Commit on your own branch after every asset, or run an autosave that commits and pushes only the
paths this run writes, every few minutes. Never a broad `git add -A`: another worker may be writing
elsewhere in the same checkout.

## 1. Brief and style bible

Before anything is drawn. Copy `style-bible-template.md` to `docs/art/BRIEF.md` and fill it in
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

**The spec** (`docs/art/specs/<id>.json`, from `spec-template.md`) covers one item or a batch of
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
## 8. Docs agree, then commit

Update the project's docs in the tier that changed (state, today, the system doc for the asset
family, the scale doc's roster). Then run the project's doc-drift check: a small script that
compares the docs with the data and code (every asset in the spec appears in the roster doc at the
same size; every roster entry still exists; every path a doc names exists) and fails on any
difference. If the project has none, write one; wire it into CI. Docs that describe art drift the
moment a roster changes.

Rebuild the batch twice (the second run meets the state the first left), commit every output,
push.
