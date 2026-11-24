# Tooling: Blender as a module, and the blueprint pattern

## Blender as a Python module

No Blender install and no `blender` binary: `pip install bpy` gives Blender as an importable
module, and scripts run as `python3.11 script.py`, never `blender --background --python`.

- **Match the wheel to the interpreter.** `bpy` 5.0.x ships for CPython 3.11 only; 5.1 and later
  for 3.13. Plain `python3` is often neither. `../scripts/setup_bpy.sh` finds one that works,
  installs `bpy` and Pillow into it, and prints the command prefix to use.
- **Cycles on CPU only** in a container without a GPU. EEVEE and Workbench do not raise without a
  GPU or `libEGL.so.1`: they abort the interpreter. Freestyle crashes headless too (its auto-created
  line set has no line style); draw wireframes with a Wireframe shader node instead.
- `import bpy` must come before `mathutils` and friends.
- Renders at 32 samples and 700 px per view take about a minute for six views on 4 cores. Keep
  review renders small; they are for looking, not for shipping.

## The blueprint pattern

One module per asset family, `BLUEPRINTS = {slug: builder}`; a builder takes the parsed spec entry
and returns parts. The registry refuses a slug the spec does not list. Part kinds that cover almost
everything: `box`, `cyl`, `cone`, `sphere`, `lathe` (revolve a profile: pots, hats, helmets),
`prism` (extrude an outline: blades, plaques), `tube` (sweep a section along a path: handles,
straps, chains), `loft` (skin a stack of rings: torsos, robes, shoes), `sweep` (a tube whose
section changes: limbs, tails). Paint bands restamp faces inside a box with another material, so
trim stays on the same shell.
