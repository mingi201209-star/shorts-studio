"""EP.09 scene pieces (Blender side, procedural; no scene text).
World: a two-lane road that follows hydro_motion's bend, lane lines, verges, the puddle (glossy water), spray from tyres in water.
Lab (far from the road, its own lights): two tread sections side by side (new 8 mm / worn 1.6 mm, drawn 10x size) with circumferential and
lateral grooves, sipes and wear bars; water running through the new grooves or pooling on the worn one; a side cutaway of a tyre on a water
film with the wedge that lifts it; a coin pushed into a groove (a plain generic coin, no portrait)."""
from __future__ import annotations

import math
import random

import bpy
from mathutils import Vector

from benchmarks.abs_brake import abs_parts as ap
from benchmarks.esc_stability.esc_parts import material
from benchmarks.hydroplaning import hydro_motion as hm

LAB = Vector((0.0, -600.0, 0.0))
LANE_W = 3.6


def _mesh(name, verts, faces, mat, parent=None, smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.update()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    ob.parent = parent
    if smooth:
        for p in ob.data.polygons:
            p.use_smooth = True
    return ob


def _strip(name, off0, off1, z, mat, y0=-40.0, y1=130.0, step=1.0, dash=None):
    """A strip between lateral offsets off0..off1 from the lane centre, following the bend. dash=(on, period) for dashed paint."""
    verts, faces = [], []
    y = y0
    while y < y1:
        ya, yb = y, min(y + step, y1)
        if dash is None or (ya % dash[1]) < dash[0]:
            quad = []
            for yy, o in ((ya, off0), (ya, off1), (yb, off1), (yb, off0)):
                h = hm.lane_heading(yy)
                cx = hm.lane_x(yy)
                quad.append((cx + o * math.cos(h), yy + o * math.sin(h), z))
            i = len(verts)
            verts += quad
            faces.append((i, i + 1, i + 2, i + 3))
        y += step
    return _mesh(name, verts, faces, mat)


def build_world():
    asphalt = material("Wet asphalt", (0.055, 0.055, 0.06), rough=0.45)
    paint = material("Line paint", (0.85, 0.85, 0.82), rough=0.5)
    grass = material("Verge", (0.10, 0.16, 0.06), rough=0.95)
    bpy.ops.mesh.primitive_plane_add(size=600, location=(0, 40, -0.02))
    g = bpy.context.object
    g.name = "Ground"
    g.data.materials.append(grass)
    objs = [g]
    objs.append(_strip("Road", -LANE_W * 1.5 - 0.6, LANE_W * 0.5 + 0.6, 0.0, asphalt, step=0.5))
    objs.append(_strip("Edge line right", LANE_W / 2 + 0.05, LANE_W / 2 + 0.2, 0.003, paint, step=0.5))
    objs.append(_strip("Edge line left", -LANE_W * 1.5 - 0.2, -LANE_W * 1.5 - 0.05, 0.003, paint, step=0.5))
    objs.append(_strip("Centre dashes", -LANE_W / 2 - 0.07, -LANE_W / 2 + 0.07, 0.003, paint, step=0.5, dash=(2.0, 5.0)))
    water = material("Puddle water", (0.10, 0.13, 0.16), rough=0.02)
    w = water.node_tree.nodes.get("Principled BSDF")
    w.inputs["Coat Weight"].default_value = 1.0
    rng = random.Random(7)
    verts, faces = [], []
    n = 72
    cy = (hm.PUDDLE_Y0 + hm.PUDDLE_Y1) / 2
    ry = (hm.PUDDLE_Y1 - hm.PUDDLE_Y0) / 2
    pts = []
    for k in range(n):
        a = 2 * math.pi * k / n
        wob = 1.0 + 0.08 * math.sin(3 * a + 1.0) + 0.05 * math.sin(7 * a) + 0.03 * rng.uniform(-1, 1)
        yy = cy + ry * math.sin(a) * wob
        xx = hm.lane_x(yy) + hm.PUDDLE_HALF_W * math.cos(a) * wob
        pts.append((xx, yy, 0.006))
    verts = [(hm.lane_x(cy), cy, 0.006)] + pts
    faces = [(0, 1 + k, 1 + (k + 1) % n) for k in range(n)]
    objs.append(_mesh("Puddle", verts, faces, water))
    return objs


class Spray:
    """Droplets thrown up behind and beside each tyre while it runs through water. Deterministic: droplets emitted at earlier times
    fly on ballistic paths; positions at time t are computed, then one mesh of tiny cubes is rebuilt."""
    WHEELS = ((-0.709, 1.087), (0.709, 1.087), (-0.709, -1.225), (0.709, -1.225))

    def __init__(self):
        self.mat = material("Spray", (0.75, 0.82, 0.90), rough=0.1)
        self.mat.node_tree.nodes.get("Principled BSDF").inputs["Alpha"].default_value = 0.7
        self.ob = _mesh("Spray", [], [], self.mat)

    def update(self, tread, t):
        verts, faces = [], []
        if t > 0:
            te = max(0.0, t - 0.6)
            k = 0
            while te < t:
                s = hm.at(tread, te)
                c, sn = math.cos(s["heading"]), math.sin(s["heading"])
                fwd = Vector((-sn, c, 0.0))
                for wi, (wx, wy) in enumerate(self.WHEELS):
                    px, py = s["x"] + wx * c - wy * sn, s["y"] + wx * sn + wy * c
                    if not hm.in_puddle(px, py):
                        continue
                    floating = s["grip_front"] < 0.5 and wi < 2
                    for j in range(3 if not floating else 5):
                        rng = random.Random(hash((tread, round(te, 3), wi, j)) & 0xFFFFFFFF)
                        v = fwd * (s["speed"] * rng.uniform(0.15, 0.45)) + Vector((math.copysign(rng.uniform(1.0, 3.5), wx), 0, rng.uniform(1.5, 4.0 if not floating else 5.5)))
                        if floating:
                            v += fwd * s["speed"] * 0.35                     # bow wave thrown ahead of a floating tyre
                        a = t - te
                        p = Vector((px, py, 0.05)) + v * a + Vector((0, 0, -0.5 * 9.81 * a * a))
                        if p.z < 0.0:
                            continue
                        sz = 0.025 + 0.02 * rng.random()
                        i = len(verts)
                        verts += [p + Vector(d) * sz for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))]
                        faces += [(i, i + 2, i + 4), (i + 2, i + 1, i + 4), (i + 1, i + 3, i + 4), (i + 3, i, i + 4),
                                  (i + 2, i, i + 5), (i + 1, i + 2, i + 5), (i + 3, i + 1, i + 5), (i, i + 3, i + 5)]
                        k += 1
                te += 0.012
        me = bpy.data.meshes.new("Spray")
        me.from_pydata([tuple(v) for v in verts], [], faces)
        me.materials.append(self.mat)
        old = self.ob.data
        self.ob.data = me
        bpy.data.meshes.remove(old)


class Lab:
    """Close-up props at 10x size, away from the road: two tread sections, water on them, the wedge cutaway and the coin."""
    SCALE = 10.0

    def __init__(self):
        self.objs = []
        rubber = material("Tread rubber", (0.035, 0.035, 0.04), rough=0.75)
        bar_m = material("Wear bar", (0.06, 0.06, 0.07), rough=0.7)
        floor = material("Lab floor", (0.75, 0.77, 0.80), rough=0.6)
        self.water = material("Lab water", (0.25, 0.55, 0.95), rough=0.05)
        self.water.node_tree.nodes.get("Principled BSDF").inputs["Alpha"].default_value = 0.65
        bpy.ops.mesh.primitive_plane_add(size=80, location=LAB + Vector((15, 0, -0.01)))
        fl = bpy.context.object
        fl.name = "Lab floor"
        fl.data.materials.append(floor)
        self.objs.append(fl)
        back = material("Lab backdrop", (0.16, 0.19, 0.24), rough=0.9)
        for cx in (0.0, 30.0):                                      # a calm backdrop behind each set
            bpy.ops.mesh.primitive_plane_add(size=1, location=LAB + Vector((cx, 1.6, 2.0)), rotation=(math.radians(90), 0, 0))
            wall = bpy.context.object
            wall.name, wall.scale = "Lab backdrop", (14.0, 6.0, 1.0)
            wall.data.materials.append(back)
            self.objs.append(wall)
        fl_m = floor
        bpy.ops.object.light_add(type="AREA", location=LAB + Vector((30.5, -2.0, 3.0)))
        l2 = bpy.context.object
        l2.data.energy, l2.data.size = 900.0, 3.0
        l2.rotation_euler = Vector((-0.2, 0.6, -1.0)).to_track_quat("-Z", "Y").to_euler()
        self.objs.append(l2)
        bpy.ops.object.light_add(type="AREA", location=LAB + Vector((0.5, -2.0, 3.0)))
        lamp = bpy.context.object
        lamp.data.energy, lamp.data.size = 900.0, 3.0
        lamp.rotation_euler = Vector((-0.2, 0.6, -1.0)).to_track_quat("-Z", "Y").to_euler()
        self.objs.append(lamp)
        self.sections = {}
        for name, x0 in (("new", -0.42), ("worn", 0.42)):
            depth = hm.TREAD_MM[name] / 1000 * self.SCALE
            root = bpy.data.objects.new(f"Tread {name}", None)
            bpy.context.collection.objects.link(root)
            root.location = LAB + Vector((x0, 0, 0))
            self.objs += self._section(root, depth, rubber, bar_m)
            self.sections[name] = (root, depth)
        self.flow = _mesh("Groove water", [], [], self.water)
        self.pool = _mesh("Pooled water", [], [], self.water)
        self.objs += [self.flow, self.pool]
        # wedge cutaway: tyre seen from the side on a water film
        self.cut = bpy.data.objects.new("Wedge cutaway", None)
        bpy.context.collection.objects.link(self.cut)
        self.cut.location = LAB + Vector((30.0, 0.0, 0))          # far from the tread sections so it never shows behind them
        road = ap.rounded_box("Cutaway road", (0, 0, -0.05), (3.4, 0.4, 0.10), material("Cutaway road", (0.12, 0.12, 0.13), rough=0.8), self.cut, bevel=0.01)
        film = ap.rounded_box("Cutaway water film", (0, 0, 0.02), (3.4, 0.38, 0.04), self.water, self.cut, bevel=0.004)
        self.tyre_pivot = bpy.data.objects.new("Cutaway tyre", None)
        bpy.context.collection.objects.link(self.tyre_pivot)
        self.tyre_pivot.parent = self.cut
        tyre = ap.cylinder_x("Cutaway tyre", 0.62, -0.2, 0.2, 0, 0, rubber, self.tyre_pivot, n=96)
        rim = ap.cylinder_x("Cutaway rim", 0.38, -0.205, 0.205, 0, 0, material("Rim", (0.6, 0.6, 0.62), metal=1.0, rough=0.3), self.tyre_pivot, n=64)
        hub = ap.cylinder_x("Cutaway hub", 0.10, -0.21, 0.21, 0, 0, material("Hub", (0.2, 0.2, 0.22), metal=1.0, rough=0.4), self.tyre_pivot, n=32)
        self.tyre_pivot.rotation_euler = (0, 0, math.radians(90))
        self.wedge = _mesh("Water wedge", [], [], self.water)
        self.wedge.parent = self.cut
        self.objs += [road, film, tyre, rim, hub, self.wedge]
        # coin
        copper = material("Coin", (0.72, 0.38, 0.20), metal=1.0, rough=0.3)
        self.coin = bpy.data.objects.new("Coin", None)
        bpy.context.collection.objects.link(self.coin)
        disc = ap.cylinder_x("Coin disc", 0.095, -0.0075, 0.0075, 0, 0, copper, self.coin, n=64)
        ring = ap.sector("Coin rim", 0.085, 0.095, 0, 2 * math.pi, -0.010, 0.010, copper, self.coin, n=64)
        boss = ap.cylinder_x("Coin relief", 0.045, -0.010, 0.010, 0, 0.01, copper, self.coin, n=32)
        self.objs += [disc, ring, boss]

    def _section(self, root, depth, rubber, bar_m):
        """A 0.7 x 0.9 tread section: four ribs between three circumferential grooves; lateral notches; sipes; wear bars in the grooves."""
        objs = []
        W, L = 0.70, 0.90
        groove_w = 0.06
        base = ap.rounded_box("Tread base", (0, 0, -0.05), (W, L, 0.10), rubber, root, bevel=0.01)
        objs.append(base)
        rib_w = (W - 3 * groove_w) / 4
        for i in range(4):
            cx = -W / 2 + rib_w / 2 + i * (rib_w + groove_w)
            for j in range(5):
                cy = -L / 2 + 0.09 + j * 0.18
                blk = ap.rounded_box(f"Tread block {i}{j}", (cx, cy, depth / 2), (rib_w, 0.15, depth), rubber, root, bevel=min(0.01, depth / 3))
                objs.append(blk)
                if depth > 0.03:
                    for s in (-0.035, 0.035):                         # sipes: thin slits across the block
                        objs.append(ap.rounded_box(f"Sipe {i}{j}{s}", (cx, cy + s, depth - 0.012), (rib_w * 0.8, 0.004, 0.026), material("Sipe", (0.0, 0.0, 0.0), rough=1.0), root, bevel=0.001))
        for g in range(3):
            gx = -W / 2 + rib_w + groove_w / 2 + g * (rib_w + groove_w)
            objs.append(ap.rounded_box(f"Wear bar {g}", (gx, 0.0, 0.016 / 2), (groove_w, 0.05, 0.016), bar_m, root, bevel=0.003))
        return objs

    def update(self, t, worn_float, mode):
        """mode: 'flow' (water runs through the new grooves), 'pool' (water sits on the worn tread), or None."""
        verts, faces = [], []
        if mode == "flow":
            root, depth = self.sections["new"]
            for g in range(3):
                gx = -0.19 + g * 0.19                 # groove centres of the 0.70-wide section (ribs 0.13, grooves 0.06)
                for k in range(14):
                    y = ((k / 14 + t * 1.6) % 1.0) * 0.9 - 0.45
                    c = root.location + Vector((gx, y, depth * 0.45))
                    i = len(verts)
                    s = 0.018
                    verts += [c + Vector(d) * s for d in ((1, 0, 0), (-1, 0, 0), (0, 2, 0), (0, -2, 0), (0, 0, 1), (0, 0, -1))]
                    faces += [(i, i + 2, i + 4), (i + 2, i + 1, i + 4), (i + 1, i + 3, i + 4), (i + 3, i, i + 4),
                              (i + 2, i, i + 5), (i + 1, i + 2, i + 5), (i + 3, i + 1, i + 5), (i, i + 3, i + 5)]
        me = bpy.data.meshes.new("Groove water")
        me.from_pydata([tuple(v) for v in verts], [], faces)
        me.materials.append(self.water)
        old = self.flow.data
        self.flow.data = me
        bpy.data.meshes.remove(old)
        root, depth = self.sections["worn"]
        pv, pf = [], []
        if mode == "pool":
            h = 0.03 + 0.03 * min(1.0, t)
            c = root.location
            pv = [c + Vector(v) for v in ((-0.36, -0.46, depth + h), (0.36, -0.46, depth + h), (0.36, 0.46, depth + h), (-0.36, 0.46, depth + h))]
            pf = [(0, 1, 2, 3)]
        me = bpy.data.meshes.new("Pooled water")
        me.from_pydata([tuple(v) for v in pv], [], pf)
        me.materials.append(self.water)
        old = self.pool.data
        self.pool.data = me
        bpy.data.meshes.remove(old)
        # wedge: grows with the float fraction; the tyre lifts (lift exaggerated to be visible)
        lift = 0.14 * worn_float                                    # exaggerated so the water layer under the tyre is visible
        self.tyre_pivot.location = (0, 0, 0.62 + 0.024 + lift)
        L = 0.35 + 0.95 * worn_float
        hgt = 0.04 + lift
        wv = [(0.10, 0, 0.04), (-0.10 - L, 0, 0.04), (0.10, 0, 0.04 + hgt)]
        wv = [(x, y + s, z) for s in (-0.18, 0.18) for (x, y, z) in wv]
        wf = [(0, 1, 2), (3, 5, 4), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)]
        me = bpy.data.meshes.new("Water wedge")
        me.from_pydata(wv, [], wf)
        me.materials.append(self.water)
        old = self.wedge.data
        self.wedge.data = me
        bpy.data.meshes.remove(old)
        self.tyre_pivot.rotation_euler = (0, 0, math.radians(90))
        self.tyre_pivot.rotation_euler.rotate_axis("X", -t * 8.0)

    def place_coin(self, which, insert):
        """Coin standing in the middle groove of the chosen section, pushed in by `insert` (0..1)."""
        root, depth = self.sections[which]
        z = 0.095 + (1.0 - insert) * 0.25                    # pushed down until its edge touches the groove floor
        self.coin.location = root.location + Vector((0.0, 0.2, z))   # middle groove, face along the groove walls

    def set_visible(self, on):
        for ob in self.objs + [c for c in self.coin.children]:
            ob.hide_render = not on
