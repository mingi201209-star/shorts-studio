"""EP.14 tempered glass: 100 % 3D renderer (Blender, Cycles CPU), house style of EP.13 (golden hour, red car, depth of field).
Car scenes: the CC0 sedan's driver-side front window is replaced, from the moment of the hit, by a mesh of several hundred glass cubes
whose positions, spins and crack states come from glass_motion every frame (dark glass until the crack front reaches a cube, then
frosty white, then clear tumbling cubes); an emergency hammer strikes it from inside; the same window as ordinary glass breaks into long
shards; a stone stars the windshield (laminated: cracks, nothing falls out). Factory hall: a pane leaves the tempering furnace glowing
and runs under air nozzles; a magnified cross-section shows the skins setting first and the core squeezing them (arrows); a steel ball
bounces off a tempered pane. No text anywhere in the picture."""
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
from benchmarks.belt_limiter import render_belt_3d as rb  # noqa: E402
from benchmarks.guardrail_end.render_terminal_3d import build_world, mesh_object  # noqa: E402
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402
from benchmarks.tempered_glass import glass_motion as gm  # noqa: E402
from benchmarks.tempered_glass import glass_timeline as tl  # noqa: E402

material, cube = base.material, base.cube
FRAME = (1080, 1920)
PAINT = (1.75, 0.30, 0.24)
INTERIOR_TINT = (0.22, 0.22, 0.25)
LAB = Vector(tl.LAB)
SLAB = LAB + Vector((0.0, 20.0, 0.0))
RIG = LAB + Vector((0.0, 40.0, 0.0))
KNIFE_Y = 0.55                        # the air knives stand this far past the furnace mouth
WINDOW_OBJECTS = ("Front side glass.003", "Front side glass.002")
CENTRE_SHIFT = 0.0013                 # the CC0 pane runs from x -0.5982 to -0.5956: cells are centred in it


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


def glass_mat(name, colour, transmission=1.0, rough=0.02, emission=0.0):
    m = material(name, colour, rough=rough, emission=emission)
    s = m.node_tree.nodes.get("Principled BSDF")
    s.inputs["Transmission Weight"].default_value = transmission
    s.inputs["IOR"].default_value = 1.52
    return m


def emissive(name, colour, strength):
    m = material(name, colour, rough=0.5)
    s = m.node_tree.nodes.get("Principled BSDF")
    s.inputs["Emission Color"].default_value = (*colour, 1)
    s.inputs["Emission Strength"].default_value = strength
    return m


def set_emission(m, colour, strength):
    s = m.node_tree.nodes.get("Principled BSDF")
    s.inputs["Emission Color"].default_value = (*colour, 1)
    s.inputs["Emission Strength"].default_value = strength


def cut_window(cab):
    """The CC0 cab is solid behind its glass (a wall at x -0.588). Cut a real opening, a little inside the driver window's outline, so the
    inside shots look out through the glass and the burst opens onto the cabin."""
    def prism(name, uv, normal):
        mid = gm.uv_to_world(uv[:, 0], uv[:, 1])
        n = len(uv)
        verts = [tuple(p + normal * 0.035) for p in mid] + [tuple(p - normal * 0.035) for p in mid]
        faces = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))] + [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
        me = bpy.data.meshes.new(name)
        me.from_pydata(verts, [], faces)
        me.update()
        ob = bpy.data.objects.new(name, me)
        bpy.context.collection.objects.link(ob)
        return ob
    uj, top_u = gm.U_JOINT, 0.4066 - gm.Y_REAR
    main = np.array([(0.012, 0.922), (uj + 0.01, 0.922), (uj + 0.01, 1.078), (top_u - 0.004, 1.136), (0.012, 1.136)])
    front = np.array([(uj - 0.01, 0.922), (uj + gm.FRONT_LEN - 0.03, 0.922), (uj - 0.01, 1.076)])
    cutters = [prism("Window cutter main", main, gm.OUT_MAIN), prism("Window cutter front", front, gm.OUT_FRONT)]
    for c in cutters:
        mod = cab.modifiers.new(c.name, "BOOLEAN")
        mod.operation, mod.object, mod.solver = "DIFFERENCE", c, "EXACT"
        with bpy.context.temp_override(object=cab, active_object=cab, selected_objects=[cab]):
            bpy.ops.object.modifier_apply(modifier=mod.name)
    for c in cutters:
        me = c.data
        bpy.data.objects.remove(c)
        bpy.data.meshes.remove(me)


def dark_backfaces(mat):
    nt = mat.node_tree
    out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None)
    if out is None or not out.inputs["Surface"].links:
        return
    src = out.inputs["Surface"].links[0].from_socket
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    trim = nt.nodes.new("ShaderNodeBsdfPrincipled")
    trim.inputs["Base Color"].default_value = (0.06, 0.06, 0.07, 1)
    trim.inputs["Roughness"].default_value = 0.8
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(geo.outputs["Backfacing"], mix.inputs["Fac"])
    nt.links.new(src, mix.inputs[1])
    nt.links.new(trim.outputs["BSDF"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])


def _rodrigues(v, rot):
    """Rotate offsets v (N, K, 3) by rotation vectors rot (N, 3)."""
    th = np.linalg.norm(rot, axis=1)
    k = np.where(th[:, None] > 1e-9, rot / np.maximum(th, 1e-9)[:, None], 0.0)[:, None, :]
    c, s = np.cos(th)[:, None, None], np.sin(th)[:, None, None]
    kv = np.cross(np.broadcast_to(k, v.shape), v)
    kd = np.sum(k * v, axis=-1, keepdims=True)
    return v * c + kv * s + k * kd * (1 - c)


class Pane:
    """The tempered window as cubes: rest prisms from glass_motion.cells, moved per frame."""

    def __init__(self, dark, frost, clear):
        quads, cen = gm.cells()
        n = len(quads)
        nrm = gm.outward(cen[:, 0])
        shift = nrm * CENTRE_SHIFT
        c3 = gm.uv_to_world(quads[..., 0], quads[..., 1]) + shift[:, None, :]          # (n, 4, 3) corners on the mid plane
        h = 0.5 * 0.003
        verts = np.concatenate([c3 + nrm[:, None, :] * h, c3 - nrm[:, None, :] * h], axis=1)   # (n, 8, 3): outer 0-3, inner 4-7
        self.centre0 = gm.uv_to_world(cen[:, 0], cen[:, 1]) + shift
        self.off0 = verts - self.centre0[:, None, :]
        faces = []
        for i in range(n):
            b = 8 * i
            faces += [(b, b + 1, b + 2, b + 3), (b + 7, b + 6, b + 5, b + 4)]
            for j in range(4):
                k = (j + 1) % 4
                faces.append((b + j, b + 4 + j, b + 4 + k, b + k))
        self.ob = mesh_object("Tempered pane cubes", verts.reshape(-1, 3), faces, dark, smooth=False)
        for m in (frost, clear):
            self.ob.data.materials.append(m)
        self.n = n

    def set(self, t, visible):
        self.ob.hide_render = not visible
        if not visible:
            return {}
        pos, rot, cracked = gm.piece_state(t)
        released = t >= gm.T_RELEASE
        off = self.off0.copy()
        if not released:
            off[cracked] *= 0.93                       # a hair of gap along every crack: the dice pattern shows before it moves
        v = pos[:, None, :] + _rodrigues(off, rot)
        self.ob.data.vertices.foreach_set("co", v.reshape(-1).astype(np.float32))
        mi = np.where(released, 2, np.where(cracked, 1, 0)).astype(np.int32)
        self.ob.data.polygons.foreach_set("material_index", np.repeat(mi, 6))
        self.ob.data.update()
        return {"cracked_fraction": round(float(np.mean(cracked)), 3), "released": bool(released), "landed_fraction": round(float(np.mean(pos[:, 2] <= gm.THICK + 1e-6)), 3)}


class Shards:
    """The same window as ordinary (annealed) glass: a few long shards."""

    def __init__(self, clear):
        polys = gm.shards()
        verts, faces, self.slices = [], [], []
        cen = np.array([p.mean(0) for p in polys])
        nrm = gm.outward(cen[:, 0])
        self.centre0 = gm.uv_to_world(cen[:, 0], cen[:, 1])
        for i, p in enumerate(polys):
            c3 = gm.uv_to_world(p[:, 0], p[:, 1])
            b = len(verts)
            k = len(p)
            for q in c3:
                verts.append(q + nrm[i] * 0.0015)
            for q in c3:
                verts.append(q - nrm[i] * 0.0015)
            faces.append(tuple(range(b, b + k)))
            faces.append(tuple(range(b + 2 * k - 1, b + k - 1, -1)))
            for j in range(k):
                faces.append((b + j, b + k + j, b + k + (j + 1) % k, b + (j + 1) % k))
            self.slices.append((b, 2 * k))
        self.verts0 = np.array(verts)
        self.ob = mesh_object("Annealed shards", verts, faces, clear, smooth=False)

    def set(self, t, visible):
        self.ob.hide_render = not visible
        if not visible:
            return
        pos, rot = gm.shard_state(t)
        v = self.verts0.copy()
        for i, (b, k) in enumerate(self.slices):
            off = (self.verts0[b:b + k] - self.centre0[i])[None]
            v[b:b + k] = pos[i] + _rodrigues(off, rot[i:i + 1])[0]
        self.ob.data.vertices.foreach_set("co", v.reshape(-1).astype(np.float32))
        self.ob.data.update()


class Windshield:
    """Star crack on the laminated windshield: ribbons along glass_motion.windshield_cracks, revealed as the crack front runs out."""

    def __init__(self, crack_mat, rock_mat):
        self.mat = crack_mat
        self.ob = None
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.012, location=(0, 0, -5))
        self.rock = bpy.context.object
        self.rock.data.materials.append(rock_mat)
        self.hit = gm.ws_point(gm.WS_HIT[0], gm.WS_HIT[1], lift=0.0)

    def set(self, t, visible):
        if self.ob is not None:
            me = self.ob.data
            bpy.data.objects.remove(self.ob)
            bpy.data.meshes.remove(me)
            self.ob = None
        self.rock.hide_render = not visible
        if not visible:
            return 0.0
        if t < 0:
            p = self.hit + gm.WS_OUT * (-t) * 28.0          # the stone comes in along the windshield normal
        else:
            p = self.hit + gm.WS_OUT * (0.015 + t * 4.0) + np.array([0.0, 0.0, 1.0]) * t * 2.0
        self.rock.location = tuple(p)
        if t <= 0:
            return 0.0
        reach = t * gm.V_CRACK
        verts, faces = [], []
        for line in gm.windshield_cracks():
            seg = np.linalg.norm(np.diff(line, axis=0), axis=1)
            closed = np.allclose(line[0], line[-1], atol=1e-6) or len(line) > 20
            if closed:
                r = float(np.mean(np.linalg.norm(line - gm.WS_HIT, axis=1)))
                if reach < 1.3 * r:
                    continue
                keep = len(line)
            else:
                cum = np.concatenate([[0.0], np.cumsum(seg)])
                keep = int(np.searchsorted(cum, reach)) + 1
                keep = min(keep, len(line))
                if keep < 2:
                    continue
            pts = line[:keep]
            d = np.gradient(pts, axis=0)
            d /= np.linalg.norm(d, axis=1, keepdims=True) + 1e-9
            side = np.stack([-d[:, 1], d[:, 0]], -1) * 0.0008
            a = gm.ws_point((pts + side)[:, 0], (pts + side)[:, 1])
            b2 = gm.ws_point((pts - side)[:, 0], (pts - side)[:, 1])
            base_i = len(verts)
            for qa, qb in zip(a, b2):
                verts += [tuple(qa), tuple(qb)]
            for i in range(len(pts) - 1):
                j = base_i + 2 * i
                faces.append((j, j + 1, j + 3, j + 2))
        if faces:
            self.ob = mesh_object("Windshield cracks", verts, faces, self.mat, smooth=False)
        return reach


class Hammer:
    def __init__(self):
        red = material("Hammer handle", (0.85, 0.08, 0.04), rough=0.35)
        black = material("Hammer head", (0.03, 0.03, 0.035), rough=0.4)
        steel = material("Hammer tip", (0.85, 0.86, 0.88), metal=1.0, rough=0.2)
        self.root = bpy.data.objects.new("Hammer", None)
        bpy.context.collection.objects.link(self.root)
        self.root.location = tuple(gm.HAMMER_PIVOT)
        tx, _, tz = gm.HAMMER_TIP_LOCAL
        bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.016, depth=0.60, location=(0, 0, tz - 0.32))
        h = bpy.context.object
        h.data.materials.append(red)
        h.parent = self.root
        head = cube("Hammer head", (tx + 0.072, 0.0, tz), (0.13, 0.034, 0.038), black)
        head.parent = self.root
        for sx, x in ((-1, tx + 0.005), (1, tx + 0.139)):
            bpy.ops.mesh.primitive_cone_add(vertices=16, radius1=0.012, radius2=0.0015, depth=0.012, location=(x, 0, tz), rotation=(0, sx * math.pi / 2, 0))
            c = bpy.context.object
            c.data.materials.append(steel)
            c.parent = self.root
        self.objs = [o for o in self.root.children]

    def set(self, t, visible):
        self.root.rotation_euler = (0.0, gm.hammer_angle(t), 0.0)
        for o in self.objs:
            o.hide_render = not visible


class Lab:
    """Factory hall with the tempering line, the magnified cross-section and the ball-drop rig."""

    def __init__(self):
        wall = material("Hall concrete", (0.09, 0.09, 0.095), rough=0.9)
        floor = material("Hall floor", (0.12, 0.115, 0.11), rough=0.8)
        cube("Hall floor", tuple(LAB + Vector((0, 30, -0.05))), (24, 90, 0.1), floor)
        cube("Hall ceiling", tuple(LAB + Vector((0, 30, 8.0))), (24, 90, 0.1), wall)
        for sx in (-1, 1):
            cube(f"Hall wall {sx}", tuple(LAB + Vector((sx * 12, 30, 4))), (0.1, 90, 8), wall)
        for sy in (-15, 75):
            cube(f"Hall end {sy}", tuple(LAB + Vector((0, sy, 4))), (24, 0.1, 8), wall)
        for site, e in ((LAB + Vector((0, 0.6, 3.2)), 900.0), (SLAB + Vector((0.8, -1.2, 2.6)), 500.0), (RIG + Vector((0.6, -0.8, 2.6)), 500.0)):
            bpy.ops.object.light_add(type="AREA", location=tuple(site))
            L = bpy.context.object
            L.data.energy, L.data.size, L.data.color = e, 2.5, (1.0, 0.86, 0.7)
            L.visible_camera = False
        steel = material("Furnace steel", (0.18, 0.19, 0.2), metal=0.7, rough=0.45)
        ceramic = material("Roller ceramic", (0.75, 0.73, 0.70), rough=0.6)
        self.glow = emissive("Furnace glow", (1.0, 0.26, 0.03), 3.5)          # deep orange: AgX washes strong emission out to white
        for name, c, d in (("Furnace top", (0, -0.8, 1.05), (1.5, 1.6, 0.1)), ("Furnace left", (-0.72, -0.8, 0.55), (0.1, 1.6, 1.0)),
                           ("Furnace right", (0.72, -0.8, 0.55), (0.1, 1.6, 1.0)), ("Furnace bottom", (0, -0.8, 0.12), (1.5, 1.6, 0.24))):
            cube(name, tuple(LAB + Vector(c)), d, steel)
        cube("Furnace back glow", tuple(LAB + Vector((0, -1.55, 0.6))), (1.34, 0.05, 0.9), self.glow)
        cube("Furnace roof glow", tuple(LAB + Vector((0, -0.8, 0.98))), (1.34, 1.5, 0.03), self.glow)
        for i in range(22):
            y = -1.45 + i * 0.18
            bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.035, depth=1.2, location=tuple(LAB + Vector((0, y, 0.42))), rotation=(0, math.pi / 2, 0))
            bpy.context.object.data.materials.append(ceramic)
        self.pane_mat = glass_mat("Hot pane", (0.85, 0.92, 0.9), transmission=0.6, rough=0.05)
        nt = self.pane_mat.node_tree
        bsdf = nt.nodes.get("Principled BSDF")
        bsdf.inputs["Emission Color"].default_value = (1.0, 0.24, 0.02, 1)
        geo, sep = nt.nodes.new("ShaderNodeNewGeometry"), nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(geo.outputs["Position"], sep.inputs[0])
        ahead = nt.nodes.new("ShaderNodeMath")                 # how far a point still is before the air knife: hot there, quenched past it
        ahead.operation = "SUBTRACT"
        ahead.inputs[0].default_value = LAB.y + KNIFE_Y
        nt.links.new(sep.outputs["Y"], ahead.inputs[1])
        hot = nt.nodes.new("ShaderNodeMath")
        hot.operation, hot.use_clamp = "MULTIPLY", True
        hot.inputs[1].default_value = 30.0
        nt.links.new(ahead.outputs[0], hot.inputs[0])
        self.glow_value = nt.nodes.new("ShaderNodeValue")
        strength = nt.nodes.new("ShaderNodeMath")
        strength.operation = "MULTIPLY"
        nt.links.new(hot.outputs[0], strength.inputs[0])
        nt.links.new(self.glow_value.outputs[0], strength.inputs[1])
        nt.links.new(strength.outputs[0], bsdf.inputs["Emission Strength"])
        self.pane = cube("Hot pane", tuple(LAB), (0.9, 0.6, 0.006), self.pane_mat)
        # air knives: a slot bar above and below the rollers, each blowing a thin sheet of air onto the glass
        self.curtain_mat = material("Air sheet", (0.6, 0.8, 1.0), rough=0.3)
        cn = self.curtain_mat.node_tree
        cb = cn.nodes.get("Principled BSDF")
        cb.inputs["Alpha"].default_value = 0.35
        cb.inputs["Emission Color"].default_value = (0.6, 0.8, 1.0, 1)
        wave = cn.nodes.new("ShaderNodeTexWave")
        wave.wave_type, wave.bands_direction = "BANDS", "Z"
        wave.inputs["Scale"].default_value = 9.0
        wave.inputs["Distortion"].default_value = 4.0
        self.wave = wave
        em = cn.nodes.new("ShaderNodeMath")
        em.operation = "MULTIPLY"
        em.inputs[1].default_value = 0.0
        self.curtain_em = em
        cn.links.new(wave.outputs["Fac"], em.inputs[0])
        cn.links.new(em.outputs[0], cb.inputs["Emission Strength"])
        self.curtains = []
        for z0, z1, tag in ((0.70, 0.462, "upper"), (0.20, 0.448, "lower")):
            cube(f"Air knife bar {tag}", tuple(LAB + Vector((0, KNIFE_Y, z0 + (0.04 if z0 > 0.455 else -0.04)))), (1.25, 0.10, 0.08), steel)
            cube(f"Air knife slot {tag}", tuple(LAB + Vector((0, KNIFE_Y, z0))), (1.15, 0.02, 0.01), material(f"Slot {tag}", (0.02, 0.02, 0.02)))
            c = cube(f"Air sheet {tag}", tuple(LAB + Vector((0, KNIFE_Y, (z0 + z1) / 2))), (1.1, 0.006, abs(z1 - z0)), self.curtain_mat)
            self.curtains.append(c)
        for sx in (-1, 1):
            cube(f"Air knife post {sx}", tuple(LAB + Vector((sx * 0.68, KNIFE_Y, 0.45))), (0.05, 0.05, 0.9), steel)
        # magnified cross-section of a tempered pane: two skins and a core
        self.skin_mat = [glass_mat(f"Skin {k}", (0.55, 0.70, 0.85), transmission=0.2, rough=0.2) for k in range(2)]
        self.core_mat = glass_mat("Core", (0.75, 0.55, 0.50), transmission=0.2, rough=0.2)
        self.skins = [cube("Skin bottom", tuple(SLAB + Vector((0, 0, 0.67))), (1.0, 0.5, 0.08), self.skin_mat[0]),
                      cube("Skin top", tuple(SLAB + Vector((0, 0, 0.93))), (1.0, 0.5, 0.08), self.skin_mat[1])]
        self.core = cube("Core", tuple(SLAB + Vector((0, 0, 0.80))), (1.0, 0.5, 0.18), self.core_mat)
        stand = material("Stand", (0.15, 0.15, 0.16), metal=0.6, rough=0.4)
        cube("Slab stand", tuple(SLAB + Vector((0, 0, 0.3))), (0.3, 0.3, 0.6), stand)
        blue = emissive("Squeeze arrow", (0.25, 0.55, 1.0), 4.0)
        red = emissive("Pull arrow", (1.0, 0.25, 0.12), 4.0)
        self.arrows = []
        for z, mat, inward in ((0.67, blue, True), (0.93, blue, True), (0.80, red, False)):
            for side in (-1, 1):
                root = bpy.data.objects.new("Arrow", None)
                bpy.context.collection.objects.link(root)
                root.location = tuple(SLAB + Vector((side * 0.62, -0.26, z)))
                d = -side if inward else side
                root.rotation_euler = (0, d * math.pi / 2, 0)
                bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.012, depth=0.14, location=(0, 0, 0.0))
                sh = bpy.context.object
                sh.data.materials.append(mat)
                sh.parent = root
                bpy.ops.mesh.primitive_cone_add(vertices=16, radius1=0.03, radius2=0.0, depth=0.06, location=(0, 0, 0.1))
                hd = bpy.context.object
                hd.data.materials.append(mat)
                hd.parent = root
                self.arrows.append((root, [sh, hd], inward, side))
        # ball-drop rig: tempered pane on a frame, steel ball
        for sx in (-1, 1):
            for sy in (-1, 1):
                cube(f"Rig leg {sx}{sy}", tuple(RIG + Vector((sx * 0.38, sy * 0.28, 0.29))), (0.03, 0.03, 0.58), stand)
        for sy in (-1, 1):
            cube(f"Rig rail {sy}", tuple(RIG + Vector((0, sy * 0.28, 0.585))), (0.8, 0.03, 0.02), stand)
        nx, ny = 24, 18
        xs, ys = np.linspace(-0.4, 0.4, nx), np.linspace(-0.3, 0.3, ny)
        gx, gy = np.meshgrid(xs, ys, indexing="ij")
        self.rig_xy = np.stack([gx.ravel(), gy.ravel()], -1)
        verts = [tuple(RIG + Vector((x, y, 0.6))) for x, y in self.rig_xy]
        faces = [(i * ny + j, (i + 1) * ny + j, (i + 1) * ny + j + 1, i * ny + j + 1) for i in range(nx - 1) for j in range(ny - 1)]
        self.rig_pane = mesh_object("Rig pane", verts, faces, glass_mat("Rig glass", (0.82, 0.92, 0.88), transmission=0.9, rough=0.03), thickness=0.006)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=gm.BALL_R, location=tuple(RIG + Vector((0, 0, 1.7))))
        self.ball = bpy.context.object
        self.ball.data.materials.append(material("Steel ball", (0.8, 0.8, 0.82), metal=1.0, rough=0.12))
        for p in self.ball.data.polygons:
            p.use_smooth = True

    def set_quench(self, t):
        y = -0.35 + gm.PANE_SPEED * t
        self.pane.location = tuple(LAB + Vector((0, y, 0.455)))
        self.glow_value.outputs[0].default_value = 5.0
        on = t > -0.3
        self.curtain_em.inputs[1].default_value = 4.0 if on else 0.0
        self.wave.inputs["Phase Offset"].default_value = -40.0 * t
        for c in self.curtains:
            c.hide_render = not on
        lead = y + 0.3
        passed = max(0.0, min(1.0, (lead - KNIFE_Y) / 0.6))
        return {"pane_y": round(y, 3), "quenched_fraction": round(passed, 3)}

    def set_section(self, t, arrows):
        ts, tc = gm.temperatures(t)
        s, c = gm.stress(t)
        k = abs(s) / abs(gm.SURFACE_MPA)
        gs = max(0.0, min(1.0, (ts - 430.0) / (gm.T_FURNACE - 430.0))) ** 2        # glow while hot, blue once set and squeezed
        for m in self.skin_mat:
            if gs > 0.02:
                set_emission(m, (1.0, 0.30, 0.04), 4.0 * gs)
            else:
                set_emission(m, (0.25, 0.55, 1.0), 1.5 * k + (0.4 if ts < gm.T_SET else 0.0))
        gc = max(0.0, min(1.0, (tc - 430.0) / (gm.T_FURNACE - 430.0))) ** 2        # the core glows longer, then turns red as it pulls
        if gc > 0.02:
            set_emission(self.core_mat, (1.0, 0.30, 0.04), 4.0 * gc)
        else:
            set_emission(self.core_mat, (1.0, 0.25, 0.12), 1.5 * k)
        self.core.scale = (1.0 - 0.035 * k, 1.0, 1.0)
        for root, objs, inward, side in self.arrows:
            for o in objs:
                o.hide_render = not (arrows and k > 0.03)
            root.scale = (1.0, 1.0, max(0.05, k))
        return {"surface_c": round(ts, 1), "core_c": round(tc, 1), "stress_fraction": round(k, 3)}

    def set_ball(self, t):
        h, flex = gm.ball_state(t)
        z = 0.6 - flex * np.cos(np.pi * self.rig_xy[:, 0] / 0.8) * np.cos(np.pi * self.rig_xy[:, 1] / 0.6)
        v = np.column_stack([RIG.x + self.rig_xy[:, 0], RIG.y + self.rig_xy[:, 1], RIG.z + z])
        self.rig_pane.data.vertices.foreach_set("co", v.ravel().astype(np.float32))
        self.rig_pane.data.update()
        self.ball.location = tuple(RIG + Vector((0, 0, 0.6 + 0.003 - (flex if h <= 0.001 else 0.0) + gm.BALL_R + h)))
        return {"ball_h": round(h, 4), "flex_mm": round(1000 * flex, 2)}


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
    sun_to = cinematic.sun_vector((0.55, -0.75), 15.0)          # low sun from the driver's side front: glints on the cubes
    cinematic.apply_sky(scene, sun_to, strength=0.24, dust=0.7)
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    sun.data.energy, sun.data.angle = 6.5, 0.02
    sun.data.color = (1.0, 0.74, 0.48)
    sun.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()
    build_world()
    bpy.context.view_layer.update()
    cut_window(bpy.data.objects["Cab and roof"])
    wheel_nodes = {w["node"] for w in wheels.values()}
    parts = [o for o in root.children_recursive if o.type == "MESH" and not any(p in wheel_nodes for p in rb._ancestors(o))]
    window = [bpy.data.objects[n] for n in WINDOW_OBJECTS]
    ghost = rb.Ghost([o for o in parts if o not in window])
    ghost.set_tint(PAINT)
    ghost.set_factor(0.0, 1e4, 4.0)
    interior = rb.build_interior(root)
    for o in [o for o in interior if o.name.startswith(("Interior door panel", "Interior B pillar", "Interior A pillar", "Interior roof"))]:
        o.hide_render = True                           # made for a wider cab: on this car they stick out through the doors and roof
        interior.remove(o)
    for o in interior:
        if o.type == "LIGHT":
            o.visible_camera = False
    trimmed = set()
    for o in parts:                                    # inside faces of the body read as dark trim, not red paint
        for m in o.data.materials:
            if m is not None and m.name not in trimmed and "glass" not in m.name.lower():
                trimmed.add(m.name)
                dark_backfaces(m)
    dark = glass_mat("Window glass", (0.45, 0.52, 0.54), transmission=0.85, rough=0.03)
    # (the dark-glass name is kept for the cube mesh's first slot: intact cells match the window)
    driver_glass = glass_mat("Driver window", (0.45, 0.52, 0.54), transmission=0.85, rough=0.03)     # its own copy: it can glow with locked-in stress
    for ob in root.children_recursive:                 # all windows: tinted glass that lets the sun into the cabin
        if ob.type == "MESH" and ("glass" in ob.name.lower() or "windscreen" in ob.name.lower()):
            for i in range(len(ob.data.materials)):
                ob.data.materials[i] = driver_glass if ob.name in WINDOW_OBJECTS else dark
    frost = glass_mat("Cracked glass", (0.93, 0.96, 0.98), transmission=0.25, rough=0.35, emission=0.0)
    clear = glass_mat("Glass cube", (0.90, 0.96, 0.95), transmission=0.7, rough=0.10)
    pane = Pane(dark, frost, clear)
    shards = Shards(clear)
    ws = Windshield(emissive("Windshield crack", (0.95, 0.97, 1.0), 0.6), material("Stone", (0.35, 0.33, 0.30), rough=0.9))
    hammer = Hammer()
    lab = Lab()
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam

    def render(sh, path):
        scene.render.resolution_x, scene.render.resolution_y = round(FRAME[0] * args.res_scale), round(FRAME[1] * args.res_scale)
        t, kind = sh["t"], sh["variant"]
        car_scene = kind in ("tempered", "annealed", "windshield")
        info = {"variant": kind, "t": round(t, 7)}
        broken_tempered = kind == "tempered" and t >= 0
        broken_annealed = kind == "annealed" and t >= 0
        for o in window:
            o.hide_render = broken_tempered or broken_annealed
        info.update(pane.set(t, broken_tempered))
        shards.set(t, broken_annealed)
        info["ws_crack_m"] = round(ws.set(t, kind == "windshield"), 4)
        hammer.set(t, kind == "tempered")
        info["hammer_angle"] = round(gm.hammer_angle(t), 4) if kind == "tempered" else None
        for o in interior:
            o.hide_render = (o.type == "LIGHT" and not sh.get("interior")) or not car_scene
        ghost.set_tint(INTERIOR_TINT if sh.get("interior") else PAINT)      # the low-poly body is solid below the windows: inside, it reads as dark trim
        glow = 0.35 * (0.55 + 0.45 * math.sin(2 * math.pi * 1.6 * sh["film_t"])) if sh.get("stress_glow") else 0.0
        set_emission(driver_glass, (1.0, 0.10, 0.04), glow)          # the energy locked in the pane, before the hit
        if kind == "quench":
            info.update(lab.set_quench(t))
        else:
            lab.set_quench(-0.9)
        if kind == "section":
            info.update(lab.set_section(t, bool(sh.get("arrows"))))
        else:
            lab.set_section(0.0, False)
        if kind == "ball":
            info.update(lab.set_ball(t))
        c = sh["cam"]
        o = {"car": Vector((0, 0, 0)), "lab": LAB, "slab": SLAB, "rig": RIG}[c["rel"]]
        loc, tgt = o + Vector(c["loc"]), o + Vector(c["target"])
        dd = cam.data
        dd.sensor_fit, dd.sensor_width, dd.lens, dd.clip_start = "HORIZONTAL", 36.0, c["lens"], 0.01
        dd.dof.use_dof = True
        dd.dof.focus_distance = (tgt - loc).length
        dd.dof.aperture_fstop = c.get("fstop", 8.0)
        base.set_camera(cam, loc, tgt)
        bpy.context.view_layer.update()
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        info["car_scene"] = car_scene
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
        print("GLASS_FRAME " + json.dumps(info), flush=True)
    (args.out / f"glass-frames-{frames[0]:05d}.json").write_text(json.dumps({"renderer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                                                            "frames": out}, indent=1))


if __name__ == "__main__":
    main()
