"""EP.26 rolling barrier: 100 % 3D renderer (Blender, Cycles CPU), house style of EP.13-EP.25 (low sun, depth of field). A two-lane
mountain road (yellow centre line) winds along a forested hillside; on its downhill side runs the rolling barrier: yellow foam rollers,
two to a shaft, with black stripes so their turning shows, held by a steel frame (rails, brackets and posts). Above the road a rock
cut, below it a steep wooded slope into the valley, mountain ridges far off, a curve warning sign before the sharp left bend.

Everything moves from roller_motion and the layout from roller_world: the CC0 red sedan comes down the straight too fast, does not
make the bend and slides into the rollers at 25 degrees; its path, heading and wheel turn; each roller pair's spin (spun up as the
car's side passes, spinning down after); the foam squashing where the car presses and the posts and rails giving way and springing
back; the tyre marks of the slide; the driver's recovery. Shot C swaps in a plain steel W-beam rail that bends back while the car
scrapes it and throws sparks. The section shot cuts one pair of rollers open: a yellow skin, tough foam inside, a steel sleeve on
the shaft. No text anywhere in the scene."""
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
from mathutils import Matrix, Vector, kdtree

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from benchmarks import hook_gate  # noqa: E402
from benchmarks.belt_limiter import render_belt_3d as rb  # noqa: E402  (car paint tint)
from benchmarks.can_opener import render_opener_3d as K  # noqa: E402  (data-API mesh helpers)
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402
from benchmarks.rock_net.render_rocknet_3d import textured  # noqa: E402
from benchmarks.roller_barrier import roller_motion as rm  # noqa: E402
from benchmarks.roller_barrier import roller_timeline as tl  # noqa: E402
from benchmarks.roller_barrier import roller_world as rw  # noqa: E402

material = base.material
FRAME = (1080, 1920)
PAINT = (1.75, 0.30, 0.24)
R = rm.ROLL_R
ROLLERS_Z = ((0.20, 0.56), (0.60, 0.96))          # the two rollers on a shaft (bottom, top)
SHAFT = (0.028, 0.10, 1.04)                        # radius, bottom, top
HOLE = 0.042
RAIL_OFF, RAIL_Z, RAIL_W, RAIL_H = 0.27, (0.14, 0.58, 1.00), 0.07, 0.08
POST_OFF, POST_EVERY = 0.37, 4
DYN_K = (-6, 22)                                   # rollers that can be hit: their own meshes (spin, squash, give)
HERO_S = (-60.0, 85.0)                             # full-detail barrier; low detail beyond
K_CUT = 4                                          # the pair cut open in the section shot
CUT_DIR = math.radians(-144.0)                     # the cut faces the section camera
STEEL_S = (-60.0, 70.0)
STEEL_POST = 1.905
SEG_HI, SEG_LO = 30, 12


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


# ------------------------------------------------------------------ fast meshes (numpy through the data API)
def np_mesh(name, co, faces, mats, mat_idx=None, smooth=False, link=True):
    """faces: list of index sequences (any sizes)."""
    sizes = np.array([len(f) for f in faces], dtype=np.int32)
    flat = np.fromiter((i for f in faces for i in f), dtype=np.int32, count=int(sizes.sum()))
    return np_mesh_flat(name, co, flat, sizes, mats, mat_idx, smooth, link)


def np_mesh_flat(name, co, flat, sizes, mats, mat_idx=None, smooth=False, link=True):
    me = bpy.data.meshes.new(name)
    co = np.asarray(co, dtype=np.float32)
    me.vertices.add(len(co))
    me.vertices.foreach_set("co", co.ravel())
    me.loops.add(len(flat))
    me.loops.foreach_set("vertex_index", np.asarray(flat, dtype=np.int32))
    me.polygons.add(len(sizes))
    me.polygons.foreach_set("loop_start", np.concatenate([[0], np.cumsum(sizes)[:-1]]).astype(np.int32))
    me.update(calc_edges=True)
    for m in mats:
        me.materials.append(m)
    if mat_idx is not None:
        me.polygons.foreach_set("material_index", np.asarray(mat_idx, dtype=np.int32))
    if smooth:
        me.polygons.foreach_set("use_smooth", np.ones(len(sizes), dtype=bool))
    ob = bpy.data.objects.new(name, me)
    if link:
        bpy.context.collection.objects.link(ob)
    return ob


class Proto:
    """A part made once (local coordinates) and stamped many times."""

    def __init__(self, co, faces, mat_idx=None):
        self.co = np.asarray(co, dtype=np.float64)
        self.sizes = np.array([len(f) for f in faces], dtype=np.int32)
        self.flat = np.array([i for f in faces for i in f], dtype=np.int32)
        self.mi = np.zeros(len(faces), dtype=np.int32) if mat_idx is None else np.asarray(mat_idx, dtype=np.int32)

    def __add__(self, other):
        n = len(self.co)
        out = Proto.__new__(Proto)
        out.co = np.vstack([self.co, other.co])
        out.sizes = np.concatenate([self.sizes, other.sizes])
        out.flat = np.concatenate([self.flat, other.flat + n])
        out.mi = np.concatenate([self.mi, other.mi])
        return out


def stamp(name, proto: Proto, mats, xforms, smooth=False):
    """xforms: list of (3, 3) rotation, (3,) translation."""
    n = len(proto.co)
    cos, flats = [], []
    for k, (rot, tr) in enumerate(xforms):
        cos.append(proto.co @ np.asarray(rot).T + np.asarray(tr))
        flats.append(proto.flat + k * n)
    co = np.vstack(cos) if cos else np.zeros((0, 3))
    flat = np.concatenate(flats) if flats else np.zeros(0, dtype=np.int32)
    sizes = np.tile(proto.sizes, len(xforms))
    mi = np.tile(proto.mi, len(xforms))
    return np_mesh_flat(name, co, flat, sizes, mats, mi, smooth)


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def barrier_frame(h):
    """Local barrier frame (lx outward, away from the road; ly along the road; z up) to world, for heading h."""
    c, s = math.cos(h), math.sin(h)
    return np.array([[c, s, 0.0], [-s, c, 0.0], [0.0, 0.0, 1.0]])


def box_proto(c, d, mi=0):
    return Proto(K.box_verts(c, d), K.BOX_FACES, [mi] * 6)


def cyl_proto(r, z0, z1, n=10, mi=0, center=(0.0, 0.0)):
    co = [(center[0] + r * math.cos(2 * math.pi * k / n), center[1] + r * math.sin(2 * math.pi * k / n), z) for z in (z0, z1) for k in range(n)]
    faces = [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)] + [tuple(reversed(range(n))), tuple(range(n, 2 * n))]
    return Proto(co, faces, [mi] * len(faces))


# ------------------------------------------------------------------ rollers
def roller_proto(z0, z1, n_seg=SEG_HI, a0=0.0, span=2 * math.pi, cut=False):
    """One foam roller around the local z axis: rounded edges, a hole for the shaft; faces 0 = yellow, 1 = black stripe; with cut,
    only `span` of the turn from a0 and the two cut faces (3 = foam)."""
    if n_seg >= 20:
        prof = [(HOLE, z0), (0.80 * R, z0), (0.95 * R, z0 + 0.008), (R, z0 + 0.035), (R, 0.5 * (z0 + z1)), (R, z1 - 0.035),
                (0.95 * R, z1 - 0.008), (0.80 * R, z1), (HOLE, z1)]
    else:
        prof = [(HOLE, z0), (R, z0), (R, z1), (HOLE, z1)]
    m = len(prof)
    closed = not cut
    n_ang = n_seg if closed else n_seg + 1
    co = []
    for j in range(n_ang):
        a = a0 + span * j / n_seg
        for r_, z in prof:
            co.append((r_ * math.cos(a), r_ * math.sin(a), z))
    faces, mi = [], []
    stripe_every = n_seg // 3 if closed else max(1, int(round(n_seg * 2 * math.pi / span)) // 3)
    width = 2 if n_seg >= 20 else 1
    for j in range(n_seg):
        j1 = (j + 1) % n_ang
        tag = 1 if (j % stripe_every) < width else 0
        for i in range(m):
            i1 = (i + 1) % m
            faces.append((j * m + i, j1 * m + i, j1 * m + i1, j * m + i1))
            mi.append(tag if i < m - 1 else 0)
    if cut:
        faces.append(tuple(range(m))[::-1])
        mi.append(3)
        last = n_seg * m
        faces.append(tuple(last + i for i in range(m)))
        mi.append(3)
    return Proto(co, faces, mi)


def pair_proto(n_seg=SEG_HI):
    p = roller_proto(*ROLLERS_Z[0], n_seg=n_seg) + roller_proto(*ROLLERS_Z[1], n_seg=n_seg)
    return p


def shaft_and_brackets(detail=True):
    p = cyl_proto(SHAFT[0], SHAFT[1], SHAFT[2], n=8 if detail else 6, mi=2)
    for z in RAIL_Z:
        p = p + box_proto(((RAIL_OFF - 0.035) / 2 + 0.01, 0.0, z), (RAIL_OFF - 0.035 - 0.02, 0.05, 0.03), 2)
    return p


def roller_material():
    yellow = material("Roller foam skin", (1.0, 0.66, 0.015), rough=0.42)
    s = yellow.node_tree.nodes.get("Principled BSDF")
    if "Coat Weight" in s.inputs:
        s.inputs["Coat Weight"].default_value = 0.25
    black = material("Roller stripe", (0.018, 0.018, 0.02), rough=0.5)
    steel = material("Galvanised steel", (0.56, 0.58, 0.60), metal=0.75, rough=0.38)
    blur = material("Roller foam (spinning fast)", (0.80, 0.53, 0.013), rough=0.45)   # the stripes smear into one colour on camera
    foam = bpy.data.materials.new("Roller foam (cut)")
    foam.use_nodes = True
    nt = foam.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = 0.85
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    rr = nt.nodes.new("ShaderNodeVectorMath")
    rr.operation = "LENGTH"
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(sep.outputs["X"], comb.inputs["X"])
    nt.links.new(sep.outputs["Y"], comb.inputs["Y"])
    nt.links.new(comb.outputs["Vector"], rr.inputs[0])
    skin = nt.nodes.new("ShaderNodeMapRange")
    skin.inputs["From Min"].default_value, skin.inputs["From Max"].default_value = R - 0.016, R - 0.011
    nt.links.new(rr.outputs["Value"], skin.inputs["Value"])
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 260.0
    nt.links.new(tc.outputs["Object"], vor.inputs["Vector"])
    cells = nt.nodes.new("ShaderNodeValToRGB")
    cells.color_ramp.elements[0].color = (0.78, 0.60, 0.16, 1)
    cells.color_ramp.elements[1].color = (0.95, 0.80, 0.34, 1)
    nt.links.new(vor.outputs["Distance"], cells.inputs["Fac"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    nt.links.new(skin.outputs["Result"], mix.inputs["Factor"])
    nt.links.new(cells.outputs["Color"], mix.inputs["A"])
    mix.inputs["B"].default_value = (1.0, 0.66, 0.015, 1)
    nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.35
    nt.links.new(vor.outputs["Distance"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], bsdf.inputs["Normal"])
    return [yellow, black, steel, foam, blur]


class Barrier:
    """Rolling barrier along the road's right edge: static pairs (full detail near the crash, low detail beyond), the pairs that can
    be hit as their own meshes, the frame (rails, brackets, posts) static outside the crash zone and giving way inside it."""

    def __init__(self, mats_r):
        self.mats = mats_r
        steel = mats_r[2]
        k0, k1 = rw.k_range()
        P, H, KS = rw.roller_stations(k0, k1 + 1)
        self.k_index = {int(k): i for i, k in enumerate(KS)}
        self.P, self.H, self.KS = P, H, KS
        rng = np.random.default_rng(2626)
        self.phase = rng.uniform(0, 2 * math.pi, len(KS))
        hi = pair_proto(SEG_HI)
        lo = pair_proto(SEG_LO)
        sb_hi, sb_lo = shaft_and_brackets(True), shaft_and_brackets(False)
        s_of = (KS + 0.5) * rm.ROLL_PITCH
        x_hi, x_lo = [], []
        for i, k in enumerate(KS):
            if DYN_K[0] <= k < DYN_K[1]:
                continue
            frame = barrier_frame(H[i])
            rot = frame @ rot_z(self.phase[i])
            tr = np.array([P[i, 0], P[i, 1], 0.0])
            (x_hi if HERO_S[0] <= s_of[i] <= HERO_S[1] else x_lo).append((rot, tr, frame))
        self.static = [stamp("Rollers (near)", hi, mats_r, [(r, t) for r, t, _ in x_hi], smooth=True),
                       stamp("Rollers (far)", lo, mats_r, [(r, t) for r, t, _ in x_lo], smooth=True),
                       stamp("Shafts (near)", sb_hi, mats_r, [(f, t) for _, t, f in x_hi]),
                       stamp("Shafts (far)", sb_lo, mats_r, [(f, t) for _, t, f in x_lo])]
        # the pairs that can be hit: their own meshes, rewritten every frame
        self.dyn = []
        pr = hi
        sb = sb_hi
        for k in range(*DYN_K):
            i = self.k_index[k]
            co = np.vstack([pr.co, sb.co])
            flat = np.concatenate([pr.flat, sb.flat + len(pr.co)])
            sizes = np.concatenate([pr.sizes, sb.sizes])
            mi = np.concatenate([pr.mi, sb.mi])
            ob = np_mesh_flat(f"Roller pair {k}", co, flat, sizes, mats_r, mi, smooth=True)
            mi_blur = mi.copy()
            mi_blur[:len(pr.sizes)] = 4
            self.dyn.append({"k": k, "i": i, "ob": ob, "n_roll": len(pr.co), "roll": pr.co.copy(), "fixed": sb.co.copy(), "s": (k + 0.5) * rm.ROLL_PITCH,
                             "mi": mi, "mi_blur": mi_blur, "blur": False})
        # the frame: rails (ribbons of box section) and posts; inside the crash zone as one mesh that gives way
        ax, hs, s_ax = rw.barrier_axis()
        self.ax, self.hs, self.s_ax = ax, np.unwrap(hs), s_ax
        s_dyn = (self.dyn[0]["s"] - 1.5, self.dyn[-1]["s"] + 1.5)
        self.s_dyn = s_dyn
        st_parts = []
        for a, b, step in ((s_ax[0] + 0.3, HERO_S[0], 1.5), (HERO_S[0], s_dyn[0], 0.25), (s_dyn[1], HERO_S[1], 0.5), (HERO_S[1], s_ax[-1] - 0.3, 1.5)):
            n = max(2, int(round((b - a) / step)) + 1)
            st_parts.append(self._rails(np.linspace(a, b, n)))
        post_s = s_of[::POST_EVERY] + 0.5 * rm.ROLL_PITCH
        posts_static = [s for s in post_s if not (s_dyn[0] <= s <= s_dyn[1])]
        self.post_proto = box_proto((0.0, 0.0, 0.24), (0.12, 0.15, 1.68), 2)
        st_parts.append(self._posts(posts_static))
        co = np.vstack([p[0] for p in st_parts])
        flat, sizes, off = [], [], 0
        for c, f, sz in st_parts:
            flat.append(f + off)
            sizes.append(sz)
            off += len(c)
        np_mesh_flat("Barrier frame", co, np.concatenate(flat), np.concatenate(sizes), [steel])
        # crash zone frame: vertices carry their station s and outward normal so they can give way
        rs = np.arange(s_dyn[0], s_dyn[1] + 1e-6, 0.1375)
        c1, f1, z1 = self._rails(rs)
        dyn_posts = [s for s in post_s if s_dyn[0] <= s <= s_dyn[1]]
        c2, f2, z2 = self._posts(dyn_posts)
        self.frame_co = np.vstack([c1, c2])
        self.frame_s = np.concatenate([self._rail_s, self._post_s])
        self.frame_post = np.concatenate([np.zeros(len(c1), bool), np.ones(len(c2), bool)])
        h = np.interp(self.frame_s, s_ax, self.hs)
        self.frame_n = np.stack([np.cos(h), -np.sin(h), np.zeros_like(h)], 1)
        self.frame_ob = np_mesh_flat("Barrier frame (crash zone)", self.frame_co, np.concatenate([f1, f2 + len(c1)]), np.concatenate([z1, z2]), [steel])
        # the cut-open pair for the section shot
        i = self.k_index[K_CUT]
        a0 = CUT_DIR + math.radians(45.0)
        cut = roller_proto(*ROLLERS_Z[0], n_seg=24, a0=a0, span=math.radians(270.0), cut=True) + \
            roller_proto(*ROLLERS_Z[1], n_seg=24, a0=a0, span=math.radians(270.0), cut=True)
        sleeve = cyl_proto(HOLE * 0.98, ROLLERS_Z[0][0] - 0.01, ROLLERS_Z[1][1] + 0.01, n=16, mi=2)
        whole = cut + sleeve + shaft_and_brackets(True)
        self.cutaway = np_mesh_flat("Roller pair cut open", whole.co, whole.flat, whole.sizes, mats_r, whole.mi, smooth=False)
        self.cutaway.location = (P[i, 0], P[i, 1], 0.0)
        self.cutaway.rotation_euler = (0.0, 0.0, -H[i])
        self.cutaway.hide_render = True
        self.all = self.static + [d["ob"] for d in self.dyn] + [self.frame_ob, bpy.data.objects["Barrier frame"]]

    def _station(self, s):
        x = np.interp(s, self.s_ax, self.ax[:, 0])
        y = np.interp(s, self.s_ax, self.ax[:, 1])
        h = np.interp(s, self.s_ax, self.hs)
        return x, y, h

    def _rails(self, ss):
        ss = np.asarray(ss, float)
        x, y, h = self._station(ss)
        nx, ny = np.cos(h), -np.sin(h)
        cos_, sizes_, flat_ = [], [], []
        svals = []
        n = len(ss)
        base = 0
        for z in RAIL_Z:
            corners = [(RAIL_OFF - RAIL_W / 2, z - RAIL_H / 2), (RAIL_OFF + RAIL_W / 2, z - RAIL_H / 2), (RAIL_OFF + RAIL_W / 2, z + RAIL_H / 2),
                       (RAIL_OFF - RAIL_W / 2, z + RAIL_H / 2)]
            co = np.zeros((n * 4, 3))
            for j, (u, zz) in enumerate(corners):
                co[j::4, 0] = x + u * nx
                co[j::4, 1] = y + u * ny
                co[j::4, 2] = zz
            cos_.append(co)
            svals.append(np.repeat(ss, 4))
            i = np.arange(n - 1)[:, None] * 4
            quads = []
            for j in range(4):
                j1 = (j + 1) % 4
                quads.append(np.concatenate([i + j, i + 4 + j, i + 4 + j1, i + j1], 1))
            q = np.vstack(quads) + base
            flat_.append(q.ravel())
            sizes_.append(np.full(len(q), 4, dtype=np.int32))
            base += len(co)
        self._rail_s = np.concatenate(svals)
        return np.vstack(cos_), np.concatenate(flat_).astype(np.int32), np.concatenate(sizes_)

    def _posts(self, ss):
        cos_, flat_, sizes_, svals = [], [], [], []
        off = 0
        for s in ss:
            x, y, h = self._station(s)
            frame = barrier_frame(float(h))
            co = (self.post_proto.co + np.array([POST_OFF, 0.0, 0.0])) @ frame.T + np.array([x, y, 0.0])
            cos_.append(co)
            flat_.append(self.post_proto.flat + off)
            sizes_.append(self.post_proto.sizes)
            svals.append(np.full(len(co), s))
            off += len(co)
        self._post_s = np.concatenate(svals) if svals else np.zeros(0)
        if not cos_:
            return np.zeros((0, 3)), np.zeros(0, dtype=np.int32), np.zeros(0, dtype=np.int32)
        return np.vstack(cos_), np.concatenate(flat_), np.concatenate(sizes_)

    def show(self, on: bool, section: bool):
        for ob in self.all:
            ob.hide_render = not on
        if on and section:
            self.dyn[K_CUT - DYN_K[0]]["ob"].hide_render = True
        self.cutaway.hide_render = not (on and section)

    def set(self, t: float, active: bool, time_scale: float) -> dict:
        """time_scale: simulated seconds per film second; a roller turning more than 40 degrees a frame on camera is drawn smeared."""
        ys = np.array([d["s"] for d in self.dyn])
        if active:
            sq, gv = rm.barrier_state(t, ys, "roller")
        else:
            sq, gv = np.zeros_like(ys), np.zeros_like(ys)
        spinning = blurred = 0
        spun = rm.crash("roller")["spun"]
        for j, d in enumerate(self.dyn):
            i, k = d["i"], d["k"]
            spin = rm.roller_spin(k, t) if active else 0.0
            w = 0.0
            if active and k in spun and t > spun[k][0]:
                w = spun[k][1] / R * math.exp(-(t - spun[k][0]) / rm.SPIN_TAU)
                spinning += int(w > 1.0)
            blur = w * abs(time_scale) / tl.FPS > math.radians(40.0)
            if blur != d["blur"]:
                d["ob"].data.polygons.foreach_set("material_index", d["mi_blur"] if blur else d["mi"])
                d["blur"] = blur
            blurred += int(blur)
            ang = self.phase[i] - spin
            loc = d["roll"] @ rot_z(ang).T
            s_ = float(sq[j])
            if s_ > 1e-4:                                           # the foam flattens where the car presses (the road side is -lx)
                front = -(R - s_)
                u = loc[:, 0].copy()
                loc[:, 0] = np.maximum(u, front)
                loc[:, 1] *= 1.0 + 0.45 * (s_ / R) * np.clip(-u / R, 0, 1) ** 2
            g = float(gv[j])
            loc[:, 0] += g
            fixed = d["fixed"].copy()
            fixed[:, 0] += g
            frame = barrier_frame(self.H[i])
            tr = np.array([self.P[i, 0], self.P[i, 1], 0.0])
            co = np.vstack([loc, fixed]) @ frame.T + tr
            me = d["ob"].data
            me.vertices.foreach_set("co", co.astype(np.float32).ravel())
            me.update()
        give = np.interp(self.frame_s, ys, gv, left=0.0, right=0.0)
        z = self.frame_co[:, 2]
        bend = np.where(self.frame_post, np.clip((z + 0.1) / 0.7, 0.0, 1.0), 1.0)
        co = self.frame_co + (give * bend)[:, None] * self.frame_n
        me = self.frame_ob.data
        me.vertices.foreach_set("co", co.astype(np.float32).ravel())
        me.update()
        return {"rollers_spinning": spinning, "rollers_blurred": blurred, "max_squash": round(float(sq.max()), 4), "max_give": round(float(gv.max()), 4)}


class SteelRail:
    """The plain steel W-beam rail for shot C, on the same line: rail, blockouts and posts; the crash zone bends back."""

    W = [(0.083, 0.395), (0.0, 0.445), (0.0, 0.49), (0.075, 0.55), (0.0, 0.61), (0.0, 0.655), (0.083, 0.705)]

    def __init__(self):
        self.mat = material("W-beam steel", (0.62, 0.64, 0.66), metal=0.8, rough=0.3)
        wood = textured("Blockout", (0.20, 0.14, 0.09), (0.30, 0.22, 0.14), 6.0, rough=0.85, bump=0.3)
        ax, hs, s_ax = rw.barrier_axis()
        self.ax, self.hs, self.s_ax = ax, np.unwrap(hs), s_ax
        ss = np.arange(STEEL_S[0], STEEL_S[1] + 1e-6, 0.25)
        x = np.interp(ss, s_ax, ax[:, 0])
        y = np.interp(ss, s_ax, ax[:, 1])
        h = np.interp(ss, s_ax, self.hs)
        nx, ny = np.cos(h), -np.sin(h)
        m = len(self.W)
        co = np.zeros((len(ss) * m, 3))
        for j, (u, z) in enumerate(self.W):
            co[j::m, 0] = x + (u - R) * nx
            co[j::m, 1] = y + (u - R) * ny
            co[j::m, 2] = z
        i = np.arange(len(ss) - 1)[:, None] * m
        quads = np.vstack([np.concatenate([i + j, i + m + j, i + m + j + 1, i + j + 1], 1) for j in range(m - 1)])
        self.ob = np_mesh_flat("W-beam rail", co, quads.ravel(), np.full(len(quads), 4, np.int32), [self.mat], smooth=False)
        sol = self.ob.modifiers.new("Thickness", "SOLIDIFY")
        sol.thickness = 0.005
        self.base = co
        self.s = np.repeat(ss, m)
        self.n = np.stack([np.repeat(nx, m), np.repeat(ny, m), np.zeros(len(co))], 1)
        posts = np.arange(STEEL_S[0] + 0.5, STEEL_S[1], STEEL_POST)
        parts_p, parts_b = [], []
        post = box_proto((0.0, 0.0, 0.05), (0.10, 0.15, 1.5), 0)
        blk = box_proto((0.0, 0.0, 0.55), (0.20, 0.15, 0.36), 0)
        self.p_base, self.p_s, self.b_base, self.b_s = [], [], [], []
        for s in posts:
            xx, yy, hh = (float(np.interp(s, s_ax, ax[:, 0])), float(np.interp(s, s_ax, ax[:, 1])), float(np.interp(s, s_ax, self.hs)))
            fr = barrier_frame(hh)
            cp = (post.co + np.array([-R + 0.083 + 0.20 + 0.05, 0.0, 0.0])) @ fr.T + np.array([xx, yy, 0.0])
            cb = (blk.co + np.array([-R + 0.083 + 0.10, 0.0, 0.0])) @ fr.T + np.array([xx, yy, 0.0])
            parts_p.append(cp)
            parts_b.append(cb)
        nposts = len(posts)
        self.posts = np_mesh_flat("W-beam posts", np.vstack(parts_p), np.concatenate([post.flat + k * 8 for k in range(nposts)]),
                                  np.tile(post.sizes, nposts), [self.mat])
        self.blocks = np_mesh_flat("W-beam blockouts", np.vstack(parts_b), np.concatenate([blk.flat + k * 8 for k in range(nposts)]),
                                   np.tile(blk.sizes, nposts), [wood])
        self.pb = np.vstack(parts_p)
        self.bb = np.vstack(parts_b)
        self.ps = np.repeat(posts, 8)
        hp = np.interp(self.ps, s_ax, self.hs)
        self.pn = np.stack([np.cos(hp), -np.sin(hp), np.zeros_like(hp)], 1)
        self.obs = [self.ob, self.posts, self.blocks]

    def show(self, on):
        for ob in self.obs:
            ob.hide_render = not on

    def set(self, t):
        ys = (np.arange(*DYN_K) + 0.5) * rm.ROLL_PITCH
        _, gv = rm.barrier_state(t, ys, "steel")
        give = np.interp(self.s, ys, gv, left=0.0, right=0.0)
        co = self.base + give[:, None] * self.n
        self.ob.data.vertices.foreach_set("co", co.astype(np.float32).ravel())
        self.ob.data.update()
        gp = np.interp(self.ps, ys, gv, left=0.0, right=0.0)
        bend = np.clip((self.pb[:, 2] + 0.1) / 0.7, 0.0, 1.0)
        for ob, b, bb in ((self.posts, self.pb, bend), (self.blocks, self.bb, np.ones(len(self.bb)))):
            c = b + (gp * bb)[:, None] * self.pn
            ob.data.vertices.foreach_set("co", c.astype(np.float32).ravel())
            ob.data.update()
        return round(float(gv.max()), 4)


# ------------------------------------------------------------------ the land
def ground_material():
    m = bpy.data.materials.new("Hillside ground")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = 0.93
    tc = nt.nodes.new("ShaderNodeTexCoord")
    rock_a = nt.nodes.new("ShaderNodeAttribute")
    rock_a.attribute_name = "rock"
    dirt_a = nt.nodes.new("ShaderNodeAttribute")
    dirt_a.attribute_name = "dirt"
    fine = nt.nodes.new("ShaderNodeTexNoise")
    fine.inputs["Scale"].default_value = 1.6
    fine.inputs["Detail"].default_value = 10.0
    nt.links.new(tc.outputs["Object"], fine.inputs["Vector"])
    big = nt.nodes.new("ShaderNodeTexNoise")
    big.inputs["Scale"].default_value = 0.02
    big.inputs["Detail"].default_value = 4.0
    nt.links.new(tc.outputs["Object"], big.inputs["Vector"])
    rock = nt.nodes.new("ShaderNodeValToRGB")
    rock.color_ramp.elements[0].color, rock.color_ramp.elements[1].color = (0.12, 0.115, 0.105, 1), (0.27, 0.25, 0.22, 1)
    nt.links.new(fine.outputs["Fac"], rock.inputs["Fac"])
    canopy = nt.nodes.new("ShaderNodeTexNoise")                     # from afar the forest floor reads as tree canopy
    canopy.inputs["Scale"].default_value = 0.25
    canopy.inputs["Detail"].default_value = 6.0
    nt.links.new(tc.outputs["Object"], canopy.inputs["Vector"])
    floor = nt.nodes.new("ShaderNodeValToRGB")
    floor.color_ramp.elements[0].position, floor.color_ramp.elements[1].position = 0.35, 0.65
    floor.color_ramp.elements[0].color, floor.color_ramp.elements[1].color = (0.012, 0.032, 0.012, 1), (0.05, 0.09, 0.03, 1)
    nt.links.new(canopy.outputs["Fac"], floor.inputs["Fac"])
    soil = nt.nodes.new("ShaderNodeValToRGB")
    soil.color_ramp.elements[0].color, soil.color_ramp.elements[1].color = (0.10, 0.08, 0.05, 1), (0.20, 0.17, 0.10, 1)
    nt.links.new(fine.outputs["Fac"], soil.inputs["Fac"])
    mix0 = nt.nodes.new("ShaderNodeMix")
    mix0.data_type = "RGBA"
    nt.links.new(dirt_a.outputs["Fac"], mix0.inputs["Factor"])
    nt.links.new(floor.outputs["Color"], mix0.inputs["A"])
    nt.links.new(soil.outputs["Color"], mix0.inputs["B"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    nt.links.new(rock_a.outputs["Fac"], mix.inputs["Factor"])
    nt.links.new(mix0.outputs["Result"], mix.inputs["A"])
    nt.links.new(rock.outputs["Color"], mix.inputs["B"])
    nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    cb = nt.nodes.new("ShaderNodeBump")
    cb.inputs["Strength"].default_value = 0.8
    nt.links.new(canopy.outputs["Fac"], cb.inputs["Height"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.5
    nt.links.new(fine.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(cb.outputs["Normal"], bp.inputs["Normal"])
    nt.links.new(bp.outputs["Normal"], bsdf.inputs["Normal"])
    return m


class Land:
    def __init__(self):
        pts, hs, s = rw.centre_line()
        self.kd = kdtree.KDTree(len(pts))
        for i, p in enumerate(pts):
            self.kd.insert((float(p[0]), float(p[1]), 0.0), i)
        self.kd.balance()
        self.pts, self.nr = pts, rw.normals(hs)
        xs = np.concatenate([np.linspace(-3200, -1250, 9), np.arange(-1250, -420, 25.0), np.arange(-420, -140, 7.0), np.arange(-140, -32, 2.0),
                             np.arange(-32, 32, 0.5), np.arange(32, 110, 2.0), np.arange(110, 420, 7.0), np.arange(420, 1250, 25.0), np.linspace(1250, 3200, 9)])
        ys = np.concatenate([np.linspace(-3400, -1300, 9), np.arange(-1300, -560, 25.0), np.arange(-560, -290, 7.0), np.arange(-290, -50, 2.0),
                             np.arange(-50, 105, 0.5), np.arange(105, 400, 2.0), np.arange(400, 700, 7.0), np.arange(700, 1400, 25.0), np.linspace(1400, 3400, 9)])
        X, Y = np.meshgrid(xs, ys, indexing="ij")
        d = self.offset(np.stack([X.ravel(), Y.ravel()], 1))
        Z = rw.ground_z(d, X.ravel(), Y.ravel())
        co = np.stack([X.ravel(), Y.ravel(), Z], 1)
        nu, nv = len(xs), len(ys)
        i = (np.arange(nu - 1)[:, None] * nv + np.arange(nv - 1)[None, :]).ravel()
        q = np.stack([i, i + nv, i + nv + 1, i + 1], 1)
        self.ob = np_mesh_flat("Hillside", co, q.ravel(), np.full(len(q), 4, np.int32), [ground_material()], smooth=True)
        rock = np.clip((-d - 4.9) / 0.4, 0.0, 1.0) * np.clip((13.4 + d) / 1.2, 0.0, 1.0)              # the rock cut above the road
        dirt = np.clip((d - 4.8) / 0.4, 0.0, 1.0) * np.clip((8.0 - d) / 2.0, 0.0, 1.0)                # the bare bank below the barrier
        for name, val in (("rock", rock), ("dirt", dirt)):
            a = self.ob.data.attributes.new(name, "FLOAT", "POINT")
            a.data.foreach_set("value", val.astype(np.float32))

    def offset(self, p):
        out = np.empty(len(p))
        for j, (x, y) in enumerate(p):
            _, i, _ = self.kd.find((float(x), float(y), 0.0))
            out[j] = (x - self.pts[i, 0]) * self.nr[i, 0] + (y - self.pts[i, 1]) * self.nr[i, 1]
        return out


def ribbon(pts, nr, a, b, z, every=1):
    p = pts[::every]
    n = nr[::every]
    left = p + a * n
    right = p + b * n
    m = len(p)
    co = np.zeros((2 * m, 3))
    co[0::2, :2], co[1::2, :2] = left, right
    co[:, 2] = z
    i = np.arange(m - 1) * 2
    q = np.stack([i, i + 2, i + 3, i + 1], 1)
    return co, q


def build_road():
    pts, hs, _ = rw.centre_line()
    nr = rw.normals(hs)
    asphalt = textured("Asphalt", (0.075, 0.075, 0.08), (0.125, 0.125, 0.13), 4.0, rough=0.85, bump=0.15)
    yellow = material("Centre line", (0.95, 0.62, 0.05), rough=0.5)
    white = material("Edge line", (0.88, 0.88, 0.84), rough=0.5)
    gutter = textured("Concrete gutter", (0.40, 0.40, 0.38), (0.55, 0.55, 0.52), 3.0, rough=0.85, bump=0.2)
    for name, a, b, z, mat in (("Road", -3.9, 4.75, 0.0, asphalt), ("Gutter", -5.05, -3.9, 0.004, gutter),
                               ("Centre line A", -0.20, -0.07, 0.006, yellow), ("Centre line B", 0.07, 0.20, 0.006, yellow),
                               ("Edge line L", -3.55, -3.40, 0.006, white), ("Edge line R", 3.40, 3.55, 0.006, white)):
        co, q = ribbon(pts, nr, a, b, z)
        np_mesh_flat(name, co, q.ravel(), np.full(len(q), 4, np.int32), [mat])


def tree_protos():
    pine = Proto(*K.cyl_geom(0.18, 2.2, (0.0, 0.0, 1.1), (0, 0, 0), 6), [1] * 8)
    jit = random.Random(3)
    for k, (r, z0, h) in enumerate(((2.2, 1.5, 3.2), (1.9, 3.0, 3.0), (1.55, 4.5, 2.8), (1.2, 5.9, 2.6), (0.8, 7.2, 2.4))):
        n = 9
        vs = [(r * jit.uniform(0.75, 1.15) * math.cos(2 * math.pi * (j + jit.uniform(-0.2, 0.2)) / n),
               r * jit.uniform(0.75, 1.15) * math.sin(2 * math.pi * (j + jit.uniform(-0.2, 0.2)) / n), z0 + jit.uniform(-0.25, 0.1)) for j in range(n)]
        vs.append((jit.uniform(-0.1, 0.1), jit.uniform(-0.1, 0.1), z0 + h))
        fs = [(j, (j + 1) % n, n) for j in range(n)] + [tuple(reversed(range(n)))]
        pine = pine + Proto(vs, fs, [0] * len(fs))
    leafy = Proto(*K.cyl_geom(0.2, 3.0, (0.0, 0.0, 1.5), (0, 0, 0), 6), [1] * 8)
    rng = random.Random(5)
    for c in ((0.0, 0.0, 4.6), (0.6, -0.5, 5.6)):
        vs, fs = [], []
        seg, rings = 7, 5
        rr = 2.0
        for i in range(1, rings):
            th = math.pi * i / rings
            for j in range(seg):
                ph = 2 * math.pi * j / seg
                q = rr * rng.uniform(0.82, 1.12)
                vs.append((c[0] + q * math.sin(th) * math.cos(ph), c[1] + q * math.sin(th) * math.sin(ph), c[2] + 0.8 * q * math.cos(th)))
        top, bot = len(vs), len(vs) + 1
        vs += [(c[0], c[1], c[2] + 0.8 * rr), (c[0], c[1], c[2] - 0.8 * rr)]
        for i in range(rings - 2):
            for j in range(seg):
                a, b = i * seg + j, i * seg + (j + 1) % seg
                fs.append((a, b, b + seg, a + seg))
        for j in range(seg):
            fs.append((top, (j + 1) % seg, j))
            fs.append((bot, (rings - 2) * seg + j, (rings - 2) * seg + (j + 1) % seg))
        leafy = leafy + Proto(vs, fs, [0] * len(fs))
    return pine, leafy


def build_trees(land: Land):
    rng = np.random.default_rng(77)
    n = 16000
    p = np.stack([rng.uniform(-300, 300, n), rng.uniform(-420, 520, n)], 1)
    d = land.offset(p)
    sc = rng.uniform(0.8, 1.45, n)
    crown = 2.3 * sc                                                     # widest crown radius (pines' lowest tier, broadleaf blobs)
    keep = ((d - crown > rw.TREE_CLEAR[0]) | (d + crown < rw.TREE_CLEAR[1])) & (np.abs(d) < 230)
    near = np.abs(d) < 60
    keep &= near | (rng.random(n) < 0.35)
    p, d, sc = p[keep], d[keep], sc[keep]
    z = rw.ground_z(d, p[:, 0], p[:, 1])
    pine, leafy = tree_protos()
    dark = textured("Pine needles", (0.015, 0.045, 0.022), (0.04, 0.085, 0.035), 2.0, rough=0.9, bump=0.5)
    leaf = textured("Leaves", (0.03, 0.075, 0.022), (0.08, 0.14, 0.035), 1.5, rough=0.9, bump=0.5)
    bark = material("Bark", (0.10, 0.07, 0.05), rough=0.9)
    xp, xl = [], []
    for k in range(len(p)):
        rot = rot_z(rng.uniform(0, 2 * math.pi)) * sc[k]
        tr = np.array([p[k, 0], p[k, 1], z[k] - 0.3])
        (xp if rng.random() < 0.55 else xl).append((rot, tr))
    stamp("Pines", pine, [dark, bark], xp, smooth=False)
    stamp("Broadleaf trees", leafy, [leaf, bark], xl, smooth=True)
    return len(p)


def build_ridges():
    mtn = textured("Far ridges", (0.10, 0.14, 0.13), (0.17, 0.21, 0.20), 0.004, rough=0.95, bump=0.2)
    for name, cx, cy, w, dd, hmax, along_x in (("Ridge north", 300.0, 3300.0, 9000.0, 1800.0, 780.0, True),
                                                ("Ridge east", 3000.0, 200.0, 9000.0, 1800.0, 650.0, False),
                                                ("Ridge south", -300.0, -3500.0, 9000.0, 1800.0, 700.0, True),
                                                ("Ridge west", -3100.0, 400.0, 9000.0, 1800.0, 900.0, False)):
        nu, nv = 140, 30
        us = np.linspace(-w / 2, w / 2, nu)
        vs = np.linspace(-dd / 2, dd / 2, nv)
        U, V = np.meshgrid(us, vs, indexing="ij")
        ridge = np.clip(1.0 - np.abs(V) / (dd / 2), 0, 1) ** 1.2
        n1 = 0.55 + 0.25 * np.sin(U / 520.0 + 1.0 + cx * 0.001) + 0.15 * np.sin(U / 190.0 + 2.0) + 0.05 * np.sin(U / 60.0)
        Zm = hmax * ridge * n1 - 60.0
        co = np.stack([cx + U, cy + V, Zm], -1).reshape(-1, 3) if along_x else np.stack([cx + V, cy + U, Zm], -1).reshape(-1, 3)
        i = (np.arange(nu - 1)[:, None] * nv + np.arange(nv - 1)[None, :]).ravel()
        q = np.stack([i, i + nv, i + nv + 1, i + 1], 1)
        np_mesh_flat(name, co, q.ravel(), np.full(len(q), 4, np.int32), [mtn], smooth=True)


def build_sign():
    """A curve warning sign (red-bordered yellow triangle, black left-bend arrow) before the bend, just behind the barrier."""
    ax, hs, s_ax = rw.barrier_axis()
    s0 = -38.0
    x, y, h = (float(np.interp(s0, s_ax, ax[:, 0])), float(np.interp(s0, s_ax, ax[:, 1])), float(np.interp(s0, s_ax, np.unwrap(hs))))
    fr = barrier_frame(h)
    pos = np.array([x, y, 0.0]) + fr @ np.array([0.75, 0.0, 0.0])
    grey = material("Sign post", (0.5, 0.5, 0.5), metal=0.6, rough=0.4)
    red = material("Sign red", (0.75, 0.04, 0.03), rough=0.4)
    yel = material("Sign yellow", (0.98, 0.72, 0.05), rough=0.4)
    blk = material("Sign black", (0.02, 0.02, 0.02), rough=0.5)
    stamp("Sign post", cyl_proto(0.04, -0.5, 2.55, n=8), [grey], [(fr, pos)])
    z0, a_out, a_in = 1.95, 1.0, 0.74                    # the plate faces the drivers coming up the road (-ly); u across, z up

    def tri(side, zc, dy):
        hgt = side * math.sqrt(3) / 2
        zb = zc - side * math.sqrt(3) / 6
        return np.array([(-side / 2, dy, zb), (side / 2, dy, zb), (0.0, dy, zb + hgt)])

    zc = z0 + a_out * math.sqrt(3) / 6
    for side, dy, mat in ((a_out, -0.05, red), (a_in, -0.056, yel)):
        w = tri(side, zc, dy) @ fr.T + pos
        np_mesh(f"Sign {mat.name}", w, [(0, 1, 2)], [mat])
    pts = [(0.0, zc - 0.17), (0.0, zc - 0.02)] + [(-0.11 + 0.11 * math.cos(a), zc - 0.02 + 0.11 * math.sin(a)) for a in np.linspace(0.2, math.pi / 2, 6)]
    co, faces = [], []
    for k, (u, v) in enumerate(pts):
        a, b = pts[max(0, k - 1)], pts[min(len(pts) - 1, k + 1)]
        du, dv = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(du, dv) or 1.0
        nu, nv = -dv / ln * 0.028, du / ln * 0.028
        co += [(u - nu, -0.062, v - nv), (u + nu, -0.062, v + nv)]
        if k:
            faces.append((2 * k - 2, 2 * k - 1, 2 * k + 1, 2 * k))
    tip_u, tip_v = pts[-1]
    co += [(tip_u, -0.062, tip_v + 0.07), (tip_u, -0.062, tip_v - 0.07), (tip_u - 0.10, -0.062, tip_v)]
    faces.append((len(co) - 3, len(co) - 2, len(co) - 1))
    np_mesh("Sign arrow", np.array(co) @ fr.T + pos, faces, [blk])


# ------------------------------------------------------------------ car extras
class Sparks:
    def __init__(self, n=180):
        hot = material("Spark", (1.0, 0.55, 0.12), rough=0.5)
        s = hot.node_tree.nodes.get("Principled BSDF")
        s.inputs["Emission Color"].default_value = (1.0, 0.36, 0.05, 1)
        s.inputs["Emission Strength"].default_value = 40.0
        self.obs = []
        for k in range(n):
            ob = K.cube(f"Spark {k}", (0, 0, -10), (1.0, 1.0, 1.0), hot)
            ob.hide_render = True
            self.obs.append(ob)

    def update(self, pts, time_scale):
        stretch = min(0.05, 0.02 / max(0.05, time_scale) * 0.1)          # shutter streak: longer when the clock runs nearer real time
        for k, ob in enumerate(self.obs):
            if k >= len(pts):
                ob.hide_render = True
                continue
            pos, vel = pts[k]
            sp = float(np.linalg.norm(vel)) + 1e-6
            ob.hide_render = False
            ob.location = tuple(pos)
            ob.rotation_mode = "QUATERNION"
            ob.rotation_quaternion = Vector(tuple(vel / sp)).to_track_quat("Z", "Y")
            ob.scale = (0.012, 0.012, max(0.03, sp * stretch))


class TyreMarks:
    N = 70

    def __init__(self, wheel_xy):
        mat = bpy.data.materials.new("Tyre marks")
        mat.use_nodes = True
        nt = mat.node_tree
        bsdf = nt.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = (0.02, 0.02, 0.02, 1)
        bsdf.inputs["Roughness"].default_value = 0.9
        bsdf.inputs["Alpha"].default_value = 0.38
        self.wheels = wheel_xy
        m = self.N
        co = np.zeros((len(wheel_xy) * 2 * m, 3))
        quads = []
        for w in range(len(wheel_xy)):
            b = w * 2 * m
            for i in range(m - 1):
                quads.append((b + 2 * i, b + 2 * i + 2, b + 2 * i + 3, b + 2 * i + 1))
        self.ob = np_mesh("Tyre marks", co, quads, [mat])

    def set(self, t, barrier):
        c = rm.crash(barrier)
        t0, t1 = 0.0, c["contact_end"] + rm.REACT_S
        m = self.N
        co = np.zeros((len(self.wheels) * 2 * m, 3))
        co[:, 2] = -5.0
        if t > t0 + 0.004:
            ts = np.linspace(t0 + 0.002, min(t, t1), m)
            poses = [rm.pose(float(x), barrier) for x in ts]
            for w, (wx, wy) in enumerate(self.wheels):
                b = w * 2 * m
                for i, p in enumerate(poses):
                    cc, ss = math.cos(p["psi"]), math.sin(p["psi"])
                    x = p["x"] + cc * wx + ss * wy
                    y = p["y"] - ss * wx + cc * wy
                    nx, ny = cc, -ss
                    co[b + 2 * i] = (x - 0.075 * nx, y - 0.075 * ny, 0.008)
                    co[b + 2 * i + 1] = (x + 0.075 * nx, y + 0.075 * ny, 0.008)
        self.ob.data.vertices.foreach_set("co", co.astype(np.float32).ravel())
        self.ob.data.update()


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
        scene.view_settings.white_balance_temperature = 7600.0
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    sun_to = cinematic.sun_vector((-0.62, 0.78), 17.0)                      # low sun behind the cameras that look back at the crash
    cinematic.apply_sky(scene, sun_to, strength=0.30, dust=0.55)
    sd = bpy.data.lights.new("Sun", "SUN")
    sd.energy, sd.angle, sd.color = 5.8, 0.02, (1.0, 0.74, 0.50)
    sun = bpy.data.objects.new("Sun", sd)
    scene.collection.objects.link(sun)
    sun.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()
    wheel_nodes = {w["node"] for w in wheels.values()}
    parts = [o for o in car_root.children_recursive if o.type == "MESH" and not any(p in wheel_nodes for p in rb._ancestors(o))]
    ghost = rb.Ghost(parts)
    ghost.set_tint(PAINT)
    ghost.set_factor(0.0, 1e4, 4.0)
    land = Land()
    build_road()
    n_trees = build_trees(land)
    build_ridges()
    build_sign()
    barrier = Barrier(roller_material())
    steel = SteelRail()
    sparks = Sparks()
    marks = TyreMarks([(float(w["base"].x), float(w["base"].y)) for w in wheels.values()])
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    segs = tl.segments()
    print("ROLLER_SCENE " + json.dumps({"trees": n_trees, "objects": len(bpy.data.objects)}), flush=True)

    def render(sh, path):
        scene.render.resolution_x, scene.render.resolution_y = round(FRAME[0] * args.res_scale), round(FRAME[1] * args.res_scale)
        v, t = sh["variant"], sh["t"]
        section = bool(sh.get("section"))
        bar = "steel" if v == "steel" else "roller"
        barrier.show(v != "steel", section)
        steel.show(v == "steel")
        info = {"rollers_spinning": 0, "rollers_blurred": 0, "max_squash": 0.0, "max_give": 0.0}
        if v != "steel":
            info = barrier.set(t, v == "roller", sh["time_scale"])
        rail_give = steel.set(t) if v == "steel" else 0.0
        p = tl.car_pose(sh)
        visible = p["visible"]
        for ob in [car_root, *car_root.children_recursive]:
            ob.hide_render = not visible
        car_root.location = (p["x"], p["y"], 0.0)
        car_root.rotation_euler = (0.0, 0.0, -p["psi"])
        wa = rm.wheel_angle(t, bar) if visible else 0.0
        for w in wheels.values():
            w["node"].rotation_euler = (-wa, 0.0, 0.0)
        pts = rm.spark_points(t) if v == "steel" else []
        sparks.update(pts, abs(sh["time_scale"]))
        if visible:
            marks.set(t, bar)
        else:
            marks.set(-1.0, bar)
        c = sh["cam"]
        o = Vector((p["x"], p["y"], 0.0)) if c["rel"] == "car" else Vector((0.0, 0.0, 0.0))
        loc, tgt = o + Vector(c["loc"]), o + Vector(c["target"])
        dd = cam.data
        dd.sensor_fit, dd.sensor_width, dd.lens, dd.clip_start = "HORIZONTAL", 36.0, c["lens"], 0.02
        dd.clip_end = 15000.0
        dd.dof.use_dof = True
        dd.dof.focus_distance = (tgt - loc).length
        dd.dof.aperture_fstop = c.get("fstop", 8.0)
        base.set_camera(cam, loc, tgt)
        bpy.context.view_layer.update()
        lo = (-geom["body_half_width"], -geom["tail"], 0.0)
        hi = (geom["body_half_width"], geom["nose"], geom["roof"])
        box = hook_gate.project_box(scene, cam, car_root.matrix_world, lo, hi) if visible else None
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        return {"variant": v, "t": round(t, 6), "car_visible": visible, "car_x": round(p["x"], 4), "car_y": round(p["y"], 4),
                "car_psi_deg": round(math.degrees(p["psi"]), 3), "speed": round(p.get("speed", 0.0), 3), "in_contact": bool(p.get("in_contact", False)),
                "wheel_angle": round(wa, 4), "sparks": len(pts), "rail_give": rail_give, "section": section, **info,
                "subject_box": box, "cam_world": [round(x, 3) for x in loc], "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    a0, b0 = (int(x) for x in args.frames.split("-"))
    frames = [int(x) for x in args.list.split(",")] if args.list else list(range(a0, b0 + 1))
    out = []
    src_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    for f in frames:
        t0 = time.time()
        sh = tl.frame_state(f, segs)
        seg = next(s for s in segs if s["label"] == sh["segment"])
        sh["time_scale"] = seg["time_scale"]
        part = render(sh, args.out / f"frame_{f:05d}.png")
        info = {"frame": f, "segment": sh["segment"], "split": False, "parts": [part], "render_seconds": round(time.time() - t0, 1)}
        out.append(info)
        print("ROLLER_FRAME " + json.dumps(info), flush=True)
    (args.out / f"roller-frames-{frames[0]:05d}.json").write_text(json.dumps({"renderer_source_sha256": src_sha, "frames": out}, indent=1))


if __name__ == "__main__":
    main()
