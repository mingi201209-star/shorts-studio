"""EP.30 swivel bridge: 100 % 3D renderer (Blender, Cycles CPU), house style of EP.13-EP.29 (low sun, depth of field). The edge of
a city on a flat plain: a four-track electrified railway (ballast, rails, sleepers, catenary masts and wires, signals), apartment
blocks, streets and trees; beside the tracks a road bridge 263.6 m long, a concrete box girder balanced on one pier like a T. At the
pier's foot the swivel: a lower turntable on the foundation with a steel ring track, a spherical hinge (concave lower half, convex
upper half, a slippery liner between), the upper turntable with support feet on the ring, two bundles of cable wrapped round it and
led to jacks on reaction blocks.

Everything moves from swivel_motion: the deck, pier and upper turntable turn together about the hinge (52.4 degrees in 68 minutes,
soft start and stop); trains pass before and after the railway's window, one waits at a red signal during it. Comparison shots add
the bridge's final place (translucent) and a clock's minute hand (translucent, turning at clock speed about the pier). The section
shot cuts the swivel open. No text anywhere in the scene."""
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
from benchmarks.can_opener import render_opener_3d as K  # noqa: E402  (data-API mesh helpers)
from benchmarks.manhole_blast.render_manhole_3d import Nodes, principled  # noqa: E402
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402
from benchmarks.rock_net.render_rocknet_3d import merged, textured  # noqa: E402
from benchmarks.roller_barrier.render_roller_3d import np_mesh  # noqa: E402
from benchmarks.swivel_bridge import swivel_motion as sm  # noqa: E402
from benchmarks.swivel_bridge import swivel_timeline as tl  # noqa: E402

material = base.material
FRAME = (1080, 1920)
PX, PY = sm.PIER
TRAIN_CARS, CAR_L = 8, 25.0


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


def ghost_material(name, color=(0.5, 0.85, 1.0), strength=3.0, base_a=0.3):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    N = Nodes(nt)
    out = N.new("ShaderNodeOutputMaterial")
    lw = N.new("ShaderNodeLayerWeight", Blend=0.35)
    em = N.new("ShaderNodeEmission", Color=color, Strength=strength)
    mix = N.new("ShaderNodeMixShader")
    N.put(mix.inputs["Fac"], N.math("MULTIPLY_ADD", lw.outputs["Facing"], 0.5, base_a, clamp=True))
    N.put(mix.inputs[1], N.new("ShaderNodeBsdfTransparent").outputs[0])
    N.put(mix.inputs[2], em.outputs[0])
    N.put(out.inputs["Surface"], mix.outputs[0])
    return m


def ballast_material():
    """Grey ballast with dark timber-coloured sleepers every 0.6 m along x."""
    m, N, bsdf = principled("Track bed", rough=0.95)
    pos = N.new("ShaderNodeTexCoord").outputs["Object"]
    x, _, _ = N.xyz(pos)
    stripe = N.math("LESS_THAN", N.math("FRACT", N.math("DIVIDE", x, 0.6)), 0.38)
    grain = N.noise(pos, 8.0, 6.0)
    stones = N.mix(grain, (0.30, 0.29, 0.27), (0.46, 0.45, 0.42))
    N.put(bsdf.inputs["Base Color"], N.mix(stripe, stones, (0.12, 0.10, 0.08)))
    return m


def deck_geom(half_len, n=60):
    """The box girder along local +y from -half_len to +half_len, deck top at z = DECK_TOP (local z = world z), haunched below.
    Faces: 0 concrete, 1 asphalt, 2 parapets."""
    co, faces, mi = [], [], []
    ys = np.linspace(-half_len, half_len, n)
    w2, b2 = sm.DECK_W / 2, 6.0
    for y in ys:
        a = abs(y)
        bottom = sm.deck_bottom_z(a)
        top = sm.DECK_TOP
        ring = [(-w2, top), (w2, top), (w2, top - 0.35), (b2 + 1.0, top - 1.4), (b2, bottom), (-b2, bottom), (-b2 - 1.0, top - 1.4), (-w2, top - 0.35)]
        co += [(x, y, z) for x, z in ring]
    m = 8
    for i in range(n - 1):
        for j in range(m):
            a, b = i * m + j, i * m + (j + 1) % m
            faces.append((a, a + m, b + m, b))
            mi.append(1 if j == 0 else 0)
    faces.append(tuple(range(m))[::-1])
    mi.append(0)
    faces.append(tuple((n - 1) * m + j for j in range(m)))
    mi.append(0)
    base_n = len(co)
    for sx in (-1, 1):
        for i, y in enumerate((ys[0], ys[-1])):
            pass
        off = len(co)
        co += [(sx * (w2 - 0.25), ys[0], sm.DECK_TOP), (sx * (w2 - 0.25), ys[-1], sm.DECK_TOP), (sx * (w2 - 0.25), ys[-1], sm.DECK_TOP + 1.1),
               (sx * (w2 - 0.25), ys[0], sm.DECK_TOP + 1.1)]
        faces.append((off, off + 1, off + 2, off + 3))
        mi.append(2)
    del base_n
    return co, faces, mi


class Bridge:
    """Deck, pier and upper turntable on one empty that turns about the hinge; the lower turntable, the ring track and the jacks stay."""

    def __init__(self):
        conc = textured("Bridge concrete", (0.52, 0.51, 0.49), (0.62, 0.61, 0.58), 1.2, rough=0.85, bump=0.15)
        asph = textured("Deck asphalt", (0.07, 0.07, 0.075), (0.11, 0.11, 0.115), 3.0, rough=0.85, bump=0.1)
        rail = material("Parapet", (0.75, 0.75, 0.73), metal=0.5, rough=0.4)
        steel = material("Swivel steel", (0.35, 0.36, 0.38), metal=0.85, rough=0.3)
        liner = material("Slide liner", (0.92, 0.92, 0.90), rough=0.25)
        grease = material("Grease", (0.06, 0.05, 0.03), rough=0.2)
        white = material("Lane paint", (0.88, 0.88, 0.85), rough=0.5)
        cable = material("Cable bundle", (0.10, 0.10, 0.11), metal=0.6, rough=0.4)
        self.root = bpy.data.objects.new("Swivel", None)
        bpy.context.collection.objects.link(self.root)
        self.root.location = (PX, PY, 0.0)
        co, faces, mi = deck_geom(sm.HALF)
        self.deck = np_mesh("Bridge deck", co, faces, [conc, asph, rail], mi, smooth=False)
        self.deck.parent = self.root
        lines = []
        for x in (-8.0, -4.0, 4.0, 8.0):
            for y in np.arange(-sm.HALF + 4, sm.HALF - 4, 12.0):
                lines.append(((x, y + 3.0, sm.DECK_TOP + 0.01), (0.15, 6.0, 0.02)))
        lines += [((sx * 0.2, 0.0, sm.DECK_TOP + 0.01), (0.15, sm.LENGTH - 6, 0.02)) for sx in (-1, 1)]
        ln = K.boxes("Deck lane lines", lines, white)
        ln.parent = self.root
        pier = K.boxes("Pier", [((0.0, 0.0, (1.8 + sm.DECK_TOP - sm.DEPTH_PIER) / 2), (11.0, 7.0, sm.DECK_TOP - sm.DEPTH_PIER - 1.8))], conc)
        pier.parent = self.root
        self.upper = [pier, self.deck, ln]
        # the swivel: built in north (y >= 0) and south halves so the section shot can cut it open
        self.south = []
        R_low, R_up, R_h = 8.0, 7.0, sm.HINGE_D / 2
        for half, (a0, a1) in (("north", (0.0, math.pi)), ("south", (math.pi, 2 * math.pi))):
            def disc(name, r0, r1, z0, z1, mat, parent, seg=40):
                angles = np.linspace(a0, a1, seg + 1)
                vs = []
                for z in (z0, z1):
                    for r in (r0, r1):
                        vs += [(r * math.cos(a), r * math.sin(a), z) for a in angles]
                n = len(angles)
                fs = []

                def ix(zi, ri, k):
                    return (zi * 2 + ri) * n + k
                for k in range(n - 1):
                    fs.append((ix(1, 0, k), ix(1, 1, k), ix(1, 1, k + 1), ix(1, 0, k + 1)))
                    fs.append((ix(0, 0, k), ix(0, 0, k + 1), ix(0, 1, k + 1), ix(0, 1, k)))
                    fs.append((ix(0, 1, k), ix(0, 1, k + 1), ix(1, 1, k + 1), ix(1, 1, k)))
                    if r0 > 0:
                        fs.append((ix(0, 0, k), ix(1, 0, k), ix(1, 0, k + 1), ix(0, 0, k + 1)))
                for k in (0, n - 1):                                     # the cut faces
                    fs.append((ix(0, 0, k), ix(0, 1, k), ix(1, 1, k), ix(1, 0, k)))
                ob = np_mesh(f"{name} ({half})", vs, fs, [mat])
                if parent is not None:
                    ob.parent = parent
                else:
                    ob.location = (PX, PY, 0.0)
                if half == "south":
                    self.south.append(ob)
                return ob
            disc("Lower turntable", 0.0, R_low, -1.5, 0.0, conc, None)
            disc("Ring track", 6.0, 6.7, 0.0, 0.12, steel, None)
            disc("Lower hinge (concave)", 0.0, R_h, 0.0, 0.35, steel, None)
            disc("Slide liner", 0.0, R_h - 0.05, 0.35, 0.42, liner, None)
            disc("Grease film", 0.0, R_h - 0.1, 0.42, 0.45, grease, None)
            disc("Upper hinge (convex)", 0.0, R_h - 0.05, 0.45, 0.8, steel, self.root)
            up = disc("Upper turntable", 0.0, R_up, 0.8, 1.8, conc, self.root)
            self.upper.append(up)
            disc("Cable bundle", R_up, R_up + 0.12, 1.1, 1.5, cable, self.root)
        feet = [((6.35 * math.cos(a), 6.35 * math.sin(a), 0.5), (0.9, 0.9, 0.8)) for a in np.linspace(0, 2 * math.pi, 9)[:-1]]
        fob = K.boxes("Support feet", feet, steel)
        fob.parent = self.root
        jacks = []
        for sy in (-1, 1):
            jacks.append(((PX + sy * 10.5, PY + sy * 6.5, 1.0), (2.4, 2.4, 2.0)))
            jacks.append(((PX + sy * 9.0, PY + sy * 6.5, 1.3), (1.2, 0.8, 0.8)))
        K.boxes("Jacks and reaction blocks", jacks, steel)
        strands = []
        for sy in (-1, 1):
            p0 = Vector((PX + sy * 8.4, PY + sy * 6.5, 1.3))
            p1 = Vector((PX + sy * 0.0, PY + sy * 7.0, 1.3))
            d = p1 - p0
            strands.append(K.cyl_geom(0.12, d.length, tuple((p0 + p1) / 2), tuple(d.to_track_quat("Z", "Y").to_euler()), 6))
        merged("Pulled strands", strands, cable)
        self.ghost = np_mesh("Bridge (where it will sit)", co, faces, [ghost_material("Ghost deck")], None, smooth=False)
        self.ghost.location = (PX, PY, 0.0)
        self.ghost.rotation_euler = (0.0, 0.0, -(sm.HEAD0 + sm.TURN))
        self.ghost.hide_render = True

    def set(self, t, flags):
        h = sm.heading(t)
        self.root.rotation_euler = (0.0, 0.0, -h)
        for ob in self.south:
            ob.hide_render = bool(flags.get("section"))
        self.ghost.hide_render = not flags.get("ghost")
        return h


class Railway:
    def __init__(self):
        bed = ballast_material()
        steel = material("Rail steel", (0.40, 0.40, 0.42), metal=0.9, rough=0.3)
        mast = material("Catenary mast", (0.55, 0.56, 0.58), metal=0.6, rough=0.4)
        wire = material("Contact wire", (0.25, 0.18, 0.12), metal=0.8, rough=0.35)
        X0, X1 = -1500.0, 1500.0
        K.cube("Railway bed", (0.0, 0.0, -0.25), (X1 - X0, 17.0, 0.5), bed)
        rails = []
        for y in sm.TRACKS_Y:
            for g in (-0.72, 0.72):
                rails.append(((0.0, y + g, 0.08), (X1 - X0, 0.08, 0.16)))
        K.boxes("Rails", rails, steel)
        masts, arms, wires = [], [], []
        for x in np.arange(X0, X1, 50.0):
            for sy in (-1, 1):
                masts.append(((x, sy * 9.0, 4.5), (0.35, 0.35, 9.0)))
                arms.append(((x, sy * 5.6, 8.6), (0.15, 7.0, 0.15)))
        K.boxes("Catenary masts", masts, mast)
        K.boxes("Catenary arms", arms, mast)
        for y in sm.TRACKS_Y:
            wires.append(((0.0, y, sm.WIRE_Z), (X1 - X0, 0.04, 0.04)))
            wires.append(((0.0, y, sm.WIRE_Z + 1.2), (X1 - X0, 0.03, 0.03)))
        K.boxes("Catenary wires", wires, wire)
        self.red = material("Signal red", (1.0, 0.05, 0.02), rough=0.4)
        self.green = material("Signal green", (0.05, 1.0, 0.3), rough=0.4)
        posts = material("Signal post", (0.2, 0.2, 0.2), rough=0.6)
        self.signals = []
        for x in (-380.0, 380.0):
            K.cube(f"Signal post {x}", (x, -8.0, 2.5), (0.2, 0.2, 5.0), posts)
            r = K.cube(f"Signal red {x}", (x, -8.0, 5.2), (0.35, 0.35, 0.35), self.red)
            g = K.cube(f"Signal green {x}", (x, -8.0, 4.7), (0.35, 0.35, 0.35), self.green)
            self.signals.append((r, g))
        body = material("Train body", (0.92, 0.92, 0.90), rough=0.35)
        band = material("Train band", (0.08, 0.35, 0.22), rough=0.4)
        glass = material("Train windows", (0.05, 0.07, 0.09), metal=0.3, rough=0.1)
        self.trains = []
        for k in range(2):
            root = bpy.data.objects.new(f"Train {k}", None)
            bpy.context.collection.objects.link(root)
            parts = []
            for c in range(TRAIN_CARS):
                x = -c * (CAR_L + 0.6)
                parts.append(K.cube(f"Train {k} car {c}", (x, 0.0, 2.3), (CAR_L, 3.1, 3.6), body))
                parts.append(K.cube(f"Train {k} band {c}", (x, 0.0, 1.0), (CAR_L + 0.02, 3.14, 0.5), band))
                parts.append(K.cube(f"Train {k} windows {c}", (x, 0.0, 2.8), (CAR_L - 2.0, 3.16, 0.8), glass))
            for ob in parts:
                ob.parent = root
            self.trains.append(root)

    def set(self, t):
        win = sm.WINDOW[0] <= t <= sm.WINDOW[1]
        for r, g in self.signals:
            r.data.materials[0] = self.red
            sr = self.red.node_tree.nodes.get("Principled BSDF")
            sg = self.green.node_tree.nodes.get("Principled BSDF")
            sr.inputs["Emission Color"].default_value = (1.0, 0.05, 0.02, 1)
            sr.inputs["Emission Strength"].default_value = 25.0 if win else 0.0
            sg.inputs["Emission Color"].default_value = (0.05, 1.0, 0.3, 1)
            sg.inputs["Emission Strength"].default_value = 0.0 if win else 20.0
        out = []
        for k, root in enumerate(self.trains):
            x = tl.train_x(k, t)
            if x is None:
                root.location = (0.0, -9999.0, -50.0)
                out.append(None)
                continue
            root.location = (x, tl.TRACK_OF[k], 0.16)
            out.append(round(x, 2))
        return win, out


def build_city():
    ground = textured("Plain ground", (0.20, 0.22, 0.12), (0.30, 0.30, 0.18), 0.05, rough=0.95, bump=0.2)
    K.cube("Ground", (0.0, 0.0, -0.55), (6000.0, 6000.0, 0.5), ground)
    road = textured("Street asphalt", (0.08, 0.08, 0.085), (0.12, 0.12, 0.125), 3.0, rough=0.85, bump=0.1)
    K.boxes("Streets", [((0.0, -60.0, -0.29), (3000.0, 16.0, 0.02)), ((0.0, 70.0, -0.29), (3000.0, 16.0, 0.02)),
                        ((-200.0, 0.0, -0.29), (16.0, 3000.0, 0.02))], road)
    wall = textured("Apartment walls", (0.70, 0.68, 0.63), (0.82, 0.80, 0.76), 2.0, rough=0.8, bump=0.1)
    win = material("Apartment windows", (0.10, 0.12, 0.15), metal=0.3, rough=0.15)
    rng = random.Random(30)
    blocks, wins = [], []
    for k in range(80):
        x = rng.uniform(-900, 900)
        y = rng.choice((-1, 1)) * rng.uniform(95, 600)
        if abs(x - PX) < 160 and abs(y) < 200:
            continue
        w, d, h = rng.uniform(16, 26), rng.uniform(12, 18), rng.uniform(25, 75)
        blocks.append(((x, y, h / 2 - 0.3), (w, d, h)))
        for z in np.arange(3.0, h - 2, 3.0):
            wins.append(((x, y - d / 2 - 0.02, z), (w - 2.0, 0.05, 1.3)))
            wins.append(((x, y + d / 2 + 0.02, z), (w - 2.0, 0.05, 1.3)))
    K.boxes("Apartment blocks", blocks, wall)
    K.boxes("Apartment windows", wins, win)
    leaf = textured("Street trees", (0.07, 0.14, 0.04), (0.14, 0.22, 0.07), 1.0, rough=0.9, bump=0.5)
    crowns = []
    for x in np.arange(-900, 900, 14.0):
        for y in (-70.0, -50.0, 60.0, 80.0):
            if abs(x - PX) < 25 and y < 0:
                continue
            crowns.append(K.cyl_geom(2.6, 4.0, (x + rng.uniform(-2, 2), y, 4.0), (0, 0, 0), 8))
    merged("Street trees", crowns, leaf, smooth=True)


class Clock:
    """A clock's minute hand (translucent) turning about the pier at clock speed, over a ring of minute ticks."""

    def __init__(self):
        g = ghost_material("Ghost clock", (1.0, 0.85, 0.4), 3.0, 0.35)
        R = 70.0
        ticks = []
        for k in range(60):
            a = 2 * math.pi * k / 60
            L = 6.0 if k % 5 == 0 else 2.5
            ticks.append(((PX + (R - L / 2) * math.sin(a), PY + (R - L / 2) * math.cos(a), 0.6), (0.6, L, 0.1)))
        self.ticks = K.boxes("Clock ticks", ticks, g)
        for ob in self.ticks.data.vertices:
            pass
        self.hand_root = bpy.data.objects.new("Minute hand", None)
        bpy.context.collection.objects.link(self.hand_root)
        self.hand_root.location = (PX, PY, 0.7)
        self.hand = K.cube("Minute hand bar", (0.0, R * 0.45, 0.0), (1.4, R * 0.9, 0.12), g)
        self.hand.parent = self.hand_root
        self.objs = [self.ticks, self.hand]
        self._rotate_ticks()

    def _rotate_ticks(self):
        me = self.ticks.data
        co = np.zeros(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        # boxes were laid out along y; turn each tick to point at the centre
        for k in range(60):
            a = 2 * math.pi * k / 60
            c = np.array([PX + 0.0, PY + 0.0])
            sl = slice(8 * k, 8 * k + 8)
            ctr = co[sl, :2].mean(0)
            rel = co[sl, :2] - ctr
            rot = np.array([[math.cos(-a), -math.sin(-a)], [math.sin(-a), math.cos(-a)]])
            co[sl, :2] = ctr + rel @ rot.T
            del c
        me.vertices.foreach_set("co", co.ravel())
        me.update()

    def set(self, on, t):
        for ob in self.objs:
            ob.hide_render = not on
        a = 2 * math.pi * (t / 3600.0)                                   # one turn an hour
        self.hand_root.rotation_euler = (0.0, 0.0, -(sm.HEAD0 + a))
        return a


def main():
    args = arguments()
    args.out.mkdir(parents=True, exist_ok=True)
    car_root, body, wheels, geom = base.load_source_car(args.source)
    for ob in [car_root, *car_root.children_recursive]:
        ob.hide_render = True
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
        scene.view_settings.white_balance_temperature = 7000.0
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    sun_to = cinematic.sun_vector((-0.6, -0.8), 22.0)
    cinematic.apply_sky(scene, sun_to, strength=0.30, dust=1.3)
    sd = bpy.data.lights.new("Sun", "SUN")
    sd.energy, sd.angle, sd.color = 4.8, 0.02, (1.0, 0.82, 0.62)
    sun = bpy.data.objects.new("Sun", sd)
    scene.collection.objects.link(sun)
    sun.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()
    build_city()
    rail = Railway()
    bridge = Bridge()
    clock = Clock()
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    segs = tl.segments()
    print("SWIVEL_SCENE " + json.dumps({"objects": len(bpy.data.objects)}), flush=True)

    def render(sh, path):
        scene.render.resolution_x, scene.render.resolution_y = round(FRAME[0] * args.res_scale), round(FRAME[1] * args.res_scale)
        t = sh["t"]
        flags = {k: sh.get(k) for k in ("ghost", "section", "clock")}
        h = bridge.set(t, flags)
        win, trains = rail.set(t)
        hand = clock.set(bool(flags["clock"]), t)
        cm = sh["cam"]
        loc, tgt = Vector(cm["loc"]), Vector(cm["target"])
        dd = cam.data
        dd.sensor_fit, dd.sensor_width, dd.lens, dd.clip_start = "HORIZONTAL", 36.0, cm["lens"], 0.05
        dd.clip_end = 20000.0
        dd.dof.use_dof = True
        dd.dof.focus_distance = (tgt - loc).length
        dd.dof.aperture_fstop = cm.get("fstop", 8.0)
        base.set_camera(cam, loc, tgt)
        bpy.context.view_layer.update()
        lo, hi = tl.subject_box(t)
        box = hook_gate.project_box(scene, cam, Matrix.Identity(4), lo, hi)
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        return {"t": round(t, 6), "heading": round(h, 6), "turned_deg": round(math.degrees(sm.turned(t)), 4), "window": win, "trains_x": trains,
                "over_tracks": sm.over_tracks(t), "ghost": bool(flags["ghost"]), "section": bool(flags["section"]), "clock": bool(flags["clock"]),
                "minute_hand_deg": round(math.degrees(hand), 3), "subject_box": box, "cam_world": [round(x, 3) for x in loc],
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

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
        print("SWIVEL_FRAME " + json.dumps(info), flush=True)
    (args.out / f"swivel-frames-{frames[0]:05d}.json").write_text(json.dumps({"renderer_source_sha256": src_sha, "frames": out}, indent=1))


if __name__ == "__main__":
    main()
