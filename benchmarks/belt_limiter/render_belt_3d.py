"""EP.05 seatbelt: 100 % 3D renderer (Blender, Cycles CPU) for the belt film (see examples/episodes/ep05-belt-load-limiter-plan.md). Same sedan, wall, cabin set, driver and see-through look as
EP.04 (pieces copied from render_crumple_3d.py so that the frozen EP.04 renderer stays untouched), plus the seatbelt strap, the reel cutaway (housing, spool with webbing, torsion bar) and
two belts in the same crash (belt_motion: plain / modern). Shots come from belt_shots.py. Not calibrated; see belt_motion."""
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
from benchmarks.belt_limiter import belt_motion as bm  # noqa: E402
from benchmarks.belt_limiter import belt_shots as shots  # noqa: E402
from benchmarks.crumple_zone import crumple_motion as cm  # noqa: E402
from benchmarks.crumple_zone import structure_geometry as sg  # noqa: E402
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402

material, cube = base.material, base.cube


def tube(name, p0, p1, radius, mat, parent, n_seg=48, n_ring=8):
    """Tube mesh between two car-frame points with many rings along its length (so the crush map can fold it). Returns (object, rest vertices (N, 3))."""
    verts = sg.tube_vertices(p0, p1, radius, n_seg, n_ring)
    faces = sg.tube_faces(n_seg, n_ring)
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([tuple(v) for v in verts], [], faces)
    mesh.update()
    mesh.polygons.foreach_set("use_smooth", [True] * len(faces))
    mesh.materials.append(mat)
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(ob)
    ob.parent = parent
    return ob, verts


class Dummy:
    """The driver as a crash-test-dummy style figure (plain shapes, no face, no text): belted in the driver's seat, parented to the car so that it moves with the cabin. The torso hinges
    forward at the hip and the head swings on the neck, driven by belt_motion (forward travel and chest load of the simulated crash). Chest and head turn from green through yellow to red
    with the peak chest load: the colour is the only 'damage' indicator."""
    HIP = (-0.36, 0.08, 0.40)
    WHEEL = (-0.36, 0.72, 0.88)
    GREEN, YELLOW, RED = (0.15, 0.75, 0.22), (0.95, 0.80, 0.08), (0.95, 0.07, 0.04)

    def __init__(self, root):
        hx, hy, hz = self.HIP
        # Same driver as the Rumble episode (benchmarks/road_safety/render_driver_insert.py): blue shirt, brown skin, dark hair, eyes, brows, nose, ears,
        # arms on the wheel; proportions of that figure scaled by SC and mirrored so that it faces the car's nose (+Y).
        SC = 0.5
        self.shirt_base = (0.035, 0.28, 0.47)
        self.skin = material("Driver shirt", self.shirt_base, rough=0.65)
        skin = material("Driver skin", (0.52, 0.28, 0.15), rough=0.65)
        dark = material("Driver hair", (0.018, 0.025, 0.035), rough=0.65)
        white = material("Driver eyes", (0.90, 0.94, 0.97), rough=0.5)
        limb = skin
        self.pivot = bpy.data.objects.new("Driver torso pivot", None)
        bpy.context.collection.objects.link(self.pivot)
        self.pivot.parent, self.pivot.location = root, (hx, hy, hz)
        self.neck = bpy.data.objects.new("Driver neck pivot", None)
        bpy.context.collection.objects.link(self.neck)
        self.neck.parent, self.neck.location = self.pivot, (0.0, 0.0, 0.55)

        def shape(kind, name, loc, scale, mat, parent):
            if kind == "sphere":
                bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=24, ring_count=16, location=(0, 0, 0))
            else:
                bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0))
            ob = bpy.context.object
            ob.name, ob.scale, ob.location = name, scale, loc
            ob.data.materials.append(mat)
            ob.parent = parent
            for p in ob.data.polygons:
                p.use_smooth = kind == "sphere"
            return ob

        shape("sphere", "Driver chest", (0.0, 0.0, 0.25), (0.185, 0.115, 0.245), self.skin, self.pivot)
        shape("sphere", "Driver neck", (0.0, 0.0, -0.07), (0.06, 0.06, 0.085), skin, self.neck)
        hc = 0.07
        shape("sphere", "Driver head", (0.0, 0.0, hc), (0.128, 0.115, 0.16), skin, self.neck)
        shape("sphere", "Driver hair", (0.0, -0.018, hc + 0.10), (0.13, 0.115, 0.075), dark, self.neck)
        shape("sphere", "Driver nose", (0.0, 0.12, hc - 0.007), (0.022, 0.037, 0.027), skin, self.neck)
        for sx in (-1, 1):
            shape("sphere", "Driver eye", (sx * 0.048, 0.107, hc + 0.033), (0.032, 0.018, 0.022), white, self.neck)
            shape("sphere", "Driver pupil", (sx * 0.048, 0.124, hc + 0.033), (0.0125, 0.007, 0.0135), dark, self.neck)
            shape("sphere", "Driver brow", (sx * 0.048, 0.108, hc + 0.07), (0.037, 0.011, 0.008), dark, self.neck)
            shape("sphere", "Driver ear", (sx * 0.127, -0.007, hc - 0.002), (0.022, 0.037, 0.042), skin, self.neck)
        shape("sphere", "Driver mouth", (0.0, 0.109, hc - 0.065), (0.033, 0.009, 0.006), dark, self.neck)
        shape("cube", "Driver pelvis", (hx, hy, hz - 0.02), (0.34, 0.27, 0.16), material("Driver trousers", (0.055, 0.085, 0.12), rough=0.7), root)
        trousers = bpy.data.materials["Driver trousers"]
        for sx in (-1, 1):
            tube(f"Driver thigh {sx}", (hx + 0.09 * sx, hy, hz), (hx + 0.09 * sx, hy + 0.46, hz + 0.05), 0.075, trousers, root, n_seg=16, n_ring=2)
            tube(f"Driver shin {sx}", (hx + 0.09 * sx, hy + 0.46, hz + 0.05), (hx + 0.09 * sx, hy + 0.52, hz - 0.36), 0.06, trousers, root, n_seg=16, n_ring=2)
            tube(f"Driver upper arm {sx}", (0.19 * sx, 0.0, 0.47), (0.20 * sx, 0.15, 0.32), 0.078, self.skin, self.pivot, n_seg=16, n_ring=8)
            tube(f"Driver forearm {sx}", (0.20 * sx, 0.15, 0.32), (0.16 * sx, 0.52, 0.44), 0.066, skin, self.pivot, n_seg=16, n_ring=8)
        wheel = material("Steering wheel", (0.05, 0.05, 0.055), rough=0.5)
        bpy.ops.mesh.primitive_torus_add(major_radius=0.18, minor_radius=0.018, location=self.WHEEL, rotation=(math.radians(-58), 0, 0))
        wob = bpy.context.object
        wob.name = "Steering wheel"
        wob.data.materials.append(wheel)
        wob.parent = root
        self.head = self.neck

    def colour(self, injury):
        a, b, t = (self.GREEN, self.YELLOW, injury * 2.0) if injury < 0.5 else (self.YELLOW, self.RED, injury * 2.0 - 1.0)
        c = tuple(a[i] + (b[i] - a[i]) * t for i in range(3))
        c = tuple(self.shirt_base[i] + (c[i] - self.shirt_base[i]) * min(1.0, injury * 3.0) for i in range(3))   # the shirt is blue until the load is felt
        bsdf = self.skin.node_tree.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = (*c, 1.0)
        bsdf.inputs["Emission Color"].default_value = (*c, 1.0)
        return c

    def pose(self, variant, sim_time):
        st = bm.at(variant, sim_time)
        hx, hy, hz = self.HIP
        self.pivot.location = (hx, hy + 0.25 * st["travel_m"], hz)
        self.pivot.rotation_euler = (-float(np.clip(st["travel_m"] / 0.55, -0.08, 1.1)), 0.0, 0.0)
        self.neck.rotation_euler = (-float(np.clip(st["chest_g"] / 120.0, 0.0, 0.7)), 0.0, 0.0)
        st["colour"] = self.colour(st["injury"])
        return st


def build_interior(root):
    """The cabin set for the interior shots (car frame, parented to the car): driver and passenger seats, dashboard, steering column, door panels, pillars, roof liner, floor. In the interior shots the car body
    is not rendered at all (like the earlier driver insert of the Rumble episode); this set and the driver are what the camera sees. Returns the list of objects."""
    seat = material("Interior seat", (0.16, 0.26, 0.40), rough=0.7)
    trim = material("Interior trim", (0.34, 0.42, 0.52), rough=0.6)
    dark = material("Interior dark", (0.09, 0.10, 0.13), rough=0.8)
    liner = trim                                                         # the roof lining has the same colour as the rest of the cabin trim (a darker ceiling looked wrong)
    out = []

    def box(name, loc, size, mat):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
        ob = bpy.context.object
        ob.name, ob.scale = name, size
        ob.data.materials.append(mat)
        ob.parent = root
        out.append(ob)
        return ob

    for sx, who in ((-0.36, "driver"), (0.36, "passenger")):
        box(f"Interior {who} seat cushion", (sx, 0.02, 0.30), (0.52, 0.58, 0.14), seat)
        box(f"Interior {who} seat back", (sx, -0.34, 0.72), (0.52, 0.14, 0.78), seat)
        box(f"Interior {who} headrest", (sx, -0.36, 1.20), (0.28, 0.10, 0.22), seat)
    box("Interior dashboard", (0.0, 1.00, 0.66), (1.56, 0.42, 0.30), trim)
    box("Interior dashboard top", (0.0, 0.86, 0.84), (1.56, 0.30, 0.08), dark)
    box("Interior steering column", (-0.36, 0.88, 0.78), (0.07, 0.40, 0.07), dark)
    box("Interior centre console", (0.0, 0.25, 0.40), (0.22, 1.1, 0.26), trim)
    box("Interior floor", (0.0, 0.2, 0.17), (1.56, 2.2, 0.05), dark)
    for sx in (-1, 1):
        box(f"Interior door panel {sx}", (0.78 * sx, 0.20, 0.62), (0.07, 1.5, 0.62), trim)
        box(f"Interior B pillar {sx}", (0.78 * sx, -0.42, 1.0), (0.08, 0.12, 0.62), trim)
        ob, _ = tube(f"Interior A pillar {sx}", (0.76 * sx, 0.98, 0.84), (0.76 * sx, 0.36, 1.24), 0.045, trim, root, n_seg=10, n_ring=2)
        out.append(ob)
    box("Interior roof header", (0.0, 0.36, 1.25), (1.56, 0.08, 0.06), liner)
    box("Interior roof liner", (0.0, 0.30, 1.27), (1.56, 1.8, 0.04), liner)      # reaches over the windscreen top so no open sky shows above the wall
    bpy.ops.object.light_add(type="AREA", location=(0.0, 0.25, 1.18))      # interior fill light: the cabin shots are lit from inside (the car body that would let the sun in is not rendered)
    lamp = bpy.context.object
    lamp.name = "Interior fill light"
    lamp.data.energy, lamp.data.shape, lamp.data.size, lamp.data.size_y = 45.0, "RECTANGLE", 1.3, 1.1
    lamp.rotation_euler = (0.0, 0.0, 0.0)      # an area light shines along its local -Z: unrotated it lights the seats and the driver from above (rotated by pi it lit only the roof liner, which blew out white)
    lamp.parent = root
    out.append(lamp)
    for ob in out:
        ob.hide_render = True
    return out


class Ghost:
    """Body materials copied with a world-space scan line: everything the line has passed turns almost transparent with a neutral light rim; the line itself flares."""
    SOFT = 0.35

    def __init__(self, parts):
        self.wipes, seen, self.paints = [], {}, []
        for o in parts:
            for i, m in enumerate(o.data.materials):
                if m is None:
                    continue
                if m.name not in seen:
                    seen[m.name] = self._material(m)
                o.data.materials[i] = seen[m.name]

    def _material(self, m):
        c = m.copy()
        c.name = m.name + " ghost"
        nt = c.node_tree
        bsdf = nt.nodes.get("Principled BSDF")
        alpha0 = bsdf.inputs["Alpha"].default_value
        base = bsdf.inputs["Base Color"]
        col = tuple(base.default_value)
        lum = 0.2126 * col[0] + 0.7152 * col[1] + 0.0722 * col[2]
        if not base.is_linked and alpha0 >= 0.99 and 0.12 < lum < 0.95:
            self.paints.append((bsdf, col))      # body paint: the rigid-front car gets a different colour so the two crashes are told apart without any text

        def node(kind, **kw):
            n = nt.nodes.new(kind)
            for k, v in kw.items():
                setattr(n, k, v)
            return n

        def op(o, a=None, b=None, clamp=False):
            n = node("ShaderNodeMath", operation=o, use_clamp=clamp)
            for i, v in enumerate((a, b)):
                if v is None:
                    continue
                if isinstance(v, (int, float)):
                    n.inputs[i].default_value = v
                else:
                    nt.links.new(v, n.inputs[i])
            return n.outputs[0]

        geo = node("ShaderNodeNewGeometry")
        sep = node("ShaderNodeSeparateXYZ")
        nt.links.new(geo.outputs["Position"], sep.inputs[0])
        wipe = node("ShaderNodeValue")
        self.wipes.append(wipe)
        mask = op("MULTIPLY", op("SUBTRACT", sep.outputs[1], wipe.outputs[0]), 1.0 / self.SOFT, clamp=True)
        nt.links.new(op("ADD", op("MULTIPLY", mask, -0.8 * alpha0), alpha0), bsdf.inputs["Alpha"])
        lw = node("ShaderNodeLayerWeight")
        lw.inputs["Blend"].default_value = 0.35
        edge = op("MULTIPLY", op("MULTIPLY", lw.outputs["Facing"], mask), 1.2)
        flare = op("MULTIPLY", op("MULTIPLY", mask, op("SUBTRACT", 1.0, mask)), 5.0)
        nt.links.new(op("ADD", edge, flare), bsdf.inputs["Emission Strength"])
        bsdf.inputs["Emission Color"].default_value = (0.85, 0.85, 0.85, 1.0)      # neutral: the see-through no longer carries a blue tint (owner request)
        return c

    def set_tint(self, mult):
        for bsdf, col in self.paints:
            bsdf.inputs["Base Color"].default_value = (min(1.0, col[0] * mult[0]), min(1.0, col[1] * mult[1]), min(1.0, col[2] * mult[2]), col[3])

    def set_factor(self, xf, y_nose, car_length, y_floor=-1e9):
        wipe = max(y_floor, y_nose + 0.6 - (0.6 + car_length + 0.4) * xf)        # the line runs from just ahead of the nose back to the passenger cell (y_floor): the cabin is never made see-through
        for w in self.wipes:
            w.outputs[0].default_value = wipe


class Deformable:
    """A mesh whose vertices are driven by the crush map: rest positions in the car frame, the object's own matrix to go back to local coordinates."""

    def __init__(self, ob, nose, local_is_car_frame=False, mapper=None):
        self.mapper = mapper or cm.crush_map
        mesh = ob.data
        if mesh.users > 1:
            ob.data = mesh = mesh.copy()
        self.ob, self.mesh = ob, mesh
        n = len(mesh.vertices)
        co = np.zeros(n * 3)
        mesh.vertices.foreach_get("co", co)
        self.local0 = co.reshape(n, 3)
        if local_is_car_frame:
            self.m3, self.t = np.eye(3), np.zeros(3)
        else:
            m = np.array(ob.matrix_world)
            self.m3, self.t = m[:3, :3], m[:3, 3]
        self.p0 = self.local0 @ self.m3.T + self.t
        self.minv = np.linalg.inv(self.m3)
        self.idx = np.where(self.p0[:, 1] > nose - cm.CRUSH_LENGTH - 1e-6)[0]

    def apply(self, s, nose):
        """Poses the vertices for crush stroke s; returns the deformed car-frame points of the affected vertices."""
        self.sub = self.p0[:0]
        if len(self.idx) == 0:
            return self.sub
        sub = self.mapper(self.p0[self.idx], s, nose)
        self.sub = sub
        out = self.local0.copy()
        out[self.idx] = (sub - self.t) @ self.minv.T
        self.mesh.vertices.foreach_set("co", out.ravel())
        self.mesh.update()
        return sub


D_RING = (-0.74, -0.28, 1.02)         # upper belt anchor on the driver's B pillar (car frame)
REEL_AT = (-0.72, -0.30, 0.36)        # the reel at the base of the B pillar
HIP_IN, LAP_MID, HIP_OUT, ANCHOR_OUT = (-0.20, 0.17, 0.47), (-0.36, 0.225, 0.47), (-0.55, 0.17, 0.47), (-0.70, 0.05, 0.40)
PAY_MAX = 0.131                       # largest webbing pay-out of the modern belt (m), for the reel animation


class Belt:
    """The strap: reel exit -> upper anchor -> shoulder -> chest -> inner hip buckle -> across the lap -> outer hip anchor. The shoulder and chest points ride on the driver's torso, so the
    strap follows the body; the rest is fixed to the car."""

    def __init__(self, root):
        self.root = root
        self.mat = material("Belt webbing", (0.10, 0.10, 0.115), rough=0.8)
        curve = bpy.data.curves.new("Belt strap", "CURVE")
        curve.dimensions = "3D"
        curve.bevel_depth, curve.bevel_resolution, curve.use_fill_caps = 0.017, 3, True
        sp = curve.splines.new("POLY")
        sp.points.add(7)
        self.sp = sp
        self.ob = bpy.data.objects.new("Belt strap", curve)
        bpy.context.collection.objects.link(self.ob)
        self.ob.data.materials.append(self.mat)

    def update(self, pivot, payout, chest_g=0.0):
        mw = self.root.matrix_world
        bsdf = self.mat.node_tree.nodes.get("Principled BSDF")
        bsdf.inputs["Emission Color"].default_value = (1.0, 0.55, 0.08, 1.0)
        bsdf.inputs["Emission Strength"].default_value = 3.0 * float(np.clip(chest_g / bm.LIMIT_G, 0.0, 1.0)) ** 0.5      # the strap glows with its tension (already visible at the snap)
        car = lambda p: mw @ Vector(p)
        tor = lambda p: pivot.matrix_world @ Vector(p)
        reel_exit = (REEL_AT[0], REEL_AT[1], REEL_AT[2] + 0.06)
        pts = [car(reel_exit), car(D_RING), tor((-0.13, 0.05, 0.50)), tor((0.02, 0.135, 0.28)), car(HIP_IN), car(LAP_MID), car(HIP_OUT), car(ANCHOR_OUT)]
        for p, w in zip(self.sp.points, pts):
            p.co = (w.x, w.y, w.z, 1.0)


class Reel:
    """Reel and pretensioner for the 'inside the part' shots (car frame, parented to the car, origin at REEL_AT, spool axis along the car's length Y).
    Along the axis: housing wall | ratchet wheel (locked by the pawl) | exposed torsion bar with a twisting stripe helix | spool flange | webbing roll | flange | pinion gear.
    The load limiter: the ratchet wheel holds one end of the bar, the spool turns the other end, so webbing pays out while the bar twists (twist = payout / spool radius).
    The pretensioner: a gas flash drives a piston and a rack down, the rack turns the pinion and the spool winds the slack in."""
    SPOOL_R = 0.04
    PINION_R = 0.04
    RACK_TRAVEL = 0.023           # m of rack travel = PINION_R x the winding angle (about 33 degrees) at full pretension

    def __init__(self, root):
        self.root = root
        housing = material("Reel housing", (0.72, 0.82, 0.92), rough=0.08)
        housing.node_tree.nodes.get("Principled BSDF").inputs["Alpha"].default_value = 0.12
        steel = material("Reel steel", (0.55, 0.56, 0.60), metal=0.8, rough=0.35)
        dark = material("Reel dark steel", (0.20, 0.21, 0.24), metal=0.7, rough=0.4)
        web = material("Reel webbing", (0.10, 0.10, 0.115), rough=0.8)
        orange = material("Torsion bar stripe", (1.0, 0.45, 0.05), rough=0.4, emission=2.0)
        flash_mat = material("Pretensioner flash", (1.0, 0.8, 0.3), rough=0.5, emission=0.0)
        self.flash_mat = flash_mat
        glass = material("Pretensioner tube", (0.75, 0.8, 0.9), rough=0.1)
        glass.node_tree.nodes.get("Principled BSDF").inputs["Alpha"].default_value = 0.18
        self.parts, self.fixed_housing = [], []
        ax, ay, az = REEL_AT

        def add(ob, parent=None, housing_part=False):
            ob.parent = parent or root
            self.parts.append(ob)
            if housing_part:
                self.fixed_housing.append(ob)
            return ob

        def cyl(name, radius, depth, loc, mat, parent):
            bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth, location=loc, rotation=(math.pi / 2, 0, 0))
            ob = add(bpy.context.object, parent)
            ob.name = name
            ob.data.materials.append(mat)
            return ob

        def box(name, loc, scale, mat, parent):
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
            ob = add(bpy.context.object, parent)
            ob.name, ob.scale = name, scale
            ob.data.materials.append(mat)
            return ob

        h = box("Reel housing", (ax, ay, az), (0.17, 0.215, 0.19), housing, root)
        self.fixed_housing.append(h)
        # fixed frame (root parented): ratchet wheel with teeth, pawl
        self.axis = bpy.data.objects.new("Reel axis", None)
        bpy.context.collection.objects.link(self.axis)
        add(self.axis).location = (ax, ay, az)
        ratchet = cyl("Ratchet wheel", 0.045, 0.014, (0, -0.082, 0), dark, self.axis)
        for k in range(14):
            ang = 2 * math.pi * k / 14
            box(f"Ratchet tooth {k}", (0.048 * math.cos(ang), -0.082, 0.048 * math.sin(ang)), (0.012, 0.014, 0.008), dark, self.axis).rotation_euler = (0.0, -ang, 0.0)
        box("Locking pawl", (0.0, -0.082, 0.056), (0.012, 0.018, 0.020), steel, self.axis)
        # turning part: spool with flanges, webbing roll, pinion
        self.spool = bpy.data.objects.new("Reel spool pivot", None)
        bpy.context.collection.objects.link(self.spool)
        add(self.spool).location = (ax, ay, az)
        cyl("Spool core", 0.040, 0.05, (0, 0.008, 0), steel, self.spool)
        cyl("Spool flange A", 0.058, 0.006, (0, -0.017, 0), steel, self.spool)
        cyl("Spool flange B", 0.058, 0.006, (0, 0.033, 0), steel, self.spool)
        self.roll = cyl("Reel webbing roll", 0.052, 0.040, (0, 0.008, 0), web, self.spool)
        cyl("Torsion bar", 0.016, 0.078, (0, -0.052, 0), dark, self.spool)      # from the spool back to the locked ratchet wheel
        cyl("Pinion gear", 0.040, 0.012, (0, 0.045, 0), steel, self.spool)
        for k in range(12):
            ang = 2 * math.pi * k / 12
            box(f"Pinion tooth {k}", (0.043 * math.cos(ang), 0.045, 0.043 * math.sin(ang)), (0.010, 0.012, 0.008), steel, self.spool).rotation_euler = (0.0, -ang, 0.0)
        self.stripes = [box(f"Torsion bar stripe {i}", (0, 0, 0), (0.014, 0.0075, 0.007), orange, self.spool) for i in range(10)]
        # pretensioner: tube, piston, rack along the pinion's inboard side, gas flash
        self.tube_x = ax + 0.058
        box("Pretensioner tube", (self.tube_x, ay + 0.045, az + 0.085), (0.028, 0.030, 0.17), glass, root)
        self.piston = box("Pretensioner piston", (self.tube_x, ay + 0.045, az + 0.12), (0.020, 0.022, 0.05), dark, root)
        self.rack = box("Pretensioner rack", (ax + 0.046, ay + 0.045, az + 0.06), (0.010, 0.012, 0.16), steel, root)
        self.rack_teeth = [box(f"Rack tooth {k}", (ax + 0.0405, ay + 0.045, az + 0.12 - 0.014 * k), (0.008, 0.012, 0.008), steel, root) for k in range(10)]
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.014, location=(self.tube_x, ay + 0.045, az + 0.17))
        self.flash = add(bpy.context.object, root)
        self.flash.name = "Pretensioner gas flash"
        self.flash.data.materials.append(flash_mat)
        self.rest_z = {"piston": az + 0.12, "rack": az + 0.06, "teeth": [az + 0.12 - 0.014 * k for k in range(10)]}

    def update(self, payout, pretension):
        """payout: webbing paid out (m). pretension: 0..1 progress of the pretensioner."""
        u = min(1.0, payout / PAY_MAX)
        twist = payout / self.SPOOL_R                        # the bar twists as much as the spool turns against the locked ratchet wheel
        wind = pretension * self.RACK_TRAVEL / self.PINION_R
        self.spool.rotation_euler = (0.0, -wind + twist, 0.0)
        r = 0.052 - 0.022 * u
        self.roll.scale = (r / 0.052, r / 0.052, 1.0)
        drop = pretension * self.RACK_TRAVEL
        self.piston.location.z = self.rest_z["piston"] - drop
        self.rack.location.z = self.rest_z["rack"] - drop
        for tooth, z0 in zip(self.rack_teeth, self.rest_z["teeth"]):
            tooth.location.z = z0 - drop
        n = len(self.stripes)
        for i, st in enumerate(self.stripes):                # stripes along the exposed bar: no twist at the ratchet end, the full twist at the spool end
            frac = i / (n - 1)
            y = -0.088 + 0.060 * frac
            a = (twist - wind) * (1.0 - frac)                # the stripes are children of the spool: relative to it the ratchet end is turned back by the full spool angle
            st.location = (0.0185 * math.cos(a), y, 0.0185 * math.sin(a))
            st.rotation_euler = (0.0, -a, 0.0)
        flash = max(0.0, 1.0 - pretension) if 0.0 < pretension < 1.0 else 0.0
        self.flash_mat.node_tree.nodes.get("Principled BSDF").inputs["Emission Color"].default_value = (1.0, 0.75, 0.25, 1.0)
        self.flash_mat.node_tree.nodes.get("Principled BSDF").inputs["Emission Strength"].default_value = 5.0 * flash
        self.flash.hide_render = flash <= 0.0

    def set_visible(self, visible, hide_housing=False):
        for ob in self.parts:
            ob.hide_render = not visible
        for ob in self.fixed_housing:
            ob.hide_render = (not visible) or hide_housing


def arguments():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--shots", default="all")
    p.add_argument("--res-scale", type=float, default=0.6667)
    p.add_argument("--samples", type=int, default=12)
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return p.parse_args(argv)


def main():
    args = arguments()
    args.out.mkdir(parents=True, exist_ok=True)
    root, body, wheels, geom = base.load_source_car(args.source)
    scene = bpy.context.scene
    scene.name = "belt"
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.exposure = -1.3
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    sun_to = cinematic.sun_vector((-0.5, -0.8), 36.0)
    cinematic.apply_sky(scene, sun_to, strength=0.25, dust=0.5)
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    sun.data.energy, sun.data.angle = 3.4, 0.03
    sun.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()
    road = material("Asphalt", (0.07, 0.07, 0.075), rough=0.85)
    base.asphalt_grain(road)
    cube("Road", (0, -10, -0.05), (14.0, 60, 0.1), road)
    concrete = material("Barrier", (0.12, 0.12, 0.115), rough=0.9)
    cube("Barrier", (0, 0.5, 1.0), (9.0, 1.0, 2.0), concrete)
    cube("Barrier stripe", (0, -0.002, 0.5), (9.0, 0.004, 0.18), material("Stripe", (0.9, 0.62, 0.05), rough=0.5))
    nose = geom["nose"]
    car_len = geom["nose"] + geom["tail"]
    wheel_nodes = {w["node"] for w in wheels.values()}
    parts = [o for o in root.children_recursive if o.type == "MESH" and not any(p in wheel_nodes for p in _ancestors(o))]
    bpy.context.view_layer.update()
    deformables = [Deformable(o, nose) for o in parts]
    cabin_y = nose - cm.CRUSH_LENGTH
    rail_mat = material("Crush rail", (1.0, 0.45, 0.05), rough=0.4, emission=2.0)
    structure = []
    for name, it in sg.structure(nose).items():
        if it["deforms"]:
            ob, v0 = tube(name, it["p0"], it["p1"], it["radius"], rail_mat, root, n_seg=it["n_seg"])
            structure.append(ob)
    structure_def = [Deformable(ob, nose, local_is_car_frame=True, mapper=cm.rail_fold) for ob in structure]
    ghost = Ghost([o for o in parts])
    dummy = Dummy(root)
    interior = build_interior(root)
    belt = Belt(root)
    reel = Reel(root)
    wheel_objs = [o for w in wheels.values() for o in [w["node"], *w["node"].children_recursive]]
    all_body = list(parts) + wheel_objs
    seat_parts = [o for o in interior if o.name.startswith(("Interior driver seat back", "Interior driver headrest", "Interior driver seat cushion"))]
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    rec = bm._crash()
    wheel_r = geom["tyre_radius"]
    names = list(shots.SHOTS) if args.shots == "all" else args.shots.split(",")
    out = []
    for name in names:
        t0 = time.time()
        sh = shots.SHOTS[name]
        t = shots.sim_time(sh)
        scene.render.resolution_x, scene.render.resolution_y = round(shots.FRAME[0] * args.res_scale), round(shots.FRAME[1] * args.res_scale)
        ps = cm.sample(rec, t)
        d, s = ps["d"], ps["s"]
        root.location = (0.0, -cm.LEAD_SIM + d - nose, 0.0)
        for dm in deformables:
            dm.apply(s, nose)
        for dm in structure_def:
            dm.apply(s, nose)
        for key, wh in wheels.items():
            y_new = cm.wheel_y(float(wh["base"].y), s, nose, wheel_r) if key.startswith("front") else float(wh["base"].y)
            wh["node"].location = (wh["base"].x, y_new, wh["base"].z)
            wh["node"].rotation_euler = (-d / wheel_r, 0, 0)
        xf, cf = sh["xray"], sh["cabin_xray"]
        ghost.set_factor(xf, root.location.y + nose, car_len, root.location.y + cabin_y + 0.04 - cf * (car_len + 0.8))
        ghost.set_tint((1.0, 1.0, 1.0))
        st = dummy.pose(sh["variant"], t)
        bpy.context.view_layer.update()      # the strap reads the torso's world matrix: it must be current
        belt.update(dummy.pivot, st["payout_m"], st["chest_g"])
        fire = bm.contact_time_s() + bm.PRETENSION_DELAY_S
        pretension = float(np.clip((t - fire) / bm.PRETENSION_TIME_S, 0.0, 1.0)) if sh["variant"] == "modern" else 0.0
        reel.update(st["payout_m"], pretension)
        c = sh["cam"]
        off = Vector(root.location) if c["rel"] == "car" else Vector((0.0, root.location.y + nose, 0.0))
        loc = Vector(c["loc"]) + off
        tgt = Vector(c["target"]) + off
        dd = cam.data
        dd.sensor_fit, dd.sensor_width, dd.lens, dd.shift_y, dd.clip_start = "HORIZONTAL", shots.SENSOR_W, c["lens"], shots.shift_y(c), 0.03
        base.set_camera(cam, loc, tgt)
        inside = bool(sh["interior"])
        for ob in all_body:
            ob.hide_render = inside
        for ob in structure:
            ob.hide_render = inside or xf <= 0.02
        for ob in interior:
            ob.hide_render = not inside
        for ob in seat_parts:
            ob.hide_render = (not inside) or bool(sh.get("hide_seat"))
        reel.set_visible(inside, bool(sh.get("hide_housing")))
        belt.ob.hide_render = False
        bpy.context.view_layer.update()
        path = args.out / f"{name}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        info = {"shot": name, "variant": sh["variant"], "sim_time": round(t, 5), "travel_m": round(st["travel_m"], 4), "chest_g": round(st["chest_g"], 2), "injury": round(st["injury"], 3),
                "payout_m": round(st["payout_m"], 4), "pull_back_m": round(st["pull_back_m"], 4), "stroke_m": round(s, 4), "render_seconds": round(time.time() - t0, 1),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        out.append(info)
        print("BELT_SHOT " + json.dumps(info), flush=True)
    (args.out / "belt-shots.json").write_text(json.dumps({"renderer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "shots": out, "belt_gate": bm.belt_limiter_physics()}, indent=1))


def _ancestors(ob):
    p = ob.parent
    while p is not None:
        yield p
        p = p.parent


main()
