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
SECTION_CUT = -sm.heading(2050.0)        # the fixed lower parts are cut along the plane the turning parts' cut has in mid-shot


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
                off = SECTION_CUT if parent is None else 0.0                # fixed parts cut along the turning parts' cut (mid-shot)
                angles = np.linspace(a0 + off, a1 + off, seg + 1)
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
            def curved(name, rmax, zb, zt, mat, parent, nr=18, seg=40):
                """A half of a round slab whose bottom and top follow zb(r), zt(r): the spherical hinge's bowl, liner and ball."""
                off = SECTION_CUT if parent is None else 0.0
                angles = np.linspace(a0 + off, a1 + off, seg + 1)
                rs = np.linspace(0.0, rmax, nr + 1)
                n = len(angles)
                vs = []
                for surf in (zb, zt):
                    for r in rs:
                        vs += [(r * math.cos(a_), r * math.sin(a_), surf(r)) for a_ in angles]
                m_ = (nr + 1) * n

                def ix(si, ri, k):
                    return si * m_ + ri * n + k
                fs = []
                for ri in range(nr):
                    for k in range(n - 1):
                        fs.append((ix(1, ri, k), ix(1, ri + 1, k), ix(1, ri + 1, k + 1), ix(1, ri, k + 1)))
                        fs.append((ix(0, ri, k), ix(0, ri, k + 1), ix(0, ri + 1, k + 1), ix(0, ri + 1, k)))
                for k in range(n - 1):
                    fs.append((ix(0, nr, k), ix(0, nr, k + 1), ix(1, nr, k + 1), ix(1, nr, k)))
                for k in (0, n - 1):                                       # the cut faces show the curved profile
                    fs.append(tuple([ix(0, ri, k) for ri in range(nr + 1)] + [ix(1, ri, k) for ri in range(nr, -1, -1)]))
                ob = np_mesh(f"{name} ({half})", vs, fs, [mat])
                if parent is not None:
                    ob.parent = parent
                else:
                    ob.location = (PX, PY, 0.0)
                if half == "south":
                    self.south.append(ob)
                return ob

            def sag(r, RS=10.8, Z0=0.12):
                return Z0 + RS - math.sqrt(RS * RS - r * r)
            disc("Lower turntable", 0.0, R_low, -1.5, 0.0, conc, None)
            disc("Ring track", 6.0, 6.7, 0.0, 0.12, steel, None)
            curved("Lower hinge (concave bowl)", R_h, lambda r: 0.0, sag, steel, None)
            curved("Slide liner", R_h - 0.05, sag, lambda r: sag(r) + 0.05, liner, None)
            curved("Grease film", R_h - 0.1, lambda r: sag(r) + 0.05, lambda r: sag(r) + 0.07, grease, None)
            curved("Upper hinge (convex ball)", R_h - 0.05, lambda r: sag(r) + 0.07, lambda r: 0.8, steel, self.root)
            up = disc("Upper turntable", 0.0, R_up, 0.8, 1.8, conc, self.root)
            self.upper.append(up)
            disc("Cable bundle", R_up, R_up + 0.12, 1.1, 1.5, cable, self.root)
        for half, keep in (("north", lambda a: math.sin(a) >= 0), ("south", lambda a: math.sin(a) < 0)):
            feet = [((6.35 * math.cos(a), 6.35 * math.sin(a), 0.5), (0.9, 0.9, 0.8)) for a in np.linspace(0, 2 * math.pi, 9)[:-1] + 0.2 if keep(a)]
            fob = K.boxes(f"Support feet ({half})", feet, steel)
            fob.parent = self.root
            if half == "south":
                self.south.append(fob)
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
            r = K.cube(f"Signal red {x}", (x, -8.0, 5.4), (0.6, 0.6, 0.6), self.red)
            g = K.cube(f"Signal green {x}", (x, -8.0, 4.6), (0.6, 0.6, 0.6), self.green)
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
            sr.inputs["Emission Strength"].default_value = 60.0 if win else 0.0
            sg.inputs["Emission Color"].default_value = (0.05, 1.0, 0.3, 1)
            sg.inputs["Emission Strength"].default_value = 0.0 if win else 45.0
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


def tower_crane(name, base_xy, jib_heading, height=48.0, jib=50.0):
    """A tower crane: lattice mast (striped), jib and counter-jib with its weight, cab, hook line."""
    yel, N, bsdf = principled(f"{name} yellow", (0.85, 0.62, 0.05), rough=0.5)
    pos = N.new("ShaderNodeTexCoord").outputs["Object"]
    _, _, z = N.xyz(pos)
    lattice = N.math("LESS_THAN", N.math("PINGPONG", N.math("ADD", z, N.math("MULTIPLY", N.xyz(pos)[0], 1.0)), 1.0), 0.18)
    N.put(bsdf.inputs["Base Color"], N.mix(lattice, (0.85, 0.62, 0.05), (0.12, 0.10, 0.06)))
    conc = material(f"{name} weight", (0.5, 0.5, 0.48), rough=0.8)
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    root.location = (base_xy[0], base_xy[1], 0.0)
    root.rotation_euler = (0.0, 0.0, -jib_heading)
    parts = [K.cube(f"{name} mast", (0.0, 0.0, height / 2), (2.0, 2.0, height), yel),
             K.cube(f"{name} jib", (0.0, jib / 2, height + 1.0), (1.4, jib, 1.8), yel),
             K.cube(f"{name} counter-jib", (0.0, -7.5, height + 0.8), (1.6, 15.0, 1.2), yel),
             K.cube(f"{name} counterweight", (0.0, -13.0, height - 0.6), (2.4, 3.0, 2.6), conc),
             K.cube(f"{name} cab", (1.6, 1.0, height - 1.2), (1.4, 2.0, 2.0), material(f"{name} cab", (0.85, 0.85, 0.82), rough=0.4)),
             K.cube(f"{name} peak", (0.0, 0.0, height + 6.0), (1.0, 1.0, 10.0), yel),
             K.cube(f"{name} line", (0.0, jib * 0.6, height / 2 + 6.0), (0.05, 0.05, height - 12.0), material(f"{name} line", (0.05, 0.05, 0.05))),
             K.cube(f"{name} hook block", (0.0, jib * 0.6, 12.0), (0.8, 0.8, 1.2), conc)]
    for ob in parts:
        ob.parent = root
    return root


def build_city():
    ground = textured("Plain ground", (0.17, 0.20, 0.10), (0.27, 0.27, 0.15), 0.012, rough=0.95, bump=0.15)
    K.cube("Ground", (0.0, 0.0, -0.55), (6000.0, 6000.0, 0.5), ground)
    dirt = textured("Construction site", (0.30, 0.24, 0.17), (0.42, 0.35, 0.26), 0.08, rough=0.95, bump=0.3)
    K.cube("Construction site", (0.0, -32.0, -0.285), (330.0, 38.0, 0.04), dirt)
    tower_crane("Tower crane west", (-70.0, -42.0), math.radians(200.0))
    tower_crane("Tower crane east", (90.0, 26.0), math.radians(20.0), height=44.0)
    cabin = material("Site cabins", (0.88, 0.88, 0.85), rough=0.6)
    blue = material("Cabin roofs", (0.10, 0.25, 0.55), rough=0.5)
    cabins, roofs = [], []
    for k in range(4):
        for lvl in range(2):
            c = (-118.0 + 6.4 * k, -44.0, 1.3 + 2.7 * lvl - 0.3)
            cabins.append((c, (6.0, 2.5, 2.6)))
            roofs.append(((c[0], c[1], c[2] + 1.35), (6.1, 2.6, 0.1)))
    K.boxes("Site cabins", cabins, cabin)
    K.boxes("Cabin roofs", roofs, blue)
    road = textured("Street asphalt", (0.08, 0.08, 0.085), (0.12, 0.12, 0.125), 3.0, rough=0.85, bump=0.1)
    K.boxes("Streets", [((0.0, -60.0, -0.29), (3000.0, 16.0, 0.02)), ((0.0, 70.0, -0.29), (3000.0, 16.0, 0.02)),
                        ((-200.0, 0.0, -0.29), (16.0, 3000.0, 0.02))], road)
    wall = textured("Apartment walls", (0.70, 0.68, 0.63), (0.82, 0.80, 0.76), 2.0, rough=0.8, bump=0.1)
    win = material("Apartment windows", (0.10, 0.12, 0.15), metal=0.3, rough=0.15)
    rng = random.Random(30)
    blocks, wins, low = [], [], []
    keep_clear = [((112.0, -124.5), 45.0), ((-175.0, 8.0), 30.0), ((-450.0, -16.0), 30.0)]     # round cameras that stand in the city

    def clear(x, y, r):
        return all(math.dist((x, y), c) > rr + r for c, rr in keep_clear)
    for k in range(200):
        x = rng.uniform(-900, 900)
        y = rng.choice((-1, 1)) * rng.uniform(95, 650)
        if (abs(x - PX) < 150 and abs(y) < 160) or not clear(x, y, 20.0):
            continue
        w, d, h = rng.uniform(16, 26), rng.uniform(12, 18), rng.uniform(25, 75)
        blocks.append(((x, y, h / 2 - 0.3), (w, d, h)))
        for z in np.arange(3.0, h - 2, 3.0):
            wins.append(((x, y - d / 2 - 0.02, z), (w - 2.0, 0.05, 1.3)))
            wins.append(((x, y + d / 2 + 0.02, z), (w - 2.0, 0.05, 1.3)))
    for k in range(420):                                                       # low buildings: sheds, shops, houses
        x = rng.uniform(-700, 700)
        y = rng.choice((-1, 1)) * rng.uniform(22, 500)
        if (abs(x - PX) < 175 and abs(y) < 140) or abs(abs(y) - 65) < 14 or abs(x + 200) < 12 or not clear(x, y, 15.0):
            continue
        w, d, h = rng.uniform(10, 34), rng.uniform(8, 22), rng.uniform(4, 12)
        low.append(((x, y, h / 2 - 0.3), (w, d, h)))
    K.boxes("Apartment blocks", blocks, wall)
    K.boxes("Apartment windows", wins, win)
    roofs = [textured(f"Low roofs {k}", c1, c2, 0.5, rough=0.8, bump=0.1) for k, (c1, c2) in
             enumerate((((0.55, 0.30, 0.22), (0.62, 0.36, 0.26)), ((0.30, 0.38, 0.48), (0.36, 0.44, 0.54)), ((0.62, 0.60, 0.56), (0.70, 0.68, 0.64))))]
    for k in range(3):
        K.boxes(f"Low buildings {k}", low[k::3], roofs[k])
    lots = []
    for k in range(70):                                                        # fields, yards and car parks break up the plain
        x = rng.uniform(-900, 900)
        y = rng.choice((-1, 1)) * rng.uniform(20, 700)
        if abs(x - PX) < 170 and abs(y) < 70:
            continue
        lots.append(((x, y, -0.295), (rng.uniform(40, 140), rng.uniform(30, 110), 0.01)))
    lot_mats = [textured("Fields", (0.36, 0.30, 0.18), (0.44, 0.38, 0.24), 0.05, rough=0.95, bump=0.2),
                textured("Car parks", (0.22, 0.22, 0.23), (0.30, 0.30, 0.31), 0.5, rough=0.9, bump=0.05),
                textured("Young crops", (0.22, 0.30, 0.10), (0.30, 0.38, 0.14), 0.08, rough=0.95, bump=0.2)]
    for k in range(3):
        K.boxes(f"Lots {k}", lots[k::3], lot_mats[k])
    leaf = textured("Street trees", (0.07, 0.14, 0.04), (0.14, 0.22, 0.07), 1.0, rough=0.9, bump=0.5)
    crowns = []
    for x in np.arange(-900, 900, 14.0):
        for y in (-70.0, -50.0, 60.0, 80.0):
            if abs(x - PX) < 25 and y < 0:
                continue
            crowns.append(K.cyl_geom(2.6, 4.0, (x + rng.uniform(-2, 2), y, 4.0), (0, 0, 0), 8))
    merged("Street trees", crowns, leaf, smooth=True)


class TurnWedge:
    """The angle the bridge has swept (translucent gold, just above the deck): two sectors on the pier, from where each half of the
    deck started to where it is now, with a bright rim; drawn for the "fifty-two degrees" line."""
    N_ARC = 64

    def __init__(self):
        n = self.N_ARC
        g = ghost_material("Turn angle", (1.0, 0.78, 0.25), 3.0, 0.42)
        rim = material("Turn angle rim", (1.0, 0.85, 0.4), rough=0.4, emission=8.0)
        faces = []
        for half in range(2):
            o = half * (n + 1)
            faces += [(o, o + 1 + i, o + 2 + i) for i in range(n - 1)]
        self.fill = K.Sheet("Turn angle", np.zeros((2 * (n + 1), 3)), faces, [g], smooth=False)
        rf = []
        for half in range(2):
            o = half * 2 * n
            rf += [(o + i, o + i + 1, o + n + i + 1, o + n + i) for i in range(n - 1)]
        self.rim = K.Sheet("Turn angle rim", np.zeros((4 * n, 3)), rf, [rim], smooth=False)
        self.objs = [self.fill.ob, self.rim.ob]

    def set(self, on, t):
        for ob in self.objs:
            ob.hide_render = not on
        n, z = self.N_ARC, sm.DECK_TOP + 1.6
        R = sm.HALF
        hs = np.linspace(sm.HEAD0, sm.heading(t), n)
        fill, rim = [], []
        for half in range(2):
            a = hs + half * math.pi
            fill.append(np.array([[PX, PY, z]]))
            fill.append(np.stack([PX + R * np.sin(a), PY + R * np.cos(a), np.full(n, z)], 1))
            for rr_ in (R - 2.5, R + 0.5):
                rim.append(np.stack([PX + rr_ * np.sin(a), PY + rr_ * np.cos(a), np.full(n, z + 0.05)], 1))
        self.fill.set(np.vstack(fill))
        self.rim.set(np.vstack(rim))
        return math.degrees(sm.turned(t))


class Clock:
    """A clock's minute hand (translucent) turning about the pier at clock speed, over a ring of minute ticks."""

    def __init__(self):
        g = ghost_material("Ghost clock", (1.0, 0.85, 0.4), 5.0, 0.45)
        R = 70.0
        zc = sm.DECK_TOP + 2.5
        ticks = []
        for k in range(60):
            a = 2 * math.pi * k / 60
            L = 9.0 if k % 5 == 0 else 4.0
            ticks.append(((PX + (R - L / 2) * math.sin(a), PY + (R - L / 2) * math.cos(a), zc), (1.4 if k % 5 == 0 else 0.8, L, 0.15)))
        self.ticks = K.boxes("Clock ticks", ticks, g)
        for ob in self.ticks.data.vertices:
            pass
        self.hand_root = bpy.data.objects.new("Minute hand", None)
        bpy.context.collection.objects.link(self.hand_root)
        self.hand_root.location = (PX, PY, zc + 0.1)
        self.hand = K.cube("Minute hand bar", (0.0, R * 0.45, 0.0), (3.0, R * 0.9, 0.15), g)
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
    wedge = TurnWedge()
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    segs = tl.segments()
    print("SWIVEL_SCENE " + json.dumps({"objects": len(bpy.data.objects)}), flush=True)

    def render(sh, path):
        scene.render.resolution_x, scene.render.resolution_y = round(FRAME[0] * args.res_scale), round(FRAME[1] * args.res_scale)
        t = sh["t"]
        flags = {k: sh.get(k) for k in ("ghost", "section", "clock", "angle")}
        h = bridge.set(t, flags)
        win, trains = rail.set(t)
        hand = clock.set(bool(flags["clock"]), t)
        swept = wedge.set(bool(flags["angle"]), t)
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
        lo, hi = tl.deck_local_box()
        box = hook_gate.project_box(scene, cam, bridge.root.matrix_world.copy(), lo, hi)
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        return {"t": round(t, 6), "heading": round(h, 6), "turned_deg": round(math.degrees(sm.turned(t)), 4), "window": win, "trains_x": trains,
                "over_tracks": sm.over_tracks(t), "ghost": bool(flags["ghost"]), "section": bool(flags["section"]), "clock": bool(flags["clock"]),
                "minute_hand_deg": round(math.degrees(hand), 3), "angle": bool(flags["angle"]), "angle_drawn_deg": round(swept, 4) if flags["angle"] else None,
                "subject_box": box, "cam_world": [round(x, 3) for x in loc],
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
