"""EP.31 snow-melting road: 100 % 3D renderer (Blender, Cycles CPU), house style of EP.13-EP.30 (depth of field), at dusk in falling
snow. A street in a snow-country town (snowmelt_world): two-storey houses with thick snow on the roofs and lit windows, covered
sidewalks (gangi) along the house fronts, concrete utility poles with street lamps and wires, snowbanks along the gutters, side
streets and the rest of the town under snow, mountains far off. In the centre line a nozzle every 3 m throws low fans of water
across the lanes; the asphalt is wet and stained orange-brown by the iron in the groundwater, and the film of water runs to the
gutters. Beyond the sprinkled stretch the street is packed snow.

Everything moves from snowmelt_world: the jets' droplets along their arcs, the falling snow (a flake vanishes where it lands in the
water, leaving a ripple), the car (keeps left; headlights and tail lights), the running film. Section shots cut the ground open
along the centre line: the well casing down to the water-bearing gravel with its slotted screen and the pump, the supply main under
the nozzles and the risers, warm water flowing up and along; in the subsidence shot the ground above the clay drops round the fixed
casing while the clay squeezes. The newer design: no jets, warm pipes under a see-through window of asphalt. No text anywhere."""
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
from benchmarks.manhole_blast.render_manhole_3d import Nodes, principled, set_values  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402
from benchmarks.rock_net.render_rocknet_3d import merged  # noqa: E402
from benchmarks.roller_barrier.render_roller_3d import Proto, box_proto, np_mesh, stamp  # noqa: E402
from benchmarks.snowmelt_road import snowmelt_timeline as tl  # noqa: E402
from benchmarks.snowmelt_road import snowmelt_world as w  # noqa: E402

material = base.material
FRAME = (1080, 1920)
PAINT = (1.75, 0.30, 0.24)
XG = 420.0
YG0, YG1 = w.Y0 - 420.0, w.Y1 + 560.0
HIDE_Z = -300.0
POLE_X = 3.95
TOWN_Y = (-330.0, 540.0)
LAMP_REACH = 1.5
WALK_TOP = 0.12


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


# --- shader helpers --------------------------------------------------------------------------------------------------------------------
def ramp(N, v, a, b):
    """0 at a -> 1 at b (smoothstep, clamped)."""
    n = N.nt.nodes.new("ShaderNodeMapRange")
    n.interpolation_type = "SMOOTHSTEP"
    n.clamp = True
    N.put(n.inputs["Value"], v)
    n.inputs["From Min"].default_value = a
    n.inputs["From Max"].default_value = b
    return n.outputs["Result"]


def vec(N, x, y, z):
    n = N.nt.nodes.new("ShaderNodeCombineXYZ")
    for i, v in enumerate((x, y, z)):
        N.put(n.inputs[i], v)
    return n.outputs[0]


def bump(N, bsdf, height, strength, distance=0.1):
    b = N.new("ShaderNodeBump", Strength=strength, Distance=distance)
    N.put(b.inputs["Height"], height)
    N.put(bsdf.inputs["Normal"], b.outputs["Normal"])


def window_mask(N, x, y, z, nx, ranges):
    """1 on the cut face (normal +x) inside any of the rectangles (y0, y1, z0, z1) in the material's own coordinates."""
    face = N.math("GREATER_THAN", nx, 0.5)
    m = None
    for y0, y1, z0, z1 in ranges:
        r = N.math("MULTIPLY", N.math("MULTIPLY", N.math("GREATER_THAN", y, y0), N.math("LESS_THAN", y, y1)),
                   N.math("MULTIPLY", N.math("GREATER_THAN", z, z0), N.math("LESS_THAN", z, z1)))
        m = r if m is None else N.math("MAXIMUM", m, r)
    return N.math("MULTIPLY", face, m)


def see_through(m, N, bsdf, mask):
    out = m.node_tree.nodes.get("Material Output")
    mix = N.new("ShaderNodeMixShader")
    N.put(mix.inputs["Fac"], mask)
    N.put(mix.inputs[1], bsdf.outputs[0])
    N.put(mix.inputs[2], N.new("ShaderNodeBsdfTransparent").outputs[0])
    N.put(out.inputs["Surface"], mix.outputs[0])


# --- materials -------------------------------------------------------------------------------------------------------------------------
def street_material():
    """Asphalt: wet and stained orange-brown by the iron in the groundwater where the jets reach, slush toward the edges, packed snow
    beyond the sprinkled stretch; the film of water runs out to the gutters (moving ripples). Values: spray (1 sprinkler road, 0 the
    newer road), flow (story time), pipes (1: a window of the road drawn see-through over the warm pipes)."""
    m, N, bsdf = principled("Street", (0.05, 0.05, 0.05), rough=0.3)
    pos = N.new("ShaderNodeNewGeometry").outputs["Position"]
    x, y, z = N.xyz(pos)
    ax = N.math("ABSOLUTE", x)
    spray, flow, pipes = N.value("spray", 1.0), N.value("flow", 0.0), N.value("pipes", 0.0)
    grain = N.noise(pos, 22.0, 6.0)
    asphalt = N.mix(grain, (0.028, 0.028, 0.030), (0.070, 0.067, 0.064))
    sprinkled = N.math("MULTIPLY", ramp(N, y, float(w.NOZZLE_Y[0]) - 6.0, float(w.NOZZLE_Y[0]) - 2.0),
                       N.math("SUBTRACT", 1.0, ramp(N, y, float(w.NOZZLE_Y[-1]) + 2.0, float(w.NOZZLE_Y[-1]) + 6.0)))
    streak = N.noise(vec(N, N.math("MULTIPLY", x, 1.6), N.math("MULTIPLY", y, 0.22), 0.0), 1.4, 4.0)
    centre = N.math("SUBTRACT", 1.0, ramp(N, ax, 1.2, 2.5))
    stain = N.math("MULTIPLY", N.math("MULTIPLY", centre, ramp(N, streak, 0.38, 0.62)), N.math("MULTIPLY", spray, sprinkled))
    col = N.mix(N.math("MULTIPLY", stain, 0.8), asphalt, (0.30, 0.11, 0.035))
    halo = N.math("MULTIPLY", N.math("SUBTRACT", 1.0, ramp(N, ax, 0.0, 0.35)), N.math("MULTIPLY", spray, sprinkled))
    col = N.mix(N.math("MULTIPLY", halo, 0.6), col, (0.22, 0.08, 0.025))                   # rust right round the nozzles
    edge = N.noise(pos, 3.0, 3.0)
    slush = N.math("MULTIPLY", ramp(N, N.math("ADD", ax, N.math("MULTIPLY", edge, 0.5)), 2.85, 3.35), sprinkled)
    col = N.mix(slush, col, (0.50, 0.52, 0.56))
    track = N.math("PINGPONG", N.math("SUBTRACT", ax, 0.85), 0.9)                           # tyre ruts in the packed snow
    snowroad = N.mix(ramp(N, track, 0.15, 0.55), (0.42, 0.43, 0.46), (0.70, 0.72, 0.76))
    col = N.mix(N.math("SUBTRACT", 1.0, sprinkled), col, snowroad)
    N.put(bsdf.inputs["Base Color"], col)
    wet = N.math("MULTIPLY", N.math("SUBTRACT", 1.0, ramp(N, ax, 2.5, 3.05)), sprinkled)
    damp = N.math("SUBTRACT", 1.0, spray)
    rough = N.math("SUBTRACT", 0.55, N.math("MULTIPLY", wet, N.math("ADD", 0.47, N.math("MULTIPLY", damp, -0.25))))
    N.put(bsdf.inputs["Roughness"], rough)
    run = vec(N, N.math("SUBTRACT", N.math("MULTIPLY", ax, 2.2), N.math("MULTIPLY", flow, 0.9)), N.math("MULTIPLY", y, 1.6),
              N.math("MULTIPLY", flow, 0.35))
    ripple = N.noise(run, 3.0, 2.0)
    bump(N, bsdf, N.math("ADD", N.math("MULTIPLY", ripple, N.math("MULTIPLY", wet, spray)), N.math("MULTIPLY", grain, 0.15)), 0.10, 0.05)
    win = N.math("MULTIPLY", N.math("MULTIPLY", pipes, N.math("MULTIPLY", N.math("GREATER_THAN", y, w.PIPE_Y[0]), N.math("LESS_THAN", y, w.PIPE_Y[1]))),
                 N.math("LESS_THAN", ax, w.ROAD_HALF - 0.05))
    see_through(m, N, bsdf, N.math("MULTIPLY", win, 0.8))
    return m


def snow_material(name, c1=(0.66, 0.70, 0.78), c2=(0.86, 0.89, 0.95), scale=1.5, bmp=0.35):
    m, N, bsdf = principled(name, c2, rough=0.8)
    pos = N.new("ShaderNodeTexCoord").outputs["Object"]
    n = N.noise(pos, scale, 6.0)
    N.put(bsdf.inputs["Base Color"], N.mix(ramp(N, n, 0.35, 0.7), c1, c2))
    bump(N, bsdf, n, bmp, 0.3)
    return m


def facade_material(name, wall, seed, lit_share=0.55, shop=True, sampled=True):
    """Board walls with windows (world position and the face normal); some upper windows and most shop windows lit warm."""
    m, N, bsdf = principled(name, wall, rough=0.85)
    pos = N.new("ShaderNodeNewGeometry")
    x, y, z = N.xyz(pos.outputs["Position"])
    nx, _, nz = N.xyz(pos.outputs["Normal"])
    ax = N.math("ABSOLUTE", nx)
    horiz = N.math("ADD", N.math("MULTIPLY", y, ax), N.math("MULTIPLY", x, N.math("SUBTRACT", 1.0, ax)))
    vert = N.math("LESS_THAN", N.math("ABSOLUTE", nz), 0.5)
    fx = N.math("FRACT", N.math("DIVIDE", horiz, 2.4))
    up = N.math("MULTIPLY", N.math("MULTIPLY", N.math("GREATER_THAN", z, 3.5), N.math("LESS_THAN", z, 4.9)),
                N.math("MULTIPLY", N.math("GREATER_THAN", fx, 0.28), N.math("LESS_THAN", fx, 0.72)))
    cell = N.math("ADD", N.math("MULTIPLY", N.math("FLOOR", N.math("DIVIDE", horiz, 2.4)), 12.9898), 78.233 + seed)
    hsh = N.math("FRACT", N.math("MULTIPLY", N.math("SINE", cell), 43758.5453))
    lit = N.math("MULTIPLY", up, N.math("LESS_THAN", hsh, lit_share))
    win = up
    if shop:
        fs = N.math("FRACT", N.math("DIVIDE", horiz, 3.6))
        low = N.math("MULTIPLY", N.math("MULTIPLY", N.math("GREATER_THAN", z, 0.45), N.math("LESS_THAN", z, 2.2)),
                     N.math("MULTIPLY", N.math("GREATER_THAN", fs, 0.08), N.math("LESS_THAN", fs, 0.92)))
        win = N.math("MAXIMUM", win, low)
        lit = N.math("MAXIMUM", lit, N.math("MULTIPLY", low, N.math("LESS_THAN", hsh, 0.8)))
    win = N.math("MULTIPLY", win, vert)
    lit = N.math("MULTIPLY", lit, vert)
    boards = N.math("LESS_THAN", N.math("FRACT", N.math("DIVIDE", z, 0.22)), 0.08)
    grain = N.noise(pos.outputs["Position"], 6.0, 4.0)
    wallc = N.mix(N.math("ADD", N.math("MULTIPLY", boards, 0.5), N.math("MULTIPLY", grain, 0.3)), wall, tuple(c * 0.6 for c in wall))
    glass = N.mix(lit, (0.02, 0.025, 0.03), (0.9, 0.62, 0.36))
    N.put(bsdf.inputs["Base Color"], N.mix(win, wallc, glass))
    N.put(bsdf.inputs["Roughness"], N.math("SUBTRACT", 0.85, N.math("MULTIPLY", win, 0.7)))
    N.put(bsdf.inputs["Emission Color"], (1.0, 0.66, 0.38))
    N.put(bsdf.inputs["Emission Strength"], N.math("MULTIPLY", lit, 1.4))
    if not sampled and hasattr(m, "cycles"):
        m.cycles.emission_sampling = "NONE"
    return m


def strata_material():
    """The ground in section, by height in the object's own coordinates (so it rides down with the block that sinks): road base,
    brown soil, sand, the water-bearing gravel (warm near the well screen) and the dark clay below; see-through where the pipes are
    cut open."""
    m, N, bsdf = principled("Ground layers", (0.3, 0.25, 0.2), rough=0.9)
    tc = N.new("ShaderNodeTexCoord").outputs["Object"]
    x, y, z = N.xyz(tc)
    nx, _, _ = N.xyz(N.new("ShaderNodeNewGeometry").outputs["Normal"])
    wob = N.math("MULTIPLY", N.noise(vec(N, 0.0, N.math("MULTIPLY", y, 0.05), 0.0), 1.0, 3.0), 1.6)
    zz = N.math("ADD", z, wob)
    stones = N.noise(tc, 9.0, 3.0)
    fine = N.noise(tc, 30.0, 4.0)
    base_c = N.mix(ramp(N, stones, 0.45, 0.6), (0.24, 0.23, 0.21), (0.42, 0.40, 0.37))
    soil = N.mix(fine, (0.20, 0.13, 0.08), (0.30, 0.20, 0.12))
    sand = N.mix(fine, (0.42, 0.34, 0.22), (0.55, 0.46, 0.31))
    gravel = N.mix(ramp(N, stones, 0.4, 0.62), (0.18, 0.22, 0.27), (0.42, 0.44, 0.47))
    clay = N.mix(fine, (0.13, 0.12, 0.12), (0.19, 0.18, 0.17))
    col = N.mix(ramp(N, zz, -60.0, -57.0), clay, gravel)
    col = N.mix(ramp(N, zz, -45.0, -43.0), col, (0.30, 0.31, 0.30))          # (the clay block sits on top of this; never seen)
    col = N.mix(ramp(N, zz, -13.0, -11.0), col, sand)
    col = N.mix(ramp(N, zz, -4.5, -3.5), col, soil)
    col = N.mix(N.math("GREATER_THAN", z, -0.5), col, base_c)
    aq = N.math("MULTIPLY", ramp(N, z, w.Z_AQ_BOT - 1.0, w.Z_AQ_BOT + 1.0), N.math("SUBTRACT", 1.0, ramp(N, z, w.Z_AQ_TOP - 1.0, w.Z_AQ_TOP)))
    near = N.math("SUBTRACT", 1.0, ramp(N, N.math("ABSOLUTE", N.math("SUBTRACT", y, w.Y_WELL)), 0.5, 7.0))
    drained = N.value("drained", 0.0)
    wet = N.math("MULTIPLY", aq, N.math("SUBTRACT", 1.0, N.math("MULTIPLY", drained, 0.8)))
    col = N.mix(N.math("MULTIPLY", wet, 0.45), col, (0.10, 0.20, 0.30))
    N.put(bsdf.inputs["Base Color"], col)
    N.put(bsdf.inputs["Roughness"], N.math("SUBTRACT", 0.9, N.math("MULTIPLY", wet, 0.55)))
    N.put(bsdf.inputs["Emission Color"], (1.0, 0.55, 0.22))
    N.put(bsdf.inputs["Emission Strength"], N.math("MULTIPLY", N.math("MULTIPLY", wet, near), N.math("MULTIPLY", ramp(N, stones, 0.5, 0.7), 1.6)))
    bump(N, bsdf, stones, 0.3, 0.2)
    r = w.R_CASING - 0.012
    mask = window_mask(N, x, y, z, nx, [(w.Y_WELL - r, w.Y_WELL + r, w.Z_SCREEN[0] - 0.4, 1.0),
                                        (w.Y_WELL, 1e4, w.Z_MAIN - w.R_MAIN + 0.012, w.Z_MAIN + w.R_MAIN - 0.012)])
    see_through(m, N, bsdf, mask)
    return m


def clay_material():
    """The clay and silt between the sand and the gravel, in thin bands that squeeze together when the ground sinks (object
    coordinates of a block whose origin is its bottom)."""
    m, N, bsdf = principled("Clay layers", (0.3, 0.3, 0.3), rough=0.9)
    tc = N.new("ShaderNodeTexCoord").outputs["Object"]
    x, y, z = N.xyz(tc)
    nx, _, _ = N.xyz(N.new("ShaderNodeNewGeometry").outputs["Normal"])
    zz = N.math("ADD", z, N.math("MULTIPLY", N.noise(vec(N, 0.0, N.math("MULTIPLY", y, 0.08), 0.0), 1.0, 2.0), 1.2))
    band = N.math("PINGPONG", zz, 1.6)
    big = N.math("PINGPONG", N.math("MULTIPLY", zz, 0.37), 1.0)
    fine = N.noise(tc, 25.0, 4.0)
    col = N.mix(ramp(N, band, 0.4, 1.2), (0.26, 0.29, 0.33), (0.40, 0.38, 0.30))
    col = N.mix(N.math("MULTIPLY", ramp(N, big, 0.72, 0.8), 0.85), col, (0.17, 0.13, 0.10))
    col = N.mix(N.math("MULTIPLY", fine, 0.35), col, (0.20, 0.20, 0.21))
    N.put(bsdf.inputs["Base Color"], col)
    r = w.R_CASING - 0.012
    see_through(m, N, bsdf, window_mask(N, x, y, z, nx, [(w.Y_WELL - r, w.Y_WELL + r, -1.0, 1e3)]))
    return m


def flow_material(name, warm=(1.0, 0.52, 0.18), speed=1.2):
    """Warm water moving through a pipe: bands drifting along (object y + z) at the flow speed; value 'flow' = story time."""
    m, N, bsdf = principled(name, (0.25, 0.12, 0.05), rough=0.15)
    tc = N.new("ShaderNodeTexCoord").outputs["Object"]
    x, y, z = N.xyz(tc)
    flow = N.value("flow", 0.0)
    s = N.math("SUBTRACT", N.math("ADD", y, z), N.math("MULTIPLY", flow, speed))
    n = N.noise(vec(N, N.math("MULTIPLY", s, 2.5), N.math("MULTIPLY", x, 6.0), 0.0), 2.0, 3.0)
    band = N.math("ADD", N.math("MULTIPLY", N.math("PINGPONG", s, 0.35), 2.0), N.math("MULTIPLY", n, 0.8))
    N.put(bsdf.inputs["Emission Color"], warm)
    N.put(bsdf.inputs["Emission Strength"], N.math("ADD", 1.0, N.math("MULTIPLY", band, 2.2)))
    N.put(bsdf.inputs["Base Color"], N.mix(ramp(N, band, 0.3, 1.0), (0.20, 0.08, 0.03), warm))
    return m


def drop_material():
    """Water thrown by the jets: clear with a cool sheen so the arcs read against the dark street."""
    m, N, bsdf = principled("Jet water", (0.85, 0.92, 1.0), rough=0.05)
    bsdf.inputs["Transmission Weight"].default_value = 1.0
    bsdf.inputs["IOR"].default_value = 1.33
    bsdf.inputs["Emission Color"].default_value = (0.70, 0.82, 1.0, 1.0)
    bsdf.inputs["Emission Strength"].default_value = 0.22
    return m


# --- geometry helpers ------------------------------------------------------------------------------------------------------------------
def flat(ob):
    """Flat shading: a mesh built through the data API without it is drawn smooth, which bends the window grid on the walls."""
    me = ob.data
    me.polygons.foreach_set("use_smooth", np.zeros(len(me.polygons), dtype=bool))
    me.update()
    return ob


def slab(name, x0, x1, y0, y1, z0, z1, mat, origin=(0.0, 0.0, 0.0)):
    c = ((x0 + x1) / 2 - origin[0], (y0 + y1) / 2 - origin[1], (z0 + z1) / 2 - origin[2])
    ob = K.new_object(name, K.box_verts(c, (x1 - x0, y1 - y0, z1 - z0)), K.BOX_FACES, mat)
    ob.location = origin
    return ob


def prism_proto(mi=0):
    """Unit gable roof: ridge along local y at z = 1 over a 1 x 1 base at z = 0."""
    co = [(-0.5, -0.5, 0.0), (0.5, -0.5, 0.0), (0.0, -0.5, 1.0), (-0.5, 0.5, 0.0), (0.5, 0.5, 0.0), (0.0, 0.5, 1.0)]
    faces = [(0, 1, 2), (5, 4, 3), (0, 2, 5, 3), (1, 4, 5, 2), (0, 3, 4, 1)]
    return Proto(co, faces, [mi] * 5)


def half_tube(axis, c, r_in, r_out, a, b, n=18, shift=-0.003):
    """The x <= 0 half of a tube (axis 'z' at (0, c[1]) or 'y' at (0, ., c[2])) from a to b along the axis, with its cut strips on
    the plane x = shift and its ends closed."""
    th = np.linspace(math.pi / 2, 3 * math.pi / 2, n + 1)
    vs, fs = [], []

    def p(r, t, s):
        u, v = r * math.cos(t) + shift, r * math.sin(t)
        return (u, c[1] + v, s) if axis == "z" else (u, s, c[2] + v)
    for s in (a, b):
        for r in (r_in, r_out):
            vs += [p(r, t, s) for t in th]
    m = n + 1

    def ix(si, ri, k):
        return (si * 2 + ri) * m + k
    for k in range(n):
        fs.append((ix(0, 1, k), ix(0, 1, k + 1), ix(1, 1, k + 1), ix(1, 1, k)))      # outside
        fs.append((ix(0, 0, k), ix(1, 0, k), ix(1, 0, k + 1), ix(0, 0, k + 1)))      # inside
        fs.append((ix(0, 0, k), ix(0, 0, k + 1), ix(0, 1, k + 1), ix(0, 1, k)))      # end a
        fs.append((ix(1, 0, k), ix(1, 1, k), ix(1, 1, k + 1), ix(1, 0, k + 1)))      # end b
    for k in (0, n):
        fs.append((ix(0, 0, k), ix(0, 1, k), ix(1, 1, k), ix(1, 0, k)))              # cut strips
    return vs, fs


def half_core(axis, c, r, a, b, n=18, shift=-0.006):
    """The x <= 0 half of a solid rod (the water in a pipe), its flat face on x = shift."""
    th = np.linspace(math.pi / 2, 3 * math.pi / 2, n + 1)
    vs, fs = [], []

    def p(t, s):
        u, v = r * math.cos(t) + shift, r * math.sin(t)
        return (u, c[1] + v, s) if axis == "z" else (u, s, c[2] + v)
    for s in (a, b):
        vs += [p(t, s) for t in th]
    m = n + 1
    for k in range(n):
        fs.append((k, k + 1, m + k + 1, m + k))
    fs.append((0, m, 2 * m - 1, m - 1))                                                     # the flat face
    fs.append(tuple(range(m)))
    fs.append(tuple(range(2 * m - 1, m - 1, -1)))
    return vs, fs


def sweep(points, r, n=6):
    pts = np.asarray(points, float)
    t = np.gradient(pts, axis=0)
    t /= np.linalg.norm(t, axis=1, keepdims=True) + 1e-12
    a = np.cross(t, np.array([0.0, 0.0, 1.0]))
    a /= np.linalg.norm(a, axis=1, keepdims=True) + 1e-12
    b = np.cross(t, a)
    ang = 2 * np.pi * np.arange(n) / n
    co = pts[:, None, :] + r * (np.cos(ang)[None, :, None] * a[:, None, :] + np.sin(ang)[None, :, None] * b[:, None, :])
    faces = [(i * n + j, i * n + (j + 1) % n, (i + 1) * n + (j + 1) % n, (i + 1) * n + j) for i in range(len(pts) - 1) for j in range(n)]
    return co.reshape(-1, 3), faces


def bicone(n, k=8):
    """n bicones (k + 2 verts each): rounder snowflakes than octahedra."""
    f = []
    for j in range(k):
        f.append((j, (j + 1) % k, k))
        f.append(((j + 1) % k, j, k + 1))
    return [tuple(i + (k + 2) * m for i in ff) for m in range(n) for ff in f]


def bicone_points(c, half_len, r, k=8):
    ang = 2 * np.pi * np.arange(k) / k
    ring = np.stack([np.cos(ang), np.sin(ang), np.zeros(k)], 1)
    v = c[:, None, :] + ring[None, :, :] * np.asarray(r)[:, None, None]
    top = c + np.stack([np.zeros(len(c)), np.zeros(len(c)), half_len], 1)
    bot = c - np.stack([np.zeros(len(c)), np.zeros(len(c)), half_len], 1)
    return np.concatenate([v, top[:, None, :], bot[:, None, :]], axis=1).reshape(-1, 3)


def octa(n):
    """n octahedra (6 verts each) as a Sheet's faces."""
    f = [(0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4), (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5)]
    return [tuple(i + 6 * k for i in ff) for k in range(n) for ff in f]


def octa_points(c, axis, half_len, r):
    """Verts (n*6, 3) of octahedra centred at c (n,3), stretched along unit `axis` (n,3) by half_len, radius r across."""
    a = np.cross(axis, np.array([0.0, 0.0, 1.0]))
    bad = np.linalg.norm(a, axis=1) < 1e-6
    a[bad] = np.array([1.0, 0.0, 0.0])
    a /= np.linalg.norm(a, axis=1, keepdims=True)
    b = np.cross(axis, a)
    hl, rr = np.asarray(half_len)[:, None], np.asarray(r)[:, None]
    v = np.stack([c + a * rr, c - a * rr, c + b * rr, c - b * rr, c + axis * hl, c - axis * hl], axis=1)
    return v.reshape(-1, 3)


# --- the street and the town -----------------------------------------------------------------------------------------------------------
def cross_free(y0, y1, margin=0.0):
    """Pieces of [y0, y1] that avoid the side streets."""
    cuts = sorted((c - w.CROSS_HALF - margin, c + w.CROSS_HALF + margin) for c in w.CROSS_Y)
    out, a = [], y0
    for c0, c1 in cuts:
        if c1 <= a or c0 >= y1:
            continue
        if c0 > a:
            out.append((a, c0))
        a = max(a, c1)
    if a < y1:
        out.append((a, y1))
    return out


class Ground:
    """Blocks of ground in halves (x < 0 kept in section shots), the street, gutters, sidewalks, snowbanks, the town's snow."""

    def __init__(self, sink_root):
        self.right, self.sinking = [], []
        strata, clay = strata_material(), clay_material()
        self.strata = strata
        self.street = street_material()
        concrete = base.material("Gutter concrete", (0.36, 0.36, 0.37), rough=0.8)
        grate = base.material("Gutter grate", (0.05, 0.05, 0.05), metal=0.6, rough=0.5)
        walk = base.material("Sidewalk", (0.40, 0.39, 0.38), rough=0.75)
        snow = snow_material("Snow")
        bank = snow_material("Snowbank", (0.55, 0.58, 0.64), (0.80, 0.83, 0.89), 2.2, 0.5)
        packed = snow_material("Packed snow road", (0.46, 0.47, 0.50), (0.72, 0.74, 0.79), 0.8, 0.2)
        # the ground in blocks: the top block (to the sand's bottom) rides down when the ground sinks, the clay squeezes
        top_l = slab("Ground top (west)", -XG, 0.0, YG0, YG1, w.Z_SOIL_BOT, -0.08, strata)
        self.clay = slab("Clay (west)", -XG, 0.0, YG0, YG1, w.Z_AQ_TOP, w.Z_SOIL_BOT, clay, origin=(0.0, 0.0, w.Z_AQ_TOP))
        slab("Deep ground (west)", -XG, 0.0, YG0, YG1, w.Z_DEEP, w.Z_AQ_TOP, strata)
        self.right.append(slab("Ground (east)", 0.0, XG, YG0, YG1, w.Z_DEEP, -0.08, strata))
        self.far_side = slab("Ground (far side of the cut)", 24.0, XG, YG0, YG1, w.Z_DEEP, -0.08, strata)      # section shots: a trench
        self.sinking.append(top_l)
        for sx in (-1, 1):
            obs = [slab(f"Street {sx}", min(0, sx * w.ROAD_HALF), max(0, sx * w.ROAD_HALF), YG0, YG1, -0.08, 0.0, self.street)]
            g0, g1 = w.ROAD_HALF, w.ROAD_HALF + w.GUTTER
            obs.append(slab(f"Gutter {sx}", min(sx * g0, sx * g1), max(sx * g0, sx * g1), YG0, YG1, -0.08, 0.02, concrete))
            grates = [((sx * (g0 + 0.25), yy, 0.021), (0.32, 0.45, 0.004)) for yy in np.arange(w.Y0, w.Y1, 6.0)]
            obs.append(K.boxes(f"Gutter grates {sx}", grates, grate))
            for a, b in cross_free(YG0, YG1):
                obs.append(slab(f"Sidewalk {sx} {a:.0f}", min(sx * g1, sx * w.FRONT), max(sx * g1, sx * w.FRONT), a, b, -0.08, WALK_TOP, walk))
                obs.append(slab(f"Town snow {sx} {a:.0f}", min(sx * w.FRONT, sx * XG), max(sx * w.FRONT, sx * XG), a, b, -0.08, 0.10, snow))
            for c in w.CROSS_Y:
                obs.append(slab(f"Side street {sx} {c:.0f}", min(sx * g1, sx * XG), max(sx * g1, sx * XG), c - w.CROSS_HALF, c + w.CROSS_HALF,
                                -0.08, 0.06, packed))
            obs.append(self._banks(sx, bank))
            for ob in obs:
                ob.parent = sink_root
                if sx > 0:
                    self.right.append(ob)
        for ob in self.sinking:
            ob.parent = sink_root
        for c, d in (((0.0, YG1 + 4000.0, -0.05), (9000.0, 8000.0, 0.1)), ((0.0, YG0 - 4000.0, -0.05), (9000.0, 8000.0, 0.1)),
                     ((XG + 4000.0, (YG0 + YG1) / 2, -0.05), (8000.0, YG1 - YG0, 0.1)), ((-XG - 4000.0, (YG0 + YG1) / 2, -0.05), (8000.0, YG1 - YG0, 0.1))):
            K.cube("Snow plain", c, d, snow)

    @staticmethod
    def _banks(sx, mat):
        rng = random.Random(31 + sx)
        vs, fs = [], []
        ring_n = 7
        for a, b in cross_free(YG0 + 40, YG1 - 40, margin=0.8):
            n = max(2, int((b - a) / 0.6))
            base_i = len(vs)
            for i in range(n + 1):
                y = a + (b - a) * i / n
                taper = min(1.0, (y - a) / 1.2, (b - y) / 1.2)
                h = (0.42 + 0.18 * math.sin(0.7 * y + sx) + 0.1 * math.sin(2.3 * y)) * max(0.12, taper)
                wd = 0.55 + 0.12 * math.sin(1.1 * y + 2 * sx)
                for j in range(ring_n):
                    ang = math.pi * j / (ring_n - 1)
                    vs.append((sx * (w.ROAD_HALF + 0.5) - wd * math.cos(ang) * sx, y, 0.0 + h * math.sin(ang) + 0.03 * rng.random()))
            for i in range(n):
                for j in range(ring_n - 1):
                    p = base_i + i * ring_n + j
                    fs.append((p, p + ring_n, p + ring_n + 1, p + 1) if sx > 0 else (p, p + 1, p + ring_n + 1, p + ring_n))
        return K.new_object(f"Snowbank {sx}", vs, fs, mat, smooth=True)


class Town:
    """Houses (front rows along the street and rows behind), covered sidewalks, utility poles, wires and street lamps."""

    def __init__(self, sink_root):
        self.right, self.lamps = [], []
        rng = random.Random(3131)
        walls = [(0.62, 0.58, 0.52), (0.36, 0.27, 0.20), (0.70, 0.68, 0.64), (0.48, 0.44, 0.40)]
        mats_front = [facade_material(f"Front walls {k}", c, 3.1 * k) for k, c in enumerate(walls)]
        mats_back = [facade_material(f"Back walls {k}", c, 5.7 * k, 0.4, shop=False, sampled=False) for k, c in enumerate(walls)]
        roof = base.material("Tin roof", (0.16, 0.10, 0.08), metal=0.4, rough=0.5)
        snowcap = snow_material("Roof snow", (0.72, 0.76, 0.84), (0.90, 0.92, 0.97), 1.0, 0.25)
        body = box_proto((0.0, 0.0, 0.5), (1.0, 1.0, 1.0))
        gable = prism_proto()
        houses = {"front": [], "back": []}
        for sx in (-1, 1):
            for a, b in cross_free(*TOWN_Y, margin=0.5):
                y = a + rng.uniform(0.3, 1.5)
                while True:
                    wy = rng.uniform(7.0, 11.0)
                    if y + wy > b - 0.3:
                        break
                    dx = rng.uniform(9.0, 12.0)
                    houses["front"].append((sx, sx * (w.FRONT + dx / 2), y + wy / 2, dx, wy, rng.uniform(5.8, 7.0), rng.random() < 0.65, rng.randrange(4)))
                    y += wy + rng.uniform(0.6, 2.2)
            for xr in np.arange(24.0, 170.0, 15.0):
                for a, b in cross_free(*TOWN_Y, margin=1.5):
                    y = a + rng.uniform(0.5, 4.0)
                    while True:
                        wy = rng.uniform(7.5, 12.0)
                        if y + wy > b - 0.5:
                            break
                        if rng.random() < 0.8:
                            dx = rng.uniform(8.0, 11.0)
                            houses["back"].append((sx, sx * (xr + rng.uniform(-1.5, 1.5)), y + wy / 2, dx, wy, rng.uniform(5.2, 7.0), rng.random() < 0.5, rng.randrange(4)))
                        y += wy + rng.uniform(2.0, 6.0)
        self.counts = {k: len(v) for k, v in houses.items()}
        for kind, mats in (("front", mats_front), ("back", mats_back)):
            for side in (-1, 1):
                hs = [h for h in houses[kind] if h[0] == side]
                for k in range(4):
                    xf = [(np.diag((dx, wy, hh)), (x, y, 0.0)) for _, x, y, dx, wy, hh, _, mi in hs if mi == k]
                    if xf:
                        ob = flat(stamp(f"Houses {kind} {side} {k}", body, [mats[k]], xf))
                        self._own(ob, side, sink_root)
                rx, sx_ = [], []
                for _, x, y, dx, wy, hh, ridge_x, _ in hs:
                    rot = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]) if ridge_x else np.eye(3)
                    ux, uy = (wy, dx) if ridge_x else (dx, wy)
                    rh = 0.33 * min(dx, wy)
                    rx.append((rot @ np.diag((ux + 0.8, uy + 0.8, rh)), (x, y, hh)))
                    sx_.append((rot @ np.diag((ux + 1.0, uy + 1.0, rh)), (x, y, hh + 0.45)))
                self._own(flat(stamp(f"Roofs {kind} {side}", gable, [roof], rx)), side, sink_root)
                self._own(flat(stamp(f"Roof snow {kind} {side}", gable, [snowcap], sx_)), side, sink_root)
        # covered sidewalks (gangi): a roof on posts over the sidewalk, snow on top
        wood = base.material("Gangi timber", (0.20, 0.13, 0.08), rough=0.7)
        for sx in (-1, 1):
            roofs, snows, posts = [], [], []
            for a, b in cross_free(*TOWN_Y, margin=0.5):
                x0, x1 = w.ROAD_HALF + w.GUTTER + 0.25, w.FRONT + 0.1
                roofs.append(((sx * (x0 + x1) / 2, (a + b) / 2, 2.72), (x1 - x0, b - a, 0.14)))
                roofs.append(((sx * (x0 + 0.06), (a + b) / 2, 2.55), (0.12, b - a, 0.22)))
                snows.append(((sx * (x0 + x1) / 2, (a + b) / 2, 2.93), (x1 - x0 + 0.12, b - a, 0.28)))
                for yy in np.arange(a + 0.3, b, 2.7):
                    posts.append(((sx * (x0 + 0.1), yy, 1.3), (0.12, 0.12, 2.6)))
            for ob in (K.boxes(f"Gangi roof {sx}", roofs, wood), K.boxes(f"Gangi snow {sx}", snows, snowcap), K.boxes(f"Gangi posts {sx}", posts, wood)):
                self._own(ob, sx, sink_root)
        # utility poles with lamps, cross-arms and wires
        pole_m = base.material("Concrete pole", (0.52, 0.52, 0.50), rough=0.75)
        wire_m = base.material("Wire", (0.02, 0.02, 0.02), rough=0.5)
        lamp_m = base.material("Lamp", (1.0, 0.80, 0.56), rough=0.4, emission=30.0)
        dark = base.material("Lamp housing", (0.12, 0.12, 0.13), metal=0.5, rough=0.4)
        for sx in (-1, 1):
            ys = [y for y in np.arange(w.Y0 + (0.0 if sx > 0 else 20.0), w.Y1, 30.0) if all(abs(y - c) > w.CROSS_HALF + 1.0 for c in w.CROSS_Y)]
            parts, arms, heads, housings, wires = [], [], [], [], []
            for y in ys:
                parts.append(K.cyl_geom(0.15, 11.0, (sx * POLE_X, y, 5.5), (0, 0, 0), 10))
                arms.append(((sx * (POLE_X + 0.0), y, 9.6), (1.8, 0.12, 0.12)))
                arms.append(((sx * (POLE_X - LAMP_REACH / 2), y, 7.05), (LAMP_REACH, 0.08, 0.08)))
                housings.append(((sx * (POLE_X - LAMP_REACH), y, 7.0), (0.55, 0.28, 0.12)))
                heads.append(((sx * (POLE_X - LAMP_REACH), y, 6.93), (0.45, 0.2, 0.02)))
                ld = bpy.data.lights.new("Street lamp", "POINT")
                ld.energy, ld.color, ld.shadow_soft_size = 420.0, (1.0, 0.78, 0.55), 0.18
                lo = bpy.data.objects.new("Street lamp", ld)
                lo.location = (sx * (POLE_X - LAMP_REACH), y, 6.8)
                bpy.context.collection.objects.link(lo)
                self._own(lo, sx, sink_root)
                self.lamps.append((sx, y))
            for dz, dxw in ((9.6, -0.8), (9.6, 0.8), (9.6, 0.0), (8.0, 0.25)):
                for y0, y1 in zip(ys[:-1], ys[1:]):
                    wires.append(((sx * POLE_X + dxw, (y0 + y1) / 2, dz), (0.025, y1 - y0, 0.025)))
            obs = [merged(f"Poles {sx}", parts, pole_m), K.boxes(f"Cross-arms {sx}", arms, pole_m), K.boxes(f"Lamp housings {sx}", housings, dark),
                   K.boxes(f"Lamp glass {sx}", heads, lamp_m), K.boxes(f"Wires {sx}", wires, wire_m)]
            for ob in obs:
                self._own(ob, sx, sink_root)

    def _own(self, ob, side, sink_root):
        ob.parent = sink_root
        if side > 0:
            self.right.append(ob)


def build_mountains():
    m, N, bsdf = principled("Mountain snow", (0.80, 0.84, 0.92), rough=0.85)
    nrm = N.new("ShaderNodeNewGeometry").outputs["Normal"]
    _, _, nz = N.xyz(nrm)
    pos = N.new("ShaderNodeNewGeometry").outputs["Position"]
    rock = N.math("MULTIPLY", ramp(N, nz, 0.75, 0.55), ramp(N, N.noise(pos, 0.006, 3.0), 0.4, 0.7))
    col = N.mix(N.math("MULTIPLY", rock, 0.55), (0.78, 0.82, 0.90), (0.32, 0.33, 0.36))
    N.put(bsdf.inputs["Base Color"], col)
    rng = np.random.default_rng(31)
    for name, ya, yb in (("Mountains north", 1300.0, 3800.0), ("Mountains south", -3800.0, -1300.0)):
        nx_, ny_ = 90, 40
        xs = np.linspace(-5000.0, 5000.0, nx_)
        ys = np.linspace(ya, yb, ny_)
        X, Y = np.meshgrid(xs, ys, indexing="ij")
        d = np.minimum(np.abs(Y - ya), np.abs(Y - yb)) / abs(yb - ya)
        Z = np.zeros_like(X)
        for _ in range(14):
            cx, cy = rng.uniform(-4500, 4500), rng.uniform(ya, yb)
            h, s = rng.uniform(250, 750), rng.uniform(500, 1300)
            Z += h * np.exp(-((X - cx) ** 2 + (Y - cy) ** 2) / (2 * s * s))
        Z *= np.clip(d * 4.0, 0.0, 1.0)
        co = np.stack([X.ravel(), Y.ravel(), Z.ravel() - 1.0], 1)
        faces = [(i * ny_ + j, (i + 1) * ny_ + j, (i + 1) * ny_ + j + 1, i * ny_ + j + 1) for i in range(nx_ - 1) for j in range(ny_ - 1)]
        np_mesh(name, co, faces, [m], smooth=True)


def dusk_world(scene):
    """Blue hour under snow clouds: a deep blue sky, paler and a little warm toward the horizon (the town's lights on the clouds)."""
    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    N = Nodes(nt)
    out = N.new("ShaderNodeOutputWorld")
    bg = N.new("ShaderNodeBackground")
    d = N.new("ShaderNodeTexCoord").outputs["Generated"]
    _, _, z = N.xyz(d)
    up = N.math("POWER", N.math("MAXIMUM", z, 0.0), 0.45)
    col = N.mix(up, (0.20, 0.17, 0.17), (0.030, 0.045, 0.085))
    N.put(bg.inputs["Color"], col)
    N.put(bg.inputs["Strength"], 1.0)
    N.put(out.inputs["Surface"], bg.outputs[0])


# --- the system ------------------------------------------------------------------------------------------------------------------------
class Sprinklers:
    """Nozzles in the centre line, the risers and the main under them, the well, the pump; jets of droplets (rebuilt every frame)."""

    def __init__(self, sink_root):
        brass = base.material("Nozzle brass", (0.55, 0.40, 0.18), metal=0.9, rough=0.3)
        hole = base.material("Nozzle hole", (0.01, 0.01, 0.01), rough=0.5)
        steel = base.material("Pipe steel", (0.40, 0.42, 0.45), metal=0.8, rough=0.35)
        pvc = base.material("Main pipe", (0.30, 0.33, 0.38), metal=0.2, rough=0.4)
        cover = base.material("Well cover", (0.07, 0.065, 0.06), metal=0.7, rough=0.5)
        self.water = flow_material("Warm water")
        cap = Proto(*K.cyl_geom(0.06, 0.05, (0.0, 0.0, 0.0), (0, 0, 0), 16))
        dot = Proto(*K.cyl_geom(0.022, 0.012, (0.0, 0.0, 0.026), (0, 0, 0), 10), [1] * 12)
        xf = [(np.eye(3), (0.0, float(y), 0.005)) for y in w.NOZZLE_Y]
        self.nozzles = stamp("Nozzles", cap + dot, [brass, hole], xf)
        self.nozzles.parent = sink_root
        risers = [K.cyl_geom(w.R_RISER, -0.03 - w.Z_MAIN, (0.0, float(y), (w.Z_MAIN - 0.03) / 2), (0, 0, 0), 10) for y in w.NOZZLE_Y if y > w.Y_WELL]
        self.risers = merged("Risers", risers, steel)
        self.risers.parent = sink_root
        y_end = float(w.NOZZLE_Y[-1]) + 1.0
        mv, mf = half_tube("y", (0.0, 0.0, w.Z_MAIN), w.R_MAIN - 0.012, w.R_MAIN, w.Y_WELL + 0.2, y_end)
        self.main = K.new_object("Supply main", mv, mf, pvc)
        cv, cf = half_core("y", (0.0, 0.0, w.Z_MAIN), w.R_MAIN - 0.015, w.Y_WELL + 0.2, y_end)
        self.main_water = K.new_object("Water in the main", cv, cf, self.water)
        for ob in (self.main, self.main_water):
            ob.parent = sink_root
        # the well: casing (fixed to the deep ground), screen, pump; its cover in the road rides with the ground
        top = -0.12
        sv, sf = half_tube("z", (0.0, w.Y_WELL, 0.0), w.R_CASING - 0.014, w.R_CASING, w.Z_SCREEN[0] - 0.4, top)
        self.casing = K.new_object("Well casing", sv, sf, steel)
        slot_m = base.material("Screen slots", (0.02, 0.02, 0.02), rough=0.6)
        slots = [((-0.001, w.Y_WELL + sy * (w.R_CASING - 0.007), z), (0.002, 0.016, 0.05)) for z in np.arange(w.Z_SCREEN[0], w.Z_SCREEN[1], 0.16) for sy in (-1, 1)]
        K.boxes("Screen slots", slots, slot_m)
        wv, wf = half_core("z", (0.0, w.Y_WELL, 0.0), w.R_CASING - 0.017, w.Z_PUMP + 0.8, top - 0.02)
        self.well_water = K.new_object("Water in the well", wv, wf, self.water)
        pump_m = base.material("Pump", (0.10, 0.18, 0.30), metal=0.6, rough=0.4)
        pv, pf = half_core("z", (0.0, w.Y_WELL, 0.0), w.R_CASING - 0.03, w.Z_PUMP - 0.8, w.Z_PUMP + 0.8, shift=-0.008)
        K.new_object("Pump", pv, pf, pump_m)
        lid = K.cyl("Well cover", 0.42, 0.02, (0.0, w.Y_WELL, 0.004), cover, verts=24)
        lid.parent = sink_root
        self.drops = K.Sheet("Jet droplets", np.zeros((self._nmax() * 6, 3)), octa(self._nmax()), [drop_material()], smooth=False)

    @staticmethod
    def _nmax():
        return len(w.NOZZLE_Y) * 2 * len(w.JET_YAWS) * w.DROPS

    def set(self, t, on, section, sink, sinking):
        self.nozzles.hide_render = not on
        for ob in (self.main, self.main_water, self.risers):
            ob.hide_render = sinking
        set_values(self.water, flow=t)
        n = self._nmax()
        co = np.full((n * 6, 3), HIDE_Z)
        count = 0
        if on:
            sides = (-1.0,) if section else (-1.0, 1.0)
            p, v, _ = w.droplets(t, -1e9, 1e9, sides, sink * w.SINK_MAX)
            sp = np.linalg.norm(v, axis=1)
            ax = v / sp[:, None]
            co[: len(p) * 6] = octa_points(p, ax, np.clip(sp * 0.009, 0.012, 0.035), np.full(len(p), 0.007))
            count = len(p)
        self.drops.set(co)
        return count


class Snowfall:
    def __init__(self):
        fm, N, bsdf = principled("Snowflake", (0.95, 0.96, 1.0), rough=0.9)
        bsdf.inputs["Emission Color"].default_value = (0.85, 0.88, 1.0, 1.0)
        bsdf.inputs["Emission Strength"].default_value = 0.2
        self.nmax = len(w.NEAR) + len(w.FAR) + len(w.MACRO)
        self.flakes = K.Sheet("Snowflakes", np.zeros((self.nmax * 10, 3)), bicone(self.nmax), [fm], smooth=True)
        rm = base.material("Ripple", (0.26, 0.27, 0.29), rough=0.07)
        self.rmax = 900
        seg = 10
        faces = []
        for k in range(self.rmax):
            o = k * 2 * seg
            faces += [(o + j, o + (j + 1) % seg, o + seg + (j + 1) % seg, o + seg + j) for j in range(seg)]
        self.seg = seg
        self.ripples = K.Sheet("Ripples", np.zeros((self.rmax * 2 * seg, 3)), faces, [rm], smooth=False)

    def set(self, t, cam_loc, cam_dir, near_d, sink, splash):
        d = np.asarray(cam_dir, float)
        c = np.asarray(cam_loc, float)
        near_c = c + d * near_d
        far_c = c + d * 38.0
        macro_c = c + d * near_d if near_d < 1.6 else None
        pos, size, near, rip = w.flakes(t, near_c, far_c, sink * w.SINK_MAX, macro_c)
        n = min(len(pos), self.nmax)
        co = np.full((self.nmax * 10, 3), HIDE_Z)
        co[: n * 10] = bicone_points(pos[:n], size[:n] * 1.3, size[:n])
        self.flakes.set(co)
        rip = np.vstack([rip, splash]) if len(splash) else rip
        m = min(len(rip), self.rmax)
        rc = np.full((self.rmax * 2 * self.seg, 3), HIDE_Z)
        if m:
            ang = 2 * np.pi * np.arange(self.seg) / self.seg
            age = rip[:m, 2]
            r_out = 0.01 + 0.16 * age
            r_in = r_out - 0.0045 * (1.0 - age / 0.45) - 0.001
            ring = []
            for rr in (r_in, r_out):
                ring.append(np.stack([rip[:m, 0:1] + rr[:, None] * np.cos(ang), rip[:m, 1:2] + rr[:, None] * np.sin(ang),
                                      np.full((m, self.seg), 0.003 - sink * w.SINK_MAX)], axis=2))
            rc[: m * 2 * self.seg] = np.concatenate(ring, axis=1).reshape(-1, 3)
        self.ripples.set(rc)
        return n, m


class HeatPipes:
    """The newer design: a serpentine of pipes in the base course under the asphalt, warm water running through."""

    def __init__(self, sink_root):
        self.mat = flow_material("Heat pipe water", (1.0, 0.45, 0.14), speed=0.8)
        pts = []
        ys = np.arange(w.PIPE_Y[0] + 0.3, w.PIPE_Y[1] - 0.3, w.PIPE_PITCH)
        xe = w.ROAD_HALF - 0.25
        for k, y in enumerate(ys):
            a, b = (-xe, xe) if k % 2 == 0 else (xe, -xe)
            seg = np.linspace(a, b, 24)
            pts += [(x, y, w.PIPE_Z) for x in seg]
            if k < len(ys) - 1:
                cx = b
                for th in np.linspace(-math.pi / 2, math.pi / 2, 7)[1:-1]:
                    s = 1.0 if b > 0 else -1.0
                    pts.append((cx + s * (w.PIPE_PITCH / 2) * math.cos(th), y + w.PIPE_PITCH / 2 + (w.PIPE_PITCH / 2) * math.sin(th), w.PIPE_Z))
        co, faces = sweep(pts, w.R_HEAT, 6)
        self.ob = np_mesh("Heat pipes", co, faces, [self.mat], smooth=True)
        self.ob.parent = sink_root

    def set(self, on, t):
        self.ob.hide_render = not on
        set_values(self.mat, flow=t)


class Car:
    def __init__(self, root, wheels, geom):
        self.root, self.wheels, self.r = root, wheels, geom["tyre_radius"]
        parts = [o for o in root.children_recursive if o.type == "MESH"]
        lamp_mats = {}
        for o in parts:
            for m in o.data.materials:
                if m is not None and m.name.split(".")[0] in ("lamp", "tail"):
                    lamp_mats[m.name] = m
        wheel_nodes = {wv["node"] for wv in wheels.values()}
        body_parts = [o for o in parts if not any(p in wheel_nodes for p in rb._ancestors(o))]
        ghost = rb.Ghost(body_parts)
        ghost.set_tint(PAINT)
        ghost.set_factor(0.0, 1e4, 4.0)
        for o in parts:
            for m in o.data.materials:
                if m is None:
                    continue
                key = m.name.split(".")[0].replace(" ghost", "")
                if key in ("lamp", "tail"):
                    b = m.node_tree.nodes.get("Principled BSDF")
                    if b is not None:
                        b.inputs["Emission Color"].default_value = (1.0, 0.95, 0.85, 1) if key == "lamp" else (1.0, 0.04, 0.02, 1)
                        b.inputs["Emission Strength"].default_value = 40.0 if key == "lamp" else 18.0
        self.lights = []
        for sx in (-1, 1):
            sd = bpy.data.lights.new("Headlight", "SPOT")
            sd.energy, sd.spot_size, sd.spot_blend, sd.color, sd.shadow_soft_size = 260.0, math.radians(55), 0.75, (0.95, 0.97, 1.0), 0.05
            so = bpy.data.objects.new("Headlight", sd)
            bpy.context.collection.objects.link(so)
            so.parent = root
            so.location = (sx * 0.52, geom["nose"] + 0.05, 0.66)
            so.rotation_euler = (math.radians(83.0), 0.0, 0.0)
            so.scale = (1.0, 0.4, 1.0)                                   # a wide, flat low beam
            td = bpy.data.lights.new("Tail light", "POINT")
            td.energy, td.color, td.shadow_soft_size = 4.0, (1.0, 0.05, 0.02), 0.05
            to = bpy.data.objects.new("Tail light", td)
            bpy.context.collection.objects.link(to)
            to.parent = root
            to.location = (sx * 0.52, -geom["tail"] - 0.08, 0.66)
            self.lights += [so, to]
        self.objs = [root, *root.children_recursive]

    def set(self, t, visible):
        y = w.car_y(t)
        show = visible and y is not None
        for ob in self.objs:
            ob.hide_render = not show
        if not show:
            self.root.location = (0.0, 0.0, HIDE_Z)
            return None
        self.root.location = (w.LANE_X, y, 0.0)
        self.root.rotation_euler = (0.0, 0.0, math.pi)
        spin = -(w.CAR_V * t) / self.r
        for wv in self.wheels.values():
            wv["node"].rotation_euler = (spin % (2 * math.pi), 0.0, 0.0)
        return round(y, 4)


def main():
    args = arguments()
    args.out.mkdir(parents=True, exist_ok=True)
    car_root, _body, wheels, geom = base.load_source_car(args.source)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    scene.cycles.transparent_max_bounces = 16
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Punchy"
    scene.view_settings.exposure = 0.6
    dusk_world(scene)
    sink_root = bpy.data.objects.new("Ground that sinks", None)
    scene.collection.objects.link(sink_root)
    ground = Ground(sink_root)
    town = Town(sink_root)
    build_mountains()
    spr = Sprinklers(sink_root)
    snow = Snowfall()
    pipes = HeatPipes(sink_root)
    car = Car(car_root, wheels, geom)
    fd = bpy.data.lights.new("Section fill", "AREA")
    fd.energy, fd.size, fd.color = 6000.0, 10.0, (1.0, 0.95, 0.9)
    fill = bpy.data.objects.new("Section fill", fd)
    scene.collection.objects.link(fill)
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    right = ground.right + town.right
    segs = tl.segments()
    print("SNOWMELT_SCENE " + json.dumps({"objects": len(bpy.data.objects), "houses": town.counts, "lamps": len(town.lamps)}), flush=True)

    def render(sh, path):
        scene.render.resolution_x, scene.render.resolution_y = round(FRAME[0] * args.res_scale), round(FRAME[1] * args.res_scale)
        t = sh["t"]
        section, pipes_on, sink = bool(sh.get("section")), bool(sh.get("pipes")), float(sh.get("sink", 0.0))
        for ob in right:
            ob.hide_render = section
        ground.far_side.hide_render = not section
        sink_root.location = (0.0, 0.0, -w.SINK_MAX * sink)
        span = w.Z_SOIL_BOT - w.Z_AQ_TOP
        ground.clay.scale = (1.0, 1.0, (span - w.SINK_MAX * sink) / span)
        set_values(ground.street, spray=0.0 if pipes_on else 1.0, flow=t, pipes=1.0 if pipes_on else 0.0)
        set_values(ground.strata, drained=sink)
        n_drops = spr.set(t, not pipes_on, section, sink, bool(sh.get("sinking")))
        pipes.set(pipes_on, t)
        car_y = car.set(t, not section)
        c = sh["cam"]
        loc, tgt = Vector(c["loc"]), Vector(c["target"])
        dvec = (tgt - loc).normalized()
        splash = np.zeros((0, 3))
        if not pipes_on:
            fy = float(loc.y + 2.5 * dvec.y)
            splash = w.splashes(t, fy - 5.0, fy + 5.0, (-1.0,) if section else (-1.0, 1.0), sink * w.SINK_MAX, age_max=0.2)
            near = np.hypot(splash[:, 0] - loc.x, splash[:, 1] - loc.y) < 6.0
            splash = splash[near]
        n_flakes, n_rip = snow.set(t, loc, dvec, min(6.0, 0.5 * (tgt - loc).length), sink, splash)
        fill.hide_render = not section
        fill.location = Vector((min(loc.x, 7.0), loc.y - 3.0, loc.z + 4.0))
        fill.rotation_euler = (Vector((-1.0, 0.25, -0.35))).to_track_quat("-Z", "Y").to_euler()
        dd = cam.data
        dd.sensor_fit, dd.sensor_width, dd.lens, dd.clip_start = "HORIZONTAL", 36.0, c["lens"], 0.02
        dd.clip_end = 12000.0
        dd.dof.use_dof = True
        dd.dof.focus_distance = (tgt - loc).length
        dd.dof.aperture_fstop = c.get("fstop", 8.0)
        base.set_camera(cam, loc, tgt)
        bpy.context.view_layer.update()
        lo, hi = tl.subject_box(t)
        box = hook_gate.project_box(scene, cam, Matrix.Identity(4), lo, hi)
        from bpy_extras.object_utils import world_to_camera_view
        seen, nearest = 0, 1e9
        if not pipes_on:
            for y in w.NOZZLE_Y:
                p = Vector((0.0, float(y), -w.SINK_MAX * sink))
                v = world_to_camera_view(scene, cam, p)
                if v.z > 0 and 0.0 <= v.x <= 1.0 and 0.0 <= v.y <= 1.0:
                    seen += 1
                    nearest = min(nearest, (p - loc).length)
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        return {"t": round(t, 6), "section": section, "pipes": pipes_on, "sink": round(sink, 6), "car_y": car_y, "droplets": n_drops,
                "flakes": n_flakes, "ripples": n_rip, "nozzles_in_view": seen, "nearest_nozzle_m": round(nearest, 3) if seen else None,
                "subject_box": box, "cam_world": [round(v, 3) for v in loc], "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

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
        print("SNOWMELT_FRAME " + json.dumps(info), flush=True)
    (args.out / f"snowmelt-frames-{frames[0]:05d}.json").write_text(json.dumps({"renderer_source_sha256": src_sha, "frames": out}, indent=1))


if __name__ == "__main__":
    main()
