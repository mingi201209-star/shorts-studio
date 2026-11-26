"""EP.33 ship-impact protection: 100 % 3D renderer (Blender, Cycles CPU), house style (golden hour, depth of field, AgX). A wide bay
crossed by a cable-stayed bridge: a concrete tower on a pier footing, the deck 52 m up with yellow stay cables, a second main pier
across the channel. In front of each main pier, an arc of dolphins: round islands, each a corrugated steel sheet-pile ring driven into
the sea bed, packed with crushed rock and capped with concrete (a yellow band and a navigation light on top). A container ship drifts
off course at the near pier: its bow crumples into the middle dolphin, the ring dents in, the rock packs tighter, water and concrete
chips fly, and the ship stops tens of metres short of the pier. Cut-away shots remove the near half of the struck dolphin, the sea and
the bed along the ship's line; in the force shot the load path glows. Everything that moves comes from dolphin_motion. No text."""
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
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from benchmarks import hook_gate  # noqa: E402
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402
from benchmarks.ship_dolphin import dolphin_motion as m  # noqa: E402
from benchmarks.ship_dolphin import dolphin_timeline as tl  # noqa: E402

material = base.material
FRAME = (1080, 1920)
CX, CY = m.dolphin_centres()[m.HIT]
PIER2_X = 366.0
DECK_Z = 52.0
TOWER_TOP = 112.0


def arguments():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=False)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--res-scale", type=float, default=0.5)
    p.add_argument("--samples", type=int, default=16)
    p.add_argument("--frames", default="0-0")
    p.add_argument("--list", default="")
    p.add_argument("--film", action="store_true")
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return p.parse_args(argv)


def mesh_object(name, verts, faces, mats, mat_index=None, smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in verts], [], [tuple(int(i) for i in f) for f in faces])
    for mt in mats if isinstance(mats, (list, tuple)) else [mats]:
        me.materials.append(mt)
    if mat_index is not None:
        me.polygons.foreach_set("material_index", np.asarray(mat_index, np.int32))
    me.update()
    for poly in me.polygons:
        poly.use_smooth = smooth
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    return ob


def box(name, center, size, mat):
    return base.cube(name, center, size, mat)


def glowable(name, colour, metal=0.0, rough=0.5, glow=(1.0, 0.22, 0.02)):
    mt = material(name, colour, metal=metal, rough=rough)
    b = mt.node_tree.nodes.get("Principled BSDF")
    b.inputs["Emission Color"].default_value = (*glow, 1.0)
    b.inputs["Emission Strength"].default_value = 0.0
    return mt


def set_glow(mt, s):
    mt.node_tree.nodes.get("Principled BSDF").inputs["Emission Strength"].default_value = s


def water_material():
    """Bay water: a refracting, rippled surface and a green-blue volume (even density: fast). After EP.27's sea."""
    mt = bpy.data.materials.new("Bay water")
    mt.use_nodes = True
    nt = mt.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    surf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    surf.inputs["Base Color"].default_value = (0.90, 0.97, 1.0, 1)
    surf.inputs["Roughness"].default_value = 0.04
    surf.inputs["IOR"].default_value = 1.333
    surf.inputs["Transmission Weight"].default_value = 1.0
    n1 = nt.nodes.new("ShaderNodeTexNoise")
    n1.inputs["Scale"].default_value = 0.35
    n1.inputs["Detail"].default_value = 4.0
    nt.links.new(tc.outputs["Object"], n1.inputs["Vector"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.18
    bp.inputs["Distance"].default_value = 0.4
    nt.links.new(n1.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], surf.inputs["Normal"])
    nt.links.new(surf.outputs[0], out.inputs["Surface"])
    absorb = nt.nodes.new("ShaderNodeVolumeAbsorption")
    absorb.inputs["Color"].default_value = (0.22, 0.55, 0.52, 1)
    absorb.inputs["Density"].default_value = 0.09
    scat = nt.nodes.new("ShaderNodeVolumeScatter")
    scat.inputs["Color"].default_value = (0.30, 0.62, 0.60, 1)
    scat.inputs["Density"].default_value = 0.01
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(absorb.outputs[0], add.inputs[0])
    nt.links.new(scat.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs["Volume"])
    return mt


def corrugated_ring(name, r, z0, z1, mat, segs=120, rings=24, amp=0.22, start=0.0, sweep=2 * math.pi):
    """A sheet-pile ring: a cylinder wall whose radius waves in and out (the piles' corrugation); open top and bottom."""
    verts, faces = [], []
    n_a = int(segs * sweep / (2 * math.pi)) + 1
    for j in range(rings + 1):
        z = z0 + (z1 - z0) * j / rings
        for i in range(n_a):
            a = start + sweep * i / (n_a - 1)
            rr = r + amp * math.sin(a * segs / 2)
            verts.append((rr * math.cos(a), rr * math.sin(a), z))
    for j in range(rings):
        for i in range(n_a - 1):
            a0 = j * n_a + i
            faces.append((a0, a0 + 1, a0 + n_a + 1, a0 + n_a))
    return mesh_object(name, verts, faces, mat)


def disc(name, r, z0, z1, mat, segs=72, start=0.0, sweep=2 * math.pi):
    """A solid cylinder or a part of one (a pie slice when sweep < 2 pi)."""
    verts, faces = [], []
    full = sweep >= 2 * math.pi - 1e-9
    n_a = segs if full else int(segs * sweep / (2 * math.pi)) + 1
    for z in (z0, z1):
        for i in range(n_a):
            a = start + (sweep * i / (segs if full else n_a - 1))
            verts.append((r * math.cos(a), r * math.sin(a), z))
    verts += [(0.0, 0.0, z0), (0.0, 0.0, z1)]
    c0, c1 = 2 * n_a, 2 * n_a + 1
    rng_ = range(n_a) if full else range(n_a - 1)
    for i in rng_:
        i2 = (i + 1) % n_a
        faces.append((i, i2, n_a + i2, n_a + i))
        faces.append((c0, i2, i))
        faces.append((c1, n_a + i, n_a + i2))
    if not full:
        faces.append((c0, 0, n_a, c1))
        faces.append((c0, c1, 2 * n_a - 1, n_a - 1))
    return mesh_object(name, verts, faces, mat)


class Dolphin:
    """One dolphin at (x, y). The struck one is built in halves (near: x > its centre; far) so the cut-aways can drop the near half,
    with a dentable ring and a rock fill in the far half."""

    def __init__(self, k, x, y, mats, struck=False):
        self.struck = struck
        self.cut_walls = []
        self.x, self.y = x, y
        steel, cap, band, rock, lamp = mats
        z_ring_top = m.CAP_TOP - 1.5
        self.parts_near, self.parts_far, self.parts = [], [], []
        if not struck:
            ring = corrugated_ring(f"Ring {k}", m.DOL_R, m.SEA_BED - 1.0, z_ring_top, steel, segs=96, rings=6)
            ring.location = (x, y, 0.0)
            c = disc(f"Cap {k}", m.DOL_R + 0.4, z_ring_top, m.CAP_TOP, cap)
            c.location = (x, y, 0.0)
            b = disc(f"Band {k}", m.DOL_R + 0.45, m.CAP_TOP - 0.9, m.CAP_TOP - 0.4, band)
            b.location = (x, y, 0.0)
            self.parts = [ring, c, b]
        else:
            for half, start in (("near", -math.pi / 2), ("far", math.pi / 2)):
                ring = corrugated_ring(f"Ring {half}", m.DOL_R, m.TIP, z_ring_top, steel, segs=120, rings=40, start=start, sweep=math.pi)
                ring.location = (x, y, 0.0)
                c = disc(f"Cap {half}", m.DOL_R + 0.4, z_ring_top, m.CAP_TOP, cap, start=start, sweep=math.pi)
                c.location = (x, y, 0.0)
                b = disc(f"Band {half}", m.DOL_R + 0.45, m.CAP_TOP - 0.9, m.CAP_TOP - 0.4, band, start=start, sweep=math.pi)
                b.location = (x, y, 0.0)
                (self.parts_near if half == "near" else self.parts_far).extend([ring, c, b])
                if half == "near":
                    self.ring_near = ring
                else:
                    self.ring_far = ring
            self.rings = []
            for ring in (self.ring_near, self.ring_far):
                n = len(ring.data.vertices)
                co = np.zeros(n * 3)
                ring.data.vertices.foreach_get("co", co)
                self.rings.append((ring, co.reshape(n, 3)))
            self.rock = self._rocks(rock)
            for sy in (-1, 1):                                    # the ring's walls where the section cuts them: two dark bars
                ob = box(f"Cut wall {sy}", (x + 0.05, y + sy * m.DOL_R, (m.TIP + z_ring_top) / 2), (0.1, 0.7, z_ring_top - m.TIP), steel)
                ob.hide_render = True
                self.cut_walls.append(ob)
        bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.12, depth=1.6, location=(x, y, m.CAP_TOP + 0.8))
        post = bpy.context.object
        post.data.materials.append(cap)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=0.28, location=(x, y, m.CAP_TOP + 1.7))
        light = bpy.context.object
        light.data.materials.append(lamp)
        self.extras = [post, light]

    def _rocks(self, mat):
        """Crushed rock packed in the far half: low-poly stones (one mesh), moved per frame where the dent packs them tighter."""
        rng = np.random.default_rng(33)
        ico_v = np.array([[-1, 1.618, 0], [1, 1.618, 0], [-1, -1.618, 0], [1, -1.618, 0], [0, -1, 1.618], [0, 1, 1.618], [0, -1, -1.618],
                          [0, 1, -1.618], [1.618, 0, -1], [1.618, 0, 1], [-1.618, 0, -1], [-1.618, 0, 1]], float)
        ico_v /= np.linalg.norm(ico_v[0])
        ico_f = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
                 (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
        centres, sizes = [], []
        z_top = m.CAP_TOP - 1.5
        while len(centres) < 1500:
            r = (m.DOL_R - 0.6) * math.sqrt(rng.uniform(0, 1))
            a = rng.uniform(math.pi / 2 - 0.05, 3 * math.pi / 2 + 0.05)
            p = (r * math.cos(a), r * math.sin(a), rng.uniform(m.SEA_BED, z_top - 0.3))
            if p[0] > 0.25:
                continue
            centres.append(p)
            sizes.append(rng.uniform(0.35, 0.75))
        verts, faces = [], []
        for c, s in zip(centres, sizes):
            b = len(verts)
            rot = np.linalg.qr(rng.standard_normal((3, 3)))[0]
            sc = np.array([s, s * rng.uniform(0.6, 1.0), s * rng.uniform(0.5, 0.9)])
            verts.extend(list((ico_v * sc) @ rot.T + np.array(c)))
            faces.extend([(b + i, b + j, b + k) for i, j, k in ico_f])
        ob = mesh_object("Rock fill", verts, faces, mat)
        ob.location = (self.x, self.y, 0.0)
        self.rock_centres = np.array(centres)
        self.rock_v0 = np.array(verts)
        return ob

    def dent(self, d):
        """The ring's front (toward -y) pushed in by d, most at the bow's height; the rock behind it moves with it, packing tighter."""
        for ring, co0 in self.rings:
            a = np.arctan2(co0[:, 1], co0[:, 0])
            front = np.clip(np.cos(a + math.pi / 2), 0.0, 1.0) ** 3                  # 1 straight toward -y
            zf = np.exp(-((co0[:, 2] - 1.0) / 7.0) ** 2)
            out = co0.copy()
            out[:, 1] += d * front * zf
            ring.data.vertices.foreach_set("co", out.ravel())
            ring.data.update()
        c = self.rock_centres
        w = np.clip(1.0 - (c[:, 1] + m.DOL_R) / 7.0, 0.0, 1.0) * np.exp(-((c[:, 2] - 1.0) / 8.0) ** 2)
        shift = np.repeat(w, 12)[:, None] * np.array([0.0, d * 0.85, -0.15 * d])
        self.rock.data.vertices.foreach_set("co", (self.rock_v0 + shift).ravel())
        self.rock.data.update()

    def set_cut(self, cut):
        for ob in self.parts_near:
            ob.hide_render = cut
        if self.struck:
            self.rock.hide_render = not cut
        else:
            for ob in self.parts + self.extras:
                ob.hide_render = cut and self.x > CX + 1.0          # the camera side of the section is cut away


def ship(mats):
    """A container ship (200 m), bow tip at the origin pointing +y: hull from stations (finer near the bow), deck boxes, the
    superstructure and funnel at the stern. Returns the root, the hull object and its rest vertices (for the bow crumpling)."""
    hull_m, deck_m, white, funnel, box_mats = mats
    stations = sorted(set(list(np.arange(-200.0, -40.0, 10.0)) + list(np.arange(-40.0, 0.01, 1.0))))
    zs = [-11.0, -8.0, -5.0, -2.0, 0.0, 3.0, 6.0, 8.0]

    def half_width(y, z):
        if y < -40.0:
            w = m.SHIP_B / 2
        else:
            u = -y / 40.0
            w = m.SHIP_B / 2 * (u ** 0.55)
        if y < -190.0:
            w *= 0.85 + 0.15 * (200.0 + y) / 10.0
        flare = 1.0 if z > -2 else 0.88 + 0.12 * (z + 11.0) / 9.0
        return max(w * flare, 0.05)

    def bow_shift(z):
        if z <= -8.0:
            return 2.2                       # the bulb at the keel line
        if z <= -5.0:
            return 2.6
        if z <= 0.0:
            return 0.0
        return 0.45 * z                      # the raked stem above the water

    verts, faces, ring_n = [], [], 2 * len(zs)
    for y in stations:
        for side in (-1, 1):
            for z in (zs if side == 1 else zs[::-1]):
                yy = y + (bow_shift(z) if y > -0.5 else bow_shift(z) * max(0.0, 1.0 + y / 6.0))
                verts.append((side * half_width(y, z), yy, z))
    n_st = len(stations)
    for s in range(n_st - 1):
        for i in range(ring_n):
            a, b = s * ring_n + i, s * ring_n + (i + 1) % ring_n
            faces.append((a, b, b + ring_n, a + ring_n))
    stern = list(range(ring_n))
    faces.append(tuple(stern[::-1]))
    hull = mesh_object("Hull", verts, faces, hull_m)
    root = bpy.data.objects.new("Ship root", None)
    bpy.context.collection.objects.link(root)
    hull.parent = root
    parts = [box("Deck", (0.0, -105.0, 8.05), (m.SHIP_B - 1.2, 170.0, 0.1), deck_m), box("Forecastle", (0.0, -14.0, 9.2), (14.0, 22.0, 2.4), deck_m),
             box("Superstructure", (0.0, -182.0, 17.0), (24.0, 14.0, 18.0), white), box("Bridge deck", (0.0, -176.5, 25.5), (m.SHIP_B, 5.0, 3.0), white),
             box("Funnel", (0.0, -192.0, 27.0), (6.0, 7.0, 10.0), funnel)]
    # containers: bays of 40 ft boxes, 12 rows across, 3-5 tiers (one mesh, colours by face)
    rng = np.random.default_rng(3300)
    cv, cf, ci = [], [], []
    for bay in range(9):
        y0 = -165.0 + bay * 16.5
        tiers = int(rng.integers(3, 6))
        for row in range(12):
            x0 = -14.6 + row * 2.45
            for tier in range(tiers):
                z0 = 8.1 + tier * 2.62
                lo = np.array([x0, y0, z0])
                hi = lo + np.array([2.4, 12.1, 2.55])
                b = len(cv)
                cv.extend([(lo[0], lo[1], lo[2]), (hi[0], lo[1], lo[2]), (hi[0], hi[1], lo[2]), (lo[0], hi[1], lo[2]),
                           (lo[0], lo[1], hi[2]), (hi[0], lo[1], hi[2]), (hi[0], hi[1], hi[2]), (lo[0], hi[1], hi[2])])
                col = int(rng.integers(0, len(box_mats)))
                for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (1, 2, 6, 5), (3, 0, 4, 7)):
                    cf.append(tuple(b + i for i in f))
                    ci.append(col)
    boxes = mesh_object("Containers", cv, cf, box_mats, mat_index=ci)
    for ob in parts + [boxes]:
        ob.parent = root
    n = len(hull.data.vertices)
    co = np.zeros(n * 3)
    hull.data.vertices.foreach_get("co", co)
    return root, hull, co.reshape(n, 3), parts[1]


def hull_material():
    """Navy topsides, a white boot top at the waterline, red antifouling below (by height in object space)."""
    mt = bpy.data.materials.new("Hull paint")
    mt.use_nodes = True
    nt = mt.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = 0.45
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    el = ramp.color_ramp.elements
    el[0].position, el[0].color = 0.0, (0.45, 0.06, 0.05, 1)
    el[1].position, el[1].color = 0.585, (0.85, 0.85, 0.82, 1)
    e3 = el.new(0.62)
    e3.color = (0.04, 0.07, 0.16, 1)
    mp = nt.nodes.new("ShaderNodeMapRange")
    mp.inputs["From Min"].default_value = -11.0
    mp.inputs["From Max"].default_value = 8.0
    nt.links.new(sep.outputs["Z"], mp.inputs["Value"])
    nt.links.new(mp.outputs["Result"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    return mt


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
    scene.view_settings.exposure = 0.1
    if hasattr(scene.view_settings, "use_white_balance"):
        scene.view_settings.use_white_balance = True
        scene.view_settings.white_balance_temperature = 7200.0
    scene.world = bpy.data.worlds.new("World")
    sun_to = cinematic.sun_vector((0.75, -0.45), 17.0)                 # low sun from the right, ahead: the struck side lit
    cinematic.apply_sky(scene, sun_to, strength=0.26, dust=0.6)
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    sun.data.energy, sun.data.angle = 6.0, 0.02
    sun.data.color = (1.0, 0.76, 0.52)
    sun.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()
    bpy.ops.object.light_add(type="AREA", location=(30.0, CY, -4.0))      # lights the section from the camera side
    fill = bpy.context.object
    fill.data.size, fill.data.color, fill.data.energy = 30.0, (1.0, 0.9, 0.8), 0.0
    fill.rotation_euler = (0.0, math.radians(-90), 0.0)
    fill.visible_camera = False
    # sea, bed and the cut-away halves (near = x > 0, the camera side of the sections)
    water = water_material()
    sand = material("Sea bed", (0.36, 0.31, 0.22), rough=0.95)
    soil = glowable("Bed in section", (0.17, 0.13, 0.09), rough=0.95)
    sea_far = box("Sea far half", (-2500.0, 0.0, (m.SEA_BED - 1.0) / 2), (5000.0, 8000.0, -m.SEA_BED + 1.0), water)
    sea_near = box("Sea near half", (2500.0, 0.0, (m.SEA_BED - 1.0) / 2), (5000.0, 8000.0, -m.SEA_BED + 1.0), water)
    for ob in (sea_far, sea_near):
        ob.visible_shadow = False
    box("Bed far", (-2500.0 - 0.15, 0.0, m.SEA_BED - 15.0), (5000.0, 8000.0, 30.0), soil)      # its face just behind the section plane
    bed_near = box("Bed near", (2500.0, 0.0, m.SEA_BED - 15.0), (5000.0, 8000.0, 30.0), soil)
    box("Bed top far", (-3000.0, 0.0, m.SEA_BED - 0.02), (6000.0, 12000.0, 0.04), sand)
    bed_top_near = box("Bed top near", (3000.0, 0.0, m.SEA_BED - 0.02), (6000.0, 12000.0, 0.04), sand)
    hills = material("Shore", (0.16, 0.20, 0.12), rough=1.0)
    for x, y, sx in ((-1800, 2600, 900), (1500, 3000, 1200), (2600, -1400, 700), (-2600, -2200, 800)):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=1.0, location=(x, y, -40))
        ob = bpy.context.object
        ob.scale = (sx, sx * 0.5, 70)
        ob.data.materials.append(hills)
    # the bridge: two main piers with towers, the deck, stay cables, approach piers
    concrete = glowable("Concrete", (0.62, 0.61, 0.58), rough=0.8)
    cable_m = material("Stay cables", (0.95, 0.72, 0.10), metal=0.3, rough=0.35)
    for px in (0.0, PIER2_X):
        box(f"Footing {px}", (px, 0.0, (m.SEA_BED + m.CAP_TOP) / 2), (2 * m.PIER_HALF[0], 2 * m.PIER_HALF[1], m.CAP_TOP - m.SEA_BED), concrete)
        for z0, z1, w0, w1 in ((m.CAP_TOP, DECK_Z, 9.0, 7.0), (DECK_Z, TOWER_TOP, 7.0, 4.5)):
            verts = []
            for z, w in ((z0, w0), (z1, w1)):
                verts += [(px - w / 2, -w * 0.45, z), (px + w / 2, -w * 0.45, z), (px + w / 2, w * 0.45, z), (px - w / 2, w * 0.45, z)]
            mesh_object(f"Tower {px} {z0}", verts, [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7), (3, 2, 1, 0)], concrete)
        for side in (-1, 1):
            for k in range(14):
                xa = px + side * (24.0 + 13.0 * k)
                za = TOWER_TOP - 2.0 - 2.4 * k
                a, b = Vector((px, 0.0, za)), Vector((xa, 0.0, DECK_Z + 2.0))
                d = b - a
                bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.22, depth=d.length, location=(a + b) / 2)
                ob = bpy.context.object
                ob.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
                ob.data.materials.append(cable_m)
    box("Deck", (PIER2_X / 2, 0.0, DECK_Z), (2400.0, 28.0, 4.0), concrete)
    for px in list(np.arange(-130.0, -1200.0, -110.0)) + list(np.arange(PIER2_X + 130.0, 1500.0, 110.0)):
        box(f"Approach pier {px:.0f}", (float(px), 0.0, (m.SEA_BED + DECK_Z) / 2), (4.0, 12.0, DECK_Z - m.SEA_BED), concrete)
    # dolphins in front of both main piers (the channel side, -y)
    steel = glowable("Sheet piles", (0.20, 0.17, 0.14), metal=0.7, rough=0.55)
    capm = glowable("Dolphin cap", (0.70, 0.69, 0.66), rough=0.75)
    band = material("Dolphin band", (0.95, 0.70, 0.05), rough=0.5)
    rock = glowable("Crushed rock", (0.42, 0.40, 0.37), rough=0.9)
    lamp = material("Navigation light", (0.2, 1.0, 0.3), emission=4.0)
    mats = (steel, capm, band, rock, lamp)
    dolphins = []
    for px in (0.0, PIER2_X):
        for k, (dx, dy) in enumerate(m.dolphin_centres()):
            x = px + (dx if px == 0.0 else -dx)
            dolphins.append(Dolphin(f"{px:.0f} {k}", x, dy, mats, struck=(px == 0.0 and k == m.HIT)))
    struck = next(d for d in dolphins if d.struck)
    # the ship
    navy = hull_material()
    deck_m = material("Ship deck", (0.32, 0.12, 0.08), rough=0.7)
    white = material("Superstructure", (0.88, 0.88, 0.85), rough=0.5)
    funnel = material("Funnel", (0.70, 0.10, 0.06), rough=0.5)
    box_mats = [material(f"Container {k}", c, rough=0.55) for k, c in enumerate(((0.65, 0.12, 0.08), (0.08, 0.30, 0.60), (0.15, 0.45, 0.20),
                                                                                    (0.80, 0.55, 0.10), (0.60, 0.60, 0.58), (0.10, 0.12, 0.14)))]
    root, hull, hull0, forecastle = ship((navy, deck_m, white, funnel, box_mats))
    spray_m = material("Spray", (0.92, 0.95, 0.97), rough=0.2)
    spray_m.node_tree.nodes.get("Principled BSDF").inputs["Alpha"].default_value = 0.55
    chip_m = material("Concrete chips", (0.62, 0.61, 0.58), rough=0.85)
    pieces = []
    for k, (_, _, _, size, kind) in enumerate(m.spray()):
        if kind == "water":
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=size / 2, location=(0, 0, -60))
            ob = bpy.context.object
            ob.data.materials.append(spray_m)
        else:
            ob = box(f"Chip {k}", (0, 0, -60), (size, size * 0.7, size * 0.5), chip_m)
        pieces.append(ob)
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam

    def render(sh, path):
        scene.render.resolution_x, scene.render.resolution_y = round(FRAME[0] * args.res_scale), round(FRAME[1] * args.res_scale)
        t = sh["t"]
        cut, force_on = bool(sh.get("cut")), bool(sh.get("force"))
        st = m.ship_state(t)
        sea_near.hide_render = cut
        bed_near.hide_render = cut
        bed_top_near.hide_render = cut
        water.node_tree.nodes["Volume Absorption"].inputs["Density"].default_value = 0.02 if cut else 0.09
        for d in dolphins:
            d.set_cut(cut)
        fill.data.energy = (1500.0 if force_on else 4000.0) if cut else 0.0
        for ob in struck.cut_walls:
            ob.hide_render = not cut
        struck.dent(st["ring_dent"])
        # the ship: its bow tip at bow_y on the dolphin's line; the bow crumples back by bow_crush with wrinkles
        root.location = (CX, st["bow_y"], 0.0)
        c = st["bow_crush"]
        out = hull0.copy()
        if c > 0:
            y = hull0[:, 1]
            zone = 9.0
            g = np.clip(1.0 + y / zone, 0.0, 1.0)
            out[:, 1] = y - c * g
            wr = np.sin(y * 3.1 + hull0[:, 2] * 1.7) * 0.18 * c / 2.7 * g
            out[:, 0] = hull0[:, 0] * (1.0 + 0.10 * g * c / 2.7) + np.sign(hull0[:, 0]) * wr
        hull.data.vertices.foreach_set("co", out.ravel())
        hull.data.update()
        forecastle.location = (0.0, -14.0 - 0.6 * c, 9.2)
        air = 0
        for k, ob in enumerate(pieces):
            p = m.spray_pose(k, t)
            if p is None:
                ob.hide_render = True
                continue
            ob.hide_render = False
            ob.location = tuple(p[0])
            air += p[1]
        f = st["force"]
        glow = 3.0 * min(1.0, f / m.F_MAX) if force_on else 0.0
        for mt in (steel, capm, rock, soil):
            set_glow(mt, glow * (0.12 if mt is soil else (0.5 if mt is capm else 1.0)))
        info = {"t": round(t, 6), "bow_y": round(st["bow_y"], 4), "give": round(st["give"], 4), "bow_crush": round(c, 4),
                "ring_dent": round(st["ring_dent"], 4), "force_MN": round(f / 1e6, 2), "cut": cut, "glow": round(glow, 3), "airborne": air}
        cm = sh["cam"]
        loc, tgt = Vector(cm["loc"]), Vector(cm["target"])
        dd = cam.data
        dd.sensor_fit, dd.sensor_width, dd.lens, dd.clip_start, dd.clip_end = "HORIZONTAL", 36.0, cm["lens"], 0.1, 20000.0
        dd.dof.use_dof = True
        dd.dof.focus_distance = (tgt - loc).length
        dd.dof.aperture_fstop = cm.get("fstop", 11.0)
        base.set_camera(cam, loc, tgt)
        bpy.context.view_layer.update()
        from mathutils import Matrix
        info["subject_box"] = hook_gate.project_box(scene, cam, Matrix.Identity(4), (CX - 13.0, CY - m.DOL_R - 26.0, -1.0),
                                                    (CX + 13.0, CY + m.DOL_R, 10.0))
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
        print("DOLPHIN_FRAME " + json.dumps(info), flush=True)
    (args.out / f"dolphin-frames-{frames[0]:05d}.json").write_text(json.dumps({"renderer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                                                              "frames": out}, indent=1))


if __name__ == "__main__":
    main()
