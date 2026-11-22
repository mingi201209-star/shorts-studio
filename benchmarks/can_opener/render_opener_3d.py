"""EP.20 "can opener" low rail bridge: 100 % 3D renderer (Blender, Cycles CPU), house style of EP.13-EP.19 (golden hour, depth of
field, the red CC0 sedan in the street). A two-lane downtown street passes under a steel plate-girder rail bridge on concrete
abutments; a striped steel crash beam on two columns hangs across the street in front of it, its underside at the posted clearance.

The 13 ft box truck is procedural and deforms from opener_motion every frame: the front wall above the clearance folds back, the
side walls above it fold outward, the roof skin (0.040 in aluminium) peels off at the beam and rolls up into a scroll against the
beam face, rivets pop out of the top rails one by one, roof bows buckle and drop into the box, shards and sparks fly from the peel
front, and the cab (lower than the beam) rolls under untouched. Upstream: the over-height detector (a red beam across the street at
11 ft 8 in that the box breaks), a warning panel with flashing beacons and a turn arrow, the signal that turns red. A freight train
crosses in the bridge shot; the 2019 raise lifts the bridge 8 in on new shims while a red outline keeps the old height. Everything
that moves comes from opener_motion. No text anywhere in the scene."""
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
from benchmarks.belt_limiter import render_belt_3d as rb  # noqa: E402
from benchmarks.can_opener import opener_motion as om  # noqa: E402
from benchmarks.can_opener import opener_timeline as tl  # noqa: E402
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402

material = base.material
FRAME = (1080, 1920)
PAINT = (1.75, 0.30, 0.24)
ROAD_HALF, WALK = 3.6, 6.0
CROSS_Y = (-14.0, -6.0)
GIRDER_YS = (0.95, 4.25)
TRACK_Y = 2.6
GIRDER_D = 1.25
BRIDGE_GAP = 0.12                      # girders sit a little higher than the beam's underside
ABUT_X = 6.3
SPAN = 7.6
W_IN = om.BOX_W / 2
R_MIN, C_CURL = 0.05, 0.34             # roof scroll: innermost radius; radius grows with the square root of the sheet wound inside
A_FLAP, B_FOLD = math.radians(126), math.radians(100)
NY = 161
SIGNAL_XY = (1.8, -14.6)                # near-side mast arm over the stop line, behind the hero cameras
WARN_SIGN = (4.9, -28.0)


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


def sstep(e0, e1, x):
    u = np.clip((np.asarray(x, dtype=float) - e0) / (e1 - e0), 0.0, 1.0)
    return u * u * (3 - 2 * u)


def crumple(a, b, seed=0.0):
    """Smooth deterministic wrinkles in material coordinates (so they stay with the metal)."""
    return (0.5 * np.sin(11.3 * a + 7.1 * b + 0.4 + seed) + 0.3 * np.sin(5.7 * a - 13.9 * b + 1.9 + 2 * seed)
            + 0.2 * np.sin(23.0 * a + 3.1 * b + 4.0 + 3 * seed) + 0.15 * np.sin(31.0 * b - 17.0 * a + seed))


def grid_faces(nu, nv):
    return [(i * nv + j, (i + 1) * nv + j, (i + 1) * nv + j + 1, i * nv + j + 1) for i in range(nu - 1) for j in range(nv - 1)]


class Sheet:
    """A mesh whose vertex positions are rewritten every frame (numpy), with a UV map fixed at build time."""

    def __init__(self, name, co, faces, mats, uv=None, thickness=0.0, parent=None, offset=0.0, smooth=True):
        me = bpy.data.meshes.new(name)
        me.from_pydata([tuple(v) for v in co], [], faces)
        me.update()
        if smooth:
            me.polygons.foreach_set("use_smooth", [True] * len(faces))
        for m in mats:
            me.materials.append(m)
        if uv is not None:
            lay = me.uv_layers.new(name="UVMap")
            vi = np.zeros(len(me.loops), dtype=np.int32)
            me.loops.foreach_get("vertex_index", vi)
            lay.data.foreach_set("uv", np.asarray(uv, dtype=np.float32)[vi].ravel())
        self.ob = bpy.data.objects.new(name, me)
        bpy.context.collection.objects.link(self.ob)
        if parent is not None:
            self.ob.parent = parent
        if thickness:
            mod = self.ob.modifiers.new("Thickness", "SOLIDIFY")
            mod.thickness, mod.offset = thickness, offset
            if len(mats) > 1:
                mod.material_offset = 1
        self.base = np.asarray(co, dtype=np.float64)

    def set(self, co):
        self.ob.data.vertices.foreach_set("co", np.asarray(co, dtype=np.float32).ravel())
        self.ob.data.update()


def pieces_mesh(name, proto_co, proto_faces, n, mat, parent=None):
    """n copies of a small piece in one mesh; set_pieces() moves and turns each copy."""
    co, faces = [], []
    for k in range(n):
        off = k * len(proto_co)
        co += [tuple(v) for v in proto_co]
        faces += [tuple(i + off for i in f) for f in proto_faces]
    s = Sheet(name, co, faces, [mat], smooth=False, parent=parent)
    s.proto = np.asarray(proto_co, dtype=np.float64)
    s.n = n
    return s


def set_pieces(sheet, pos, rot=None, scale=None):
    """pos: (n, 3); rot: (n, 3, 3) or None; scale: (n,) or None. A piece at z < -40 is hidden under the road."""
    p = sheet.proto[None, :, :]
    if scale is not None:
        p = p * np.asarray(scale)[:, None, None]
    if rot is not None:
        p = np.einsum("nij,nvj->nvi", rot, np.broadcast_to(p, (sheet.n, *sheet.proto.shape)))
    sheet.set((p + np.asarray(pos)[:, None, :]).reshape(-1, 3))


def rot_xyz(ax, ay, az):
    cx, sx, cy, sy, cz, sz = np.cos(ax), np.sin(ax), np.cos(ay), np.sin(ay), np.cos(az), np.sin(az)
    one, zero = np.ones_like(ax), np.zeros_like(ax)
    rx = np.stack([np.stack([one, zero, zero], -1), np.stack([zero, cx, -sx], -1), np.stack([zero, sx, cx], -1)], -2)
    ry = np.stack([np.stack([cy, zero, sy], -1), np.stack([zero, one, zero], -1), np.stack([-sy, zero, cy], -1)], -2)
    rz = np.stack([np.stack([cz, -sz, zero], -1), np.stack([sz, cz, zero], -1), np.stack([zero, zero, one], -1)], -2)
    return rz @ ry @ rx


def node_value(nt, label, value):
    n = nt.nodes.new("ShaderNodeValue")
    n.label = label
    n.outputs[0].default_value = value
    return n


def box_paint(name, colour, rough, glow_band=True, alpha_node=False, stripe=False):
    """Box panels: paint or bare aluminium with exterior post ridges along the UV (u = metres along the box, v = height), an emission
    band above the clearance (v > h_cut) switched by 'band' and an optional 'alpha' for the x-ray shot."""
    m = material(name, colour, metal=0.0 if colour[0] > 0.8 else 0.85, rough=rough)
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    uv = nt.nodes.new("ShaderNodeUVMap")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(uv.outputs["UV"], sep.inputs[0])
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type, wave.bands_direction = "BANDS", "X"
    wave.inputs["Scale"].default_value = 1.0 / om.BOW_PITCH * 0.5
    wave.inputs["Distortion"].default_value = 0.0
    nt.links.new(uv.outputs["UV"], wave.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[1].position = 0.86, 0.96
    nt.links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.35
    bump.inputs["Distance"].default_value = 0.01
    nt.links.new(ramp.outputs["Color"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    if stripe:
        lo = nt.nodes.new("ShaderNodeMath")
        lo.operation = "GREATER_THAN"
        lo.inputs[1].default_value = 1.55
        nt.links.new(sep.outputs["Y"], lo.inputs[0])
        hi = nt.nodes.new("ShaderNodeMath")
        hi.operation = "LESS_THAN"
        hi.inputs[1].default_value = 1.95
        nt.links.new(sep.outputs["Y"], hi.inputs[0])
        both = nt.nodes.new("ShaderNodeMath")
        both.operation = "MULTIPLY"
        nt.links.new(lo.outputs[0], both.inputs[0])
        nt.links.new(hi.outputs[0], both.inputs[1])
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        nt.links.new(both.outputs[0], mix.inputs["Factor"])
        mix.inputs["A"].default_value = (*colour, 1.0)
        mix.inputs["B"].default_value = (0.03, 0.16, 0.48, 1.0)
        nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    m["band"] = node_value(nt, "band", 0.0).name
    m["h_cut"] = node_value(nt, "h_cut", om.CLEAR_OLD).name
    if glow_band:
        gt = nt.nodes.new("ShaderNodeMath")
        gt.operation = "GREATER_THAN"
        nt.links.new(sep.outputs["Y"], gt.inputs[0])
        nt.links.new(nt.nodes[m["h_cut"]].outputs[0], gt.inputs[1])
        mul = nt.nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        nt.links.new(gt.outputs[0], mul.inputs[0])
        nt.links.new(nt.nodes[m["band"]].outputs[0], mul.inputs[1])
        bsdf.inputs["Emission Color"].default_value = (1.0, 0.12, 0.05, 1.0)
        nt.links.new(mul.outputs[0], bsdf.inputs["Emission Strength"])
    if alpha_node:
        m["alpha"] = node_value(nt, "alpha", 1.0).name
        nt.links.new(nt.nodes[m["alpha"]].outputs[0], bsdf.inputs["Alpha"])
    return m


def set_node(m, key, value):
    if key in m.keys():
        m.node_tree.nodes[m[key]].outputs[0].default_value = value


def stripes(name):
    """Yellow and black diagonal hazard stripes in object space, with dark scuffs low on the faces (no text)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = 0.5
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (math.radians(45), 0.0, 0.0)
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type, wave.bands_direction = "BANDS", "X"
    wave.inputs["Scale"].default_value = 1.1
    wave.inputs["Distortion"].default_value = 0.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    ramp.color_ramp.elements[0].color = (0.02, 0.02, 0.02, 1)
    ramp.color_ramp.elements[1].position = 0.5
    ramp.color_ramp.elements[1].color = (0.95, 0.66, 0.03, 1)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], wave.inputs["Vector"])
    nt.links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 7.0
    noise.inputs["Detail"].default_value = 6.0
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    scuff = nt.nodes.new("ShaderNodeValToRGB")
    scuff.color_ramp.elements[0].position, scuff.color_ramp.elements[1].position = 0.55, 0.68
    scuff.color_ramp.elements[0].color = (0.10, 0.09, 0.08, 1)
    scuff.color_ramp.elements[1].color = (1, 1, 1, 1)
    nt.links.new(noise.outputs["Fac"], scuff.inputs["Fac"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type, mix.blend_type = "RGBA", "MULTIPLY"
    mix.inputs["Factor"].default_value = 1.0
    nt.links.new(ramp.outputs["Color"], mix.inputs["A"])
    nt.links.new(scuff.outputs["Color"], mix.inputs["B"])
    nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    return m


def facade(name, brick, seed):
    """Brick or stucco walls with a grid of dark windows from object coordinates and the face normal (no geometry per window)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = 0.85
    tc = nt.nodes.new("ShaderNodeTexCoord")
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    nsep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Normal"], nsep.inputs[0])

    def math(op, a, b=None):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                nt.links.new(v, n.inputs[i])
        return n.outputs[0]

    ax = math("ABSOLUTE", nsep.outputs["X"])
    horiz = math("ADD", math("MULTIPLY", sep.outputs["Y"], ax), math("MULTIPLY", sep.outputs["X"], math("SUBTRACT", 1.0, ax)))
    fx = math("FRACT", math("DIVIDE", horiz, 2.6))
    fz = math("FRACT", math("DIVIDE", math("ADD", sep.outputs["Z"], 0.0), 3.3))
    wx = math("MULTIPLY", math("GREATER_THAN", fx, 0.22), math("LESS_THAN", fx, 0.78))
    wz = math("MULTIPLY", math("GREATER_THAN", fz, 0.30), math("LESS_THAN", fz, 0.80))
    up = math("GREATER_THAN", sep.outputs["Z"], 0.9)
    vert = math("LESS_THAN", math("ABSOLUTE", nsep.outputs["Z"]), 0.5)
    win = math("MULTIPLY", math("MULTIPLY", wx, wz), math("MULTIPLY", up, vert))
    bt = nt.nodes.new("ShaderNodeTexBrick")
    bt.inputs["Color1"].default_value = (*brick, 1)
    bt.inputs["Color2"].default_value = (*(c * 0.8 for c in brick), 1)
    bt.inputs["Mortar"].default_value = (0.55, 0.52, 0.48, 1)
    bt.inputs["Scale"].default_value = 4.0
    bt.inputs["Mortar Size"].default_value = 0.015
    nt.links.new(tc.outputs["Object"], bt.inputs["Vector"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    nt.links.new(win, mix.inputs["Factor"])
    nt.links.new(bt.outputs["Color"], mix.inputs["A"])
    mix.inputs["B"].default_value = (0.03, 0.04, 0.05, 1)
    nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    r = math("ADD", 0.85, math("MULTIPLY", win, -0.75))
    nt.links.new(r, bsdf.inputs["Roughness"])
    return m


BOX_FACES = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]


def box_verts(center, dims):
    cx, cy, cz = center
    hx, hy, hz = (d / 2 for d in dims)
    return [(cx + sx * hx, cy + sy * hy, cz + sz * hz) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]


def new_object(name, verts, faces, mat, smooth=False):
    """Mesh object through the data API (no operators: building hundreds of parts with bpy.ops took minutes per render shard)."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.update()
    if smooth:
        me.polygons.foreach_set("use_smooth", [True] * len(faces))
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    return ob


def cube(name, center, dims, mat):
    return new_object(name, box_verts(center, dims), BOX_FACES, mat)


def boxes(name, items, mat):
    """Many boxes [(center, dims), ...] in one mesh."""
    verts, faces = [], []
    for c, d in items:
        off = len(verts)
        verts += box_verts(c, d)
        faces += [tuple(i + off for i in f) for f in BOX_FACES]
    return new_object(name, verts, faces, mat)


def cyl_geom(r, depth, loc, rot=(0.0, 0.0, 0.0), verts=16):
    m = Matrix.Translation(loc) @ _euler(rot)
    vs = [m @ Vector((r * math.cos(2 * math.pi * k / verts), r * math.sin(2 * math.pi * k / verts), z)) for z in (-depth / 2, depth / 2) for k in range(verts)]
    faces = [(k, (k + 1) % verts, verts + (k + 1) % verts, verts + k) for k in range(verts)]
    faces += [tuple(reversed(range(verts))), tuple(range(verts, 2 * verts))]
    return [tuple(v) for v in vs], faces


def _euler(rot):
    from mathutils import Euler
    return Euler(rot, "XYZ").to_matrix().to_4x4()


def cyl(name, r, depth, loc, mat, rot=(0.0, 0.0, 0.0), verts=16):
    v, f = cyl_geom(r, depth, loc, rot, verts)
    return new_object(name, v, f, mat, smooth=True)


def cyl_x(name, r, length, loc, mat, verts=16):
    """Cylinder with its axis along x and its origin at its centre (for parts that spin, move or stretch every frame)."""
    v, f = cyl_geom(r, length, (0.0, 0.0, 0.0), (0.0, math.pi / 2, 0.0), verts)
    ob = new_object(name, v, f, mat, smooth=True)
    ob.location = loc
    return ob


def cyls(name, items, mat, verts=14):
    """Many cylinders [(r, depth, loc, rot), ...] in one mesh."""
    vs, fs = [], []
    for r, depth, loc, rot in items:
        v, f = cyl_geom(r, depth, loc, rot, verts)
        off = len(vs)
        vs += v
        fs += [tuple(i + off for i in ff) for ff in f]
    return new_object(name, vs, fs, mat, smooth=True)


def sphere(name, r, loc, mat, scale=(1.0, 1.0, 1.0), seg=12, rings=8):
    vs, fs = [], []
    for i in range(1, rings):
        th = math.pi * i / rings
        for k in range(seg):
            ph = 2 * math.pi * k / seg
            vs.append((loc[0] + r * scale[0] * math.sin(th) * math.cos(ph), loc[1] + r * scale[1] * math.sin(th) * math.sin(ph), loc[2] + r * scale[2] * math.cos(th)))
    top, bot = len(vs), len(vs) + 1
    vs += [(loc[0], loc[1], loc[2] + r * scale[2]), (loc[0], loc[1], loc[2] - r * scale[2])]
    for i in range(rings - 2):
        for k in range(seg):
            a, b = i * seg + k, i * seg + (k + 1) % seg
            fs.append((a, b, b + seg, a + seg))
    for k in range(seg):
        fs.append((top, (k + 1) % seg, k))
        fs.append((bot, (rings - 2) * seg + k, (rings - 2) * seg + (k + 1) % seg))
    return new_object(name, vs, fs, mat, smooth=True)


def bevel(ob, w=0.04, seg=2):
    mod = ob.modifiers.new("Bevel", "BEVEL")
    mod.width, mod.segments = w, seg
    return ob


def parent_to(obs, parent):
    for o in obs:
        o.parent = parent


# --- the street ----------------------------------------------------------------------------------------------------------------------
class Street:
    def __init__(self):
        road = material("Asphalt", (0.07, 0.07, 0.075), rough=0.85)
        base.asphalt_grain(road)
        walk = material("Sidewalk", (0.50, 0.49, 0.46), rough=0.85)
        curb = material("Curb", (0.60, 0.59, 0.55), rough=0.8)
        white = material("Line paint", (0.85, 0.85, 0.80), rough=0.6)
        yellow = material("Centre line", (0.85, 0.62, 0.08), rough=0.6)
        grass = material("Grass", (0.11, 0.21, 0.045), rough=0.95)
        lot = material("Lot asphalt", (0.10, 0.10, 0.105), rough=0.9)
        y0, y1 = -140.0, 110.0
        cube("Road", (0.0, (y0 + y1) / 2, -0.05), (2 * ROAD_HALF, y1 - y0, 0.1), road)
        cube("Cross street", (0.0, sum(CROSS_Y) / 2, -0.049), (120.0, CROSS_Y[1] - CROSS_Y[0], 0.1), road)
        for sx in (-1, 1):
            for a, b in ((y0, CROSS_Y[0]), (CROSS_Y[1], y1)):
                cube(f"Sidewalk {sx} {a:.0f}", (sx * (ROAD_HALF + WALK) / 2, (a + b) / 2, 0.075), (WALK - ROAD_HALF, b - a, 0.15), walk)
                cube(f"Curb {sx} {a:.0f}", (sx * (ROAD_HALF + 0.08), (a + b) / 2, 0.08), (0.16, b - a, 0.16), curb)
        cube("Ground left", (-40.0, -15.0, -0.06), (68.0, 250.0, 0.1), grass)
        cube("Ground right", (40.0, -15.0, -0.06), (68.0, 250.0, 0.1), grass)
        cube("Parking lot", (-14.0, -26.0, 0.005), (16.0, 22.0, 0.02), lot)
        items = []                                                             # double yellow centre line
        for k in range(int((y1 - y0) / 6)):
            y = y0 + 6 * k + 1.5
            if CROSS_Y[0] - 1 < y < CROSS_Y[1] + 1:
                continue
            items += [((dx, y + 1.5, 0.004), (0.10, 6.0, 0.01)) for dx in (-0.09, 0.09)]
        boxes("Centre line", items, yellow)
        cube("Stop line", (ROAD_HALF / 2, om.Y_STOP + 0.2, 0.006), (ROAD_HALF - 0.2, 0.40, 0.01), white)
        boxes("Crosswalk", [((-ROAD_HALF + 0.45 + 0.75 * k, CROSS_Y[0] - 1.35, 0.006), (0.45, 2.2, 0.01)) for k in range(10)], white)
        bark = material("Bark", (0.10, 0.07, 0.05), rough=0.9)
        leaves = material("Leaves", (0.12, 0.20, 0.06), rough=0.85)
        rng = random.Random(20)
        for x, y in ((-5.2, -73), (5.2, -66), (-5.2, -86), (5.2, -52), (5.2, -21.0), (-5.2, 20), (5.2, 27), (-5.2, 38), (5.2, 50)):
            h = rng.uniform(5.5, 7.5)
            cyl("Trunk", 0.15, h * 0.55, (x, y, h * 0.27), bark, verts=8)
            sphere("Canopy", h * 0.28, (x, y, h * 0.70), leaves, scale=(1.0, 1.0, 1.15))
        pole = material("Lamp pole", (0.12, 0.12, 0.13), metal=0.6, rough=0.45)
        for x, y in ((-5.6, -56), (5.6, -38), (-5.6, -36), (5.6, 16), (-5.6, 30)):
            cyl("Lamp pole", 0.08, 7.5, (x, y, 3.75), pole, verts=10)
            cube("Lamp arm", (x - math.copysign(0.8, x), y, 7.4), (1.6, 0.12, 0.10), pole)
        bricks = [((0.42, 0.18, 0.11), 1), ((0.55, 0.45, 0.33), 2), ((0.36, 0.20, 0.15), 3), ((0.62, 0.58, 0.50), 4), ((0.30, 0.16, 0.10), 5)]
        mats = [facade(f"Facade {k}", c, s) for k, (c, s) in enumerate(bricks)]
        roof = material("Flat roof", (0.20, 0.20, 0.21), rough=0.9)
        blocks = [(1, -76, -58, 9.5), (1, -57, -41, 7.0), (1, -40, -18, 11.0), (-1, -78, -60, 8.0), (-1, -59, -37, 12.5),
                  (1, 12, 30, 8.5), (1, 31, 55, 12.0), (-1, 13, 34, 10.0), (-1, 35, 60, 7.5), (1, -110, -79, 14.0), (-1, -110, -80, 9.0)]
        for k, (sx, a, b, h) in enumerate(blocks):
            depth = 14.0
            cube(f"Building {k}", (sx * (WALK + 0.5 + depth / 2), (a + b) / 2, h / 2), (depth, b - a, h), mats[k % len(mats)])
            cube(f"Parapet {k}", (sx * (WALK + 0.5 + depth / 2), (a + b) / 2, h + 0.25), (depth + 0.2, b - a + 0.2, 0.5), roof)


# --- bridge, beam, signals ---------------------------------------------------------------------------------------------------------
class Bridge:
    def __init__(self):
        concrete = material("Abutment concrete", (0.46, 0.45, 0.42), rough=0.85)
        new_concrete = material("New concrete", (0.70, 0.69, 0.66), rough=0.8)
        steel = material("Girder steel", (0.16, 0.17, 0.18), metal=0.7, rough=0.55)
        rust = material("Girder rust", (0.24, 0.14, 0.09), metal=0.4, rough=0.75)
        ballast = material("Ballast", (0.33, 0.31, 0.29), rough=0.95)
        tie_m = material("Ties", (0.17, 0.11, 0.07), rough=0.9)
        rail_m = material("Rail", (0.40, 0.38, 0.36), metal=0.9, rough=0.35)
        grass = material("Embankment grass", (0.12, 0.20, 0.05), rough=0.95)
        self.beam_m = stripes("Crash beam stripes")
        col_m = material("Column steel", (0.20, 0.20, 0.21), metal=0.6, rough=0.5)
        z_seat = om.CLEAR_OLD + BRIDGE_GAP
        for sx in (-1, 1):                                                     # abutments and the embankment behind them
            cube(f"Abutment {sx}", (sx * (ABUT_X + 0.7), TRACK_Y, z_seat / 2), (1.4, 5.6, z_seat), concrete)
            cube(f"Wing {sx} a", (sx * (ABUT_X + 0.9), TRACK_Y - 3.0, 2.0), (1.0, 0.5, 4.0), concrete)
            cube(f"Wing {sx} b", (sx * (ABUT_X + 0.9), TRACK_Y + 3.0, 2.0), (1.0, 0.5, 4.0), concrete)
            verts, faces = [], []
            for k, (yy, zz) in enumerate(((TRACK_Y - 10.0, 0.0), (TRACK_Y - 2.6, z_seat + GIRDER_D + 0.25), (TRACK_Y + 2.6, z_seat + GIRDER_D + 0.25), (TRACK_Y + 10.0, 0.0))):
                verts += [(sx * (ABUT_X + 1.4), yy, zz), (sx * 90.0, yy, zz)]
            for k in range(3):
                faces.append((2 * k, 2 * k + 1, 2 * k + 3, 2 * k + 2) if sx > 0 else (2 * k, 2 * k + 2, 2 * k + 3, 2 * k + 1))
            emb = bpy.data.meshes.new(f"Embankment {sx}")
            emb.from_pydata(verts, [], faces)
            ob = bpy.data.objects.new(f"Embankment {sx}", emb)
            bpy.context.collection.objects.link(ob)
            emb.materials.append(grass)
            cube(f"Embankment ballast {sx}", (sx * 48.0, TRACK_Y, z_seat + GIRDER_D + 0.33), (84.0, 4.0, 0.16), ballast)
        self.lift = bpy.data.objects.new("Bridge lift", None)
        bpy.context.collection.objects.link(self.lift)
        lifted = []
        for gy in GIRDER_YS:                                                   # plate girders with stiffeners
            lifted.append(cube(f"Girder web {gy}", (0.0, gy, z_seat + GIRDER_D / 2), (2 * SPAN, 0.03, GIRDER_D), steel))
            for dz in (0.02, GIRDER_D - 0.02):
                lifted.append(cube(f"Girder flange {gy} {dz}", (0.0, gy, z_seat + dz), (2 * SPAN, 0.46, 0.04), steel))
            for m_, pick in ((rust, 0), (steel, 1)):
                lifted.append(boxes(f"Stiffeners {gy} {pick}", [((k * 1.0, gy + side * 0.11, z_seat + GIRDER_D / 2), (0.025, 0.2, GIRDER_D - 0.08))
                                                             for k in range(-7, 8) for side in (-1, 1) if (k % 3 == 0) == (pick == 0)], m_))
        lifted.append(cube("Deck", (0.0, TRACK_Y, z_seat + GIRDER_D - 0.25), (2 * SPAN, GIRDER_YS[1] - GIRDER_YS[0] - 0.1, 0.3), steel))
        lifted.append(cube("Bridge ballast", (0.0, TRACK_Y, z_seat + GIRDER_D + 0.05), (2 * SPAN, 3.2, 0.3), ballast))
        z_tie = z_seat + GIRDER_D + 0.25
        lifted.append(boxes("Ties on bridge", [((k * 0.55, TRACK_Y, z_tie), (0.22, 2.6, 0.15)) for k in range(-40, 41) if abs(k * 0.55) <= SPAN], tie_m))
        boxes("Ties", [((k * 0.55, TRACK_Y, z_tie), (0.22, 2.6, 0.15)) for k in range(-40, 41) if abs(k * 0.55) > SPAN], tie_m)
        for dy in (-0.7175, 0.7175):
            lifted.append(cube(f"Rail {dy}", (0.0, TRACK_Y + dy, z_tie + 0.15), (2 * SPAN, 0.07, 0.15), rail_m))
            for sx in (-1, 1):
                cube(f"Rail far {dy} {sx}", (sx * (SPAN + 40.0), TRACK_Y + dy, z_tie + 0.15), (80.0, 0.07, 0.15), rail_m)
        self.beam = cube("Crash beam", (0.0, 0.0, om.CLEAR_OLD + om.BEAM_D / 2), (12.6, om.BEAM_T, om.BEAM_D), self.beam_m)
        bevel(self.beam, 0.015, 1)
        lifted.append(self.beam)
        self.columns = []
        for sx in (-1, 1):
            c = cube(f"Beam column {sx}", (sx * 4.05, 0.0, om.CLEAR_OLD / 2), (0.32, 0.32, om.CLEAR_OLD), col_m)    # origin at road level: scale.z stretches it up
            self.columns.append(c)
            cube(f"Column base {sx}", (sx * 4.05, 0.0, 0.08), (0.6, 0.6, 0.16), concrete)
        parent_to(lifted, self.lift)
        self.shims = []
        for sx in (-1, 1):
            s = cube(f"Shim {sx}", (sx * (ABUT_X + 0.7), TRACK_Y, 0.0), (1.42, 5.62, om.RAISE), new_concrete)
            s.data.transform(Matrix.Translation((0.0, 0.0, om.RAISE / 2)))
            s.location.z = z_seat
            self.shims.append(s)
        ghost_m = material("Old height", (1.0, 0.10, 0.06), emission=6.0)
        self.ghost = cube("Old height line", (0.0, -om.BEAM_T / 2 - 0.02, om.CLEAR_OLD), (12.8, 0.025, 0.025), ghost_m)

    def set(self, raise_m, ghost):
        self.lift.location.z = raise_m
        for c in self.columns:
            c.scale.z = (om.CLEAR_OLD + raise_m) / om.CLEAR_OLD
        for s in self.shims:
            s.scale.z = max(1e-3, raise_m / om.RAISE)
            s.hide_render = raise_m < 1e-3
        self.ghost.hide_render = not ghost


class Signals:
    def __init__(self):
        pole = material("Signal pole", (0.16, 0.16, 0.17), metal=0.6, rough=0.45)
        housing = material("Signal housing", (0.75, 0.58, 0.08), rough=0.5)
        black = material("Back plate", (0.03, 0.03, 0.03), rough=0.6)
        px, py = 4.6, SIGNAL_XY[1]
        cyl("Signal pole", 0.14, 6.2, (px, py, 3.1), pole)
        cube("Signal arm", ((px + SIGNAL_XY[0] - 0.6) / 2, py, 5.9), (px - SIGNAL_XY[0] + 0.6, 0.14, 0.14), pole)
        cube("Signal head", (SIGNAL_XY[0], py, 5.15), (0.42, 0.30, 1.15), housing)
        cube("Signal backplate", (SIGNAL_XY[0], py + 0.17, 5.15), (0.75, 0.03, 1.45), black)
        self.lamps = {}
        for k, (name, col) in enumerate((("red", (1.0, 0.05, 0.02)), ("yellow", (1.0, 0.55, 0.02)), ("green", (0.05, 1.0, 0.35)))):
            m = material(f"Lamp {name}", col, rough=0.3, emission=0.0)
            cyl(f"Lamp {name}", 0.13, 0.04, (SIGNAL_XY[0], py - 0.16, 5.5 - 0.36 * k), m, rot=(math.pi / 2, 0, 0))
            cube(f"Visor {name}", (SIGNAL_XY[0], py - 0.27, 5.62 - 0.36 * k), (0.32, 0.22, 0.02), housing)
            self.lamps[name] = m
        sx, sy = WARN_SIGN                                                     # over-height warning: beacons and a turn arrow, no words
        cyl("Warning pole", 0.09, 4.6, (sx, sy, 2.3), pole)
        cube("Warning panel", (sx - 0.7, sy, 3.9), (2.2, 0.08, 1.3), black)
        amber = material("Beacon amber", (1.0, 0.55, 0.02), rough=0.3)
        self.beacons = []
        for k, dx in enumerate((-1.6, 0.2)):
            b = cyl(f"Beacon {k}", 0.13, 0.08, (sx - 0.7 + dx + 0.7, sy - 0.06, 4.75), amber.copy(), rot=(math.pi / 2, 0, 0))
            self.beacons.append(b.data.materials[0])
        arrow_m = material("Arrow LEDs", (1.0, 0.62, 0.05), rough=0.4)
        self.arrow_m = arrow_m
        shaft = [(-0.35, -0.38), (0.10, -0.38), (0.10, 0.10), (-0.05, 0.10), (0.20, 0.42), (0.45, 0.10), (0.30, 0.10), (0.30, -0.18), (-0.35, -0.18)]
        verts = [(sx - 0.7 + 0.9 * u, sy - 0.05, 3.9 + 0.9 * v) for u, v in shaft]
        me = bpy.data.meshes.new("Turn arrow")
        me.from_pydata(verts, [], [tuple(range(len(verts)))])
        ob = bpy.data.objects.new("Turn arrow", me)
        bpy.context.collection.objects.link(ob)
        me.materials.append(arrow_m)
        box_m = material("Detector box", (0.55, 0.56, 0.58), metal=0.5, rough=0.4)
        for dx in (-4.3, 4.3):
            cyl("Detector pole", 0.08, om.CLEAR_OLD + 0.6, (dx, om.Y_SENSOR, (om.CLEAR_OLD + 0.6) / 2), pole)
            cube("Detector head", (dx - math.copysign(0.12, dx), om.Y_SENSOR, om.CLEAR_OLD), (0.22, 0.22, 0.30), box_m)
        self.ray_m = material("Detector ray", (1.0, 0.04, 0.02), emission=12.0)
        self.ray = cyl_x("Detector ray", 0.012, 1.0, (0.0, om.Y_SENSOR, om.CLEAR_OLD), self.ray_m, verts=8)
        self.spot = cyl_x("Detector spot", 0.06, 0.01, (0, 0, -50), material("Ray spot", (1.0, 0.1, 0.05), emission=25.0))

    def set(self, st, film_t, box_front_y, visible_truck):
        sig = st["signal"]
        for name, m in self.lamps.items():
            m.node_tree.nodes.get("Principled BSDF").inputs["Emission Strength"].default_value = 18.0 if name == sig else 0.0
        on = st["warning"]
        for k, m in enumerate(self.beacons):
            lit = on and (int(film_t * 3.0) + k) % 2 == 0
            m.node_tree.nodes.get("Principled BSDF").inputs["Emission Strength"].default_value = 30.0 if lit else 0.0
        b = self.arrow_m.node_tree.nodes.get("Principled BSDF")
        b.inputs["Emission Color"].default_value = (1.0, 0.62, 0.05, 1.0)
        b.inputs["Emission Strength"].default_value = 14.0 if on else 0.0
        x0, x1 = -4.18, 4.18
        broken = visible_truck and box_front_y >= om.Y_SENSOR and box_front_y - om.BOX_L <= om.Y_SENSOR
        if broken:
            x0 = om.X_LANE + W_IN + 0.01                                        # the box stops the ray at its right wall
            self.spot.location = (x0, om.Y_SENSOR, om.CLEAR_OLD)
        else:
            self.spot.location = (0, 0, -50)
        self.ray.location = ((x0 + x1) / 2, om.Y_SENSOR, om.CLEAR_OLD)
        self.ray.scale = (x1 - x0, 1.0, 1.0)
        return broken


class Train:
    def __init__(self):
        stripe_m = material("Loco stripe", (0.85, 0.85, 0.82), rough=0.5)
        car_m = material("Boxcar paint", (0.36, 0.13, 0.07), rough=0.7)
        under = material("Bogies", (0.05, 0.05, 0.05), rough=0.6)
        glass = material("Loco glass", (0.05, 0.07, 0.09), metal=0.5, rough=0.1)
        self.root = bpy.data.objects.new("Train", None)
        bpy.context.collection.objects.link(self.root)
        obs = []
        z0 = om.CLEAR_OLD + BRIDGE_GAP + GIRDER_D + 0.25 + 0.30
        x = 0.0
        hood_m = material("Loco hood", (0.10, 0.16, 0.30), rough=0.45)
        rail_c = material("Loco handrail", (0.85, 0.85, 0.82), metal=0.6, rough=0.4)
        lamp = material("Loco headlight", (1.0, 0.95, 0.8), emission=25.0)
        obs.append(cube("Loco deck", (x, TRACK_Y, z0 + 1.25), (21.0, 3.1, 0.30), under))
        obs.append(bevel(cube("Loco hood", (x + 1.6, TRACK_Y, z0 + 2.7), (15.0, 2.3, 2.6), hood_m), 0.08, 2))
        obs.append(bevel(cube("Loco cab", (x - 7.4, TRACK_Y, z0 + 2.95), (3.6, 3.0, 3.1), hood_m), 0.10, 2))
        obs.append(bevel(cube("Loco nose", (x - 9.8, TRACK_Y, z0 + 2.0), (1.6, 2.6, 1.2), hood_m), 0.08, 2))
        obs.append(cube("Loco windows", (x - 9.25, TRACK_Y, z0 + 3.8), (0.05, 2.6, 0.8), glass))
        obs.append(cube("Loco side windows", (x - 7.4, TRACK_Y, z0 + 3.8), (2.4, 3.02, 0.7), glass))
        obs.append(cube("Loco stripe", (x + 1.6, TRACK_Y, z0 + 1.65), (15.2, 2.34, 0.22), stripe_m))
        obs.append(cube("Loco fuel tank", (x, TRACK_Y, z0 + 0.85), (6.0, 2.4, 0.6), under))
        obs.append(cube("Loco headlight", (x - 10.62, TRACK_Y, z0 + 2.3), (0.04, 0.5, 0.18), lamp))
        obs.append(boxes("Loco handrails", [((x, TRACK_Y + sy * 1.5, z0 + 2.15), (20.5, 0.04, 0.04)) for sy in (-1, 1)], rail_c))
        for bx in (-6.5, 6.5):
            obs.append(cube("Loco truck", (x + bx, TRACK_Y, z0 + 0.55), (4.2, 2.6, 0.7), under))
        wheel_m = material("Train wheels", (0.10, 0.09, 0.09), metal=0.7, rough=0.4)
        door_m = material("Boxcar door", (0.30, 0.11, 0.06), rough=0.7)
        wheels = [(0.5, 0.12, (x + bx + wx, TRACK_Y + sy * 0.72, z0 + 0.45), (math.pi / 2, 0, 0)) for bx in (-6.5, 6.5) for wx in (-1.4, 0.0, 1.4) for sy in (-1, 1)]
        ribs = []
        x += 21.0
        for k in range(4):
            obs.append(bevel(cube(f"Boxcar {k}", (x + 9.0, TRACK_Y, z0 + 2.5), (17.5, 3.0, 3.4), car_m), 0.06, 1))
            obs.append(cube(f"Boxcar underframe {k}", (x + 9.0, TRACK_Y, z0 + 0.72), (17.0, 2.4, 0.25), under))
            for side in (-1, 1):
                ribs.append(((x + 9.0, TRACK_Y + side * 1.52, z0 + 2.3), (3.2, 0.04, 2.9)))
                ribs += [((x + 9.0 + rib * 1.15, TRACK_Y + side * 1.51, z0 + 2.5), (0.07, 0.03, 3.3)) for rib in range(-7, 8)]
            for bx in (-6.0, 6.0):
                obs.append(cube(f"Boxcar bogie {k}", (x + 9.0 + bx, TRACK_Y, z0 + 0.45), (2.8, 2.2, 0.5), under))
                wheels += [(0.42, 0.10, (x + 9.0 + bx + wx, TRACK_Y + sy * 0.72, z0 + 0.42), (math.pi / 2, 0, 0)) for wx in (-0.9, 0.9) for sy in (-1, 1)]
            x += 18.5
        obs.append(boxes("Boxcar doors and ribs", ribs, door_m))
        obs.append(cyls("Train wheels", wheels, wheel_m))
        parent_to(obs, self.root)

    def set(self, visible, x, lift):
        self.root.location = (x, 0.0, lift)
        for c in self.root.children:
            c.hide_render = not visible


# --- the box truck ---------------------------------------------------------------------------------------------------------------
class Truck:
    def __init__(self):
        self.root = bpy.data.objects.new("Truck root", None)
        bpy.context.collection.objects.link(self.root)
        R = self.root
        white = material("Cab white", (0.86, 0.86, 0.84), rough=0.32)
        dark = material("Truck black", (0.04, 0.04, 0.045), rough=0.55)
        chrome = material("Chrome", (0.85, 0.86, 0.88), metal=1.0, rough=0.12)
        glass = material("Truck glass", (0.06, 0.08, 0.10), metal=0.4, rough=0.06)
        tyre = material("Truck tyre", (0.03, 0.03, 0.035), rough=0.85)
        rim = material("Truck rim", (0.62, 0.63, 0.65), metal=0.9, rough=0.3)
        self.head_m = material("Headlamp", (1.0, 0.95, 0.85), rough=0.2, emission=2.0)
        self.tail_m = material("Tail lamp", (0.9, 0.03, 0.02), rough=0.3, emission=1.0)
        marker = material("Marker amber", (1.0, 0.5, 0.05), rough=0.3, emission=3.0)
        cf = om.CAB_FRONT
        parts = [
            bevel(cube("Cab", (0.0, 0.95, 1.92), (2.30, 1.55, 1.66), white), 0.08, 3),
            bevel(cube("Cab roof", (0.0, 0.92, 2.83), (2.18, 1.45, 0.22), white), 0.08, 3),
            bevel(cube("Hood", (0.0, 2.05, 1.38), (2.05, 0.95, 0.95), white), 0.10, 3),
            cube("Windshield", (0.0, 1.73, 2.20), (2.06, 0.03, 0.80), glass),
            cube("Side window L", (-1.16, 0.95, 2.25), (0.02, 1.10, 0.62), glass),
            cube("Side window R", (1.16, 0.95, 2.25), (0.02, 1.10, 0.62), glass),
            cube("Grille", (0.0, cf - 0.02, 1.30), (1.15, 0.04, 0.70), dark),
            bevel(cube("Bumper", (0.0, cf, 0.70), (2.30, 0.16, 0.28), chrome), 0.03, 2),
            cube("Headlamp L", (-0.82, cf - 0.03, 1.32), (0.32, 0.04, 0.20), self.head_m),
            cube("Headlamp R", (0.82, cf - 0.03, 1.32), (0.32, 0.04, 0.20), self.head_m),
            cube("Fuel tank", (-1.0, -0.35, 0.82), (0.45, 1.25, 0.45), chrome),
            cube("Step", (1.12, 0.55, 0.62), (0.18, 0.55, 0.06), dark),
            cube("Frame L", (-0.43, -2.0, 0.85), (0.10, 8.6, 0.25), dark),
            cube("Frame R", (0.43, -2.0, 0.85), (0.10, 8.6, 0.25), dark),
            cube("Box sill", (0.0, -om.BOX_L / 2, om.BOX_FLOOR - 0.07), (om.BOX_W + 0.04, om.BOX_L, 0.14), dark),
            cube("Rear bar", (0.0, -om.BOX_L - 0.05, 0.62), (2.1, 0.12, 0.12), chrome),
            cube("Tail L", (-1.05, -om.BOX_L - 0.03, 1.32), (0.18, 0.04, 0.12), self.tail_m),
            cube("Tail R", (1.05, -om.BOX_L - 0.03, 1.32), (0.18, 0.04, 0.12), self.tail_m),
        ]
        for sx in (-1, 1):
            arm = cube(f"Mirror arm {sx}", (sx * 1.28, 1.55, 2.15), (0.30, 0.04, 0.04), dark)
            mir = bevel(cube(f"Mirror {sx}", (sx * 1.42, 1.50, 2.05), (0.07, 0.20, 0.42), dark), 0.02, 1)
            parts += [arm, mir]
            parts.append(cube(f"Fender {sx}", (sx * 1.0, 1.95, 1.02), (0.36, 1.25, 0.10), dark))
        for k in range(5):
            parts.append(cube(f"Cab marker {k}", (-0.6 + 0.3 * k, 1.55, 2.97), (0.12, 0.06, 0.05), marker))
        self.wheels = []
        for wy, dual in ((1.95, False), (-4.45, True)):
            for sx in (-1, 1):
                for k in ((0, 1) if dual else (0,)):
                    x = sx * (1.0 - 0.30 * k) if dual else sx * 1.02
                    t = cyl_x(f"Tyre {wy} {sx} {k}", 0.50, 0.28, (x, wy, 0.50), tyre, verts=28)
                    r = cyl_x(f"Rim {wy} {sx} {k}", 0.30, 0.29, (x, wy, 0.50), rim, verts=8)
                    parts += [t, r]
                    self.wheels.append((t, r))
        parent_to(parts, R)
        # --- the box: panels that deform -------------------------------------------------------------------------------------------
        self.wall_m = box_paint("Box wall", (0.93, 0.93, 0.92), 0.35, stripe=True)
        self.liner_m = material("Box liner", (0.50, 0.38, 0.24), rough=0.85)
        self.skin_m = box_paint("Roof skin", (0.78, 0.79, 0.81), 0.30, alpha_node=True)
        self.rail_m = box_paint("Top rail", (0.70, 0.71, 0.73), 0.28)
        self.bow_m = material("Roof bow", (0.66, 0.67, 0.69), metal=0.9, rough=0.35)
        rows = sorted(set([om.BOX_FLOOR, 1.6, 2.1, 2.6, 3.0, 3.25, 3.40] + [round(v, 4) for v in np.arange(3.46, om.TRUCK_H, 0.02)]
                          + [round(om.CLEAR_OLD, 4), round(om.CLEAR_NEW, 4), round(om.TRUCK_H, 4)]))
        rows = [r for k, r in enumerate(rows) if k == 0 or r - rows[k - 1] > 0.004]
        self.rows = np.array(rows)
        ys = np.linspace(0.0, -om.BOX_L, NY)
        self.walls = []
        for sx in (-1, 1):
            co = np.array([(sx * W_IN, y, z) for y in ys for z in rows])
            uv = np.array([(-y, z) for y in ys for z in rows])
            faces = grid_faces(NY, len(rows))
            if sx > 0:                                                         # normals out of the box: paint outside, liner inside
                faces = [tuple(reversed(f)) for f in faces]
            w = Sheet(f"Box wall {sx}", co, faces, [self.wall_m, self.liner_m], uv=uv, thickness=0.025, parent=R, offset=-1.0)
            w.sx = sx
            self.walls.append(w)
        xs = np.linspace(-W_IN, W_IN, 25)
        co = np.array([(x, 0.0, z) for x in xs for z in rows])
        self.front = Sheet("Box front", co, [tuple(reversed(f)) for f in grid_faces(len(xs), len(rows))], [self.wall_m, self.liner_m],
                           uv=np.array([(x, z) for x in xs for z in rows]), thickness=0.03, parent=R, offset=-1.0)
        self.skin_x = np.linspace(-W_IN + 0.03, W_IN - 0.03, 25)
        self.skin_s = np.linspace(0.0, om.BOX_L, NY)
        co = np.array([(x, -s, om.TRUCK_H) for s in self.skin_s for x in self.skin_x])
        self.skin = Sheet("Roof skin", co, grid_faces(NY, len(self.skin_x)), [self.skin_m], uv=np.array([(s, x) for s in self.skin_s for x in self.skin_x]),
                          thickness=0.004, parent=R)
        cube("Rear door", (0.0, -om.BOX_L, (om.BOX_FLOOR + om.TRUCK_H) / 2), (om.BOX_W, 0.05, om.TRUCK_H - om.BOX_FLOOR), self.wall_m).parent = R
        for k in range(8):
            cube(f"Door rib {k}", (0.0, -om.BOX_L - 0.03, om.BOX_FLOOR + 0.35 * (k + 1)), (om.BOX_W - 0.1, 0.02, 0.025), self.rail_m).parent = R
        for sx in (-1, 1):
            cube(f"Rear post {sx}", (sx * (W_IN + 0.01), -om.BOX_L + 0.04, (om.BOX_FLOOR + om.TRUCK_H) / 2), (0.08, 0.10, om.TRUCK_H - om.BOX_FLOOR), self.rail_m).parent = R
        self.rails = []
        prof = [(-0.025, -0.07), (0.025, -0.07), (0.025, 0.0), (-0.025, 0.0)]
        for sx in (-1, 1):
            co, faces = [], []
            for i, y in enumerate(ys):
                for (dx, dz) in prof:
                    co.append((sx * W_IN + dx, y, om.TRUCK_H + dz))
            for i in range(NY - 1):
                for k in range(4):
                    a, b = i * 4 + k, i * 4 + (k + 1) % 4
                    faces.append((a, b, b + 4, a + 4))
            uv = np.array([(-c[1], c[2]) for c in co])
            self.rails.append(Sheet(f"Top rail {sx}", co, faces, [self.rail_m], uv=uv, parent=R, smooth=False))
        self.bow_s = om.bows()
        co, faces = [], []
        bx = np.linspace(-W_IN + 0.02, W_IN - 0.02, 13)
        for k, s in enumerate(self.bow_s):
            off = len(co)
            for x in bx:
                for (dy, dz) in ((-0.022, -0.06), (0.022, -0.06), (0.022, -0.025), (-0.022, -0.025)):
                    co.append((x, -s + dy, om.TRUCK_H + dz))
            for i in range(len(bx) - 1):
                for q in range(4):
                    a, b = off + i * 4 + q, off + i * 4 + (q + 1) % 4
                    faces.append((a, b, b + 4, a + 4))
        self.bows = Sheet("Roof bows", co, faces, [self.bow_m], parent=R, smooth=False)
        self.bow_nx = len(bx)
        rv = []
        for k in range(6):
            a = 2 * math.pi * k / 6
            rv += [(0.011 * math.cos(a), 0.011 * math.sin(a), 0.0), (0.008 * math.cos(a), 0.008 * math.sin(a), 0.007)]
        rf = [(2 * k, 2 * ((k + 1) % 6), 2 * ((k + 1) % 6) + 1, 2 * k + 1) for k in range(6)] + [tuple(2 * k + 1 for k in range(6))]
        self.rivet_s = om.rivets()
        self.rivets = pieces_mesh("Rivets", rv, rf, 2 * len(self.rivet_s), self.rail_m, parent=R)
        cargo_m = material("Cardboard", (0.55, 0.38, 0.20), rough=0.9)
        rng = random.Random(7)
        for k in range(16):
            w = rng.uniform(0.45, 0.7)
            h = rng.uniform(0.4, 0.6)
            cube(f"Moving box {k}", (rng.uniform(-0.8, 0.8), -0.5 - rng.uniform(0.0, 4.5), om.BOX_FLOOR + h / 2 + (k % 3) * 0.45), (w, w, h), cargo_m).parent = R
        self.state = None

    # --- deformation ---------------------------------------------------------------------------------------------------------------
    def wall_fold(self, sx, y, z, p, h_cut, on):
        """Side-wall points (and anything fixed to the wall top) above the clearance fold outward about the clearance line once the beam
        has reached them; the fold finishes before the beam passes over (q = 0)."""
        h = np.maximum(z - h_cut, 0.0)
        q = y + p
        a = A_FLAP * sstep(-0.24, 0.0, q) * on
        a = np.where(z > h_cut, a, 0.0)
        n = 0.035 * crumple(y, h, 1.3 * sx) * sstep(0.0, 0.25, q) * on * (h > 0)
        x = sx * W_IN + sx * h * np.sin(a) + sx * np.cos(a) * n
        zz = np.where(z > h_cut, h_cut + h * np.cos(a) - np.sin(a) * n, z)
        return x, zz

    def curl(self, p, n=500):
        """Path of the peeled skin from the peel front (u = 0, at the beam face) to its free end (u = p, the innermost turn): a rise up
        the beam face and above it, then a curl back over the roof whose radius grows with the length of sheet already wound inside it,
        like a sardine-can lid."""
        h1 = min(0.5 * p, 0.40 + 0.15 * p)                                    # forced up the beam face, then free above it
        th0 = math.radians(95.0 + 12.0 * float(sstep(0.0, 4.0, p)))
        us = np.linspace(0.0, max(p, 1e-6), n)
        kap = np.where(us < h1, 0.0, 1.0 / (R_MIN + C_CURL * np.sqrt(np.maximum(p - us, 0.0))))
        th = th0 + np.concatenate([[0.0], np.cumsum(0.5 * (kap[1:] + kap[:-1]) * np.diff(us))])
        y = -p + np.concatenate([[0.0], np.cumsum(0.5 * (np.cos(th[1:]) + np.cos(th[:-1])) * np.diff(us))])
        z = om.TRUCK_H + np.concatenate([[0.0], np.cumsum(0.5 * (np.sin(th[1:]) + np.sin(th[:-1])) * np.diff(us))])
        return us, y, z, th

    def set(self, st, flags):
        p, h_cut = st["peel"], st["clearance"]
        crash = st["variant"] in ("old", "raised")
        on = float(sstep(0.0, 0.08, p)) if crash else 0.0
        for w in self.walls:
            x, z = self.wall_fold(w.sx, w.base[:, 1], w.base[:, 2], p, h_cut, on)
            w.set(np.stack([x, w.base[:, 1], z], 1))
        fb = self.front.base
        h = np.maximum(fb[:, 2] - h_cut, 0.0)
        beta = B_FOLD * float(sstep(0.0, 0.08, p)) * on
        nz = 0.03 * crumple(fb[:, 0], h, 4.0) * on * (h > 0)
        fy = np.where(fb[:, 2] > h_cut, -h * math.sin(beta) + math.cos(beta) * nz, 0.0)
        fz = np.where(fb[:, 2] > h_cut, h_cut + h * math.cos(beta) + math.sin(beta) * nz, fb[:, 2])
        self.front.set(np.stack([fb[:, 0], fy, fz], 1))
        for k, r in enumerate(self.rails):
            sx = -1 if k == 0 else 1
            b = r.base
            x, z = self.wall_fold(sx, b[:, 1], b[:, 2], p, h_cut, on)
            r.set(np.stack([x + (b[:, 0] - sx * W_IN), b[:, 1], z], 1))
        # roof skin
        S, X = np.meshgrid(self.skin_s, self.skin_x, indexing="ij")
        S, X = S.ravel(), X.ravel()
        y, z = -S, np.full_like(S, om.TRUCK_H)
        if crash and p > 1e-4:
            us, cy, cz, cth = self.curl(p)
            det = S < p
            u = p - S[det]
            yy, zz, th = np.interp(u, us, cy), np.interp(u, us, cz), np.interp(u, us, cth)
            amp = (0.05 * crumple(X[det], S[det], 2.0) + 0.09 * (2 * X[det] / om.BOX_W) ** 2) * sstep(0.0, 0.35, u)
            yy, zz = yy - np.sin(th) * amp, zz + np.cos(th) * amp
            zz = np.maximum(zz, om.TRUCK_H + 0.012)
            yy = np.minimum(yy, -p - 0.006)
            y[det], z[det] = yy, zz
            att = ~det
            z[att] = om.TRUCK_H + 0.035 * (1.0 - sstep(0.0, 0.25, S[att] - p)) * on
        self.skin.set(np.stack([X, y, z], 1))
        # bows
        co = self.bows.base.copy()
        per = self.bow_nx * 4
        for k, s in enumerate(self.bow_s):
            b = float(sstep(s - 0.12, s + 0.04, p)) if crash else 0.0
            if b <= 0:
                continue
            sl = slice(k * per, (k + 1) * per)
            xn = co[sl, 0] / W_IN
            co[sl, 2] -= b * (0.45 + 0.20 * (1 - xn ** 2) + 0.05 * np.sin(7 * xn + k))
            co[sl, 1] -= b * 0.14 * (1 - xn ** 2)
            co[sl, 0] *= 1 - 0.07 * b
        self.bows.set(co)
        # rivets: on the rails until the peel front reaches them
        n = len(self.rivet_s)
        pos = np.zeros((2 * n, 3))
        for k, sx in enumerate((-1, 1)):
            ss = np.array(self.rivet_s)
            yy = -ss
            x, zz = self.wall_fold(sx, yy, np.full(n, om.TRUCK_H + 0.001), p, h_cut, on)
            pos[k * n:(k + 1) * n] = np.stack([x - sx * 0.012, yy, zz], 1)
            if crash:
                pos[k * n:(k + 1) * n][ss < p] = (0.0, 0.0, -50.0)
        set_pieces(self.rivets, pos)
        # paint: x-ray roof, glowing band, brake and tail lights
        set_node(self.skin_m, "alpha", 0.22 if flags.get("xray") else 1.0)
        for m in (self.wall_m, self.skin_m, self.rail_m):
            set_node(m, "band", 12.0 if flags.get("band") else 0.0)
            set_node(m, "h_cut", h_cut)
        self.tail_m.node_tree.nodes.get("Principled BSDF").inputs["Emission Strength"].default_value = 14.0 if st["braking"] else 1.2

    def place(self, x, y, dist):
        self.root.location = (x, y, 0.0)
        for t, r in self.wheels:
            for o in (t, r):
                o.rotation_euler = (dist / 0.5, 0.0, 0.0)


# --- flying things (world frame) -------------------------------------------------------------------------------------------------------
class Flyers:
    """Rivets torn out of the rails, aluminium shards and paint chips, and sparks, all launched from the peel front at the
    model's times (rivet pops, bow buckles, the first contact) and flown ballistically; shards come to rest on the road."""
    G = 9.81

    def __init__(self, rivet_mesh_proto, rail_m):
        rng = np.random.default_rng(20)
        self.rivet_s = om.rivets()
        n = 2 * len(self.rivet_s)
        rv, rf = rivet_mesh_proto
        self.rivets = pieces_mesh("Flying rivets", rv, rf, n, rail_m)
        self.r_side = np.array([-1] * len(self.rivet_s) + [1] * len(self.rivet_s))
        self.r_s = np.array(self.rivet_s * 2)
        self.r_v = np.stack([self.r_side * rng.uniform(0.6, 2.4, n), rng.uniform(-2.8, -0.6, n), rng.uniform(1.2, 3.6, n)], 1)
        self.r_w = rng.uniform(-30, 30, (n, 3))
        shard_m = material("Shard aluminium", (0.80, 0.81, 0.83), metal=0.9, rough=0.3)
        tri = [(-0.05, -0.03, 0.0), (0.06, -0.025, 0.0), (0.0, 0.05, 0.0)]
        self.n_sh = 150
        self.shards = pieces_mesh("Shards", tri, [(0, 1, 2)], self.n_sh, shard_m)
        ev = [(0.0, 60)] + [(s, 9) for s in om.bows()]
        self.sh_src, k = [], 0
        for s, cnt in ev:
            for _ in range(cnt):
                if k < self.n_sh:
                    self.sh_src.append(s)
                    k += 1
        while len(self.sh_src) < self.n_sh:
            self.sh_src.append(1e9)
        self.sh_src = np.array(self.sh_src)
        self.sh_x = rng.uniform(-W_IN, W_IN, self.n_sh)
        self.sh_z = rng.uniform(0.0, 1.0, self.n_sh)
        self.sh_v = np.stack([np.sign(self.sh_x) * rng.uniform(0.3, 2.8, self.n_sh), rng.uniform(-2.5, 3.0, self.n_sh), rng.uniform(1.0, 4.5, self.n_sh)], 1)
        self.sh_w = rng.uniform(-25, 25, (self.n_sh, 3))
        self.sh_scale = rng.uniform(0.8, 3.2, self.n_sh)
        spark_m = material("Spark", (1.0, 0.55, 0.15), emission=40.0)
        streak = [(-0.007, 0.0, 0.0), (0.007, 0.0, 0.0), (0.007, 1.0, 0.0), (-0.007, 1.0, 0.0)]
        self.n_sp = 110
        self.sparks = pieces_mesh("Sparks", streak, [(0, 1, 2, 3)], self.n_sp, spark_m)
        sp_ev = [(0.0, 50)] + [(s, 6) for s in om.bows()]
        src = []
        for s, cnt in sp_ev:
            src += [s] * cnt
        src = (src + [1e9] * self.n_sp)[:self.n_sp]
        self.sp_src = np.array(src)
        self.sp_x = rng.uniform(-W_IN, W_IN, self.n_sp)
        self.sp_v = np.stack([rng.uniform(-3.5, 3.5, self.n_sp), rng.uniform(-4.0, 2.0, self.n_sp), rng.uniform(0.5, 4.5, self.n_sp)], 1)
        self.sp_life = rng.uniform(0.25, 0.7, self.n_sp)

    def _launch(self, s_src, variant):
        """Time each piece leaves the peel front (None if the peel never gets there)."""
        out = np.full(len(s_src), np.nan)
        for i, s in enumerate(s_src):
            if s > 1e8:
                continue
            tp = 0.0 if s <= 0 else om.pop_time(float(s), variant)
            if tp is not None:
                out[i] = tp
        return out

    def set(self, t, variant, h_cut):
        crash = variant in ("old", "raised")
        res = {"rivets_flying": 0, "shards_airborne": 0, "sparks": 0}
        if not crash:
            for s in (self.rivets, self.shards, self.sparks):
                set_pieces(s, np.tile([0.0, 0.0, -50.0], (s.n, 1)))
            return res
        key = (variant,)
        if getattr(self, "_key", None) != key:
            self._key = key
            self.r_t = self._launch(self.r_s, variant)
            self.sh_t = self._launch(self.sh_src, variant)
            self.sp_t = self._launch(self.sp_src, variant)
        x_face = om.FACE_Y
        # rivets
        n = len(self.r_s)
        pos = np.tile([0.0, 0.0, -50.0], (n, 1))
        rot = np.repeat(np.eye(3)[None], n, 0)
        tau = t - self.r_t
        fly = np.isfinite(self.r_t) & (tau >= 0)
        if fly.any():
            p0 = np.stack([om.X_LANE + self.r_side * (W_IN - 0.012), np.full(n, x_face - 0.03), np.full(n, om.TRUCK_H)], 1)
            tt = np.where(fly, tau, 0.0)
            pp = p0 + self.r_v * tt[:, None] + np.array([0, 0, -0.5 * self.G])[None] * (tt ** 2)[:, None]
            land = pp[:, 2] < 0.01
            pp[:, 2] = np.maximum(pp[:, 2], 0.01)
            pos[fly] = pp[fly]
            ang = self.r_w * np.minimum(tt, 1.2)[:, None]
            rot[fly] = rot_xyz(ang[fly, 0], ang[fly, 1], ang[fly, 2])
            res["rivets_flying"] = int((fly & ~land).sum())
        set_pieces(self.rivets, pos, rot, np.full(n, 2.0))
        # shards
        n = self.n_sh
        pos = np.tile([0.0, 0.0, -50.0], (n, 1))
        rot = np.repeat(np.eye(3)[None], n, 0)
        tau = t - self.sh_t
        fly = np.isfinite(self.sh_t) & (tau >= 0)
        if fly.any():
            band = om.TRUCK_H - h_cut
            p0 = np.stack([om.X_LANE + self.sh_x, np.full(n, x_face - 0.05), om.TRUCK_H - self.sh_z * band], 1)
            tt = np.where(fly, tau, 0.0)
            pp = p0 + self.sh_v * tt[:, None] + np.array([0, 0, -0.5 * self.G])[None] * (tt ** 2)[:, None]
            t_land = (self.sh_v[:, 2] + np.sqrt(self.sh_v[:, 2] ** 2 + 2 * self.G * p0[:, 2])) / self.G
            landed = tt >= t_land
            pl = p0 + self.sh_v * t_land[:, None] + np.array([0, 0, -0.5 * self.G])[None] * (t_land ** 2)[:, None]
            pp[landed] = pl[landed]
            pp[landed, 2] = 0.004
            pos[fly] = pp[fly]
            ang = self.sh_w * np.minimum(tt, t_land)[:, None]
            r = rot_xyz(ang[:, 0], ang[:, 1], ang[:, 2])
            flat = rot_xyz(np.zeros(n), np.zeros(n), ang[:, 2])
            r[landed] = flat[landed]
            rot[fly] = r[fly]
            res["shards_airborne"] = int((fly & ~landed).sum())
        set_pieces(self.shards, pos, rot, self.sh_scale)
        # sparks: thin streaks along their velocity, short-lived
        n = self.n_sp
        pos = np.tile([0.0, 0.0, -50.0], (n, 1))
        rot = np.repeat(np.eye(3)[None], n, 0)
        scale = np.ones(n)
        tau = t - self.sp_t
        live = np.isfinite(self.sp_t) & (tau >= 0) & (tau < self.sp_life)
        if live.any():
            p0 = np.stack([om.X_LANE + self.sp_x, np.full(n, x_face - 0.02), np.full(n, h_cut + 0.02)], 1)
            tt = np.where(live, tau, 0.0)
            v = self.sp_v + np.array([0, 0, -self.G])[None] * tt[:, None]
            pp = p0 + self.sp_v * tt[:, None] + np.array([0, 0, -0.5 * self.G])[None] * (tt ** 2)[:, None]
            yaw = np.arctan2(-v[:, 0], v[:, 1])
            pitch = np.arctan2(v[:, 2], np.hypot(v[:, 0], v[:, 1]))
            r = rot_xyz(pitch, np.zeros(n), yaw)
            pos[live] = pp[live]
            rot[live] = r[live]
            scale = np.clip(np.linalg.norm(v, axis=1) * 0.06, 0.05, 0.30)
            res["sparks"] = int(live.sum())
        set_pieces(self.sparks, pos, rot, scale)
        return res


def main():
    args = arguments()
    args.out.mkdir(parents=True, exist_ok=True)
    car_root, body, car_wheels, geom = base.load_source_car(args.source)
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
    sun_to = cinematic.sun_vector((-0.42, -0.90), 18.0)
    cinematic.apply_sky(scene, sun_to, strength=0.24, dust=0.7)
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    sun.data.energy, sun.data.angle = 6.0, 0.02
    sun.data.color = (1.0, 0.76, 0.52)
    sun.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()
    Street()
    bridge = Bridge()
    signals = Signals()
    train = Train()
    truck = Truck()
    rv = []
    for k in range(6):
        a = 2 * math.pi * k / 6
        rv += [(0.011 * math.cos(a), 0.011 * math.sin(a), 0.0), (0.008 * math.cos(a), 0.008 * math.sin(a), 0.007)]
    rf = [(2 * k, 2 * ((k + 1) % 6), 2 * ((k + 1) % 6) + 1, 2 * k + 1) for k in range(6)] + [tuple(2 * k + 1 for k in range(6))]
    flyers = Flyers((rv, rf), truck.rail_m)
    wheel_nodes = {w["node"] for w in car_wheels.values()}
    parts = [o for o in car_root.children_recursive if o.type == "MESH" and not any(p in wheel_nodes for p in rb._ancestors(o))]
    ghost = rb.Ghost(parts)
    ghost.set_tint(PAINT)
    ghost.set_factor(0.0, 1e4, 4.0)
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam

    def render(sh, path):
        scene.render.resolution_x, scene.render.resolution_y = round(FRAME[0] * args.res_scale), round(FRAME[1] * args.res_scale)
        t, variant, film_t = sh["t"], sh["variant"], sh["film_t"]
        st = om.state(t, variant)
        raise_m = om.RAISE if variant == "raised" else (om.RAISE * min(1.0, max(0.0, t)) if variant == "raising" else 0.0)
        bridge.set(raise_m, bool(sh.get("ghost")))
        show_truck = variant != "raising"
        for o in [truck.root, *truck.root.children_recursive]:
            o.hide_render = not show_truck
        y_front = st["y"]
        dist = om.travel(t, variant) if variant != "warned" else om.warned_y(t) - om.Y_SENSOR
        truck.place(om.X_LANE, y_front if show_truck else -300.0, dist)
        truck.set(st, sh)
        fl = flyers.set(t, variant, st["clearance"])
        broken = signals.set(st, film_t, y_front, show_truck)
        train_x = 26.0 - 9.0 * (t + 3.4) if sh.get("train") else 300.0          # nose first toward -x, onto the bridge during the shot
        train.set(bool(sh.get("train")), train_x, raise_m)
        if sh.get("sedan"):
            car_y = 24.0 - 9.0 * (t + 3.4)
            car_root.location = (-1.8, car_y, 0.0)
            car_root.rotation_euler = (0.0, 0.0, math.pi)
            for wh in car_wheels.values():
                wh["node"].rotation_mode = "ZXY"
                wh["node"].rotation_euler = (-(t + 3.4) * 9.0 / geom["tyre_radius"], 0, 0)
        else:
            car_y = -400.0
            car_root.location = (-1.8, car_y, 0.0)
        c = sh["cam"]
        o = Vector((0.0, 0.0, 0.0))
        if c["rel"] == "truck":
            o = Vector((om.X_LANE, y_front, 0.0))
        loc, tgt = o + Vector(c["loc"]), o + Vector(c["target"])
        dd = cam.data
        dd.sensor_fit, dd.sensor_width, dd.lens, dd.clip_start = "HORIZONTAL", 36.0, c["lens"], 0.02
        dd.clip_end = 900.0
        dd.dof.use_dof = True
        dd.dof.focus_distance = (tgt - loc).length
        dd.dof.aperture_fstop = c.get("fstop", 8.0)
        base.set_camera(cam, loc, tgt)
        bpy.context.view_layer.update()
        box = hook_gate.project_box(scene, cam, truck.root.matrix_world, (-1.25, -om.BOX_L - 0.1, 0.0), (1.25, om.CAB_FRONT, om.TRUCK_H)) if show_truck else None
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        return {"variant": variant, "t": round(t, 6), "box_front_y": round(y_front, 4), "peel": round(st["peel"], 4), "bows": st["bows"],
                "rivets": st["rivets"], "clearance": round(st["clearance"], 4), "raise_m": round(raise_m, 4), "signal": st["signal"],
                "warning": st["warning"], "braking": st["braking"], "detector_broken": broken, "train_x": round(train_x, 3), "sedan_y": round(car_y, 3),
                "subject_box": box, "xray": bool(sh.get("xray")), "band": bool(sh.get("band")), **fl,
                "cam_world": [round(v, 3) for v in loc], "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

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
        print("OPENER_FRAME " + json.dumps(info), flush=True)
    (args.out / f"opener-frames-{frames[0]:05d}.json").write_text(json.dumps({"renderer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                                                             "frames": out}, indent=1))


if __name__ == "__main__":
    main()
