"""EP.23 exploding manhole covers: 100 % 3D renderer (Blender, Cycles CPU), house style of EP.13-EP.22 (low sun, depth of field).
A city street on a winter evening: brick blocks with lit windows, snowbanks along the curbs, slush on the asphalt, a parked red sedan,
street lights on. In the right-hand lane a 30 in cast-iron cover sits in its frame; a vented cover lies in the next lane. Under the
first one a concrete electrical vault: power cables on steel racks along both long walls between duct banks at the ends, a splice in
the middle of the east wall, a salty puddle on the floor. Section shots show the street cut open along the vault (asphalt, gravel base
and soil in layers, a water main and phone ducts in the cut).

Everything moves from manhole_motion: meltwater drops falling from the ceiling onto the cables, salt on the cables, char and embers on
the splice, arcs (when and how bright from the model's arc schedule), the gas haze filling the vault (its density from the gas share),
the spark, the flame front burning through the vault (from the burned share), fire and smoke pushed out of the hole (from the outflow
and fireball), the cover's flight (height, drift, one turn over, the landing and its coin-like wobble), sparks and slush thrown up,
smoke pouring out afterwards; a vented cover breathing smoke out of its holes; a latched cover popping up 3.5 in and dropping back.
No text anywhere in the scene."""
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
from benchmarks.manhole_blast import manhole_motion as mm  # noqa: E402
from benchmarks.manhole_blast import manhole_timeline as tl  # noqa: E402
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402
from benchmarks.rock_net.render_rocknet_3d import Tube, cone_geom, merged, textured  # noqa: E402

material = base.material
cube, boxes, cyl, cyl_geom, new_object = K.cube, K.boxes, K.cyl, K.cyl_geom, K.new_object
pieces_mesh, set_pieces, rot_xyz = K.pieces_mesh, K.set_pieces, K.rot_xyz
FRAME = (1080, 1920)
ROAD_HALF, WALK = 6.0, 9.5
X_FAR, Y_FAR, Z_BOT = 26.0, 70.0, -6.0
MX, MY = mm.MX, mm.MY
IX, IY = mm.VAULT_W / 2, mm.VAULT_L / 2
WALL = 0.2
ZC, ZF = mm.Z_CEIL, mm.Z_FLOOR
Z_ROOF = ZC + WALL
RN, RN_OUT, RF = mm.R_NECK, 0.52, 0.56
RC, TC = mm.R_COVER, mm.T_COVER
CABLE_R = 0.055
CABLE_Z = (-1.235, -1.55, -1.865, -2.18)
CABLE_X = mm.SPLICE[0] - MX
DECO = (MX - 1.9, MY - 3.4)
N_FIRE, N_SMOKE, N_WISP, N_VENT, N_SPARK, N_CHUNK, N_VFIRE = 22, 26, 12, 18, 140, 70, 16
TILT_AXIS = Vector((-mm.DRIFT[1], mm.DRIFT[0], 0.0)).normalized()


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


# --- node helpers -----------------------------------------------------------------------------------------------------------------
class Nodes:
    def __init__(self, nt):
        self.nt = nt

    def new(self, kind, **inputs):
        n = self.nt.nodes.new(kind)
        for k, v in inputs.items():
            self.put(n.inputs[k], v)
        return n

    def put(self, sock, v):
        if isinstance(v, (int, float)):
            sock.default_value = v
        elif isinstance(v, tuple):
            sock.default_value = v if len(v) == len(sock.default_value) else (*v, 1.0)
        else:
            self.nt.links.new(v, sock)

    def math(self, op, a, b=None, c=None, clamp=False):
        n = self.nt.nodes.new("ShaderNodeMath")
        n.operation = op
        n.use_clamp = clamp
        for i, v in enumerate((a, b, c)):
            if v is not None:
                self.put(n.inputs[i], v)
        return n.outputs[0]

    def mix(self, fac, a, b):
        n = self.nt.nodes.new("ShaderNodeMix")
        n.data_type = "RGBA"
        self.put(n.inputs["Factor"], fac)
        self.put(n.inputs["A"], a)
        self.put(n.inputs["B"], b)
        return n.outputs["Result"]

    def value(self, label, v):
        return K.node_value(self.nt, label, v).outputs[0]

    def noise(self, vec, scale, detail=4.0):
        n = self.new("ShaderNodeTexNoise", Scale=scale, Detail=detail)
        self.put(n.inputs["Vector"], vec)
        return n.outputs["Fac"]

    def xyz(self, vec):
        s = self.nt.nodes.new("ShaderNodeSeparateXYZ")
        self.put(s.inputs[0], vec)
        return s.outputs[0], s.outputs[1], s.outputs[2]


def principled(name, color=(0.5, 0.5, 0.5), rough=0.6, metal=0.0):
    m = material(name, color, metal=metal, rough=rough)
    return m, Nodes(m.node_tree), m.node_tree.nodes.get("Principled BSDF")


def ground_material():
    """Asphalt with slush and wet patches on top, then the gravel base and the soil below (by height, so the cut shows the layers)."""
    m, N, bsdf = principled("Street and soil", rough=0.8)
    pos = N.new("ShaderNodeNewGeometry").outputs["Position"]
    x, _, z = N.xyz(pos)
    grain = N.noise(pos, 14.0, 6.0)
    blotch = N.noise(pos, 0.45, 3.0)
    asphalt = N.mix(grain, (0.035, 0.035, 0.038), (0.085, 0.083, 0.08))
    near_curb = N.math("MULTIPLY", N.math("GREATER_THAN", N.math("ABSOLUTE", x), 4.2), N.math("GREATER_THAN", blotch, 0.6))
    slush = N.math("MULTIPLY", near_curb, N.math("GREATER_THAN", z, -0.03))
    asphalt = N.mix(slush, asphalt, (0.30, 0.30, 0.31))
    stones = N.noise(pos, 22.0, 2.0)
    gravel = N.mix(N.math("GREATER_THAN", stones, 0.55), (0.20, 0.19, 0.17), (0.38, 0.36, 0.33))
    soil = N.mix(grain, (0.10, 0.065, 0.04), (0.19, 0.13, 0.08))
    soil = N.mix(N.math("GREATER_THAN", stones, 0.70), soil, (0.30, 0.28, 0.25))
    low = N.mix(N.math("GREATER_THAN", z, -0.45), soil, gravel)
    col = N.mix(N.math("GREATER_THAN", z, -0.12), low, asphalt)
    N.put(bsdf.inputs["Base Color"], col)
    wet = N.math("MULTIPLY", N.math("GREATER_THAN", blotch, 0.50), N.math("LESS_THAN", blotch, 0.58))
    top = N.math("GREATER_THAN", z, -0.03)
    N.put(bsdf.inputs["Roughness"], N.math("SUBTRACT", 0.85, N.math("MULTIPLY", N.math("MULTIPLY", wet, top), 0.5)))
    bump = N.new("ShaderNodeBump", Strength=0.25)
    N.put(bump.inputs["Height"], grain)
    N.put(bsdf.inputs["Normal"], bump.outputs["Normal"])
    return m


def cover_material(name, kind):
    """Cast iron: a raised diamond tread on top (solid), concentric rings (latched) or a grid of round holes (vented); two pick slots."""
    m, N, bsdf = principled(name, (0.06, 0.055, 0.05), rough=0.45, metal=0.8)
    tc = N.new("ShaderNodeTexCoord").outputs["Object"]
    x, y, z = N.xyz(tc)
    top = N.math("GREATER_THAN", z, TC / 2 - 0.004)
    r = N.math("SQRT", N.math("ADD", N.math("MULTIPLY", x, x), N.math("MULTIPLY", y, y)))
    if kind == "latched":
        ring = N.math("PINGPONG", N.math("DIVIDE", r, 0.035), 0.5)
        h = N.math("GREATER_THAN", ring, 0.22)
    else:
        u = N.math("FRACT", N.math("DIVIDE", N.math("ADD", x, y), 0.06))
        v = N.math("FRACT", N.math("DIVIDE", N.math("SUBTRACT", x, y), 0.06))
        d = N.math("MAXIMUM", N.math("ABSOLUTE", N.math("SUBTRACT", u, 0.5)), N.math("ABSOLUTE", N.math("SUBTRACT", v, 0.5)))
        h = N.math("LESS_THAN", d, 0.30)
    rim = N.math("GREATER_THAN", r, RC - 0.035)
    h = N.math("MAXIMUM", N.math("MULTIPLY", h, N.math("SUBTRACT", 1.0, rim)), rim)
    rust = N.noise(tc, 9.0, 5.0)
    col = N.mix(N.math("MULTIPLY", N.math("GREATER_THAN", rust, 0.6), 0.7), (0.07, 0.065, 0.06), (0.20, 0.10, 0.05))
    worn = N.math("MULTIPLY", N.math("MULTIPLY", h, top), 0.8)
    col = N.mix(worn, col, (0.22, 0.21, 0.20))                                       # the raised tread polished by tyres
    N.put(bsdf.inputs["Base Color"], col)
    N.put(bsdf.inputs["Roughness"], N.math("SUBTRACT", 0.62, N.math("MULTIPLY", worn, 0.3)))
    bump = N.new("ShaderNodeBump", Strength=0.6, Distance=0.004)
    N.put(bump.inputs["Height"], N.math("MULTIPLY", h, top))
    N.put(bsdf.inputs["Normal"], bump.outputs["Normal"])
    slot = N.math("MULTIPLY", N.math("LESS_THAN", N.math("ABSOLUTE", y), 0.013),
                  N.math("MULTIPLY", N.math("GREATER_THAN", N.math("ABSOLUTE", x), 0.27), N.math("LESS_THAN", N.math("ABSOLUTE", x), 0.31)))
    if kind == "vented":
        gx = N.math("SUBTRACT", N.math("FRACT", N.math("DIVIDE", x, 0.068)), 0.5)
        gy = N.math("SUBTRACT", N.math("FRACT", N.math("DIVIDE", y, 0.068)), 0.5)
        dd = N.math("SQRT", N.math("ADD", N.math("MULTIPLY", gx, gx), N.math("MULTIPLY", gy, gy)))
        hole = N.math("MULTIPLY", N.math("LESS_THAN", dd, 0.27), N.math("LESS_THAN", r, 0.315))
        slot = N.math("MAXIMUM", slot, hole)
    out = m.node_tree.nodes.get("Material Output")
    mixs = N.new("ShaderNodeMixShader")
    N.put(mixs.inputs["Fac"], slot)
    N.put(mixs.inputs[1], bsdf.outputs[0])
    N.put(mixs.inputs[2], N.new("ShaderNodeBsdfTransparent").outputs[0])
    N.put(out.inputs["Surface"], mixs.outputs[0])
    return m


def facade_lit(name, brick, seed):
    """Brick walls with a grid of windows (from object coordinates and the face normal); about a third of them lit."""
    m, N, bsdf = principled(name, brick, rough=0.85)
    tc = N.new("ShaderNodeTexCoord").outputs["Object"]
    nrm = N.new("ShaderNodeNewGeometry").outputs["Normal"]
    x, y, z = N.xyz(tc)
    nx, _, nz = N.xyz(nrm)
    ax = N.math("ABSOLUTE", nx)
    horiz = N.math("ADD", N.math("MULTIPLY", y, ax), N.math("MULTIPLY", x, N.math("SUBTRACT", 1.0, ax)))
    fx = N.math("FRACT", N.math("DIVIDE", horiz, 2.6))
    fz = N.math("FRACT", N.math("DIVIDE", z, 3.3))
    wx = N.math("MULTIPLY", N.math("GREATER_THAN", fx, 0.24), N.math("LESS_THAN", fx, 0.76))
    wz = N.math("MULTIPLY", N.math("GREATER_THAN", fz, 0.30), N.math("LESS_THAN", fz, 0.82))
    up = N.math("GREATER_THAN", z, 0.9)
    vert = N.math("LESS_THAN", N.math("ABSOLUTE", nz), 0.5)
    win = N.math("MULTIPLY", N.math("MULTIPLY", wx, wz), N.math("MULTIPLY", up, vert))
    cell = N.math("ADD", N.math("MULTIPLY", N.math("FLOOR", N.math("DIVIDE", horiz, 2.6)), 12.9898),
                  N.math("MULTIPLY", N.math("FLOOR", N.math("DIVIDE", z, 3.3)), 78.233 + seed))
    hsh = N.math("FRACT", N.math("MULTIPLY", N.math("SINE", cell), 43758.5453))
    lit = N.math("MULTIPLY", win, N.math("GREATER_THAN", hsh, 0.62))
    bt = N.new("ShaderNodeTexBrick", Color1=brick, Color2=tuple(c * 0.8 for c in brick), Mortar=(0.5, 0.48, 0.45), Scale=4.0)
    bt.inputs["Mortar Size"].default_value = 0.015
    N.put(bt.inputs["Vector"], tc)
    col = N.mix(win, bt.outputs["Color"], (0.025, 0.03, 0.035))
    N.put(bsdf.inputs["Base Color"], col)
    N.put(bsdf.inputs["Roughness"], N.math("SUBTRACT", 0.85, N.math("MULTIPLY", win, 0.75)))
    N.put(bsdf.inputs["Emission Color"], (1.0, 0.72, 0.42))
    N.put(bsdf.inputs["Emission Strength"], N.math("MULTIPLY", lit, 3.0))
    return m


def puff_material(name):
    """Soft fire and smoke on a sphere's surface (fast, no volume): transparent toward the silhouette and broken up by noise; per
    object the colour carries (heat, soot, -, density) so every puff is set by the model each frame."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    N = Nodes(nt)
    out = N.new("ShaderNodeOutputMaterial")
    info = N.new("ShaderNodeObjectInfo")
    sep = N.new("ShaderNodeSeparateColor")
    N.put(sep.inputs["Color"], info.outputs["Color"])
    heat, soot = sep.outputs["Red"], sep.outputs["Green"]
    lw = N.new("ShaderNodeLayerWeight", Blend=0.5)
    soft = N.math("POWER", N.math("SUBTRACT", 1.0, lw.outputs["Facing"], clamp=True), 1.6)
    tc = N.new("ShaderNodeTexCoord").outputs["Object"]
    off = N.new("ShaderNodeVectorMath")
    off.operation = "ADD"
    N.put(off.inputs[0], tc)
    N.put(off.inputs[1], info.outputs["Random"])
    nz = N.noise(off.outputs[0], 3.6, 5.0)
    alpha = N.math("MULTIPLY", N.math("MULTIPLY", soft, N.math("MULTIPLY_ADD", nz, 2.2, -0.55)), info.outputs["Alpha"], clamp=True)
    diff = N.new("ShaderNodeBsdfDiffuse")
    pale = N.math("SUBTRACT", 1.0, N.math("MAXIMUM", soot, heat), clamp=True)                     # light grey only for cool, clean smoke
    N.put(diff.inputs["Color"], N.mix(pale, N.mix(soot, (0.16, 0.12, 0.09), (0.025, 0.022, 0.02)), (0.55, 0.54, 0.52)))
    bb = N.new("ShaderNodeBlackbody")
    N.put(bb.inputs["Temperature"], N.math("MULTIPLY_ADD", heat, 900.0, 1100.0))
    em = N.new("ShaderNodeEmission")
    core = N.math("MULTIPLY", N.math("POWER", soft, 2.0), N.math("MULTIPLY_ADD", nz, 1.4, 0.2))
    N.put(em.inputs["Color"], N.mix(N.math("MINIMUM", core, 1.0), (1.0, 0.30, 0.04), (1.0, 0.68, 0.22)))
    N.put(em.inputs["Strength"], N.math("MULTIPLY", N.math("MULTIPLY", heat, heat), N.math("MULTIPLY_ADD", core, 16.0, 1.2)))
    add = N.new("ShaderNodeAddShader")
    N.put(add.inputs[0], diff.outputs[0])
    N.put(add.inputs[1], em.outputs[0])
    mix = N.new("ShaderNodeMixShader")
    N.put(mix.inputs["Fac"], alpha)
    N.put(mix.inputs[1], N.new("ShaderNodeBsdfTransparent").outputs[0])
    N.put(mix.inputs[2], add.outputs[0])
    N.put(out.inputs["Surface"], mix.outputs[0])
    return m


def vault_air_material():
    """The vault's air as one even volume (fast): a yellow-grey haze whose density follows the gas share, a glow while the gas burns,
    black smoke after it."""
    m = bpy.data.materials.new("Vault air")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    N = Nodes(nt)
    out = N.new("ShaderNodeOutputMaterial")
    vol = N.new("ShaderNodeVolumePrincipled")
    gas, heat, smoke = (N.value(k, 0.0) for k in ("gas", "heat", "smoke"))
    N.put(vol.inputs["Density"], N.math("ADD", N.math("MULTIPLY", gas, 1.5), N.math("MULTIPLY", smoke, 1.6)))
    N.put(vol.inputs["Color"], N.mix(N.math("MINIMUM", smoke, 1.0), (0.78, 0.70, 0.52), (0.05, 0.045, 0.04)))
    N.put(vol.inputs["Emission Color"], (1.0, 0.45, 0.12))
    N.put(vol.inputs["Emission Strength"], N.math("MULTIPLY", heat, 2.5))
    N.put(out.inputs["Volume"], vol.outputs[0])
    return m


def set_values(m, **kw):
    for n in m.node_tree.nodes:
        if n.type == "VALUE" and n.label in kw:
            n.outputs[0].default_value = kw[n.label]


# --- geometry helpers -------------------------------------------------------------------------------------------------------------
def rect_reach(th, xa, xb, ya, yb):
    """Distance from the origin to the rectangle [xa, xb] x [ya, yb] (around the origin) along the ray at angle th."""
    c, s = math.cos(th), math.sin(th)
    ds = []
    if c > 1e-9:
        ds.append(xb / c)
    elif c < -1e-9:
        ds.append(xa / c)
    if s > 1e-9:
        ds.append(yb / s)
    elif s < -1e-9:
        ds.append(ya / s)
    return min(ds)


def polar_slab(cx, cy, z0, z1, r_in, outer, th0, th1, n=48, corners=()):
    """A slab between a circle (r_in) and an outer edge (function of the angle) from angle th0 to th1 (all the way round if 2 pi)."""
    full = th1 - th0 >= 2 * math.pi - 1e-9
    ths = sorted(set([th0 + (th1 - th0) * k / n for k in range(n + (0 if full else 1))] + [c for c in corners if th0 < c < th1]))
    vs, fs = [], []
    for th in ths:
        c, s = math.cos(th), math.sin(th)
        ro = outer(th)
        vs += [(cx + r_in * c, cy + r_in * s, z0), (cx + r_in * c, cy + r_in * s, z1), (cx + ro * c, cy + ro * s, z0), (cx + ro * c, cy + ro * s, z1)]
    m = len(ths)
    rng = range(m) if full else range(m - 1)
    for i in rng:
        a, b = 4 * i, 4 * ((i + 1) % m)
        fs += [(a + 1, a + 3, b + 3, b + 1), (a, b, b + 2, a + 2), (a, a + 1, b + 1, b), (a + 2, b + 2, b + 3, a + 3)]
    if not full:
        e = 4 * (m - 1)
        fs += [(0, 2, 3, 1), (e, e + 1, e + 3, e + 2)]
    return vs, fs


def half_turn(side):
    return (-math.pi / 2, math.pi / 2) if side > 0 else (math.pi / 2, 3 * math.pi / 2)


def rect_slab(name, side, xa, xb, ya, yb, z0, z1, r_hole, mat):
    """The part of a slab over [xa, xb] x [ya, yb] (relative to the manhole) on one side of the cut, with the round hole taken out."""
    th0, th1 = half_turn(side)
    corners = [math.atan2(y, x) % (2 * math.pi) if side < 0 else math.atan2(y, x) for x in (xa, xb) for y in (ya, yb)]
    v, f = polar_slab(MX, MY, z0, z1, r_hole, lambda th: rect_reach(th, xa, xb, ya, yb), th0, th1, 40, corners)
    return new_object(name, v, f, mat)


def ring(name, side, r_in, r_out, z0, z1, mat, n=40, cx=MX, cy=MY):
    th0, th1 = half_turn(side) if side else (0.0, 2 * math.pi)
    v, f = polar_slab(cx, cy, z0, z1, r_in, lambda th: r_out, th0, th1, n)
    return new_object(name, v, f, mat, smooth=True)


def align_z(v):
    """Rotation matrices turning +z onto each vector of v (n, 3)."""
    v = np.asarray(v, float)
    n = v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-12)
    ref = np.where(np.abs(n[:, 2:3]) < 0.9, np.array([[0.0, 0.0, 1.0]]), np.array([[1.0, 0.0, 0.0]]))
    a = np.cross(ref, n)
    a /= np.linalg.norm(a, axis=1, keepdims=True) + 1e-12
    b = np.cross(n, a)
    return np.stack([a, b, n], axis=2)


# --- the street -------------------------------------------------------------------------------------------------------------------
class Street:
    def __init__(self):
        self.west = []
        ground = ground_material()
        conc = textured("Vault concrete", (0.22, 0.215, 0.20), (0.36, 0.35, 0.33), 3.5, rough=0.9, bump=0.25)
        self.conc = conc
        W = self.west.append
        # east of the cut (always there): soil blocks around the vault and the road above it
        cube("Ground east", ((MX + IX + WALL + X_FAR) / 2, 0.0, (Z_BOT + 0.0) / 2), (X_FAR - MX - IX - WALL, 2 * Y_FAR, -Z_BOT), ground)
        for sy in (-1, 1):
            yy = (IY + WALL + Y_FAR) / 2 * sy + MY
            cube(f"Ground east {sy}", (MX + (IX + WALL) / 2, yy, Z_BOT / 2), (IX + WALL, Y_FAR - IY - WALL, -Z_BOT), ground)
        cube("Ground under the vault", (MX + (IX + WALL) / 2, MY, (Z_BOT + ZF - WALL) / 2), (IX + WALL, 2 * (IY + WALL), ZF - WALL - Z_BOT), ground)
        rect_slab("Road over the vault E", 1, 0.0, IX + WALL, -IY - WALL, IY + WALL, Z_ROOF, 0.0, RN_OUT, ground)
        # west of the cut (street shots only): the road as a slab, the vault's other half
        W(cube("Road west", ((MX - IX - WALL - X_FAR) / 2, 0.0, Z_ROOF / 2), (X_FAR + MX - IX - WALL, 2 * Y_FAR, -Z_ROOF), ground))
        for sy in (-1, 1):
            yy = (IY + WALL + Y_FAR) / 2 * sy + MY
            W(cube(f"Road west {sy}", (MX - (IX + WALL) / 2, yy, Z_ROOF / 2), (IX + WALL, Y_FAR - IY - WALL, -Z_ROOF), ground))
        W(rect_slab("Road over the vault W", -1, -IX - WALL, 0.0, -IY - WALL, IY + WALL, Z_ROOF, 0.0, RN_OUT, ground))
        for side in (1, -1):
            sx = side
            parts = [cube(f"Long wall {side}", (MX + sx * (IX + WALL / 2), MY, (ZF - WALL + Z_ROOF) / 2), (WALL, 2 * (IY + WALL), Z_ROOF - ZF + WALL), conc)]
            for sy in (-1, 1):
                parts.append(cube(f"End wall {side} {sy}", (MX + sx * IX / 2, MY + sy * (IY + WALL / 2), (ZF + Z_ROOF) / 2), (IX, WALL, Z_ROOF - ZF), conc))
            parts.append(cube(f"Floor {side}", (MX + sx * IX / 2, MY, ZF - WALL / 2), (IX, 2 * IY, WALL), conc))
            xa, xb = (0.0, IX) if side > 0 else (-IX, 0.0)
            parts.append(rect_slab(f"Roof {side}", side, xa, xb, -IY, IY, ZC, Z_ROOF, RN, conc))
            parts.append(ring(f"Neck {side}", side, RN, RN_OUT, Z_ROOF, -0.075, conc))
            if side < 0:
                self.west += parts
        # the street above: sidewalks, curbs, snowbanks, lines, buildings, lamps, hydrant
        walk = textured("Sidewalk", (0.46, 0.45, 0.42), (0.58, 0.57, 0.54), 1.2, rough=0.85, bump=0.1)
        curb = material("Curb", (0.58, 0.57, 0.54), rough=0.8)
        snow = textured("Dirty snow", (0.62, 0.62, 0.64), (0.86, 0.87, 0.90), 1.6, rough=0.7, bump=0.6)
        yellow = material("Centre line", (0.80, 0.58, 0.08), rough=0.6)
        white = material("Line paint", (0.80, 0.80, 0.76), rough=0.6)
        rng = random.Random(23)
        for sx in (-1, 1):
            obs = [cube(f"Sidewalk {sx}", (sx * (ROAD_HALF + WALK) / 2, 0.0, 0.075), (WALK - ROAD_HALF, 2 * Y_FAR, 0.15), walk),
                   cube(f"Curb {sx}", (sx * (ROAD_HALF + 0.08), 0.0, 0.08), (0.16, 2 * Y_FAR, 0.16), curb)]
            vs, fs = [], []
            for a, b in ((-60.0, -26.0), (-17.0, 31.0), (40.0, 66.0)):
                n = int((b - a) / 0.5)
                ring_n = 7
                base_i = len(vs)
                for i in range(n + 1):
                    y = a + (b - a) * i / n
                    taper = min(1.0, (y - a) / 1.5, (b - y) / 1.5)
                    h = (0.38 + 0.16 * math.sin(0.9 * y + sx) + 0.08 * math.sin(2.7 * y)) * max(0.15, taper)
                    w = 0.55 + 0.12 * math.sin(1.3 * y + 2 * sx)
                    for j in range(ring_n):
                        ang = math.pi * j / (ring_n - 1)
                        vs.append((sx * (ROAD_HALF + 0.55) - w * math.cos(ang), y, 0.12 + h * math.sin(ang) + 0.03 * rng.random()))
                for i in range(n):
                    for j in range(ring_n - 1):
                        p = base_i + i * ring_n + j
                        fs.append((p, p + 1, p + ring_n + 1, p + ring_n))
            obs.append(new_object(f"Snowbank {sx}", vs, fs, snow, smooth=True))
            if sx < 0:
                self.west += obs
        self.centre = boxes("Centre line", [((dx, 0.0, 0.003), (0.10, 2 * Y_FAR, 0.006)) for dx in (-0.09, 0.09)], yellow)
        self.west.append(self.centre)
        self.west.append(boxes("Crosswalk", [((-ROAD_HALF + 0.45 + 0.75 * k, -21.5, 0.004), (0.45, 2.6, 0.008)) for k in range(16)], white))
        mats = [facade_lit(f"Facade {k}", c, 1.7 * k) for k, c in enumerate([(0.42, 0.18, 0.11), (0.55, 0.45, 0.33), (0.36, 0.20, 0.15), (0.30, 0.16, 0.10), (0.48, 0.30, 0.20)])]
        roof = material("Parapet", (0.20, 0.20, 0.21), rough=0.9)
        blocks = [(1, -60, -27, 13.0), (1, -16, 4, 11.0), (1, 5, 30, 15.0), (1, 41, 66, 12.0),
                  (-1, -60, -27, 9.0), (-1, -16, 10, 12.0), (-1, 11, 30, 8.5), (-1, 41, 66, 14.0)]
        for k, (sx, a, b, h) in enumerate(blocks):
            depth = 14.0
            ob = cube(f"Building {k}", (sx * (WALK + 0.3 + depth / 2), (a + b) / 2, h / 2), (depth, b - a, h), mats[k % len(mats)])
            pa = cube(f"Parapet {k}", (sx * (WALK + 0.3 + depth / 2), (a + b) / 2, h + 0.3), (depth + 0.25, b - a + 0.25, 0.6), roof)
            if sx < 0:
                self.west += [ob, pa]
        pole = material("Lamp pole", (0.10, 0.10, 0.11), metal=0.6, rough=0.45)
        glow = material("Lamp", (1.0, 0.78, 0.50), rough=0.4, emission=12.0)
        self.lamps = []
        for x, y in ((6.7, -20.0), (-6.7, -6.0), (6.7, 14.0), (-6.7, 30.0), (6.7, 46.0)):
            sx = 1 if x > 0 else -1
            obs = [cyl("Lamp pole", 0.08, 7.6, (x, y, 3.8), pole, verts=10),
                   cube("Lamp arm", (x - sx * 0.9, y, 7.5), (1.8, 0.10, 0.10), pole),
                   cube("Lamp head", (x - sx * 1.7, y, 7.42), (0.55, 0.26, 0.10), glow)]
            ld = bpy.data.lights.new("Street lamp", "POINT")
            ld.energy, ld.color, ld.shadow_soft_size = 260.0, (1.0, 0.70, 0.42), 0.3
            lo = bpy.data.objects.new("Street lamp", ld)
            lo.location = (x - sx * 1.7, y, 7.2)
            bpy.context.collection.objects.link(lo)
            obs.append(lo)
            if sx < 0:
                self.west += obs
        red = material("Hydrant", (0.55, 0.05, 0.03), rough=0.45)
        cyl("Hydrant", 0.13, 0.62, (6.55, -3.2, 0.46), red, verts=14)
        K.sphere("Hydrant cap", 0.14, (6.55, -3.2, 0.78), red, scale=(1.0, 1.0, 0.7))
        cyl("Hydrant nozzle", 0.05, 0.40, (6.55, -3.2, 0.62), red, rot=(math.pi / 2, 0.0, 0.0), verts=10)
        # in the cut: a water main and a bundle of phone ducts crossing under the street, beside the vault
        pipe = material("Water main", (0.18, 0.20, 0.22), metal=0.5, rough=0.5)
        water = material("Water", (0.02, 0.05, 0.07), rough=0.1)
        cyl("Water main", 0.32, X_FAR - MX, ((MX + X_FAR) / 2, MY - 4.6, -1.7), pipe, rot=(0.0, math.pi / 2, 0.0), verts=28)
        cyl("Water main inside", 0.28, X_FAR - MX, ((MX + X_FAR) / 2 + 0.002, MY - 4.6, -1.7), water, rot=(0.0, math.pi / 2, 0.0), verts=28)
        duct = material("Phone duct", (0.75, 0.38, 0.08), rough=0.5)
        dark = material("Duct inside", (0.02, 0.02, 0.02), rough=0.9)
        for k in range(6):
            y, z = MY + 3.4 + 0.19 * (k % 3), -1.15 - 0.19 * (k // 3)
            cyl("Phone duct", 0.08, X_FAR - MX, ((MX + X_FAR) / 2, y, z), duct, rot=(0.0, math.pi / 2, 0.0), verts=14)
            cyl("Phone duct inside", 0.065, X_FAR - MX, ((MX + X_FAR) / 2 + 0.002, y, z), dark, rot=(0.0, math.pi / 2, 0.0), verts=14)


class Vault:
    """Cable racks, cables, the splice, duct openings, the puddle; the air volume (haze, flame front, smoke); drops of meltwater."""

    def __init__(self, conc):
        self.west = []
        rack = material("Rack steel", (0.32, 0.31, 0.30), metal=0.8, rough=0.55)
        rubber, N, bsdf = principled("Cable", (0.025, 0.025, 0.027), rough=0.45)
        pos = N.new("ShaderNodeNewGeometry")
        nz = N.noise(pos.outputs["Position"], 26.0, 3.0)
        _, _, ndz = N.xyz(pos.outputs["Normal"])
        salt = N.math("MULTIPLY", N.math("GREATER_THAN", nz, 0.62), N.math("GREATER_THAN", ndz, 0.2))
        N.put(bsdf.inputs["Base Color"], N.mix(salt, (0.025, 0.025, 0.027), (0.78, 0.78, 0.74)))
        N.put(bsdf.inputs["Roughness"], N.math("ADD", 0.45, N.math("MULTIPLY", salt, 0.5)))
        self.splice_m, N, bsdf = principled("Splice", (0.03, 0.03, 0.03), rough=0.5)
        p = N.new("ShaderNodeNewGeometry").outputs["Position"]
        n1, n2 = N.noise(p, 14.0, 5.0), N.noise(p, 40.0, 2.0)
        char, ember = N.value("char", 0.0), N.value("ember", 0.0)
        charred = N.math("GREATER_THAN", n1, N.math("SUBTRACT", 1.05, N.math("MULTIPLY", char, 0.7)))
        crust = N.math("MULTIPLY", N.math("GREATER_THAN", n2, 0.66), N.math("SUBTRACT", 1.0, charred))
        col = N.mix(charred, N.mix(crust, (0.03, 0.03, 0.03), (0.8, 0.8, 0.76)), (0.012, 0.010, 0.008))
        N.put(bsdf.inputs["Base Color"], col)
        N.put(bsdf.inputs["Roughness"], N.math("ADD", 0.5, N.math("MULTIPLY", charred, 0.45)))
        glowing = N.math("MULTIPLY", charred, N.math("GREATER_THAN", n2, 0.58))
        N.put(bsdf.inputs["Emission Color"], (1.0, 0.33, 0.06))
        N.put(bsdf.inputs["Emission Strength"], N.math("MULTIPLY", glowing, N.math("MULTIPLY", ember, 25.0)))
        dark = material("Duct opening", (0.01, 0.01, 0.01), rough=0.9)
        for side in (1, -1):
            sx = side
            items = []
            for y in (-1.0, 0.0, 1.0):
                items.append(((MX + sx * (IX - 0.03), MY + y, (ZF + ZC) / 2), (0.06, 0.05, ZC - ZF - 0.1)))
                for z in CABLE_Z:
                    items.append(((MX + sx * (IX - 0.16), MY + y, z - CABLE_R - 0.012), (0.26, 0.05, 0.024)))
            racks = boxes(f"Racks {side}", items, rack)
            cabs = []
            for k, z in enumerate(CABLE_Z):
                if side > 0 and k == 1:
                    y0, y1 = mm.SPLICE[1] - 0.32, mm.SPLICE[1] + 0.32
                    cabs += [cyl_geom(CABLE_R, y0 + IY + WALL - MY, (MX + sx * CABLE_X, (y0 - IY - WALL + MY) / 2, z), (math.pi / 2, 0, 0), 16),
                             cyl_geom(CABLE_R, IY + WALL + MY - y1, (MX + sx * CABLE_X, (y1 + IY + WALL + MY) / 2, z), (math.pi / 2, 0, 0), 16)]
                else:
                    cabs.append(cyl_geom(CABLE_R, 2 * (IY + WALL), (MX + sx * CABLE_X, MY, z), (math.pi / 2, 0, 0), 16))
            cables = merged(f"Cables {side}", cabs, rubber, smooth=True)
            holes = []
            for sy in (-1, 1):
                for xo in (CABLE_X, 0.48, 0.24):
                    for z in (CABLE_Z if xo == CABLE_X else (-1.4, -1.75, -2.1)):
                        r = CABLE_R + 0.025 if xo == CABLE_X else 0.07
                        holes.append(cyl_geom(r, 0.01, (MX + sx * xo, MY + sy * (IY - 0.004), z), (math.pi / 2, 0, 0), 16))
            ducts = merged(f"Duct openings {side}", holes, dark)
            if side < 0:
                self.west += [racks, cables, ducts]
        sp = mm.SPLICE
        self.splice = merged("Splice", [cyl_geom(0.085, 0.56, sp, (math.pi / 2, 0, 0), 20), cyl_geom(0.07, 0.66, sp, (math.pi / 2, 0, 0), 16)], self.splice_m, smooth=True)
        puddle = material("Salty puddle", (0.08, 0.085, 0.08), rough=0.05)
        self.puddle_e = cube("Puddle E", (MX + IX / 2, MY, ZF + 0.012), (IX - 0.02, 2 * IY - 0.02, 0.024), puddle)
        self.west.append(cube("Puddle W", (MX - IX / 2, MY, ZF + 0.012), (IX - 0.02, 2 * IY - 0.02, 0.024), puddle))
        self.air_m = vault_air_material()
        self.air_full = cube("Vault air", (MX, MY, (ZF + ZC) / 2), (2 * IX - 0.02, 2 * IY - 0.02, ZC - ZF - 0.02), self.air_m)
        self.air_half = cube("Vault air (cut)", (MX + IX / 2, MY, (ZF + ZC) / 2), (IX - 0.01, 2 * IY - 0.02, ZC - ZF - 0.02), self.air_m)
        drop_m = bpy.data.materials.new("Meltwater")
        drop_m.use_nodes = True
        b = drop_m.node_tree.nodes.get("Principled BSDF")
        b.inputs["Base Color"].default_value = (0.75, 0.85, 0.9, 1)
        b.inputs["Roughness"].default_value = 0.02
        b.inputs["Transmission Weight"].default_value = 0.5
        b.inputs["IOR"].default_value = 1.33
        b.inputs["Emission Color"].default_value = (0.7, 0.85, 1.0, 1)                  # a glint, so the drops read against the walls
        b.inputs["Emission Strength"].default_value = 2.5
        proto = [(0.0, 0.0, 0.07), (0.014, 0.0, 0.0), (0.0, 0.014, 0.0), (-0.014, 0.0, 0.0), (0.0, -0.014, 0.0), (0.0, 0.0, -0.015)]   # a drop and its streak
        pf = [(0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1), (5, 2, 1), (5, 3, 2), (5, 4, 3), (5, 1, 4)]
        self.drips = mm.drips()
        self.drops = pieces_mesh("Meltwater drops", proto, pf, len(self.drips), drop_m)
        arc_m = material("Arc", (0.62, 0.78, 1.0), rough=0.5, emission=60.0)
        self.arc_m = arc_m
        self.arcs = [Tube(f"Arc {k}", 16, 0.005, arc_m, sides=5) for k in range(3)]
        ld = bpy.data.lights.new("Arc light", "POINT")
        ld.color, ld.shadow_soft_size = (0.65, 0.8, 1.0), 0.05
        self.arc_light = bpy.data.objects.new("Arc light", ld)
        self.arc_light.location = (sp[0] - 0.15, sp[1], sp[2] + 0.05)
        bpy.context.collection.objects.link(self.arc_light)
        ld = bpy.data.lights.new("Vault fire light", "POINT")
        ld.color, ld.shadow_soft_size = (1.0, 0.55, 0.22), 0.6
        self.fire_light = bpy.data.objects.new("Vault fire light", ld)
        self.fire_light.location = (MX, MY, -1.4)
        bpy.context.collection.objects.link(self.fire_light)

    def set(self, st, section, film_t):
        v, t = st["variant"], st["t"]
        blast = v in ("blast", "latched")
        self.air_full.hide_render = section
        self.air_half.hide_render = not section
        b = st["burn"]
        heat = 0.0 if t <= 0 or not blast else b * (1.0 if t < mm.T_BURN else math.exp(-(t - mm.T_BURN) / 0.25))
        smoke = 0.0 if not blast or t <= 0 else min(1.0, 1.0 - math.exp(-max(0.0, t - 0.1) / 0.4))
        set_values(self.air_m, gas=st["gas_vs_lfl"] * (1.0 - b), heat=heat, smoke=smoke)
        ember = 0.0
        if v in ("smoulder", "vented") and t > 0:
            ember = st["char"] * (0.65 + 0.35 * math.sin(7.0 * film_t) ** 2)
        elif blast:
            ember = 1.0
        set_values(self.splice_m, char=st["char"], ember=ember)
        self.fire_light.data.energy = 9000.0 * heat * b if blast else 0.0
        arc = st["arc"]
        self.arc_light.data.energy = 900.0 * arc
        rng = np.random.default_rng(int(abs(t) * 1000) % 100000 + 7)
        sp = np.array(mm.SPLICE)
        ends = [sp + np.array([0.1, 0.05, -(CABLE_Z[1] - CABLE_Z[2]) + CABLE_R + 0.02]), sp + np.array([0.02, -0.2, CABLE_Z[0] - CABLE_Z[1] - CABLE_R]),
                np.array([MX + IX - 0.01, sp[1] + 0.22, sp[2] + 0.05])]
        for k, tube in enumerate(self.arcs):
            on = arc > 0.05 and (k == 0 or arc > 0.35 + 0.2 * k)
            tube.sheet.ob.hide_render = not on
            if not on:
                continue
            p0 = sp + np.array([-0.06, 0.08 * (k - 1), 0.03])
            p1 = ends[k]
            pts = np.linspace(p0, p1, 16)
            ln = float(np.linalg.norm(p1 - p0))
            jit = rng.normal(0.0, 0.18 * ln, (16, 3)) * np.sin(np.linspace(0, math.pi, 16))[:, None]
            tube.set(pts + jit)
        for n in self.arc_m.node_tree.nodes:
            if n.type == "BSDF_PRINCIPLED":
                n.inputs["Emission Strength"].default_value = 60.0 * max(arc, 0.0)
        pos = np.tile([0.0, 0.0, -50.0], (len(self.drips), 1))
        falling = 0
        if v in ("smoulder", "vented"):
            for i, d in enumerate(self.drips):
                z = mm.drop_height(film_t, d)
                if z is not None and (section or abs(d[1] - MX) < RN):
                    pos[i] = (d[1], d[2], z)
                    falling += 1
        set_pieces(self.drops, pos, None, np.full(len(self.drips), 1.0))
        return falling


class Covers:
    """Three cast-iron covers (solid, vented, latched) in one frame, and a vented cover on another vault in the next lane."""

    def __init__(self):
        iron = material("Frame iron", (0.07, 0.065, 0.06), metal=0.75, rough=0.5)
        self.west = []
        for side in (1, -1):
            parts = [ring(f"Frame flange {side}", side, RC + 0.006, RF, -0.015, 0.004, iron), ring(f"Frame skirt {side}", side, RC + 0.006, RC + 0.026, -0.085, 0.0, iron),
                     ring(f"Frame seat {side}", side, RN - 0.01, RC + 0.026, -0.085, -TC, iron)]
            if side < 0:
                self.west += parts
        self.obs = {}
        for kind in ("solid", "vented", "latched"):
            m = cover_material(f"Cover {kind}", kind)
            parts = [cyl_geom(RC, TC, (0.0, 0.0, 0.0), (0, 0, 0), 56)]
            if kind != "vented":
                for k in range(8):
                    a = math.pi * k / 8
                    parts.append(_rib(a))
                parts.append(_ring_rib(0.22))
            if kind == "latched":
                for s in (-1, 1):                                                         # straps whose feet catch under the frame
                    parts.append(_box(0.0, s * 0.30, -TC / 2 - 0.08, 0.10, 0.025, 0.16))
                    parts.append(_box(0.0, s * 0.3075, -TC / 2 - 0.155, 0.10, 0.075, 0.02))
            ob = merged(f"Cover {kind}", parts, m)
            self.obs[kind] = ob
        if True:
            hook = material("Latch", (0.35, 0.34, 0.32), metal=0.8, rough=0.4)
            hk = []
            for s in (-1, 1):
                hk.append(_box(MX, MY + s * 0.3425, -TC - 0.145 + mm.Z_LATCH + 0.006 - 0.01, 0.12, 0.035, 0.012))
            self.hooks = merged("Latch catches", hk, hook)
        dm = cover_material("Cover vented (next lane)", "vented")
        self.deco = merged("Next-lane cover", [cyl_geom(RC, TC, (0.0, 0.0, 0.0), (0, 0, 0), 56)], dm)
        self.deco.location = (DECO[0], DECO[1], 0.004 - TC / 2)
        black = material("Deep", (0.005, 0.005, 0.005), rough=1.0)
        self.west += [self.deco, cyl("Next-lane hole", RC - 0.01, 0.002, (DECO[0], DECO[1], 0.0015), black, verts=40),
                      ring("Next-lane frame", 0, RC + 0.004, RF, 0.0, 0.006, iron, cx=DECO[0], cy=DECO[1])]

    def set(self, st):
        v = st["variant"]
        kind = {"smoulder": "solid", "blast": "solid", "vented": "vented", "latched": "latched"}[v]
        for k, ob in self.obs.items():
            ob.hide_render = k != kind
        self.hooks.hide_render = kind != "latched"
        c = st["cover"]
        ob = self.obs[kind]
        rot = Matrix.Rotation(c["tumble"], 4, TILT_AXIS)
        z = c["z"]
        if c["tilt"] > 0:
            ax = Vector((math.cos(c["tilt_dir"] + math.pi / 2), math.sin(c["tilt_dir"] + math.pi / 2), 0.0))
            rot = Matrix.Rotation(c["tilt"], 4, ax) @ rot
            z = TC / 2 * math.cos(c["tilt"]) + RC * math.sin(c["tilt"])
        ob.matrix_world = Matrix.Translation((c["x"], c["y"], z)) @ rot
        return ob


def _box(cx, cy, cz, dx, dy, dz):
    return K.box_verts((cx, cy, cz), (dx, dy, dz)), K.BOX_FACES


def _rib(a):
    v = [(x, y, z) for x, y, z in K.box_verts((0.0, 0.0, -TC / 2 - 0.018), (2 * RC - 0.05, 0.022, 0.036))]
    c, s = math.cos(a), math.sin(a)
    return [(c * x - s * y, s * x + c * y, z) for x, y, z in v], K.BOX_FACES


def _ring_rib(r):
    v, f = polar_slab(0.0, 0.0, -TC / 2 - 0.036, -TC / 2, r - 0.012, lambda th: r + 0.012, 0.0, 2 * math.pi, 40)
    return v, f


class Fire:
    """Fire and smoke out of the hole (volumes set from the model's outflow and fireball), sparks, slush chunks, smoke wisps in the
    vault, smoke breathing out of a vented cover, the ring of fire and smoke from under a latched cover."""

    def __init__(self):
        self.vm = puff_material("Fire and smoke")
        mk = lambda name: K.sphere(name, 1.0, (0.0, 0.0, 0.0), self.vm, seg=16, rings=10)       # noqa: E731
        self.fire = [mk(f"Fire {k}") for k in range(N_FIRE)]
        self.vfire = [mk(f"Vault fire {k}") for k in range(N_VFIRE)]
        g = np.random.default_rng(77)
        self.vpos = np.stack([g.uniform(MX + 0.12, MX + IX - 0.12, N_VFIRE), g.uniform(MY - IY + 0.2, MY + IY - 0.2, N_VFIRE),
                              g.uniform(ZF + 0.3, ZC - 0.15, N_VFIRE)], 1)
        self.vpos[:4] = [(MX + 0.1 * k, MY, ZC - 0.1 - 0.1 * k) for k in range(4)]                  # up into the neck
        self.vdist = np.linalg.norm(self.vpos - np.array(mm.SPLICE), axis=1)
        self.smoke = [mk(f"Smoke {k}") for k in range(N_SMOKE)]
        self.wisps = [mk(f"Wisp {k}") for k in range(N_WISP)]
        self.vent = [mk(f"Vent smoke {k}") for k in range(N_VENT)]
        rng = np.random.default_rng(2323)
        d = rng.normal(0, 1, (N_FIRE, 3))
        d[:, 2] = np.abs(d[:, 2]) * 0.8
        self.fdir = d / np.linalg.norm(d, axis=1, keepdims=True)
        self.fsize = rng.uniform(0.55, 1.1, N_FIRE)
        self.fdelay = rng.uniform(0.0, 0.06, N_FIRE)
        self.sjit = rng.normal(0, 1, (N_SMOKE, 3))
        self.wjit = rng.normal(0, 1, (N_WISP, 3))
        self.vjit = rng.uniform(0, 1, (N_VENT, 3))
        spark_m = material("Sparks", (1.0, 0.55, 0.16), rough=0.5, emission=30.0)
        proto = K.box_verts((0.0, 0.0, 0.0), (0.05, 0.05, 1.0))
        self.sparks = pieces_mesh("Sparks", proto, K.BOX_FACES, N_SPARK, spark_m)
        a = rng.uniform(0, 2 * math.pi, N_SPARK)
        up = rng.uniform(0.35, 1.0, N_SPARK)
        sp = rng.uniform(4.0, 13.0, N_SPARK)
        self.svel = np.stack([np.cos(a) * np.sqrt(1 - up ** 2) * sp, np.sin(a) * np.sqrt(1 - up ** 2) * sp, up * sp], 1)
        self.st0 = rng.uniform(0.05, 0.35, N_SPARK)
        self.slife = rng.uniform(0.5, 1.2, N_SPARK)
        self.sr = rng.uniform(0.25, 0.36, N_SPARK)
        self.sa = a
        chunk_m = textured("Slush chunks", (0.55, 0.56, 0.58), (0.85, 0.86, 0.88), 6.0, rough=0.6)
        tet = [(0.05, 0.0, 0.0), (-0.025, 0.043, 0.0), (-0.025, -0.043, 0.0), (0.0, 0.0, 0.055)]
        self.chunks = pieces_mesh("Slush chunks", tet, [(0, 1, 2), (0, 1, 3), (1, 2, 3), (2, 0, 3)], N_CHUNK, chunk_m)
        ca = rng.uniform(0, 2 * math.pi, N_CHUNK)
        self.cpos = np.stack([MX + np.cos(ca) * rng.uniform(0.42, 0.75, N_CHUNK), MY + np.sin(ca) * rng.uniform(0.42, 0.75, N_CHUNK), np.full(N_CHUNK, 0.02)], 1)
        cs = rng.uniform(1.5, 5.5, N_CHUNK)
        self.cvel = np.stack([np.cos(ca) * cs * 0.6, np.sin(ca) * cs * 0.6, rng.uniform(2.0, 6.5, N_CHUNK)], 1)
        self.cspin = rng.uniform(-18, 18, (N_CHUNK, 3))
        self.csize = rng.uniform(0.6, 2.0, N_CHUNK)
        ld = bpy.data.lights.new("Fire light", "POINT")
        ld.color, ld.shadow_soft_size = (1.0, 0.52, 0.18), 0.8
        self.light = bpy.data.objects.new("Fire light", ld)
        bpy.context.collection.objects.link(self.light)

    @staticmethod
    def _put(ob, loc, r, heat, soot, dens, stretch=(1.0, 1.0, 1.0)):
        if dens <= 0.004 or r <= 0.01:
            ob.hide_render = True
            return 0
        ob.hide_render = False
        ob.location = loc
        ob.scale = (r * stretch[0], r * stretch[1], r * stretch[2])
        ob.color = (min(1.0, max(0.0, heat)), min(1.0, max(0.0, soot)), 0.0, min(1.0, dens))
        return 1

    def set(self, st, film_t, section, street_visible):
        v, t = st["variant"], st["t"]
        n_fire = n_smoke = 0
        for ob in self.fire + self.smoke + self.vent + self.wisps + self.vfire:
            ob.hide_render = True
        if v in ("blast", "latched") and t > 0:                                            # the flame front through the vault
            front = 2.9 * st["burn"] ** (1 / 3)
            for k, ob in enumerate(self.vfire):
                lit = front - self.vdist[k]
                if lit <= 0:
                    continue
                age = lit / 2.9 * mm.T_BURN + max(0.0, t - mm.T_BURN)
                hot = math.exp(-age / 0.22)
                n_fire += self._put(ob, tuple(self.vpos[k]), 0.35 + 0.25 * min(1.0, age / 0.1), hot, 1.0 - hot, 0.95 * min(1.0, lit / 0.3))
        self.light.data.energy = 0.0
        spos = np.tile([0.0, 0.0, -50.0], (N_SPARK, 1))
        srot = np.repeat(np.eye(3)[None], N_SPARK, 0)
        sscale = np.full(N_SPARK, 0.1)
        cpos = np.tile([0.0, 0.0, -50.0], (N_CHUNK, 1))
        crot = np.repeat(np.eye(3)[None], N_CHUNK, 0)
        airborne = 0
        if v == "blast" and t > 0:
            fb = st["fireball"]
            q = st["outflow"]
            jet = min(1.0, q / 60.0)
            zc = 0.25 + 0.85 * fb + 0.9 * max(0.0, t - 0.25) ** 1.3
            heat_c = math.exp(-max(0.0, t - 0.2) / 0.45)
            soot_c = 1.0 - math.exp(-max(0.0, t - 0.25) / 0.5)
            for k, ob in enumerate(self.fire):
                tt = t - self.fdelay[k]
                if tt <= 0:
                    continue
                if k < 6:                                                                    # the jet up the neck and out of the hole
                    h = (k + 0.5) / 6 * (0.6 + 3.0 * jet)
                    n_fire += self._put(ob, (MX, MY, -0.5 + h), 0.22 + 0.12 * jet, 0.95, 0.1, 0.9 * jet, (1.0, 1.0, 1.8))
                    continue
                h = (k - 6 + 0.5) / (N_FIRE - 6)
                z_top = 0.4 + 2.0 * fb + 1.1 * max(0.0, t - 0.3)
                cz = st["cover"]["z"]
                if cz > 0.3 and t < mm.landing_time():
                    z_top = min(z_top, cz - 0.4 - (0.25 + 0.42 * fb))                       # the fire stays under the flying cover
                zz = 0.15 + h * max(0.2, z_top - 0.15)
                c = Vector((MX + 0.45 * fb * self.fdir[k, 0] * (0.35 + 0.65 * h), MY + 0.45 * fb * self.fdir[k, 1] * (0.35 + 0.65 * h), zz))
                r = (0.25 + 0.42 * fb * (0.55 + 0.45 * h)) * self.fsize[k] * min(1.0, tt / 0.05)
                n_fire += self._put(ob, c, r, heat_c * (0.75 + 0.25 * (1 - h)), soot_c * (0.6 + 0.4 * h), 0.85)
            for k, ob in enumerate(self.smoke):
                t0 = 0.18 + 0.16 * k
                a = t - t0
                if a < 0 or a > 3.6:
                    continue
                j = self.sjit[k]
                loc = (MX + 0.35 * j[0] + 0.25 * a, MY + 0.35 * j[1] + 0.7 * a, 0.35 + 1.5 * a + 0.3 * j[2])
                n_smoke += self._put(ob, loc, 0.32 + 0.42 * a, 0.55 * math.exp(-a / 0.2), 0.92, 0.85 * (1 - a / 3.6) * min(1.0, a / 0.15))
            self.light.location = (MX, MY, max(0.4, 0.5 * zc))
            self.light.data.energy = 6000.0 * heat_c * max(fb, 0.5 * jet) ** 2 + 600.0 * min(1.0, t / 0.3)
            st_t = t - self.st0
            live = (st_t > 0) & (st_t < self.slife)
            if live.any():
                tt = np.where(live, st_t, 0.0)
                p0 = np.stack([MX + np.cos(self.sa) * self.sr, MY + np.sin(self.sa) * self.sr, np.full(N_SPARK, 0.05)], 1)
                pp = p0 + self.svel * tt[:, None] + np.array([0, 0, -0.5 * mm.G]) * (tt ** 2)[:, None]
                vel = self.svel + np.array([0, 0, -mm.G]) * tt[:, None]
                ok = live & (pp[:, 2] > 0.02)
                spos[ok] = pp[ok]
                srot[ok] = align_z(vel[ok])
                sscale[ok] = np.clip(np.linalg.norm(vel[ok], axis=1) * 0.012, 0.03, 0.16)
                airborne = int(ok.sum())
            t_pop = 0.07
            tc_ = t - t_pop
            if tc_ > 0:
                pp = self.cpos + self.cvel * tc_ + np.array([0, 0, -0.5 * mm.G]) * tc_ ** 2
                landed = pp[:, 2] < 0.02
                pp[landed, 2] = 0.02
                cpos = pp
                crot = rot_xyz(*(self.cspin * min(tc_, 1.2)).T)
        elif v == "latched" and t > 0:
            q = st["outflow"]
            lift = st["cover"]["z"] + TC / 2
            rate = min(1.0, q / 40.0)
            for k, ob in enumerate(self.vent):
                age = (k / N_VENT) * 0.55
                a = t - age * 0.3
                if a <= 0:
                    continue
                ang = 2 * math.pi * self.vjit[k, 0]
                reach = 0.42 + 0.75 * (1 - math.exp(-a / 0.18)) * (0.5 + self.vjit[k, 1])
                hot = math.exp(-a / 0.25)
                dens = 0.8 * min(1.0, a / 0.03) * math.exp(-max(0.0, t - 0.4) / 0.5)
                n_fire += self._put(ob, (MX + reach * math.cos(ang), MY + reach * math.sin(ang), max(0.05, lift * 0.6) + 0.35 * a ** 1.2),
                                    0.07 + 0.22 * (1 - math.exp(-a / 0.25)), hot * (0.4 + 0.6 * rate), 0.55 + 0.45 * (1 - hot), 0.6 * dens, (1.0, 1.0, 0.75))
            self.light.location = (MX, MY, 0.3)
            self.light.data.energy = 1200.0 * rate
        if v in ("smoulder", "vented") and t > 0:
            dens = min(1.0, 0.3 + st["char"])
            for k, ob in enumerate(self.wisps):
                age = ((film_t * 0.22 + k / N_WISP) % 1.0)
                j = self.wjit[k]
                sp = mm.SPLICE
                if v == "vented" and age > 0.45:                                        # drawn up the neck and out through the holes
                    u = (age - 0.45) / 0.55
                    loc = (MX + 0.15 * j[0], MY + 0.15 * j[1], ZC + (0.0 - ZC + 0.6) * u)
                    r = 0.18 + 0.1 * u
                else:
                    rise = min(1.0, age / 0.45)
                    loc = (sp[0] - 0.1 - 0.35 * rise + 0.08 * j[0], sp[1] + 0.25 * j[1] + 0.6 * age * j[2], sp[2] + (ZC - 0.15 - sp[2]) * rise ** 0.7)
                    r = 0.12 + 0.35 * age
                if section and loc[0] < MX + 0.08:
                    loc = (MX + 0.08 + 0.1 * abs(j[0]), loc[1], loc[2])
                n_smoke += self._put(ob, loc, 1.3 * r, 0.0, 0.5, 0.6 * dens * math.sin(math.pi * age))
            if v == "vented" and street_visible:
                for k, ob in enumerate(self.vent):
                    age = ((film_t * 0.3 + self.vjit[k, 2]) % 1.0)
                    ang = 2 * math.pi * self.vjit[k, 0]
                    rr = 0.3 * math.sqrt(self.vjit[k, 1])
                    loc = (MX + rr * math.cos(ang) + 0.15 * age, MY + rr * math.sin(ang) + 0.5 * age, 0.06 + 1.3 * age)
                    n_smoke += self._put(ob, loc, 0.10 + 0.36 * age, 0.0, 0.35, 0.5 * dens * math.sin(math.pi * age) ** 0.7)
        set_pieces(self.sparks, spos, srot, sscale)
        set_pieces(self.chunks, cpos, crot, self.csize)
        return {"fire_puffs": n_fire, "smoke_puffs": n_smoke, "sparks_airborne": airborne}


def main():
    args = arguments()
    args.out.mkdir(parents=True, exist_ok=True)
    car_root, _body, _wheels, _geom = base.load_source_car(args.source)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    scene.cycles.volume_step_rate = 2.0
    scene.cycles.volume_max_steps = 128
    scene.cycles.transparent_max_bounces = 32
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Punchy"
    scene.view_settings.exposure = -0.1
    if hasattr(scene.view_settings, "use_white_balance"):
        scene.view_settings.use_white_balance = True
        scene.view_settings.white_balance_temperature = 6800.0
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    sun_to = cinematic.sun_vector((-0.25, -0.97), 8.0)
    cinematic.apply_sky(scene, sun_to, strength=0.26, dust=1.4)
    sd = bpy.data.lights.new("Sun", "SUN")
    sd.energy, sd.angle, sd.color = 3.6, 0.02, (1.0, 0.62, 0.38)
    sun = bpy.data.objects.new("Sun", sd)
    scene.collection.objects.link(sun)
    sun.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()
    car_root.location = (4.75, 7.4, 0.0)
    street = Street()
    vault = Vault(street.conc)
    covers = Covers()
    fire = Fire()
    west = street.west + vault.west + covers.west
    fd = bpy.data.lights.new("Section fill", "AREA")
    fd.energy, fd.size, fd.color = 320.0, 3.0, (0.85, 0.9, 1.0)
    fill = bpy.data.objects.new("Section fill", fd)
    scene.collection.objects.link(fill)
    fill.location = (MX - 3.2, MY - 0.8, -1.2)
    fill.rotation_euler = Vector((1.0, 0.25, 0.0)).to_track_quat("-Z", "Y").to_euler()
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    car_parts = [car_root, *car_root.children_recursive]

    def render(sh, path):
        scene.render.resolution_x, scene.render.resolution_y = round(FRAME[0] * args.res_scale), round(FRAME[1] * args.res_scale)
        section = bool(sh.get("section"))
        st = mm.state(sh["t"], sh["variant"])
        for ob in west:
            ob.hide_render = section
        fill.hide_render = not section
        for ob in car_parts:
            ob.hide_render = False
        falling = vault.set(st, section, sh["film_t"])
        cov = covers.set(st)
        fx = fire.set(st, sh["film_t"], section, True)
        c = sh["cam"]
        loc, tgt = Vector(c["loc"]), Vector(c["target"])
        dd = cam.data
        dd.sensor_fit, dd.sensor_width, dd.lens, dd.clip_start = "HORIZONTAL", 36.0, c["lens"], 0.02
        dd.clip_end = 1000.0
        dd.dof.use_dof = True
        dd.dof.focus_distance = (tgt - loc).length
        dd.dof.aperture_fstop = c.get("fstop", 8.0)
        base.set_camera(cam, loc, tgt)
        bpy.context.view_layer.update()
        cv = st["cover"]
        fb = st["fireball"]
        w = max(RC + 0.15, fb)
        lo = (min(cv["x"] - RC, MX - w), min(cv["y"] - RC, MY - w), 0.0)
        hi = (max(cv["x"] + RC, MX + w), max(cv["y"] + RC, MY + w), max(cv["z"] + RC, 0.25 + 1.6 * fb if fb > 0 else 0.1))
        box = hook_gate.project_box(scene, cam, Matrix.Identity(4), lo, hi)
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        del cov
        return {"variant": st["variant"], "t": round(st["t"], 6), "gas": round(st["gas"], 5), "arc": round(st["arc"], 4), "char": round(st["char"], 4),
                "pressure": round(st["pressure"], 1), "outflow": round(st["outflow"], 3), "burn": round(st["burn"], 4), "fireball": round(st["fireball"], 4),
                "cover": {k: round(v, 5) for k, v in cv.items()}, "drops_falling": falling, **fx, "section": section,
                "subject_box": box, "cam_world": [round(v, 3) for v in loc], "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

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
        print("MANHOLE_FRAME " + json.dumps(info), flush=True)
    (args.out / f"manhole-frames-{frames[0]:05d}.json").write_text(json.dumps({"renderer_source_sha256": src_sha, "frames": out}, indent=1))


if __name__ == "__main__":
    main()
