"""Isolated driver acting pilot. No existing vehicle/road inputs are modified.

Procedural geometry authored here: no downloaded human model or paid API.
Silent 3-second action proof, not a narration-aligned final film.
Run only on GitHub Actions standard runners.

Idle motion (chest breathing + three blinks placed inside the pre-notice,
inter-notice/turn, and post-turn holds) keeps those holds from being a
frozen still, without touching the notice/turn reaction timing itself or
the camera framing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path


def main():
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("driver rendering is restricted to GitHub Actions")
    import bpy
    from mathutils import Vector

    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, default=90)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    assert 1 <= args.start <= args.end <= 90
    args.out.mkdir(parents=True, exist_ok=False)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    def material(name, color, roughness=.65):
        m = bpy.data.materials.new(name)
        m.diffuse_color = (*color, 1)
        m.use_nodes = True
        bsdf = m.node_tree.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = (*color, 1)
        bsdf.inputs["Roughness"].default_value = roughness
        return m

    skin = material("skin", (.52, .28, .15))
    shirt = material("shirt", (.035, .28, .47))
    dark = material("rubber", (.018, .025, .035))
    white = material("eyes", (.90, .94, .97))
    seat_mat = material("seat", (.055, .085, .12))
    cabin_mat = material("cabin", (.16, .20, .25))
    bg = material("background", (.08, .13, .18))

    def ball(name, location, scale, mat, parent=None):
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=24, ring_count=12, radius=1, location=location)
        ob = bpy.context.object
        ob.name = name
        ob.scale = scale
        ob.data.materials.append(mat)
        for poly in ob.data.polygons:
            poly.use_smooth = True
        if parent:
            ob.parent = parent
        return ob

    def box(name, location, scale, mat):
        bpy.ops.mesh.primitive_cube_add(size=1, location=location)
        ob = bpy.context.object
        ob.name = name
        ob.dimensions = scale
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        bevel = ob.modifiers.new("soft edges", "BEVEL")
        bevel.width, bevel.segments = .04, 3
        ob.modifiers.new("normals", "WEIGHTED_NORMAL")
        ob.data.materials.append(mat)
        return ob

    def empty(name, location):
        ob = bpy.data.objects.new(name, None)
        bpy.context.collection.objects.link(ob)
        ob.location = location
        return ob

    def limb(name, a, b, radius, mat):
        ob = ball(name, (0, 0, 0), (radius, radius, 1), mat)
        set_limb(ob, a, b, radius)
        return ob

    def set_limb(ob, a, b, radius):
        a, b = Vector(a), Vector(b)
        ob.location = (a + b) / 2
        ob.scale = (radius, radius, (b - a).length / 2 + radius * .3)
        ob.rotation_euler = (b - a).to_track_quat("Z", "Y").to_euler()

    box("seat back", (0, .24, .95), (.86, .23, 1.20), seat_mat)
    box("headrest", (0, .24, 1.72), (.60, .23, .45), seat_mat)
    box("seat cushion", (0, -.10, .39), (.85, .85, .20), seat_mat)
    torso = ball("torso", (0, 0, .99), (.37, .23, .49), shirt)
    ball("neck", (0, -.015, 1.44), (.12, .12, .17), skin)
    head = empty("acting head", (0, -.02, 1.73))
    ball("head", (0, 0, 0), (.255, .23, .32), skin, head)
    ball("hair", (0, .035, .20), (.26, .23, .15), dark, head)
    ball("nose", (0, -.24, -.015), (.045, .075, .055), skin, head)
    eyes, brows = [], []
    for side in (-1, 1):
        eye = ball("eye", (side * .095, -.213, .065), (.064, .035, .044), white, head)
        eyes.append(eye)
        ball("pupil", (side * .095, -.247, .065), (.025, .014, .027), dark, head)
        brows.append(ball("brow", (side * .095, -.215, .139),
                          (.073, .022, .015), dark, head))
    mouth = ball("mouth", (0, -.218, -.13), (.065, .018, .012), dark, head)
    for side in (-1, 1):
        ball("ear", (side * .25, .015, -.005), (.045, .075, .085), skin, head)
    wheel = empty("steering assembly", (0, -.67, 1.06))
    bpy.ops.mesh.primitive_torus_add(
        major_radius=.31, minor_radius=.027, major_segments=64, minor_segments=12)
    ring = bpy.context.object
    ring.name = "steering rim"
    ring.parent = wheel
    ring.location = (0, 0, 0)
    ring.rotation_euler.x = math.pi / 2
    ring.data.materials.append(dark)
    ball("hub", (0, 0, 0), (.085, .035, .085), cabin_mat, wheel)
    for side in (-1, 1):
        spoke = ball("spoke", (side * .15, 0, 0), (.16, .018, .021), cabin_mat, wheel)
        spoke.name = "wheel spoke"
    hands = []
    arms = []
    for side in (-1, 1):
        hands.append(ball("hand", (side * .31, -.012, .025),
                          (.068, .055, .087), skin, wheel))
        shoulder = (side * .31, -.02, 1.21)
        elbow = (side * .43, -.30, .94)
        arms.append((side, limb("upper arm", shoulder, elbow, .085, shirt),
                     limb("forearm", elbow, (side * .31, -.67, 1.085), .065, skin)))
    box("dashboard", (0, -.94, .64), (1.65, .38, .27), cabin_mat)
    box("left pillar", (-.87, -.45, 1.35), (.10, .18, 1.70), cabin_mat)
    box("right pillar", (.87, -.45, 1.35), (.10, .18, 1.70), cabin_mat)
    box("rear cabin", (0, .65, 1.05), (2.05, .08, 2.30), bg)
    # A fixed front passenger/hood viewpoint; no camera movement to fake action.
    bpy.ops.object.camera_add(location=(2.45, -5.7, 2.75))
    camera = bpy.context.object
    camera.rotation_euler = (Vector((0, -.15, 1.16)) - camera.location).to_track_quat(
        "-Z", "Y").to_euler()
    camera.data.type, camera.data.ortho_scale = "ORTHO", 2.75
    scene = bpy.context.scene
    scene.camera = camera
    for location, power, size in [((0, -3, 4), 400, 4), ((-3, -1, 2), 180, 3)]:
        bpy.ops.object.light_add(type="AREA", location=location)
        light = bpy.context.object
        light.data.energy, light.data.shape, light.data.size = power, "DISK", size
        light.rotation_euler = (Vector((0, 0, 1)) - light.location).to_track_quat(
            "-Z", "Y").to_euler()
    scene.world.color = (.15, .15, .15)
    scene.render.engine = "CYCLES"
    scene.cycles.device, scene.cycles.samples, scene.cycles.seed = "CPU", 32, 19
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = 1080, 1920
    scene.render.resolution_percentage, scene.render.fps = 100, 30
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "AgX"
    # Idle motion so the pre-notice, inter-notice/turn, and post-turn holds
    # are not a frozen still: a continuous chest-breathing cycle plus three
    # short blinks placed to sit entirely inside those holds (never
    # overlapping the notice [.65-1.05s] or turn [1.65-2.40s] ramps above),
    # so the already-correct reaction/turn timing is untouched.
    BLINK_CENTERS = (.30, 1.30, 2.70)
    BLINK_HALF_WIDTH = .09

    def blink_amount(t):
        amt = 0.0
        for center in BLINK_CENTERS:
            d = abs(t - center)
            if d < BLINK_HALF_WIDTH:
                amt = max(amt, 1 - d / BLINK_HALF_WIDTH)
        return amt

    poses = []
    for frame in range(args.start, args.end + 1):
        t = (frame - 1) / 30
        notice = max(0, min(1, (t - .65) / .40))
        turn = max(0, min(1, (t - 1.65) / .75))
        smooth_turn = turn * turn * (3 - 2 * turn)
        breathing = math.sin(2 * math.pi * t / 2.6)
        blink = blink_amount(t)
        head.rotation_euler.x = .28 * (1 - notice)
        head.rotation_euler.z = -.10 * (1 - notice)
        head.location.z = 1.73 + .025 * math.sin(math.pi * notice) + .010 * math.sin(t * 4)
        torso.scale.y = .23 * (1 + .035 * breathing)
        wheel.rotation_euler.y = -.35 * smooth_turn
        for eye, brow in zip(eyes, brows):
            eye.scale.z = (.044 + .018 * notice) * (1 - .85 * blink)
            brow.location.z = .139 + .035 * notice
        mouth.scale.z = .012 + .030 * math.sin(math.pi * notice)
        bpy.context.view_layer.update()
        for (side, upper, fore), hand in zip(arms, hands):
            shoulder = (side * .31, -.02, 1.21)
            hand_world = hand.matrix_world.translation
            elbow = (side * .43, -.30, .94 + side * .05 * smooth_turn)
            set_limb(upper, shoulder, elbow, .085)
            set_limb(fore, elbow, hand_world, .065)
        scene.frame_set(frame)
        scene.render.filepath = str(args.out / f"{frame:04d}.png")
        bpy.ops.render.render(write_still=True)
        poses.append({"frame": frame, "notice": notice,
                      "steering_radians": wheel.rotation_euler.y,
                      "breathing": breathing, "blink": blink})
    bpy.ops.wm.save_as_mainfile(filepath=str(args.out / "driver-pilot.blend"))
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(args.out.glob("*.png"))}
    count = args.end - args.start + 1
    assert len(hashes) == count and len(set(hashes.values())) == count
    receipt = {"status": "RENDERED_REVIEW_REQUIRED", "is_final": False,
               "silent": True, "narration_alignment": "NOT_YET_APPLIED",
               "human_review": "UNVERIFIED", "editorial_status": "REVIEW_REQUIRED",
               "renderer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "blender": bpy.app.version_string, "samples": 32,
               "resolution": [1080, 1920], "fps": 30, "frame_count": count,
               "frame_numbers": list(range(args.start, args.end + 1)),
               "geometry_source": "procedural authoring in this script",
               "poses": poses, "png_sha256": hashes}
    (args.out / "driver-pilot.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
