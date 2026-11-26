"""EP.34 runaway-truck arrester nets: 100 % 3D renderer (Blender, Cycles CPU), house style of EP.13-EP.33 (golden hour, depth of
field). A mountain highway and, beside it, an escape ramp between two concrete walls. Eight steel cable nets hang across the ramp
from posts on the walls. Each side edge of a net is tied to two steel tapes that run into an energy absorber inside the wall: a steel
box with two coils of tape and a row of offset pins.

A runaway semi (red tractor, white box trailer) plows into the nets. Each net it picks up wraps its front, the net's sides stretch
back toward the walls and the tapes run out: the coils shrink and spin, and the tape slides through the pins. Cut-away shots remove
the wall's inner face and the box's side plate at net 2. The rating shot uses a 90,000 lb tanker at 90 mph. The reset shot shows the
crew lowering a fresh coil into net 1's absorber. Everything that moves comes from net_motion. No text."""
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
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402
from benchmarks.truck_net import net_motion as m  # noqa: E402
from benchmarks.truck_net import net_timeline as tl  # noqa: E402

material, cube = base.material, base.cube
FRAME = (1080, 1920)
WX = m.WALL_X
WALL_Y = (-45.0, 150.0)
ROAD = (-25.0, -10.2)            # the highway's paved width (four lanes; the downhill pair on the right)
DETAIL = {0: "open", 1: "cut"}   # nets whose right-hand absorber is built inside: 0 for the crew, 1 (net 2) for the cut-away
BOX_X = (WX + 0.08, WX + 0.82)
BOX_DY = (-2.75, -0.06)          # along y, relative to the net's station
BOX_Z = (0.12, 1.55)
COIL_X, COIL_DY = WX + 0.48, -2.05
R_HUB, TAPE_TH = 0.10, 0.0016    # coil hub radius; tape thickness for the coil's radius
PIN_X, PIN_R, PIN_A = WX + 0.40, 0.038, 0.05
PIN_DY = [-1.40 + 0.13 * j for j in range(6)]
TICK = 0.30                      # spacing of the dark marks along the tape inside the box (they show it moving)
NU, NZ = 25, 7                   # the net's vertical and horizontal cables


def arguments():
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--res-scale", type=float, default=0.5)
    p.add_argument("--samples", type=int, default=16)
    p.add_argument("--frames", default="0-0")
    p.add_argument("--list", default="")
    p.add_argument("--source", type=Path, default=None)          # unused (no CC0 car here); kept so the shared render scripts can pass it
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return p.parse_args(argv)


def flat(ob):
    for poly in ob.data.polygons:
        poly.use_smooth = False
    return ob


def mesh_object(name, verts, faces, mat):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(mat)
    return flat(ob)


def cyl(name, r, depth, loc, mat, rot=(0.0, 0.0, 0.0), verts=24):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth, location=loc, rotation=rot)
    ob = bpy.context.object
    ob.name = name
    ob.data.materials.append(mat)
    return ob


def curve_object(name, mat, bevel):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = bevel
    cu.bevel_resolution = 1
    cu.fill_mode = "FULL"
    ob = bpy.data.objects.new(name, cu)
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(mat)
    return ob


def set_polylines(ob, lines):
    cu = ob.data
    cu.splines.clear()
    for pts in lines:
        sp = cu.splines.new("POLY")
        sp.points.add(len(pts) - 1)
        for p, q in zip(sp.points, pts):
            p.co = (float(q[0]), float(q[1]), float(q[2]), 1.0)


def strip(ob, a, b, height, thick=0.008):
    """Place a unit cube as a thin vertical strip from plan point a to b (a tape seen edge-on from above, broad face vertical)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy)
    if L < 1e-3:
        ob.hide_render = True
        return
    ob.hide_render = False
    ob.location = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, a[2])
    ob.rotation_euler = (0.0, 0.0, math.atan2(-dx, dy))
    ob.scale = (thick, L, height)


def rock_material(name, colour):
    mt = material(name, colour, rough=0.95)
    nt = mt.node_tree
    b = nt.nodes.get("Principled BSDF")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.08
    noise.inputs["Detail"].default_value = 6
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (colour[0] * 0.6, colour[1] * 0.6, colour[2] * 0.6, 1)
    ramp.color_ramp.elements[1].color = (min(1, colour[0] * 1.35), min(1, colour[1] * 1.35), min(1, colour[2] * 1.35), 1)
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    return mt


def glass_material(name):
    """Cab glass that shows the cab's inside (mostly see-through, a light tint and a little reflection)."""
    mt = material(name, (0.30, 0.36, 0.40), rough=0.05)
    mt.node_tree.nodes.get("Principled BSDF").inputs["Alpha"].default_value = 0.28
    return mt


class Site:
    """The highway, the ramp and its walls, posts, tape exits and run-out, the mountainside, pines and far peaks."""

    def __init__(self):
        asphalt = material("Asphalt", (0.07, 0.07, 0.075), rough=0.85)
        base.asphalt_grain(asphalt)
        ramp_mt = material("Ramp asphalt", (0.10, 0.10, 0.105), rough=0.85)
        base.asphalt_grain(ramp_mt)
        paint = material("Line paint", (0.86, 0.86, 0.80), rough=0.6)
        yellow = material("Yellow line", (0.85, 0.60, 0.05), rough=0.6)
        gravel = rock_material("Gravel", (0.36, 0.30, 0.22))
        self.concrete = material("Wall concrete", (0.50, 0.49, 0.46), rough=0.8)
        self.cut_face = material("Cut concrete", (0.44, 0.43, 0.40), rough=0.9)
        steel = material("Galvanised steel", (0.55, 0.56, 0.57), metal=0.85, rough=0.38)
        dark = material("Slot dark", (0.02, 0.02, 0.02), rough=0.8)
        rock = rock_material("Mountainside", (0.13, 0.14, 0.09))
        forest = material("Forest floor", (0.13, 0.15, 0.08), rough=1.0)
        y0, y1 = -420.0, 420.0
        L = y1 - y0
        cube("Highway", ((ROAD[0] + ROAD[1]) / 2, 0.0, -0.05), (ROAD[1] - ROAD[0], L, 0.1), asphalt)
        cube("Ramp entrance", ((ROAD[1] + WX + 0.9) / 2, (y0 + WALL_Y[0]) / 2, -0.051), (WX + 0.9 - ROAD[1], WALL_Y[0] - y0, 0.1), asphalt)
        cube("Ramp", (0.0, (WALL_Y[0] + WALL_Y[1]) / 2, -0.049), (2 * WX, WALL_Y[1] - WALL_Y[0], 0.1), ramp_mt)
        cube("Run-out gravel", (0.0, WALL_Y[1] + 30.0, -0.02), (2 * WX + 1.8, 60.0, 0.1), gravel)
        cube("Gore", ((ROAD[1] - WX - 0.9) / 2, (WALL_Y[0] + y1) / 2, -0.04), (abs(ROAD[1]) - WX - 0.9, y1 - WALL_Y[0], 0.1), gravel)
        cube("Shelf right", (WX + 0.9 + 2.0, 0.0, -0.06), (4.0, L, 0.1), forest)
        for x in (-17.6, -17.4):
            cube(f"Centre line {x}", (x, 0.0, 0.003), (0.12, L, 0.004), yellow)
        cube("Edge line left", (ROAD[0] + 0.25, 0.0, 0.003), (0.15, L, 0.004), paint)
        cube("Edge line right", (ROAD[1] - 0.15, 0.0, 0.003), (0.15, L, 0.004), paint)
        y = y0
        while y < y1:
            for x in (-21.4, -13.8):
                cube(f"Dash {x} {y:.0f}", (x, y + 1.5, 0.003), (0.15, 3.0, 0.004), paint)
            y += 12.0
        # guardrail along the valley edge
        rail = material("Guardrail", (0.62, 0.63, 0.64), metal=0.8, rough=0.35)
        cube("Guardrail", (ROAD[0] - 0.6, 0.0, 0.62), (0.08, L, 0.32), rail)
        for yy in np.arange(y0, y1, 4.0):
            cube(f"Rail post {yy:.0f}", (ROAD[0] - 0.68, yy, 0.38), (0.12, 0.12, 0.76), dark)
        # walls: plain stretches, and at every net a pocket for the absorber (hollow only where the absorber is built in detail)
        self.inner_slabs, self.top_slabs, self.cut_faces = {}, {}, []
        for s in (-1, 1):
            xs = s * (WX + 0.45)
            edges = []
            for i, yn in enumerate(m.NET_Y):
                edges.append((yn + BOX_DY[0] - 0.05, yn + 0.15, i))
            ya = WALL_Y[0]
            for a, b, i in edges:
                cube(f"Wall {s} {ya:.0f}", (xs, (ya + a) / 2, m.WALL_H / 2), (0.9, a - ya, m.WALL_H), self.concrete)
                if s == 1 and i in DETAIL:
                    self.pocket(i, a, b)
                else:
                    cube(f"Wall {s} pocket {i}", (xs, (a + b) / 2, m.WALL_H / 2), (0.9, b - a, m.WALL_H), self.concrete)
                ya = b
            cube(f"Wall {s} end", (xs, (ya + WALL_Y[1]) / 2, m.WALL_H / 2), (0.9, WALL_Y[1] - ya, m.WALL_H), self.concrete)
            chev = self.chevron_panel(f"Wall end {s}")
            chev.location = (xs, WALL_Y[0] - 0.03, 0.8)
        # tape exits (dark slots), posts and arms at every net, both walls
        self.slots = {}
        for i, yn in enumerate(m.NET_Y):
            for s in (-1, 1):
                for zt in m.TAPE_Z:
                    ob = cube(f"Slot {i} {s} {zt}", (s * (WX - 0.004), yn, zt), (0.012, 0.20, 0.14), dark)
                    if s == 1 and i in DETAIL:
                        self.slots.setdefault(i, []).append(ob)
                cube(f"Post {i} {s}", (s * (WX + 0.45), yn, m.WALL_H + 0.95), (0.2, 0.2, 1.9), steel)
                cube(f"Arm {i} {s}", (s * (WX + 0.22), yn, m.WALL_H + 1.75), (0.5, 0.12, 0.12), steel)
        # the mountainside on the right, the drop to the valley on the left
        self.slope("Mountainside", WX + 4.9, 150.0, 0.62, rock)
        self.slope("Valley side", ROAD[0] - 1.5, -220.0, -0.55, forest)
        bpy.ops.mesh.primitive_plane_add(size=1.0, location=(-900.0, 0.0, -125.0))
        ob = bpy.context.object
        ob.scale = (1400.0, 4000.0, 1.0)
        ob.data.materials.append(forest)
        peaks = rock_material("Far peaks", (0.30, 0.31, 0.34))
        snow = material("Snow", (0.92, 0.93, 0.96), rough=0.6)
        rng = random.Random(34)
        for k in range(18):
            side = 1 if k % 2 else -1
            x = rng.uniform(-1500, 1400)
            y = side * rng.uniform(900, 1900)
            h = rng.uniform(320, 640)
            r = h * rng.uniform(1.1, 1.6)
            bpy.ops.mesh.primitive_cone_add(vertices=9, radius1=r, radius2=0.0, depth=h, location=(x, y, -100 + h / 2))
            bpy.context.object.data.materials.append(peaks)
            bpy.ops.mesh.primitive_cone_add(vertices=9, radius1=r * 0.28, radius2=0.0, depth=h * 0.28, location=(x, y, -100 + h * 0.86 + 0.5))
            bpy.context.object.data.materials.append(snow)
        self.pines(rng)

    def chevron_panel(self, name):
        mt = bpy.data.materials.get("End chevrons")
        if mt is None:
            mt = bpy.data.materials.new("End chevrons")
            mt.use_nodes = True
            nt = mt.node_tree
            bsdf = nt.nodes.get("Principled BSDF")
            tc = nt.nodes.new("ShaderNodeTexCoord")
            sep = nt.nodes.new("ShaderNodeSeparateXYZ")
            nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
            add = nt.nodes.new("ShaderNodeMath")
            add.operation = "ADD"
            nt.links.new(sep.outputs["X"], add.inputs[0])
            nt.links.new(sep.outputs["Z"], add.inputs[1])
            mul = nt.nodes.new("ShaderNodeMath")
            mul.operation = "MULTIPLY"
            mul.inputs[1].default_value = 3.0
            nt.links.new(add.outputs[0], mul.inputs[0])
            fr = nt.nodes.new("ShaderNodeMath")
            fr.operation = "FRACT"
            nt.links.new(mul.outputs[0], fr.inputs[0])
            ramp = nt.nodes.new("ShaderNodeValToRGB")
            ramp.color_ramp.interpolation = "CONSTANT"
            ramp.color_ramp.elements[0].color = (0.02, 0.02, 0.02, 1)
            ramp.color_ramp.elements[1].position = 0.5
            ramp.color_ramp.elements[1].color = (0.95, 0.66, 0.03, 1)
            nt.links.new(fr.outputs[0], ramp.inputs["Fac"])
            nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
        return cube(name, (0, 0, 0), (0.92, 0.04, 1.6), mt)

    def pocket(self, i, a, b):
        """The wall around net i's right-hand absorber: floor, outer side, ends, a lid slab and the inner face (with the tape exits),
        so the cut-away can remove the inner face and the open box its lid."""
        yn = m.NET_Y[i]
        c = self.concrete
        x0, x1 = WX, WX + 0.9
        cube(f"Pocket {i} floor", ((x0 + x1) / 2, (a + b) / 2, BOX_Z[0] / 2), (0.9, b - a, BOX_Z[0]), c)
        cube(f"Pocket {i} outer", (BOX_X[1] + (x1 - BOX_X[1]) / 2, (a + b) / 2, m.WALL_H / 2), (x1 - BOX_X[1], b - a, m.WALL_H), c)
        cube(f"Pocket {i} end a", ((x0 + x1) / 2, a + 0.025, m.WALL_H / 2), (0.9, 0.05, m.WALL_H), c)
        cube(f"Pocket {i} end b", ((x0 + x1) / 2, (yn + BOX_DY[1] + b) / 2, m.WALL_H / 2), (0.9, b - yn - BOX_DY[1], m.WALL_H), c)
        self.top_slabs[i] = cube(f"Pocket {i} top", ((x0 + x1) / 2, (a + b) / 2, (BOX_Z[1] + m.WALL_H) / 2), (0.9, b - a, m.WALL_H - BOX_Z[1]), c)
        self.inner_slabs[i] = cube(f"Pocket {i} inner", ((x0 + BOX_X[0]) / 2, (a + b) / 2, (BOX_Z[0] + BOX_Z[1]) / 2),
                                   (BOX_X[0] - x0, b - a, BOX_Z[1] - BOX_Z[0]), c)
        # the cut faces seen when the inner face is removed: darker concrete at the pocket's ends
        for k, yy in enumerate((a + 0.052, b - 0.002)):
            f = cube(f"Pocket {i} cut {k}", (WX + 0.04, yy, m.WALL_H / 2), (0.08, 0.004, m.WALL_H), self.cut_face)
            f.hide_render = True
            self.cut_faces.append((i, f))

    def slope(self, name, x_edge, width, grade, mt):
        """A big sloping plane from x_edge outward (width along x, negative = to -x), rising (grade > 0) or falling."""
        x1 = x_edge + width
        z1 = abs(width) * grade
        verts = [(x_edge, -900.0, 0.0), (x_edge, 900.0, 0.0), (x1, 900.0, z1), (x1, -900.0, z1)]
        ob = mesh_object(name, verts, [(0, 1, 2, 3)] if width > 0 else [(0, 3, 2, 1)], mt)
        sub = ob.modifiers.new("Sub", "SUBSURF")
        sub.subdivision_type = "SIMPLE"
        sub.levels = sub.render_levels = 5
        disp = ob.modifiers.new("Lumps", "DISPLACE")
        tex = bpy.data.textures.new(f"{name} lumps", "CLOUDS")
        tex.noise_scale = 40.0
        disp.texture = tex
        disp.strength = 9.0
        disp.mid_level = 0.5
        return ob

    def pines(self, rng):
        needles = [material("Pine a", (0.05, 0.11, 0.05), rough=0.9), material("Pine b", (0.07, 0.13, 0.06), rough=0.9)]
        bark = material("Pine bark", (0.10, 0.07, 0.05), rough=0.9)
        protos = []
        for k, mt in enumerate(needles):
            bpy.ops.mesh.primitive_cone_add(vertices=10, radius1=1.0, radius2=0.0, depth=1.0, location=(0, 0, -200))
            ob = bpy.context.object
            ob.data.materials.append(mt)
            protos.append(ob)
        trunk = cyl("Trunk proto", 0.08, 1.0, (0, 0, -200), bark, verts=6)
        placed = 0
        while placed < 170:
            side = rng.choice((-1, 1))
            if side > 0:
                x = rng.uniform(WX + 9.0, 120.0)
                z = (x - WX - 4.9) * 0.62
            else:
                x = rng.uniform(-150.0, ROAD[0] - 9.0)
                z = (ROAD[0] - 1.5 - x) * -0.55
            y = rng.uniform(-400.0, 400.0)
            h = rng.uniform(7.0, 15.0)
            p = protos[placed % 2].copy()
            p.data = protos[placed % 2].data
            bpy.context.collection.objects.link(p)
            p.location = (x, y, z + h * 0.62)
            p.scale = (h * 0.26, h * 0.26, h * 0.85)
            t = trunk.copy()
            t.data = trunk.data
            bpy.context.collection.objects.link(t)
            t.location = (x, y, z + h * 0.12)
            t.scale = (1.6, 1.6, h * 0.3)
            placed += 1
        for ob in protos + [trunk]:
            ob.location = (0, 0, -300)

    def set(self, cut, opened):
        for i, ob in self.inner_slabs.items():
            ob.hide_render = cut and DETAIL[i] == "cut"
        for i, ob in self.top_slabs.items():
            ob.hide_render = opened and DETAIL[i] == "open"
        for i, f in self.cut_faces:
            f.hide_render = not (cut and DETAIL[i] == "cut")
        for i, obs in self.slots.items():
            for ob in obs:
                ob.hide_render = cut and DETAIL[i] == "cut"


class Absorber:
    """Net i's right-hand absorber in detail: the steel box (its inner plate and lid removable), two coils of tape (low and high), a
    row of offset pins and the tape's path through them to the exit, with dark marks along the tape that move as it pays out."""

    def __init__(self, i):
        self.i, self.yn = i, m.NET_Y[i]
        yn = self.yn
        steel = material(f"Box steel {i}", (0.16, 0.17, 0.18), metal=0.6, rough=0.5)
        self.tape_mt = material(f"Tape steel {i}", (0.80, 0.81, 0.82), metal=0.35, rough=0.32)     # not mirror-like: inside a dark box it must read bright
        coil_mt = material(f"Coil {i}", (0.70, 0.71, 0.72), metal=0.4, rough=0.35)
        hub_mt = material(f"Hub {i}", (0.06, 0.06, 0.07), rough=0.6)
        pin_mt = material(f"Pins {i}", (0.20, 0.21, 0.23), metal=0.8, rough=0.3)
        mark = material(f"Tape marks {i}", (0.03, 0.03, 0.03), rough=0.6)
        ya, yb = yn + BOX_DY[0], yn + BOX_DY[1]
        xa, xb = BOX_X
        za, zb = BOX_Z
        self.plates = [cube(f"Box {i} floor", ((xa + xb) / 2, (ya + yb) / 2, za + 0.01), (xb - xa, yb - ya, 0.02), steel),
                       cube(f"Box {i} back", (xb - 0.01, (ya + yb) / 2, (za + zb) / 2), (0.02, yb - ya, zb - za), steel),
                       cube(f"Box {i} end a", ((xa + xb) / 2, ya + 0.01, (za + zb) / 2), (xb - xa, 0.02, zb - za), steel),
                       cube(f"Box {i} end b", ((xa + xb) / 2, yb - 0.01, (za + zb) / 2), (xb - xa, 0.02, zb - za), steel)]
        self.lid = cube(f"Box {i} lid", ((xa + xb) / 2, (ya + yb) / 2, zb - 0.01), (xb - xa, yb - ya, 0.02), steel)
        self.inner = cube(f"Box {i} inner", (xa + 0.01, (ya + yb) / 2, (za + zb) / 2), (0.02, yb - ya, zb - za), steel)
        self.pins = []
        for zt in m.TAPE_Z:
            self.pins += [cyl(f"Pin {i} {zt} {j}", PIN_R, 0.26, (PIN_X + PIN_A_OFF(j), yn + dy, zt), pin_mt, verts=14) for j, dy in enumerate(PIN_DY)]
            for dz in (-0.135, 0.135):
                cube(f"Bender plate {i} {zt} {dz}", (PIN_X, yn + (PIN_DY[0] + PIN_DY[-1]) / 2, zt + dz), (0.34, PIN_DY[-1] - PIN_DY[0] + 0.26, 0.012), pin_mt)
        self.coils, self.hubs, self.marks, self.ribbons, self.ticks = [], [], [], [], []
        for k, zt in enumerate(m.TAPE_Z):
            self.coils.append(cyl(f"Coil {i} {k}", 1.0, 0.09, (COIL_X, yn + COIL_DY, zt), coil_mt, verts=40))
            self.hubs.append(cyl(f"Hub {i} {k}", R_HUB, 0.11, (COIL_X, yn + COIL_DY, zt), hub_mt, verts=20))
            self.marks.append([cube(f"Coil mark {i} {k} {j}", (0, 0, -50), (0.012, 1.0, 0.012), mark) for j in range(2)])
            n = len(self.path(0.0, zt))
            verts = [(0, 0, 0)] * (2 * n)
            faces = [(2 * a, 2 * a + 1, 2 * a + 3, 2 * a + 2) for a in range(n - 1)]
            self.ribbons.append(mesh_object(f"Tape path {i} {k}", verts, faces, self.tape_mt))
            self.ticks.append([cube(f"Tick {i} {k} {j}", (0, 0, -50), (0.010, 0.03, 0.122), mark) for j in range(16)])

    def coil_r(self, p):
        return math.sqrt(R_HUB ** 2 + max(0.0, m.L_TAPE - p) * TAPE_TH / math.pi)

    def path(self, p, zt):
        """Plan path of the tape from the coil, through the pins, to the exit in the wall's face (x = WALL_X at the net's station)."""
        yn, r = self.yn, self.coil_r(p)
        pts = [(COIL_X - r, yn + COIL_DY), (PIN_X, yn + PIN_DY[0] - 0.16)]
        for a in range(len(PIN_DY) - 1):
            y0, y1 = yn + PIN_DY[a], yn + PIN_DY[a + 1]
            for q in range(6):
                u = q / 6
                pts.append((PIN_X + PIN_A_SIGN(a) * PIN_A * math.cos(math.pi * u), y0 + (y1 - y0) * u))
        pts.append((PIN_X + PIN_A_SIGN(len(PIN_DY) - 1) * PIN_A, yn + PIN_DY[-1]))
        pts += [(PIN_X, yn + PIN_DY[-1] + 0.16), (WX + 0.22, yn - 0.25), (WX + 0.06, yn - 0.04), (WX - 0.01, yn)]
        return [(x, y, zt) for x, y in pts]

    def set(self, payouts, cut, opened, replace=-1):
        p = max(payouts) if payouts else 0.0
        for k, zt in enumerate(m.TAPE_Z):
            r = self.coil_r(p)
            co = self.coils[k]
            co.scale = (r, r, 1.0)
            gone = k == replace
            co.hide_render = gone
            self.hubs[k].hide_render = gone
            ang = p / max(r, 0.12)
            for j, mk in enumerate(self.marks[k]):
                a = ang + j * math.pi
                mk.location = (COIL_X + 0.5 * r * math.cos(a), self.yn + COIL_DY + 0.5 * r * math.sin(a), zt + 0.048)
                mk.rotation_euler = (0.0, 0.0, a + math.pi / 2)
                mk.scale = (1.0, r * 0.9, 1.0)
                mk.hide_render = gone
            pts = self.path(p, zt)
            verts = []
            for x, y, z in pts:
                verts += [(x, y, z - 0.06), (x, y, z + 0.06)]
            rib = self.ribbons[k]
            rib.data.vertices.foreach_set("co", np.array(verts, dtype=np.float32).ravel())
            rib.data.update()
            rib.hide_render = gone
            seg = [math.dist(a[:2], b[:2]) for a, b in zip(pts[:-1], pts[1:])]
            total = sum(seg)
            for j, tk in enumerate(self.ticks[k]):
                s = (j * TICK + p) % (len(self.ticks[k]) * TICK)
                if s > total or gone:
                    tk.hide_render = True
                    continue
                acc, q = 0.0, 0
                while q < len(seg) - 1 and acc + seg[q] < s:
                    acc += seg[q]
                    q += 1
                f = (s - acc) / max(seg[q], 1e-9)
                a, b = pts[q], pts[q + 1]
                tk.hide_render = False
                tk.location = (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, zt)
                tk.rotation_euler = (0.0, 0.0, math.atan2(-(b[0] - a[0]), b[1] - a[1]))
        self.inner.hide_render = cut
        self.lid.hide_render = opened


def PIN_A_SIGN(j):
    return 1 if j % 2 == 0 else -1


def PIN_A_OFF(j):
    """Pin j sits just outside the tape's bend: alternately left and right of the tape's centre line."""
    return PIN_A_SIGN(j) * (PIN_A + PIN_R + 0.004)


class Nets:
    """The eight nets (curves with round cables), their side edges, the four tapes outside the wall per net, and the links that hold
    each hanging net's top corners to the arms on the posts."""

    def __init__(self):
        self.mt = material("Net stainless", (0.78, 0.79, 0.80), metal=0.9, rough=0.26)
        tape_mt = material("Tape outside", (0.70, 0.71, 0.72), metal=0.9, rough=0.3)
        self.curves = [curve_object(f"Net {i}", self.mt, 0.011) for i in range(m.N_NETS)]
        self.tapes = [[cube(f"Tape {i} {s} {k}", (0, 0, -50), (1, 1, 1), tape_mt) for s in (-1, 1) for k in range(2)] for i in range(m.N_NETS)]
        self.links = [[cube(f"Link {i} {s}", (s * (WX - 0.02), yn, (m.NET_Z[1] + m.WALL_H + 1.75) / 2), (0.03, 0.03, m.WALL_H + 1.75 - m.NET_Z[1]),
                            self.mt) for s in (-1, 1)] for i, yn in enumerate(m.NET_Y)]

    @staticmethod
    def front(yf, z):
        """The truck's front profile at height z as (y, z): bumper, the recessed grille, then lying back over the hood."""
        if z < 0.85:
            return yf, z
        if z < 2.1:
            return yf - 0.22, z
        k = z - 2.1
        return yf - 0.22 - 1.3 * k, 2.1 + 0.25 * k

    def point(self, u, z, d, yn, rank, yf):
        if d <= 0.0:
            belly = 0.06 * (1.0 - (u / WX) ** 2) * math.sin(math.pi * (z - m.NET_Z[0]) / (m.NET_Z[1] - m.NET_Z[0]))
            return (u, yn + belly, z)
        fy, fz = self.front(yf + 0.025 * rank, z)
        if abs(u) <= m.HALF_T:
            return (u, fy, fz)
        s = 1 if u > 0 else -1
        w = (abs(u) - m.HALF_T) / m.S_SIDE
        ex, ey = m.side_edge(d, yn, s)
        cx, cy = s * (m.HALF_T + 0.03), fy - 0.05
        return (cx + w * (ex - cx), cy + w * (ey - cy), fz + w * (z - fz))

    def set(self, st, hidden_truck):
        d_all = st["d"] if not hidden_truck else [-1.0] * m.N_NETS
        engaged = [i for i, d in enumerate(d_all) if d > 0.0]
        yf = st["front_y"]
        us = np.linspace(-WX + 0.05, WX - 0.05, NU)
        zs = np.linspace(m.NET_Z[0], m.NET_Z[1], NZ)
        uh = np.linspace(-WX + 0.05, WX - 0.05, 4 * NU)
        info = []
        for i, yn in enumerate(m.NET_Y):
            d = d_all[i]
            rank = engaged.index(i) if i in engaged else 0
            lines = [[self.point(u, z, d, yn, rank, yf) for u in uh] for z in zs]
            lines += [[self.point(u, z, d, yn, rank, yf) for z in np.linspace(m.NET_Z[0], m.NET_Z[1], 3 * NZ)] for u in us]
            set_polylines(self.curves[i], lines)
            for s_i, s in enumerate((-1, 1)):
                ex, ey = m.side_edge(d, yn, s)
                for k, zt in enumerate(m.TAPE_Z):
                    strip(self.tapes[i][2 * s_i + k], (s * WX, yn, zt), (ex, ey, zt), 0.08)
                self.links[i][s_i].hide_render = d > 0.0
            info.append(round(m.payout(d), 4))
        return info


class Rig:
    """Tractor (conventional, long hood) with a driver, and two trailers (a box van and a tanker). Reference: the front bumper's face
    at local y = 0, the truck along -y, the ground at z = 0."""

    def __init__(self):
        self.root = bpy.data.objects.new("Tractor root", None)
        bpy.context.collection.objects.link(self.root)
        self.paint = material("Tractor paint", (0.55, 0.035, 0.03), metal=0.3, rough=0.32)
        chrome = material("Chrome", (0.85, 0.86, 0.88), metal=1.0, rough=0.12)
        dark = material("Rig dark", (0.035, 0.035, 0.04), rough=0.6)
        grille = material("Grille mesh", (0.10, 0.10, 0.11), metal=0.7, rough=0.4)
        glass = glass_material("Cab glass")
        tyre = material("Rig tyre", (0.03, 0.03, 0.035), rough=0.85)
        hub = material("Rig hub", (0.70, 0.70, 0.68), metal=0.9, rough=0.25)
        lamp = material("Head lamps", (0.95, 0.93, 0.85), rough=0.1, emission=0.6)
        P = self.paint
        parts = [cube("Bumper", (0.0, -0.13, 0.65), (2.5, 0.26, 0.40), chrome),
                 cube("Grille", (0.0, -0.30, 1.48), (1.10, 0.12, 1.25), grille),
                 cube("Grille frame top", (0.0, -0.30, 2.13), (1.18, 0.14, 0.08), chrome),
                 cube("Grille frame L", (-0.58, -0.30, 1.48), (0.06, 0.14, 1.3), chrome),
                 cube("Grille frame R", (0.58, -0.30, 1.48), (0.06, 0.14, 1.3), chrome),
                 cube("Hood", (0.0, -1.50, 1.62), (1.30, 2.30, 1.05), P),
                 cube("Hood top", (0.0, -1.50, 2.13), (1.20, 2.30, 0.06), P),
                 cube("Fender L", (-0.98, -1.30, 1.02), (0.58, 1.60, 0.30), P),
                 cube("Fender R", (0.98, -1.30, 1.02), (0.58, 1.60, 0.30), P),
                 cube("Lamp L", (-0.95, -0.52, 1.05), (0.34, 0.06, 0.16), lamp),
                 cube("Lamp R", (0.95, -0.52, 1.05), (0.34, 0.06, 0.16), lamp),
                 # the cab as panels around a hollow inside, so the driver shows through the glass
                 cube("Cab front low", (0.0, -2.65, 1.665), (2.40, 0.10, 1.13), P),
                 cube("Cab pillar L", (-1.125, -2.65, 2.62), (0.15, 0.10, 0.78), P),
                 cube("Cab pillar R", (1.125, -2.65, 2.62), (0.15, 0.10, 0.78), P),
                 cube("Cab roof", (0.0, -3.70, 3.06), (2.40, 2.20, 0.10), P),
                 cube("Cab back", (0.0, -4.75, 2.10), (2.40, 0.10, 1.95), P),
                 cube("Cab floor", (0.0, -3.70, 1.12), (2.40, 2.20, 0.12), dark),
                 cube("Cab side L low", (-1.175, -3.70, 1.645), (0.05, 2.20, 1.09), P),
                 cube("Cab side R low", (1.175, -3.70, 1.645), (0.05, 2.20, 1.09), P),
                 cube("Cab side L high", (-1.175, -3.70, 2.96), (0.05, 2.20, 0.10), P),
                 cube("Cab side R high", (1.175, -3.70, 2.96), (0.05, 2.20, 0.10), P),
                 cube("Cab side L front", (-1.175, -2.66, 2.55), (0.05, 0.12, 0.72), P),
                 cube("Cab side R front", (1.175, -2.66, 2.55), (0.05, 0.12, 0.72), P),
                 cube("Cab side L back", (-1.175, -4.29, 2.55), (0.05, 1.02, 0.72), P),
                 cube("Cab side R back", (1.175, -4.29, 2.55), (0.05, 1.02, 0.72), P),
                 cube("Dash", (0.0, -2.85, 2.05), (2.30, 0.35, 0.30), dark),
                 cube("Sleeper", (0.0, -5.25, 2.30), (2.40, 0.90, 2.40), P),
                 cube("Windshield", (0.0, -2.62, 2.62), (2.05, 0.03, 0.78), glass),
                 cube("Side window L", (-1.205, -3.25, 2.55), (0.03, 1.05, 0.72), glass),
                 cube("Side window R", (1.205, -3.25, 2.55), (0.03, 1.05, 0.72), glass),
                 cube("Frame rails", (0.0, -5.0, 0.88), (1.0, 9.6, 0.26), dark),
                 cube("Fifth wheel", (0.0, -6.75, 1.12), (1.3, 1.1, 0.12), dark),
                 cyl("Tank L", 0.32, 1.2, (-1.05, -3.7, 0.80), chrome, rot=(math.pi / 2, 0, 0)),
                 cyl("Tank R", 0.32, 1.2, (1.05, -3.7, 0.80), chrome, rot=(math.pi / 2, 0, 0)),
                 cyl("Stack L", 0.09, 2.2, (-1.12, -4.75, 3.25), chrome),
                 cyl("Stack R", 0.09, 2.2, (1.12, -4.75, 3.25), chrome)]
        for wy in (-1.30, -6.10, -7.40):
            for sx in (-1, 1):
                parts.append(cyl(f"Tyre {wy} {sx}", 0.52, 0.34 if wy > -2 else 0.60, (sx * 0.98, wy, 0.52), tyre, rot=(0, math.pi / 2, 0), verts=28))
                parts.append(cyl(f"Hub {wy} {sx}", 0.28, (0.36 if wy > -2 else 0.62), (sx * 0.98, wy, 0.52), hub, rot=(0, math.pi / 2, 0), verts=16))
        # the driver: seated on the left, hands on the wheel
        shirt = material("Driver shirt", (0.10, 0.18, 0.40), rough=0.8)
        skin = material("Driver skin", (0.55, 0.36, 0.25), rough=0.7)
        cap = material("Driver cap", (0.12, 0.12, 0.12), rough=0.7)
        parts += [cube("Driver torso", (-0.55, -3.75, 2.30), (0.46, 0.28, 0.66), shirt),
                  cube("Driver arm L", (-0.78, -3.40, 2.38), (0.11, 0.55, 0.12), shirt),
                  cube("Driver arm R", (-0.32, -3.40, 2.38), (0.11, 0.55, 0.12), shirt),
                  cube("Seat", (-0.55, -3.95, 1.85), (0.55, 0.55, 0.30), dark),
                  cube("Seat back", (-0.55, -4.18, 2.35), (0.55, 0.12, 0.85), dark)]
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=10, radius=0.13, location=(-0.55, -3.72, 2.80))
        head = bpy.context.object
        head.data.materials.append(skin)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.14, location=(-0.55, -3.72, 2.88))
        hat = bpy.context.object
        hat.scale = (1.0, 1.05, 0.6)
        hat.data.materials.append(cap)
        bpy.ops.mesh.primitive_torus_add(major_radius=0.22, minor_radius=0.025, location=(-0.55, -3.10, 2.30), rotation=(math.radians(60), 0, 0))
        wheel = bpy.context.object
        wheel.data.materials.append(dark)
        parts += [head, hat, wheel]
        bpy.ops.object.light_add(type="POINT", location=(-0.2, -3.4, 2.9))
        self.cab_light = bpy.context.object
        self.cab_light.data.energy = 0.0
        self.cab_light.data.color = (1.0, 0.9, 0.8)
        self.cab_light.data.shadow_soft_size = 0.3
        parts.append(self.cab_light)
        for ob in parts:
            ob.parent = self.root
        self.trailers = {"truck": self.van(), "rating": self.tanker()}

    def trailer_root(self, name):
        r = bpy.data.objects.new(name, None)
        bpy.context.collection.objects.link(r)
        return r

    def van(self):
        root = self.trailer_root("Van root")
        white = material("Van white", (0.86, 0.86, 0.84), rough=0.45)
        dark = material("Van dark", (0.04, 0.04, 0.045), rough=0.6)
        tyre = bpy.data.materials["Rig tyre"]
        hub = bpy.data.materials["Rig hub"]
        parts = [cube("Van box", (0.0, -8.075, 2.70), (2.6, 16.15, 2.85), white),
                 cube("Van floor", (0.0, -8.075, 1.22), (2.5, 16.15, 0.14), dark),
                 cube("Van skirt L", (-1.24, -7.4, 0.88), (0.03, 7.0, 0.55), white),
                 cube("Van skirt R", (1.24, -7.4, 0.88), (0.03, 7.0, 0.55), white),
                 cube("Van gear", (0.0, -2.6, 0.70), (2.0, 0.2, 1.0), dark)]
        for wy in (-14.3, -15.6):
            for sx in (-1, 1):
                parts.append(cyl(f"Van tyre {wy} {sx}", 0.52, 0.60, (sx * 0.98, wy, 0.52), tyre, rot=(0, math.pi / 2, 0), verts=28))
                parts.append(cyl(f"Van hub {wy} {sx}", 0.28, 0.62, (sx * 0.98, wy, 0.52), hub, rot=(0, math.pi / 2, 0), verts=16))
        for ob in parts:
            ob.parent = root
        return root

    def tanker(self):
        root = self.trailer_root("Tanker root")
        steel = material("Tank steel", (0.80, 0.81, 0.82), metal=0.95, rough=0.18)
        dark = material("Tank dark", (0.04, 0.04, 0.045), rough=0.6)
        tyre = bpy.data.materials["Rig tyre"]
        hub = bpy.data.materials["Rig hub"]
        parts = [cyl("Tank", 1.05, 13.2, (0.0, -7.4, 2.25), steel, rot=(math.pi / 2, 0, 0), verts=40),
                 cube("Tank frame", (0.0, -7.4, 1.12), (1.2, 13.4, 0.2), dark)]
        for k, yy in enumerate((-0.8, -14.0)):
            bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=12, radius=1.05, location=(0.0, yy, 2.25))
            cap = bpy.context.object
            cap.scale = (1.0, 0.35, 1.0)
            cap.data.materials.append(steel)
            parts.append(cap)
        for wy in (-12.6, -13.9):
            for sx in (-1, 1):
                parts.append(cyl(f"Tank tyre {wy} {sx}", 0.52, 0.60, (sx * 0.98, wy, 0.52), tyre, rot=(0, math.pi / 2, 0), verts=28))
                parts.append(cyl(f"Tank hub {wy} {sx}", 0.28, 0.62, (sx * 0.98, wy, 0.52), hub, rot=(0, math.pi / 2, 0), verts=16))
        for ob in parts:
            ob.parent = root
        return root

    def set(self, variant, front_y, driver):
        if variant not in self.trailers:
            self.root.location = (0, 0, -60)
            for r in self.trailers.values():
                r.location = (0, 0, -60)
            self.cab_light.data.energy = 0.0
            return
        colour = (0.55, 0.035, 0.03) if variant == "truck" else (0.05, 0.16, 0.42)
        self.paint.node_tree.nodes.get("Principled BSDF").inputs["Base Color"].default_value = (*colour, 1.0)
        x = m.path_x(front_y - 3.0)
        yaw = m.heading(front_y - 3.0)
        self.root.location = (x, front_y, 0.0)
        self.root.rotation_euler = (0.0, 0.0, -yaw)
        king = Vector((x - 6.75 * math.sin(yaw), front_y - 6.75 * math.cos(yaw), 0.0))      # the fifth wheel
        tyaw = m.heading(king.y - 7.0)
        for k, r in self.trailers.items():
            if k == variant:
                r.location = (king.x + 0.8 * math.sin(tyaw), king.y + 0.8 * math.cos(tyaw), 0.0)
                r.rotation_euler = (0.0, 0.0, -tyaw)
            else:
                r.location = (0, 0, -60)
        self.cab_light.data.energy = 25.0 if driver else 0.0


def crew():
    """Two road workers at net 1's open absorber, one lowering a fresh coil of tape; the used tape lies along the ramp."""
    out = []
    for k, (x, y, rot, bend) in enumerate(((3.85, -0.9, math.pi / 2, 0.45), (3.75, -2.2, math.pi / 2, 0.15))):
        vest = material(f"Vest {k}", (0.98, 0.42, 0.02), rough=0.55)
        jeans = material(f"Trousers {k}", (0.08, 0.10, 0.16), rough=0.8)
        skin = material(f"Skin {k}", (0.55, 0.36, 0.25), rough=0.7)
        hat = material(f"Hard hat {k}", (0.95, 0.95, 0.93), rough=0.35)
        root = bpy.data.objects.new(f"Worker {k}", None)
        bpy.context.collection.objects.link(root)
        legs = [cube(f"Leg L {k}", (-0.1, 0.0, 0.43), (0.15, 0.17, 0.86), jeans), cube(f"Leg R {k}", (0.1, 0.0, 0.43), (0.15, 0.17, 0.86), jeans)]
        torso = bpy.data.objects.new(f"Torso pivot {k}", None)
        bpy.context.collection.objects.link(torso)
        torso.location = (0, 0, 0.88)
        torso.parent = root
        up = [cube(f"Torso {k}", (0, 0, 0.30), (0.42, 0.24, 0.60), vest),
              cube(f"Arm L {k}", (-0.27, -0.12, 0.28), (0.11, 0.42, 0.13), vest), cube(f"Arm R {k}", (0.27, -0.12, 0.28), (0.11, 0.42, 0.13), vest)]
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=10, radius=0.12, location=(0, 0, 0.74))
        head = bpy.context.object
        head.data.materials.append(skin)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.14, location=(0, 0, 0.80))
        cap = bpy.context.object
        cap.scale = (1.0, 1.1, 0.7)
        cap.data.materials.append(hat)
        for ob in up + [head, cap]:
            ob.parent = torso
        for ob in legs:
            ob.parent = root
        torso.rotation_euler = (bend, 0, 0)
        root.location = (x, y, 0.0)
        root.rotation_euler = (0, 0, rot)
        out.append(root)
    fresh_mt = material("Fresh coil", (0.80, 0.81, 0.83), metal=0.95, rough=0.18)
    coil = cyl("Fresh coil", 0.28, 0.09, (0, 0, -40), fresh_mt, verts=40)
    used_mt = material("Used tape", (0.48, 0.47, 0.45), metal=0.7, rough=0.5)
    n = 160
    pts = [(WX - 0.35 - 0.12 * math.sin(k * 0.9) * (k > 3), 0.4 + 0.25 * k, 0.01) for k in range(n)]
    verts = []
    for x, y, z in pts:
        verts += [(x - 0.04, y, z), (x + 0.04, y, z)]
    faces = [(2 * a, 2 * a + 1, 2 * a + 3, 2 * a + 2) for a in range(n - 1)]
    used = mesh_object("Used tape", verts, faces, used_mt)
    return out, coil, used


def main():
    args = arguments()
    args.out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_homefile(use_empty=True)
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
        scene.view_settings.white_balance_temperature = 7400.0
    scene.world = bpy.data.worlds.new("World")
    sun_to = cinematic.sun_vector((0.5, 0.86), 24.0)                    # low sun ahead-right: the truck's front lit, the walls' shadows out of the way
    cinematic.apply_sky(scene, sun_to, strength=0.26, dust=0.6)
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    sun.data.energy, sun.data.angle = 6.0, 0.02
    sun.data.color = (1.0, 0.76, 0.52)
    sun.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()
    bpy.ops.object.light_add(type="AREA", location=(2.2, m.NET_Y[1] - 1.2, 1.2))   # lights the cut-open absorber from the ramp side
    fill = bpy.context.object
    fill.data.size, fill.data.color, fill.data.energy = 1.6, (1.0, 0.9, 0.8), 0.0
    fill.rotation_euler = (0.0, math.radians(-90), 0.0)
    fill.visible_camera = False
    site = Site()
    nets = Nets()
    absorbers = {i: Absorber(i) for i in DETAIL}
    rig = Rig()
    workers, fresh, used = crew()
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam

    def render(sh, path):
        scene.render.resolution_x, scene.render.resolution_y = round(FRAME[0] * args.res_scale), round(FRAME[1] * args.res_scale)
        t, variant = sh["t"], sh["variant"]
        cut, opened, driver = bool(sh.get("cut")), bool(sh.get("open")), bool(sh.get("driver"))
        reset = variant == "reset"
        st = m.truck_state(t, rating=variant == "rating") if not reset else m.truck_state(-50.0)
        site.set(cut, opened)
        payout = nets.set(st, reset)
        for i, ab in absorbers.items():
            ab.set([payout[i]], cut and DETAIL[i] == "cut", opened and DETAIL[i] == "open", replace=1 if reset and DETAIL[i] == "open" else -1)
        fill.data.energy = 120.0 if cut else 0.0
        rig.set(variant, st["front_y"], driver)
        for w in workers:
            w.hide_render = not reset
            for ob in w.children_recursive:
                ob.hide_render = not reset
        used.hide_render = not reset
        if reset:                                   # slid over the wall's edge from the worker's hands, then lowered onto the high coil's seat
            u = min(1.0, sh["u"] * 1.3)
            a, b = min(1.0, u / 0.6), max(0.0, (u - 0.6) / 0.4)
            a, b = a * a * (3 - 2 * a), b * b * (3 - 2 * b)
            fresh.location = (4.25 + (COIL_X - 4.25) * a, -2.1 + 0.05 * a, 1.75 - 0.40 * b)
        else:
            fresh.location = (0, 0, -40)
        info = {"variant": variant, "t": round(t, 6), "front_y": round(st["front_y"], 4), "speed": round(st["speed"], 4),
                "decel_g": round(st["decel_g"], 4), "engaged": 0 if reset else st["engaged"], "payout": payout, "cut": cut, "open": opened,
                "driver": driver}
        c = sh["cam"]
        loc, tgt = Vector(c["loc"]), Vector(c["target"])
        if c["rel"] == "front":                     # a tracking shot: y measured from the truck's front
            loc.y += st["front_y"]
            tgt.y += st["front_y"]
        dd = cam.data
        dd.sensor_fit, dd.sensor_width, dd.lens, dd.clip_start = "HORIZONTAL", 36.0, c["lens"], 0.02
        dd.clip_end = 6000.0
        dd.dof.use_dof = True
        dd.dof.focus_distance = (tgt - loc).length
        dd.dof.aperture_fstop = c.get("fstop", 8.0)
        base.set_camera(cam, loc, tgt)
        bpy.context.view_layer.update()
        if reset:
            info["subject_box"] = hook_gate.project_box(scene, cam, _ident(), (3.4, -3.3, 0.0), (5.4, 0.3, 2.0))
        else:
            info["subject_box"] = hook_gate.project_box(scene, cam, rig.root.matrix_world, (-1.3, -7.4, 0.0), (1.3, 0.3, 4.0))
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        info["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        return info

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
        print("NET_FRAME " + json.dumps(info), flush=True)
    (args.out / f"net-frames-{frames[0]:05d}.json").write_text(json.dumps({"renderer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                                                          "frames": out}, indent=1))


def _ident():
    from mathutils import Matrix
    return Matrix.Identity(4)


if __name__ == "__main__":
    main()
