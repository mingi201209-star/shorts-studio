"""EP.16 tyre blowout: 100 % 3D renderer (Blender, Cycles CPU), house style of EP.13-EP.15 (golden hour, red car, depth of field).
A one-way highway (two lanes, shoulders, grass median); the red CC0 sedan in the left lane. Its front-left tyre is replaced by a
procedural tyre rebuilt every frame from blowout_motion: the sidewall flattens and bulges at the bottom (drawn twice as deep as the
model's deflection), lateral sipes turn with the wheel, a cut-away window shows the section with its two steel belts, the rubber glows
with the heat in the heat shots, the tread peels and flaps, then the carcass bursts: the tread strip and rubber pieces fly
(ballistic, one bounce, slide to a stop), a dust puff, the rim drops. Shreds of earlier blowouts lie on the shoulder. No text."""
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
from benchmarks.guardrail_end.render_terminal_3d import mesh_object  # noqa: E402
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402
from benchmarks.tire_blowout import blowout_motion as bm  # noqa: E402
from benchmarks.tire_blowout import blowout_timeline as tl  # noqa: E402

material, cube = base.material, base.cube
FRAME = (1080, 1920)
PAINT = (1.75, 0.30, 0.24)
Y_RANGE = (-260.0, 260.0)
PARKED = (4.35, -150.0)
VIS_PARKED = 3.0                       # the sag over months is drawn three times as deep as the model's, so it reads
N_A = 240                              # angular steps around the tyre
SIPES = 40


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


def build_highway(seed=16):
    road = material("Asphalt", (0.07, 0.07, 0.075), rough=0.85)
    base.asphalt_grain(road)
    paint = material("Line paint", (0.85, 0.85, 0.80), rough=0.6)
    grass = material("Grass", (0.11, 0.21, 0.045), rough=0.95)
    ym, yl = sum(Y_RANGE) / 2, Y_RANGE[1] - Y_RANGE[0]
    cube("Carriageway", (0.0, ym, -0.05), (10.4, yl, 0.1), road)
    for xe in (-3.7, 3.7):
        cube(f"Edge line {xe}", (xe, ym, 0.002), (0.15, yl, 0.004), paint)
    for i in range(int(yl / tl.DASH)):
        cube(f"Lane dash {i}", (0.0, Y_RANGE[0] + 6 + i * tl.DASH, 0.002), (0.13, 3.0, 0.004), paint)
    cube("Median", (-11.2, ym, -0.03), (12.0, yl, 0.1), grass)
    cube("Verge", (35.2, ym, -0.06), (60.0, yl, 0.1), grass)
    bark = material("Bark", (0.10, 0.07, 0.05), rough=0.9)
    leaves = [material("Leaves a", (0.10, 0.17, 0.05), rough=0.85), material("Leaves b", (0.16, 0.19, 0.05), rough=0.85)]
    rng = random.Random(seed)
    for k in range(48):
        x = rng.choice((-1, 1)) * rng.uniform(13, 60)
        y = rng.uniform(-240, 240)
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


def glow_material(name, colour, rough=0.8, metal=0.0):
    m = material(name, colour, metal=metal, rough=rough)
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Emission Color"].default_value = (1.0, 0.28, 0.05, 1.0)
    bsdf.inputs["Emission Strength"].default_value = 0.0
    return m


def set_glow(m, strength):
    m.node_tree.nodes.get("Principled BSDF").inputs["Emission Strength"].default_value = strength


def shreds(mat, seed=7):
    """Curled strips of tread from earlier blowouts on the shoulders (scenery, never on the car's path)."""
    rng = np.random.default_rng(seed)
    obs = []
    for k in range(30):
        side = -1 if k < 22 else 1
        x = side * rng.uniform(3.95, 5.0) if k % 4 else side * rng.uniform(3.1, 3.5)
        y = rng.uniform(-28.0, -9.0) if side < 0 and k < 14 else rng.uniform(-60.0, -2.0) if side < 0 else rng.uniform(-60.0, 20.0)
        length, width = rng.uniform(0.4, 1.3), rng.uniform(0.14, 0.22)
        curl, yaw = rng.uniform(0.1, 0.45), rng.uniform(-0.6, 0.6) + (math.pi / 2 if rng.random() < 0.3 else 0.0)
        n = 10
        verts, faces = [], []
        for i in range(n + 1):
            s = (i / n - 0.5) * length
            z = 0.008 + curl * (2 * i / n - 1) ** 2 * length * 0.5
            for wv in (-width / 2, width / 2):
                lx, ly = wv, s
                verts.append((x + lx * math.cos(yaw) - ly * math.sin(yaw), y + lx * math.sin(yaw) + ly * math.cos(yaw), z))
            if i:
                b = 2 * (i - 1)
                faces.append((b, b + 1, b + 3, b + 2))
        obs.append(mesh_object(f"Shred {k}", verts, faces, mat, thickness=0.012))
    return obs


def profile():
    """Outer cross-section from the outboard bead to the inboard bead: rows of (w, r, kind); w < 0 is outboard (the car's left)."""
    pts = []
    for i in range(9):
        s = i / 8
        pts.append((-(0.090 + 0.012 * math.sin(math.pi * s)), bm.RIM_R + 0.006 + s * (bm.R - 0.035 - bm.RIM_R - 0.006), "side", s))
    pts += [(-0.097, bm.R - 0.018, "shoulder", 0.0), (-0.085, bm.R - 0.005, "shoulder", 0.0)]
    for i in range(17):
        w = -0.075 + 0.15 * i / 16
        pts.append((w, bm.R, "tread", 0.0))
    pts += [(0.085, bm.R - 0.005, "shoulder", 0.0), (0.097, bm.R - 0.018, "shoulder", 0.0)]
    for i in range(9):
        s = 1 - i / 8
        pts.append(((0.090 + 0.012 * math.sin(math.pi * s)), bm.RIM_R + 0.006 + s * (bm.R - 0.035 - bm.RIM_R - 0.006), "side", s))
    return pts


PROFILE = profile()


def _groove(w):
    return 0.008 if min(abs(w - g) for g in (-0.04, 0.0, 0.04)) < 0.005 else 0.0


class Tyre:
    """The front-left tyre, rebuilt every frame in the wheel's non-rotating frame (X axle, outboard -X; Y forward; Z up)."""

    def __init__(self, rubber, belt, cap, glue):
        self.rubber, self.belt, self.cap, self.glue = rubber, belt, cap, glue
        self.obs = []

    def clear(self):
        for ob in self.obs:
            me = ob.data
            bpy.data.objects.remove(ob)
            bpy.data.meshes.remove(me)
        self.obs = []

    def _point(self, w, r, kind, s, a_world, a_mat, st, squash, lost):
        on_tread = kind in ("tread", "shoulder")
        if kind == "tread":
            r -= _groove(w)
            if (a_mat % (2 * math.pi / SIPES)) < 0.035:
                r -= 0.006
        if on_tread and not lost:
            r += st["sep"]
        span, lift = st["peel_span"], st["peel_lift"]
        in_peel = span > 0 and (a_mat % (2 * math.pi)) < span * 2 * math.pi
        if in_peel and on_tread:
            u = (a_mat % (2 * math.pi)) / (span * 2 * math.pi)
            r += lift * math.sin(math.pi * u) * (0.7 + 0.3 * math.sin(9 * a_mat + 40 * st["t"]))
        if lost and kind == "tread":
            r = bm.R - 0.016
        c = max(0.0, math.cos(a_world))
        rr = r - squash * c ** 6 * (r - bm.RIM_R) / (bm.R - bm.RIM_R)
        if kind == "side":
            bulge = 1 + 5.0 * squash * c ** 4 * math.sin(math.pi * s)
            if st["burst"]:
                bulge += 0.25 * c ** 2 * math.sin(math.pi * s) * (0.6 + 0.4 * math.sin(14 * a_world))
            w = w * bulge
        z = -rr * math.cos(a_world)
        floor = -(bm.R - squash)
        if z < floor:
            z = floor
        return (w, rr * math.sin(a_world), z)

    def set(self, st, spin, squash, cut=None, show=True):
        self.clear()
        if not show:
            return
        lost_span = 0.58 if st["burst"] else 0.0
        verts, faces, mats = [], [], []
        np_ = len(PROFILE)
        alphas = [2 * math.pi * i / N_A for i in range(N_A)]
        keep = [True] * N_A
        if cut:
            c0, c1 = math.radians(cut[0]), math.radians(cut[1])
            keep = [not (c0 < a < c1) for a in alphas]
        for a in alphas:
            a_mat = a + spin
            lost = lost_span > 0 and (a_mat % (2 * math.pi)) < lost_span * 2 * math.pi
            for (w, r, kind, s) in PROFILE:
                verts.append(self._point(w, r, kind, s, a, a_mat, st, squash, lost))
        for i in range(N_A):
            j = (i + 1) % N_A
            if not (keep[i] and keep[j]):
                continue
            a_mat = alphas[i] + spin
            lost = lost_span > 0 and (a_mat % (2 * math.pi)) < lost_span * 2 * math.pi
            torn = st["burst"] and 0.0 < ((a_mat - 0.3) % (2 * math.pi)) < math.radians(26)
            for k in range(np_ - 1):
                kind = PROFILE[k][2]
                if torn and kind == "side" and PROFILE[k][0] < 0 and 2 <= k <= 6:
                    continue                                           # the rupture in the outboard sidewall
                faces.append((i * np_ + k, j * np_ + k, j * np_ + k + 1, i * np_ + k + 1))
                mats.append(1 if (lost and kind == "tread") else 0)
        ob = mesh_object("FL tyre", verts, faces, self.rubber)
        ob.data.materials.append(self.belt)
        ob.data.polygons.foreach_set("material_index", mats)
        self.obs.append(ob)
        if st["peel_span"] > 0:                                        # the steel belt laid bare under the lifting strip
            bv, bf = [], []
            n = max(2, int(st["peel_span"] * N_A))
            for i in range(n + 1):
                a_mat = 2 * math.pi * st["peel_span"] * i / n
                a = a_mat - spin
                for w in (-0.07, 0.07):
                    bv.append(self._point(w, bm.R - 0.012, "belt", 0.0, a, a_mat, st, squash, False))
                if i:
                    b = 2 * (i - 1)
                    bf.append((b, b + 1, b + 3, b + 2))
            self.obs.append(mesh_object("Bare belt", bv, bf, self.belt))
        if cut:
            for ang in cut:
                self._cap(math.radians(ang), st, squash, spin)

    def _cap(self, a, st, squash, spin):
        """Section face at world angle a: rubber ring (sidewalls 10 mm, tread 22 mm), two steel belts, the glue line between them and the
        tread (it glows in the heat shots)."""
        def pt(w, r, kind="belt", s=0.0):
            return self._point(w, r, kind, s, a, a + spin, st, squash, False)
        outer = [pt(w, r, kind, s) for (w, r, kind, s) in PROFILE]
        inner = []
        for (w, r, kind, s) in PROFILE:
            t = 0.022 if kind == "tread" else 0.014 if kind == "shoulder" else 0.010
            wi = w - math.copysign(0.010, w) if kind == "side" else w
            inner.append(pt(wi, r - t if kind != "side" else r, "belt"))
        verts = outer + inner
        n = len(PROFILE)
        faces = [(k, k + 1, n + k + 1, n + k) for k in range(n - 1)]
        self.obs.append(mesh_object("Cap", verts, faces, self.cap, smooth=False))
        normal = Vector((0.0, math.cos(a), math.sin(a)))
        off = normal * -0.002
        for (r0, r1, mat, name) in ((bm.R - 0.020, bm.R - 0.016, self.belt, "Belt 1"), (bm.R - 0.015, bm.R - 0.011, self.belt, "Belt 2"),
                                    (bm.R - 0.010, bm.R - 0.008 + st["sep"], self.glue, "Glue")):
            v = [Vector(pt(w, r)) + off for (w, r) in ((-0.072, r0), (0.072, r0), (0.072, r1), (-0.072, r1))]
            self.obs.append(mesh_object(name, v, [(0, 1, 2, 3)], mat, smooth=False))


class Debris:
    def __init__(self, mat):
        self.obs = []
        for k, (_, _, _, size, _, kind) in enumerate(bm.debris()):
            self.obs.append(cube(f"Rubber {kind} {k}", (0, 0, -9), size, mat))

    def set(self, t, y_shift):
        air = out = 0
        for k, ob in enumerate(self.obs):
            p = bm.debris_pose(k, t)
            if p is None:
                ob.hide_render = True
                continue
            pos, rot, flying = p
            ob.hide_render = False
            ob.location = (pos[0], pos[1] - y_shift, pos[2])
            ob.rotation_euler = tuple(rot)
            out += 1
            air += flying
        return air, out


class Puff:
    """Dust and powder blown out of the carcass at the burst (fades in about 1.5 s)."""

    def __init__(self, n=16):
        m = bpy.data.materials.new("Dust")
        m.use_nodes = True
        nt = m.node_tree
        bsdf = nt.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = (0.62, 0.58, 0.52, 1.0)
        bsdf.inputs["Roughness"].default_value = 1.0
        info = nt.nodes.new("ShaderNodeObjectInfo")
        nt.links.new(info.outputs["Alpha"], bsdf.inputs["Alpha"])
        rng = np.random.default_rng(3)
        self.obs, self.specs = [], []
        for k in range(n):
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1.0, location=(0, 0, -9))
            ob = bpy.context.object
            ob.data.materials.append(m)
            ob.name = f"Dust {k}"
            self.obs.append(ob)
            self.specs.append((rng.uniform(0, 0.05), np.array([rng.uniform(-3.5, -0.5), rng.uniform(-1, 1), rng.uniform(0.3, 1.6)]), rng.uniform(0.7, 1.3)))

    def set(self, t, y_shift):
        w0 = bm.wheel_world(0.0)
        for ob, (tb, v, sc) in zip(self.obs, self.specs):
            tau = t - tb
            if tau < 0 or tau > 1.6:
                ob.hide_render = True
                continue
            ob.hide_render = False
            c = w0 + v * 0.35 * (1 - math.exp(-tau / 0.35)) + np.array([0, -bm.V0 * 0.15 * tau, 0.0])
            ob.location = (c[0], c[1] - y_shift, max(0.15, c[2]))
            ob.scale = (sc * (0.10 + 0.55 * math.sqrt(tau)),) * 3
            ob.color = (1, 1, 1, 0.45 * math.exp(-tau / 0.55))


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
    sun_to = cinematic.sun_vector((0.6, -0.7), 15.0)                 # low sun from the car's left front: the burst side is lit
    cinematic.apply_sky(scene, sun_to, strength=0.24, dust=0.7)
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    sun.data.energy, sun.data.angle = 6.5, 0.02
    sun.data.color = (1.0, 0.74, 0.48)
    sun.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()
    build_highway()
    wheel_nodes = {w["node"] for w in wheels.values()}
    parts = [o for o in root.children_recursive if o.type == "MESH" and not any(p in wheel_nodes for p in rb._ancestors(o))]
    ghost = rb.Ghost(parts)
    ghost.set_tint(PAINT)
    ghost.set_factor(0.0, 1e4, 4.0)
    fl = wheels["front_left"]
    for o in fl["node"].children_recursive:
        if "tire" in o.name:
            o.hide_render = True                                   # replaced by the procedural tyre
    rubber = glow_material("Tyre rubber", (0.035, 0.035, 0.04), rough=0.75)
    belt = material("Steel belt", (0.55, 0.55, 0.57), metal=0.85, rough=0.35)
    cap = glow_material("Tyre section", (0.09, 0.09, 0.10), rough=0.9)
    glue = glow_material("Belt bond", (0.20, 0.12, 0.06), rough=0.8)
    tyre = Tyre(rubber, belt, cap, glue)
    rim = material("Rim barrel", (0.30, 0.30, 0.32), metal=0.8, rough=0.35)
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=bm.RIM_R + 0.004, depth=bm.W - 0.03)
    barrel = bpy.context.object
    barrel.name = "Rim barrel"
    barrel.data.materials.append(rim)
    barrel.rotation_euler = (0.0, math.pi / 2, 0.0)
    debris = Debris(material("Torn rubber", (0.075, 0.075, 0.08), rough=0.55))
    puff = Puff()
    shreds(material("Old shreds", (0.05, 0.05, 0.055), rough=0.6))
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    r_t = geom["tyre_radius"]
    fl_base = fl["node"].location.copy()

    def render(sh, path):
        scene.render.resolution_x, scene.render.resolution_y = round(FRAME[0] * args.res_scale), round(FRAME[1] * args.res_scale)
        t, pt, ys = sh["t"], sh["pose_t"], sh["y_shift"]
        parked = sh["variant"] == "parked"
        if parked:
            p = bm.pressure_after(t)
            st = {"t": -1e3, "x": PARKED[0], "y": PARKED[1], "psi": 0.0, "dist": 0.0, "pressure": p, "squash": VIS_PARKED * bm.deflection(p),
                  "drop": 0.0, "peel_span": 0.0, "peel_lift": 0.0, "temp": bm.T_AMB, "sep": 0.0, "burst": False}
            ys = 0.0
        else:
            pose = bm.state(pt)
            st = bm.state(t)
            st.update({k: pose[k] for k in ("x", "y", "psi", "dist")})
        root.location = (st["x"], st["y"] - ys, 0.0)
        root.rotation_euler = (0.0, 0.0, st["psi"])
        drop = st["drop"]
        body.location = (0.0, 0.0, -0.5 * drop)
        body.rotation_euler = (-0.35 * drop, -0.6 * drop, 0.0)
        spin = st["dist"] / r_t
        for key, wh in wheels.items():
            wh["node"].rotation_mode = "ZXY"
            wh["node"].rotation_euler = (-spin, 0, 0)
        fl["node"].location = (fl_base.x, fl_base.y, fl_base.z - drop)
        bpy.context.view_layer.update()
        wc = fl["node"].matrix_world.translation.copy()
        tyre_ob_loc, tyre_rot = wc, (0.0, 0.0, st["psi"])
        tyre.set(st, spin, st["squash"], cut=sh.get("cut"))
        for ob in tyre.obs:
            ob.location, ob.rotation_euler = tyre_ob_loc, tyre_rot
        barrel.location = wc
        barrel.rotation_euler = (0.0, math.pi / 2, st["psi"])
        heat = 0.0
        if sh.get("heat"):
            heat = max(0.0, (st["temp"] - 45.0) / (bm.temp_eq(bm.P_LOW) - 45.0))
        set_glow(rubber, 2.2 * heat)
        set_glow(cap, 3.0 * heat)
        set_glow(glue, (2.0 + 6.0 * min(1.0, st["sep"] / 0.01)) * heat)
        if parked:
            air, out = 0, 0
            for ob in debris.obs:
                ob.hide_render = True
            for ob in puff.obs:
                ob.hide_render = True
        else:
            air, out = debris.set(t, ys)
            puff.set(t, ys)
        c = sh["cam"]
        if c["rel"] == "car":
            o = Vector(root.location)
        elif c["rel"] == "wheel":
            o = Vector(wc)
        else:
            o = Vector((0.0, 0.0, 0.0))
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
        return {"variant": sh["variant"], "t": round(t, 6), "pose_t": round(pt, 6), "y_shift": ys, "x": round(st["x"], 4), "y": round(st["y"], 4),
                "psi": round(st["psi"], 5), "pressure": round(st["pressure"], 3), "squash": round(st["squash"], 5), "peel_span": round(st["peel_span"], 4),
                "temp": round(st["temp"], 2), "heat_glow": round(heat, 3), "burst": bool(st["burst"]), "airborne": air, "pieces_out": out,
                "cut": sh.get("cut"), "wheel_x": round(wc.x, 4), "wheel_y_world": round(wc.y + ys, 4),
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
        print("BLOWOUT_FRAME " + json.dumps(info), flush=True)
    (args.out / f"blowout-frames-{frames[0]:05d}.json").write_text(json.dumps({"renderer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                                                              "frames": out}, indent=1))


if __name__ == "__main__":
    main()
