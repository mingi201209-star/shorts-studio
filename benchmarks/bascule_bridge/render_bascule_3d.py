"""EP.25 drawbridge: 100 % 3D renderer (Blender, Cycles CPU), house style of EP.13-EP.24 (low sun, depth of field). A green river
between stone walls in a city of brick and glass towers; three Chicago-type double-leaf bascule bridges cross it. The hero bridge has
the full machinery: each leaf is a steel deck on deep girders that turns on a trunnion shaft; behind the trunnion its tail carries a
concrete counterweight that hangs in a pit under the street; a curved rack on the tail meshes with a pinion driven by a small motor.
Bridge houses at the corners, gates with red lights, cars waiting (the CC0 sedan in house red at the front), a sailboat motoring
through.

Everything moves from bascule_motion: the leaves' angle (up in about a minute, down again later; the other bridges a little later
in turn), the counterweight swinging down into the pit, the pinion turning against the rack, the gates, the red lights blinking, the
sailboat's run. Section shots cut the street, the pier, the pit, the counterweight and the leaf open along the bridge's middle. No
text anywhere in the scene."""
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
from benchmarks.bascule_bridge import bascule_motion as bm  # noqa: E402
from benchmarks.bascule_bridge import bascule_timeline as tl  # noqa: E402
from benchmarks.belt_limiter import render_belt_3d as rb  # noqa: E402  (car paint tint)
from benchmarks.can_opener import render_opener_3d as K  # noqa: E402  (data-API mesh helpers)
from benchmarks.manhole_blast.render_manhole_3d import facade_lit  # noqa: E402
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402
from benchmarks.rock_net.render_rocknet_3d import merged, textured  # noqa: E402

material = base.material
cube, boxes, cyl, cyl_geom, new_object = K.cube, K.boxes, K.cyl, K.cyl_geom, K.new_object
FRAME = (1080, 1920)
RIVER_X = 30.0                          # river walls and pier faces at x = +-30
WATER_Z = -5.0
HALF_W = 9.0                            # deck half width (roadway 14 m + sidewalks)
PIT = (32.0, 48.0, -18.0, -0.6)         # x0, x1, z0, z1 of the counterweight pit (east side; the west one is mirrored)
PIT_Y = 9.6
STREET_Y = 10.5
LEAF_U = (-bm.TAIL_L, bm.LEAF_L)
CW_U, CW_V = bm.CW_BOX
RACK_R, RACK_Y = bm.RACK_R, 8.6
PINION_R = bm.PINION_R
PINION_ANG = math.radians(285.0)        # where the pinion meshes, measured in the leaf's (u, v) plane from the river direction
BRIDGES = ((0.0, 0.0), (140.0, 28.0), (280.0, 56.0))      # y and the delay of each bridge's opening (the boat reaches it later)
PAINT = (1.75, 0.30, 0.24)


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


class Split:
    """Builds boxes and meshes in two halves at y = 0 (around the hero bridge) so section shots can hide the near half."""

    def __init__(self):
        self.south = []

    def box(self, name, c, d, mat, parent=None):
        y0, y1 = c[1] - d[1] / 2, c[1] + d[1] / 2
        out = []
        for lo, hi, tag in ((y0, min(y1, 0.0), "S"), (max(y0, 0.0), y1, "N")):
            if hi - lo < 1e-6:
                continue
            ob = cube(f"{name} {tag}", (c[0], (lo + hi) / 2, c[2]), (d[0], hi - lo, d[2]), mat)
            if parent is not None:
                ob.parent = parent
            if tag == "S":
                self.south.append(ob)
            out.append(ob)
        return out

    def mesh(self, name, parts, mat, parent=None, smooth=False):
        """parts: [(verts, faces)], each wholly on one side of y = 0 (by its first vertex)."""
        south = [p for p in parts if p[0][0][1] < 0]
        north = [p for p in parts if p[0][0][1] >= 0]
        out = []
        for tag, ps in (("S", south), ("N", north)):
            if not ps:
                continue
            ob = merged(f"{name} {tag}", ps, mat, smooth=smooth)
            if parent is not None:
                ob.parent = parent
            if tag == "S":
                self.south.append(ob)
            out.append(ob)
        return out


def girder_profile(u0, u1, top, depth_fn, n=24):
    """(u, v) outline of a girder: flat top, curved bottom (deep near the trunnion)."""
    us = np.linspace(u0, u1, n)
    top_pts = [(u, top) for u in us]
    bot_pts = [(u, top - depth_fn(u)) for u in us[::-1]]
    return top_pts + bot_pts


def prism(outline_uv, y0, y1, side):
    """A plate from a (u, v) outline between y0 and y1, in a leaf's local frame (x = -side * u, z = v)."""
    n = len(outline_uv)
    vs = [(-side * u, y0, v) for u, v in outline_uv] + [(-side * u, y1, v) for u, v in outline_uv]
    fs = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))]
    fs += [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)]
    return vs, fs


def box_uv(side, u0, u1, y0, y1, v0, v1):
    xa, xb = sorted((-side * u0, -side * u1))
    return K.box_verts(((xa + xb) / 2, (y0 + y1) / 2, (v0 + v1) / 2), (xb - xa, y1 - y0, v1 - v0)), K.BOX_FACES


class Leaf:
    """One leaf of a bascule: deck, sidewalks, markings, girders, railings, lamp posts; on the hero bridge also the tail,
    counterweight and rack. Built around a pivot (an empty at the trunnion) that turns about y."""

    def __init__(self, side, by, mats, split: Split | None, hero):
        self.side = side
        self.pivot = bpy.data.objects.new(f"Leaf pivot {side} {by:.0f}", None)
        bpy.context.collection.objects.link(self.pivot)
        self.pivot.location = (side * bm.TRUNNION_X, by, bm.TRUNNION_Z)
        self.pivot.rotation_mode = "XYZ"
        v_top = -bm.TRUNNION_Z
        u0 = LEAF_U[0] if hero else -1.0
        sp = split if (hero and split) else None

        def add_box(name, u_a, u_b, ya, yb, va, vb, mat):
            vs, fs = box_uv(side, u_a, u_b, ya, yb, va, vb)
            if sp is not None:
                sp.mesh(name, [(vs, fs)], mat, self.pivot)
            else:
                ob = new_object(name, vs, fs, mat)
                ob.parent = self.pivot

        for ya, yb in ((-HALF_W, 0.0), (0.0, HALF_W)):
            add_box("Deck", u0, LEAF_U[1], ya, yb, v_top - 0.4, v_top, mats["deck"])
        for sy in (-1, 1):
            add_box("Sidewalk", u0, LEAF_U[1], sy * 7.0 if sy > 0 else -HALF_W, HALF_W if sy > 0 else -7.0, v_top, v_top + 0.18, mats["walk"])
        marks = []
        for dy in (-0.12, 0.12):
            marks.append(box_uv(side, u0 + 0.5, LEAF_U[1] - 0.3, dy - 0.06, dy + 0.06, v_top + 0.003, v_top + 0.012))
        for ly in (-3.5, 3.5):
            for k in range(int((LEAF_U[1] - u0) / 6)):
                ua = u0 + 1.0 + 6 * k
                marks.append(box_uv(side, ua, ua + 3.0, ly - 0.06, ly + 0.06, v_top + 0.003, v_top + 0.012))
        for vs, fs in marks:
            ob = new_object("Lane marks", vs, fs, mats["yellow"] if abs(vs[0][1]) < 1 else mats["white"])
            ob.parent = self.pivot
            if sp is not None and vs[0][1] < 0:
                sp.south.append(ob)

        def depth(u):
            if u >= 0:
                return 1.2 + 4.2 * max(0.0, 1.0 - u / bm.LEAF_L) ** 1.6
            return 5.4
        parts = []
        for gy in (-6.6, -0.25, 6.35) if hero else (-6.6, 6.35):
            outline = girder_profile(u0, LEAF_U[1] - 0.2, v_top - 0.4, depth)
            parts.append(prism(outline, gy, gy + 0.25 if abs(gy) < 1 else gy + 0.5, side))
            for k in range(int((LEAF_U[1] - max(u0, 0.0)) / 3.0)):
                u = max(u0, 0.0) + 1.5 + 3.0 * k
                d = depth(u)
                for sgn in (-1, 1):
                    yy = gy + (0.5 if sgn > 0 else -0.08)
                    parts.append(box_uv(side, u - 0.12, u + 0.12, yy - 0.04, yy + 0.04, v_top - 0.4 - d, v_top - 0.4))
        if sp is not None:
            sp.mesh("Girders", parts, mats["steel"], self.pivot)
        else:
            ob = merged("Girders", parts, mats["steel"])
            ob.parent = self.pivot
        rail = []
        for sy in (-1, 1):
            y = sy * (HALF_W - 0.1)
            rail.append(box_uv(side, u0 + 0.2, LEAF_U[1] - 0.2, y - 0.05, y + 0.05, v_top + 1.05, v_top + 1.15))
            rail.append(box_uv(side, u0 + 0.2, LEAF_U[1] - 0.2, y - 0.04, y + 0.04, v_top + 0.55, v_top + 0.62))
            for k in range(int((LEAF_U[1] - u0) / 1.2)):
                u = u0 + 0.4 + 1.2 * k
                rail.append(box_uv(side, u - 0.04, u + 0.04, y - 0.04, y + 0.04, v_top + 0.18, v_top + 1.1))
            for k in range(3):
                u = 6.0 + 11.0 * k
                rail.append(box_uv(side, u - 0.08, u + 0.08, y - 0.08, y + 0.08, v_top + 0.18, v_top + 4.6))
                rail.append(box_uv(side, u - 0.25, u + 0.25, y - 0.25, y + 0.25, v_top + 4.6, v_top + 5.1))
        if sp is not None:
            sp.mesh("Railings", rail, mats["rail"], self.pivot)
        else:
            ob = merged("Railings", rail, mats["rail"])
            ob.parent = self.pivot
        self.cw = []
        if hero:
            for ya, yb in ((-8.0, 0.0), (0.0, 8.0)):
                add_box("Counterweight", CW_U[0], CW_U[1], ya, yb, CW_V[0], CW_V[1], mats["cw"])
            arc, teeth = [], []
            a0, a1 = math.radians(200.0), math.radians(292.0)
            n = 40
            for k in range(n):
                a = a0 + (a1 - a0) * k / (n - 1)
                b = a0 + (a1 - a0) * (k + 1) / (n - 1)
                if k < n - 1:
                    pa = [(RACK_R - 0.35) * math.cos(a), (RACK_R - 0.35) * math.sin(a), RACK_R * math.cos(a), RACK_R * math.sin(a)]
                    pb = [(RACK_R - 0.35) * math.cos(b), (RACK_R - 0.35) * math.sin(b), RACK_R * math.cos(b), RACK_R * math.sin(b)]
                    quad = [(pa[0], pa[1]), (pa[2], pa[3]), (pb[2], pb[3]), (pb[0], pb[1])]
                    arc.append(prism(quad, RACK_Y - 0.25, RACK_Y + 0.25, side))
                c, s = math.cos(a), math.sin(a)
                tooth = [((RACK_R + dr) * c + dt * -s, (RACK_R + dr) * s + dt * c) for dr, dt in ((0.0, -0.09), (0.22, -0.05), (0.22, 0.05), (0.0, 0.09))]
                teeth.append(prism(tooth, RACK_Y - 0.25, RACK_Y + 0.25, side))
            ob = merged("Rack", arc + teeth, mats["gear"])
            ob.parent = self.pivot
            ob2 = merged("Rack arm", [box_uv(side, -7.0, -1.0, RACK_Y - 0.2, RACK_Y + 0.2, -3.2, 2.1)], mats["steel"])
            ob2.parent = self.pivot

    def set(self, theta):
        self.pivot.rotation_euler = (0.0, self.side * theta, 0.0)


class City:
    def __init__(self, split: Split, mats):
        stone = textured("River wall stone", (0.52, 0.49, 0.43), (0.66, 0.62, 0.55), 2.5, rough=0.9, bump=0.3)
        conc = textured("Pier concrete", (0.44, 0.43, 0.41), (0.58, 0.57, 0.54), 3.0, rough=0.9, bump=0.25)
        fill = textured("Fill and soil", (0.25, 0.20, 0.15), (0.36, 0.30, 0.23), 1.4, rough=0.95, bump=0.3)
        pave = textured("Pavement", (0.30, 0.30, 0.31), (0.40, 0.40, 0.41), 3.0, rough=0.85, bump=0.1)
        asphalt = textured("Street asphalt", (0.07, 0.07, 0.075), (0.12, 0.12, 0.125), 6.0, rough=0.85, bump=0.1)
        water = material("River", (0.035, 0.085, 0.07), rough=0.07)
        nt = water.node_tree
        bsdf = nt.nodes.get("Principled BSDF")
        tc = nt.nodes.new("ShaderNodeTexCoord")
        nz = nt.nodes.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 0.6
        nz.inputs["Detail"].default_value = 6.0
        nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.25
        nt.links.new(nz.outputs["Fac"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
        S = split
        S.box("River", (0.0, 0.0, WATER_Z), (2 * RIVER_X, 900.0, 0.1), water)
        for sx in (-1, 1):
            S.box(f"River wall {sx}", (sx * (RIVER_X + 0.6), 0.0, -4.0), (1.2, 900.0, 8.0), stone)
            S.box(f"Riverwalk {sx}", (sx * (RIVER_X - 1.6), 0.0, -3.6), (3.2, 900.0, 0.4), pave)
            x0, x1, z0, z1 = PIT
            px0, px1 = sx * x0, sx * x1
            cx = (px0 + px1) / 2
            S.box(f"Pier front {sx}", (sx * (RIVER_X + 1.6), 0.0, (z0 - 1.0 + z1) / 2), (0.8, 2 * PIT_Y + 2, z1 - z0 + 1.0), conc)
            S.box(f"Pier back {sx}", (sx * (x1 + 0.5), 0.0, (z0 + 0.0) / 2), (1.0, 2 * PIT_Y + 2, -z0), conc)
            for sy in (-1, 1):
                S.box(f"Pit wall {sx} {sy}", (cx, sy * (PIT_Y + 0.5), (z0 + 0.0) / 2), (abs(px1 - px0) + 2, 1.0, -z0), conc)
            S.box(f"Pit floor {sx}", (cx, 0.0, z0 - 0.5), (abs(px1 - px0) + 2, 2 * PIT_Y + 2, 1.0), conc)
            S.box(f"Pit roof {sx}", (sx * ((bm.TRUNNION_X + bm.TAIL_L + x1 + 1.0) / 2), 0.0, -0.3), (x1 + 1.0 - bm.TRUNNION_X - bm.TAIL_L, 2 * PIT_Y + 2, 0.6), conc)
            for sy in (-1, 1):
                S.box(f"Trunnion pedestal {sx} {sy}", (sx * bm.TRUNNION_X, sy * 9.15, (z0 + bm.TRUNNION_Z - 0.6) / 2), (1.6, 0.7, bm.TRUNNION_Z - 0.6 - z0), conc)
                S.box(f"Trunnion bearing {sx} {sy}", (sx * bm.TRUNNION_X, sy * 9.15, bm.TRUNNION_Z), (1.4, 0.8, 1.3), mats["gear"])
            for ya, yb in ((-9.6, 0.0), (0.0, 9.6)):
                ob = cyl(f"Trunnion {sx} {ya:.0f}", 0.45, yb - ya, (sx * bm.TRUNNION_X, (ya + yb) / 2, bm.TRUNNION_Z), mats["gear"], rot=(math.pi / 2, 0, 0), verts=24)
                if ya < 0:
                    S.south.append(ob)
            land_x1 = 700.0
            for ya, yb in ((-450.0, -PIT_Y - 1.0), (PIT_Y + 1.0, 450.0)):
                S.box(f"Bank fill {sx} {ya:.0f}", (sx * (RIVER_X + 1.2 + land_x1) / 2 + sx * 0.0, (ya + yb) / 2, -12.1), (land_x1 - RIVER_X - 1.2, yb - ya, 24.0), fill)
                S.box(f"Bank walk {sx} {ya:.0f}", (sx * (RIVER_X + 1.2 + land_x1) / 2, (ya + yb) / 2, 0.05), (land_x1 - RIVER_X - 1.2, yb - ya, 0.1), pave)
            S.box(f"Bank fill behind {sx}", (sx * (x1 + 1.0 + land_x1) / 2, 0.0, -12.1), (land_x1 - x1 - 1.0, 2 * PIT_Y + 2, 24.0), fill)
            S.box(f"Street {sx}", (sx * (bm.TRUNNION_X + bm.TAIL_L + land_x1) / 2, 0.0, -0.05), (land_x1 - bm.TRUNNION_X - bm.TAIL_L, 2 * STREET_Y, 0.1), asphalt)
        rng = random.Random(25)
        bricks = [(0.42, 0.18, 0.11), (0.58, 0.52, 0.44), (0.36, 0.20, 0.15), (0.66, 0.62, 0.55), (0.48, 0.30, 0.20)]
        fmats = [facade_lit(f"Facade {k}", c, 1.3 * k) for k, c in enumerate(bricks)]
        glass = material("Glass tower", (0.10, 0.14, 0.18), metal=0.7, rough=0.12)
        roof = material("Tower roof", (0.18, 0.18, 0.19), rough=0.9)
        for sx in (-1, 1):
            y = -430.0
            while y < 430.0:
                w = rng.uniform(22.0, 40.0)
                if any(abs(y + w / 2 - by) < w / 2 + STREET_Y + 2 for by, _ in BRIDGES):
                    y += 14.0
                    continue
                h = rng.uniform(30.0, 170.0) * (1.0 if abs(y) < 250 else 0.8)
                d = rng.uniform(20.0, 36.0)
                x = sx * (RIVER_X + 26.0 + d / 2 + rng.uniform(0.0, 6.0))
                m = glass if rng.random() < 0.3 else fmats[rng.randrange(len(fmats))]
                ob = cube("Tower", (x, y + w / 2, h / 2), (d, w - 2.0, h), m)
                ob2 = cube("Tower roof", (x, y + w / 2, h + 0.4), (d + 0.3, w - 1.7, 0.8), roof)
                if y + w < 0:
                    split.south += [ob, ob2]
                y += w + rng.uniform(1.0, 6.0)
        house = textured("Bridge house stone", (0.66, 0.62, 0.55), (0.76, 0.72, 0.64), 2.0, rough=0.85, bump=0.3)
        copper = material("Copper roof", (0.20, 0.36, 0.31), rough=0.5, metal=0.3)
        for by, _ in BRIDGES:
            for sx in (-1, 1):
                for sy in (-1, 1):
                    hx, hy = sx * (bm.TRUNNION_X + bm.TAIL_L + 2.8), by + sy * (HALF_W + 2.8)
                    a = cube("Bridge house", (hx, hy, 3.5), (5.0, 4.4, 7.0), house)
                    v, f = K.box_verts((hx, hy, 7.4), (5.6, 5.0, 0.8)), K.BOX_FACES
                    b = new_object("Bridge house cornice", v, f, house)
                    r = _hip_roof(hx, hy, 7.8, 2.8, 2.5, 2.4, copper)
                    if by == 0.0 and sy < 0:
                        split.south += [a, b, r]


def _hip_roof(cx, cy, z, hx, hy, h, mat):
    vs = [(cx - hx, cy - hy, z), (cx + hx, cy - hy, z), (cx + hx, cy + hy, z), (cx - hx, cy + hy, z), (cx, cy, z + h)]
    fs = [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4), (3, 2, 1, 0)]
    return new_object("Bridge house roof", vs, fs, mat)


class Gates:
    """Traffic gates (striped arms) and red lights on both approaches of the hero bridge."""

    def __init__(self, split: Split):
        red = material("Gate red", (0.65, 0.05, 0.04), rough=0.5)
        white = material("Gate white", (0.85, 0.85, 0.82), rough=0.5)
        post = material("Gate post", (0.12, 0.12, 0.13), metal=0.5, rough=0.5)
        self.lamp_m = material("Warning lamp", (1.0, 0.08, 0.04), rough=0.4, emission=0.0)
        self.arms = []
        for sx in (-1, 1):
            gx = sx * (bm.TRUNNION_X + bm.TAIL_L + 6.0)
            for sy in (-1, 1):
                py = sy * (STREET_Y - 0.6)
                pivot = bpy.data.objects.new(f"Gate pivot {sx} {sy}", None)
                bpy.context.collection.objects.link(pivot)
                pivot.location = (gx, py, 1.05)
                pivot.rotation_mode = "XYZ"
                L = STREET_Y - 0.9
                for k in range(8):
                    m = red if k % 2 == 0 else white
                    seg = cube("Gate arm", (0.0, -sy * (0.3 + L * (k + 0.5) / 8), 0.0), (0.12, L / 8, 0.12), m)
                    seg.parent = pivot
                    if sy < 0:
                        split.south.append(seg)
                p = cube("Gate post", (gx, py, 0.55), (0.35, 0.35, 1.1), post)
                lamp_post = cube("Signal post", (gx + sx * 0.8, py + sy * 0.4, 2.0), (0.15, 0.15, 4.0), post)
                lamp = K.sphere("Warning lamp", 0.22, (gx + sx * 0.6, py + sy * 0.4, 3.6), self.lamp_m)
                if sy < 0:
                    split.south += [p, lamp_post, lamp]
                self.arms.append((pivot, sy))

    def set(self, t, film_t):
        down = bm.gate_down(t)
        for pivot, sy in self.arms:
            pivot.rotation_euler = (-sy * (1.0 - down) * math.pi / 2, 0.0, 0.0)
        on = bm.gates_down(t) and (film_t * 2.0) % 1.0 < 0.55
        for n in self.lamp_m.node_tree.nodes:
            if n.type == "BSDF_PRINCIPLED":
                n.inputs["Emission Color"].default_value = (1.0, 0.1, 0.04, 1)
                n.inputs["Emission Strength"].default_value = 18.0 if on else 0.0
        return down


class Ship:
    """A sailboat motoring through with its sails furled: white hull, cabin, a tall mast."""

    def __init__(self):
        white = material("Hull white", (0.85, 0.86, 0.86), rough=0.3)
        deck = material("Teak deck", (0.45, 0.32, 0.20), rough=0.7)
        navy = material("Boot stripe", (0.06, 0.10, 0.25), rough=0.4)
        mast_m = material("Mast", (0.75, 0.76, 0.78), metal=0.8, rough=0.3)
        sail = material("Furled sail", (0.88, 0.86, 0.80), rough=0.8)
        self.root = bpy.data.objects.new("Sailboat", None)
        bpy.context.collection.objects.link(self.root)
        L, B = 15.0, 4.2
        sections = [(-L / 2, 0.75), (-L / 4, 1.0), (L / 4, 0.92), (L / 2 - 1.2, 0.45), (L / 2, 0.02)]
        vs, fs = [], []
        for y, s in sections:
            hb = B / 2 * s
            vs += [(-hb, y, 1.4), (hb, y, 1.4), (hb * 0.85, y, 0.2), (0.0, y, -1.2 * (0.4 + 0.6 * s)), (-hb * 0.85, y, 0.2)]
        n = 5
        for i in range(len(sections) - 1):
            for k in range(n):
                a, b = i * n + k, i * n + (k + 1) % n
                fs.append((a, b, b + n, a + n))
        fs.append(tuple(range(n))[::-1])
        hull = new_object("Hull", vs, fs, white)
        hull.parent = self.root
        parts = [(K.box_verts((0.0, -1.5, 1.45), (B * 0.85, L * 0.7, 0.1)), K.BOX_FACES)]
        merged("Deck", parts, deck).parent = self.root
        cube("Cabin", (0.0, -1.0, 2.1), (2.6, 4.5, 1.3), white).parent = self.root
        cube("Boot stripe", (0.0, 0.0, 0.25), (B * 0.86, L * 0.85, 0.15), navy).parent = self.root
        cyl("Mast", 0.12, 22.0, (0.0, 0.8, 12.4), mast_m, verts=10).parent = self.root
        ob = cyl("Boom", 0.09, 6.0, (0.0, -2.2, 4.0), mast_m, rot=(math.pi / 2, 0, 0), verts=8)
        ob.parent = self.root
        ob = cyl("Furled main", 0.28, 5.4, (0.0, -2.1, 4.35), sail, rot=(math.pi / 2, 0, 0), verts=10)
        ob.parent = self.root
        ob = cyl("Furled jib", 0.16, 18.0, (0.0, 4.8, 10.5), sail, rot=(math.radians(-17), 0, 0), verts=8)
        ob.parent = self.root

    def set(self, t, film_t):
        y = bm.ship_y(t)
        self.root.location = (bm.SHIP_X, y, WATER_Z + 0.05 + 0.06 * math.sin(1.3 * film_t))
        self.root.rotation_euler = (0.012 * math.sin(0.9 * film_t), 0.02 * math.sin(1.1 * film_t + 0.5), 0.0)
        return y


class Machinery:
    """The pinion and its motor in the east pit (fixed), turning as the rack on the leaf's tail passes."""

    def __init__(self, split: Split):
        gear = material("Gear steel", (0.25, 0.24, 0.22), metal=0.85, rough=0.35)
        motor_m = material("Motor housing", (0.12, 0.28, 0.42), metal=0.3, rough=0.45)
        u = (RACK_R + 0.22 + PINION_R) * math.cos(PINION_ANG)
        v = (RACK_R + 0.22 + PINION_R) * math.sin(PINION_ANG)
        self.center = (bm.TRUNNION_X - u, RACK_Y, bm.TRUNNION_Z + v)
        self.pinion = bpy.data.objects.new("Pinion", None)
        bpy.context.collection.objects.link(self.pinion)
        self.pinion.location = self.center
        self.pinion.rotation_mode = "XYZ"
        parts = [cyl_geom(PINION_R, 0.5, (0.0, 0.0, 0.0), (math.pi / 2, 0, 0), 28)]
        nt = 16
        for k in range(nt):
            a = 2 * math.pi * k / nt
            c, s = math.cos(a), math.sin(a)
            pts = [((PINION_R + dr) * c - dt * s, (PINION_R + dr) * s + dt * c) for dr, dt in ((-0.02, -0.08), (0.2, -0.045), (0.2, 0.045), (-0.02, 0.08))]
            vs = [(x, -0.25, z) for x, z in pts] + [(x, 0.25, z) for x, z in pts]
            fs = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
            parts.append((vs, fs))
        ob = merged("Pinion gear", parts, gear)
        ob.parent = self.pinion
        cx, cy, cz = self.center
        cube("Pinion shaft", (cx, cy - 0.9, cz), (0.3, 1.4, 0.3), gear)
        cube("Gearbox", (cx + 0.2, cy - 2.0, cz - 0.1), (1.4, 1.0, 1.4), motor_m)
        cyl("Motor", 0.55, 1.6, (cx + 0.2, cy - 3.3, cz - 0.1), motor_m, rot=(math.pi / 2, 0, 0), verts=20)
        cube("Machinery floor", (cx + 0.4, cy - 2.0, cz - 1.1), (3.0, 4.6, 0.3), gear)

    def set(self, theta):
        ang = bm.pinion_angle(theta)
        self.pinion.rotation_euler = (0.0, ang, 0.0)
        return ang


def build_cars():
    paints = [(0.85, 0.85, 0.82), (0.05, 0.05, 0.06), (0.10, 0.20, 0.45), (0.60, 0.62, 0.64), (0.95, 0.72, 0.05), (0.30, 0.05, 0.05)]
    glass = material("Car glass", (0.04, 0.05, 0.06), metal=0.2, rough=0.1)
    tyre = material("Tyre", (0.03, 0.03, 0.03), rough=0.8)
    spots = [(1, 61.5, 3.4), (1, 68.0, 3.2), (1, 56.0, 6.6), (1, 62.5, 6.8), (-1, -55.0, -3.4), (-1, -61.5, -3.2), (-1, -56.5, -6.6), (-1, -68.0, -3.5)]
    out = []
    for k, (heading, x, y) in enumerate(spots):
        body = material(f"Car paint {k}", paints[k % len(paints)], metal=0.4, rough=0.35)
        parts = [(K.box_verts((x, y, 0.62), (4.4, 1.8, 0.65)), K.BOX_FACES)]
        cab = merged("Car cabin", [(K.box_verts((x + heading * 0.2, y, 1.22), (2.3, 1.6, 0.6)), K.BOX_FACES)], glass)
        ob = merged("Car body", parts, body)
        wheels = merged("Car wheels", [cyl_geom(0.34, 0.25, (x + dx, y + dy, 0.34), (math.pi / 2, 0, 0), 14) for dx in (-1.35, 1.35) for dy in (-0.82, 0.82)], tyre)
        out += [ob, cab, wheels]
    return out


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
    scene.view_settings.exposure = 0.1
    if hasattr(scene.view_settings, "use_white_balance"):
        scene.view_settings.use_white_balance = True
        scene.view_settings.white_balance_temperature = 7400.0
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    sun_to = cinematic.sun_vector((0.75, -0.45), 15.0)
    cinematic.apply_sky(scene, sun_to, strength=0.28, dust=1.0)
    sd = bpy.data.lights.new("Sun", "SUN")
    sd.energy, sd.angle, sd.color = 5.0, 0.02, (1.0, 0.72, 0.48)
    sun = bpy.data.objects.new("Sun", sd)
    scene.collection.objects.link(sun)
    sun.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()
    wheel_nodes = {w["node"] for w in wheels.values()}
    parts = [o for o in car_root.children_recursive if o.type == "MESH" and not any(p in wheel_nodes for p in rb._ancestors(o))]
    ghost = rb.Ghost(parts)
    ghost.set_tint(PAINT)
    ghost.set_factor(0.0, 1e4, 4.0)
    car_root.location = (54.5, 3.4, 0.0)
    car_root.rotation_euler = (0.0, 0.0, math.pi / 2)
    split = Split()
    mats = {
        "deck": textured("Deck asphalt", (0.08, 0.08, 0.085), (0.13, 0.13, 0.135), 5.0, rough=0.85, bump=0.1),
        "walk": textured("Deck sidewalk", (0.42, 0.41, 0.39), (0.52, 0.51, 0.49), 2.0, rough=0.85, bump=0.1),
        "yellow": material("Centre line", (0.85, 0.62, 0.08), rough=0.6),
        "white": material("Lane line", (0.85, 0.85, 0.80), rough=0.6),
        "steel": material("Bridge steel", (0.16, 0.20, 0.22), metal=0.5, rough=0.5),
        "rail": material("Bridge railing", (0.05, 0.08, 0.07), metal=0.5, rough=0.45),
        "cw": textured("Counterweight concrete", (0.30, 0.29, 0.28), (0.42, 0.41, 0.39), 2.5, rough=0.9, bump=0.3),
        "gear": material("Gear steel", (0.25, 0.24, 0.22), metal=0.85, rough=0.35),
    }
    City(split, mats)
    leaves = []
    for by, delay in BRIDGES:
        for side in (1, -1):
            leaves.append((Leaf(side, by, mats, split if by == 0.0 else None, by == 0.0), delay, by))
    gates = Gates(split)
    ship = Ship()
    machinery = Machinery(split)
    cars = build_cars()
    for ob in cars:
        if ob.name.startswith("Car") and any(v.co.y < 0 for v in ob.data.vertices[:1]):
            split.south.append(ob)
    fd = bpy.data.lights.new("Section fill", "AREA")
    fd.energy, fd.size, fd.color = 2600.0, 14.0, (0.9, 0.93, 1.0)
    fill = bpy.data.objects.new("Section fill", fd)
    scene.collection.objects.link(fill)
    fill.location = (38.0, -16.0, -7.0)
    fill.rotation_euler = Vector((0.0, 1.0, 0.15)).to_track_quat("-Z", "Y").to_euler()
    pit_lights = []
    for sx in (-1, 1):
        for k, (px, pz) in enumerate(((36.0, -6.0), (44.0, -6.0), (40.0, -14.0))):
            ld = bpy.data.lights.new("Pit work light", "POINT")
            ld.energy, ld.color, ld.shadow_soft_size = 900.0, (1.0, 0.85, 0.65), 0.4
            lo = bpy.data.objects.new("Pit work light", ld)
            lo.location = (sx * px, 6.5, pz)
            scene.collection.objects.link(lo)
            pit_lights.append(lo)
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    hero_east = leaves[0][0]

    def render(sh, path):
        scene.render.resolution_x, scene.render.resolution_y = round(FRAME[0] * args.res_scale), round(FRAME[1] * args.res_scale)
        t, film_t = sh["t"], sh["film_t"]
        section = bool(sh.get("section"))
        for ob in split.south:
            ob.hide_render = section
        car_root.hide_render = False
        fill.hide_render = not section
        thetas = []
        for leaf, delay, by in leaves:
            th = bm.angle(t - delay)
            leaf.set(th)
            if leaf.side == 1:
                thetas.append(round(th, 6))
        down = gates.set(t, film_t)
        ship_y = ship.set(t, film_t)
        pin = machinery.set(bm.angle(t))
        c = sh["cam"]
        loc, tgt = Vector(c["loc"]), Vector(c["target"])
        dd = cam.data
        dd.sensor_fit, dd.sensor_width, dd.lens, dd.clip_start = "HORIZONTAL", 36.0, c["lens"], 0.05
        dd.clip_end = 6000.0
        dd.dof.use_dof = True
        dd.dof.focus_distance = (tgt - loc).length
        dd.dof.aperture_fstop = c.get("fstop", 8.0)
        base.set_camera(cam, loc, tgt)
        bpy.context.view_layer.update()
        box = hook_gate.project_box(scene, cam, hero_east.pivot.matrix_world, (-bm.LEAF_L, -HALF_W, -5.6), (bm.TAIL_L, HALF_W, 3.2))
        th0 = bm.angle(t)
        lowest = bm.cw_lowest_z(th0)
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        return {"t": round(t, 6), "theta": round(th0, 6), "theta_deg": round(math.degrees(th0), 3), "bridges_theta": thetas, "gates_down": round(down, 4),
                "lamps": bm.gates_down(t), "ship_y": round(ship_y, 3), "pinion": round(pin, 5), "cw_lowest_z": round(lowest, 3), "section": section,
                "subject_box": box, "cam_world": [round(x, 3) for x in loc], "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    segs = tl.segments()
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
        print("BASCULE_FRAME " + json.dumps(info), flush=True)
    (args.out / f"bascule-frames-{frames[0]:05d}.json").write_text(json.dumps({"renderer_source_sha256": src_sha, "frames": out}, indent=1))


if __name__ == "__main__":
    main()
