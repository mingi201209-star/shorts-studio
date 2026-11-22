"""EP.17 moveable barrier ("zipper"): 100 % 3D renderer (Blender, Cycles CPU), house style of EP.13-EP.16 (golden hour, depth of
field, warm grade). A six-lane highway with a pinned chain of concrete T-top blocks down the middle; a yellow barrier transfer
machine with an open frame drives along it; under the frame an S-shaped track of wheel pairs grips each block's T head, lifts the chain
and sets it down one lane over. Every block's pose, the machine and the traffic come from zipper_motion. Variants: day, morning
(wall one lane over, rush hour, no machine), night (dusk, beacons, the machine moves the wall back). No text."""
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
from benchmarks import hook_gate  # noqa: E402
from benchmarks.following.render_follow_3d import duplicate_car  # noqa: E402
from benchmarks.guardrail_end.render_terminal_3d import mesh_object  # noqa: E402
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402
from benchmarks.road_zipper import zipper_motion as zm  # noqa: E402
from benchmarks.road_zipper import zipper_timeline as tl  # noqa: E402

material, cube = base.material, base.cube
FRAME = (1080, 1920)
Y_RANGE = (-200.0, 260.0)
N_ROLLERS = 36


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


def emissive(name, colour, strength):
    m = material(name, colour, rough=0.4)
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Emission Color"].default_value = (*colour, 1.0)
    b.inputs["Emission Strength"].default_value = strength
    return m


def set_emission(m, strength):
    m.node_tree.nodes.get("Principled BSDF").inputs["Emission Strength"].default_value = strength


def build_highway(seed=17):
    road = material("Asphalt", (0.07, 0.07, 0.075), rough=0.85)
    base.asphalt_grain(road)
    paint = material("Line paint", (0.85, 0.85, 0.80), rough=0.6)
    grass = material("Grass", (0.11, 0.21, 0.045), rough=0.95)
    ym, yl = sum(Y_RANGE) / 2, Y_RANGE[1] - Y_RANGE[0]
    half = 3 * zm.LANE + 0.6
    cube("Carriageway", (0.0, ym, -0.05), (2 * half, yl, 0.1), road)
    for xe in (-3 * zm.LANE, 3 * zm.LANE):
        cube(f"Edge line {xe}", (xe, ym, 0.002), (0.15, yl, 0.004), paint)
    for xe in (-2 * zm.LANE, -zm.LANE, zm.LANE, 2 * zm.LANE):
        for i in range(int(yl / 12)):
            cube(f"Lane dash {xe} {i}", (xe, Y_RANGE[0] + 6 + i * 12, 0.002), (0.13, 3.0, 0.004), paint)
    for sx in (-1, 1):
        cube(f"Verge {sx}", (sx * (half + 30), ym, -0.06), (60.0, yl, 0.1), grass)
    bark = material("Bark", (0.10, 0.07, 0.05), rough=0.9)
    leaves = [material("Leaves a", (0.10, 0.17, 0.05), rough=0.85), material("Leaves b", (0.16, 0.19, 0.05), rough=0.85)]
    rng = random.Random(seed)
    for k in range(60):
        x = rng.choice((-1, 1)) * rng.uniform(half + 4, half + 50)
        y = rng.uniform(-180, 240)
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


def block_mesh(concrete, steel, amber):
    """One block (profile extruded along y) with pin knuckles at both ends and a small amber reflector; shared by every block."""
    h = (zm.BLOCK_L - zm.GAP) / 2
    prof = zm.PROFILE
    n = len(prof)
    verts = [(x, -h, z) for x, z in prof] + [(x, h, z) for x, z in prof]
    faces = [tuple(range(n))[::-1], tuple(range(n, 2 * n))]
    faces += [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)]
    ob = mesh_object("Block", verts, faces, concrete, smooth=False)
    ob.data.materials.append(steel)
    ob.data.materials.append(amber)
    bm_v, bm_f, mats = list(ob.data.vertices), [], []
    me = ob.data
    extra_v, extra_f, extra_m = [], [], []

    def box(cx, cy, cz, sx, sy, sz, mi):
        b = len(me.vertices) + len(extra_v)
        for dx in (-sx / 2, sx / 2):
            for dy in (-sy / 2, sy / 2):
                for dz in (-sz / 2, sz / 2):
                    extra_v.append((cx + dx, cy + dy, cz + dz))
        idx = lambda i, j, k: b + i * 4 + j * 2 + k  # noqa: E731
        for f in ((idx(0, 0, 0), idx(0, 1, 0), idx(0, 1, 1), idx(0, 0, 1)), (idx(1, 0, 0), idx(1, 0, 1), idx(1, 1, 1), idx(1, 1, 0)),
                  (idx(0, 0, 0), idx(0, 0, 1), idx(1, 0, 1), idx(1, 0, 0)), (idx(0, 1, 0), idx(1, 1, 0), idx(1, 1, 1), idx(0, 1, 1)),
                  (idx(0, 0, 0), idx(1, 0, 0), idx(1, 1, 0), idx(0, 1, 0)), (idx(0, 0, 1), idx(0, 1, 1), idx(1, 1, 1), idx(1, 0, 1))):
            extra_f.append(f)
            extra_m.append(mi)
    for sy in (-1, 1):                                       # pin knuckles: steel loops sticking out at each end (the "bike chain")
        for zc in (0.30, 0.50):
            box(0.0, sy * (h + 0.01), zc + (0.05 if sy > 0 else 0.0), 0.16, 0.06, 0.08, 1)
    box(-0.205, 0.0, 0.40, 0.01, 0.16, 0.06, 2)              # reflector on the face toward the cameras
    del bm_v, bm_f, mats
    import bmesh
    bmh = bmesh.new()
    bmh.from_mesh(me)
    vs = [bmh.verts.new(v) for v in extra_v]
    bmh.verts.ensure_lookup_table()
    base_n = len(me.vertices)
    for f, mi in zip(extra_f, extra_m):
        face = bmh.faces.new([vs[i - base_n] for i in f])
        face.material_index = mi
    bmh.to_mesh(me)
    bmh.free()
    me.update()
    return ob


class Wall:
    def __init__(self, concrete, steel, amber):
        proto = block_mesh(concrete, steel, amber)
        self.obs = [proto]
        for k in range(1, len(zm.BLOCK_Y)):
            ob = proto.copy()
            bpy.context.collection.objects.link(ob)
            self.obs.append(ob)

    def set(self, t, variant):
        b = zm.blocks(t, variant)
        for k, ob in enumerate(self.obs):
            ob.location = (float(b["x"][k]), float(b["y"][k]), float(b["z"][k]))
            ob.rotation_euler = (0.0, 0.0, float(b["yaw"][k]))
        return b


def tube(name, pts, r, mat, n=8):
    verts, faces = [], []
    pts = np.asarray(pts, float)
    d = np.gradient(pts, axis=0)
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    for i, (p, di) in enumerate(zip(pts, d)):
        e1 = np.cross(di, [0, 0, 1.0])
        e1 /= np.linalg.norm(e1) + 1e-9
        e2 = np.cross(di, e1)
        for a in np.linspace(0, 2 * np.pi, n, endpoint=False):
            verts.append(tuple(p + r * (math.cos(a) * e1 + math.sin(a) * e2)))
        if i:
            b = (i - 1) * n
            for j in range(n):
                k = (j + 1) % n
                faces.append((b + j, b + k, b + n + k, b + n + j))
    return mesh_object(name, verts, faces, mat)


class Machine:
    """Open yellow frame on eight wheels with a cab at each end; under it the S track (two rails) and the gripping wheel pairs.
    Everything is parented to a root at (0, machine y, 0) in world x (the frame is centred on x = SHIFT / 2)."""

    def __init__(self):
        self.root = bpy.data.objects.new("Machine root", None)
        bpy.context.collection.objects.link(self.root)
        yellow = material("Machine yellow", (0.95, 0.62, 0.05), metal=0.2, rough=0.45)
        dark = material("Machine dark", (0.08, 0.08, 0.09), metal=0.4, rough=0.5)
        rubber = material("Machine tyre", (0.03, 0.03, 0.035), rough=0.8)
        glass = material("Cab glass", (0.10, 0.14, 0.16), metal=0.5, rough=0.1)
        self.beacon = emissive("Beacon", (1.0, 0.45, 0.05), 1.0)
        cx, hw = zm.SHIFT / 2, zm.MACHINE_HALF_W
        parts = []
        for sx in (-1, 1):
            parts.append(cube(f"Side beam {sx}", (cx + sx * hw, 0.0, 1.45), (0.32, 18.0, 0.55), yellow))
            parts.append(cube(f"Lower rail {sx}", (cx + sx * hw, 0.0, 1.05), (0.18, 15.0, 0.12), dark))
        for y in (-8.4, -4.0, 0.0, 4.0, 8.4):
            parts.append(cube(f"Cross member {y}", (cx, y, 1.78), (2 * hw + 0.3, 0.28, 0.16), yellow))
        cab_l, cab_r = cx - hw - 0.75, cx + hw + 0.75          # cabs hang outboard so the wall's way in and out stays in view
        parts.append(cube("Front cab", (cab_l, 7.6, 2.2), (1.4, 1.9, 1.55), yellow))
        parts.append(cube("Front cab glass", (cab_l, 8.56, 2.4), (1.2, 0.04, 0.8), glass))
        parts.append(cube("Rear cab", (cab_r, -7.6, 2.2), (1.4, 1.9, 1.55), yellow))
        parts.append(cube("Rear cab glass", (cab_r, -8.56, 2.4), (1.2, 0.04, 0.8), glass))
        parts.append(cube("Engine housing", (cab_l + 0.1, -1.5, 2.0), (1.2, 4.5, 0.9), yellow))
        for (x, y) in ((cab_l, 7.6), (cab_r, -7.6)):
            bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.12, depth=0.18, location=(x, y, 3.07))
            bpy.context.object.data.materials.append(self.beacon)
            parts.append(bpy.context.object)
        self.wheels = []
        for wx in zm.MACHINE_WHEEL_X:
            for wy in (-6.6, -5.4, 5.4, 6.6):
                bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.5, depth=0.42, location=(wx, wy, 0.5), rotation=(0, math.pi / 2, 0))
                ob = bpy.context.object
                ob.data.materials.append(rubber)
                parts.append(ob)
                self.wheels.append(ob)
                parts.append(cube(f"Wheel leg {wx} {wy}", (wx, wy, 1.05), (0.3, 0.3, 0.9), dark))
        self.tracks = {}
        for variant in ("day", "night"):
            us = np.linspace(0, 1, 60)
            xs = zm.SHIFT * (zm._s(us) if variant == "day" else 1 - zm._s(us))
            ys = zm.LT / 2 - us * zm.LT
            zs = zm.LIFT * np.sin(np.pi * us) + zm.T_TOP_Z + 0.32
            obs = []
            for side in (-1, 1):
                obs.append(tube(f"S track {variant} {side}", np.stack([xs + side * 0.22, ys, zs], -1), 0.05, dark))
            for k in range(0, 60, 6):                                  # hangers from the frame down to the track
                obs.append(cube(f"Hanger {variant} {k}", (float(xs[k]), float(ys[k]), (zs[k] + 1.2) / 2), (0.08, 0.08, 1.2 - zs[k]), dark))
            self.tracks[variant] = obs
            parts += obs
        roller_me = None
        self.rollers = []
        for k in range(N_ROLLERS):
            for side in (-1, 1):
                bpy.ops.mesh.primitive_cylinder_add(vertices=14, radius=0.055, depth=0.05, location=(0, 0, -9))
                ob = bpy.context.object
                if roller_me is None:
                    ob.data.materials.append(dark)
                    roller_me = ob.data
                else:
                    old = ob.data
                    ob.data = roller_me
                    bpy.data.meshes.remove(old)
                self.rollers.append((k, side, ob))
        for ob in parts:
            mw = ob.matrix_world.copy()
            ob.parent = self.root
            ob.matrix_world = mw
        self.lamps = []
        for (x, y) in ((cx - 1.0, 9.0), (cx + 1.0, -9.0)):
            bpy.ops.object.light_add(type="SPOT", location=(x, y, 3.2))
            lamp = bpy.context.object
            lamp.data.energy, lamp.data.spot_size = 0.0, math.radians(70)
            lamp.data.color = (1.0, 0.85, 0.6)
            lamp.rotation_euler = (math.radians(55) if y > 0 else -math.radians(55), 0.0, 0.0) if False else (0.0, 0.0, 0.0)
            lamp.rotation_euler = (Vector((0.0, 0.0, -1.0)) + Vector((0.0, 0.6 if y > 0 else -0.6, 0.0))).to_track_quat("-Z", "Y").to_euler()
            lamp.parent = self.root
            self.lamps.append(lamp)

    def set(self, t, variant, visible, night):
        self.root.location = (0.0, zm.machine_y(t), 0.0)
        for ob in self.root.children:
            ob.hide_render = not visible
        for v, obs in self.tracks.items():
            for ob in obs:
                ob.hide_render = (not visible) or v != ("night" if variant == "night" else "day")
        spin = zm.machine_y(t) / 0.5
        for ob in self.wheels:
            ob.rotation_euler = (spin, math.pi / 2, 0.0)
        for k, side, ob in self.rollers:
            ob.hide_render = not visible
            u = (k + 0.5) / N_ROLLERS
            s = zm._s(np.array(u))
            x = zm.SHIFT * (float(s) if variant != "night" else 1 - float(s))
            y = zm.machine_y(t) + zm.LT / 2 - u * zm.LT
            z = zm.LIFT * math.sin(math.pi * u) + zm.T_TOP_Z - 0.06
            ob.location = (x + side * 0.115, y, z)
            ob.rotation_euler = (zm.machine_y(t) / 0.055, 0.0, 0.0)
        set_emission(self.beacon, (12.0 if night else 2.0) * (0.6 + 0.4 * math.sin(2 * math.pi * 1.5 * t) ** 2))
        for lamp in self.lamps:
            lamp.data.energy = 900.0 if (night and visible) else 0.0


class Traffic:
    def __init__(self, root, wheels):
        self.cars = []
        for k, (x, d, y0, v, colour) in enumerate(zm.TRAFFIC + zm.MORNING_EXTRA):
            r, _, w, _ = duplicate_car(root, wheels, colour)
            self.cars.append((r, w, k >= len(zm.TRAFFIC)))

    def set(self, t, variant):
        pos = zm.traffic(t, variant)
        for k, (r, w, extra) in enumerate(self.cars):
            if extra and variant != "morning":
                r.location = (0.0, 0.0, -50.0)
                continue
            x, y, d = pos[k] if k < len(pos) else (0.0, 0.0, 1)
            r.location = (x, y, 0.0)
            r.rotation_euler = (0.0, 0.0, 0.0 if d > 0 else math.pi)
            for wh in w.values():
                wh["node"].rotation_mode = "ZXY"
                wh["node"].rotation_euler = (-(y * d) / 0.281, 0, 0)
        return pos


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
    sun_to = cinematic.sun_vector((0.6, -0.7), 15.0)
    cinematic.apply_sky(scene, sun_to, strength=0.24, dust=0.7)
    sky_nodes = [n for n in scene.world.node_tree.nodes if n.type == "BACKGROUND"]
    sky_strength = [n.inputs["Strength"].default_value for n in sky_nodes]
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    sun.data.energy, sun.data.angle = 6.5, 0.02
    sun.data.color = (1.0, 0.74, 0.48)
    sun.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()
    build_highway()
    traffic = Traffic(root, wheels)
    root.location = (0.0, 0.0, -50.0)                        # the source car is only the template for the traffic
    wall = Wall(material("Concrete", (0.46, 0.455, 0.44), rough=0.85), material("Pin steel", (0.25, 0.25, 0.27), metal=0.8, rough=0.4),
                emissive("Reflector", (1.0, 0.55, 0.05), 0.5))
    machine = Machine()
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam

    def render(sh, path):
        scene.render.resolution_x, scene.render.resolution_y = round(FRAME[0] * args.res_scale), round(FRAME[1] * args.res_scale)
        t, variant = sh["t"], sh["variant"]
        night = variant == "night"
        sun.data.energy = 0.15 if night else 6.5
        sun.data.color = (0.55, 0.65, 1.0) if night else (1.0, 0.74, 0.48)
        for n, s0 in zip(sky_nodes, sky_strength):
            n.inputs["Strength"].default_value = s0 * (0.12 if night else 1.0)
        b = wall.set(t, variant)
        machine.set(t, variant, variant != "morning", night)
        cars = traffic.set(t, variant)
        c = sh["cam"]
        o = Vector((0.0, zm.machine_y(t), 0.0)) if c["rel"] == "machine" else Vector((0.0, 0.0, 0.0))
        loc, tgt = o + Vector(c["loc"]), o + Vector(c["target"])
        dd = cam.data
        dd.sensor_fit, dd.sensor_width, dd.lens, dd.clip_start = "HORIZONTAL", 36.0, c["lens"], 0.02
        dd.dof.use_dof = True
        dd.dof.focus_distance = (tgt - loc).length
        dd.dof.aperture_fstop = c.get("fstop", 8.0)
        base.set_camera(cam, loc, tgt)
        bpy.context.view_layer.update()
        cx, hw = zm.SHIFT / 2, zm.MACHINE_HALF_W
        box = hook_gate.project_box(scene, cam, machine.root.matrix_world, (cx - hw - 1.5, -9.2, 0.0), (cx + hw + 1.5, 9.2, 3.2))
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        ym = zm.machine_y(t)
        near = int(np.argmin(np.abs(b["y"] - ym)))
        return {"variant": variant, "t": round(t, 6), "machine_y": round(ym, 4) if variant != "morning" else None, "subject_box": box,
                "block_x_at_machine": round(float(b["x"][near]), 4), "max_lift": round(float(b["z"].max()), 4),
                "blocks_moved": int((np.abs(b["x"] - zm.SHIFT) < 1e-6).sum()), "max_pin_gap": round(float(zm.pin_gaps(t, variant).max()), 4),
                "cars": [[round(x, 3), round(y, 3)] for x, y, _ in cars], "night": night,
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
        print("ZIPPER_FRAME " + json.dumps(info), flush=True)
    (args.out / f"zipper-frames-{frames[0]:05d}.json").write_text(json.dumps({"renderer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                                                             "frames": out}, indent=1))


if __name__ == "__main__":
    main()
