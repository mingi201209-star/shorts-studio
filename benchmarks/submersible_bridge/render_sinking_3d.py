"""EP.27 submersible bridge: 100 % 3D renderer (Blender, Cycles CPU), house style of EP.13-EP.26 (sunlight, depth of field). The
mouth of the Corinth Canal: clear turquoise water between two breakwaters, the channel cutting inland between limestone walls that
rise to about 50 m, dry scrub and pines on the land, hills and the sea beyond. At the mouth the road crosses on a 33 m steel deck
between concrete quays; gates with red lights, cars waiting on both sides (the CC0 sedan in house red at the front), a small control
house. A tall ship with three masts comes in from the sea.

Everything moves from sinking_motion: the deck's height (down about 8 m into a pit in the bed at about 4 m a minute, back up after
the ship), the gates and the blinking lights, the ship's run, how wet the road looks; foam where the water floods over the road,
air bubbling out of the girders on the way down, a cloud of silt where it settles, sheets of water pouring off its edges as it
comes up. Underwater shots look through the water itself (a volume); the lift-bridge shot shows the towers a lift bridge would need
for the same masts, translucent. Painted depth bands on the quay walls show the speed. No text anywhere in the scene."""
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
from benchmarks.manhole_blast.render_manhole_3d import Nodes, principled, puff_material  # noqa: E402
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402
from benchmarks.rock_net.render_rocknet_3d import textured  # noqa: E402
from benchmarks.roller_barrier.render_roller_3d import Proto, box_proto, cyl_proto, np_mesh, np_mesh_flat, rot_z, stamp  # noqa: E402
from benchmarks.submersible_bridge import sinking_motion as sm  # noqa: E402
from benchmarks.submersible_bridge import sinking_timeline as tl  # noqa: E402
from benchmarks.submersible_bridge import sinking_world as sw  # noqa: E402

material = base.material
FRAME = (1080, 1920)
PAINT = (1.75, 0.30, 0.24)
HALF_L, HALF_W = sm.DECK_L / 2, sm.DECK_W / 2
GATE_X = 20.5
N_BUBBLES, N_DRIPS, N_SILT = 70, 90, 26


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


# ------------------------------------------------------------------ materials
def land_material():
    """Dry scrub on the land, layered limestone on the canal walls, concrete quays, sand on the bed and the beaches (per-point
    attributes from sinking_world.surface_kind)."""
    m, N, bsdf = principled("Land", rough=0.92)
    pos = N.new("ShaderNodeNewGeometry").outputs["Position"]
    _, _, z = N.xyz(pos)
    attr = {}
    for name in ("quay", "cliff", "bed", "beach"):
        a = N.new("ShaderNodeAttribute")
        a.attribute_name = name
        attr[name] = a.outputs["Fac"]
    fine = N.noise(pos, 3.0, 8.0)
    big = N.noise(pos, 0.06, 4.0)
    scrub = N.mix(N.math("GREATER_THAN", big, 0.47), N.mix(fine, (0.22, 0.20, 0.11), (0.33, 0.29, 0.17)), N.mix(fine, (0.07, 0.10, 0.04), (0.13, 0.16, 0.06)))
    warp = N.math("ADD", z, N.math("MULTIPLY", N.noise(pos, 0.4, 3.0), 1.6))
    band = N.math("SINE", N.math("MULTIPLY", warp, 2.3))
    strata = N.mix(N.math("MULTIPLY_ADD", band, 0.5, 0.5), (0.62, 0.53, 0.38), (0.80, 0.72, 0.56))
    rock = N.mix(N.math("MULTIPLY", fine, 0.6), strata, (0.50, 0.43, 0.32))
    concrete = N.mix(fine, (0.48, 0.47, 0.44), (0.62, 0.61, 0.58))
    sand = N.mix(fine, (0.62, 0.55, 0.40), (0.76, 0.69, 0.52))
    c = N.mix(attr["cliff"], scrub, rock)
    c = N.mix(attr["quay"], c, concrete)
    c = N.mix(attr["bed"], c, N.mix(fine, (0.42, 0.40, 0.33), (0.55, 0.52, 0.43)))
    c = N.mix(attr["beach"], c, sand)
    N.put(bsdf.inputs["Base Color"], c)
    bp = N.new("ShaderNodeBump", Strength=0.6)
    N.put(bp.inputs["Height"], N.math("ADD", fine, N.math("MULTIPLY", band, 0.3)))
    N.put(bsdf.inputs["Normal"], bp.outputs["Normal"])
    return m


def water_material():
    """Clear Mediterranean water: a refracting, gently rippled surface and a turquoise volume (even density: fast)."""
    m = bpy.data.materials.new("Sea water")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    N = Nodes(nt)
    out = N.new("ShaderNodeOutputMaterial")
    pos = N.new("ShaderNodeTexCoord").outputs["Object"]
    surf = N.new("ShaderNodeBsdfPrincipled")
    N.put(surf.inputs["Base Color"], (0.92, 0.98, 1.0))
    N.put(surf.inputs["Roughness"], 0.03)
    N.put(surf.inputs["IOR"], 1.333)
    N.put(surf.inputs["Transmission Weight"], 1.0)
    ripples = N.math("ADD", N.noise(pos, 0.9, 3.0), N.math("MULTIPLY", N.noise(pos, 0.12, 2.0), 1.5))
    bp = N.new("ShaderNodeBump", Strength=0.12, Distance=0.2)
    N.put(bp.inputs["Height"], ripples)
    N.put(surf.inputs["Normal"], bp.outputs["Normal"])
    N.put(out.inputs["Surface"], surf.outputs[0])
    absorb = N.new("ShaderNodeVolumeAbsorption", Color=(0.30, 0.78, 0.80), Density=0.14)
    scat = N.new("ShaderNodeVolumeScatter", Color=(0.35, 0.80, 0.85), Density=0.012, Anisotropy=0.55)
    add = N.new("ShaderNodeAddShader")
    N.put(add.inputs[0], absorb.outputs[0])
    N.put(add.inputs[1], scat.outputs[0])
    N.put(out.inputs["Volume"], add.outputs[0])
    return m


def road_material(name):
    """Asphalt that darkens and shines when wet (node 'wet' set per frame)."""
    m, N, bsdf = principled(name, rough=0.8)
    pos = N.new("ShaderNodeTexCoord").outputs["Object"]
    wet = N.value("wet", 0.0)
    grain = N.noise(pos, 6.0, 6.0)
    dry = N.mix(grain, (0.085, 0.085, 0.09), (0.15, 0.15, 0.155))
    soaked = N.mix(grain, (0.03, 0.032, 0.035), (0.06, 0.062, 0.066))
    N.put(bsdf.inputs["Base Color"], N.mix(wet, dry, soaked))
    N.put(bsdf.inputs["Roughness"], N.math("MULTIPLY_ADD", wet, -0.72, 0.85))
    return m


def foam_material(name, value_label, base_alpha=0.9):
    """White water broken up by noise; its strength is a node value set per frame."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    N = Nodes(nt)
    out = N.new("ShaderNodeOutputMaterial")
    pos = N.new("ShaderNodeTexCoord").outputs["Object"]
    k = N.value(value_label, 0.0)
    nz = N.noise(pos, 1.8, 6.0)
    streak = N.noise(pos, 7.0, 3.0)
    alpha = N.math("MULTIPLY", k, N.math("MULTIPLY", N.math("MULTIPLY_ADD", nz, 2.6, -0.95, clamp=True), N.math("MULTIPLY_ADD", streak, 0.8, 0.5)), clamp=True)
    alpha = N.math("MULTIPLY", alpha, base_alpha)
    white = N.new("ShaderNodeBsdfPrincipled")
    N.put(white.inputs["Base Color"], (0.95, 0.97, 0.98))
    N.put(white.inputs["Roughness"], 0.35)
    mix = N.new("ShaderNodeMixShader")
    N.put(mix.inputs["Fac"], alpha)
    N.put(mix.inputs[1], N.new("ShaderNodeBsdfTransparent").outputs[0])
    N.put(mix.inputs[2], white.outputs[0])
    N.put(out.inputs["Surface"], mix.outputs[0])
    return m


def ghost_material():
    m = bpy.data.materials.new("Ghost lift bridge")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    N = Nodes(nt)
    out = N.new("ShaderNodeOutputMaterial")
    lw = N.new("ShaderNodeLayerWeight", Blend=0.35)
    em = N.new("ShaderNodeEmission", Color=(0.45, 0.85, 1.0), Strength=4.0)
    mix = N.new("ShaderNodeMixShader")
    N.put(mix.inputs["Fac"], N.math("MULTIPLY_ADD", lw.outputs["Facing"], 0.5, 0.35, clamp=True))
    N.put(mix.inputs[1], N.new("ShaderNodeBsdfTransparent").outputs[0])
    N.put(mix.inputs[2], em.outputs[0])
    N.put(out.inputs["Surface"], mix.outputs[0])
    return m


# ------------------------------------------------------------------ the land, the water, the town
def grid_mesh(name, xs, ys, fz, mats, attrs=None, smooth=True):
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    Z = fz(X.ravel(), Y.ravel())
    co = np.stack([X.ravel(), Y.ravel(), Z], 1)
    nu, nv = len(xs), len(ys)
    i = (np.arange(nu - 1)[:, None] * nv + np.arange(nv - 1)[None, :]).ravel()
    q = np.stack([i, i + nv, i + nv + 1, i + 1], 1)
    ob = np_mesh_flat(name, co, q.ravel(), np.full(len(q), 4, np.int32), mats, smooth=smooth)
    if attrs:
        for k, v in attrs(X.ravel(), Y.ravel()).items():
            a = ob.data.attributes.new(k, "FLOAT", "POINT")
            a.data.foreach_set("value", np.asarray(v, np.float32))
    return ob


def build_land():
    xs = np.concatenate([np.linspace(-4000, -420, 10), np.arange(-420, -80, 8.0), np.arange(-80, -24, 1.5), np.arange(-24, 24.001, 0.35),
                         np.arange(25.5, 80, 1.5), np.arange(80, 420, 8.0), np.linspace(420, 4000, 10)])
    ys = np.concatenate([np.linspace(-4000, -420, 10), np.arange(-420, -120, 6.0), np.arange(-120, -16, 1.5), np.arange(-16, 16, 0.5),
                         np.arange(16, 400, 1.5), np.arange(400, 3200, 6.0), np.linspace(3200, 7000, 8)])

    def attrs(x, y):
        q, c, b, s = sw.surface_kind(x, y)
        return {"quay": q, "cliff": c, "bed": b, "beach": s}

    return grid_mesh("Land and canal", xs, ys, sw.ground_z, [land_material()], attrs)


def build_water():
    """One closed body of water: the surface at z = 0, sides and bottom well inside the land and the sea floor."""
    co = K.box_verts((0.0, 0.0, -30.0), (9000.0, 15000.0, 60.0))
    co = [(x, y, min(z, 0.0)) for x, y, z in co]
    ob = K.new_object("Sea water", co, K.BOX_FACES, water_material())
    ob.visible_shadow = False                                          # the sun reaches what is under water (light through the surface)
    return ob


def build_ridges():
    mtn = textured("Far hills", (0.30, 0.30, 0.25), (0.42, 0.40, 0.32), 0.004, rough=0.95, bump=0.2)
    for name, cx, cy, w, dd, hmax, along_x in (("Hills across the gulf", 0.0, -9000.0, 26000.0, 3000.0, 900.0, True),
                                                ("Hills inland", 2000.0, 7800.0, 20000.0, 3000.0, 700.0, True),
                                                ("Hills east", 7000.0, 0.0, 16000.0, 2600.0, 600.0, False),
                                                ("Hills west", -7000.0, 1500.0, 16000.0, 2600.0, 750.0, False)):
        nu, nv = 140, 26
        us = np.linspace(-w / 2, w / 2, nu)
        vs = np.linspace(-dd / 2, dd / 2, nv)
        U, V = np.meshgrid(us, vs, indexing="ij")
        ridge = np.clip(1.0 - np.abs(V) / (dd / 2), 0, 1) ** 1.2
        n1 = 0.55 + 0.25 * np.sin(U / 620.0 + 1.0 + cx * 0.001) + 0.15 * np.sin(U / 210.0 + 2.0) + 0.05 * np.sin(U / 70.0)
        Zm = hmax * ridge * n1 - 40.0
        co = np.stack([cx + U, cy + V, Zm], -1).reshape(-1, 3) if along_x else np.stack([cx + V, cy + U, Zm], -1).reshape(-1, 3)
        i = (np.arange(nu - 1)[:, None] * nv + np.arange(nv - 1)[None, :]).ravel()
        q = np.stack([i, i + nv, i + nv + 1, i + 1], 1)
        np_mesh_flat(name, co, q.ravel(), np.full(len(q), 4, np.int32), [mtn], smooth=True)


def build_vegetation():
    rng = np.random.default_rng(27)
    n = 9000
    x = rng.uniform(-600, 600, n)
    y = rng.uniform(-60, 1200, n)
    z = sw.ground_z(x, y)
    land = sw.land_level(x, y)
    keep = (z > land - 0.05) & (np.abs(x) > sw.canal_half_width(y) + 8.0) & ~((np.abs(y) < 14) & (np.abs(x) < 70)) & (z > 0.8)
    keep &= ~((np.abs(y) < 5.0) & (np.abs(x) < 200))                   # not on the road
    x, y, z = x[keep], y[keep], z[keep]
    pine = Proto(*K.cyl_geom(0.22, 5.0, (0.0, 0.0, 2.5), (0, 0, 0), 6), [1] * 8)
    jit = random.Random(4)
    for k in range(5):                                                   # an umbrella pine's flat crown
        a = 2 * math.pi * k / 5
        vs, fs = [], []
        r = 2.4
        c = (1.2 * math.cos(a), 1.2 * math.sin(a), 5.6 + jit.uniform(-0.3, 0.3))
        seg = 8
        for j in range(seg):
            ph = 2 * math.pi * j / seg
            vs.append((c[0] + r * math.cos(ph), c[1] + r * math.sin(ph), c[2]))
        vs += [(c[0], c[1], c[2] + 1.1), (c[0], c[1], c[2] - 0.5)]
        for j in range(seg):
            fs.append((j, (j + 1) % seg, seg))
            fs.append(((j + 1) % seg, j, seg + 1))
        pine = pine + Proto(vs, fs, [0] * len(fs))
    shrub = Proto(*K.cyl_geom(1.0, 0.9, (0.0, 0.0, 0.45), (0, 0, 0), 7), [0] * 9)
    needles = textured("Pine crowns", (0.07, 0.11, 0.05), (0.13, 0.17, 0.08), 1.5, rough=0.9, bump=0.5)
    bark = material("Pine bark", (0.16, 0.11, 0.08), rough=0.9)
    scrub = textured("Scrub", (0.16, 0.17, 0.08), (0.28, 0.27, 0.13), 2.0, rough=0.9, bump=0.6)
    xp, xs_ = [], []
    for k in range(len(x)):
        sc = rng.uniform(0.7, 1.4)
        rot = rot_z(rng.uniform(0, 2 * math.pi)) * sc
        tr = np.array([x[k], y[k], z[k] - 0.1])
        (xp if rng.random() < 0.3 else xs_).append((rot, tr))
    stamp("Umbrella pines", pine, [needles, bark], xp)
    stamp("Scrub", shrub, [scrub], xs_, smooth=True)
    return len(x)


def build_quays_and_roads():
    asphalt = road_material("Approach asphalt")
    white = material("Road paint", (0.86, 0.86, 0.82), rough=0.5)
    kerb = textured("Kerb concrete", (0.55, 0.54, 0.50), (0.68, 0.67, 0.63), 3.0, rough=0.85, bump=0.2)
    rail = material("Railing", (0.70, 0.71, 0.72), metal=0.8, rough=0.35)
    red = material("Depth band red", (0.75, 0.06, 0.04), rough=0.5)
    whiteb = material("Depth band white", (0.88, 0.88, 0.85), rough=0.5)
    for sx in (-1, 1):
        x0, x1 = sx * (sw.QUAY_X + 0.02), sx * 260.0
        cx, lx = 0.5 * (x0 + x1), abs(x1 - x0)
        K.cube(f"Approach road {sx}", (cx, 0.0, sw.ROAD_Z - 0.02), (lx, sm.DECK_W, 0.06), asphalt)
        K.boxes(f"Approach lines {sx}", [((cx, 0.0, sw.ROAD_Z + 0.013), (lx, 0.12, 0.006)),
                                         ((cx, 3.2, sw.ROAD_Z + 0.013), (lx, 0.12, 0.006)), ((cx, -3.2, sw.ROAD_Z + 0.013), (lx, 0.12, 0.006))], white)
        K.boxes(f"Sidewalks {sx}", [((cx, sy * 4.3, sw.ROAD_Z + 0.08), (lx, 1.6, 0.2)) for sy in (-1, 1)], kerb)
        posts = [((sx * (sw.QUAY_X + 0.4), y, sw.ROAD_Z + 0.55), (0.08, 0.08, 1.1)) for y in np.arange(-14.0, 14.1, 2.0) if abs(y) > 5.2]
        posts += [((sx * (sw.QUAY_X + 0.4), sy * 9.6, sw.ROAD_Z + 1.05), (0.06, 8.8, 0.06)) for sy in (-1, 1)]
        K.boxes(f"Quay railing {sx}", posts, rail)
        bands_r, bands_w = [], []
        for k in range(20):                                              # depth bands every half metre on the quay faces at the deck's ends
            z0 = sw.ROAD_Z - 0.5 * (k + 1)
            if z0 < sm.CANAL_BED:
                break
            for y0 in (-HALF_W - 0.9, HALF_W + 0.9):
                (bands_r if k % 2 == 0 else bands_w).append(((sx * (sw.QUAY_X - 0.01), y0, z0 + 0.25), (0.02, 0.6, 0.5)))
        K.boxes(f"Depth bands red {sx}", bands_r, red)
        K.boxes(f"Depth bands white {sx}", bands_w, whiteb)


def build_town():
    rng = random.Random(9)
    white = textured("House walls", (0.86, 0.84, 0.78), (0.94, 0.92, 0.87), 3.0, rough=0.8, bump=0.1)
    roof = material("Terracotta", (0.55, 0.22, 0.12), rough=0.8)
    blue = material("Shutters", (0.10, 0.25, 0.55), rough=0.6)
    boxes_w, boxes_r, boxes_b = [], [], []
    spots = [(-34.0, -14.0), (-46.0, -16.0), (-58.0, -13.0), (36.0, -15.0), (48.0, -17.0), (62.0, -14.0), (-40.0, 16.0), (44.0, 17.0),
             (-75.0, -20.0), (80.0, -22.0), (-90.0, 14.0), (95.0, 15.0)]
    for x, y in spots:
        w, d, h = rng.uniform(6, 10), rng.uniform(6, 9), rng.uniform(3.2, 6.5)
        z0 = float(sw.ground_z(np.array([x]), np.array([y]))[0])
        boxes_w.append(((x, y, z0 + h / 2), (w, d, h)))
        boxes_r.append(((x, y, z0 + h + 0.25), (w + 0.4, d + 0.4, 0.5)))
        for k in range(2):
            boxes_b.append(((x + (k - 0.5) * w * 0.45, y - d / 2 - 0.03, z0 + h * 0.55), (0.9, 0.06, 1.2)))
    K.boxes("Houses", boxes_w, white)
    K.boxes("Roofs", boxes_r, roof)
    K.boxes("Shutters", boxes_b, blue)
    ctl = (-24.0, 9.5)                                                   # the bridge keeper's house
    K.cube("Control house", (ctl[0], ctl[1], sw.ROAD_Z + 1.8), (5.0, 4.0, 3.6), white)
    K.cube("Control house roof", (ctl[0], ctl[1], sw.ROAD_Z + 3.75), (5.6, 4.6, 0.3), material("Flat roof", (0.5, 0.5, 0.48), rough=0.8))
    glass = material("Control house glass", (0.05, 0.08, 0.1), metal=0.3, rough=0.1)
    K.cube("Control house window", (ctl[0] + 1.0, ctl[1] - 2.02, sw.ROAD_Z + 2.2), (2.6, 0.06, 1.3), glass)


# ------------------------------------------------------------------ the bridge
class Deck:
    """The 33 m steel deck: the road (asphalt that looks wet when it has been under), lines, kerbs and railings on top, box girders
    and cross beams under it; all hung from one empty that moves in z."""

    def __init__(self):
        self.root = bpy.data.objects.new("Deck", None)
        bpy.context.collection.objects.link(self.root)
        steel = material("Deck steel", (0.30, 0.33, 0.34), metal=0.6, rough=0.45)
        self.road = road_material("Deck asphalt")
        white = material("Deck paint", (0.86, 0.86, 0.82), rough=0.5)
        rail = material("Deck railing", (0.70, 0.71, 0.72), metal=0.8, rough=0.35)
        parts = [
            K.cube("Deck road", (0.0, 0.0, -0.04), (sm.DECK_L, sm.DECK_W, 0.08), self.road),
            K.boxes("Deck lines", [((0.0, 0.0, 0.003), (sm.DECK_L, 0.12, 0.006)), ((0.0, 3.2, 0.003), (sm.DECK_L, 0.12, 0.006)),
                                   ((0.0, -3.2, 0.003), (sm.DECK_L, 0.12, 0.006))], white),
            K.boxes("Deck girders", [((0.0, y, -0.85), (sm.DECK_L - 0.2, 0.5, 1.5)) for y in (-3.0, -1.0, 1.0, 3.0)]
                    + [((x, 0.0, -1.45), (0.4, sm.DECK_W - 0.2, 0.3)) for x in np.arange(-15.0, 15.1, 3.0)]
                    + [((sx * (HALF_L - 0.15), 0.0, -0.8), (0.3, sm.DECK_W, 1.6)) for sx in (-1, 1)], steel),
            K.boxes("Deck kerbs", [((0.0, sy * (HALF_W - 0.15), 0.12), (sm.DECK_L, 0.3, 0.24)) for sy in (-1, 1)], steel),
            K.boxes("Deck railings", [((x, sy * (HALF_W - 0.15), 0.6), (0.07, 0.07, 0.95)) for x in np.arange(-15.5, 15.6, 2.2) for sy in (-1, 1)]
                    + [((0.0, sy * (HALF_W - 0.15), 1.05), (sm.DECK_L - 0.6, 0.06, 0.06)) for sy in (-1, 1)], rail),
        ]
        for ob in parts:
            ob.parent = self.root
        self.parts = parts

    def set(self, t):
        z = sm.deck_z(t)
        self.root.location = (0.0, 0.0, z)
        K.node_value(self.road.node_tree, "wet", sm.wet(t))
        return z


class Gates:
    """Barrier arms (red and white) across each approach, swinging down from sinking_motion.gates_down, and red lights that blink."""

    def __init__(self):
        stripe, N, bsdf = principled("Gate arm", rough=0.45)                  # red and white bands along the arm
        pos = N.new("ShaderNodeTexCoord").outputs["Object"]
        _, ay, _ = N.xyz(pos)
        band = N.math("GREATER_THAN", N.math("FRACT", N.math("DIVIDE", ay, 0.9)), 0.5)
        N.put(bsdf.inputs["Base Color"], N.mix(band, (0.80, 0.04, 0.03), (0.92, 0.92, 0.90)))
        post = material("Gate post", (0.8, 0.8, 0.78), rough=0.6)
        self.lamp = material("Gate lamp", (1.0, 0.05, 0.02), rough=0.4, emission=0.0)
        self.arms, self.lamps = [], []
        for sx in (-1, 1):
            px, py = sx * GATE_X, -sx * 4.4
            K.cube(f"Gate post {sx}", (px, py, sw.ROAD_Z + 0.6), (0.35, 0.35, 1.2), post)
            pivot = bpy.data.objects.new(f"Gate pivot {sx}", None)
            bpy.context.collection.objects.link(pivot)
            pivot.location = (px, py, sw.ROAD_Z + 1.05)
            arm = K.cube(f"Gate arm {sx}", (0.0, sx * 3.6, 0.0), (0.12, 7.2, 0.12), stripe)
            arm.parent = pivot
            self.arms.append((pivot, sx))
            for k, dz in enumerate((2.3, 2.3)):
                lp = K.cube(f"Gate lamp {sx}{k}", (px + 0.0, py + (k - 0.5) * 0.5, sw.ROAD_Z + dz), (0.25, 0.22, 0.22), self.lamp)
                self.lamps.append(lp)
            K.cube(f"Lamp post {sx}", (px, py, sw.ROAD_Z + 1.6), (0.12, 0.12, 1.6), post)

    def set(self, t, film_t):
        d = sm.gates_down(t)
        for pivot, sx in self.arms:
            pivot.rotation_euler = (sx * (1.0 - d) * math.radians(85.0), 0.0, 0.0)
        on = sm.lights_on(t) and int(film_t * 2.5) % 2 == 0
        s = self.lamp.node_tree.nodes.get("Principled BSDF")
        s.inputs["Emission Color"].default_value = (1.0, 0.06, 0.02, 1)
        s.inputs["Emission Strength"].default_value = 30.0 if on else 0.0
        return d


class TallShip:
    """A three-masted tall ship (46 m, 8.2 m beam, 3.8 m draft, masts 38 m above the water), sails furled, motoring along +y."""

    def __init__(self):
        self.root = bpy.data.objects.new("Tall ship", None)
        bpy.context.collection.objects.link(self.root)
        L, B, D = sm.SHIP_L, sm.SHIP_BEAM, sm.SHIP_DRAFT
        hull_dark = material("Hull", (0.03, 0.05, 0.10), rough=0.45)
        anti = material("Antifouling", (0.35, 0.07, 0.05), rough=0.6)
        stripe = material("Hull stripe", (0.85, 0.82, 0.70), rough=0.5)
        teak = textured("Teak deck", (0.32, 0.20, 0.11), (0.45, 0.30, 0.17), 3.0, rough=0.7, bump=0.2)
        spar = material("Spars", (0.32, 0.22, 0.13), rough=0.6)
        sail = textured("Furled sails", (0.86, 0.84, 0.78), (0.95, 0.94, 0.90), 4.0, rough=0.9, bump=0.3)
        white = material("Deckhouse", (0.9, 0.9, 0.88), rough=0.6)
        rope = material("Rigging", (0.08, 0.07, 0.06), rough=0.8)
        nu, nz = 40, 9
        zs = np.linspace(-D, 2.4, nz)
        co, faces, mi = [], [], []
        for i in range(nu):
            u = i / (nu - 1)                                              # 0 = bow, 1 = stern
            y = -u * L
            full = math.sin(math.pi * min(1.0, u * 1.15 + 0.04)) ** 0.55 if u < 0.85 else 0.75 + 0.25 * (1 - u) / 0.15
            full = max(0.05, full) if u > 0.0 else 0.02
            for j, z in enumerate(zs):
                v = (z + D) / (2.4 + D)
                keel = v ** 0.6
                half = B / 2 * full * (0.18 + 0.82 * keel)
                zz = z
                if u < 0.12:                                              # the stem rakes forward and the keel rises at the bow
                    zz = max(z, -D + (0.12 - u) / 0.12 * (D + 0.5))
                    y_off = (z + D) / (2.4 + D) * 2.0 * (0.12 - u) / 0.12
                else:
                    y_off = 0.0
                if u > 0.9:
                    zz = max(z, -D + (u - 0.9) / 0.1 * (D - 0.5))
                co.append((half, y + y_off, zz))
        base = len(co)
        for i in range(nu):
            for j in range(nz):
                x, y, z = co[i * nz + j]
                co.append((-x, y, z))
        for side, off in ((1, 0), (-1, base)):
            for i in range(nu - 1):
                for j in range(nz - 1):
                    a, b = off + i * nz + j, off + (i + 1) * nz + j
                    f = (a, b, b + 1, a + 1) if side == 1 else (a, a + 1, b + 1, b)
                    faces.append(f)
                    zc = zs[j]
                    mi.append(1 if zc < -0.1 else (2 if 1.0 < zc < 1.6 else 0))
        for i in range(nu - 1):                                           # the deck
            faces.append((base + i * nz + nz - 1, base + (i + 1) * nz + nz - 1, (i + 1) * nz + nz - 1, i * nz + nz - 1))
            mi.append(3)
        for i in range(nu - 1):                                           # the keel line
            faces.append((i * nz, (i + 1) * nz, base + (i + 1) * nz, base + i * nz))
            mi.append(1)
        faces.append(tuple([(nu - 1) * nz + j for j in range(nz)] + [base + (nu - 1) * nz + j for j in range(nz)][::-1]))
        mi.append(0)
        hull = np_mesh("Ship hull", co, faces, [hull_dark, anti, stripe, teak], mi, smooth=True)
        hull.parent = self.root
        parts = [hull]
        parts.append(K.boxes("Deckhouses", [((0.0, -L * 0.62, 3.3), (4.0, 7.0, 1.8)), ((0.0, -L * 0.88, 3.6), (5.0, 4.0, 2.4))], white))
        masts = []
        for k, frac in enumerate((0.24, 0.47, 0.70)):
            y = -L * frac
            h = sm.MAST_H - (k == 2) * 3.0
            masts.append((y, h))
        mast_parts, yard_parts, sail_parts, rig = [], [], [], []
        for y, h in masts:
            mast_parts.append(K.cyl_geom(0.28, h - 2.4, (0.0, y, 2.4 + (h - 2.4) / 2), (0, 0, 0), 10))
            for zy, half in ((h * 0.42, 7.5), (h * 0.58, 6.4), (h * 0.72, 5.2), (h * 0.85, 4.0)):
                yard_parts.append(K.cyl_geom(0.13, 2 * half, (0.0, y, zy), (0, math.pi / 2, 0), 8))
                sail_parts.append(K.cyl_geom(0.32, 2 * half - 0.6, (0.0, y + 0.25, zy - 0.15), (0, math.pi / 2, 0), 8))
            for sxx in (-1, 1):
                for dy in (-1.2, 0.0, 1.2):
                    p0 = Vector((sxx * (B / 2 - 0.3), y + dy, 2.4))
                    p1 = Vector((0.0, y, h - 0.5))
                    d = p1 - p0
                    rig.append(K.cyl_geom(0.025, d.length, tuple((p0 + p1) / 2), tuple(d.to_track_quat("Z", "Y").to_euler()), 4))
        bow_sprit = K.cyl_geom(0.22, 11.0, (0.0, 4.0, 3.6), (math.radians(-80), 0, 0), 8)
        from benchmarks.rock_net.render_rocknet_3d import merged
        parts += [merged("Masts", mast_parts + [bow_sprit], spar, smooth=True), merged("Yards", yard_parts, spar, smooth=True),
                  merged("Furled sails", sail_parts, sail, smooth=True), merged("Rigging", rig, rope)]
        for ob in parts[1:]:
            ob.parent = self.root
        wake = bpy.data.meshes.new("Wake")
        wv = [(0.0, 1.5, 0.02), (-B / 2 - 0.6, -2.0, 0.02), (B / 2 + 0.6, -2.0, 0.02), (-B / 2 - 9.0, -L - 30.0, 0.02), (B / 2 + 9.0, -L - 30.0, 0.02),
              (-B / 2 + 0.5, -L, 0.02), (B / 2 - 0.5, -L, 0.02)]
        wake.from_pydata(wv, [], [(0, 2, 4, 6, 5, 3, 1)])
        wake.materials.append(foam_material("Wake foam", "wake", 0.75))
        self.wake = bpy.data.objects.new("Wake", wake)
        bpy.context.collection.objects.link(self.wake)
        self.wake.parent = self.root
        self.wake_mat = wake.materials[0]
        self.parts = parts + [self.wake]

    def set(self, t):
        y = sm.ship_bow_y(t)
        self.root.location = (0.0, y, 0.0)
        K.node_value(self.wake_mat.node_tree, "wake", 0.8 if sm.SHIP_V > 0 else 0.0)
        return y


class LiftGhost:
    """What a lift bridge would need for the same masts: two towers taller than the masts, the deck held up above the mastheads."""

    def __init__(self):
        g = ghost_material()
        tower_h = sm.MAST_H + sm.LIFT_CLEAR + sm.LIFT_MACHINERY
        deck_z = sm.MAST_H + sm.LIFT_CLEAR
        parts = []
        for sx in (-1, 1):
            for sy in (-1, 1):
                parts.append(((sx * 19.6, sy * 3.2, sw.ROAD_Z + tower_h / 2), (0.8, 0.8, tower_h)))
            for z in np.arange(4.0, tower_h, 6.0):
                parts.append(((sx * 19.6, 0.0, sw.ROAD_Z + z), (0.5, 6.4, 0.4)))
            parts.append(((sx * 19.6, 0.0, sw.ROAD_Z + tower_h), (2.6, 8.0, 1.2)))
        parts.append(((0.0, 0.0, deck_z), (sm.DECK_L + 6.0, sm.DECK_W, 1.4)))
        self.ob = K.boxes("Lift bridge (would need)", parts, g)
        self.ob.hide_render = True
        self.tower_h = tower_h

    def show(self, on):
        self.ob.hide_render = not on


class Effects:
    """Foam where the sea floods over the road, air bubbling out of the girders on the way down, silt where the deck settles, sheets
    of water pouring off its edges and drips as it comes up."""

    def __init__(self):
        self.foam_mat = foam_material("Flooding foam", "foam", 0.95)
        co = []
        faces = []
        for (x0, x1, y0, y1) in ((-HALF_L - 0.6, HALF_L + 0.6, -HALF_W - 1.2, HALF_W + 1.2),):
            co = [(x0, y0, 0.012), (x1, y0, 0.012), (x1, y1, 0.012), (x0, y1, 0.012)]
            faces = [(0, 1, 2, 3)]
        self.foam = np_mesh("Flooding foam", co, faces, [self.foam_mat])
        self.fall_mat = foam_material("Pouring water", "falls", 0.8)
        fall_co, fall_faces = [], []
        for (ax, ay, bx, by) in ((-HALF_L, -HALF_W - 0.05, HALF_L, -HALF_W - 0.05), (-HALF_L, HALF_W + 0.05, HALF_L, HALF_W + 0.05),
                                 (-HALF_L - 0.05, -HALF_W, -HALF_L - 0.05, HALF_W), (HALF_L + 0.05, -HALF_W, HALF_L + 0.05, HALF_W)):
            i = len(fall_co)
            fall_co += [(ax, ay, 0.0), (bx, by, 0.0), (bx, by, -1.0), (ax, ay, -1.0)]
            fall_faces.append((i, i + 1, i + 2, i + 3))
        self.falls = np_mesh("Pouring water", fall_co, fall_faces, [self.fall_mat])
        self.fall_base = np.array(fall_co)
        glass = bpy.data.materials.new("Bubble")
        glass.use_nodes = True
        s = glass.node_tree.nodes.get("Principled BSDF")
        s.inputs["Base Color"].default_value = (1, 1, 1, 1)
        s.inputs["Roughness"].default_value = 0.02
        s.inputs["IOR"].default_value = 0.75                             # air in water
        s.inputs["Transmission Weight"].default_value = 1.0
        v, f = K.cyl_geom(1.0, 1.0, (0, 0, 0), (0, 0, 0), 6)
        rng = np.random.default_rng(5)
        self.bub_seed = rng.uniform(0, 1, (N_BUBBLES, 4))
        bub_co, bub_f = [], []
        for k in range(N_BUBBLES):
            vv, ff = K.cyl_geom(0.05, 0.08, (0.0, 0.0, -50.0), (0, 0, 0), 6)
            off = len(bub_co)
            bub_co += vv
            bub_f += [tuple(i + off for i in fc) for fc in ff]
        self.bubbles = K.Sheet("Bubbles", bub_co, bub_f, [glass], smooth=True)
        self.bub_proto = np.array(K.cyl_geom(0.05, 0.08, (0.0, 0.0, 0.0), (0, 0, 0), 6)[0])
        self.drip_mat = material("Drip", (0.9, 0.95, 1.0), rough=0.05)
        dp, df = [], []
        for k in range(N_DRIPS):
            vv = K.box_verts((0.0, 0.0, -50.0), (0.025, 0.025, 0.18))
            off = len(dp)
            dp += vv
            df += [tuple(i + off for i in fc) for fc in K.BOX_FACES]
        self.drips = K.Sheet("Drips", dp, df, [self.drip_mat], smooth=False)
        self.drip_proto = np.array(K.box_verts((0.0, 0.0, 0.0), (0.025, 0.025, 0.18)))
        self.drip_seed = rng.uniform(0, 1, (N_DRIPS, 3))
        self.silt_mat = puff_material("Silt")
        self.silt = []
        for k in range(N_SILT):
            ob = K.sphere(f"Silt {k}", 1.0, (0, 0, -60), self.silt_mat)
            ob.hide_render = True
            self.silt.append(ob)
        self.silt_seed = rng.uniform(0, 1, (N_SILT, 3))
        del v, f

    def set(self, t, film_t):
        z = sm.deck_z(t)
        v = sm.deck_speed(t)
        foam = math.exp(-((z - 0.02) / 0.28) ** 2) if abs(v) > 1e-4 else 0.0
        K.node_value(self.foam_mat.node_tree, "foam", foam)
        self.foam.hide_render = foam < 0.02
        t_out = sm.t_out()
        since = t - t_out
        falls = 0.0
        if t > sm.T_UP0 and 0.0 <= since and z > 0.02:
            falls = math.exp(-since / 9.0)
        K.node_value(self.fall_mat.node_tree, "falls", falls)
        co = self.fall_base.copy()
        co[:, 2] = np.where(co[:, 2] > -0.5, z - 0.02, 0.0)
        self.falls.data.vertices.foreach_set("co", co.astype(np.float32).ravel())
        self.falls.data.update()
        self.falls.hide_render = falls < 0.02
        # bubbles: air leaving the girders while the deck goes down (and a little after)
        pos = np.full((N_BUBBLES, 3), -50.0)
        n_b = 0
        if sm.T_DOWN0 + 8.0 < t < sm.T_DOWN0 + sm.move_time() + 15.0 and z < -0.3:
            for k, (a, b, c, d) in enumerate(self.bub_seed):
                period = 6.0 + 4.0 * d
                age = ((t * (1.0 + c)) + a * period) % period
                x0 = (a - 0.5) * (sm.DECK_L - 2.0)
                y0 = (b - 0.5) * (sm.DECK_W - 1.0)
                zz = z + 0.1 + age * 1.1
                if zz < -0.05:
                    pos[k] = (x0 + 0.2 * math.sin(age * 3 + k), y0 + 0.2 * math.cos(age * 2.6 + k), zz)
                    n_b += 1
        sc = 0.6 + 0.8 * self.bub_seed[:, 3]
        self.bubbles.set((self.bub_proto[None, :, :] * sc[:, None, None] + pos[:, None, :]).reshape(-1, 3))
        # drips off the edges after it comes up
        dpos = np.full((N_DRIPS, 3), -50.0)
        n_d = 0
        if t > sm.T_UP0 and since >= 0.0 and z > 0.05 and since < 90.0:
            rate = math.exp(-since / 30.0)
            for k, (a, b, c) in enumerate(self.drip_seed):
                if c > rate + 0.15:
                    continue
                period = 0.6 + 0.6 * b
                fall = ((film_t + a * period) % period) / period
                edge = k % 4
                s_ = (a - 0.5)
                if edge < 2:
                    x0, y0 = s_ * sm.DECK_L, (-1 if edge == 0 else 1) * (HALF_W + 0.06)
                else:
                    x0, y0 = (-1 if edge == 2 else 1) * (HALF_L + 0.06), s_ * sm.DECK_W
                zz = z - 0.1 - fall * max(0.1, z)
                if zz > 0.02:
                    dpos[k] = (x0, y0, zz)
                    n_d += 1
        self.drips.set((self.drip_proto[None, :, :] + dpos[:, None, :]).reshape(-1, 3))
        # silt where it settles
        n_s = 0
        t_land = sm.T_DOWN0 + sm.move_time()
        age = t - (t_land - 6.0)
        for k, ob in enumerate(self.silt):
            a, b, c = self.silt_seed[k]
            if 0.0 < age < 60.0:
                edge = k % 2
                x0 = (a - 0.5) * (sm.DECK_L + 2.0)
                y0 = (-1 if edge == 0 else 1) * (HALF_W + 0.6 + 1.5 * b * min(1.0, age / 20.0))
                r = 0.6 + 2.2 * min(1.0, age / 18.0) * (0.6 + 0.4 * c)
                ob.location = (x0, y0, sm.PIT + 0.4 + 0.6 * min(1.0, age / 12.0) + r * 0.3)
                ob.scale = (r, r * 0.8, r * 0.55)
                fade = min(1.0, age / 3.0) * math.exp(-max(0.0, age - 12.0) / 14.0)
                ob.color = (0.0, 0.35, 0.0, 0.55 * fade)
                ob.hide_render = fade < 0.03
                n_s += int(not ob.hide_render)
            else:
                ob.hide_render = True
        return {"foam": round(foam, 3), "falls": round(falls, 3), "bubbles": n_b, "drips": n_d, "silt": n_s}


def build_cars():
    paints = [(0.85, 0.85, 0.82), (0.05, 0.05, 0.06), (0.10, 0.20, 0.45), (0.60, 0.62, 0.64), (0.95, 0.72, 0.05), (0.30, 0.05, 0.05)]
    glass = material("Car glass", (0.04, 0.05, 0.06), metal=0.2, rough=0.1)
    tyre = material("Tyre", (0.03, 0.03, 0.03), rough=0.8)
    from benchmarks.rock_net.render_rocknet_3d import merged
    spots = [(-31.0, -1.75), (-37.2, -1.75), (-43.6, -1.75), (-50.0, -1.75), (25.4, 1.75), (31.6, 1.75), (38.0, 1.75), (44.4, 1.75)]
    for k, (x, y) in enumerate(spots):
        body = material(f"Car paint {k}", paints[k % len(paints)], metal=0.4, rough=0.35)
        z = sw.ROAD_Z
        merged("Car body", [(K.box_verts((x, y, z + 0.62), (4.4, 1.8, 0.65)), K.BOX_FACES)], body)
        merged("Car cabin", [(K.box_verts((x - 0.2 * np.sign(x), y, z + 1.22), (2.3, 1.6, 0.6)), K.BOX_FACES)], glass)
        merged("Car wheels", [K.cyl_geom(0.34, 0.25, (x + dx, y + dy, z + 0.34), (math.pi / 2, 0, 0), 14) for dx in (-1.35, 1.35) for dy in (-0.82, 0.82)], tyre)


def main():
    args = arguments()
    args.out.mkdir(parents=True, exist_ok=True)
    car_root, body, wheels, geom = base.load_source_car(args.source)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 8
    scene.cycles.transmission_bounces = 6
    scene.cycles.volume_bounces = 1
    scene.cycles.caustics_reflective = False
    scene.cycles.caustics_refractive = False
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Punchy"
    scene.view_settings.exposure = -0.15
    if hasattr(scene.view_settings, "use_white_balance"):
        scene.view_settings.use_white_balance = True
        scene.view_settings.white_balance_temperature = 6600.0
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    sun_to = cinematic.sun_vector((-0.45, -0.89), 34.0)                      # afternoon sun over the sea (south-west)
    cinematic.apply_sky(scene, sun_to, strength=0.30, dust=0.3)
    sd = bpy.data.lights.new("Sun", "SUN")
    sd.energy, sd.angle, sd.color = 4.6, 0.02, (1.0, 0.90, 0.78)
    sun = bpy.data.objects.new("Sun", sd)
    scene.collection.objects.link(sun)
    sun.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()
    wheel_nodes = {w["node"] for w in wheels.values()}
    parts = [o for o in car_root.children_recursive if o.type == "MESH" and not any(p in wheel_nodes for p in rb._ancestors(o))]
    ghost = rb.Ghost(parts)
    ghost.set_tint(PAINT)
    ghost.set_factor(0.0, 1e4, 4.0)
    car_root.location = (-24.6, -1.75, sw.ROAD_Z)
    car_root.rotation_euler = (0.0, 0.0, -math.pi / 2)                       # nose toward +x, waiting at the gate
    build_land()
    build_water()
    build_ridges()
    n_veg = build_vegetation()
    build_quays_and_roads()
    build_town()
    build_cars()
    deck = Deck()
    gates = Gates()
    ship = TallShip()
    lift = LiftGhost()
    fx = Effects()
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    segs = tl.segments()
    print("SINKING_SCENE " + json.dumps({"plants": n_veg, "objects": len(bpy.data.objects)}), flush=True)

    def render(sh, path):
        scene.render.resolution_x, scene.render.resolution_y = round(FRAME[0] * args.res_scale), round(FRAME[1] * args.res_scale)
        t, film_t = sh["t"], sh["film_t"]
        z = deck.set(t)
        down = gates.set(t, film_t)
        ship_y = ship.set(t)
        lift.show(bool(sh.get("ghost")))
        e = fx.set(t, film_t)
        c = sh["cam"]
        loc, tgt = Vector(c["loc"]), Vector(c["target"])
        dd = cam.data
        dd.sensor_fit, dd.sensor_width, dd.lens, dd.clip_start = "HORIZONTAL", 36.0, c["lens"], 0.05
        dd.clip_end = 20000.0
        dd.dof.use_dof = True
        dd.dof.focus_distance = (tgt - loc).length
        dd.dof.aperture_fstop = c.get("fstop", 8.0)
        base.set_camera(cam, loc, tgt)
        bpy.context.view_layer.update()
        lo, hi = tl.deck_box(t)
        box = hook_gate.project_box(scene, cam, Matrix.Identity(4), lo, hi)
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        return {"t": round(t, 6), "deck_z": round(z, 4), "deck_speed": round(sm.deck_speed(t), 5), "gates_down": round(down, 4),
                "lights": sm.lights_on(t), "ship_bow_y": round(ship_y, 3), "ship_over_deck": sm.ship_over_deck(t), "wet": round(sm.wet(t), 4),
                "ghost": bool(sh.get("ghost")), "under": bool(sh.get("under")), **e, "subject_box": box,
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
        print("SINKING_FRAME " + json.dumps(info), flush=True)
    (args.out / f"sinking-frames-{frames[0]:05d}.json").write_text(json.dumps({"renderer_source_sha256": src_sha, "frames": out}, indent=1))


if __name__ == "__main__":
    main()
