---
name: model-build
description: Build a 3D model with code (Blender as a Python module, a blueprint script per asset), render a review sheet of it beside its concept, look at the sheet and record what you saw. Use when asked to model a character, creature, prop or set piece from an approved spec, when a model "passes validation" and nobody has looked at it yet, or when a model changed and needs a fresh review sheet before the session can end.
---

# Model: build by blueprint, then look at it

Needs an approved spec with real-world reference first (the art-brief-spec skill). Rule two:
**look at it.** Nothing made by code is done until someone has opened a picture of it beside its
reference and concept and written down what they saw. A validator that passes says the numbers are
legal (closed mesh, under budget, right height). It cannot say the hat looks like a hat. The
plugin's Stop hook enforces this: a session cannot end while a model it changed has no review sheet
newer than the model, opened in this session, with a written verdict.

## Stage 4: the model

A blueprint per asset, in code: a list of parts (lathe, loft, sweep, tube, prism, box...) each with
a material family and, for rigged assets, a bone. The forge builds the mesh, bevels, unwraps, bakes
one texture set, and exports FBX (engine axes), glTF and `.blend`. A validator checks: closed and
manifold, consistent winding, UVs in 0-1, one material slot, identity transforms, grounded, under
the triangle budget, the height or bbox within tolerance of the spec, and (rigged) every vertex
weighted, at most 4 influences, weights summing to 1.

Then the review sheet: the concept on the left; three-quarter, front (beside the reference human),
side and wireframe renders on the right; a caption with triangles against budget, size against
spec, bones.

**Gate:** open the sheet. Silhouette and proportion against the concept; colours; key details
present; the caption's numbers. At least one improvement pass. A real conflict between the spec's
size line and its build notes is recorded as an override with the reason; the model is never
shrunk to pass.

## Steps

1. **Set up Blender as a Python module**: `sh scripts/setup_bpy.sh` (from this skill's folder).
   It finds a Python that matches a `bpy` wheel and installs it with Pillow. Cycles on CPU only:
   EEVEE and Workbench abort without a GPU. `references/tooling.md` has the rest.
2. **Build by blueprint, never by hand-edit.** Fix the generator, not its output, so a rebuild
   keeps the fix. Every output is regenerable from a committed script and spec. The blueprint
   pattern is in `references/tooling.md`.
3. **Render and compose the review sheet** for every model you touch:

   ```bash
   python3.11 scripts/render_views.py <model.fbx|.glb|.blend> --out <dir>
   python3 scripts/review_sheet.py --concept <concept.png> --views <dir> --title "<Name>" --out <sheet.png>
   ```

   Projects with their own renderer use it instead; the gate only
   cares that a fresh sheet exists and was opened. Finished sheets to copy the layout from:
   `examples/tripod-cauldron-review.png`, `examples/wizard-review.png`.
4. **Look.** Open the sheet with Read. Compare it with the concept, and write down what you saw:
   what matches, what does not, what you will change. Change, rebuild, re-render, look again. At
   least one improvement pass per asset; "it passed" is not a look.
5. **Record the look** so the gate can see it:

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/review.py" record --model <model path> --sheet <sheet.png> \
       --verdict pass --seen "<what you saw, at least 40 characters>"
   ```

   `--verdict waived` (with the reason in `--seen`) is for a model that genuinely cannot be
   rendered here; it is reported, never silent. `python "${CLAUDE_PLUGIN_ROOT}/scripts/review.py"
   status` lists what the gate will say before you stop.

## Traps that already cost a day

- **bmesh handles and index order go stale** after an op reallocates; stamp each element (material
  index, bone id) the moment it is created.
- **Material indices clamp to the slot count.** Writing index 3 to a mesh with no slots silently
  becomes 0: attach materials before writing face indices, and assert the families after baking.
- **Bevel interpolates float attributes** across the mesh; keep per-face identity in integer face
  data (material slots, an int face layer), never a float attribute.
- **A clamped bevel still leaves slivers** on thin trim: `use_clamp_overlap` plus a
  dissolve-degenerate pass.
- **8-bit emission maps clamp at 1.0;** scale the glow back up in the shipping material.
- **Metals render too warm** in a warm review studio; judge silver and steel from the baked colour.
- **Validation passing proves nothing about the look.** Every one of these traps passed validation.

## References

- `references/tooling.md`: Blender as a module, and the blueprint pattern.
- `scripts/`: `setup_bpy.sh`, `render_views.py`, `review_sheet.py`.
- `examples/`: two finished review sheets.
