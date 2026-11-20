"""EP.11 speed: 100 % 3D renderer (Blender, Cycles CPU). The CC0 sedan with the stylised driver hits a concrete wall at 30 or 40 mph; its
nose is crushed per frame with the EP.04 crush map (rails fold like an accordion in the x-ray shots, front wheels pushed back, cabin never
moves). Drop site: the same car falls nose first from the equivalent height next to a building. Braking road: the same car brakes from the
same hazard line, a cone marks where the 30 mph car stops. Everything that moves comes from speed_motion. No scene text."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from benchmarks.airbag import human  # noqa: E402
from benchmarks.belt_limiter import render_belt_3d as rb  # noqa: E402
from benchmarks.crumple_zone import crumple_motion as cm  # noqa: E402
from benchmarks.crumple_zone import structure_geometry as sg  # noqa: E402
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402
from benchmarks.speed_energy import speed_motion as sm  # noqa: E402
from benchmarks.speed_energy import speed_timeline as tl  # noqa: E402

material, cube = base.material, base.cube
FRAME, HALF = (1080, 1920), (1080, 960)
DROP_X = 900.0                 # drop site (world x), far outside every wall/brake shot
BRAKE_Y = -420.0               # hazard line of the braking road (world y)
STOREY = sm.STOREY_M


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


def build_world():
    road = material("Asphalt", (0.07, 0.07, 0.075), rough=0.85)
    base.asphalt_grain(road)
    paint = material("Line paint", (0.85, 0.85, 0.82), rough=0.6)
    grass = material("Verge", (0.10, 0.16, 0.06), rough=0.95)
    cube("Road", (0, -260, -0.05), (9.0, 540, 0.1), road)
    cube("Verge right", (34.5, -260, -0.06), (60, 540, 0.1), grass)
    cube("Verge left", (-34.5, -260, -0.06), (60, 540, 0.1), grass)
    for sx in (-1, 1):
        cube(f"Edge line {sx}", (sx * 4.2, -260, 0.002), (0.15, 540, 0.004), paint)
    concrete = material("Wall concrete", (0.20, 0.20, 0.19), rough=0.9)
    cube("Wall", (0, 0.75, 1.1), (9.0, 1.5, 2.2), concrete)                       # front face at y = 0
    stripe = material("Wall stripe", (0.9, 0.62, 0.05), rough=0.5)
    dark = material("Wall stripe dark", (0.05, 0.05, 0.05), rough=0.6)
    for k in range(9):
        cube(f"Wall chevron {k}", (-4.0 + k, -0.004, 1.65), (0.5, 0.008, 0.36), stripe if k % 2 == 0 else dark)
    # braking road: a cone where the 30 mph car comes to rest
    cone = material("Cone", (0.95, 0.32, 0.03), rough=0.5)
    white = material("Cone band", (0.92, 0.92, 0.9), rough=0.5)
    cy = BRAKE_Y + sm.stop_distance("slow")
    for dx in (2.2, -2.2):
        bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=0.2, radius2=0.03, depth=0.75, location=(dx, cy, 0.375))
        bpy.context.object.data.materials.append(cone)
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.115, depth=0.08, location=(dx, cy, 0.45))
        bpy.context.object.data.materials.append(white)
        cube(f"Cone base {dx}", (dx, cy, 0.02), (0.46, 0.46, 0.04), material("Cone base", (0.05, 0.05, 0.05), rough=0.7))
    cube("Hazard line", (0, cy, 0.003), (8.0, 0.25, 0.006), paint)
    # drop site: ground pad and a building with a floor line every storey
    yard = material("Yard concrete", (0.25, 0.25, 0.24), rough=0.9)
    cube("Drop yard", (DROP_X, 0, -0.05), (40, 40, 0.1), yard)
    wall_m = material("Building wall", (0.55, 0.50, 0.44), rough=0.85)
    slab = material("Building slab", (0.82, 0.80, 0.76), rough=0.7)
    glass = material("Building glass", (0.10, 0.16, 0.22), metal=0.2, rough=0.08)
    floors = 6
    cube("Building", (DROP_X, 6.0, floors * STOREY / 2), (16.0, 6.0, floors * STOREY), wall_m)
    for k in range(1, floors + 1):
        cube(f"Building slab {k}", (DROP_X, 2.95, k * STOREY - 0.15), (16.4, 0.12, 0.3), slab)
        for j in range(-3, 4):
            cube(f"Window {k} {j}", (DROP_X + j * 2.2, 2.97, (k - 1) * STOREY + 1.55), (1.3, 0.06, 1.5), glass)


def set_tail(mat, on):
    if mat is None:
        return
    s = mat.node_tree.nodes.get("Principled BSDF")
    s.inputs["Emission Color"].default_value = (1.0, 0.05, 0.03, 1)
    s.inputs["Emission Strength"].default_value = 40.0 if on else 0.0


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
    sun_to = cinematic.sun_vector((-0.5, -0.8), 36.0)
    cinematic.apply_sky(scene, sun_to, strength=0.25, dust=0.6)
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    sun.data.energy, sun.data.angle = 3.3, 0.04
    sun.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()
    build_world()
    nose, car_len, wheel_r = geom["nose"], geom["nose"] + geom["tail"], geom["tyre_radius"]
    cabin_y = nose - cm.CRUSH_LENGTH
    tail_mat = next((m for m in bpy.data.materials if m.name.startswith("tail")), None)
    wheel_nodes = {w["node"] for w in wheels.values()}
    parts = [o for o in root.children_recursive if o.type == "MESH" and not any(p in wheel_nodes for p in rb._ancestors(o))]
    bpy.context.view_layer.update()
    deformables = [rb.Deformable(o, nose) for o in parts]
    rail_mat = material("Crush rail", (1.0, 0.45, 0.05), rough=0.4, emission=5.0)
    structure = []
    for name, it in sg.structure(nose).items():
        if it["deforms"]:
            ob, _ = rb.tube(name, it["p0"], it["p1"], it["radius"], rail_mat, root, n_seg=it["n_seg"])
            structure.append(ob)
    structure_def = [rb.Deformable(ob, nose, local_is_car_frame=True, mapper=cm.rail_fold) for ob in structure]
    ghost = rb.Ghost(parts)
    ghost.set_tint((0.45, 0.8, 1.7))          # blue paint, as in EP.04's second car
    interior = rb.build_interior(root)
    driver = human.Human(root)
    driver_objs = [o for o in root.children_recursive if o.name.startswith("Driver")]
    wheel_objs = [o for w in wheels.values() for o in [w["node"], *w["node"].children_recursive]]
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    s_max = sm.crush_m("fast")

    def render(sh, kind, path, size):
        scene.render.resolution_x, scene.render.resolution_y = round(size[0] * args.res_scale), round(size[1] * args.res_scale)
        t = sh["t"]
        braking = False
        if sh.get("brake"):
            bs = sm.brake_state(kind, t)
            s, v, travel = 0.0, bs["v"], bs["x"]
            braking = bs["braking"]
            root.rotation_euler = (0.0, 0.0, 0.0)
            root.location = (0.0, BRAKE_Y + bs["x"] - nose, 0.0)
            body.rotation_euler = (-0.02 if braking and v > 0.3 else 0.0, 0, 0)
            drop_h = None
        elif sh.get("drop"):
            if t < 0:
                tt = max(t, -tl.T_FALL[kind])
                hgt = -sm.v0(kind) * tt - 0.5 * sm.G * tt * tt
                s, v = 0.0, sm.v0(kind) + sm.G * tt
            else:
                cs = sm.crash_state(kind, t)
                hgt, s, v = 0.0, cs["s"], cs["v"]
            travel = 0.0
            root.rotation_euler = (-math.pi / 2, 0.0, math.pi)      # nose straight down, roof towards the camera
            root.location = (DROP_X, 0.0, nose + hgt - s)
            body.rotation_euler = (0, 0, 0)
            drop_h = hgt
        else:
            cs = sm.crash_state(kind, t)
            s, v, travel = cs["s"], cs["v"], cs["y"]
            root.rotation_euler = (0.0, 0.0, 0.0)
            root.location = (0.0, cs["y"] - nose, 0.0)
            body.rotation_euler = (0, 0, 0)
            drop_h = None
        for dm in deformables:
            dm.apply(s, nose)
        for dm in structure_def:
            dm.apply(s, nose)
        for key, wh in wheels.items():
            y_new = cm.wheel_y(float(wh["base"].y), s, nose, wheel_r) if key.startswith("front") else float(wh["base"].y)
            wh["node"].location = (wh["base"].x, y_new, wh["base"].z)
            wh["node"].rotation_mode = "ZXY"
            wh["node"].rotation_euler = (-travel / wheel_r, 0, 0)
        set_tail(tail_mat, braking)
        xf = float(sh.get("xray", 0.0))
        if xf > 0.0:
            ghost.set_factor(xf, root.location.y + nose, car_len, root.location.y + cabin_y + 0.04)
        else:
            ghost.set_factor(0.0, 1e4, car_len)
        inside = bool(sh.get("interior"))
        for ob in parts + wheel_objs:
            if ob.name.startswith("Driver") or ob in interior:
                continue
            ob.hide_render = inside
        for ob in structure:
            ob.hide_render = inside or xf <= 0.02
        for ob in interior:
            ob.hide_render = not inside
        for ob in driver_objs:
            ob.hide_render = False
        lurch = min(1.0, s / s_max) if t > 0 else 0.0                # the body keeps going while the cabin stops (belted: leans into the belt)
        hx, hy, hz = driver.HIP
        driver.pivot.location = (hx, hy + 0.10 * lurch, hz)
        driver.pivot.rotation_euler = (-0.55 * lurch * (sm.v0(kind) / sm.v0("fast")), 0.0, 0.0)
        driver.neck.rotation_euler = (-0.35 * lurch * (sm.v0(kind) / sm.v0("fast")), 0.0, 0.0)
        c = sh["cam"]
        if c["rel"] == "car":
            o = Vector(root.location)
        elif c["rel"] == "drop":
            o = Vector((DROP_X, 0.0, 0.0))
        elif c["rel"] == "brake":
            o = Vector((0.0, BRAKE_Y, 0.0))
        else:
            o = Vector((0.0, 0.0, 0.0))
        dd = cam.data
        dd.sensor_fit, dd.sensor_width, dd.lens, dd.clip_start = "HORIZONTAL", 36.0, c["lens"], 0.02
        base.set_camera(cam, o + Vector(c["loc"]), o + Vector(c["target"]))
        bpy.context.view_layer.update()
        scene.render.filepath = str(path)
        marks = None
        if sh.get("ruler"):          # where the wall face and the front of the cabin are in the picture (assembly draws the 'crumple zone left' bracket)
            def px(p):
                co = world_to_camera_view(scene, cam, Vector(p))
                return [round(co.x, 4), round(1.0 - co.y, 4)]
            marks = {"wall": px((-0.85, 0.0, 1.0)), "cabin": px((-0.85, root.location.y + cabin_y, 1.0)), "zone_left_cm": round(100 * (root.location.y + cabin_y) * -1, 1)}
        bpy.ops.render.render(write_still=True)
        return {"marks": marks, "variant": kind, "t": round(t, 5), "mph": round(v / sm.MPH, 2), "crush_cm": round(100 * s, 2), "travel_m": round(travel, 3),
                "root": [round(x, 3) for x in root.location], "xray": round(xf, 3), "braking": braking, "drop_h_m": None if drop_h is None else round(drop_h, 3),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    segs = tl.segments()
    a0, b0 = (int(x) for x in args.frames.split("-"))
    out = []
    for f in range(a0, b0 + 1):
        t0 = time.time()
        sh = tl.frame_state(f, segs)
        if sh.get("split"):
            prts = [render(sh, "slow", args.out / f"frame_{f:05d}_top.png", HALF), render(sh, "fast", args.out / f"frame_{f:05d}_bot.png", HALF)]
        else:
            prts = [render(sh, sh["variant"], args.out / f"frame_{f:05d}.png", FRAME)]
        info = {"frame": f, "segment": sh["segment"], "split": bool(sh.get("split")), "parts": prts, "render_seconds": round(time.time() - t0, 1)}
        out.append(info)
        print("SPEED_FRAME " + json.dumps(info), flush=True)
    (args.out / f"speed-frames-{a0:05d}.json").write_text(json.dumps({"renderer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "frames": out}, indent=1))


if __name__ == "__main__":
    main()
