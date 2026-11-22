"""EP.21 rockfall ring net: 100 % 3D renderer (Blender, Cycles CPU), house style of EP.13-EP.20 (golden hour, depth of field, the
red CC0 sedan on the road). A two-lane mountain road runs along the foot of a 38-degree slope; halfway up the slope a flexible
barrier stands across it: steel posts on footings, a net of about two thousand interlocked steel rings, support ropes top and bottom,
retaining ropes up the slope to anchors, and on every retaining rope a ring brake (a loop of steel tube held by a press sleeve).

A 20 t boulder rolls down, hops off a bump and hits the middle span. Everything moves from rocknet_motion every frame: the net bulges
down the slope around the rock (a broad bulge plus a pocket that wraps the rock's front), every ring turns with the net surface, the
posts lean, the ropes follow, each brake loop shrinks by the length of tube it has pulled through its sleeve and glows with the power
it is turning into heat; chips and dust fly at the hit. The clean-up shot shrinks the rock away, lets the net spring back and grows the
new brake loops. No text anywhere in the scene."""
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
from benchmarks.can_opener import render_opener_3d as K  # noqa: E402  (data-API mesh helpers)
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402
from benchmarks.rock_net import rocknet_motion as rm  # noqa: E402
from benchmarks.rock_net import rocknet_timeline as tl  # noqa: E402

material = base.material
cube, boxes, cyl, cyls, new_object, Sheet = K.cube, K.boxes, K.cyl, K.cyls, K.new_object, K.Sheet
pieces_mesh, set_pieces, rot_xyz, sstep, grid_faces = K.pieces_mesh, K.set_pieces, K.rot_xyz, K.sstep, K.grid_faces
FRAME = (1080, 1920)
PAINT = (1.75, 0.30, 0.24)
D_HAT = rm.d_hat()
UPS = np.array([math.cos(rm.SLOPE), 0.0, math.sin(rm.SLOPE)])         # up the slope
SY = SH = 0.26                                                         # ring pitch along the net and up it
RING_R, WIRE_R = 0.15, 0.014
LY, LH = 3.6, 3.0                                                      # bulge decay along and across the net
TUBE_R = 0.028
SLEEVE_BACK = 2.0                                                      # brake sleeve this far from the anchor


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


def smooth_noise(a, b, seed=0.0):
    return (0.5 * np.sin(0.21 * a + 0.7 + seed) * np.sin(0.17 * b + 1.1 * seed) + 0.3 * np.sin(0.6 * a + 1.3 * b + 2.0 + seed)
            + 0.2 * np.sin(1.7 * a - 0.9 * b + 4.0 + 2 * seed))


def textured(name, c1, c2, scale, rough=0.9, bump=0.4):
    """Two colours mixed by noise in object space, with a bump (rock, dirt, grass)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = rough
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = scale
    nz.inputs["Detail"].default_value = 8.0
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[1].position = 0.40, 0.62
    ramp.color_ramp.elements[0].color = (*c1, 1)
    ramp.color_ramp.elements[1].color = (*c2, 1)
    nt.links.new(nz.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = bump
    nt.links.new(nz.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def slope_material():
    """Scree and grass on the slope: large soft patches from world-space noise, fine grain and bump on top."""
    m = bpy.data.materials.new("Slope ground")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = 0.92
    tc = nt.nodes.new("ShaderNodeTexCoord")
    big = nt.nodes.new("ShaderNodeTexNoise")
    big.inputs["Scale"].default_value = 0.05
    big.inputs["Detail"].default_value = 4.0
    nt.links.new(tc.outputs["Object"], big.inputs["Vector"])
    fine = nt.nodes.new("ShaderNodeTexNoise")
    fine.inputs["Scale"].default_value = 2.5
    fine.inputs["Detail"].default_value = 10.0
    nt.links.new(tc.outputs["Object"], fine.inputs["Vector"])
    patches = nt.nodes.new("ShaderNodeValToRGB")
    patches.color_ramp.elements[0].position, patches.color_ramp.elements[1].position = 0.40, 0.52
    nt.links.new(big.outputs["Fac"], patches.inputs["Fac"])
    rock = nt.nodes.new("ShaderNodeValToRGB")
    rock.color_ramp.elements[0].color, rock.color_ramp.elements[1].color = (0.20, 0.19, 0.17, 1), (0.40, 0.37, 0.33, 1)
    nt.links.new(fine.outputs["Fac"], rock.inputs["Fac"])
    grass = nt.nodes.new("ShaderNodeValToRGB")
    grass.color_ramp.elements[0].color, grass.color_ramp.elements[1].color = (0.10, 0.14, 0.05, 1), (0.22, 0.25, 0.09, 1)
    nt.links.new(fine.outputs["Fac"], grass.inputs["Fac"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    nt.links.new(patches.outputs["Color"], mix.inputs["Factor"])
    nt.links.new(rock.outputs["Color"], mix.inputs["A"])
    nt.links.new(grass.outputs["Color"], mix.inputs["B"])
    nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.6
    nt.links.new(fine.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def cone_geom(r, h, base_pt, verts=10):
    x, y, z = base_pt
    vs = [(x + r * math.cos(2 * math.pi * k / verts), y + r * math.sin(2 * math.pi * k / verts), z) for k in range(verts)] + [(x, y, z + h)]
    fs = [(k, (k + 1) % verts, verts) for k in range(verts)] + [tuple(reversed(range(verts)))]
    return vs, fs


def merged(name, parts, mat, smooth=False):
    vs, fs = [], []
    for v, f in parts:
        off = len(vs)
        vs += v
        fs += [tuple(i + off for i in ff) for ff in f]
    return new_object(name, vs, fs, mat, smooth=smooth)


def torus_geom(R, r, center, normal, n_major=14, n_minor=4):
    """Torus of major radius R around `normal` through `center` (numpy arrays out)."""
    n = np.asarray(normal, float)
    n /= np.linalg.norm(n)
    a = np.cross(n, [0.0, 0.0, 1.0]) if abs(n[2]) < 0.9 else np.cross(n, [1.0, 0.0, 0.0])
    a /= np.linalg.norm(a)
    b = np.cross(n, a)
    pts = []
    for i in range(n_major):
        th = 2 * math.pi * i / n_major
        c = math.cos(th) * a + math.sin(th) * b
        for j in range(n_minor):
            ph = 2 * math.pi * j / n_minor
            pts.append(np.asarray(center) + (R + r * math.cos(ph)) * c + r * math.sin(ph) * n)
    faces = [(i * n_minor + j, ((i + 1) % n_major) * n_minor + j, ((i + 1) % n_major) * n_minor + (j + 1) % n_minor, i * n_minor + (j + 1) % n_minor)
             for i in range(n_major) for j in range(n_minor)]
    return np.array(pts), faces


class Tube:
    """A rope or tube through a list of points, rebuilt every frame (fixed point count)."""

    def __init__(self, name, n, r, mat, sides=6):
        self.n, self.r, self.sides = n, r, sides
        co = np.zeros((n * sides, 3))
        faces = [(i * sides + j, i * sides + (j + 1) % sides, (i + 1) * sides + (j + 1) % sides, (i + 1) * sides + j) for i in range(n - 1) for j in range(sides)]
        self.sheet = Sheet(name, co, faces, [mat], smooth=True)

    def set(self, pts):
        pts = np.asarray(pts, float)
        t = np.gradient(pts, axis=0)
        t /= np.linalg.norm(t, axis=1, keepdims=True) + 1e-12
        ref = np.where(np.abs(t[:, 2:3]) < 0.9, np.array([[0.0, 0.0, 1.0]]), np.array([[1.0, 0.0, 0.0]]))
        a = np.cross(t, ref)
        a /= np.linalg.norm(a, axis=1, keepdims=True) + 1e-12
        b = np.cross(t, a)
        ang = 2 * np.pi * np.arange(self.sides) / self.sides
        co = pts[:, None, :] + self.r * (np.cos(ang)[None, :, None] * a[:, None, :] + np.sin(ang)[None, :, None] * b[:, None, :])
        self.sheet.set(co.reshape(-1, 3))


def resample(points, n):
    """n points evenly spaced along a polyline."""
    p = np.asarray(points, float)
    seg = np.linalg.norm(np.diff(p, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    u = np.linspace(0.0, s[-1], n)
    return np.stack([np.interp(u, s, p[:, k]) for k in range(3)], 1)


def rock_geom(r, center, rng):
    """A small faceted rock (for the scree on the slope)."""
    vs, fs = [], []
    seg, rings = 7, 5
    for i in range(1, rings):
        th = math.pi * i / rings
        for k in range(seg):
            ph = 2 * math.pi * k / seg
            rr = r * rng.uniform(0.75, 1.15)
            vs.append((center[0] + rr * math.sin(th) * math.cos(ph), center[1] + rr * math.sin(th) * math.sin(ph), center[2] + 0.7 * rr * math.cos(th)))
    top, bot = len(vs), len(vs) + 1
    vs += [(center[0], center[1], center[2] + 0.7 * r), (center[0], center[1], center[2] - 0.7 * r)]
    for i in range(rings - 2):
        for k in range(seg):
            a, b = i * seg + k, i * seg + (k + 1) % seg
            fs.append((a, b, b + seg, a + seg))
    for k in range(seg):
        fs.append((top, (k + 1) % seg, k))
        fs.append((bot, (rings - 2) * seg + k, (rings - 2) * seg + (k + 1) % seg))
    return vs, fs


class Terrain:
    def __init__(self):
        rock_m = slope_material()
        grass_m = textured("Valley grass", (0.13, 0.17, 0.06), (0.24, 0.26, 0.10), 1.6, bump=0.3)
        asphalt = material("Asphalt", (0.07, 0.07, 0.075), rough=0.85)
        base.asphalt_grain(asphalt)
        gravel = textured("Shoulder gravel", (0.33, 0.31, 0.28), (0.45, 0.43, 0.39), 9.0, bump=0.5)
        white = material("Line paint", (0.85, 0.85, 0.80), rough=0.6)
        yellow = material("Centre line", (0.85, 0.62, 0.08), rough=0.6)
        steel = material("Guardrail", (0.62, 0.63, 0.64), metal=0.8, rough=0.35)
        mtn = textured("Mountains", (0.26, 0.29, 0.33), (0.40, 0.43, 0.47), 0.02, bump=0.2)
        snow = material("Snow caps", (0.86, 0.88, 0.92), rough=0.6)
        bark = material("Bark", (0.12, 0.08, 0.05), rough=0.9)
        pine = textured("Pine needles", (0.05, 0.10, 0.05), (0.09, 0.16, 0.07), 6.0, bump=0.3)
        y0, y1 = -170.0, 170.0
        us = np.arange(-1.0, 112.0, 1.25)
        ys = np.arange(y0, y1 + 0.1, 2.5)
        U, Y = np.meshgrid(us, ys, indexing="ij")
        quiet = 1.0 - 0.8 * np.exp(-(Y / 22.0) ** 2) * np.exp(-((U - 24.0) / 30.0) ** 2)
        n = (0.45 * smooth_noise(U, Y) + 0.25 * smooth_noise(2.3 * U, 1.9 * Y, 1.7)) * quiet * np.clip(U / 3.0, 0, 1)
        nrm = np.array([-math.sin(rm.SLOPE), 0.0, math.cos(rm.SLOPE)])
        X = rm.X_TOE + U * math.cos(rm.SLOPE) + n * nrm[0]
        Z = U * math.sin(rm.SLOPE) + n * nrm[2]
        co = np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1)
        faces = grid_faces(len(us), len(ys))
        Sheet("Slope", co, [tuple(reversed(f)) for f in faces], [rock_m], smooth=True)
        xs = np.arange(-4.4, -90.0, -2.5)
        X2, Y2 = np.meshgrid(xs, ys, indexing="ij")
        Z2 = 0.72 * (X2 + 4.4) + 0.6 * smooth_noise(X2, Y2, 3.0) * np.clip(-(X2 + 4.4) / 4.0, 0, 1)          # falls away to the valley
        co2 = np.stack([X2.ravel(), Y2.ravel(), Z2.ravel()], 1)
        Sheet("Valley", co2, grid_faces(len(xs), len(ys)), [grass_m], smooth=True)
        cube("Road", (0.0, 0.0, -0.05), (7.2, y1 - y0, 0.1), asphalt)
        cube("Shoulder", ((3.6 + rm.X_TOE) / 2, 0.0, -0.06), (rm.X_TOE - 3.6 + 0.4, y1 - y0, 0.1), gravel)
        cube("Valley shoulder", (-4.0, 0.0, -0.06), (0.9, y1 - y0, 0.1), gravel)
        items = []
        for k in range(int((y1 - y0) / 6)):
            y = y0 + 6 * k + 1.5
            items += [((dx, y + 1.5, 0.004), (0.10, 6.0, 0.01)) for dx in (-0.09, 0.09)]
        boxes("Centre line", items, yellow)
        boxes("Edge lines", [((sx * 3.45, 0.0, 0.004), (0.12, y1 - y0, 0.01)) for sx in (-1, 1)], white)
        boxes("Guardrail beam", [((-3.95, 0.0, 0.62), (0.08, y1 - y0, 0.32))], steel)
        boxes("Guardrail posts", [((-4.05, y, 0.4), (0.12, 0.12, 0.8)) for y in np.arange(y0, y1, 2.0)], steel)
        rng = random.Random(21)
        trunks, crowns = [], []
        for _ in range(120):
            side = rng.random()
            if side < 0.7:
                u = rng.uniform(4.0, 95.0)
                y = rng.uniform(y0 + 10, y1 - 10)
                if abs(y) < 24.0 and u < 60.0:
                    continue
                x = rm.X_TOE + u * math.cos(rm.SLOPE)
                z = u * math.sin(rm.SLOPE)
            else:
                x = rng.uniform(-60.0, -8.0)
                y = rng.uniform(y0 + 10, y1 - 10)
                z = 0.72 * (x + 4.4)
            h = rng.uniform(7.0, 13.0)
            trunks.append(K.cyl_geom(0.18, h * 0.4, (x, y, z + h * 0.2)))
            for k, (rf, zf) in enumerate(((0.32, 0.25), (0.25, 0.45), (0.17, 0.65))):
                crowns.append(cone_geom(h * rf, h * 0.42, (x, y, z + h * zf)))
        scree = []
        for _ in range(420):                                                  # loose rocks on the slope, none on the boulder's line
            u = rng.uniform(1.0, 100.0)
            y = rng.uniform(y0 + 5, y1 - 5)
            if abs(y) < 2.8:
                continue
            r = rng.uniform(0.12, 0.55) if rng.random() < 0.85 else rng.uniform(0.6, 1.1)
            x = rm.X_TOE + u * math.cos(rm.SLOPE)
            scree.append(rock_geom(r, (x, y, u * math.sin(rm.SLOPE) + 0.25 * r), rng))
        merged("Scree", scree, textured("Scree rock", (0.24, 0.22, 0.20), (0.42, 0.39, 0.35), 3.0, rough=0.85, bump=0.7))
        merged("Trunks", trunks, bark)
        merged("Pine crowns", crowns, pine)
        peaks = []
        for x, y, r, hgt in ((480, 200, 260, 330), (560, -300, 300, 420), (420, -820, 240, 300), (-520, 300, 300, 360), (-620, -400, 320, 450),
                             (-480, 900, 260, 310), (300, 900, 240, 280)):
            peaks.append(cone_geom(r, hgt, (x, y, -60.0), verts=9))
        merged("Mountains", peaks, mtn)
        merged("Snow caps", [cone_geom(r * 0.28, hgt * 0.28, (x, y, -60.0 + hgt * 0.72), verts=9) for x, y, r, hgt in
                             ((480, 200, 260, 330), (560, -300, 300, 420), (-620, -400, 320, 450))], snow)


class Barrier:
    def __init__(self):
        post_m = material("Post steel", (0.30, 0.32, 0.33), metal=0.7, rough=0.45)
        concrete = material("Footing concrete", (0.52, 0.51, 0.48), rough=0.85)
        self.ring_m = material("Ring wire", (0.70, 0.72, 0.74), metal=0.95, rough=0.32)
        rope_m = material("Rope", (0.55, 0.57, 0.59), metal=0.9, rough=0.4)
        self.brake_m = material("Brake tube", (0.72, 0.73, 0.75), metal=0.9, rough=0.3)
        b = self.brake_m.node_tree.nodes.get("Principled BSDF")
        b.inputs["Emission Color"].default_value = (1.0, 0.22, 0.03, 1.0)
        b.inputs["Emission Strength"].default_value = 0.0
        sleeve_m = material("Press sleeve", (0.80, 0.80, 0.78), metal=0.7, rough=0.35)
        anchor_m = material("Anchor", (0.35, 0.33, 0.30), metal=0.6, rough=0.5)
        self.posts = []
        for yp in rm.POST_YS:
            ob = new_object(f"Post {yp}", K.box_verts((0.0, 0.0, rm.H_NET / 2), (0.22, 0.22, rm.H_NET)), K.BOX_FACES, post_m)
            ob.location = (rm.X_B, yp, rm.Z_B)
            self.posts.append(ob)
            cube(f"Footing {yp}", (rm.X_B, yp, rm.Z_B - 0.25), (0.9, 0.9, 0.6), concrete)
            cube(f"Base plate {yp}", (rm.X_B, yp, rm.Z_B + 0.03), (0.5, 0.5, 0.06), post_m)
        ys = np.arange(-15.0 + SY / 2, 15.0, SY)
        hs = np.arange(SH / 2, rm.H_NET, SH)
        Y, Hh = np.meshgrid(ys, hs, indexing="ij")
        self.grid_shape = Y.shape
        self.ring_y, self.ring_h = Y.ravel(), Hh.ravel()
        self.rest = np.stack([np.full(self.ring_y.size, rm.X_B), self.ring_y, rm.Z_B + self.ring_h], 1)
        pts, faces = torus_geom(RING_R, WIRE_R, (0, 0, 0), (1.0, 0.0, 0.0))
        self.rings = pieces_mesh("Ring net", [tuple(p) for p in pts], faces, self.ring_y.size, self.ring_m)
        ii, jj = np.meshgrid(np.arange(Y.shape[0]), np.arange(Y.shape[1]), indexing="ij")
        self.tilt = np.where(((ii + jj) % 2).ravel() == 0, 0.26, -0.26)
        self.top_rope = Tube("Top rope", 60, 0.011, rope_m)
        self.bot_rope = Tube("Bottom rope", 60, 0.011, rope_m)
        self.anchors = []
        for yp in rm.POST_YS:
            a = np.array([rm.X_B, yp, rm.Z_B]) + rm.ANCHOR_UP * UPS
            self.anchors.append(a)
            cube(f"Anchor {yp}", tuple(a + np.array([0, 0, 0.05])), (0.35, 0.35, 0.12), anchor_m)
        self.ret = [Tube(f"Retaining rope {k}", 2, 0.011, rope_m) for k in range(len(rm.POST_YS))]
        self.tail = [Tube(f"Rope tail {k}", 2, 0.011, rope_m) for k in range(len(rm.POST_YS))]
        n_major, n_minor = 40, 6
        self.loop_n = (n_major, n_minor)
        p0, f0 = torus_geom(rm.LOOP_R0, TUBE_R, (0, 0, 0), (0, 1, 0), n_major, n_minor)
        self.loops = [Sheet(f"Brake loop {k}", p0, f0, [self.brake_m], smooth=True) for k in range(len(rm.POST_YS))]
        self.sleeves = [cyl(f"Press sleeve {k}", 0.045, 0.16, (0, 0, -50), sleeve_m) for k in range(len(rm.POST_YS))]
        self.ghost_m = material("Rest plane", (1.0, 0.10, 0.06), emission=6.0)
        g = []
        for h in (0.0, rm.H_NET):
            g.append(((rm.X_B, 0.0, rm.Z_B + h), (0.03, 10.0, 0.03)))
        for yp in (-5.0, 5.0):
            g.append(((rm.X_B, yp, rm.Z_B + rm.H_NET / 2), (0.03, 0.03, rm.H_NET)))
        self.ghost = boxes("Rest plane outline", g, self.ghost_m)

    def displacement(self, y, h, w, rock_scale=1.0):
        """Net deflection along D_HAT at net coordinates (y, h): a broad bulge plus the pocket that wraps the rock's front."""
        dy, dh = y - rm.HIT_Y, h - rm.HIT_H
        broad = w * np.exp(-(dy / LY) ** 2) * np.exp(-(dh / LH) ** 2)
        r = rm.R_ROCK * rock_scale
        rho2 = dy * dy + dh * dh
        cap = np.where(rho2 < r * r, w - r + np.sqrt(np.maximum(r * r - rho2, 0.0)), 0.0) if rock_scale > 0.01 else 0.0
        return np.maximum(np.maximum(broad, cap), 0.0)

    def set(self, w, lean, loop_r, power, ghost, rock_scale=1.0):
        Dg = self.displacement(self.ring_y, self.ring_h, w, rock_scale)
        D2 = Dg.reshape(self.grid_shape)
        dDy, dDh = np.gradient(D2, SY, SH)
        ty = np.stack([np.zeros_like(D2), np.ones_like(D2), np.zeros_like(D2)], -1) + dDy[..., None] * D_HAT
        th = np.stack([np.zeros_like(D2), np.zeros_like(D2), np.ones_like(D2)], -1) + dDh[..., None] * D_HAT
        nrm = np.cross(ty, th).reshape(-1, 3)
        nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
        x0 = np.array([1.0, 0.0, 0.0])
        axis = np.cross(np.broadcast_to(x0, nrm.shape), nrm)
        s = np.linalg.norm(axis, axis=1)
        c = nrm[:, 0]
        k = axis / np.maximum(s, 1e-9)[:, None]
        Kx = np.zeros((len(k), 3, 3))
        Kx[:, 0, 1], Kx[:, 0, 2], Kx[:, 1, 0], Kx[:, 1, 2], Kx[:, 2, 0], Kx[:, 2, 1] = -k[:, 2], k[:, 1], k[:, 2], -k[:, 0], -k[:, 1], k[:, 0]
        Rn = np.eye(3)[None] + s[:, None, None] * Kx + (1 - c)[:, None, None] * (Kx @ Kx)
        Rt = rot_xyz(np.zeros_like(self.tilt), np.zeros_like(self.tilt), self.tilt)
        pos = self.rest + Dg[:, None] * D_HAT
        set_pieces(self.rings, pos, Rn @ Rt)
        for ob in self.posts:
            ob.rotation_euler = (0.0, -lean, 0.0)
        bpy.context.view_layer.update()
        tops = [np.array(ob.matrix_world @ Vector((0.0, 0.0, rm.H_NET))) for ob in self.posts]
        yy = np.linspace(-15.0, 15.0, 60)
        for rope, h in ((self.top_rope, rm.H_NET), (self.bot_rope, 0.0)):
            d = self.displacement(yy, np.full_like(yy, h), w, rock_scale)
            pts = np.stack([np.full_like(yy, rm.X_B), yy, np.full_like(yy, rm.Z_B + h)], 1) + d[:, None] * D_HAT
            if h > 0:
                for k, yp in enumerate(rm.POST_YS):
                    j = int(np.argmin(np.abs(yy - yp)))
                    pts[j] = tops[k]
            rope.set(pts)
        for k, (top, a) in enumerate(zip(tops, self.anchors)):
            u = (a - top) / np.linalg.norm(a - top)
            sleeve = a - SLEEVE_BACK * u
            up = np.cross(u, [0.0, 1.0, 0.0])
            up = -up if up[2] < 0 else up
            centre = sleeve + loop_r * up
            p, _ = torus_geom(loop_r, TUBE_R, centre, (0.0, 1.0, 0.0), *self.loop_n)
            self.loops[k].set(p)
            self.ret[k].set([top, sleeve])
            self.tail[k].set([sleeve, a])
            sv = self.sleeves[k]
            sv.location = tuple(sleeve)
            sv.rotation_euler = Vector(tuple(u)).to_track_quat("Z", "Y").to_euler()
        b = self.brake_m.node_tree.nodes.get("Principled BSDF")
        b.inputs["Emission Strength"].default_value = 7.0 * min(1.0, power / 1.6e7) ** 0.7
        self.ghost.hide_render = not ghost


class Rock:
    def __init__(self):
        m = textured("Granite", (0.36, 0.34, 0.32), (0.55, 0.52, 0.48), 3.0, rough=0.85, bump=0.8)
        ob = K.sphere("Boulder", 1.0, (0, 0, 0), m, seg=28, rings=18)
        me = ob.data
        co = np.zeros(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        rng = np.random.default_rng(21)
        dirs = co / np.linalg.norm(co, axis=1, keepdims=True)
        n = 1.0 + 0.10 * np.sin(3.1 * dirs[:, 0] + 1.0) * np.cos(2.7 * dirs[:, 1]) + 0.07 * np.sin(5.3 * dirs[:, 2] + 2.0 * dirs[:, 0])
        for _ in range(9):                                                 # flat facets: cut the sphere with a few planes
            pn = rng.normal(size=3)
            pn /= np.linalg.norm(pn)
            d = rng.uniform(0.80, 0.93)
            proj = dirs @ pn
            n = np.minimum(n, np.where(proj > 0, d / np.maximum(proj, 1e-3), 9.0))
        co = dirs * n[:, None] * rm.R_ROCK * np.array([1.08, 1.0, 0.92])
        me.vertices.foreach_set("co", co.ravel())
        me.polygons.foreach_set("use_smooth", [False] * len(me.polygons))
        me.update()
        self.ob = ob
        dust = bpy.data.materials.new("Dust")
        dust.use_nodes = True
        nt = dust.node_tree
        bsdf = nt.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = (0.62, 0.56, 0.48, 1.0)
        bsdf.inputs["Roughness"].default_value = 1.0
        info = nt.nodes.new("ShaderNodeObjectInfo")
        nt.links.new(info.outputs["Alpha"], bsdf.inputs["Alpha"])
        self.puffs = [K.sphere(f"Dust {k}", 1.0, (0, 0, 0), dust, seg=12, rings=8) for k in range(10)]          # geometry at the origin: placed by location
        self.puff_dir = rng.normal(size=(10, 3)) * np.array([1.0, 1.6, 0.6]) + np.array([0.6, 0.0, 0.4])
        chip_m = textured("Rock chips", (0.33, 0.31, 0.29), (0.5, 0.47, 0.43), 4.0)
        tet = [(0.06, 0.0, 0.0), (-0.03, 0.05, 0.0), (-0.03, -0.05, 0.0), (0.0, 0.0, 0.07)]
        self.n_chips = 70
        self.chips = pieces_mesh("Rock chips", tet, [(0, 1, 2), (0, 1, 3), (1, 2, 3), (2, 0, 3)], self.n_chips, chip_m)
        self.chip_v = rng.normal(size=(self.n_chips, 3)) * np.array([3.0, 4.5, 2.0]) + np.array([3.0, 0.0, 3.5])
        self.chip_w = rng.uniform(-20, 20, (self.n_chips, 3))
        self.chip_s = rng.uniform(0.6, 2.4, self.n_chips)
        self.chip_off = rng.normal(size=(self.n_chips, 3)) * 0.5

    def set(self, t, center, spin, scale=1.0):
        self.ob.location = tuple(center)
        self.ob.rotation_euler = (0.0, spin, 0.3)
        self.ob.scale = (scale, scale, scale)
        self.ob.hide_render = scale < 0.02
        hit = rm.contact_point()
        airborne = 0
        n = self.n_chips
        pos = np.tile([0.0, 0.0, -50.0], (n, 1))
        rot = np.repeat(np.eye(3)[None], n, 0)
        if t >= 0:
            tt = np.full(n, t)
            p0 = hit + self.chip_off
            pp = p0 + self.chip_v * tt[:, None] + np.array([0, 0, -0.5 * rm.G]) * (tt ** 2)[:, None]
            ground = np.array([rm.slope_z(x) for x in pp[:, 0]]) + 0.03
            landed = pp[:, 2] < ground
            pp[landed, 2] = ground[landed]
            pos = pp
            rot = rot_xyz(*(self.chip_w * np.minimum(tt, 1.2)[:, None]).T)
            airborne = int((~landed).sum())
        set_pieces(self.chips, pos, rot, self.chip_s)
        for k, ob in enumerate(self.puffs):
            tau = t - 0.015 * k
            if tau < 0 or tau > 2.2:
                ob.location = (0, 0, -50)
                continue
            g = 1 - math.exp(-tau / 0.45)
            p = hit + self.puff_dir[k] * (0.5 + 2.2 * g)
            ob.location = tuple(p)
            r = 0.3 + 1.3 * g
            ob.scale = (r, r, r * 0.8)
            ob.color = (1, 1, 1, 0.40 * (1 - tau / 2.2) ** 1.6)
        return airborne


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
    sun_to = cinematic.sun_vector((-0.85, -0.45), 24.0)
    cinematic.apply_sky(scene, sun_to, strength=0.24, dust=0.7)
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    sun.data.energy, sun.data.angle = 6.0, 0.02
    sun.data.color = (1.0, 0.76, 0.52)
    sun.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()
    Terrain()
    barrier = Barrier()
    rock = Rock()
    wheel_nodes = {w["node"] for w in car_wheels.values()}
    parts = [o for o in car_root.children_recursive if o.type == "MESH" and not any(p in wheel_nodes for p in rb._ancestors(o))]
    ghost = rb.Ghost(parts)
    ghost.set_tint(PAINT)
    ghost.set_factor(0.0, 1e4, 4.0)
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    w_rest = rm.deflection(30.0)

    def render(sh, path):
        scene.render.resolution_x, scene.render.resolution_y = round(FRAME[0] * args.res_scale), round(FRAME[1] * args.res_scale)
        t, variant = sh["t"], sh["variant"]
        if variant == "restore":
            f = min(1.0, max(0.0, t))
            scale = 1.0 - float(sstep(0.0, 0.45, f))
            relax = float(sstep(0.40, 0.80, f))
            w = w_rest * (1.0 - relax)
            lean = rm.post_lean(30.0) * (1.0 - relax)
            loop_r = rm.loop_radius(30.0) + (rm.LOOP_R0 - rm.loop_radius(30.0)) * float(sstep(0.62, 0.90, f))
            power = 0.0
            centre = rm.rock_center(30.0) + rm.d_hat() * 0.0
            spin = rm.rock_spin(30.0)
            st = {"w": w, "slip": rm.brake_slip(30.0) * (1 - float(sstep(0.62, 0.90, f))), "loop_r": loop_r, "lean": lean, "power": 0.0, "speed": 0.0}
        else:
            st = rm.state(t)
            w, lean, loop_r, power = st["w"], st["lean"], st["loop_r"], st["power"]
            centre = rm.rock_center(t)
            spin = rm.rock_spin(t)
            scale = 1.0
        barrier.set(w, lean, loop_r, power, bool(sh.get("ghost")), rock_scale=scale)
        airborne = rock.set(t if variant == "catch" else 30.0, centre, spin, scale)
        cy = tl.car_y(sh)
        if cy is not None:
            car_root.location = (-1.8, cy, 0.0)
            car_root.rotation_euler = (0.0, 0.0, math.pi)
            for wh in car_wheels.values():
                wh["node"].rotation_mode = "ZXY"
                wh["node"].rotation_euler = (-(cy - 26.0) / geom["tyre_radius"], 0, 0)
        else:
            car_root.location = (-1.8, -400.0, 0.0)
        c = sh["cam"]
        loc, tgt = Vector(c["loc"]), Vector(c["target"])
        dd = cam.data
        dd.sensor_fit, dd.sensor_width, dd.lens, dd.clip_start = "HORIZONTAL", 36.0, c["lens"], 0.02
        dd.clip_end = 3000.0
        dd.dof.use_dof = True
        dd.dof.focus_distance = (tgt - loc).length
        dd.dof.aperture_fstop = c.get("fstop", 8.0)
        base.set_camera(cam, loc, tgt)
        bpy.context.view_layer.update()
        box = hook_gate.project_box(scene, cam, Matrix.Identity(4), (rm.X_B - 0.4, -5.2, rm.Z_B), (rm.X_B + 0.3, 5.2, rm.Z_B + rm.H_NET + 0.2))   # the middle span
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        return {"variant": variant, "t": round(t, 6), "w": round(w, 4), "rock": [round(float(v), 4) for v in centre], "rock_scale": round(scale, 4),
                "slip": round(st["slip"], 4), "loop_r": round(loop_r, 4), "lean": round(lean, 5), "power": round(power, 1), "car_y": None if cy is None else round(cy, 3),
                "chips_airborne": airborne, "ghost": bool(sh.get("ghost")), "subject_box": box, "cam_world": [round(v, 3) for v in loc],
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

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
        print("ROCKNET_FRAME " + json.dumps(info), flush=True)
    (args.out / f"rocknet-frames-{frames[0]:05d}.json").write_text(json.dumps({"renderer_source_sha256": src_sha, "frames": out}, indent=1))


if __name__ == "__main__":
    main()
