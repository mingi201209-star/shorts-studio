"""A better-looking driver (Blender side, procedural; no scene text). Same rig as EP.05's Dummy (render_belt_3d.Dummy): a torso pivot at the
hip and a neck pivot, parented to the car, so Dummy.pose / Dummy.colour drive it unchanged. Only the geometry is new:
- capsule limbs with tapering radius (rounded ends, smooth shading, subdivision): shoulders, upper arms, elbows, forearms, hands with four
  fingers and a thumb wrapped on the rim; thighs, knees, shins, shoes;
- a shaped torso with a shirt collar; an egg-shaped head with jaw, nose, ears, eyes (white, iris, pupil, upper lid), brows, lips and hair;
- skin with a little subsurface scattering, cloth materials for shirt and trousers.
The shirt material is self.skin (the name Dummy.colour expects): it turns green -> yellow -> red with the load, exactly like before."""
from __future__ import annotations

import math

import bpy
from mathutils import Matrix, Vector

from benchmarks.belt_limiter import render_belt_3d as rb
from benchmarks.road_safety import render_jersey_barrier as base

material = base.material


def _subsurf(ob, levels=1):
    m = ob.modifiers.new("Smooth", "SUBSURF")
    m.levels = m.render_levels = levels
    for p in ob.data.polygons:
        p.use_smooth = True


def capsule(name, p0, p1, r0, r1, mat, parent, rings=10, seg=20, squash=1.0):
    """Tapered capsule from p0 (radius r0) to p1 (radius r1) in the parent's frame, with hemispherical ends. squash < 1 flattens it front-to-back."""
    p0, p1 = Vector(p0), Vector(p1)
    axis = p1 - p0
    L = axis.length
    rot = axis.normalized().to_track_quat("Z", "Y").to_matrix()
    verts, profile = [], []
    for i in range(rings + 1):                                   # bottom cap
        a = -math.pi / 2 + (math.pi / 2) * i / rings
        profile.append((r0 * math.sin(a), r0 * math.cos(a)))
    for i in range(1, rings):                                    # body
        u = i / rings
        profile.append((L * u, r0 + (r1 - r0) * u))
    for i in range(rings + 1):                                   # top cap
        a = (math.pi / 2) * i / rings
        profile.append((L + r1 * math.sin(a), r1 * math.cos(a)))
    for z, r in profile:
        for j in range(seg):
            b = 2 * math.pi * j / seg
            verts.append(p0 + rot @ Vector((r * math.cos(b), r * math.sin(b) * squash, z)))
    faces = []
    n = len(profile)
    for i in range(n - 1):
        for j in range(seg):
            k = (j + 1) % seg
            faces.append((i * seg + j, i * seg + k, (i + 1) * seg + k, (i + 1) * seg + j))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([tuple(v) for v in verts], [], faces)
    mesh.update()
    mesh.materials.append(mat)
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(ob)
    ob.parent = parent
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def blob(name, loc, scale, mat, parent, rot=(0, 0, 0), seg=32, rings=16):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=seg, ring_count=rings, location=(0, 0, 0))
    ob = bpy.context.object
    ob.name, ob.scale, ob.location, ob.rotation_euler = name, scale, loc, rot
    ob.data.materials.append(mat)
    for p in ob.data.polygons:
        p.use_smooth = True
    ob.parent = parent
    return ob


def skin_material():
    m = material("Driver skin", (0.42, 0.25, 0.16), rough=0.5)
    s = m.node_tree.nodes.get("Principled BSDF")
    s.inputs["Subsurface Weight"].default_value = 0.15
    s.inputs["Subsurface Radius"].default_value = (1.0, 0.35, 0.2)
    s.inputs["Subsurface Scale"].default_value = 0.02
    return m


class Human(rb.Dummy):
    """Drop-in replacement for rb.Dummy with a more detailed body. Pose and colour come from rb.Dummy."""

    def __init__(self, root):
        hx, hy, hz = self.HIP
        self.shirt_base = (0.035, 0.28, 0.47)
        self.skin = material("Driver shirt", self.shirt_base, rough=0.7)        # Dummy.colour tints this
        skin = skin_material()
        hair = material("Driver hair", (0.02, 0.015, 0.012), rough=0.6)
        white = material("Driver eyes", (0.92, 0.93, 0.94), rough=0.25)
        iris = material("Driver iris", (0.20, 0.12, 0.06), rough=0.3)
        dark = material("Driver pupil", (0.01, 0.01, 0.01), rough=0.2)
        lip = material("Driver lips", (0.50, 0.24, 0.20), rough=0.5)
        trousers = material("Driver trousers", (0.06, 0.08, 0.13), rough=0.8)
        shoe = material("Driver shoes", (0.05, 0.035, 0.03), rough=0.45)
        self.pivot = bpy.data.objects.new("Driver torso pivot", None)
        bpy.context.collection.objects.link(self.pivot)
        self.pivot.parent, self.pivot.location = root, (hx, hy, hz)
        self.neck = bpy.data.objects.new("Driver neck pivot", None)
        bpy.context.collection.objects.link(self.neck)
        self.neck.parent, self.neck.location = self.pivot, (0.0, 0.0, 0.55)
        P, N = self.pivot, self.neck
        # torso: a tapered capsule (waist -> chest), shoulders, collar
        capsule("Driver torso", (0, 0, 0.04), (0, 0.01, 0.40), 0.150, 0.165, self.skin, P, squash=0.70)
        for sx in (-1, 1):
            blob(f"Driver shoulder {sx}", (sx * 0.150, 0.0, 0.415), (0.058, 0.056, 0.050), self.skin, P)
        bpy.ops.mesh.primitive_torus_add(major_radius=0.062, minor_radius=0.016, location=(0, 0, 0))
        col = bpy.context.object
        col.name, col.location, col.rotation_euler = "Driver collar", (0, 0.005, 0.50), (math.radians(8), 0, 0)
        col.data.materials.append(self.skin)
        col.parent = P
        # neck and head (head frame: N; the face looks along +y)
        capsule("Driver neck", (0, 0, -0.08), (0, 0.01, 0.02), 0.048, 0.044, skin, N)
        hc = Vector((0, 0.0, 0.085))
        blob("Driver head", hc, (0.095, 0.110, 0.125), skin, N)
        blob("Driver jaw", hc + Vector((0, 0.030, -0.065)), (0.075, 0.070, 0.055), skin, N)
        blob("Driver chin", hc + Vector((0, 0.075, -0.095)), (0.030, 0.022, 0.022), skin, N)
        blob("Driver hair", hc + Vector((0, -0.012, 0.035)), (0.100, 0.112, 0.105), hair, N)
        blob("Driver hair back", hc + Vector((0, -0.045, -0.015)), (0.092, 0.075, 0.095), hair, N)
        nose = capsule("Driver nose", hc + Vector((0, 0.100, 0.005)), hc + Vector((0, 0.122, -0.030)), 0.010, 0.016, skin, N)
        blob("Driver nose tip", hc + Vector((0, 0.124, -0.032)), (0.017, 0.014, 0.013), skin, N)
        for sx in (-1, 1):
            e = hc + Vector((sx * 0.036, 0.098, 0.012))
            blob(f"Driver eye {sx}", e, (0.019, 0.010, 0.013), white, N)
            blob(f"Driver iris {sx}", e + Vector((0, 0.0085, 0)), (0.0095, 0.003, 0.0095), iris, N)
            blob(f"Driver pupil {sx}", e + Vector((0, 0.0105, 0)), (0.004, 0.0015, 0.004), dark, N)
            blob(f"Driver lid {sx}", e + Vector((0, 0.002, 0.008)), (0.019, 0.011, 0.006), skin, N)
            blob(f"Driver brow {sx}", e + Vector((sx * 0.004, 0.006, 0.026)), (0.022, 0.006, 0.0045), hair, N, rot=(0, sx * math.radians(-8), 0))
            blob(f"Driver ear {sx}", hc + Vector((sx * 0.094, 0.000, 0.000)), (0.012, 0.024, 0.034), skin, N)
            blob(f"Driver cheek {sx}", hc + Vector((sx * 0.045, 0.070, -0.030)), (0.028, 0.020, 0.022), skin, N)
        blob("Driver upper lip", hc + Vector((0, 0.098, -0.060)), (0.024, 0.008, 0.006), lip, N)
        blob("Driver lower lip", hc + Vector((0, 0.094, -0.071)), (0.021, 0.008, 0.006), lip, N)
        # arms: shoulder -> elbow -> wrist -> hand gripping the rim (torso frame, they move with the torso)
        wheel_c = Vector(self.WHEEL) - Vector(self.HIP)
        tilt = Matrix.Rotation(math.radians(-58), 3, "X")
        for sx in (-1, 1):
            sh = Vector((sx * 0.175, 0.0, 0.42))
            grip = wheel_c + tilt @ Vector((sx * 0.170, 0.035, -0.025))
            el = sh + (grip - sh) * 0.48 + Vector((sx * 0.07, -0.02, -0.12))
            wr = grip + (el - grip).normalized() * 0.07
            capsule(f"Driver upper arm {sx}", sh, el, 0.044, 0.037, self.skin, P)
            capsule(f"Driver forearm {sx}", el, wr, 0.034, 0.026, skin, P)
            blob(f"Driver elbow {sx}", el, (0.037, 0.037, 0.037), self.skin, P)
            d = (grip - wr).normalized()
            palm = wr + d * 0.045
            blob(f"Driver palm {sx}", palm, (0.040, 0.030, 0.050), skin, P, rot=d.to_track_quat("Z", "Y").to_euler())
            side = d.cross(Vector((0, 0, 1))).normalized()
            for k in range(4):
                base_pt = palm + d * 0.040 + side * (-0.022 + 0.0147 * k)
                capsule(f"Driver finger {sx}{k}", base_pt, base_pt + d * 0.030 + Vector((0, 0.0, -0.025)), 0.0085, 0.0075, skin, P, rings=4, seg=10)
            capsule(f"Driver thumb {sx}", palm + side * (0.034 * sx), palm + side * (0.034 * sx) + d * 0.035 + Vector((0, 0, 0.015)), 0.010, 0.008, skin, P, rings=4, seg=10)
        # legs (car frame through root: they stay in the footwell)
        for sx in (-1, 1):
            hip = Vector((hx + 0.095 * sx, hy, hz))
            knee = Vector((hx + 0.11 * sx, hy + 0.47, hz + 0.07))
            ankle = Vector((hx + 0.11 * sx, hy + 0.55, hz - 0.33))
            capsule(f"Driver thigh {sx}", hip, knee, 0.085, 0.062, trousers, root)
            capsule(f"Driver shin {sx}", knee, ankle, 0.058, 0.045, trousers, root)
            blob(f"Driver knee {sx}", knee, (0.063, 0.063, 0.063), trousers, root)
            capsule(f"Driver shoe {sx}", ankle + Vector((0, -0.03, -0.04)), ankle + Vector((0, 0.13, -0.06)), 0.045, 0.040, shoe, root, squash=0.75)
        capsule("Driver pelvis", (hx - 0.12, hy - 0.01, hz + 0.02), (hx + 0.12, hy - 0.01, hz + 0.02), 0.11, 0.11, trousers, root, squash=0.85)
        # steering wheel (rim + three spokes + hub), same place and tilt as before
        wheel = material("Steering wheel", (0.04, 0.04, 0.045), rough=0.45)
        bpy.ops.mesh.primitive_torus_add(major_radius=0.18, minor_radius=0.019, major_segments=64, minor_segments=16, location=self.WHEEL,
                                         rotation=(math.radians(-58), 0, 0))
        wob = bpy.context.object
        wob.name = "Steering wheel"
        wob.data.materials.append(wheel)
        wob.parent = root
        for p in wob.data.polygons:
            p.use_smooth = True
        self.head = self.neck
