"""EP.28 robotic car tower: 100 % 3D renderer (Blender, Cycles CPU), house style of EP.13-EP.27 (low sun, depth of field). Two glass
silos 48 m tall on a lawn beside a lagoon, a glass delivery hall, a canal and, across it, a factory with four tall chimneys. Inside
each silo 20 floors of 20 bays around a steel mast, new cars lying along the radius, lit by rings of light under every floor; two
lift carriages per silo turn and run up and down the mast. Under the hero silo a transfer station where the tunnel from the
factory arrives: new cars ride through it on low carriers.

Everything moves from tower_motion: the hero carriage (height, heading, the fork's reach and lift) and the CC0 sedan in house red,
from the tunnel onto the fork, up to floor 16, into its bay, and later fetched and brought down; the other carriages run their own
deterministic errands. No text anywhere in the scene."""
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
from benchmarks.car_tower import tower_motion as tm  # noqa: E402
from benchmarks.car_tower import tower_timeline as tl  # noqa: E402
from benchmarks.manhole_blast.render_manhole_3d import Nodes, principled  # noqa: E402
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402
from benchmarks.rock_net.render_rocknet_3d import textured  # noqa: E402
from benchmarks.roller_barrier.render_roller_3d import Proto, box_proto, cyl_proto, np_mesh, np_mesh_flat, rot_z, stamp  # noqa: E402

material = base.material
FRAME = (1080, 1920)
PAINT = (1.75, 0.30, 0.24)
TOWERS = ((0.0, 0.0), (30.0, 16.0))                 # the hero silo at the origin, its twin beside it
TOP = tm.floor_z(tm.N_FLOORS - 1) + tm.FLOOR_H + 1.5
SEG = 48


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
def thin_glass(name, tint=(0.86, 0.93, 0.95), refl=0.05):
    """Facade glass seen as a thin sheet: mostly see-through, a little sky reflected toward grazing angles (no refraction: fast)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    N = Nodes(nt)
    out = N.new("ShaderNodeOutputMaterial")
    lw = N.new("ShaderNodeLayerWeight", Blend=0.25)
    tr = N.new("ShaderNodeBsdfTransparent", Color=tint)
    gl = N.new("ShaderNodeBsdfGlossy", Roughness=0.03)
    mix = N.new("ShaderNodeMixShader")
    N.put(mix.inputs["Fac"], N.math("MULTIPLY_ADD", lw.outputs["Fresnel"], 0.6, refl, clamp=True))
    N.put(mix.inputs[1], tr.outputs[0])
    N.put(mix.inputs[2], gl.outputs[0])
    N.put(out.inputs["Surface"], mix.outputs[0])
    return m


def emissive(name, color, strength):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    N = Nodes(nt)
    out = N.new("ShaderNodeOutputMaterial")
    em = N.new("ShaderNodeEmission", Color=color, Strength=strength)
    N.put(out.inputs["Surface"], em.outputs[0])
    return m


def water_material():
    m, N, bsdf = principled("Lagoon water", (0.03, 0.07, 0.08), rough=0.04)
    pos = N.new("ShaderNodeTexCoord").outputs["Object"]
    bp = N.new("ShaderNodeBump", Strength=0.08)
    N.put(bp.inputs["Height"], N.noise(pos, 0.5, 3.0))
    N.put(bsdf.inputs["Normal"], bp.outputs["Normal"])
    return m


# ------------------------------------------------------------------ geometry helpers
def ring_mesh(name, r0, r1, z0, z1, mat, seg=SEG, center=(0.0, 0.0), gap=None):
    """An annulus (r0..r1) from z0 to z1 (a thick ring); gap=(a0, a1) leaves that sector open (radians)."""
    cx, cy = center
    if gap is None:
        angles = [2 * math.pi * k / seg for k in range(seg)]
        closed = True
    else:
        a0, a1 = gap
        angles = list(np.linspace(a1, a0 + 2 * math.pi, seg + 1))
        closed = False
    n = len(angles)
    co = []
    for z in (z0, z1):
        for r in (r0, r1):
            for a in angles:
                co.append((cx + r * math.cos(a), cy + r * math.sin(a), z))
    faces = []

    def idx(zi, ri, k):
        return (zi * 2 + ri) * n + (k % n if closed else k)
    for k in range(n if closed else n - 1):
        faces.append((idx(1, 0, k), idx(1, 1, k), idx(1, 1, k + 1), idx(1, 0, k + 1)))
        faces.append((idx(0, 0, k), idx(0, 0, k + 1), idx(0, 1, k + 1), idx(0, 1, k)))
        faces.append((idx(0, 1, k), idx(0, 1, k + 1), idx(1, 1, k + 1), idx(1, 1, k)))
        faces.append((idx(0, 0, k), idx(1, 0, k), idx(1, 0, k + 1), idx(0, 0, k + 1)))
    return np_mesh(name, co, faces, [mat])


def box_car_proto():
    """A new car as a few boxes and wheels, nose along +x (local), standing on z = 0: body 0, glass 1, tyres 2."""
    p = box_proto((0.0, 0.0, 0.62), (4.4, 1.78, 0.62), 0)
    p = p + box_proto((-0.25, 0.0, 1.17), (2.3, 1.6, 0.5), 1)
    p = p + box_proto((1.45, 0.0, 0.92), (1.3, 1.7, 0.12), 0)
    for dx in (-1.35, 1.35):
        for dy in (-0.8, 0.8):
            v, f = K.cyl_geom(0.33, 0.24, (dx, dy, 0.33), (math.pi / 2, 0, 0), 10)
            p = p + Proto(v, f, [2] * len(f))
    return p


def car_xform(x, y, z, heading):
    """Rotation for a box car whose nose (local +x) points along `heading`, standing at (x, y, z)."""
    return rot_z(heading), np.array([x, y, z])


class Tower:
    """One silo: glass skin and mullions, floor rings, ring lights, the mast, two carriages; its stored cars (stamped per colour)."""

    def __init__(self, cx, cy, name, mats, car_mats, rng, hero=False):
        self.c = np.array([cx, cy])
        self.hero = hero
        glass, steel, deck, light = mats["glass"], mats["steel"], mats["deck"], mats["light"]
        parts = []
        parts.append(ring_mesh(f"{name} glass", tm.R_GLASS, tm.R_GLASS + 0.05, 0.0, TOP, glass, center=(cx, cy)))
        roof = ring_mesh(f"{name} roof", 0.0, tm.R_GLASS + 0.3, TOP, TOP + 0.6, steel, center=(cx, cy))
        parts.append(roof)
        mull = [((cx + (tm.R_GLASS + 0.1) * math.cos(a), cy + (tm.R_GLASS + 0.1) * math.sin(a), TOP / 2), (0.18, 0.18, TOP))
                for a in np.linspace(0, 2 * math.pi, 21)[:-1]]
        parts.append(K.boxes(f"{name} mullions", mull, steel))
        decks = []
        half = math.pi / tm.N_BAYS
        th_slot = tm.bay_angle(tm.SLOT_BAY)
        gap = (th_slot - half, th_slot + half) if hero else None             # the open column in the hero silo
        for k in range(tm.N_FLOORS):
            z = tm.floor_z(k)
            decks.append(ring_mesh(f"{name} floor {k}", tm.R_BAY - tm.CAR_L / 2 - 0.25, tm.R_GLASS - 0.15, z - 0.14, z, deck, center=(cx, cy), gap=gap))
            decks.append(ring_mesh(f"{name} light {k}", tm.R_GLASS - 1.1, tm.R_GLASS - 0.4, z - 0.19, z - 0.15, light, center=(cx, cy), gap=gap))
        decks.append(ring_mesh(f"{name} ground floor", tm.R_BAY - tm.CAR_L / 2 - 0.1, tm.R_GLASS + 0.3, -0.12, 0.0, deck, center=(cx, cy)))
        parts += decks
        mast = []
        for sx in (-1, 1):
            for sy in (-1, 1):
                mast.append(((cx + sx * 1.05, cy + sy * 1.05, (tm.Z_TRANSFER - 0.5 + TOP) / 2), (0.3, 0.3, TOP - tm.Z_TRANSFER + 0.5)))
        for z in np.arange(tm.Z_TRANSFER, TOP, 2.3):
            mast.append(((cx, cy, z), (2.4, 2.4, 0.18)))
        parts.append(K.boxes(f"{name} mast", mast, steel))
        self.parts = parts
        # stored cars: about 85 % of the bays, the hero's bay kept free
        xf = {i: [] for i in range(len(car_mats))}
        self.filled = set()
        for k in range(tm.N_FLOORS):
            for j in range(tm.N_BAYS):
                if hero and ((k, j) == (tm.HERO_FLOOR, tm.HERO_BAY) or j == tm.SLOT_BAY):
                    continue
                if rng.random() > 0.86:
                    continue
                th = tm.bay_angle(j)
                x = cx + tm.R_BAY * math.cos(th)
                y = cy + tm.R_BAY * math.sin(th)
                xf[rng.randrange(len(car_mats))].append(car_xform(x, y, tm.floor_z(k) + tm.RAIL_H, th + math.pi))
                self.filled.add((k, j))
        proto = box_car_proto()
        self.cars = [stamp(f"{name} cars {i}", proto, [car_mats[i], mats["car_glass"], mats["tyre"]], v) for i, v in xf.items() if v]
        # two carriages: a collar on the mast and a fork (two tines) that reaches out along the radius
        self.carriages = []
        for half in range(2):
            root = bpy.data.objects.new(f"{name} carriage {half}", None)
            bpy.context.collection.objects.link(root)
            collar = K.boxes(f"{name} collar {half}", [((0.0, 0.0, -0.35), (3.0, 3.0, 0.5))], mats["carriage"])
            collar.parent = root
            arm = bpy.data.objects.new(f"{name} arm {half}", None)
            bpy.context.collection.objects.link(arm)
            arm.parent = root
            beam = K.boxes(f"{name} arm beam {half}", [((tm.R_HOME, 0.0, -0.3), (5.2, 2.2, 0.3))], mats["carriage"])
            beam.parent = arm
            fork = bpy.data.objects.new(f"{name} fork {half}", None)
            bpy.context.collection.objects.link(fork)
            fork.parent = arm
            tines = K.boxes(f"{name} tines {half}", [((0.0, sy * 0.7, -0.06), (4.8, 0.25, 0.12)) for sy in (-1, 1)], mats["fork"])
            tines.parent = fork
            self.carriages.append({"root": root, "arm": arm, "fork": fork, "parts": [collar, beam, tines]})
        self.carry = []
        for half in range(2):
            v = car_xform(0.0, 0.0, 0.0, 0.0)
            ob = stamp(f"{name} carried car {half}", proto, [car_mats[(half + 2) % len(car_mats)], mats["car_glass"], mats["tyre"]], [v])
            self.carry.append(ob)

    def set_carriage(self, half, z, th, r, dz):
        c = self.carriages[half]
        c["root"].location = (self.c[0], self.c[1], z)
        c["root"].rotation_euler = (0.0, 0.0, th)
        c["arm"].location = (0.0, 0.0, 0.0)
        c["fork"].location = (r, 0.0, dz)


def errand(t, seed, half):
    """A background carriage's position: deterministic moves between random floors (z, theta, carrying?)."""
    rng = random.Random(seed * 100 + half)
    period = 38.0 + 10.0 * rng.random()
    k = math.floor((t + rng.uniform(0, period)) / period)
    r2 = random.Random(seed * 1000 + half * 77 + k)
    r3 = random.Random(seed * 1000 + half * 77 + k + 1)
    z0 = tm.floor_z(r2.randrange(tm.N_FLOORS)) + tm.RAIL_H
    z1 = tm.floor_z(r3.randrange(tm.N_FLOORS)) + tm.RAIL_H
    th0 = math.radians(half * 180 + r2.uniform(10, 170))
    th1 = math.radians(half * 180 + r3.uniform(10, 170))
    u = ((t + rng.uniform(0, period)) % period)
    d, f = tm._moves(z0, th0, z1, th1)
    z, th = f(min(u, d))
    return z, th, r2.random() < 0.6


def build_site():
    grass = textured("Lawn", (0.10, 0.20, 0.05), (0.16, 0.28, 0.08), 0.8, rough=0.9, bump=0.3)
    path = textured("Paths", (0.55, 0.53, 0.50), (0.66, 0.64, 0.60), 2.0, rough=0.8, bump=0.1)
    hw = 8.0                                                             # the shaft down to the transfer station
    K.boxes("Ground", [((0.0, (hw + 2000.0) / 2, -0.06), (4000.0, 2000.0 - hw, 0.1)), ((0.0, -(hw + 2000.0) / 2, -0.06), (4000.0, 2000.0 - hw, 0.1)),
                       (((hw + 2000.0) / 2, 0.0, -0.06), (2000.0 - hw, 2 * hw, 0.1)), ((-(hw + 2000.0) / 2, 0.0, -0.06), (2000.0 - hw, 2 * hw, 0.1))], grass)
    water = water_material()
    K.cube("Lagoon", (-30.0, -34.0, -0.25), (70.0, 26.0, 0.1), water)
    K.cube("Canal", (0.0, 105.0, -0.8), (4000.0, 34.0, 0.1), water)
    K.boxes("Canal banks", [((0.0, 87.5, -0.4), (4000.0, 1.0, 0.8)), ((0.0, 122.5, -0.4), (4000.0, 1.0, 0.8))], path)
    K.boxes("Paths", [((0.0, -20.0, 0.0), (6.0, 26.0, 0.04)), ((15.0, 8.0, 0.0), (30.0, 5.0, 0.04)), ((-40.0, -6.0, 0.0), (40.0, 5.0, 0.04))], path)
    hall_glass = thin_glass("Hall glass", (0.80, 0.88, 0.92), 0.18)
    steel = material("Hall frame", (0.82, 0.82, 0.80), metal=0.6, rough=0.3)
    hx, hy = -40.0, 62.0
    K.cube("Delivery hall", (hx, hy, 9.0), (40.0, 26.0, 18.0), hall_glass)
    K.boxes("Delivery hall frame", [((hx + dx, hy + dy, 9.0), (0.4, 0.4, 18.0)) for dx in (-20, -10, 0, 10, 20) for dy in (-13, 13)]
            + [((hx, hy, 18.1), (40.4, 26.4, 0.4))], steel)
    brick = textured("Factory brick", (0.30, 0.11, 0.07), (0.42, 0.17, 0.10), 1.5, rough=0.9, bump=0.2)
    K.boxes("Factory halls", [((x, 175.0, 14.0), (95.0, 80.0, 28.0)) for x in (-250.0, -150.0, -50.0, 50.0, 150.0, 250.0)], brick)
    for k, x in enumerate((-60.0, -30.0, 0.0, 30.0)):
        K.cyl(f"Chimney {k}", 3.4, 125.0, (x + 40.0, 150.0, 62.5), brick, verts=18)
    rng = np.random.default_rng(28)
    trees = []
    for _ in range(140):
        x, y = rng.uniform(-160, 160), rng.uniform(-120, 80)
        if any(math.hypot(x - tx, y - ty) < 20 for tx, ty in TOWERS) or (-62 < x < -18 and 46 < y < 78) or (-66 < x < 6 and -48 < y < -20) \
                or (-95 < x < -30 and -40 < y < 10) or (y > 82):
            continue
        h = rng.uniform(6, 13)
        trees.append((x, y, h))
    leaf = textured("Tree crowns", (0.06, 0.12, 0.03), (0.12, 0.20, 0.06), 1.0, rough=0.9, bump=0.5)
    bark = material("Tree bark", (0.14, 0.10, 0.07), rough=0.9)
    crown = []
    trunk = []
    for x, y, h in trees:
        crown.append(K.cyl_geom(h * 0.32, h * 0.6, (x, y, h * 0.65), (0, 0, 0), 9))
        trunk.append(K.cyl_geom(0.22, h * 0.45, (x, y, h * 0.22), (0, 0, 0), 6))
    from benchmarks.rock_net.render_rocknet_3d import merged
    merged("Tree crowns", crown, leaf, smooth=True)
    merged("Tree trunks", trunk, bark)


def build_tunnel(mats):
    """The tunnel from the factory: a concrete tube along -y under the lawn, lit along its ceiling, ending in the transfer station."""
    conc = textured("Tunnel concrete", (0.38, 0.38, 0.37), (0.50, 0.50, 0.48), 2.0, rough=0.85, bump=0.2)
    z0 = tm.Z_TRANSFER - 0.05
    zc = -0.2                                                            # tunnel and station ceilings, just under the lawn
    hgt = zc - z0
    y0, y1 = -8.0, -320.0
    yc, ly = 0.5 * (y0 + y1), abs(y1 - y0)
    K.boxes("Tunnel", [((0.0, yc, z0 - 0.15), (7.0, ly, 0.3)), ((-3.6, yc, z0 + hgt / 2), (0.3, ly, hgt)), ((3.6, yc, z0 + hgt / 2), (0.3, ly, hgt)),
                       ((0.0, yc, zc + 0.12), (7.4, ly, 0.24))], conc)
    K.boxes("Tunnel lights", [((0.0, y, zc - 0.05), (0.5, 3.0, 0.06)) for y in np.arange(y0 - 2.0, y1, -8.0)], mats["light"])
    K.boxes("Transfer station", [((0.0, 0.0, z0 - 0.15), (16.0, 16.0, 0.3)), ((-8.0, 0.0, z0 + hgt / 2), (0.3, 16.0, hgt)), ((8.0, 0.0, z0 + hgt / 2), (0.3, 16.0, hgt)),
                                 ((0.0, 8.0, z0 + hgt / 2), (16.0, 0.3, hgt)), ((-5.4, -8.0, z0 + hgt / 2), (5.2, 0.3, hgt)), ((5.4, -8.0, z0 + hgt / 2), (5.2, 0.3, hgt))], conc)
    K.boxes("Station lights", [((x, y, zc - 0.3), (0.4, 3.0, 0.06)) for x in (-6.5, 6.5) for y in (-4.0, 4.0)], mats["light"])
    rails = [((sx * 0.7, yc, z0 + 0.05), (0.12, ly, 0.1)) for sx in (-1, 1)]
    K.boxes("Tunnel rails", rails, mats["steel"])


class Carriers:
    """Low carriers rolling through the tunnel: the hero car's, and others ahead and behind with new cars on them."""

    def __init__(self, mats, car_mats):
        self.mat = mats["carriage"]
        self.obs = []
        proto = box_car_proto()
        for k in range(6):
            root = bpy.data.objects.new(f"Carrier {k}", None)
            bpy.context.collection.objects.link(root)
            plate = K.cube(f"Carrier plate {k}", (0.0, 0.0, -0.18), (2.2, 4.8, 0.3), self.mat)
            plate.parent = root
            car = stamp(f"Carrier car {k}", proto, [car_mats[k % len(car_mats)], mats["car_glass"], mats["tyre"]], [car_xform(0, 0, 0, math.pi / 2)])
            car.parent = root
            self.obs.append((root, car, plate))

    def set(self, t, hero_y):
        for k, (root, car, plate) in enumerate(self.obs):
            y = hero_y - 22.0 * (k + 1) if t < tm.T_ARRIVE else -tm.R_HOME - 22.0 * (k + 1) - tm.V_TUNNEL * max(0.0, t - tm.T_ARRIVE) % 22.0
            root.location = (0.0, y, tm.Z_TRANSFER + tm.RAIL_H + tm.LIFT_DZ)


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
    scene.cycles.transparent_max_bounces = 16
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Punchy"
    scene.view_settings.exposure = 0.2
    if hasattr(scene.view_settings, "use_white_balance"):
        scene.view_settings.use_white_balance = True
        scene.view_settings.white_balance_temperature = 6800.0
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    sun_to = cinematic.sun_vector((-0.75, -0.66), 9.0)                       # a low evening sun; the silos glow inside
    cinematic.apply_sky(scene, sun_to, strength=0.24, dust=0.6)
    sd = bpy.data.lights.new("Sun", "SUN")
    sd.energy, sd.angle, sd.color = 3.6, 0.02, (1.0, 0.70, 0.45)
    sun = bpy.data.objects.new("Sun", sd)
    scene.collection.objects.link(sun)
    sun.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()
    wheel_nodes = {w["node"] for w in wheels.values()}
    parts = [o for o in car_root.children_recursive if o.type == "MESH" and not any(p in wheel_nodes for p in rb._ancestors(o))]
    ghost = rb.Ghost(parts)
    ghost.set_tint(PAINT)
    ghost.set_factor(0.0, 1e4, 4.0)
    mats = {"glass": thin_glass("Silo glass"), "steel": material("Silo steel", (0.80, 0.81, 0.82), metal=0.7, rough=0.3),
            "deck": material("Floor grating", (0.28, 0.29, 0.30), metal=0.6, rough=0.5), "light": emissive("Ring light", (1.0, 0.93, 0.82), 14.0),
            "carriage": material("Carriage", (0.92, 0.55, 0.08), metal=0.3, rough=0.4), "fork": material("Fork", (0.25, 0.26, 0.28), metal=0.8, rough=0.35),
            "car_glass": material("Car glass", (0.03, 0.04, 0.05), metal=0.3, rough=0.08), "tyre": material("Tyre", (0.02, 0.02, 0.02), rough=0.8)}
    car_mats = [material(f"New car paint {i}", c, metal=0.5, rough=0.25) for i, c in enumerate(
        [(0.85, 0.86, 0.86), (0.04, 0.04, 0.05), (0.55, 0.57, 0.60), (0.08, 0.18, 0.45), (0.70, 0.71, 0.72), (0.30, 0.32, 0.34), (0.60, 0.08, 0.06)])]
    rng = random.Random(2828)
    towers = [Tower(x, y, f"Silo {i}", mats, car_mats, rng, hero=(i == 0)) for i, (x, y) in enumerate(TOWERS)]
    build_site()
    build_tunnel(mats)
    carriers = Carriers(mats, car_mats)
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    segs = tl.segments()
    print("TOWER_SCENE " + json.dumps({"objects": len(bpy.data.objects), "stored_cars": [len(t.filled) for t in towers]}), flush=True)

    def render(sh, path):
        scene.render.resolution_x, scene.render.resolution_y = round(FRAME[0] * args.res_scale), round(FRAME[1] * args.res_scale)
        t = sh["t"]
        c = tm.carriage(t)
        h = tm.hero_car(t)
        hero = towers[0]
        hero.set_carriage(0, c["z"], c["th"], c["r"], c["dz"])
        hero.carry[0].hide_render = True
        for i, tw in enumerate(towers):
            for half in range(2):
                if i == 0 and half == 0:
                    continue
                z, th, carrying = errand(t, i + 1, half)
                tw.set_carriage(half, z, th, tm.R_HOME, tm.LIFT_DZ if carrying else 0.0)
                ob = tw.carry[half]
                ob.hide_render = not carrying
                ob.location = (tw.c[0] + tm.R_HOME * math.cos(th), tw.c[1] + tm.R_HOME * math.sin(th), z + tm.LIFT_DZ)
                ob.rotation_euler = (0.0, 0.0, th + math.pi)
        car_root.location = (h["x"], h["y"], h["z"])
        car_root.rotation_euler = (0.0, 0.0, h["heading"] - math.pi / 2)              # the CC0 car's nose is local +y
        carriers.set(t, h["y"])
        cm = sh["cam"]
        if cm.get("rel") == "carriage":
            o = Vector((0.0, 0.0, c["z"]))
        else:
            o = Vector((0.0, 0.0, 0.0))
        loc, tgt = o + Vector(cm["loc"]), o + Vector(cm["target"])
        dd = cam.data
        dd.sensor_fit, dd.sensor_width, dd.lens, dd.clip_start = "HORIZONTAL", 36.0, cm["lens"], 0.05
        dd.clip_end = 20000.0
        dd.dof.use_dof = True
        dd.dof.focus_distance = (tgt - loc).length
        dd.dof.aperture_fstop = cm.get("fstop", 8.0)
        base.set_camera(cam, loc, tgt)
        bpy.context.view_layer.update()
        lo, hi = tl.subject_box(sh)
        box = hook_gate.project_box(scene, cam, Matrix.Identity(4), lo, hi)
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        return {"t": round(t, 6), "carriage_z": round(c["z"], 4), "carriage_th": round(c["th"], 5), "fork_r": round(c["r"], 4), "fork_dz": round(c["dz"], 4),
                "car_where": h["where"], "car_x": round(h["x"], 4), "car_y": round(h["y"], 4), "car_z": round(h["z"], 4),
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
        print("TOWER_FRAME " + json.dumps(info), flush=True)
    (args.out / f"tower-frames-{frames[0]:05d}.json").write_text(json.dumps({"renderer_source_sha256": src_sha, "frames": out}, indent=1))


if __name__ == "__main__":
    main()
