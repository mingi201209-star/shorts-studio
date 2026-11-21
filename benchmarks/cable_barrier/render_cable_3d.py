"""EP.15 median cable barrier: 100 % 3D renderer (Blender, Cycles CPU), house style of EP.13/EP.14 (golden hour, red car, depth of
field). Divided highway with a grass median; three steel wire ropes on thin posts along its centre. The red CC0 sedan drifts off its
lanes across the median and into the ropes; the ropes are rebuilt every frame in the V shape the model gives (kink at the car's front
corner), the posts in the pushed stretch fold over, turf flies from the tyres, a blue car comes the other way on the far side.
World = model mirrored in x (the car's lanes are on the right of the median). Everything that moves comes from cable_motion. No text."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from benchmarks.belt_limiter import render_belt_3d as rb  # noqa: E402
from benchmarks.cable_barrier import cable_motion as cm  # noqa: E402
from benchmarks.cable_barrier import cable_timeline as tl  # noqa: E402
from benchmarks.following.render_follow_3d import duplicate_car  # noqa: E402
from benchmarks.guardrail_end.render_terminal_3d import galvanised, mesh_object  # noqa: E402
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402

material, cube = base.material, base.cube
FRAME = (1080, 1920)
PAINT = (1.75, 0.30, 0.24)
Y_RANGE = (-140.0, 160.0)


def arguments():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--res-scale", type=float, default=0.5)
    p.add_argument("--samples", type=int, default=16)
    p.add_argument("--frames", default="0-0")
    p.add_argument("--list", default="")
    p.add_argument("--film", action="store_true")
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return p.parse_args(argv)


def build_highway(seed=5):
    road = material("Asphalt", (0.07, 0.07, 0.075), rough=0.85)
    base.asphalt_grain(road)
    paint = material("Line paint", (0.85, 0.85, 0.80), rough=0.6)
    grass = material("Median grass", (0.11, 0.21, 0.045), rough=0.95)
    verge = material("Verge grass", (0.12, 0.20, 0.05), rough=0.95)
    ym, yl = sum(Y_RANGE) / 2, Y_RANGE[1] - Y_RANGE[0]
    for sx in (-1, 1):
        cube(f"Carriageway {sx}", (sx * 10.0, ym, -0.05), (8.0, yl, 0.1), road)
        for xe in (6.3, 13.7):
            cube(f"Edge line {sx} {xe}", (sx * xe, ym, 0.002), (0.15, yl, 0.004), paint)
        for i in range(int(yl / 12)):
            cube(f"Lane dash {sx} {i}", (sx * 10.0, Y_RANGE[0] + 6 + i * 12, 0.002), (0.13, 3.0, 0.004), paint)
        cube(f"Verge {sx}", (sx * 44.0, ym, -0.06), (60.0, yl, 0.1), verge)
    cube("Median", (0.0, ym, -0.03), (12.0, yl, 0.1), grass)
    bark = material("Bark", (0.10, 0.07, 0.05), rough=0.9)
    leaves = [material("Leaves a", (0.10, 0.17, 0.05), rough=0.85), material("Leaves b", (0.16, 0.19, 0.05), rough=0.85)]
    rng = random.Random(seed)
    for k in range(40):
        x = rng.choice((-1, 1)) * rng.uniform(17, 60)
        y = rng.uniform(-100, 140)
        h = rng.uniform(5, 11)
        bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.18, depth=h * 0.5, location=(x, y, h * 0.25))
        bpy.context.object.data.materials.append(bark)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=h * 0.32, location=(x, y, h * 0.62))
        ob = bpy.context.object
        ob.scale = (1.0, 1.0, 1.25)
        ob.data.materials.append(leaves[k % 2])
    hill = material("Hills", (0.10, 0.14, 0.10), rough=1.0)
    for x, y, sx in ((260, 120, 180), (230, -160, 140), (-280, 60, 200), (-240, 260, 180)):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=1.0, location=(x, y, -10))
        ob = bpy.context.object
        ob.scale = (sx, sx * 0.8, 45)
        ob.data.materials.append(hill)


class Ropes:
    """Three wire ropes, rebuilt each frame as tubes along their (mirrored) model shape."""

    def __init__(self, mat):
        self.mat = mat
        self.obs = []

    def set(self, t):
        for ob in self.obs:
            me = ob.data
            bpy.data.objects.remove(ob)
            bpy.data.meshes.remove(me)
        self.obs = []
        st = cm.state(t)
        ys = np.arange(-40.0, 100.0, 0.5)
        if st["kink_y"] is not None:
            ys = np.sort(np.unique(np.concatenate([ys, [st["kink_y"]]])))
        xs = -cm.rope_offset(ys, t)
        n_ring = 8
        ang = np.linspace(0, 2 * np.pi, n_ring, endpoint=False)
        for z in cm.ROPE_Z:
            verts, faces = [], []
            pts = np.stack([xs, ys, np.full_like(ys, z)], -1)
            d = np.gradient(pts, axis=0)
            d /= np.linalg.norm(d, axis=1, keepdims=True)
            for i, (p, di) in enumerate(zip(pts, d)):
                e1 = np.cross(di, [0, 0, 1.0])
                e1 /= np.linalg.norm(e1) + 1e-9
                e2 = np.cross(di, e1)
                for a in ang:
                    verts.append(tuple(p + 0.019 * (math.cos(a) * e1 + math.sin(a) * e2)))      # a little thicker than life (19 mm): reads on a phone
                if i:
                    b = (i - 1) * n_ring
                    for j in range(n_ring):
                        k = (j + 1) % n_ring
                        faces.append((b + j, b + k, b + n_ring + k, b + n_ring + j))
            self.obs.append(mesh_object(f"Wire rope {z}", verts, faces, self.mat))
        return float(-xs.min()) if len(xs) else 0.0


class Posts:
    def __init__(self, mat, cap):
        self.pivots = []
        for i, y in enumerate(cm.post_ys()):
            piv = bpy.data.objects.new(f"Post pivot {i}", None)
            bpy.context.collection.objects.link(piv)
            piv.location = (0.0, y, 0.0)
            post = cube(f"Post {i}", (0.0, y, 0.43), (0.06, 0.10, 0.86), mat)
            top = cube(f"Post cap {i}", (0.0, y, 0.87), (0.08, 0.12, 0.03), cap)
            for ob in (post, top):
                mw = ob.matrix_world.copy()
                ob.parent = piv
                ob.matrix_world = mw
            self.pivots.append(piv)

    def set(self, t):
        down = 0
        for i, piv in enumerate(self.pivots):
            a = cm.post_angle(i, t)
            piv.rotation_euler = (0.0, -a, 0.0)          # pushed toward -x (the far side), like the ropes
            down += a > 0.0
        return down


class Turf:
    """Clods thrown from the red car's tyres while it is on the grass median (deterministic)."""

    def __init__(self, n=140):
        mats = [material("Turf", (0.06, 0.09, 0.03), rough=0.95), material("Soil", (0.16, 0.11, 0.07), rough=0.95)]
        self.obs = [cube(f"Clod {k}", (0, 0, -9), (0.05, 0.04, 0.03), mats[k % 2]) for k in range(n)]
        rng = np.random.default_rng(15)
        self.spawns = []
        for t in np.arange(-0.6, 5.0, 0.012):
            st = cm.state(float(t))
            sp = math.hypot(st["vx"], st["vy"])
            if abs(st["cx"]) < 5.6 and sp > 3.0:
                h = cm.heading_vec(st["psi"])
                for side in (-1, 1):
                    right = np.array([math.cos(st["psi"]), -math.sin(st["psi"])])
                    w = np.array([st["cx"], st["cy"]]) - 1.2 * h + side * 0.75 * right
                    vel = np.array([-h[0] * sp * 0.25 + rng.normal(0, 1.2), -h[1] * sp * 0.25 + rng.normal(0, 1.2), rng.uniform(1.5, 4.0)])
                    self.spawns.append((float(t), np.array([-w[0], w[1], 0.05]), np.array([-vel[0], vel[1], vel[2]]), rng.uniform(0, 6, 3)))

    def set(self, t):
        live = [(t - tb, p, v, r) for tb, p, v, r in self.spawns if 0 <= t - tb <= 0.8]
        for k, ob in enumerate(self.obs):
            if k >= len(live):
                ob.hide_render = True
                continue
            tau, p, v, r = live[k]
            q = p + v * tau + np.array([0, 0, -4.9 * tau * tau])
            ob.hide_render = q[2] < 0.0
            ob.location = tuple(np.maximum(q, [-1e9, -1e9, 0.02]))
            ob.rotation_euler = tuple(r * tau * 8)
        return len(live)


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
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Punchy"
    scene.view_settings.exposure = 0.2
    if hasattr(scene.view_settings, "use_white_balance"):
        scene.view_settings.use_white_balance = True
        scene.view_settings.white_balance_temperature = 7600.0
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    sun_to = cinematic.sun_vector((0.55, 0.75), 15.0)
    cinematic.apply_sky(scene, sun_to, strength=0.24, dust=0.7)
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    sun.data.energy, sun.data.angle = 6.5, 0.02
    sun.data.color = (1.0, 0.74, 0.48)
    sun.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()
    build_highway()
    oncoming_root, _, oncoming_wheels, _ = duplicate_car(root, wheels, (0.08, 0.30, 0.95))
    wheel_nodes = {w["node"] for w in wheels.values()}
    parts = [o for o in root.children_recursive if o.type == "MESH" and not any(p in wheel_nodes for p in rb._ancestors(o))]
    ghost = rb.Ghost(parts)
    ghost.set_tint(PAINT)
    ghost.set_factor(0.0, 1e4, 4.0)
    ropes = Ropes(galvanised("Wire rope", (0.88, 0.89, 0.90)))
    posts = Posts(material("Post steel", (0.55, 0.56, 0.58), metal=0.8, rough=0.35), material("Post cap", (0.85, 0.75, 0.15), rough=0.4))
    turf = Turf()
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    r_t = geom["tyre_radius"]

    def render(sh, path):
        scene.render.resolution_x, scene.render.resolution_y = round(FRAME[0] * args.res_scale), round(FRAME[1] * args.res_scale)
        t = sh["t"]
        st = cm.state(t)
        root.location = (-st["cx"], st["cy"], 0.0)
        root.rotation_euler = (0.0, 0.0, st["psi"])
        for wh in wheels.values():
            wh["node"].rotation_mode = "ZXY"
            wh["node"].rotation_euler = (-(st["cy"] + 200.0) / r_t, 0, 0)
        oy = cm.oncoming_y(t)
        oncoming_root.location = (-cm.ONCOMING_X, oy, 0.0)
        oncoming_root.rotation_euler = (0.0, 0.0, math.pi)
        for wh in oncoming_wheels.values():
            wh["node"].rotation_mode = "ZXY"
            wh["node"].rotation_euler = ((oy + 200.0) / r_t, 0, 0)
        depth = ropes.set(t)
        down = posts.set(t)
        clods = turf.set(t)
        c = sh["cam"]
        o = Vector(root.location) if c["rel"] == "car" else Vector((0.0, 0.0, 0.0))
        loc, tgt = o + Vector(c["loc"]), o + Vector(c["target"])
        dd = cam.data
        dd.sensor_fit, dd.sensor_width, dd.lens, dd.clip_start = "HORIZONTAL", 36.0, c["lens"], 0.02
        dd.dof.use_dof = True
        dd.dof.focus_distance = (tgt - loc).length
        dd.dof.aperture_fstop = c.get("fstop", 8.0)
        base.set_camera(cam, loc, tgt)
        bpy.context.view_layer.update()
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        return {"variant": "crash", "t": round(t, 6), "cx": round(st["cx"], 4), "cy": round(st["cy"], 4), "psi": round(st["psi"], 5),
                "rope_depth": round(depth, 4), "posts_down": int(down), "clods": clods, "oncoming_y": round(oy, 3),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    segs = tl.segments()
    a0, b0 = (int(v) for v in args.frames.split("-"))
    frames = [int(v) for v in args.list.split(",")] if args.list else list(range(a0, b0 + 1))
    out = []
    for f in frames:
        t0 = time.time()
        sh = tl.frame_state(f, segs)
        part = render(sh, args.out / f"frame_{f:05d}.png")
        info = {"frame": f, "segment": sh["segment"], "split": False, "parts": [part], "render_seconds": round(time.time() - t0, 1)}
        out.append(info)
        print("CABLE_FRAME " + json.dumps(info), flush=True)
    (args.out / f"cable-frames-{frames[0]:05d}.json").write_text(json.dumps({"renderer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                                                            "frames": out}, indent=1))


if __name__ == "__main__":
    main()
