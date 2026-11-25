"""EP.29 wind-turbine blade lifter: 100 % 3D renderer (Blender, Cycles CPU), house style of EP.13-EP.28 (morning sun, depth of
field). The winding mountain road of EP.26 (forested hillside, rock cut on the left, steep wooded slope and a valley on the right,
ridges far off), here without the roller barrier. Up it crawls a special transport: a tractor unit, a multi-axle lifter trailer and,
held by its root in the lifter's tilting cradle, an 85 m blade (white, a red band at the tip), with escort cars and amber beacons
ahead (the CC0 sedan in house red) and behind.

Everything moves from blade_motion: the rig's place and heading along the lane, the blade's tilt (35 degrees on the straights, up to
60 in the bends) and its swing (up to 20 degrees toward the road ahead). The comparison shots add a translucent blade lying flat
along the trailer, which runs into the rock cut and the trees. The wind shot stops the rig: leaves streak past, the trees' crowns
lean, a windsock stands out and the raised blade sways. No text anywhere in the scene."""
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
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from benchmarks import hook_gate  # noqa: E402
from benchmarks.belt_limiter import render_belt_3d as rb  # noqa: E402  (car paint tint)
from benchmarks.blade_lifter import blade_motion as bm  # noqa: E402
from benchmarks.blade_lifter import blade_timeline as tl  # noqa: E402
from benchmarks.can_opener import render_opener_3d as K  # noqa: E402  (data-API mesh helpers)
from benchmarks.manhole_blast.render_manhole_3d import Nodes  # noqa: E402
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402
from benchmarks.roller_barrier import render_roller_3d as rr  # noqa: E402  (the mountain land, road and trees of EP.26)

material = base.material
FRAME = (1080, 1920)
PAINT = (1.75, 0.30, 0.24)
N_LEAVES = 160


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


def ghost_material(name, color=(0.5, 0.85, 1.0), strength=2.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    N = Nodes(nt)
    out = N.new("ShaderNodeOutputMaterial")
    lw = N.new("ShaderNodeLayerWeight", Blend=0.35)
    em = N.new("ShaderNodeEmission", Color=color, Strength=strength)
    mix = N.new("ShaderNodeMixShader")
    N.put(mix.inputs["Fac"], N.math("MULTIPLY_ADD", lw.outputs["Facing"], 0.5, 0.3, clamp=True))
    N.put(mix.inputs[1], N.new("ShaderNodeBsdfTransparent").outputs[0])
    N.put(mix.inputs[2], em.outputs[0])
    N.put(out.inputs["Surface"], mix.outputs[0])
    return m


def blade_geom(n_span=48, n_sec=20):
    """The blade along local +y from its root (y = 0) to its tip, chord along x, thickness along z: a round root that turns into a
    twisted, tapering airfoil. Faces: 0 = white, 1 = red tip band, 2 = root flange."""
    L = bm.L_BLADE
    co, faces, mi = [], [], []
    for i in range(n_span):
        u = i / (n_span - 1)
        y = u * L
        if u < 0.04:
            chord, thick, roundness = 3.3, 3.3, 1.0
        elif u < 0.22:
            w = (u - 0.04) / 0.18
            chord, thick, roundness = 3.3 + (bm.CHORD - 3.3) * w, 3.3 - 2.0 * w, 1.0 - w
        else:
            w = (u - 0.22) / 0.78
            chord, thick, roundness = bm.CHORD * (1 - 0.86 * w), 1.3 * (1 - 0.85 * w), 0.0
        twist = math.radians(14.0) * (1 - u)
        for k in range(n_sec):
            a = 2 * math.pi * k / n_sec
            cx, cz = 0.5 * chord * math.cos(a), 0.5 * thick * math.sin(a)
            if roundness < 1.0:                                      # airfoil: blunt leading edge, sharp trailing edge, cambered
                ex = 0.5 * chord * (math.cos(a) * (1 - roundness) ** 0.0)
                cz = 0.5 * thick * math.sin(a) * (0.55 + 0.45 * math.cos(a)) + 0.06 * thick * (1 - math.cos(a))
                cx = roundness * cx + (1 - roundness) * ex
            x = cx * math.cos(twist) - cz * math.sin(twist)
            z = cx * math.sin(twist) + cz * math.cos(twist)
            co.append((x, y, z))
    for i in range(n_span - 1):
        u = (i + 0.5) / (n_span - 1)
        tag = 1 if u > 0.93 else (2 if u < 0.012 else 0)
        for k in range(n_sec):
            a, b = i * n_sec + k, i * n_sec + (k + 1) % n_sec
            faces.append((a, b, b + n_sec, a + n_sec))
            mi.append(tag)
    faces.append(tuple(range(n_sec))[::-1])
    mi.append(2)
    faces.append(tuple((n_span - 1) * n_sec + k for k in range(n_sec)))
    mi.append(1)
    return co, faces, mi


class Rig:
    """Tractor, lifter trailer with its slewing ring and tilting cradle, and the blade; escort cars with beacons."""

    def __init__(self, car_root):
        white = material("Rig white", (0.86, 0.86, 0.84), rough=0.45)
        orange = material("Rig orange", (0.90, 0.38, 0.05), metal=0.2, rough=0.4)
        dark = material("Rig dark", (0.05, 0.05, 0.055), rough=0.7)
        steel = material("Rig steel", (0.45, 0.46, 0.48), metal=0.8, rough=0.35)
        glass = material("Rig glass", (0.04, 0.05, 0.06), metal=0.3, rough=0.08)
        tyre = material("Rig tyre", (0.02, 0.02, 0.02), rough=0.8)
        self.beacon = material("Beacon", (1.0, 0.55, 0.05), rough=0.4)
        from benchmarks.rock_net.render_rocknet_3d import merged
        # tractor: local frame, forward +y, origin at its rear axle group, on the road
        self.tractor = bpy.data.objects.new("Tractor", None)
        bpy.context.collection.objects.link(self.tractor)
        tparts = [
            merged("Tractor cab", [(K.box_verts((0.0, 4.6, 2.3), (2.5, 2.2, 2.4)), K.BOX_FACES), (K.box_verts((0.0, 5.8, 1.5), (2.5, 0.6, 1.4)), K.BOX_FACES)], orange),
            merged("Tractor windows", [(K.box_verts((0.0, 5.72, 2.75), (2.3, 0.08, 0.9)), K.BOX_FACES)], glass),
            merged("Tractor chassis", [(K.box_verts((0.0, 1.6, 0.95), (1.1, 8.0, 0.5)), K.BOX_FACES), (K.box_verts((0.0, -0.2, 1.3), (2.3, 1.6, 0.18)), K.BOX_FACES)], dark),
            merged("Tractor wheels", [K.cyl_geom(0.55, 0.45, (sx * 1.05, yy, 0.55), (0, math.pi / 2, 0), 14) for sx in (-1, 1) for yy in (-0.7, 0.7, 4.4)], tyre),
            merged("Tractor beacons", [(K.box_verts((sx * 0.8, 4.6, 3.6), (0.3, 0.3, 0.2)), K.BOX_FACES) for sx in (-1, 1)], self.beacon),
        ]
        for ob in tparts:
            ob.parent = self.tractor
        # lifter trailer: local frame at the lifter (blade root), forward +y
        self.trailer = bpy.data.objects.new("Lifter trailer", None)
        bpy.context.collection.objects.link(self.trailer)
        rparts = [
            merged("Trailer deck", [(K.box_verts((0.0, 3.0, 1.05), (2.9, 9.0, 0.5)), K.BOX_FACES)], orange),
            merged("Trailer wheels", [K.cyl_geom(0.42, 0.32, (sx * x0, yy, 0.42), (0, math.pi / 2, 0), 12) for sx in (-1, 1) for x0 in (0.55, 1.25)
                                      for yy in (-0.6, 0.9, 2.4, 3.9, 5.4)], tyre),
            merged("Lifter base", [(K.box_verts((0.0, 0.0, 1.55), (2.6, 2.6, 0.6)), K.BOX_FACES)], dark),
            merged("Slewing ring", [K.cyl_geom(1.25, 0.35, (0.0, 0.0, 2.0), (0, 0, 0), 24)], steel),
        ]
        for ob in rparts:
            ob.parent = self.trailer
        self.swing = bpy.data.objects.new("Lifter swing", None)
        bpy.context.collection.objects.link(self.swing)
        self.swing.parent = self.trailer
        self.swing.location = (0.0, 0.0, 2.2)
        sparts = [merged("Cradle posts", [(K.box_verts((sx * 1.3, 0.0, 0.5), (0.4, 1.0, 1.4)), K.BOX_FACES) for sx in (-1, 1)], orange)]
        for ob in sparts:
            ob.parent = self.swing
        self.tilt = bpy.data.objects.new("Lifter tilt", None)
        bpy.context.collection.objects.link(self.tilt)
        self.tilt.parent = self.swing
        self.tilt.location = (0.0, 0.0, bm.ROOT_H - 2.2)
        co, faces, mi = blade_geom()
        self.blade = rr.np_mesh("Blade", co, faces, [material("Blade white", (0.90, 0.91, 0.90), rough=0.35),
                                                    material("Blade red tip", (0.75, 0.06, 0.04), rough=0.4), steel], mi, smooth=True)
        self.blade.parent = self.tilt
        clamp = merged("Root clamp", [K.cyl_geom(1.9, 1.2, (0.0, 1.0, 0.0), (math.pi / 2, 0, 0), 24)], steel)
        clamp.parent = self.tilt
        self.ram = merged("Tilt ram", [K.cyl_geom(0.22, 1.0, (0.0, 0.0, 0.5), (0, 0, 0), 10)], steel)
        # the flat blade a normal trailer would carry (translucent)
        self.ghost = rr.np_mesh("Flat blade (would hit)", co, faces, [ghost_material("Ghost blade")], None, smooth=True)
        self.ghost.hide_render = True
        self.car = car_root
        self.rear = merged("Escort car behind", [(K.box_verts((0.0, 0.0, 0.62), (1.8, 4.4, 0.65)), K.BOX_FACES), (K.box_verts((0.0, 0.2, 1.22), (1.6, 2.3, 0.6)), K.BOX_FACES)],
                           material("Escort white", (0.88, 0.88, 0.86), rough=0.4))
        self.rear_beacon = merged("Escort beacon", [(K.box_verts((0.0, 0.2, 1.6), (1.2, 0.3, 0.12)), K.BOX_FACES)], self.beacon)
        self.rear_beacon.parent = self.rear
        self.lead_beacon = K.cube("Lead beacon", (0.0, 0.0, 1.45), (0.25, 1.1, 0.12), self.beacon)
        self.lead_beacon.parent = car_root
        self.lead_beacon.location = (0.0, 0.1, 1.42)

    def set(self, t, film_t, flags):
        s = bm.s_of(t) if not flags.get("wind") else tl.WIND_S
        p, h = bm.at(s)
        a = bm.alpha(s)
        ps = bm.psi(s, a)
        if flags.get("wind"):
            a += math.radians(0.8) * math.sin(2 * math.pi * 0.55 * film_t)
            ps += math.radians(0.6) * math.sin(2 * math.pi * 0.37 * film_t + 1.0)
        self.trailer.location = (p[0], p[1], 0.0)
        self.trailer.rotation_euler = (0.0, 0.0, -h)
        self.swing.rotation_euler = (0.0, 0.0, -ps)
        self.tilt.rotation_euler = (a, 0.0, 0.0)
        pt, ht = bm.at(s + bm.TRACTOR_AHEAD)
        self.tractor.location = (pt[0], pt[1], 0.0)
        self.tractor.rotation_euler = (0.0, 0.0, -ht)
        self.ghost.hide_render = not flags.get("ghost")
        self.blade.hide_render = bool(flags.get("flat_only"))             # the "lying flat" picture: only the flat blade
        self.ghost.location = (p[0], p[1], bm.ROOT_H)
        self.ghost.rotation_euler = (0.0, 0.0, -h)
        pc, hc = bm.at(s + 38.0)
        self.car.location = (pc[0], pc[1], 0.0)
        self.car.rotation_euler = (0.0, 0.0, -hc)
        pr, hr = bm.at(s - 24.0)
        self.rear.location = (pr[0], pr[1], 0.0)
        self.rear.rotation_euler = (0.0, 0.0, -hr)
        on = int(film_t * 3.0) % 2 == 0
        sb = self.beacon.node_tree.nodes.get("Principled BSDF")
        sb.inputs["Emission Color"].default_value = (1.0, 0.5, 0.05, 1)
        sb.inputs["Emission Strength"].default_value = 18.0 if on else 1.0
        return {"s": round(s, 4), "x": round(float(p[0]), 4), "y": round(float(p[1]), 4), "heading": round(h, 5), "alpha": round(a, 5), "psi": round(ps, 5)}


class Wind:
    """Leaves streaking past and a windsock standing out, for the wind shot only."""

    def __init__(self):
        leaf = material("Blown leaves", (0.30, 0.22, 0.07), rough=0.8)
        self.leaves = []
        for k in range(N_LEAVES):
            ob = K.cube(f"Leaf {k}", (0, 0, -50), (0.06, 0.04, 0.005), leaf)
            ob.hide_render = True
            self.leaves.append(ob)
        self.seed = np.random.default_rng(29).uniform(0, 1, (N_LEAVES, 4))
        p, h = bm.at(tl.WIND_S + 22.0)
        nrm = (-math.cos(h), math.sin(h))
        self.sock_base = (p[0] + nrm[0] * 6.2, p[1] + nrm[1] * 6.2)
        pole = material("Sock pole", (0.7, 0.7, 0.7), metal=0.6, rough=0.4)
        sock = material("Windsock", (0.95, 0.35, 0.05), rough=0.6)
        self.pole = K.cyl("Windsock pole", 0.06, 6.0, (self.sock_base[0], self.sock_base[1], 3.0), pole, verts=8)
        v, f = K.cyl_geom(0.35, 2.2, (0.0, 1.1, 0.0), (math.pi / 2, 0, 0), 12)
        v = [(x * (1.0 - 0.45 * (y / 2.2)), y, z * (1.0 - 0.45 * (y / 2.2))) for x, y, z in v]
        self.sock = rr.np_mesh("Windsock", v, f, [sock])
        self.sock.location = (self.sock_base[0], self.sock_base[1], 5.9)
        self.objs = [self.pole, self.sock]
        self.wind_dir = math.radians(80.0)

    def set(self, on, film_t, cam_loc):
        for ob in self.objs:
            ob.hide_render = not on
        self.sock.rotation_euler = (math.radians(-5.0 + 3.0 * math.sin(film_t * 9.0)), 0.0, -self.wind_dir)
        n = 0
        for k, ob in enumerate(self.leaves):
            if not on:
                ob.hide_render = True
                continue
            a, b, c, d = self.seed[k]
            period = 1.2 + 1.2 * d
            u = ((film_t + a * period) % period) / period
            dirx, diry = math.sin(self.wind_dir), math.cos(self.wind_dir)
            along = -25.0 + 50.0 * u
            side = (b - 0.5) * 30.0
            x = cam_loc[0] + 18.0 * math.sin(math.radians(-80)) + along * dirx - side * diry
            y = cam_loc[1] + 18.0 * math.cos(math.radians(-80)) + along * diry + side * dirx
            z = 0.5 + 9.0 * c + 1.2 * math.sin(film_t * 7 + k)
            ob.hide_render = False
            ob.location = (x, y, z)
            ob.rotation_euler = (film_t * (5 + 7 * c), film_t * (3 + 5 * d), film_t * 4)
            ob.scale = (1.0 + 2.0 * d, 1.0, 1.0)
            n += 1
        return n


def main():
    args = arguments()
    args.out.mkdir(parents=True, exist_ok=True)
    car_root, body, wheels, geom = base.load_source_car(args.source)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Punchy"
    scene.view_settings.exposure = 0.0
    if hasattr(scene.view_settings, "use_white_balance"):
        scene.view_settings.use_white_balance = True
        scene.view_settings.white_balance_temperature = 6900.0
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    sun_to = cinematic.sun_vector((0.85, -0.5), 24.0)                         # morning sun from the east, over the valley
    cinematic.apply_sky(scene, sun_to, strength=0.30, dust=0.9)
    sd = bpy.data.lights.new("Sun", "SUN")
    sd.energy, sd.angle, sd.color = 5.0, 0.02, (1.0, 0.86, 0.68)
    sun = bpy.data.objects.new("Sun", sd)
    scene.collection.objects.link(sun)
    sun.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()
    wheel_nodes = {w["node"] for w in wheels.values()}
    parts = [o for o in car_root.children_recursive if o.type == "MESH" and not any(p in wheel_nodes for p in rb._ancestors(o))]
    ghost = rb.Ghost(parts)
    ghost.set_tint(PAINT)
    ghost.set_factor(0.0, 1e4, 4.0)
    land = rr.Land()
    rr.build_road()
    n_trees = rr.build_trees(land)
    rr.build_ridges()
    rig = Rig(car_root)
    wind = Wind()
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    segs = tl.segments()
    print("BLADE_SCENE " + json.dumps({"trees": n_trees, "objects": len(bpy.data.objects)}), flush=True)

    def render(sh, path):
        scene.render.resolution_x, scene.render.resolution_y = round(FRAME[0] * args.res_scale), round(FRAME[1] * args.res_scale)
        t = sh["t"]
        flags = {k: sh.get(k) for k in ("ghost", "wind", "flat_only")}
        st = rig.set(t, sh["film_t"], flags)
        cm = sh["cam"]
        o = Vector((st["x"], st["y"], 0.0)) if cm["rel"] == "rig" else Vector((0.0, 0.0, 0.0))
        loc, tgt = o + Vector(cm["loc"]), o + Vector(cm["target"])
        leaves = wind.set(bool(sh.get("wind")), sh["film_t"], loc)
        dd = cam.data
        dd.sensor_fit, dd.sensor_width, dd.lens, dd.clip_start = "HORIZONTAL", 36.0, cm["lens"], 0.05
        dd.clip_end = 15000.0
        dd.dof.use_dof = True
        dd.dof.focus_distance = (tgt - loc).length
        dd.dof.aperture_fstop = cm.get("fstop", 8.0)
        base.set_camera(cam, loc, tgt)
        bpy.context.view_layer.update()
        pts = bm.blade_axis(st["s"], st["alpha"], st["psi"], 2)
        lo = tuple(np.minimum(pts[0], pts[1]) - np.array([2.0, 2.0, 3.2]))
        hi = tuple(np.maximum(pts[0], pts[1]) + np.array([2.0, 2.0, 1.0]))
        box = hook_gate.project_box(scene, cam, Matrix.Identity(4), lo, hi)
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        return {"t": round(t, 6), **st, "ghost": bool(flags["ghost"]), "wind": bool(flags["wind"]), "flat_only": bool(flags["flat_only"]), "leaves": leaves,
                "subject_box": box, "cam_world": [round(x, 3) for x in loc], "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    a0, b0 = (int(x) for x in args.frames.split("-"))
    frames = [int(x) for x in args.list.split(",")] if args.list else list(range(a0, b0 + 1))
    out = []
    src_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    for f in frames:
        t0 = time.time()
        sh = tl.frame_state(f, segs)
        part = render(sh, args.out / f"frame_{f:05d}.png")
        info = {"frame": f, "segment": sh["segment"], "split": False, "parts": [part], "render_seconds": round(time.time() - t0, 1)}
        out.append(info)
        print("BLADE_FRAME " + json.dumps(info), flush=True)
    (args.out / f"blade-frames-{frames[0]:05d}.json").write_text(json.dumps({"renderer_source_sha256": src_sha, "frames": out}, indent=1))


if __name__ == "__main__":
    main()
