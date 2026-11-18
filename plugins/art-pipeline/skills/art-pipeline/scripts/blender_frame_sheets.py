"""Frame sheets in Blender: a clip file's actions played on the model's own armature, no engine retargeting, laid out
like unity_frame_sheets.cs (rest pose on top, a row per clip, evenly spaced frames, three-quarter then side view).
It also compares the rest pose of the clip file's armature with the model's: a clip exported on another rest pose
plays with every prop on that bone turned by the difference (the Crusader's greatsword was 65 degrees off).

Run with Blender itself (workbench needs a GPU; the bpy wheel without one should use --engine CYCLES):
  blender -b --factory-startup -P blender_frame_sheets.py -- --model <model.fbx|.glb|.blend> [--clips <clip file>] \
          --out <dir> [--name N] [--steps 5] [--max-deg 5] [--gap BoneA BoneB] [--dir Bone] [--engine WORKBENCH]
Without --clips the actions inside the model file are used. Writes <out>/raw/<name>_blender.png and .json, and
<out>/<name>_rest.json (the rest-pose comparison); then run frame_sheet_pages.py label <out>.
"""
import argparse
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser(prog="blender_frame_sheets.py")
ap.add_argument("--model", required=True)
ap.add_argument("--clips")
ap.add_argument("--out", required=True)
ap.add_argument("--name")
ap.add_argument("--steps", type=int, default=5)
ap.add_argument("--max-deg", type=float, default=5.0, help="rest-pose difference, in degrees, that counts as a mismatch")
ap.add_argument("--gap", nargs=2, metavar=("BONE_A", "BONE_B"))
ap.add_argument("--dir", metavar="BONE")
ap.add_argument("--engine", default="BLENDER_WORKBENCH")
a = ap.parse_args(argv)
W, H = 240, 320
name = a.name or os.path.splitext(os.path.basename(a.model))[0]
raw_dir = os.path.join(a.out, "raw")
os.makedirs(raw_dir, exist_ok=True)


def load(path):
    before_obj, before_act = set(bpy.data.objects), set(bpy.data.actions)
    ext = os.path.splitext(path)[1].lower()
    if ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    elif ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".blend":
        with bpy.data.libraries.load(path) as (src, dst):
            dst.objects, dst.actions = src.objects, src.actions
        for o in dst.objects:
            if o is not None:
                bpy.context.scene.collection.objects.link(o)
    else:
        sys.exit("blender_frame_sheets: cannot load %s" % path)
    objs = [o for o in bpy.data.objects if o not in before_obj]
    rig = next((o for o in objs if o.type == "ARMATURE"), None)
    return objs, rig, [x for x in bpy.data.actions if x not in before_act]


bpy.ops.wm.read_factory_settings(use_empty=True)
model_objs, rig, model_actions = load(a.model)
if rig is None:
    sys.exit("blender_frame_sheets: %s has no armature" % a.model)
if a.clips and os.path.normcase(os.path.abspath(a.clips)) != os.path.normcase(os.path.abspath(a.model)):
    clip_objs, clip_rig, actions = load(a.clips)
    for o in clip_objs:  # the clip file brings its own armature and meshes: hide them, keep its actions
        o.hide_render = o.hide_viewport = True
else:
    clip_rig, actions = None, model_actions
if not actions:
    sys.exit("blender_frame_sheets: no actions in %s" % (a.clips or a.model))


def rest_local(bone):
    """The bone's rest orientation relative to its parent, which is what a clip's keys are applied on top of."""
    return (bone.parent.matrix_local.inverted() @ bone.matrix_local) if bone.parent else bone.matrix_local


rest = {"model": a.model, "clips": a.clips or a.model, "max_deg": a.max_deg, "bones": [], "mismatch": [],
        "only_in_model": [], "only_in_clips": []}
if clip_rig is not None:
    clip_bones, model_bones = clip_rig.data.bones, rig.data.bones
    for b in model_bones:
        if b.name not in clip_bones:
            rest["only_in_model"].append(b.name)
            continue
        q1, q2 = rest_local(b).to_quaternion(), rest_local(clip_bones[b.name]).to_quaternion()
        deg = math.degrees(q1.rotation_difference(q2).angle)
        deg = min(deg, 360 - deg)
        rest["bones"].append({"bone": b.name, "deg": round(deg, 2)})
        if deg > a.max_deg:
            rest["mismatch"].append({"bone": b.name, "deg": round(deg, 2)})
    rest["only_in_clips"] = [b.name for b in clip_bones if b.name not in model_bones]
rest_path = os.path.join(a.out, name + "_rest.json")
with open(rest_path, "w", encoding="utf-8") as fh:
    json.dump(rest, fh, indent=1)
    fh.write("\n")
print("REST: %d bones compared, %d over %.1f deg: %s" % (
    len(rest["bones"]), len(rest["mismatch"]), a.max_deg,
    ", ".join("%s %.1f" % (m["bone"], m["deg"]) for m in rest["mismatch"]) or "none"))

scene = bpy.context.scene
scene.render.engine = a.engine
if a.engine == "BLENDER_WORKBENCH":
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "TEXTURE"
else:
    scene.cycles.samples = 16
scene.render.resolution_x, scene.render.resolution_y = W, H
scene.render.film_transparent = False
scene.world = bpy.data.worlds.new("w")
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
cam.data.lens = 50
scene.collection.objects.link(cam)
scene.camera = cam
if scene.render.engine != "BLENDER_WORKBENCH":
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.rotation_euler = (math.radians(50), 0, math.radians(30))
    scene.collection.objects.link(sun)

height = max([(o.matrix_world @ Vector(c)).z for o in model_objs if o.type == "MESH" for c in o.bound_box] or [1.5])
height = max(height, 1.5)
target = Vector((0, 0, height * 0.5))
dist = height * 2.6
VIEWS = (35, 90)  # three-quarter front, then the model's right side, as in the Unity sheet


def aim(yaw_deg):
    # FBX import turns Unity's +Z forward into Blender's -Y: the model faces -Y.
    yaw = math.radians(yaw_deg)
    cam.location = target + Vector((math.sin(yaw) * dist, -math.cos(yaw) * dist, height * 0.12))
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()


def render():
    path = os.path.join(bpy.app.tempdir, "frame.png")
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(path)
    px = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)
    bpy.data.images.remove(img)
    return px  # bottom-up rows


def probe(r):
    """The same numbers unity_frame_sheets.cs writes, in Unity's axes (x right, y up, z forward)."""
    out, m = {}, r.matrix_world
    pb = r.pose.bones
    if a.gap and all(n in pb for n in a.gap):
        out["gap"] = round(((m @ pb[a.gap[0]].head) - (m @ pb[a.gap[1]].head)).length, 3)
    if a.dir and a.dir in pb:
        d = ((m @ pb[a.dir].tail) - (m @ pb[a.dir].head)).normalized()
        out["dir"] = [round(-d.x, 3), round(d.z, 3), round(-d.y, 3)]
    return out


if rig.animation_data is None:
    rig.animation_data_create()
grid, rows = [], []
rig.animation_data.action = None
for pb in rig.pose.bones:
    pb.matrix_basis.identity()
scene.frame_set(0)
rows.append({"label": "rest pose", "probe": probe(rig)})
cells = []
for v in VIEWS:
    aim(v)
    cells.append(render())
blank = np.broadcast_to(cells[0][0, 0], (H, W, 4))
grid.append([cells[0]] + [blank] * (a.steps - 1) + [cells[1]] + [blank] * (a.steps - 1))
for act in actions:
    rig.animation_data.action = act
    if hasattr(rig.animation_data, "action_slot") and getattr(act, "slots", None):
        rig.animation_data.action_slot = act.slots[0]
    start, end = act.frame_range
    frames = [int(round(start + (end - start) * i / (a.steps - 1))) for i in range(a.steps)]
    per_view = [[None] * a.steps for _ in VIEWS]
    if clip_rig is not None:  # the clip file's own skeleton plays it too: the numbers as authored
        if clip_rig.animation_data is None:
            clip_rig.animation_data_create()
        clip_rig.animation_data.action = act
        if hasattr(clip_rig.animation_data, "action_slot") and getattr(act, "slots", None):
            clip_rig.animation_data.action_slot = act.slots[0]
    for i, f in enumerate(frames):
        scene.frame_set(f)
        if i == 0:
            p = probe(rig)
            p_own = probe(clip_rig) if clip_rig is not None else None
        for vi, v in enumerate(VIEWS):
            aim(v)
            per_view[vi][i] = render()
    grid.append([c for row in per_view for c in row])
    label = act.name.split("|")[-1]
    rows.append({"label": label, "frames": [int(start), int(end)], "probe": p})
    if p_own is not None:
        rows[-1]["probe_clip_rig"] = p_own
    print("ROW %d: %s %d-%d model rig %s, clip file's rig %s" % (len(rows) - 1, label, start, end, p, p_own))

# Images are bottom-up, so the first row (rest pose) goes last in memory.
sheet = np.concatenate([np.concatenate(row, axis=1) for row in grid[::-1]], axis=0)
img = bpy.data.images.new("sheet", sheet.shape[1], sheet.shape[0], alpha=True)
img.pixels = sheet.ravel()
img.filepath_raw = os.path.join(raw_dir, name + "_blender.png")
img.file_format = "PNG"
img.save()
with open(os.path.join(raw_dir, name + "_blender.json"), "w", encoding="utf-8") as fh:
    json.dump({"name": name + "_blender", "engine": "blender", "asset": a.model, "clips_from": a.clips or a.model,
               "cell": [W, H], "steps": a.steps, "views": ["three-quarter", "side"], "axes": "x right, y up, z forward",
               "probe_bones": {"gap": " ".join(a.gap or []), "dir": a.dir or ""}, "rest_pose": rest_path,
               "rows": rows}, fh, indent=1)
    fh.write("\n")
print("saved", img.filepath_raw)
