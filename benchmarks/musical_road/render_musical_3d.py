"""EP.24 musical road: 100 % 3D renderer (Blender, Cycles CPU), house style of EP.13-EP.23 (golden hour, depth of field). A straight
two-lane road across the high desert (sand, creosote bushes, Joshua trees, power poles, snow-capped mountains far off); in the
right-hand lane a stretch of grooves milled across the lane, note by note. The CC0 red sedan drives over it, its wheels turning and
its body jiggling over the grooves.

Everything comes from musical_motion: the grooves where the model cuts them (as designed or as built), the car's place and speed, the
wheel turn, a ring on the asphalt for every thump of the front tyre in the slow-motion shots, the grooves just played glowing in the
aerial shots, the plan's groove-to-groove bar against the crew's gap bar with the grooves sliding to where the crew cut them, and the
planned grooves as faint blue lines between the built ones. No text anywhere in the scene."""
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
from benchmarks.can_opener import render_opener_3d as K  # noqa: E402  (data-API mesh helpers)
from benchmarks.musical_road import musical_motion as mm  # noqa: E402
from benchmarks.musical_road import musical_timeline as tl  # noqa: E402
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402
from benchmarks.rock_net.render_rocknet_3d import cone_geom, merged, smooth_noise, textured  # noqa: E402

material = base.material
cube, boxes, cyl, cyl_geom, new_object, Sheet = K.cube, K.boxes, K.cyl, K.cyl_geom, K.new_object, K.Sheet
pieces_mesh, set_pieces = K.pieces_mesh, K.set_pieces
FRAME = (1080, 1920)
ROAD_HALF = 3.6
Y0, Y1 = -420.0, 700.0
MACRO_Y = -40.0                         # a patch of road where the spacing mistake is shown, away from the musical section
N_MACRO = 6
N_RINGS = 8
PAINT = (1.75, 0.30, 0.24)              # body paint multiplier on the CC0 car's light paint: the house red car


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


def groove_material(name, colour=(0.035, 0.034, 0.033)):
    """Dark milled grooves; a glow by world y (node values lo/hi/on) marks the grooves the front tyre has just played."""
    m = material(name, colour, rough=0.9)
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sep.inputs[0])
    lo, hi, on = (K.node_value(nt, k, 0.0) for k in ("lo", "hi", "on"))

    def math_(op, a, b):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        for i, v in enumerate((a, b)):
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                nt.links.new(v, n.inputs[i])
        return n.outputs[0]

    y = sep.outputs["Y"]
    inside = math_("MULTIPLY", math_("GREATER_THAN", y, lo.outputs[0]), math_("LESS_THAN", y, hi.outputs[0]))
    fade = math_("DIVIDE", math_("SUBTRACT", y, lo.outputs[0]), math_("MAXIMUM", math_("SUBTRACT", hi.outputs[0], lo.outputs[0]), 0.01))
    glow = math_("MULTIPLY", math_("MULTIPLY", inside, fade), on.outputs[0])
    bsdf.inputs["Emission Color"].default_value = (1.0, 0.78, 0.35, 1)
    nt.links.new(math_("MULTIPLY", glow, 6.0), bsdf.inputs["Emission Strength"])
    return m


def strips(name, ys, mat, width, x0, x1, z):
    """One thin box across the lane per y (grooves, ghost lines)."""
    items = [((0.5 * (x0 + x1), float(y), z), (x1 - x0, width, 0.002)) for y in ys]
    return boxes(name, items, mat)


class Desert:
    def __init__(self):
        sand = textured("Desert sand", (0.50, 0.40, 0.28), (0.66, 0.55, 0.40), 0.35, rough=0.95, bump=0.3)
        asphalt = textured("Desert asphalt", (0.17, 0.165, 0.16), (0.25, 0.245, 0.235), 3.0, rough=0.85, bump=0.15)
        gravel = textured("Shoulder gravel", (0.36, 0.31, 0.25), (0.52, 0.46, 0.38), 6.0, rough=0.95, bump=0.4)
        yellow = material("Centre line", (0.85, 0.62, 0.08), rough=0.6)
        white = material("Edge line", (0.85, 0.85, 0.80), rough=0.6)
        xs = np.concatenate([np.linspace(-1500, -60, 30), np.linspace(-58, -5, 28), np.linspace(5, 58, 28), np.linspace(60, 1500, 30)])
        ys = np.concatenate([np.linspace(-1800, Y0, 10), np.arange(Y0 + 10, Y1, 10.0), np.linspace(Y1, 2600, 12)])
        X, Y = np.meshgrid(xs, ys, indexing="ij")
        far = np.clip((np.abs(X) - 6.0) / 60.0, 0.0, 1.0)
        Z = -0.12 + far * (0.6 * smooth_noise(X, Y, 1.0) + 0.25 * np.sin(0.013 * X + 0.007 * Y)) + 0.02 * np.sin(1.7 * X) * np.sin(1.3 * Y)
        co = np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1)
        Sheet("Desert floor", co, K.grid_faces(len(xs), len(ys)), [sand], smooth=True)
        cube("Road", (0.0, (Y0 + Y1) / 2, -0.05), (2 * ROAD_HALF, Y1 - Y0, 0.1), asphalt)
        for sx in (-1, 1):
            cube(f"Shoulder {sx}", (sx * (ROAD_HALF + 0.7), (Y0 + Y1) / 2, -0.07), (1.4, Y1 - Y0, 0.1), gravel)
        boxes("Centre line", [((dx, (Y0 + Y1) / 2, 0.003), (0.10, Y1 - Y0, 0.006)) for dx in (-0.09, 0.09)], yellow)
        boxes("Edge lines", [((sx * 3.47, (Y0 + Y1) / 2, 0.003), (0.12, Y1 - Y0, 0.006)) for sx in (-1, 1)], white)
        rng = random.Random(24)
        bush = textured("Creosote", (0.16, 0.20, 0.08), (0.28, 0.30, 0.13), 3.0, rough=0.9, bump=0.5)
        parts = []
        for _ in range(520):
            x = rng.choice((-1, 1)) * rng.uniform(5.5, 140.0)
            y = rng.uniform(Y0 + 20, Y1 - 20)
            r = rng.uniform(0.35, 0.9)
            for k in range(3):
                c = (x + rng.uniform(-0.4, 0.4) * r, y + rng.uniform(-0.4, 0.4) * r, r * rng.uniform(0.45, 0.8))
                vs, fs = _blob(r * rng.uniform(0.55, 0.85), c, rng)
                parts.append((vs, fs))
        merged("Creosote bushes", parts, bush)
        bark = textured("Joshua bark", (0.22, 0.17, 0.12), (0.34, 0.27, 0.19), 5.0, rough=0.95, bump=0.6)
        spikes = textured("Joshua leaves", (0.20, 0.27, 0.10), (0.34, 0.40, 0.16), 9.0, rough=0.8, bump=0.8)
        trunks, leaves = [], []
        for _ in range(70):
            x = rng.choice((-1, 1)) * rng.uniform(7.0, 160.0)
            y = rng.uniform(Y0 + 20, Y1 - 20)
            h = rng.uniform(2.2, 4.5)
            trunks.append(cyl_geom(0.16, h, (x, y, h / 2), (0, 0, 0), 8))
            for b in range(rng.randint(2, 4)):
                a = rng.uniform(0, 2 * math.pi)
                tilt = rng.uniform(0.5, 1.0)
                L = rng.uniform(0.8, 1.6)
                z0 = h * rng.uniform(0.55, 0.95)
                tip = (x + L * math.sin(tilt) * math.cos(a), y + L * math.sin(tilt) * math.sin(a), z0 + L * math.cos(tilt))
                trunks.append(_segment(0.09, (x, y, z0), tip))
                leaves.append(_spiky(0.45, tip, rng))
            leaves.append(_spiky(0.5, (x, y, h), rng))
        merged("Joshua trunks", trunks, bark, smooth=True)
        merged("Joshua leaves", leaves, spikes)
        wood = material("Pole wood", (0.22, 0.16, 0.11), rough=0.9)
        wire = material("Wire", (0.05, 0.05, 0.05), metal=0.5, rough=0.5)
        poles, wires = [], []
        ys_p = np.arange(Y0, Y1, 55.0)
        for y in ys_p:
            poles.append(cyl_geom(0.14, 11.0, (-9.0, y, 5.5), (0, 0, 0), 8))
            poles.append((K.box_verts((-9.0, y, 10.4), (2.6, 0.14, 0.14)), K.BOX_FACES))
        merged("Power poles", poles, wood, smooth=True)
        for dx in (-1.15, 0.0, 1.15):
            for a, b in zip(ys_p[:-1], ys_p[1:]):
                pts = [(-9.0 + dx, a + (b - a) * u, 10.55 - 0.9 * 4 * u * (1 - u)) for u in np.linspace(0, 1, 7)]
                for p0, p1 in zip(pts[:-1], pts[1:]):
                    wires.append(_segment(0.012, p0, p1, verts=4))
        merged("Power lines", wires, wire)
        mtn = textured("Mountains", (0.17, 0.18, 0.22), (0.27, 0.27, 0.31), 0.004, rough=0.95, bump=0.2)
        snow = material("Snow caps", (0.92, 0.93, 0.96), rough=0.6)
        for name, cx, cy, w, d, hmax in (("Mountains north", 0.0, 9000.0, 26000.0, 3500.0, 1300.0), ("Mountains west", -9500.0, 1500.0, 3500.0, 16000.0, 800.0),
                                         ("Mountains south", 1500.0, -9500.0, 24000.0, 3000.0, 700.0)):
            nu, nv = 120, 30
            us = np.linspace(-w / 2, w / 2, nu)
            vs_ = np.linspace(-d / 2, d / 2, nv)
            U, V = np.meshgrid(us, vs_, indexing="ij")
            ridge = np.clip(1.0 - np.abs(V) / (d / 2), 0, 1) ** 1.3
            n1 = 0.55 + 0.25 * np.sin(U / 610.0 + 1.0) + 0.15 * np.sin(U / 230.0 + 2.0) + 0.05 * np.sin(U / 70.0)
            Zm = hmax * ridge * n1 - 40.0
            if name.endswith("north"):
                co = np.stack([cx + U, cy + V, Zm], -1).reshape(-1, 3)
            else:
                co = np.stack([cx + V, cy + U, Zm], -1).reshape(-1, 3)
            Sheet(name, co, K.grid_faces(nu, nv), [mtn], smooth=True)
            caps = co[co[:, 2] > 0.78 * hmax]
            cap_parts = [(_blob(70.0, tuple(p), random.Random(int(p[0]) ^ int(p[1])))) for p in caps[::3]]
            if cap_parts:
                merged(f"{name} snow", cap_parts, snow, smooth=True)


def _blob(r, c, rng):
    vs, fs = [], []
    seg, rings = 7, 5
    for i in range(1, rings):
        th = math.pi * i / rings
        for k in range(seg):
            ph = 2 * math.pi * k / seg
            rr = r * rng.uniform(0.8, 1.15)
            vs.append((c[0] + rr * math.sin(th) * math.cos(ph), c[1] + rr * math.sin(th) * math.sin(ph), c[2] + 0.75 * rr * math.cos(th)))
    top, bot = len(vs), len(vs) + 1
    vs += [(c[0], c[1], c[2] + 0.75 * r), (c[0], c[1], c[2] - 0.75 * r)]
    for i in range(rings - 2):
        for k in range(seg):
            a, b = i * seg + k, i * seg + (k + 1) % seg
            fs.append((a, b, b + seg, a + seg))
    for k in range(seg):
        fs.append((top, (k + 1) % seg, k))
        fs.append((bot, (rings - 2) * seg + k, (rings - 2) * seg + (k + 1) % seg))
    return vs, fs


def _segment(r, p0, p1, verts=6):
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    rot = d.to_track_quat("Z", "Y").to_euler()
    mid = (p0 + p1) / 2
    return cyl_geom(r, d.length, tuple(mid), tuple(rot), verts)


def _spiky(r, c, rng):
    """A Joshua-tree leaf cluster: a ball of thin spikes."""
    vs, fs = [], []
    for k in range(14):
        th = math.acos(rng.uniform(-0.4, 1.0))
        ph = rng.uniform(0, 2 * math.pi)
        d = Vector((math.sin(th) * math.cos(ph), math.sin(th) * math.sin(ph), math.cos(th)))
        base_pt = Vector(c)
        v, f = cone_geom(0.05, r * rng.uniform(0.8, 1.2), (0.0, 0.0, 0.0), verts=4)
        q = d.to_track_quat("Z", "Y")
        off = len(vs)
        vs += [tuple(base_pt + q @ Vector(p)) for p in v]
        fs += [tuple(i + off for i in ff) for ff in f]
    return vs, fs


class Grooves:
    """The musical section as designed and as built; faint blue planned grooves; the glow trail; the spacing-mistake patch."""

    def __init__(self):
        self.mats = {v: groove_material(f"Grooves {v}") for v in ("design", "built")}
        self.obs = {v: strips(f"Grooves {v}", mm.grooves(v), self.mats[v], mm.GROOVE_W, *mm.LANE_X, 0.0012) for v in ("design", "built")}
        ghost = material("Planned grooves", (0.10, 0.35, 1.0), rough=0.5, emission=3.0)
        self.ghost = strips("Planned grooves", mm.grooves("design"), ghost, 0.005, mm.LANE_X[0] + 0.3, mm.LANE_X[1] - 0.3, 0.0022)
        macro_m = material("Patch grooves", (0.035, 0.034, 0.033), rough=0.9)
        proto = K.box_verts((0.0, 0.0, 0.0), (mm.LANE_X[1] - mm.LANE_X[0], mm.GROOVE_W, 0.002))
        self.macro = pieces_mesh("Spacing patch grooves", proto, K.BOX_FACES, N_MACRO, macro_m)
        blue = material("Plan bar", (0.25, 0.55, 1.0), rough=0.5, emission=6.0)
        red = material("Crew bar", (1.0, 0.18, 0.12), rough=0.5, emission=6.0)
        self.blue = cube("Plan bar", (0, 0, 0), (1.0, 1.0, 1.0), blue)
        self.red = cube("Crew bar", (0, 0, 0), (1.0, 1.0, 1.0), red)
        self.s = mm.V_DESIGN / mm.freq("B3")

    def set(self, sh, front_y):
        v = sh["variant"]
        version = "built" if v in ("built", "compare") else "design"
        for k, ob in self.obs.items():
            ob.hide_render = k != version
        self.ghost.hide_render = v != "compare"
        glow = bool(sh.get("glow"))
        for k, m in self.mats.items():
            for n in m.node_tree.nodes:
                if n.type == "VALUE":
                    n.outputs[0].default_value = {"lo": front_y - 14.0, "hi": front_y, "on": 1.0 if glow else 0.0}[n.label]
        morph = 0.0
        if v == "gap":
            f = min(1.0, max(0.0, sh["t"]))
            morph = float(K.sstep(0.32, 0.72, f))
            s_now = self.s + mm.GROOVE_W * morph
            ys = MACRO_Y + s_now * np.arange(N_MACRO)
            xc = 0.5 * (mm.LANE_X[0] + mm.LANE_X[1])
            set_pieces(self.macro, np.stack([np.full(N_MACRO, xc), ys, np.full(N_MACRO, 0.0012)], 1))
            k = 2
            y_a, y_b = ys[k], ys[k + 1]
            xb = 2.2
            self.blue.location = (xb, MACRO_Y + self.s * k + self.s / 2, 0.006)
            self.blue.scale = (0.04, self.s, 0.004)                                           # groove to groove, as planned
            show_red = f > 0.3
            self.red.hide_render = not show_red
            gap = (y_b - y_a) - mm.GROOVE_W
            self.red.location = (xb - 0.09, y_a + mm.GROOVE_W / 2 + gap / 2, 0.006)
            self.red.scale = (0.04, max(0.001, gap), 0.004)                                   # the gap the crew measured
            self.blue.hide_render = False
            self.macro.ob.hide_render = False
        else:
            self.blue.hide_render = self.red.hide_render = True
            self.macro.ob.hide_render = True
        return version, morph


class Rings:
    """A ring on the asphalt for every thump of the front-right tyre, in slow motion only (drawn in film time)."""

    def __init__(self):
        m = material("Thump ring", (1.0, 0.95, 0.85), rough=0.5, emission=5.0)
        m.node_tree.nodes.get("Principled BSDF").inputs["Alpha"].default_value = 1.0
        info_mix = m
        self.obs = []
        for k in range(N_RINGS):
            v, f = K_ring(0.92, 1.0, 40)
            ob = new_object(f"Thump ring {k}", v, f, info_mix)
            self.obs.append(ob)
        tr = m.node_tree
        out = tr.nodes.get("Material Output")
        bsdf = tr.nodes.get("Principled BSDF")
        info = tr.nodes.new("ShaderNodeObjectInfo")
        mix = tr.nodes.new("ShaderNodeMixShader")
        tr.links.new(info.outputs["Alpha"], mix.inputs["Fac"])
        tr.links.new(tr.nodes.new("ShaderNodeBsdfTransparent").outputs[0], mix.inputs[1])
        tr.links.new(bsdf.outputs[0], mix.inputs[2])
        tr.links.new(mix.outputs[0], out.inputs["Surface"])

    def set(self, recent, car_y_now, x_tyre):
        """recent: [(film age s, y of the groove)] newest first."""
        shown = 0
        for k, ob in enumerate(self.obs):
            if k >= len(recent):
                ob.hide_render = True
                continue
            age, yg = recent[k]
            if age > 0.7:
                ob.hide_render = True
                continue
            ob.hide_render = False
            r = 0.06 + 0.9 * age
            ob.location = (x_tyre, yg, 0.004)
            ob.scale = (r, r, 1.0)
            ob.color = (1, 1, 1, max(0.0, 1.0 - age / 0.7) ** 1.5)
            shown += 1
        return shown


def K_ring(r_in, r_out, n):
    vs, fs = [], []
    for k in range(n):
        a = 2 * math.pi * k / n
        vs += [(r_in * math.cos(a), r_in * math.sin(a), 0.0), (r_out * math.cos(a), r_out * math.sin(a), 0.0)]
    for k in range(n):
        a, b = 2 * k, 2 * ((k + 1) % n)
        fs.append((a, b, b + 1, a + 1))
    return vs, fs


def film_time_of(seg, sim):
    lo_s, hi_s = min(seg["sim0"], seg["sim1"]), max(seg["sim0"], seg["sim1"])
    if not lo_s <= sim <= hi_s:
        return None
    lo, hi = seg["t0"], seg["t1"]
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        if tl.sim_time(seg, mid) < sim:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


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
    scene.view_settings.exposure = 0.15
    if hasattr(scene.view_settings, "use_white_balance"):
        scene.view_settings.use_white_balance = True
        scene.view_settings.white_balance_temperature = 7800.0
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    sun_to = cinematic.sun_vector((-0.45, 0.89), 12.0)                          # low sun behind the cameras that face the car's nose
    cinematic.apply_sky(scene, sun_to, strength=0.26, dust=1.0)
    sd = bpy.data.lights.new("Sun", "SUN")
    sd.energy, sd.angle, sd.color = 5.5, 0.02, (1.0, 0.68, 0.42)
    sun = bpy.data.objects.new("Sun", sd)
    scene.collection.objects.link(sun)
    sun.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()
    wheel_nodes = {w["node"] for w in wheels.values()}
    parts = [o for o in car_root.children_recursive if o.type == "MESH" and not any(p in wheel_nodes for p in rb._ancestors(o))]
    ghost = rb.Ghost(parts)
    ghost.set_tint(PAINT)
    ghost.set_factor(0.0, 1e4, 4.0)                                                 # fully solid (the ghost fade is for x-ray shots)
    Desert()
    grooves = Grooves()
    rings = Rings()
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    segs = tl.segments()
    x_tyre = mm.CAR_X - mm.TRACK / 2                                              # the front-left tyre, on the sunny side

    def render(sh, path):
        scene.render.resolution_x, scene.render.resolution_y = round(FRAME[0] * args.res_scale), round(FRAME[1] * args.res_scale)
        v, t = sh["variant"], sh["t"]
        cs = tl.car_state(sh)
        car_root.hide_render = False
        car_root.location = (mm.CAR_X, cs["y"], 0.0)
        car_root.rotation_euler = (0.0, 0.0, 0.0)
        body.location = (0.0, 0.0, cs["bounce"])
        for name, w in wheels.items():
            w["node"].rotation_euler = (-cs["wheel_angle"], 0.0, 0.0)
        for ob in car_root.children_recursive:
            ob.hide_render = not cs["visible"]
        front_y = cs["y"] + mm.FRONT_AXLE
        version, morph = grooves.set(sh, front_y)
        n_rings = 0
        if sh.get("rings") and cs["visible"]:
            seg = next(s for s in segs if s["label"] == sh["segment"])
            front, _ = mm.hits(version, cs["speed"])
            past = front[(front <= t) & (front >= t - 2.0)][::-1]
            recent = []
            for h in past[:N_RINGS]:
                ft = film_time_of(seg, float(h))
                if ft is not None:
                    recent.append((sh["film_t"] - ft, mm.START_Y + (mm.V_DESIGN if cs["speed"] == "design" else mm.V_SLOW) * float(h)))
            rate = len([a for a, _ in recent if a < 0.5]) / 0.5
            if rate > 14:
                recent = []
            n_rings = rings.set(recent, cs["y"], x_tyre)
        else:
            rings.set([], cs["y"], x_tyre)
        c = sh["cam"]
        o = Vector((mm.CAR_X, cs["y"], 0.0)) if c["rel"] == "car" else Vector((0.0, 0.0, 0.0))
        loc, tgt = o + Vector(c["loc"]), o + Vector(c["target"])
        dd = cam.data
        dd.sensor_fit, dd.sensor_width, dd.lens, dd.clip_start = "HORIZONTAL", 36.0, c["lens"], 0.02
        dd.clip_end = 12000.0
        dd.dof.use_dof = True
        dd.dof.focus_distance = (tgt - loc).length
        dd.dof.aperture_fstop = c.get("fstop", 8.0)
        base.set_camera(cam, loc, tgt)
        bpy.context.view_layer.update()
        lo = (mm.CAR_X - geom["body_half_width"], cs["y"] - geom["tail"], 0.0)
        hi = (mm.CAR_X + geom["body_half_width"], cs["y"] + geom["nose"], geom["roof"])
        box = hook_gate.project_box(scene, cam, Matrix.Identity(4), lo, hi)
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        return {"variant": v, "t": round(t, 6), "version": version, "speed": cs["speed"], "car_y": round(cs["y"], 4), "car_visible": cs["visible"],
                "wheel_angle": round(cs["wheel_angle"], 5), "note": cs["note"], "thump_rate": round(cs["thump_rate"], 3), "rings": n_rings,
                "glow": bool(sh.get("glow")), "morph": round(morph, 4), "ghost": v == "compare", "subject_box": box,
                "cam_world": [round(x, 3) for x in loc], "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

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
        print("MUSICAL_FRAME " + json.dumps(info), flush=True)
    (args.out / f"musical-frames-{frames[0]:05d}.json").write_text(json.dumps({"renderer_source_sha256": src_sha, "frames": out}, indent=1))


if __name__ == "__main__":
    main()
