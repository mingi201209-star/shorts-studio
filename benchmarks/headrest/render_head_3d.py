"""EP.12 headrest: 100 % 3D renderer (Blender, Cycles CPU). The CC0 sedan waits at a light with the stylised driver; a red copy of it
hits it from behind. Interior shots: the car body is hidden and the driver's door side is open, so the camera sees the driver from the side
in their own seat (seat back, cushion, headrest on two chrome posts). The head rotates on the neck by the angle from head_motion; the neck
turns from skin colour to red as it bends back. Headrest 'high' (top level with the head, 4 cm behind it) or 'low' (pushed down, top below
the head). No scene text."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from benchmarks.abs_brake import abs_parts as ap  # noqa: E402
from benchmarks.airbag import human  # noqa: E402
from benchmarks.belt_limiter import render_belt_3d as rb  # noqa: E402
from benchmarks.following.render_follow_3d import duplicate_car, set_tail  # noqa: E402
from benchmarks.headrest import head_motion as hm  # noqa: E402
from benchmarks.headrest import head_timeline as tl  # noqa: E402
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402

material, cube = base.material, base.cube
FRAME, HALF = (1080, 1920), (1080, 960)
SX = -0.36                                   # driver seat centre (car frame x)
HEAD_BACK_Y = -0.062                         # back of the hair at rest (car frame y)
HR_SIZE = (0.27, 0.10, 0.20)
HIGH = {"y": HEAD_BACK_Y - hm.BACKSET - HR_SIZE[1] / 2, "z": 1.19 - HR_SIZE[2] / 2}
LOW = {"y": -0.19 - HR_SIZE[1] / 2, "z": 0.94 - HR_SIZE[2] / 2}
STRIKE_V = 20 * hm.MPH                        # the car behind: equal mass, so the struck car gains 10 mph


def arguments():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--res-scale", type=float, default=0.5)
    p.add_argument("--samples", type=int, default=16)
    p.add_argument("--frames", default="0-0")
    p.add_argument("--film", action="store_true")
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return p.parse_args(argv)


def build_road():
    road = material("Asphalt", (0.07, 0.07, 0.075), rough=0.85)
    base.asphalt_grain(road)
    paint = material("Line paint", (0.85, 0.85, 0.82), rough=0.6)
    grass = material("Verge", (0.10, 0.16, 0.06), rough=0.95)
    cube("Road", (0, 0, -0.05), (9.0, 200, 0.1), road)
    cube("Verge right", (34.5, 0, -0.06), (60, 200, 0.1), grass)
    cube("Verge left", (-34.5, 0, -0.06), (60, 200, 0.1), grass)
    for sx in (-1, 1):
        cube(f"Edge line {sx}", (sx * 4.2, 0, 0.002), (0.15, 200, 0.004), paint)
    cube("Stop line", (0, 3.2, 0.003), (8.0, 0.4, 0.006), paint)
    pole = material("Signal pole", (0.12, 0.12, 0.13), metal=0.6, rough=0.4)
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.08, depth=4.2, location=(-4.8, 3.6, 2.1))
    bpy.context.object.data.materials.append(pole)
    cube("Signal head", (-4.8, 3.6, 4.0), (0.35, 0.3, 0.9), material("Signal box", (0.05, 0.05, 0.05), rough=0.5))
    lamp = material("Signal red", (1.0, 0.05, 0.03), rough=0.3, emission=12.0)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.11, location=(-4.8, 3.44, 4.25))
    bpy.context.object.data.materials.append(lamp)


class Seat:
    """Driver seat for the side shots: cushion, back (its front face touches the driver's back), headrest on two chrome posts."""

    def __init__(self, root):
        cloth = material("Seat cloth", (0.10, 0.11, 0.14), rough=0.85)
        foam = material("Headrest cloth", (0.13, 0.14, 0.18), rough=0.8)
        chrome = material("Headrest post", (0.8, 0.8, 0.82), metal=1.0, rough=0.2)
        self.objs = [ap.rounded_box("Seat cushion", (SX, 0.05, 0.31), (0.50, 0.55, 0.13), cloth, root, bevel=0.035),
                     ap.rounded_box("Seat back", (SX, -0.11, 0.63), (0.50, 0.14, 0.52), cloth, root, bevel=0.04)]
        self.hr = bpy.data.objects.new("Headrest", None)
        bpy.context.collection.objects.link(self.hr)
        self.hr.parent = root
        self.objs.append(ap.rounded_box("Headrest pad", (0, 0, 0), HR_SIZE, foam, self.hr, bevel=0.03))
        self.posts = []
        for dx in (-0.08, 0.08):
            bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.007, depth=0.40, location=(0, 0, 0))
            ob = bpy.context.object
            ob.name = f"Headrest post {dx}"
            ob.data.materials.append(chrome)
            ob.parent = self.hr
            ob.location = (dx, 0.01, -0.20)
            self.posts.append(ob)
            self.objs.append(ob)

    def set(self, height: float, close: float):
        """height 0 = low, 1 = high; close 0 = low's backset, 1 = the 4 cm backset."""
        z = LOW["z"] + (HIGH["z"] - LOW["z"]) * height
        y = LOW["y"] + (HIGH["y"] - LOW["y"]) * close
        self.hr.location = (SX, y, z)

    def show(self, on):
        for ob in self.objs:
            ob.hide_render = not on


def main():
    args = arguments()
    args.out.mkdir(parents=True, exist_ok=True)
    root, body, wheels, geom = base.load_source_car(args.source)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.exposure = -1.3
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    sun_to = cinematic.sun_vector((-0.6, -0.7), 30.0)
    cinematic.apply_sky(scene, sun_to, strength=0.25, dust=0.7)
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    sun.data.energy, sun.data.angle = 3.2, 0.04
    sun.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()
    build_road()
    tail_mat = next((m for m in bpy.data.materials if m.name.startswith("tail")), None)
    lead_root, lead_body, lead_wheels, lead_tail = duplicate_car(root, wheels, (0.62, 0.05, 0.04))
    interior = rb.build_interior(root)
    hide_always = [o for o in interior if o.name.startswith(("Interior driver", "Interior passenger", "Interior door panel -1", "Interior B pillar -1", "Interior A pillar -1", "Interior roof header"))]
    interior = [o for o in interior if o not in hide_always]
    for o in hide_always:
        o.hide_render = True
    driver = human.Human(root)
    neck_ob = next(o for o in root.children_recursive if o.name.startswith("Driver neck") and o.type == "MESH")
    neck_mat = material("Driver neck tint", (0.80, 0.55, 0.42), rough=0.5)
    neck_ob.data.materials.clear()
    neck_ob.data.materials.append(neck_mat)
    neck_bsdf = neck_mat.node_tree.nodes.get("Principled BSDF")
    seat = Seat(root)
    bpy.ops.object.light_add(type="AREA", location=(0, 0, 0))
    key = bpy.context.object                   # soft key light from the open driver side, so the face and neck read in the side shots
    key.data.energy, key.data.size = 60.0, 0.8
    key.parent, key.location = root, (-1.3, 0.35, 1.35)
    key.rotation_euler = (0.0, math.radians(-65), 0.0)
    for lamp in [key] + [o for o in interior if o.type == "LIGHT"]:
        lamp.visible_camera = False             # the lamp panels themselves showed up as a black and white box at the roof edge
    wheel_nodes = {w["node"] for w in wheels.values()}
    body_objs = [o for o in root.children_recursive if o.type == "MESH" and not any(p in wheel_nodes for p in rb._ancestors(o))
                 and o not in interior and o not in hide_always and not o.name.startswith(("Driver", "Steering", "Seat", "Headrest"))]
    wheel_objs = [o for w in wheels.values() for o in [w["node"], *w["node"].children_recursive]]
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    nose, tail = geom["nose"], geom["tail"]
    skin = (0.80, 0.55, 0.42)

    def render(sh, kind, path, size):
        scene.render.resolution_x, scene.render.resolution_y = round(size[0] * args.res_scale), round(size[1] * args.res_scale)
        t = sh["t"]
        model = "low" if kind in ("low", "adjust") else kind
        st = hm.at(model, t)
        x = st["car_x"]
        root.location = (0.0, x, 0.0)
        for wh in wheels.values():
            wh["node"].rotation_mode = "ZXY"
            wh["node"].rotation_euler = (-x / geom["tyre_radius"], 0, 0)
        set_tail(tail_mat, True)                    # foot on the brake at the light
        exterior = bool(sh.get("exterior"))
        rx = STRIKE_V * t if t < 0 else x           # the car behind: closes in, then moves on with the struck car
        lead_root.location = (0.0, -tail - nose + rx, 0.0)
        lead_root.hide_render = False
        for ob in lead_root.children_recursive:
            ob.hide_render = not exterior
        for ob in body_objs + wheel_objs:
            ob.hide_render = not exterior
        for ob in interior:
            ob.hide_render = exterior
        seat.show(True)
        if kind == "adjust":
            s = sh["setting"]
            seat.set(s["height"], s["close"])
        else:
            seat.set(1.0, 1.0) if kind == "high" else seat.set(0.0, 0.0)
        lean = 0.06 * st["accel_g"] / (hm.A_PEAK / hm.G)       # the seat back pushes the torso: a small lean back into it during the pulse
        driver.pivot.rotation_euler = (lean, 0.0, 0.0)
        driver.neck.rotation_euler = (st["theta"], 0.0, 0.0)
        r = min(1.0, max(0.0, (st["deg"] - 10.0) / (hm.WHIPLASH_DEG + 15.0)))
        col = tuple(skin[i] + ((0.95, 0.08, 0.05)[i] - skin[i]) * r for i in range(3))
        neck_bsdf.inputs["Base Color"].default_value = (*col, 1.0)
        neck_bsdf.inputs["Emission Color"].default_value = (*col, 1.0)
        neck_bsdf.inputs["Emission Strength"].default_value = 1.2 * r
        c = sh["cam"]
        o = Vector(root.location) if c["rel"] == "car" else Vector((0.0, 0.0, 0.0))
        dd = cam.data
        dd.sensor_fit, dd.sensor_width, dd.lens, dd.clip_start = "HORIZONTAL", 36.0, c["lens"], 0.02
        base.set_camera(cam, o + Vector(c["loc"]), o + Vector(c["target"]))
        bpy.context.view_layer.update()
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        return {"variant": kind, "t": round(t, 5), "deg": round(st["deg"], 2), "car_x": round(x, 4), "car_mph": round(st["car_v"] / hm.MPH, 2),
                "caught": st["caught"], "headrest": [round(v, 4) for v in seat.hr.location], "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    segs = tl.segments()
    a0, b0 = (int(v) for v in args.frames.split("-"))
    out = []
    for f in range(a0, b0 + 1):
        t0 = time.time()
        sh = tl.frame_state(f, segs)
        if sh.get("split"):
            prts = [render(sh, "high", args.out / f"frame_{f:05d}_top.png", HALF), render(sh, "low", args.out / f"frame_{f:05d}_bot.png", HALF)]
        else:
            prts = [render(sh, sh["variant"], args.out / f"frame_{f:05d}.png", FRAME)]
        info = {"frame": f, "segment": sh["segment"], "split": bool(sh.get("split")), "parts": prts, "render_seconds": round(time.time() - t0, 1)}
        out.append(info)
        print("HEAD_FRAME " + json.dumps(info), flush=True)
    (args.out / f"head-frames-{a0:05d}.json").write_text(json.dumps({"renderer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "frames": out}, indent=1))


if __name__ == "__main__":
    main()
