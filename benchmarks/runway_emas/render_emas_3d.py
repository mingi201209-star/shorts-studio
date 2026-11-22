"""EP.22 runway arrestor bed (EMAS): 100 % 3D renderer (Blender, Cycles CPU), house style of EP.13-EP.21 (golden hour, depth of
field, a red stripe on the hero). A runway ends at a short setback with yellow chevrons and then a bed of about four thousand 4 ft
cellular-concrete blocks, shallow at the front and deeper further in; beyond it a perimeter road, a fence and a bay.

A procedural 737-class jet (white with a red cheatline, beacon, strobes and landing lights) leaves the end of the runway at 70 knots.
Everything moves from emas_motion: the jet's position and speed, its height and pitch on the crushed bed, the wheels turning, the
blocks under each gear crushed to the depth the tyres sink as the gear passes (three ruts grow behind the wheels), chunks and dust
thrown up by every gear at a rate that follows the speed. The bubble shot shows the foam inside the blocks on the bed's front edge;
the clean-up time-lapse tows the jet out and fills the ruts with new blocks. No text anywhere in the scene."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from benchmarks import hook_gate  # noqa: E402
from benchmarks.can_opener import render_opener_3d as K  # noqa: E402  (data-API mesh helpers)
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402
from benchmarks.rock_net.render_rocknet_3d import merged, textured  # noqa: E402
from benchmarks.runway_emas import emas_motion as em  # noqa: E402
from benchmarks.runway_emas import emas_timeline as tl  # noqa: E402

material = base.material
cube, boxes, cyl, new_object, Sheet = K.cube, K.boxes, K.cyl, K.new_object, K.Sheet
pieces_mesh, set_pieces, rot_xyz, sstep = K.pieces_mesh, K.set_pieces, K.rot_xyz, K.sstep
FRAME = (1080, 1920)
RW_HALF = 22.5
AXIS_Z = 3.2
FUS_R = 1.88
NOSE_Y, TAIL_Y = 18.8, -20.7
WHEEL_R_MAIN, WHEEL_R_NOSE = 0.56, 0.35
MAIN_XS = (-em.MAIN_X - 0.43, -em.MAIN_X + 0.43, em.MAIN_X - 0.43, em.MAIN_X + 0.43)
TRACKS = (("nose", 0.0, 0.5), ("main", -em.MAIN_X, 0.85), ("main", em.MAIN_X, 0.85))
N_CHUNK = 260


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


def ride_height(y: float) -> float:
    """Height of the tyre bottoms above the pavement where the bed is crushed under them."""
    return (1.0 - em.SINK) * em.bed_depth(y)


def plane_pose(y_main: float) -> tuple[float, float]:
    h_m, h_n = ride_height(y_main), ride_height(y_main + em.WHEELBASE)
    return h_m, math.atan2(h_n - h_m, em.WHEELBASE)


def fuselage_geom():
    stations = np.concatenate([np.linspace(NOSE_Y, 14.8, 14), np.linspace(14.6, -8.0, 22), np.linspace(-8.6, TAIL_Y, 18)])
    n = 28
    verts, faces = [], []
    for y in stations:
        if y > 14.8:
            u = (y - 14.8) / (NOSE_Y - 14.8)
            r = FUS_R * math.sqrt(max(0.0, 1 - u ** 2)) ** 0.9
            zc = AXIS_Z - 0.35 * u * u
        elif y < -8.0:
            u = (-8.0 - y) / (-8.0 - TAIL_Y)
            r = FUS_R - (FUS_R - 0.30) * u ** 1.4
            zc = AXIS_Z + 1.25 * u ** 1.6
        else:
            r, zc = FUS_R, AXIS_Z
        for k in range(n):
            a = 2 * math.pi * k / n
            verts.append((r * math.cos(a), y, zc + 1.03 * r * math.sin(a)))
    for i in range(len(stations) - 1):
        for k in range(n):
            a, b = i * n + k, i * n + (k + 1) % n
            faces.append((a, b, b + n, a + n))
    tip, tail = len(verts), len(verts) + 1
    verts += [(0.0, NOSE_Y + 0.02, AXIS_Z - 0.35), (0.0, TAIL_Y - 0.05, AXIS_Z + 1.25)]
    for k in range(n):
        faces.append((tip, (k + 1) % n, k))
        last = (len(stations) - 1) * n
        faces.append((tail, last + k, last + (k + 1) % n))
    return verts, faces


def wing_geom(root_le, root_chord, tip_le, tip_chord, root_t, tip_t, root_xyz, tip_xyz, vertical=False):
    """A tapered lifting surface: a rounded diamond section lofted from root to tip."""
    prof = [(0.0, 0.0), (0.12, 0.45), (0.35, 0.5), (0.7, 0.3), (1.0, 0.0), (0.7, -0.22), (0.35, -0.35), (0.12, -0.32)]
    verts, faces = [], []
    for (le, ch, th, (x, y, z)) in ((root_le, root_chord, root_t, root_xyz), (tip_le, tip_chord, tip_t, tip_xyz)):
        for (u, v) in prof:
            if vertical:
                verts.append((x + v * th, le - u * ch, z))
            else:
                verts.append((x, le - u * ch, z + v * th))
    n = len(prof)
    for k in range(n):
        faces.append((k, (k + 1) % n, n + (k + 1) % n, n + k))
    faces += [tuple(reversed(range(n))), tuple(range(n, 2 * n))]
    return verts, faces


def fuselage_material():
    """White paint with a red cheatline and dark passenger windows from object coordinates (no geometry per window)."""
    m = bpy.data.materials.new("Fuselage paint")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = 0.28
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])

    def op(o, a, b=None):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = o
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                nt.links.new(v, n.inputs[i])
        return n.outputs[0]

    y, z = sep.outputs["Y"], sep.outputs["Z"]
    cabin = op("MULTIPLY", op("GREATER_THAN", y, -7.5), op("LESS_THAN", y, 13.2))
    band = op("MULTIPLY", op("GREATER_THAN", z, AXIS_Z + 0.28), op("LESS_THAN", z, AXIS_Z + 0.58))
    pitch = op("MULTIPLY", op("GREATER_THAN", op("FRACT", op("DIVIDE", y, 0.53)), 0.25), op("LESS_THAN", op("FRACT", op("DIVIDE", y, 0.53)), 0.62))
    win = op("MULTIPLY", op("MULTIPLY", cabin, band), pitch)
    cockpit = op("MULTIPLY", op("MULTIPLY", op("GREATER_THAN", y, 15.6), op("LESS_THAN", y, 17.0)),
                 op("MULTIPLY", op("GREATER_THAN", z, AXIS_Z + 0.35), op("LESS_THAN", z, AXIS_Z + 0.95)))
    dark = op("MAXIMUM", win, cockpit)
    stripe = op("MULTIPLY", op("MULTIPLY", op("GREATER_THAN", z, AXIS_Z - 0.15), op("LESS_THAN", z, AXIS_Z + 0.12)), op("GREATER_THAN", y, -14.0))
    m1 = nt.nodes.new("ShaderNodeMix")
    m1.data_type = "RGBA"
    nt.links.new(stripe, m1.inputs["Factor"])
    m1.inputs["A"].default_value = (0.92, 0.92, 0.93, 1)
    m1.inputs["B"].default_value = (0.75, 0.05, 0.04, 1)
    m2 = nt.nodes.new("ShaderNodeMix")
    m2.data_type = "RGBA"
    nt.links.new(dark, m2.inputs["Factor"])
    nt.links.new(m1.outputs["Result"], m2.inputs["A"])
    m2.inputs["B"].default_value = (0.02, 0.025, 0.035, 1)
    nt.links.new(m2.outputs["Result"], bsdf.inputs["Base Color"])
    return m


def block_material():
    """Light cellular concrete with per-block variation; the 'cut' value shows the foam (bubbles) on the blocks' side faces."""
    m = bpy.data.materials.new("EMAS blocks")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = 0.9
    tc = nt.nodes.new("ShaderNodeTexCoord")
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 1.3
    nz.inputs["Detail"].default_value = 6.0
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    base_c = nt.nodes.new("ShaderNodeValToRGB")
    base_c.color_ramp.elements[0].color, base_c.color_ramp.elements[1].color = (0.50, 0.50, 0.48, 1), (0.66, 0.66, 0.63, 1)
    nt.links.new(nz.outputs["Fac"], base_c.inputs["Fac"])
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.feature = "DISTANCE_TO_EDGE"
    vor.inputs["Scale"].default_value = 16.0
    nt.links.new(tc.outputs["Object"], vor.inputs["Vector"])
    holes = nt.nodes.new("ShaderNodeValToRGB")
    holes.color_ramp.elements[0].position, holes.color_ramp.elements[1].position = 0.03, 0.12
    holes.color_ramp.elements[0].color, holes.color_ramp.elements[1].color = (0.86, 0.85, 0.81, 1), (0.16, 0.15, 0.14, 1)
    nt.links.new(vor.outputs["Distance"], holes.inputs["Fac"])
    sepn = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Normal"], sepn.inputs[0])
    side = nt.nodes.new("ShaderNodeMath")
    side.operation = "LESS_THAN"
    side.inputs[1].default_value = 0.5
    absn = nt.nodes.new("ShaderNodeMath")
    absn.operation = "ABSOLUTE"
    nt.links.new(sepn.outputs["Z"], absn.inputs[0])
    nt.links.new(absn.outputs[0], side.inputs[0])
    cut = K.node_value(nt, "cut", 0.0)
    m["cut"] = cut.name
    f = nt.nodes.new("ShaderNodeMath")
    f.operation = "MULTIPLY"
    nt.links.new(side.outputs[0], f.inputs[0])
    nt.links.new(cut.outputs[0], f.inputs[1])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    nt.links.new(f.outputs[0], mix.inputs["Factor"])
    nt.links.new(base_c.outputs["Color"], mix.inputs["A"])
    nt.links.new(holes.outputs["Color"], mix.inputs["B"])
    nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.25
    nt.links.new(nz.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], bsdf.inputs["Normal"])
    return m


class Airfield:
    def __init__(self):
        asphalt = material("Runway asphalt", (0.075, 0.075, 0.08), rough=0.85)
        base.asphalt_grain(asphalt)
        concrete = material("Setback pavement", (0.40, 0.40, 0.39), rough=0.8)
        white = material("Runway paint", (0.88, 0.88, 0.85), rough=0.6)
        yellow = material("Chevrons", (0.90, 0.68, 0.08), rough=0.6)
        grass = textured("Airfield grass", (0.12, 0.19, 0.06), (0.20, 0.27, 0.09), 0.3, rough=0.95, bump=0.2)
        water = material("Bay water", (0.05, 0.12, 0.17), metal=0.0, rough=0.08)
        road = material("Perimeter road", (0.10, 0.10, 0.11), rough=0.85)
        fence = material("Fence", (0.45, 0.46, 0.47), metal=0.6, rough=0.4)
        city = textured("Far shore", (0.30, 0.30, 0.32), (0.55, 0.53, 0.50), 0.08)
        red = material("Runway end lights", (1.0, 0.05, 0.03), emission=12.0)
        cube("Ground", (0.0, -700.0, -0.06), (2400.0, 1800.0, 0.1), grass)
        cube("Runway", (0.0, -750.0, 0.0), (2 * RW_HALF, 1500.0, 0.06), asphalt)
        cube("Setback", (0.0, em.Y_BED / 2, 0.0), (2 * RW_HALF, em.Y_BED, 0.06), concrete)
        boxes("Centreline", [((0.0, -40.0 - 60.0 * k, 0.035), (0.9, 36.0, 0.01)) for k in range(20)], white)
        boxes("Edge stripes", [((sx * (RW_HALF - 0.9), -750.0, 0.035), (0.9, 1500.0, 0.01)) for sx in (-1, 1)], white)
        chev = []
        for k in range(4):
            y0 = 1.5 + 2.6 * k
            for sx in (-1, 1):
                for j in range(8):
                    x = sx * (1.4 * j + 0.7)
                    chev.append(((x, y0 + 0.35 * j, 0.034), (1.5, 0.9, 0.01)))
        boxes("Blast pad chevrons", chev, yellow)
        boxes("Runway end lights", [((x, 0.2, 0.06), (0.25, 0.25, 0.08)) for x in np.arange(-RW_HALF + 1.0, RW_HALF, 2.5)], red)
        cube("Perimeter road", (0.0, em.Y_BED + em.BED_L + 30.0, 0.0), (400.0, 9.0, 0.06), road)
        boxes("Fence posts", [((x, em.Y_BED + em.BED_L + 22.0, 1.0), (0.08, 0.08, 2.0)) for x in np.arange(-120, 121, 3.0)], fence)
        boxes("Fence rails", [((0.0, em.Y_BED + em.BED_L + 22.0, z), (240.0, 0.05, 0.05)) for z in (0.6, 1.3, 1.95)], fence)
        cube("Bay", (0.0, em.Y_BED + em.BED_L + 700.0, -0.4), (6000.0, 1300.0, 0.1), water)
        rng = np.random.default_rng(22)
        towers = [((float(x), 1450.0 + float(rng.uniform(0, 80)), float(h) / 2), (float(w), float(w), float(h)))
                  for x, w, h in zip(np.arange(-900, 900, 38), rng.uniform(15, 35, 48), rng.uniform(10, 70, 48))]
        boxes("Far shore buildings", towers, city)
        cube("Far shore", (0.0, 1480.0, -0.5), (6000.0, 120.0, 1.0), city)


class Bed:
    def __init__(self):
        self.m = block_material()
        nx = int(em.BED_W / em.BLOCK)
        ny = int(em.BED_L / em.BLOCK)
        xs = -em.BED_W / 2 + em.BLOCK * (np.arange(nx) + 0.5)
        ys = em.Y_BED + em.BLOCK * (np.arange(ny) + 0.5)
        X, Y = np.meshgrid(xs, ys, indexing="ij")
        self.bx, self.by = X.ravel(), Y.ravel()
        self.depth = np.array([em.bed_depth(float(y)) for y in self.by])
        g = em.BLOCK / 2 - 0.012
        proto = [(sx * g, sy * g, sz) for sx in (-1, 1) for sy in (-1, 1) for sz in (0.0, 1.0)]
        self.blocks = pieces_mesh("EMAS bed", proto, K.BOX_FACES, len(self.bx), self.m)
        self.track = np.full(len(self.bx), -1)
        for k, (_, tx, half) in enumerate(TRACKS):
            self.track[np.abs(self.bx - tx) < half + em.BLOCK / 2] = k
        self.pos = np.stack([self.bx, self.by, np.zeros_like(self.bx)], 1)
        self.proto = np.asarray(proto)
        rng = np.random.default_rng(2223)
        rub_m = textured("Rut rubble", (0.30, 0.30, 0.29), (0.52, 0.51, 0.48), 5.0)
        tet = [(0.09, 0.0, 0.0), (-0.045, 0.08, 0.0), (-0.045, -0.08, 0.0), (0.0, 0.0, 0.07)]
        per = 340
        self.rub_track = np.repeat(np.arange(len(TRACKS)), per)
        self.rub_y = np.tile(np.linspace(em.Y_BED + 0.3, em.Y_BED + em.BED_L - 1.0, per), len(TRACKS)) + rng.uniform(-0.2, 0.2, per * len(TRACKS))
        half = np.array([TRACKS[k][2] for k in self.rub_track])
        self.rub_x = np.array([TRACKS[k][1] for k in self.rub_track]) + rng.uniform(-1.0, 1.0, per * len(TRACKS)) * half
        self.rub_rot = rot_xyz(*rng.uniform(-3.1, 3.1, (per * len(TRACKS), 3)).T)
        self.rub_s = rng.uniform(0.8, 2.6, per * len(TRACKS))
        self.rubble = pieces_mesh("Rut rubble", tet, [(0, 1, 2), (0, 1, 3), (1, 2, 3), (2, 0, 3)], per * len(TRACKS), rub_m)

    def set(self, y_main: float, refill: float, cut: bool) -> int:
        """Crush the blocks the gears have rolled over; refill (0..1) restores them in the clean-up."""
        h = self.depth.copy()
        crushed = 0
        for k, (gear, _, _) in enumerate(TRACKS):
            yg = y_main + (em.WHEELBASE if gear == "nose" else 0.0)
            sel = (self.track == k) & (self.by <= yg + em.BLOCK / 2)
            crushed += int(sel.sum())
            h[sel] = self.depth[sel] * (1.0 - em.SINK) * 1.0 + self.depth[sel] * em.SINK * refill
        p = self.proto[None, :, :].repeat(len(h), 0)
        p[:, :, 2] *= h[:, None]
        self.blocks.set((p + self.pos[:, None, :]).reshape(-1, 3))
        K.set_node(self.m, "cut", 1.0 if cut else 0.0)
        pos = np.tile([0.0, 0.0, -50.0], (len(self.rub_y), 1))
        for k, (gear, _, _) in enumerate(TRACKS):
            yg = y_main + (em.WHEELBASE if gear == "nose" else 0.0)
            sel = (self.rub_track == k) & (self.rub_y <= yg - 0.3) & (refill < 0.5)
            floor = np.array([(1.0 - em.SINK) * em.bed_depth(float(y)) for y in self.rub_y[sel]])
            pos[sel] = np.stack([self.rub_x[sel], self.rub_y[sel], floor + 0.03], 1)
        set_pieces(self.rubble, pos, self.rub_rot, self.rub_s)
        return crushed if refill < 0.999 else 0


class Jet:
    def __init__(self):
        self.root = bpy.data.objects.new("Jet root", None)
        bpy.context.collection.objects.link(self.root)
        paint = fuselage_material()
        wing_m = material("Wing grey", (0.70, 0.71, 0.73), metal=0.3, rough=0.35)
        nacelle_m = material("Nacelle", (0.82, 0.83, 0.85), metal=0.5, rough=0.25)
        intake_m = material("Intake", (0.03, 0.03, 0.035), metal=0.6, rough=0.4)
        tail_m = material("Tail red", (0.75, 0.05, 0.04), rough=0.3)
        gear_m = material("Gear", (0.55, 0.56, 0.58), metal=0.85, rough=0.3)
        tyre_m = material("Aircraft tyre", (0.03, 0.03, 0.035), rough=0.85)
        self.beacon_m = material("Beacon", (1.0, 0.05, 0.03), emission=0.0)
        self.strobe_m = material("Strobe", (1.0, 1.0, 1.0), emission=0.0)
        land_m = material("Landing light", (1.0, 0.95, 0.85), emission=30.0)
        parts = []
        v, f = fuselage_geom()
        parts.append(new_object("Fuselage", v, f, paint, smooth=True))
        for sx in (-1, 1):
            v, f = wing_geom(4.6, 7.3, -2.5, 1.4, 0.75, 0.16, (sx * 1.6, 0, 2.05), (sx * 17.2, 0, 3.65))
            if sx < 0:
                f = [tuple(reversed(ff)) for ff in f]
            parts.append(new_object(f"Wing {sx}", v, f, wing_m, smooth=True))
            v, f = wing_geom(-15.6, 3.9, -19.9, 1.3, 0.32, 0.10, (sx * 0.5, 0, 4.35), (sx * 7.2, 0, 4.75))
            if sx < 0:
                f = [tuple(reversed(ff)) for ff in f]
            parts.append(new_object(f"Stabiliser {sx}", v, f, wing_m, smooth=True))
            parts.append(K.cyl(f"Nacelle {sx}", 0.98, 3.9, (sx * 5.0, 5.9, 1.62), nacelle_m, rot=(math.pi / 2, 0, 0), verts=24))
            parts.append(K.cyl(f"Intake {sx}", 0.86, 0.05, (sx * 5.0, 7.86, 1.62), intake_m, rot=(math.pi / 2, 0, 0), verts=24))
            parts.append(cube(f"Pylon {sx}", (sx * 5.0, 4.6, 2.35), (0.25, 2.8, 0.7), wing_m))
            parts.append(cube(f"Landing light {sx}", (sx * 2.2, 4.4, 2.0), (0.35, 0.05, 0.18), land_m))
            parts.append(cube(f"Strobe {sx}", (sx * 17.25, -2.6, 3.7), (0.08, 0.2, 0.08), self.strobe_m))
        v, f = wing_geom(-14.2, 6.2, -19.6, 1.9, 0.32, 0.12, (0, 0, 4.75), (0, 0, 11.2), vertical=True)
        parts.append(new_object("Fin", v, f, tail_m, smooth=True))
        parts.append(cube("Beacon", (0.0, 2.0, AXIS_Z + FUS_R + 0.05), (0.18, 0.3, 0.1), self.beacon_m))
        self.wheels = []
        for x in MAIN_XS:
            t = K.cyl_x(f"Main tyre {x:.2f}", WHEEL_R_MAIN, 0.36, (x, 0.0, WHEEL_R_MAIN), tyre_m, verts=28)
            hub = K.cyl_x(f"Main hub {x:.2f}", 0.30, 0.38, (x, 0.0, WHEEL_R_MAIN), gear_m, verts=12)
            self.wheels += [(t, WHEEL_R_MAIN), (hub, WHEEL_R_MAIN)]
            parts += [t, hub]
        for sx in (-1, 1):
            parts.append(cube(f"Main leg {sx}", (sx * em.MAIN_X, 0.0, 1.35), (0.22, 0.22, 1.6), gear_m))
            parts.append(cube(f"Main axle {sx}", (sx * em.MAIN_X, 0.0, WHEEL_R_MAIN), (1.0, 0.14, 0.14), gear_m))
        for x in (-0.24, 0.24):
            t = K.cyl_x(f"Nose tyre {x}", WHEEL_R_NOSE, 0.24, (x, em.WHEELBASE, WHEEL_R_NOSE), tyre_m, verts=22)
            self.wheels.append((t, WHEEL_R_NOSE))
            parts.append(t)
        parts.append(cube("Nose leg", (0.0, em.WHEELBASE, 0.95), (0.16, 0.16, 1.2), gear_m))
        K.parent_to(parts, self.root)

    def set(self, y_main, dist, film_t, visible=True):
        h, pitch = plane_pose(y_main)
        self.root.location = (0.0, y_main, h)
        self.root.rotation_euler = (pitch, 0.0, 0.0)
        for ob, r in self.wheels:
            ob.rotation_euler = (-dist / r, 0.0, 0.0)
        self.beacon_m.node_tree.nodes.get("Principled BSDF").inputs["Emission Strength"].default_value = 40.0 if (film_t % 1.0) < 0.12 else 0.0
        self.strobe_m.node_tree.nodes.get("Principled BSDF").inputs["Emission Strength"].default_value = 60.0 if (film_t % 1.3) < 0.06 else 0.0
        for o in [self.root, *self.root.children_recursive]:
            o.hide_render = not visible
        return h, pitch


class Spray:
    """Chunks and dust thrown up by each gear while it rolls through the bed, emitted at a rate that follows the speed."""

    def __init__(self):
        rng = np.random.default_rng(2222)
        chunk_m = textured("Crushed concrete", (0.48, 0.47, 0.44), (0.70, 0.69, 0.65), 6.0)
        tet = [(0.10, 0.0, 0.0), (-0.05, 0.085, 0.0), (-0.05, -0.085, 0.0), (0.0, 0.0, 0.11)]
        n = N_CHUNK * len(TRACKS)
        self.chunks = pieces_mesh("Spray chunks", tet, [(0, 1, 2), (0, 1, 3), (1, 2, 3), (2, 0, 3)], n, chunk_m)
        self.n = n
        self.gear = np.repeat(np.arange(len(TRACKS)), N_CHUNK)
        self.u = np.tile(np.linspace(0.0, 1.0, N_CHUNK), len(TRACKS))       # position along the gear's path through the bed (0..1)
        self.vel = np.stack([rng.uniform(-4.5, 4.5, n), rng.uniform(0.2, 1.2, n), rng.uniform(2.5, 8.0, n)], 1)
        self.spin = rng.uniform(-25, 25, (n, 3))
        self.size = rng.uniform(0.8, 4.5, n)
        self.dx = rng.uniform(-0.4, 0.4, n)
        dust = bpy.data.materials.new("Concrete dust")
        dust.use_nodes = True
        nt = dust.node_tree
        bsdf = nt.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = (0.88, 0.86, 0.82, 1.0)
        bsdf.inputs["Roughness"].default_value = 1.0
        info = nt.nodes.new("ShaderNodeObjectInfo")
        nt.links.new(info.outputs["Alpha"], bsdf.inputs["Alpha"])
        self.puffs = [K.sphere(f"Dust {k}", 1.0, (0, 0, 0), dust, seg=14, rings=9) for k in range(3 * 8)]          # geometry at the origin: placed by location
        self._key = None

    def _times(self):
        """Emission time of each chunk: when its gear is at the chunk's place along its path through the bed."""
        stop = em.main_y(60.0)
        t_out = np.full(self.n, np.nan)
        y_out = np.zeros(self.n)
        for k, (gear, _, _) in enumerate(TRACKS):
            off = em.WHEELBASE if gear == "nose" else 0.0
            y_end = stop + off
            if y_end <= em.Y_BED:
                continue
            sel = self.gear == k
            ys = em.Y_BED + 0.5 + self.u[sel] * (y_end - em.Y_BED - 0.5)
            ts = np.array([em.time_at(y - off) for y in ys], dtype=float)
            t_out[sel] = ts
            y_out[sel] = ys
        return t_out, y_out

    def set(self, t, y_main, visible=True, dust=True):
        if self._key is None:
            self._key = self._times()
        te, ye = self._key
        tau = t - te
        live = np.isfinite(te) & (tau >= 0) & visible
        pos = np.tile([0.0, 0.0, -50.0], (self.n, 1))
        rot = np.repeat(np.eye(3)[None], self.n, 0)
        airborne = 0
        if live.any():
            gx = np.array([TRACKS[g][1] for g in self.gear]) + self.dx
            v_plane = np.array([em.speed(float(x)) if np.isfinite(x) else 0.0 for x in te])
            vel = self.vel * np.array([1.0, 1.0, 1.0]) + np.stack([np.zeros(self.n), 0.35 * v_plane, 0.08 * v_plane], 1)
            p0 = np.stack([gx, ye, np.array([em.bed_depth(float(y)) for y in ye])], 1)
            tt = np.where(live, tau, 0.0)
            pp = p0 + vel * tt[:, None] + np.array([0, 0, -0.5 * em.G]) * (tt ** 2)[:, None]
            floor = np.array([em.bed_depth(float(y)) if em.Y_BED <= y <= em.Y_BED + em.BED_L else 0.0 for y in pp[:, 1]]) + 0.02
            landed = pp[:, 2] < floor
            pp[landed, 2] = floor[landed]
            pos[live] = pp[live]
            r = rot_xyz(*(self.spin * np.minimum(tt, 1.0)[:, None]).T)
            rot[live] = r[live]
            airborne = int((live & ~landed).sum())
        set_pieces(self.chunks, pos, rot, self.size)
        for k, ob in enumerate(self.puffs):
            gear = k // 8
            off = em.WHEELBASE if TRACKS[gear][0] == "nose" else 0.0
            yg = y_main + off
            v = em.speed(t)
            if not visible or not dust or yg < em.Y_BED or v < 0.5:
                ob.location = (0, 0, -50)
                continue
            j = k % 8
            age = ((t * 1.8 + j / 8.0) % 1.0)
            side = 1.0 if TRACKS[gear][1] >= 0 else -1.0
            ob.location = (TRACKS[gear][1] + side * (0.6 + 2.2 * age) * math.cos(2.4 * j), yg + 0.5 - 7.0 * age, em.bed_depth(yg) + 0.6 + 2.2 * age)
            r = (1.0 + 3.6 * age) * (0.7 if TRACKS[gear][0] == "nose" else 1.0)
            ob.scale = (r, r * 1.2, r * 0.7)
            ob.color = (1, 1, 1, 0.8 * (1 - age) ** 1.2 * min(1.0, v / 8.0))
        return airborne


def main():
    args = arguments()
    args.out.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
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
    sun_to = cinematic.sun_vector((-0.75, 0.45), 20.0)
    cinematic.apply_sky(scene, sun_to, strength=0.24, dust=0.7)
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    sun.data.energy, sun.data.angle = 6.0, 0.02
    sun.data.color = (1.0, 0.76, 0.52)
    sun.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()
    Airfield()
    bed = Bed()
    jet = Jet()
    spray = Spray()
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    y_rest = em.main_y(60.0)

    def render(sh, path):
        scene.render.resolution_x, scene.render.resolution_y = round(FRAME[0] * args.res_scale), round(FRAME[1] * args.res_scale)
        t, variant, film_t = sh["t"], sh["variant"], sh["film_t"]
        y = tl.plane_y(sh)
        if variant == "restore":
            f = min(1.0, max(0.0, t))
            refill = float(sstep(0.45, 0.95, f))
            crush_y = y_rest
            sim = 60.0
            dist = y - y_rest
        else:
            refill, crush_y, sim, dist = 0.0, y, t, y + 30.0
        crushed = bed.set(crush_y, refill, bool(sh.get("cut")))
        h, pitch = jet.set(y, dist, film_t, visible=(variant != "restore" or y > -55.0))
        airborne = spray.set(sim, y, visible=(variant == "overrun"), dust=not sh.get("nodust"))
        c = sh["cam"]
        o = Vector((0.0, y, 0.0)) if c["rel"] == "plane" else Vector((0.0, 0.0, 0.0))
        loc, tgt = o + Vector(c["loc"]), o + Vector(c["target"])
        dd = cam.data
        dd.sensor_fit, dd.sensor_width, dd.lens, dd.clip_start = "HORIZONTAL", 36.0, c["lens"], 0.02
        dd.clip_end = 4000.0
        dd.dof.use_dof = True
        dd.dof.focus_distance = (tgt - loc).length
        dd.dof.aperture_fstop = c.get("fstop", 8.0)
        base.set_camera(cam, loc, tgt)
        bpy.context.view_layer.update()
        box = hook_gate.project_box(scene, cam, jet.root.matrix_world, (-17.2, TAIL_Y, 0.0), (17.2, NOSE_Y, 11.2))
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        return {"variant": variant, "t": round(t, 6), "y_main": round(y, 4), "speed": round(em.speed(sim), 4) if variant == "overrun" else 0.0,
                "height": round(h, 4), "pitch": round(pitch, 6), "crushed_blocks": crushed, "refill": round(refill, 4), "chunks_airborne": airborne,
                "cut": bool(sh.get("cut")), "subject_box": box, "cam_world": [round(v, 3) for v in loc], "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    segs = tl.segments()
    a0, b0 = (int(v) for v in args.frames.split("-"))
    frames = [int(v) for v in args.list.split(",")] if args.list else list(range(a0, b0 + 1))
    out = []
    src_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    for f in frames:
        t0 = time.time()
        sh = tl.frame_state(f, segs)
        part = render(sh, args.out / f"frame_{f:05d}.png")
        info = {"frame": f, "segment": sh["segment"], "split": False, "parts": [part], "render_seconds": round(time.time() - t0, 1)}
        out.append(info)
        print("EMAS_FRAME " + json.dumps(info), flush=True)
    (args.out / f"emas-frames-{frames[0]:05d}.json").write_text(json.dumps({"renderer_source_sha256": src_sha, "frames": out}, indent=1))


if __name__ == "__main__":
    main()
