"""EP.32 truck-mounted attenuator: 100 % 3D renderer (Blender, Cycles CPU), house style of EP.13-EP.31 (golden hour, red car, depth of
field). A two-lane one-way highway with the right lane closed for road work: a cone taper, an orange protective truck with a flashing
arrow board parked in the closed lane, and ahead of it the crew (simple figures in orange vests and white hard hats) with a roller.
Behind the truck hangs its crash cushion: a mount frame on a hinge, three blocks of aluminum honeycomb (hexagonal tubes along the crush
direction) in a thin aluminum skin, and a rear face with yellow-and-black chevrons. The red CC0 sedan (or the white 5,000 lb test
pickup) drives into it: the blocks crush row by row from the back (each crushed part becomes a dark folded band, the skin pleats
like an accordion), torn skin, bumper plastic and lamp glass fly, and the braked truck is shoved a few feet, leaving tyre marks.
Cut-away shots remove the near skin; the reveal shot slides the blocks apart; the ghost shot keeps the uncrushed outline drawn.
Everything that moves comes from tma_motion. No text."""
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
from benchmarks.attenuator_truck import tma_motion as m  # noqa: E402
from benchmarks.attenuator_truck import tma_timeline as tl  # noqa: E402
from benchmarks.belt_limiter import render_belt_3d as rb  # noqa: E402
from benchmarks.crumple_zone import crumple_motion as cm  # noqa: E402
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402

material, cube = base.material, base.cube
FRAME = (1080, 1920)
PAINT = (1.75, 0.30, 0.24)
Y_RANGE = (-330.0, 160.0)
ROAD_HALF = m.LANE_W
SHOULDER = 3.0
X = m.LANE_R
CELL = 0.11                       # honeycomb cell (flat-to-flat), large enough to read at phone size
TAPER = (-150.0, -46.0)           # cones from the right edge across to the lane line
WORK_Y = (18.0, 70.0)


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


def glowable(name, colour, metal=0.0, rough=0.5, glow=(1.0, 0.55, 0.12)):
    mt = material(name, colour, metal=metal, rough=rough)
    b = mt.node_tree.nodes.get("Principled BSDF")
    b.inputs["Emission Color"].default_value = (*glow, 1.0)
    b.inputs["Emission Strength"].default_value = 0.0
    return mt


def set_glow(mt, s):
    mt.node_tree.nodes.get("Principled BSDF").inputs["Emission Strength"].default_value = s


def chevrons(name, scale=2.2):
    """Yellow and black chevrons (an inverted V repeated), in object space: the stripes slope one way on each half (no text)."""
    mt = bpy.data.materials.new(name)
    mt.use_nodes = True
    nt = mt.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = 0.4
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    absx = nt.nodes.new("ShaderNodeMath")
    absx.operation = "ABSOLUTE"
    nt.links.new(sep.outputs["X"], absx.inputs[0])
    add = nt.nodes.new("ShaderNodeMath")
    add.operation = "ADD"
    nt.links.new(absx.outputs[0], add.inputs[0])
    nt.links.new(sep.outputs["Z"], add.inputs[1])
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = scale
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
    return mt


def cone_mesh(name, r0, r1, h, mat, verts=14):
    bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r0, radius2=r1, depth=h, location=(0, 0, -50))
    ob = bpy.context.object
    ob.name = name
    ob.data.materials.append(mat)
    return ob


class Site:
    def __init__(self):
        road = material("Asphalt", (0.075, 0.075, 0.08), rough=0.85)
        base.asphalt_grain(road)
        paint = material("Line paint", (0.86, 0.86, 0.80), rough=0.6)
        yellow = material("Yellow line", (0.85, 0.60, 0.05), rough=0.6)
        grass = material("Grass", (0.11, 0.21, 0.045), rough=0.95)
        shoulder = material("Shoulder", (0.16, 0.155, 0.15), rough=0.9)
        concrete = material("Median barrier", (0.58, 0.57, 0.54), rough=0.8)
        y0, y1 = Y_RANGE
        L = y1 - y0
        cube("Road", (0.0, (y0 + y1) / 2, -0.05), (2 * ROAD_HALF, L, 0.1), road)
        cube("Shoulder right", (ROAD_HALF + SHOULDER / 2, (y0 + y1) / 2, -0.06), (SHOULDER, L, 0.1), shoulder)
        cube("Shoulder left", (-ROAD_HALF - 0.7, (y0 + y1) / 2, -0.06), (1.4, L, 0.1), shoulder)
        cube("Median barrier", (-ROAD_HALF - 1.55, (y0 + y1) / 2, 0.42), (0.55, L, 0.84), concrete)
        cube("Ground right", (ROAD_HALF + SHOULDER + 30.0, (y0 + y1) / 2, -0.1), (60.0, L, 0.1), grass)
        cube("Ground left", (-ROAD_HALF - 32.0, (y0 + y1) / 2, -0.1), (60.0, L, 0.1), grass)
        cube("Edge line right", (ROAD_HALF - 0.1, (y0 + y1) / 2, 0.002), (0.15, L, 0.004), paint)
        cube("Edge line left", (-ROAD_HALF + 0.1, (y0 + y1) / 2, 0.002), (0.15, L, 0.004), yellow)
        y = y0
        while y < y1:                                            # dashed lane line: 3 m dash, 9 m gap
            cube(f"Dash {y:.0f}", (0.0, y + 1.5, 0.002), (0.15, 3.0, 0.004), paint)
            y += 12.0
        # cones: a taper from the right edge to the lane line, then a row along the lane line past the crew
        orange = material("Cone orange", (0.95, 0.25, 0.02), rough=0.5)
        white = material("Cone band", (0.92, 0.92, 0.90), rough=0.4)
        black = material("Cone base", (0.03, 0.03, 0.03), rough=0.8)
        self.cones = []
        pts = [(ROAD_HALF - 0.4 - (ROAD_HALF - 0.75) * (yy - TAPER[0]) / (TAPER[1] - TAPER[0]), yy) for yy in np.arange(TAPER[0], TAPER[1] + 0.1, 8.0)]
        pts += [(0.35, yy) for yy in np.arange(TAPER[1] + 9.0, WORK_Y[1] + 40.0, 9.0) if not -12.0 < yy < 12.0]
        cone = cone_mesh("Cone proto", 0.17, 0.035, 0.72, orange)
        band = cone_mesh("Cone band proto", 0.105, 0.075, 0.12, white)
        for k, (cx, cy) in enumerate(pts):
            ob = cone.copy()
            ob.data = cone.data
            bpy.context.collection.objects.link(ob)
            ob.location = (cx, cy, 0.40)
            bd = band.copy()
            bd.data = band.data
            bpy.context.collection.objects.link(bd)
            bd.location = (cx, cy, 0.52)
            cube(f"Cone base {k}", (cx, cy, 0.02), (0.38, 0.38, 0.04), black)
        cone.location = band.location = (0, 0, -60)
        # the work area: a fresh asphalt patch, a roller and the crew
        fresh = material("Fresh asphalt", (0.035, 0.035, 0.038), rough=0.7)
        cube("Fresh patch", (X, (WORK_Y[0] + WORK_Y[1]) / 2, 0.004), (3.0, WORK_Y[1] - WORK_Y[0], 0.01), fresh)
        self.roller(X - 0.1, 40.0)
        for k, (wx, wy, rot, bend) in enumerate(((X + 0.9, 22.5, 2.6, 0.0), (X - 0.8, 25.0, -0.4, 0.5), (X + 0.4, 31.0, 1.3, 0.0),
                                                 (X - 0.6, 52.0, 3.0, 0.35))):
            self.worker(k, wx, wy, rot, bend)
        # trees, hills, a far overpass-free horizon
        bark = material("Bark", (0.10, 0.07, 0.05), rough=0.9)
        leaves = [material("Leaves a", (0.10, 0.17, 0.05), rough=0.85), material("Leaves b", (0.16, 0.19, 0.05), rough=0.85)]
        rng = random.Random(32)
        for k in range(70):
            side = rng.choice((-1, 1))
            x = side * rng.uniform(30, 80)                         # clear of every camera
            y = rng.uniform(-300, 150)
            h = rng.uniform(5, 11)
            bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.18, depth=h * 0.5, location=(x, y, h * 0.25))
            bpy.context.object.data.materials.append(bark)
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=h * 0.32, location=(x, y, h * 0.62))
            ob = bpy.context.object
            ob.scale = (1.0, 1.0, 1.25)
            ob.data.materials.append(leaves[k % 2])
        hill = material("Hills", (0.10, 0.14, 0.10), rough=1.0)
        for x, y, sx in ((260, 220, 200), (-240, 260, 220), (300, -120, 160), (-300, -60, 180), (40, 520, 260)):
            bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=1.0, location=(x, y, -10))
            ob = bpy.context.object
            ob.scale = (sx, sx * 0.8, 45)
            ob.data.materials.append(hill)

    def roller(self, x, y):
        yel = material("Roller yellow", (0.92, 0.62, 0.04), rough=0.5)
        steel = material("Roller drum", (0.35, 0.36, 0.37), metal=0.8, rough=0.35)
        dark = material("Roller dark", (0.05, 0.05, 0.05), rough=0.6)
        cube("Roller body", (x, y, 1.05), (1.5, 2.2, 0.9), yel)
        cube("Roller cab", (x, y - 0.2, 2.0), (1.3, 1.1, 1.0), dark)
        cube("Roller roof", (x, y - 0.2, 2.55), (1.5, 1.4, 0.08), yel)
        for dy in (-1.5, 1.5):
            bpy.ops.mesh.primitive_cylinder_add(vertices=28, radius=0.62, depth=1.6, location=(x, y + dy, 0.62), rotation=(0, math.pi / 2, 0))
            bpy.context.object.data.materials.append(steel)

    def worker(self, k, x, y, rot, bend):
        vest = material(f"Vest {k}", (0.98, 0.42, 0.02), rough=0.55)
        trim = material(f"Vest trim {k}", (0.85, 0.88, 0.80), metal=0.3, rough=0.3)
        jeans = material(f"Trousers {k}", (0.08, 0.10, 0.16), rough=0.8)
        skin = material(f"Skin {k}", (0.55, 0.36, 0.25), rough=0.7)
        hat = material(f"Hard hat {k}", (0.95, 0.95, 0.93), rough=0.35)
        root = bpy.data.objects.new(f"Worker {k}", None)
        bpy.context.collection.objects.link(root)
        parts = [cube(f"Leg L {k}", (-0.1, 0.0, 0.43), (0.15, 0.17, 0.86), jeans), cube(f"Leg R {k}", (0.1, 0.0, 0.43), (0.15, 0.17, 0.86), jeans)]
        torso = bpy.data.objects.new(f"Torso pivot {k}", None)
        bpy.context.collection.objects.link(torso)
        torso.location = (0, 0, 0.88)
        torso.parent = root
        up = [cube(f"Torso {k}", (0, 0, 0.30), (0.42, 0.24, 0.60), vest), cube(f"Trim {k}", (0, -0.125, 0.22), (0.43, 0.01, 0.06), trim),
              cube(f"Arm L {k}", (-0.27, 0.05, 0.25), (0.11, 0.13, 0.58), vest), cube(f"Arm R {k}", (0.27, 0.05, 0.25), (0.11, 0.13, 0.58), vest)]
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=10, radius=0.12, location=(0, 0, 0.74))
        head = bpy.context.object
        head.data.materials.append(skin)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.14, location=(0, 0, 0.80))
        cap = bpy.context.object
        cap.scale = (1.0, 1.1, 0.7)
        cap.data.materials.append(hat)
        for ob in up + [head, cap]:
            ob.parent = torso
        for ob in parts:
            ob.parent = root
        torso.rotation_euler = (bend, 0, 0)
        root.location = (x, y, 0.0)
        root.rotation_euler = (0, 0, rot)


class Truck:
    """The protective truck: reference = its rear frame at y = 0 (the cushion's hinge), length along +y."""

    def __init__(self):
        self.root = bpy.data.objects.new("Truck root", None)
        bpy.context.collection.objects.link(self.root)
        orange = material("Truck orange", (0.95, 0.33, 0.03), rough=0.45)
        white = material("Truck white", (0.88, 0.88, 0.86), rough=0.45)
        dark = material("Truck dark", (0.05, 0.05, 0.055), rough=0.6)
        steel = material("Truck steel", (0.30, 0.31, 0.32), metal=0.8, rough=0.4)
        glass = material("Truck glass", (0.08, 0.10, 0.12), metal=0.5, rough=0.1)
        tyre = material("Truck tyre", (0.03, 0.03, 0.035), rough=0.85)
        hub = material("Truck hub", (0.62, 0.62, 0.60), metal=0.8, rough=0.3)
        parts = [cube("Frame rails", (0.0, 3.9, 0.78), (1.0, 7.8, 0.25), dark),
                 cube("Rear frame", (0.0, 0.12, 0.92), (2.40, 0.24, 0.55), steel),
                 cube("Dump body", (0.0, 2.95, 1.62), (2.45, 5.2, 1.15), orange),
                 cube("Body floor", (0.0, 2.95, 1.0), (2.45, 5.2, 0.12), dark),
                 cube("Cab", (0.0, 6.45, 1.95), (2.30, 1.9, 1.55), white),
                 cube("Cab roof", (0.0, 6.45, 2.76), (2.32, 1.92, 0.08), orange),
                 cube("Hood", (0.0, 7.75, 1.40), (2.0, 0.9, 0.85), white),
                 cube("Grille", (0.0, 8.21, 1.35), (1.4, 0.04, 0.6), dark),
                 cube("Bumper", (0.0, 8.24, 0.72), (2.35, 0.14, 0.26), steel),
                 cube("Windshield", (0.0, 7.41, 2.25), (2.05, 0.04, 0.75), glass),
                 cube("Side window L", (-1.16, 6.55, 2.2), (0.03, 1.1, 0.65), glass),
                 cube("Side window R", (1.16, 6.55, 2.2), (0.03, 1.1, 0.65), glass),
                 cube("Mast", (0.0, 5.25, 3.05), (0.14, 0.14, 1.7), dark)]
        # rear chevron panel across the dump body's tailgate and the bumper
        self.chev = chevrons("Truck chevrons", 2.4)
        parts.append(cube("Tailgate chevrons", (0.0, -0.002, 1.62), (2.40, 0.02, 1.05), self.chev))
        # arrow board facing traffic (-y): a black panel with amber lamps forming an arrow pointing left
        parts.append(cube("Arrow board", (0.0, 5.12, 3.95), (2.45, 0.12, 1.25), dark))
        self.lamp = glowable("Arrow lamps", (1.0, 0.55, 0.05), rough=0.3, glow=(1.0, 0.50, 0.04))
        lamp_pts = [(-0.9 + 0.2 * i, 0.0) for i in range(10)] + [(-0.9 + 0.17 * j, 0.17 * j) for j in range(1, 4)] + [(-0.9 + 0.17 * j, -0.17 * j) for j in range(1, 4)]
        for k, (lx, lz) in enumerate(lamp_pts):
            bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.065, depth=0.05, location=(lx, 5.05, 3.95 + lz), rotation=(math.pi / 2, 0, 0))
            ob = bpy.context.object
            ob.data.materials.append(self.lamp)
            parts.append(ob)
        self.beacon = glowable("Beacons", (1.0, 0.6, 0.1), rough=0.3, glow=(1.0, 0.55, 0.05))
        for bx in (-0.8, 0.8):
            bpy.ops.mesh.primitive_cylinder_add(vertices=14, radius=0.1, depth=0.16, location=(bx, 6.2, 2.88))
            ob = bpy.context.object
            ob.data.materials.append(self.beacon)
            parts.append(ob)
        self.wheels = []
        for wy in (1.55, 2.85, 7.35):
            for sx in (-1, 1):
                bpy.ops.mesh.primitive_cylinder_add(vertices=28, radius=0.52, depth=0.42, location=(sx * 1.0, wy, 0.52), rotation=(0, math.pi / 2, 0))
                t_ob = bpy.context.object
                t_ob.data.materials.append(tyre)
                bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.30, depth=0.44, location=(sx * 1.0, wy, 0.52), rotation=(0, math.pi / 2, 0))
                h_ob = bpy.context.object
                h_ob.data.materials.append(hub)
                self.wheels.append((t_ob, h_ob))
                parts += [t_ob, h_ob]
        for ob in parts:
            ob.parent = self.root
        self.root.location = (X, 0.0, 0.0)

    def set(self, roll, t, film_t):
        self.root.location = (X, roll, 0.0)
        on = (film_t % 1.0) < 0.62
        set_glow(self.lamp, 14.0 if on else 0.4)
        set_glow(self.beacon, 9.0 if (film_t * 1.7) % 1.0 < 0.5 else 1.5)


def hex_tube_mesh(width, height, cell):
    """Hexagonal tubes along y in local y 0..1, filling width x height (walls only): the honeycomb's cells."""
    r = cell / math.sqrt(3)                        # circumradius for a flat-to-flat of `cell`
    verts, faces = [], []
    nx = int(width / (1.5 * r)) + 1
    nz = int(height / cell) + 1
    for i in range(nx):
        cx = -width / 2 + r + i * 1.5 * r
        for j in range(nz):
            cz = -height / 2 + cell / 2 + j * cell + (cell / 2 if i % 2 else 0.0)
            if cz + cell / 2 > height / 2 + 1e-6 or cx + r > width / 2 + 1e-6:
                continue
            ring = [(cx + r * math.cos(math.pi / 3 * a), cz + r * math.sin(math.pi / 3 * a)) for a in range(6)]
            b = len(verts)
            for (px, pz) in ring:
                verts.append((px, 0.0, pz))
                verts.append((px, 1.0, pz))
            for a in range(6):
                i0, i1 = b + 2 * a, b + 2 * ((a + 1) % 6)
                faces.append((i0, i1, i1 + 1, i0 + 1))
    return verts, faces


def hex_rim_mesh(width, height, cell, t=0.007):
    """The cells' open ends as thin flat strips in the x-z plane (local y = 0): the bright hexagon outlines seen on the block's face."""
    r = cell / math.sqrt(3)
    verts, faces = [], []
    nx = int(width / (1.5 * r)) + 1
    nz = int(height / cell) + 1
    for i in range(nx):
        cx = -width / 2 + r + i * 1.5 * r
        for j in range(nz):
            cz = -height / 2 + cell / 2 + j * cell + (cell / 2 if i % 2 else 0.0)
            if cz + cell / 2 > height / 2 + 1e-6 or cx + r > width / 2 + 1e-6:
                continue
            for a in range(6):
                p0 = (cx + r * math.cos(math.pi / 3 * a), cz + r * math.sin(math.pi / 3 * a))
                p1 = (cx + r * math.cos(math.pi / 3 * (a + 1)), cz + r * math.sin(math.pi / 3 * (a + 1)))
                q0 = (cx + (r - t) * math.cos(math.pi / 3 * a), cz + (r - t) * math.sin(math.pi / 3 * a))
                q1 = (cx + (r - t) * math.cos(math.pi / 3 * (a + 1)), cz + (r - t) * math.sin(math.pi / 3 * (a + 1)))
                b = len(verts)
                verts += [(p0[0], 0.0, p0[1]), (p1[0], 0.0, p1[1]), (q1[0], 0.0, q1[1]), (q0[0], 0.0, q0[1])]
                faces.append((b, b + 1, b + 2, b + 3))
    return verts, faces


def pleat_mesh(width, height, folds=7, depth=0.05):
    """A crushed band in local y 0..1: a box whose four sides fold in and out like an accordion."""
    verts, faces = [], []
    n = 2 * folds
    w2, h2 = width / 2, height / 2
    for i in range(n + 1):
        y = i / n
        d = depth if i % 2 else 0.0
        for (x, z) in ((-w2 - d, -h2 - d), (w2 + d, -h2 - d), (w2 + d, h2 + d), (-w2 - d, h2 + d)):
            verts.append((x, y, z))
    for i in range(n):
        a, b = 4 * i, 4 * (i + 1)
        for k in range(4):
            k2 = (k + 1) % 4
            faces.append((a + k, a + k2, b + k2, b + k))
    faces.append((0, 3, 2, 1))
    faces.append((4 * n, 4 * n + 1, 4 * n + 2, 4 * n + 3))
    return verts, faces


class Cushion:
    """Mount frame, three honeycomb blocks (index 0 = the back one, crushes first) and the rear face, on a pivot at the hinge."""

    def __init__(self, truck: Truck):
        self.pivot = bpy.data.objects.new("Cushion hinge", None)
        bpy.context.collection.objects.link(self.pivot)
        self.pivot.parent = truck.root
        self.pivot.location = (0.0, m.HINGE[0], m.HINGE[1])
        self.honey = glowable("Honeycomb aluminum", (0.78, 0.79, 0.80), metal=1.0, rough=0.32, glow=(1.0, 0.62, 0.18))
        self.crushed = material("Crushed aluminum", (0.30, 0.30, 0.31), metal=0.9, rough=0.55)
        self.skin = material("Cushion skin", (0.95, 0.68, 0.04), rough=0.45)
        self.face_m = chevrons("Cushion chevrons", 2.0)
        self.plate_m = material("Diaphragm", (0.16, 0.16, 0.17), metal=0.7, rough=0.5)
        self.rim_m = material("Cell rims", (0.92, 0.93, 0.94), metal=1.0, rough=0.25, emission=0.0)
        steel = material("Mount steel", (0.20, 0.20, 0.22), metal=0.8, rough=0.4)
        self.ghost_m = glowable("Ghost outline", (0.7, 0.95, 1.0), rough=0.3, glow=(0.55, 0.9, 1.0))
        set_glow(self.ghost_m, 4.0)
        w, z0, z1 = m.CUSHION_W, m.CUSHION_Z0 - m.HINGE[1], m.CUSHION_Z1 - m.HINGE[1]
        self.h, self.zc = z1 - z0, (z0 + z1) / 2
        self.w = w
        self.mount = cube("Mount frame", (0.0, -m.MOUNT_L / 2, self.zc), (w - 0.3, m.MOUNT_L, self.h - 0.1), steel)
        self.mount.parent = self.pivot
        hv, hf = hex_tube_mesh(w - 0.06, self.h - 0.06, CELL)
        pv, pf = pleat_mesh(w - 0.04, self.h - 0.04)
        rv, rf = hex_rim_mesh(w - 0.06, self.h - 0.06, CELL)
        self.blocks = []
        for k in range(3):
            node = bpy.data.objects.new(f"Block {k}", None)
            bpy.context.collection.objects.link(node)
            node.parent = self.pivot
            honey = mesh_object(f"Honeycomb {k}", hv, hf, self.honey)
            honey.parent = node
            band = mesh_object(f"Crushed band {k}", pv, pf, self.crushed)
            band.parent = node
            skins = {}
            for side, (sx, sz, dx, dz) in {"near": (w / 2, 0, 0.012, self.h), "far": (-w / 2, 0, 0.012, self.h),
                                           "top": (0, self.h / 2, w, 0.012), "bottom": (0, -self.h / 2, w, 0.012)}.items():
                ob = cube(f"Skin {side} {k}", (sx, 0.5, self.zc + sz), (dx, 1.0, dz), self.skin)
                ob.parent = node
                skins[side] = ob
            plate = cube(f"Diaphragm {k}", (0.0, 1.0, 0.0), (w - 0.02, 0.03, self.h - 0.02), self.plate_m)   # at the block's front end
            plate.parent = honey
            rim = mesh_object(f"Cell rims {k}", rv, rf, self.rim_m)          # the open ends' outlines, on the block's back face
            rim.parent = node
            pleat_skin = mesh_object(f"Skin pleats {k}", *pleat_mesh(w + 0.02, self.h + 0.02, folds=6, depth=0.07), self.skin)
            pleat_skin.parent = node
            self.blocks.append({"node": node, "honey": honey, "band": band, "skins": skins, "pleats": pleat_skin, "rim": rim})
        self.face = cube("Rear face", (0.0, 0.0, self.zc), (w, m.FACE_T, self.h), self.face_m)
        self.face.parent = self.pivot
        # the ghost: the uncrushed outline (12 thin glowing edges)
        self.ghost = []
        L = m.CUSHION_L - m.MOUNT_L
        for (x, z) in ((-w / 2, z0), (w / 2, z0), (-w / 2, z1), (w / 2, z1)):
            self.ghost.append((cube(f"Ghost edge y {x} {z}", (x, -m.MOUNT_L - L / 2, z), (0.025, L, 0.025), self.ghost_m), "y"))
        for z in (z0, z1):
            self.ghost.append((cube(f"Ghost edge x {z}", (0.0, -m.CUSHION_L, z), (w, 0.025, 0.025), self.ghost_m), "x"))
        for x in (-w / 2, w / 2):
            self.ghost.append((cube(f"Ghost edge z {x}", (x, -m.CUSHION_L, self.zc), (0.025, 0.025, self.h), self.ghost_m), "z"))
        for ob, _ in self.ghost:
            ob.parent = self.pivot

    def set(self, crush, fold, cut=False, explode=0.0, ghost=False, glow=0.0, open_back=False):
        self.pivot.rotation_euler = (-fold, 0.0, 0.0)
        s = m.stage_crush(crush)
        y = -m.MOUNT_L                                   # build from the hinge backwards: block 2 (front), 1, 0 (back)
        lengths = []
        for k in (2, 1, 0):
            b = self.blocks[k]
            full = m.BLOCK_LEN[k]
            band = s[k] * (0.15 / 0.85)                  # the crushed part squeezed to 15 % of its length
            clean = full - s[k] / 0.85
            cur = clean + band
            y -= explode * (1 if k < 2 else 0.4)
            back = y - cur
            b["node"].location = (0.0, back, self.zc)
            b["honey"].location = (0.0, band, 0.0)
            b["rim"].location = (0.0, band - 0.001, 0.0)
            b["rim"].hide_render = band > 0.004                # once crushed, the face is the folded band
            b["honey"].scale = (1.0, max(clean, 1e-3), 1.0)
            b["band"].location = (0.0, 0.0, 0.0)
            b["band"].scale = (1.0, max(band, 1e-4), 1.0)
            b["band"].hide_render = band < 0.004
            for side, ob in b["skins"].items():
                ob.location = (ob.location.x, band + clean / 2, ob.location.z)
                ob.scale = (1.0, max(clean, 1e-3), 1.0)
                ob.hide_render = cut and side in ("near", "top")
            b["pleats"].scale = (1.0, max(band, 1e-4), 1.0)
            b["pleats"].hide_render = band < 0.004 or cut
            lengths.append(cur)
            y = back
        self.face.location = (0.0, y - m.FACE_T / 2, self.zc)
        self.face.hide_render = bool(open_back)                 # the reveal opens the cushion from the back
        for ob, _ in self.ghost:
            ob.hide_render = not ghost
        set_glow(self.honey, glow)
        return {"stage_crush": [round(v, 4) for v in s], "face_y_local": round(y - m.FACE_T, 4), "explode": round(explode, 3)}


def pickup():
    root = bpy.data.objects.new("Pickup root", None)
    bpy.context.collection.objects.link(root)
    white = material("Pickup white", (0.90, 0.90, 0.88), rough=0.35)
    dark = material("Pickup dark", (0.05, 0.05, 0.055), rough=0.6)
    glass = material("Pickup glass", (0.07, 0.09, 0.11), metal=0.5, rough=0.1)
    tyre = material("Pickup tyre", (0.03, 0.03, 0.035), rough=0.85)
    hub = material("Pickup hub", (0.65, 0.65, 0.63), metal=0.8, rough=0.3)
    lamp = material("Pickup lamps", (0.95, 0.95, 0.9), rough=0.2, emission=0.0)
    front = [cube("Pickup hood", (0.0, 2.15, 1.02), (1.95, 1.6, 0.46), white), cube("Pickup grille", (0.0, 2.93, 0.95), (1.7, 0.05, 0.42), dark),
             cube("Pickup bumper", (0.0, 2.97, 0.62), (2.0, 0.16, 0.24), dark), cube("Pickup lamp L", (-0.72, 2.94, 1.08), (0.3, 0.04, 0.14), lamp),
             cube("Pickup lamp R", (0.72, 2.94, 1.08), (0.3, 0.04, 0.14), lamp)]
    rest = [cube("Pickup lower", (0.0, 0.05, 0.78), (2.0, 5.75, 0.42), white), cube("Pickup cab", (0.0, 0.55, 1.45), (1.95, 1.75, 0.95), white),
            cube("Pickup windshield", (0.0, 1.44, 1.52), (1.8, 0.04, 0.7), glass), cube("Pickup side L", (-0.98, 0.5, 1.55), (0.03, 1.4, 0.55), glass),
            cube("Pickup side R", (0.98, 0.5, 1.55), (0.03, 1.4, 0.55), glass), cube("Pickup bed L", (-0.96, -1.6, 1.22), (0.08, 2.4, 0.5), white),
            cube("Pickup bed R", (0.96, -1.6, 1.22), (0.08, 2.4, 0.5), white), cube("Pickup tailgate", (0.0, -2.8, 1.22), (2.0, 0.08, 0.5), white)]
    wheels = []
    for wy in (1.85, -1.75):
        for sx in (-1, 1):
            bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.40, depth=0.3, location=(sx * 0.9, wy, 0.40), rotation=(0, math.pi / 2, 0))
            ob = bpy.context.object
            ob.data.materials.append(tyre)
            bpy.ops.mesh.primitive_cylinder_add(vertices=14, radius=0.22, depth=0.32, location=(sx * 0.9, wy, 0.40), rotation=(0, math.pi / 2, 0))
            hb = bpy.context.object
            hb.data.materials.append(hub)
            wheels += [ob, hb]
    for ob in front + rest + wheels:
        ob.parent = root
    return root, [(ob, ob.location.copy()) for ob in front], wheels


class Traffic:
    """Two simple cars in the open left lane (wide shots only): positions from simulated time."""

    def __init__(self):
        self.cars = []
        for k, (col, y0, v) in enumerate((((0.10, 0.22, 0.55), 37.0, 26.0), ((0.85, 0.85, 0.83), 70.0, 24.0))):
            root = bpy.data.objects.new(f"Traffic {k}", None)
            bpy.context.collection.objects.link(root)
            paint = material(f"Traffic paint {k}", col, metal=0.3, rough=0.35)
            glass = material(f"Traffic glass {k}", (0.06, 0.08, 0.1), metal=0.5, rough=0.1)
            tyre = material(f"Traffic tyre {k}", (0.03, 0.03, 0.03), rough=0.85)
            parts = [cube(f"Traffic body {k}", (0, 0, 0.6), (1.8, 4.5, 0.6), paint), cube(f"Traffic cabin {k}", (0, -0.2, 1.15), (1.6, 2.3, 0.55), glass)]
            for wy in (1.4, -1.4):
                for sx in (-1, 1):
                    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.33, depth=0.22, location=(sx * 0.85, wy, 0.33), rotation=(0, math.pi / 2, 0))
                    bpy.context.object.data.materials.append(tyre)
                    parts.append(bpy.context.object)
            for ob in parts:
                ob.parent = root
            self.cars.append((root, y0, v))

    def set(self, t):
        for root, y0, v in self.cars:
            root.location = (m.LANE_L, y0 + v * t, 0.0)


class Deformable:
    """A mesh whose vertices follow crumple_motion's crush map (the car's nose against the cushion)."""

    def __init__(self, ob, nose):
        mesh = ob.data
        if mesh.users > 1:
            ob.data = mesh = mesh.copy()
        self.ob, self.mesh = ob, mesh
        n = len(mesh.vertices)
        co = np.zeros(n * 3)
        mesh.vertices.foreach_get("co", co)
        self.local0 = co.reshape(n, 3)
        mw = np.array(ob.matrix_world)
        self.m3, self.t = mw[:3, :3], mw[:3, 3]
        self.p0 = self.local0 @ self.m3.T + self.t
        self.minv = np.linalg.inv(self.m3)
        self.idx = np.where(self.p0[:, 1] > nose - cm.CRUSH_LENGTH - 1e-6)[0]

    def apply(self, s, nose):
        if len(self.idx) == 0:
            return
        out = self.local0.copy()
        out[self.idx] = (cm.crush_map(self.p0[self.idx], s, nose) - self.t) @ self.minv.T
        self.mesh.vertices.foreach_set("co", out.ravel())
        self.mesh.update()


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
    sun_to = cinematic.sun_vector((-0.55, 0.8), 16.0)                  # low sun from the left, behind the camera side of the closed lane
    cinematic.apply_sky(scene, sun_to, strength=0.24, dust=0.7)
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    sun.data.energy, sun.data.angle = 6.5, 0.02
    sun.data.color = (1.0, 0.74, 0.48)
    sun.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()
    bpy.ops.object.light_add(type="AREA", location=(X + 6.0, -3.0, 2.2))      # fills the cut-away from the camera side
    fill = bpy.context.object
    fill.data.size, fill.data.color = 2.5, (1.0, 0.86, 0.72)
    fill.rotation_euler = (0.0, math.radians(-90), 0.0)
    fill.visible_camera = False
    site = Site()
    truck = Truck()
    cushion = Cushion(truck)
    traffic = Traffic()
    pick, pick_front, pick_wheels = pickup()
    # the red car, its nose crushable
    wheel_nodes = {w["node"] for w in wheels.values()}
    parts = [o for o in root.children_recursive if o.type == "MESH" and not any(p in wheel_nodes for p in rb._ancestors(o))]
    ghost = rb.Ghost(parts)
    ghost.set_tint(PAINT)
    ghost.set_factor(0.0, 1e4, 4.0)
    bpy.context.view_layer.update()
    nose = geom["nose"]
    deform = [Deformable(o, nose) for o in parts]
    # skid marks under the rear tandem (four tyres), drawn as long as the truck has slid
    skid_m = material("Skid marks", (0.015, 0.015, 0.015), rough=0.9)
    skids = [cube(f"Skid {sx} {wy}", (0, 0, -40), (0.36, 1.0, 0.006), skid_m) for wy in (1.55, 2.85) for sx in (-1, 1)]
    mats = {"foil": material("Torn skin", (0.80, 0.80, 0.78), metal=0.8, rough=0.3), "glass": material("Lamp glass", (0.85, 0.92, 0.95), rough=0.15),
            "plastic": material("Bumper plastic", (0.06, 0.06, 0.07), rough=0.6)}
    pieces = [cube(f"Debris {k} {kind}", (0, 0, -30), size, mats[kind]) for k, (_, _, _, size, _, kind) in enumerate(m.debris())]
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    r_t = geom["tyre_radius"]

    def render(sh, path):
        scene.render.resolution_x, scene.render.resolution_y = round(FRAME[0] * args.res_scale), round(FRAME[1] * args.res_scale)
        t, variant = sh["t"], sh["variant"]
        cut, reveal, ghost_on, skid_on = bool(sh.get("cut")), bool(sh.get("reveal")), bool(sh.get("ghost")), bool(sh.get("skid"))
        is_pick = variant == "pickup"
        st = m.vehicle_state(t, is_pick) if variant != "deploy" else {"y": -400.0, "crush": 0.0, "roll": 0.0, "speed": 0.0, "force": 0.0}
        fold = m.fold_angle(t) if variant == "deploy" else 0.0
        truck.set(st["roll"], t, sh["film_t"])
        ue = min(1.0, sh["u"] / 0.8)
        explode = 0.45 * ue * ue * (3 - 2 * ue) if reveal else 0.0          # the reveal slides the blocks apart
        glow = 0.0
        cinfo = cushion.set(st["crush"], fold, cut=cut, explode=explode, ghost=ghost_on, glow=glow, open_back=reveal)
        traffic.set(t)
        info = {"variant": variant, "t": round(t, 6), "fold_deg": round(math.degrees(fold), 3), "crush": round(st["crush"], 4),
                "roll": round(st["roll"], 4), "cut": cut, "ghost": ghost_on, **cinfo}
        if variant == "car":
            root.hide_render = False
            for ob in parts:
                ob.hide_render = False
            root.matrix_world = Matrix.Translation(Vector((X, st["y"], 0.0)))
            nc = m.car_nose_crush(t)
            for dm in deform:
                dm.apply(nc, nose)
            spin = (st["y"] + 400.0) / r_t
            for wh in wheels.values():
                wh["node"].rotation_mode = "ZXY"
                wh["node"].rotation_euler = (-spin, 0, 0)
            pick.location = (0, 0, -80)
            info.update({"car_y": round(st["y"], 4), "nose_crush": round(nc, 4)})
        else:
            root.location = (0, 0, -80)
            for dm in deform:
                dm.apply(0.0, nose)
            if is_pick:
                pick.location = (X, st["y"], 0.0)
                nc = m.car_nose_crush(t, True)
                for ob, loc in pick_front:
                    ob.location = (loc.x, loc.y - nc, loc.z)
                for k, w in enumerate(pick_wheels):
                    w.rotation_euler = ((st["y"] + 400.0) / 0.40, math.pi / 2, 0)
                info.update({"pickup_y": round(st["y"], 4), "nose_crush": round(nc, 4)})
            else:
                pick.location = (0, 0, -80)
        # skid marks: from where each rear tyre stood to where it is now
        for k, ob in enumerate(skids):
            wy = (1.55, 2.85)[k // 2]
            sx = (-1, 1)[k % 2]
            L = st["roll"]
            if skid_on and L > 0.02:
                ob.hide_render = False
                ob.location = (X + sx * 1.0, wy + L / 2, 0.004)
                ob.scale = (1.0, L, 1.0)
            else:
                ob.hide_render = True
        air = 0
        for k, ob in enumerate(pieces):
            p = m.debris_pose(k, t) if variant == "car" else None
            if p is None:
                ob.hide_render = True
                continue
            ob.hide_render = False
            ob.location = tuple(p[0])
            ob.rotation_euler = tuple(p[1])
            air += p[2]
        info["airborne"] = air
        info["force_kN"] = round(st["force"] / 1000, 1)
        c = sh["cam"]
        loc, tgt = Vector(c["loc"]), Vector(c["target"])
        dd = cam.data
        dd.sensor_fit, dd.sensor_width, dd.lens, dd.clip_start = "HORIZONTAL", 36.0, c["lens"], 0.02
        dd.clip_end = 5000.0
        dd.dof.use_dof = True
        dd.dof.focus_distance = (tgt - loc).length
        dd.dof.aperture_fstop = c.get("fstop", 8.0)
        base.set_camera(cam, loc, tgt)
        bpy.context.view_layer.update()
        if variant == "car":
            info["subject_box"] = hook_gate.project_box(scene, cam, root.matrix_world, (-0.85, -m.TAIL, 0.0), (0.85, m.NOSE, 1.45))
        elif is_pick:
            info["subject_box"] = hook_gate.project_box(scene, cam, pick.matrix_world, (-1.0, -m.PICKUP_TAIL, 0.0), (1.0, m.PICKUP_NOSE, 1.9))
        else:
            info["subject_box"] = hook_gate.project_box(scene, cam, truck.root.matrix_world, (-1.2, -m.CUSHION_L, 0.0), (1.2, 1.0, 5.2))
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
        print("TMA_FRAME " + json.dumps(info), flush=True)
    (args.out / f"tma-frames-{frames[0]:05d}.json").write_text(json.dumps({"renderer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                                                          "frames": out}, indent=1))


if __name__ == "__main__":
    main()
