#!/usr/bin/env python3
"""Review sheets for one character: every frame of every clip it plays, from four angles, plus a video per clip.

    python angle_sheets.py --config angle-review.json <Character> [--out DIR] [--tile 160] [--only CLIP ...]

Needs the `bpy` and `pillow` Python packages and `ffmpeg` on PATH. The config (see ../references/config.md)
names the model .blend of each character and the animation FBX files it plays. Each clip is copied onto the
character's own armature by world pose, one frame at a time, and drawn with the Workbench renderer from front,
three-quarter, side and top-down orthographic cameras that follow the hips.

Output under --out: <Character>.json (the index), videos/<Character>/NN_<clip>.mp4 (the four views as a
2 x 2 picture), strips/<Character>/NN_<clip>_<k>.jpg (frames in bands of 3 columns x 8 rows, read each column
top to bottom, then the next column to the right). The last line is RESULT <Character>: ... on success.
"""

import argparse
import glob
import importlib.util
import json
import math
import os
import sys
import subprocess
import tempfile
import time

import bpy
from mathutils import Matrix, Vector
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ANGLES = ("front", "three-quarter", "side", "top")
COLUMNS, ROWS = 3, 8      # a band of the sheet: 8 frames down each of 3 columns, read column by column
VIDEO_SIZE = 256          # each view is drawn this big; the sheet shrinks it to --tile
FPS = 30

# Clips that only start a turn while the game's agent turns the body are listed in the config's "agent_yaw_file":
# a Python file defining AGENT_YAW = {clip_name: function(seconds) -> degrees}. Empty when the project has none.
AGENT_YAW = {}
CFG = {}


def load_config(path):
    global ANIMS, AGENT_YAW
    CFG.update(json.load(open(path, encoding="utf-8")))
    base = os.path.dirname(os.path.abspath(path))
    ANIMS = os.path.join(base, CFG["clips_dir"])
    if CFG.get("agent_yaw_file"):
        spec = importlib.util.spec_from_file_location("agent_yaw", os.path.join(base, CFG["agent_yaw_file"]))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        AGENT_YAW = mod.AGENT_YAW
    CFG["_base"] = base


def find_blend(character):
    hits = glob.glob(os.path.join(CFG["_base"], CFG["model_glob"].replace("{character}", character)))
    if not hits:
        sys.exit(f"no model for {character} matching {CFG['model_glob']}")
    return hits[0]


def relative_scale(pose_bone, rig, world):
    """The bone's own keyed scale. The Ophan's file keys its Core bone at 48.8 times (probably the FBX unit,
    not the motion), so a scale above 5 is drawn as 1 and counted in SCALE_CLAMPED."""
    s = pose_bone.scale.copy()
    if any(c > 5 for c in s):
        SCALE_CLAMPED[pose_bone.name] = SCALE_CLAMPED.get(pose_bone.name, 0) + 1
        return Vector((1, 1, 1))
    return s


SCALE_CLAMPED = {}

def parents_first(rig):
    order = []

    def walk(bone):
        order.append(bone.name)
        for child in bone.children:
            walk(child)

    for bone in rig.data.bones:
        if bone.parent is None:
            walk(bone)
    return order


def leg_length(rig, names=("UpperLeg.L", "LowerLeg.L")):
    """Summed length of the named bones in world space (the legs by default, which do not change when a rest pose is posed)."""
    world = rig.matrix_world
    total = 0.0
    for name in names:
        bone = rig.data.bones[name]
        total += ((world @ bone.tail_local) - (world @ bone.head_local)).length
    return total


def set_up_scene(model, mesh_objects, tile):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = scene.render.resolution_y = tile
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "TEXTURE"
    scene.display.shading.show_shadows = False
    if scene.world is None:
        scene.world = bpy.data.worlds.new("w")
    scene.world.color = (0.55, 0.57, 0.6)
    # Floor strip so feet sliding and sinking read from the side.
    floor = bpy.data.objects.new("floor", bpy.data.meshes.new("floor"))
    floor.data.from_pydata([(-1.5, -1.5, -0.01), (1.5, -1.5, -0.01), (1.5, 1.5, -0.01), (-1.5, 1.5, -0.01)], [], [(0, 1, 2, 3)])
    scene.collection.objects.link(floor)
    mat = bpy.data.materials.new("floor")
    mat.diffuse_color = (0.42, 0.44, 0.42, 1)
    floor.data.materials.append(mat)
    cam_data = bpy.data.cameras.new("cam")
    cam_data.type = "ORTHO"
    cam = bpy.data.objects.new("cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    return floor, cam


def forward_of(rig):
    bone = rig.data.bones.get("Foot.L")
    if bone is not None:
        v = rig.matrix_world.to_3x3() @ (bone.tail_local - bone.head_local)
        v.z = 0
        if v.length > 1e-4:
            return v.normalized()
    return Vector((0, -1, 0))


def aim(cam, centre, direction, up_hint, distance):
    """Place the camera `distance` from `centre` along `direction`, looking at it; `up_hint` is the image's up."""
    cam.location = centre + direction * distance
    look = (centre - cam.location).normalized()
    right = look.cross(up_hint if up_hint is not None else Vector((0, 0, 1))).normalized()
    up = right.cross(look)
    cam.matrix_world = Matrix(((right.x, up.x, -look.x, cam.location.x),
                               (right.y, up.y, -look.y, cam.location.y),
                               (right.z, up.z, -look.z, cam.location.z),
                               (0, 0, 0, 1)))


def render_tile(path):
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    with Image.open(path) as im:
        return im.convert("RGB")


def clip_actions(fbx):
    before_objects, before_actions = set(bpy.data.objects), set(bpy.data.actions)
    bpy.ops.import_scene.fbx(filepath=fbx)
    source = next(o for o in bpy.data.objects if o not in before_objects and o.type == "ARMATURE")
    actions = [a for a in bpy.data.actions if a not in before_actions]
    return source, actions


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", required=True)
    parser.add_argument("character")
    parser.add_argument("--out", required=True)
    parser.add_argument("--tile", type=int, default=160)
    parser.add_argument("--only", nargs="*", default=None)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
    load_config(args.config)
    entry = CFG["characters"].get(args.character)
    if entry is None:
        sys.exit(f"unknown character {args.character}; known: {', '.join(CFG['characters'])}")
    files = ([] if entry.get("no_base") else CFG.get("base_clips", [])) + entry.get("clips", [])
    if not files:
        sys.exit(f"{args.character} has no clip files")

    bpy.ops.wm.open_mainfile(filepath=find_blend(args.character))
    model = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    floor, cam = set_up_scene(model, meshes, VIDEO_SIZE)
    for pb in model.pose.bones:
        pb.rotation_mode = "QUATERNION"
    order = parents_first(model)
    height = max(o.dimensions.z for o in meshes) or 1.8
    forward = forward_of(model)
    side = Vector((-forward.y, forward.x, 0))
    distance = max(8.0, height * 3)    # a giant must not swallow the camera
    ortho = height * 1.3
    cam.data.ortho_scale = ortho
    cam.data.clip_end = 100
    tmp = tempfile.mkdtemp(prefix="angle_")
    tmp_png = os.path.join(tmp, "t.png")
    index = []          # one entry per clip: its video and its sheet strips
    started = time.time()
    base_yaw = model.rotation_euler.z

    for name in files:
        path = os.path.join(ANIMS, name)
        source, actions = clip_actions(path)
        source_world, model_world = source.matrix_world.copy(), model.matrix_world.copy()
        source_origin, model_origin = source_world.to_translation(), model_world.to_translation()
        legs = ("UpperLeg.L", "LowerLeg.L")
        if not all(b in model.data.bones and b in source.data.bones for b in legs):
            legs = [b.name for b in model.data.bones if b.name in source.data.bones]    # a rig without legs: every shared bone
        scale = leg_length(model, legs) / leg_length(source, legs)
        model_rotation = model_world.to_quaternion()
        shared = [b for b in order if b in source.pose.bones]
        for action in sorted(actions, key=lambda a: a.name):
            clip = action.name.split("|")[-1]
            if args.only and clip not in args.only:
                continue
            source.animation_data_create()
            source.animation_data.action = action
            if action.slots:
                source.animation_data.action_slot = action.slots[0]
            start, end = (int(round(f)) for f in action.frame_range)
            hips_bone = order[0] if "Hips" not in model.pose.bones else "Hips"

            def pose_frame(frame):
                """Copy the clip's pose for `frame` onto the model and apply the agent's turn; returns the hips in the world."""
                bpy.context.scene.frame_set(frame)
                for bone in shared:
                    spb = source.pose.bones[bone]
                    world = source_world @ spb.matrix
                    position = model_origin + (world.to_translation() - source_origin) * scale
                    rotation = model_rotation.inverted() @ world.to_quaternion()
                    model.pose.bones[bone].matrix = Matrix.LocRotScale(model_world.inverted() @ position, rotation, relative_scale(spb, source, source_world))
                    bpy.context.view_layer.update()
                turn = AGENT_YAW[clip]((frame - start) / FPS) if clip in AGENT_YAW else 0.0
                model.rotation_euler.z = base_yaw + math.radians(turn)
                bpy.context.view_layer.update()
                return model.matrix_world @ model.pose.bones[hips_bone].head

            def show(visible):
                for m in meshes:
                    m.hide_viewport = not visible

            # Pass 1: how far the body reaches over the whole clip, so every frame of it is framed the same way
            # (a halberd, a body lying down and a standing man each fit, and the tiles of one clip stay comparable).
            reach, low, high = 0.0, 0.0, height
            for frame in range(start, end + 1):
                hips = pose_frame(frame)
                show(True)
                bpy.context.view_layer.update()
                depsgraph = bpy.context.evaluated_depsgraph_get()
                for m in meshes:
                    evaluated = m.evaluated_get(depsgraph)
                    for corner in evaluated.bound_box:
                        w = evaluated.matrix_world @ Vector(corner)
                        reach = max(reach, math.hypot(w.x - hips.x, w.y - hips.y))
                        low, high = min(low, w.z), max(high, w.z)
                show(False)
            mid = (low + high) / 2
            body_ortho = max(2 * max(high - mid, reach) * 1.08, height * 0.9)
            top_ortho = max(2 * reach * 1.12, height * 0.4)

            # Pass 2: draw each frame from the four angles at video size, keep a small copy for the sheet.
            clip_dir = f"{len(index) + 1:02d}_{clip}"
            video_rel = f"videos/{args.character}/{clip_dir}.mp4"
            video = start_video(os.path.join(args.out, video_rel))
            frames = []
            for frame in range(start, end + 1):
                hips = pose_frame(frame)
                show(True)
                centre = Vector((hips.x, hips.y, mid))
                floor.location = Vector((hips.x, hips.y, 0))
                big = []
                for angle in ANGLES:
                    cam.data.ortho_scale = top_ortho if angle == "top" else body_ortho
                    if angle == "front":
                        aim(cam, centre, forward, None, distance)
                    elif angle == "side":
                        aim(cam, centre, side, None, distance)
                    elif angle == "three-quarter":
                        d = (forward * math.cos(math.radians(40)) + side * math.sin(math.radians(40)))
                        aim(cam, centre, (d + Vector((0, 0, 0.35))).normalized(), None, distance)
                    else:
                        aim(cam, Vector((hips.x, hips.y, 0)), Vector((0, 0, 1)), forward, distance)
                    big.append(render_tile(tmp_png))
                show(False)
                number, total = frame - start + 1, end - start + 1
                video.stdin.write(video_frame(big, clip, number, total).tobytes())
                frames.append((number, [im.resize((args.tile, args.tile), Image.LANCZOS) for im in big]))
            video.stdin.close()
            video.wait()
            strips = write_strips(args, clip_dir, clip, frames)
            index.append({"clip": clip, "frames": len(frames), "fps": FPS, "video": video_rel, "strips": strips})
            print(f"{args.character} {clip}: {len(frames)} frames ({time.time() - started:.0f}s)", flush=True)
        bpy.data.objects.remove(source)

    if SCALE_CLAMPED:
        print(f"NOTE {args.character}: scale above 5 drawn as 1 on {SCALE_CLAMPED}", flush=True)
    with open(os.path.join(args.out, f"{args.character}.json"), "w", encoding="utf-8") as fh:
        json.dump({"character": args.character, "tile": args.tile, "columns": COLUMNS, "rows": ROWS, "clips": index}, fh, indent=1)
    print(f"RESULT {args.character}: {sum(c['frames'] for c in index)} frames, {len(index)} clips, {len(index)} videos -> {args.out}", flush=True)


def font(size, bold=True):
    for name in ("arialbd.ttf" if bold else "arial.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def start_video(path):
    """An ffmpeg process that takes raw RGB frames on stdin and writes a looping-friendly H.264 file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{VIDEO_SIZE * 2}x{VIDEO_SIZE * 2 + 36}",
         "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23", "-preset", "veryfast",
         "-movflags", "+faststart", path], stdin=subprocess.PIPE)


def video_frame(big, clip, number, total):
    """The four views as a 2 x 2 picture with a labelled bar: front | three-quarter over side | top."""
    frame = Image.new("RGB", (VIDEO_SIZE * 2, VIDEO_SIZE * 2 + 36), (24, 24, 26))
    draw = ImageDraw.Draw(frame)
    for i, (name, im) in enumerate(zip(ANGLES, big)):
        x, y = (i % 2) * VIDEO_SIZE, (i // 2) * VIDEO_SIZE
        frame.paste(im, (x, y))
        draw.text((x + 6, y + VIDEO_SIZE - 24), name, fill=(255, 255, 255), font=font(18), stroke_width=2, stroke_fill=(0, 0, 0))
    draw.text((8, VIDEO_SIZE * 2 + 5), f"{clip}   frame {number} of {total}", fill=(255, 220, 90), font=font(22))
    return frame


def write_strips(args, clip_dir, clip, frames):
    """One JPEG per band of ROWS x COLUMNS frames; frames run down a column, then on to the column to its right."""
    tile, gap = args.tile, 8
    cell_w, head = tile * 4 + gap, 46
    per_band, strips = COLUMNS * ROWS, []
    small, label = font(15), font(max(22, tile // 5))
    for band in range(-(-len(frames) // per_band)):
        chunk = frames[band * per_band:(band + 1) * per_band]
        rows = min(ROWS, len(chunk))
        image = Image.new("RGB", (cell_w * COLUMNS, head + rows * tile), (24, 24, 26))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, image.width, head - 2), fill=(70, 55, 20))
        draw.text((8, 3), f"{args.character}  {clip}   frames {chunk[0][0]} to {chunk[-1][0]} of {len(frames)}   "
                          f"(read each column top to bottom, then the next column to the right)", fill="white", font=font(17))
        for column in range(-(-len(chunk) // rows)):
            for v, name in enumerate(ANGLES):
                draw.text((column * cell_w + v * tile + 6, 26), name, fill=(255, 230, 150), font=small)
        for i, (number, tiles) in enumerate(chunk):
            x, y = (i // rows) * cell_w, head + (i % rows) * tile
            for v, im in enumerate(tiles):
                image.paste(im, (x + v * tile, y))
            tag = str(number)
            box = draw.textbbox((0, 0), tag, font=label)
            draw.rectangle((x + 2, y + 2, x + 10 + box[2], y + 8 + box[3]), fill=(0, 0, 0))
            draw.text((x + 6, y + 3), tag, fill=(255, 220, 60), font=label)
            draw.line((x + cell_w - gap // 2, y, x + cell_w - gap // 2, y + tile), fill=(200, 60, 60), width=3)
            draw.line((x, y + tile - 1, x + cell_w - gap, y + tile - 1), fill=(60, 60, 64))
        rel = f"strips/{args.character}/{clip_dir}_{band + 1}.jpg"
        os.makedirs(os.path.join(args.out, os.path.dirname(rel)), exist_ok=True)
        image.save(os.path.join(args.out, rel), quality=86)
        strips.append(rel)
    return strips


if __name__ == "__main__":
    main()