"""Frame sheets in Blender: a clip file's actions played on the model's own armature, no engine retargeting, laid out
like unity_frame_sheets.cs (rest pose on top, a row per clip, evenly spaced frames, three-quarter then side view).
It also compares the rest pose of the clip file's armature with the model's: a clip exported on another rest pose
plays with every prop on that bone turned by the difference (the Crusader's greatsword was 65 degrees off).

The camera, light and layout come from frame_camera.txt, the file unity_frame_sheets.cs reads too, turned from Unity's
axes into Blender's (the model faces -Y, as an FBX from Unity imports). With --match <Unity raw sheet .json> it also
takes that sheet's framing height, row order and loop flags, so every cell is the same moment from the same camera:
a controlled comparison (frame_sheet_pages.py compare lays the two side by side and scores every cell).

Run with Blender itself or the bpy module (EEVEE needs a GPU; without one use --engine CYCLES):
  blender -b --factory-startup -P blender_frame_sheets.py -- --model <model.fbx|.glb|.blend> [--clips <clip file>] \
          --out <dir> [--name N] [--match <out>/raw/<unity name>.json] [--steps 5] [--max-deg 5] \
          [--gap BoneA BoneB] [--dir Bone] [--engine BLENDER_EEVEE]
Paths must be absolute. Without --clips the actions inside the model file are used. Writes <out>/raw/<name>_blender.png
and .json, and <out>/<name>_rest.json (the rest-pose comparison); then run frame_sheet_pages.py label <out>.
"""
import argparse
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))


def read_camera(path):
    """frame_camera.txt: one setting per line, numbers after the key; 'light' may repeat."""
    cam = {"light": []}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            bits = line.split("#")[0].split()
            if bits:
                nums = [float(x) for x in bits[1:]]
                if bits[0] == "light":
                    cam["light"].append(nums)
                else:
                    cam[bits[0]] = nums
    return cam


CAMERA = read_camera(os.path.join(HERE, "frame_camera.txt"))

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser(prog="blender_frame_sheets.py")
ap.add_argument("--model", required=True)
ap.add_argument("--clips")
ap.add_argument("--out", required=True)
ap.add_argument("--name")
ap.add_argument("--steps", type=int, help="moments per clip (default: frame_camera.txt)")
ap.add_argument("--match", help="the Unity sheet's raw .json: use its framing height, row order and loop flags")
ap.add_argument("--max-deg", type=float, default=5.0, help="rest-pose difference, in degrees, that counts as a mismatch")
ap.add_argument("--gap", nargs=2, metavar=("BONE_A", "BONE_B"))
ap.add_argument("--dir", metavar="BONE")
ap.add_argument("--engine", default="BLENDER_EEVEE")
a = ap.parse_args(argv)
W, H = (int(x) for x in CAMERA["cell"])
match = None
if a.match:
    with open(a.match, encoding="utf-8") as fh:
        match = json.load(fh)
    if "frame" not in match:
        sys.exit("blender_frame_sheets: %s has no framing height; re-render it with this plugin's unity_frame_sheets.sh" % a.match)
a.steps = a.steps or (match["steps"] if match else int(CAMERA["steps"][0]))
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
scene.render.resolution_x, scene.render.resolution_y = W, H
scene.render.resolution_percentage = 100
scene.render.film_transparent = True  # the background colour goes in afterwards, exactly as Unity clears to it
scene.view_settings.view_transform = "Standard"  # Unity writes plain sRGB: no filmic tone curve
scene.view_settings.look = "None"
if a.engine == "CYCLES":
    scene.cycles.samples = 16
scene.world = bpy.data.worlds.new("w")  # flat ambient, as Unity's preview ambient colour
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = list(CAMERA["ambient"]) + [1.0]
scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
cam.data.sensor_fit = "VERTICAL"
cam.data.angle_y = math.radians(CAMERA["fov"][0])
cam.data.clip_start, cam.data.clip_end = 0.05, 100.0
scene.collection.objects.link(cam)
scene.camera = cam


def unity_dir(pitch_deg, yaw_deg):
    """Where Unity's Euler(pitch, yaw, 0) points its forward axis, in Blender's axes (Unity x, y, z -> -x, -z, y)."""
    p, y = math.radians(pitch_deg), math.radians(yaw_deg)
    ux, uy, uz = math.cos(p) * math.sin(y), -math.sin(p), math.cos(p) * math.cos(y)
    return Vector((-ux, -uz, uy))


for i, (lp, ly, r, g, b, strength) in enumerate(CAMERA["light"]):
    sun = bpy.data.objects.new("sun%d" % i, bpy.data.lights.new("sun%d" % i, "SUN"))
    sun.data.color, sun.data.energy, sun.data.angle = (r, g, b), strength, 0.0
    sun.data.use_shadow = False  # Unity's preview lights cast none
    sun.rotation_euler = unity_dir(lp, ly).to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(sun)

if match:
    height = match["frame"]["height"]
else:  # the same measure Unity takes: the height of everything drawn, at rest, at least 1.5
    zs = [(o.matrix_world @ Vector(c)).z for o in model_objs if o.type == "MESH" and not o.hide_render for c in o.bound_box]
    height = max(max(zs) - min(zs) if zs else 0.0, 1.5)
target = Vector((0, 0, height * 0.5))
dist = height * 0.5 / math.tan(math.radians(CAMERA["fov"][0]) * 0.5) * CAMERA["fit"][0]
VIEWS = CAMERA["yaws"]
BACKGROUND = np.array(CAMERA["background"], dtype=np.float32)


def aim(yaw_deg):
    # Unity puts its camera at target - Euler(pitch, 180 + yaw) * forward * dist, looking at the target.
    cam.location = target - unity_dir(CAMERA["pitch"][0], 180.0 + yaw_deg) * dist
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()


def render():
    path = os.path.join(bpy.app.tempdir, "frame.png")
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(path)
    px = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)
    bpy.data.images.remove(img)
    alpha = px[:, :, 3:4]
    px[:, :, :3] = px[:, :, :3] * alpha + BACKGROUND * (1.0 - alpha)
    px[:, :, 3] = 1.0
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
grid.append([c for cell in cells for c in [cell] + [blank] * (a.steps - 1)])
by_label = {}
for act in actions:
    by_label.setdefault(act.name.split("|")[-1], act)
if match:  # Unity's rows in Unity's order; a clip only one side has still gets a row, left empty on the other
    plan = [(r["label"], r.get("loop", False)) for r in match["rows"][1:]]
    plan += [(lab, False) for lab in by_label if lab not in {p[0] for p in plan}]
else:
    plan = [(lab, False) for lab in by_label]
for label, loop in plan:
    act = by_label.get(label)
    if act is None:
        grid.append([blank] * (a.steps * len(VIEWS)))
        rows.append({"label": label, "loop": loop, "missing": "not in %s" % (a.clips or a.model)})
        print("ROW %d: %s missing from the clip file" % (len(rows) - 1, label))
        continue
    rig.animation_data.action = act
    if hasattr(rig.animation_data, "action_slot") and getattr(act, "slots", None):
        rig.animation_data.action_slot = act.slots[0]
    start, end = act.frame_range
    # Unity samples a looping clip at length * i / steps (the last moment would repeat the first), else i / (steps - 1).
    # On a whole key, as unity_frame_sheets.cs samples: between keys each engine interpolates its own way.
    frames = [start + math.floor((end - start) * i / (a.steps if loop else a.steps - 1) + 0.5) for i in range(a.steps)]
    per_view = [[None] * a.steps for _ in VIEWS]
    if clip_rig is not None:  # the clip file's own skeleton plays it too: the numbers as authored
        if clip_rig.animation_data is None:
            clip_rig.animation_data_create()
        clip_rig.animation_data.action = act
        if hasattr(clip_rig.animation_data, "action_slot") and getattr(act, "slots", None):
            clip_rig.animation_data.action_slot = act.slots[0]
    for i, f in enumerate(frames):
        scene.frame_set(int(math.floor(f)), subframe=f - math.floor(f))
        if i == 0:
            p = probe(rig)
            p_own = probe(clip_rig) if clip_rig is not None else None
        for vi, v in enumerate(VIEWS):
            aim(v)
            per_view[vi][i] = render()
    grid.append([c for row in per_view for c in row])
    rows.append({"label": label, "frames": [int(start), int(end)], "loop": loop, "probe": p})
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
               "frame": {"height": height}, "matched_to": a.match or "",
               "probe_bones": {"gap": " ".join(a.gap or []), "dir": a.dir or ""}, "rest_pose": rest_path,
               "rows": rows}, fh, indent=1)
    fh.write("\n")
print("saved", img.filepath_raw)
