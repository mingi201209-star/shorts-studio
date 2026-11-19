"""EP.06 detailed brake and pedal parts (Blender side, procedural meshes; no scene text). Geometry helpers build exact meshes with from_pydata so no
boolean modifiers are needed: annular sectors (disc plates, caliper body, pads), tapered cylinders, curves with a bevel for hoses and cables, and
rounded boxes (bevel modifier). Coordinates follow render_abs_3d.BrakeCutaway: x is the wheel axle (the left wheel's outside is -x), the disc lies
in the y-z plane, and an angle theta is measured in that plane from +y toward +z."""
from __future__ import annotations

import math

import bpy
from mathutils import Vector


def _obj(name, verts, faces, mat, parent=None, loc=(0, 0, 0), smooth=False):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([tuple(v) for v in verts], [], faces)
    mesh.update()
    if smooth:
        mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
    mesh.materials.append(mat)
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(ob)
    ob.parent, ob.location = parent, loc
    return ob


def sector(name, r0, r1, a0, a1, x0, x1, mat, parent=None, loc=(0, 0, 0), n=32):
    """Solid annular sector: radii r0..r1, angles a0..a1 (rad, a full ring if a1 - a0 >= 2*pi), axial extent x0..x1."""
    full = a1 - a0 >= 2 * math.pi - 1e-6
    k = n if full else n + 1
    verts = []
    for i in range(k):
        a = a0 + (a1 - a0) * i / n
        c, s = math.cos(a), math.sin(a)
        for r in (r0, r1):
            for x in (x0, x1):
                verts.append((x, r * c, r * s))
    faces = []
    for i in range(n):
        j = (i + 1) % k if full else i + 1
        a, b = 4 * i, 4 * j
        faces += [(a + 0, a + 1, b + 1, b + 0),        # inner surface
                  (a + 2, b + 2, b + 3, a + 3),        # outer surface
                  (a + 0, b + 0, b + 2, a + 2),        # x0 face
                  (a + 1, a + 3, b + 3, b + 1)]        # x1 face
    if not full:
        e = 4 * n
        faces += [(0, 2, 3, 1), (e + 0, e + 1, e + 3, e + 2)]
    return _obj(name, verts, faces, mat, parent, loc, smooth=False)


def cylinder_x(name, r, x0, x1, y, z, mat, parent=None, n=24, r1=None):
    """Cylinder (or cone if r1 is given) along x, centred on (y, z)."""
    r1 = r if r1 is None else r1
    verts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        verts += [(x0, y + r * math.cos(a), z + r * math.sin(a)), (x1, y + r1 * math.cos(a), z + r1 * math.sin(a))]
    faces = [(2 * i, 2 * ((i + 1) % n), 2 * ((i + 1) % n) + 1, 2 * i + 1) for i in range(n)]
    faces += [tuple(2 * i for i in range(n))[::-1], tuple(2 * i + 1 for i in range(n))]
    return _obj(name, verts, faces, mat, parent, smooth=True)


def rounded_box(name, center, size, mat, parent=None, bevel=0.01, segments=3, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
    ob = bpy.context.object
    ob.name = name
    ob.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    ob.data.materials.append(mat)
    m = ob.modifiers.new("Round edges", "BEVEL")
    m.width, m.segments, m.limit_method = bevel, segments, "ANGLE"
    for p in ob.data.polygons:
        p.use_smooth = True
    ob.parent, ob.location, ob.rotation_euler = parent, center, rot
    return ob


def tube_curve(name, points, radius, mat, parent=None):
    """Hose or cable: a smooth curve through the points with a round bevel (geometry, not text)."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth, cu.bevel_resolution, cu.use_fill_caps = radius, 4, True
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(points) - 1)
    for bp, p in zip(sp.bezier_points, points):
        bp.co = p
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    ob = bpy.data.objects.new(name, cu)
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(mat)
    ob.parent = parent
    return ob


def polar(r, a):
    return r * math.cos(a), r * math.sin(a)


def build_disc(node, steel, dark, hat_m):
    """Vented brake disc at x = -0.06: two friction plates joined by radial vanes, cross-drilled holes, a hat with five wheel studs. Turns with the wheel."""
    xc, plate, gap = -0.06, 0.0075, 0.010
    parts = []
    xo0, xo1 = xc - gap / 2 - plate, xc - gap / 2           # outboard plate
    xi0, xi1 = xc + gap / 2, xc + gap / 2 + plate            # inboard plate
    parts.append(sector("Disc outboard plate", 0.112, 0.19, 0, 2 * math.pi, xo0, xo1, steel, node, n=72))
    parts.append(sector("Disc inboard plate", 0.112, 0.19, 0, 2 * math.pi, xi0, xi1, steel, node, n=72))
    for i in range(30):                                       # cooling vanes between the plates
        a = 2 * math.pi * i / 30
        parts.append(sector(f"Disc vane {i}", 0.115, 0.187, a, a + 0.035, xo1, xi0, dark, node, n=1))
    for i in range(24):                                       # cross-drilled holes on the outboard face (dark inserts read as holes)
        a = 2 * math.pi * i / 24 + (0.07 if i % 2 else 0.0)
        r = 0.135 if i % 2 else 0.165
        y, z = polar(r, a)
        parts.append(cylinder_x(f"Disc hole {i}", 0.0055, xo0 - 0.0006, xo0 + 0.004, y, z, dark, node, n=12))
    parts.append(sector("Disc hat wall", 0.078, 0.086, 0, 2 * math.pi, xo0 - 0.035, xo1, hat_m, node, n=48))
    parts.append(sector("Disc hat face", 0.030, 0.086, 0, 2 * math.pi, xo0 - 0.040, xo0 - 0.035, hat_m, node, n=48))
    for i in range(5):                                        # wheel studs with lug nuts
        y, z = polar(0.055, 2 * math.pi * i / 5 + 0.3)
        parts.append(cylinder_x(f"Wheel stud {i}", 0.006, xo0 - 0.065, xo0 - 0.040, y, z, steel, node, n=12))
        parts.append(cylinder_x(f"Lug nut {i}", 0.011, xo0 - 0.058, xo0 - 0.044, y, z, steel, node, n=6))
    parts.append(cylinder_x("Hub cap", 0.026, xo0 - 0.052, xo0 - 0.040, 0, 0, dark, node, n=24))
    return parts


def build_tone_ring(node, ring_m, n_teeth=44):
    """ABS tone ring (drawn outboard of the disc so it is visible): a band with square teeth and gaps the sensor counts."""
    x0, x1 = -0.112, -0.096
    parts = [sector("Tone ring band", 0.090, 0.098, 0, 2 * math.pi, x0, x1, ring_m, node, n=88)]
    w = 2 * math.pi / n_teeth
    for i in range(n_teeth):
        a = i * w
        parts.append(sector(f"Tone ring tooth {i}", 0.098, 0.110, a, a + 0.5 * w, x0, x1, ring_m, node, n=1))
    return parts


def build_caliper(fixed, body_m, steel, pad_m, back_m, hose_m, rubber_m):
    """Floating caliper over the rear-top of the disc: an arched body (outboard and inboard halves joined by a bridge over the disc edge), two pistons,
    guide bolts, a bleed screw and the brake hose. Pads (friction material on a steel backing plate) sit either side of the disc and are returned so
    their gap can follow the pressure. Does not turn with the wheel."""
    a0, a1 = math.radians(98), math.radians(150)
    xc = -0.06
    parts = []
    parts.append(sector("Caliper outboard half", 0.118, 0.212, a0, a1, xc - 0.046, xc - 0.024, body_m, fixed, n=24))
    parts.append(sector("Caliper inboard half", 0.118, 0.212, a0, a1, xc + 0.024, xc + 0.058, body_m, fixed, n=24))
    parts.append(sector("Caliper bridge", 0.196, 0.214, a0 + 0.06, a1 - 0.06, xc - 0.030, xc + 0.030, body_m, fixed, n=24))
    for k, a in enumerate((math.radians(110), math.radians(138))):
        y, z = polar(0.165, a)
        parts.append(cylinder_x(f"Caliper piston bore {k}", 0.021, xc + 0.058, xc + 0.064, y, z, steel, fixed, n=32))
        parts.append(cylinder_x(f"Caliper piston boot {k}", 0.017, xc + 0.064, xc + 0.068, y, z, rubber_m, fixed, n=32))
    for k, a in enumerate((a0 - 0.05, a1 + 0.05)):            # guide-pin bolts at both ends
        y, z = polar(0.150, a)
        parts.append(cylinder_x(f"Caliper guide bolt {k}", 0.010, xc + 0.040, xc + 0.075, y, z, steel, fixed, n=6))
        parts.append(rounded_box(f"Caliper bolt boss {k}", (xc + 0.040, y, z), (0.022, 0.028, 0.028), body_m, fixed, bevel=0.004))
    y, z = polar(0.205, math.radians(104))
    bleed = cylinder_x("Bleed screw", 0.004, xc + 0.050, xc + 0.075, y, z, steel, fixed, n=12)
    bleed.rotation_euler = (math.radians(-25), 0, 0)
    parts.append(bleed)
    hy, hz = polar(0.20, math.radians(128))
    parts.append(cylinder_x("Hose fitting", 0.008, xc + 0.058, xc + 0.075, hy, hz, steel, fixed, n=6))
    parts.append(tube_curve("Brake hose", [Vector((xc + 0.075, hy, hz)), Vector((xc + 0.13, hy - 0.03, hz + 0.08)), Vector((xc + 0.17, hy - 0.12, hz + 0.20)),
                                         Vector((xc + 0.22, hy - 0.25, hz + 0.24))], 0.007, hose_m, fixed))
    pads = []
    for side in (-1, 1):
        fr = sector(f"Brake pad friction {side}", 0.128, 0.186, a0 + 0.03, a1 - 0.03, -0.004, 0.004, pad_m, fixed, n=16)
        bk = sector(f"Brake pad backing {side}", 0.124, 0.190, a0 + 0.01, a1 - 0.01, side * 0.004, side * 0.0075, back_m, fixed, n=16)
        pads.append((fr, bk, side))
    return parts, pads


def build_sensor(fixed, body_m, hex_m, cable_m, tip_m):
    """Wheel-speed sensor under the tone ring, pointing at the teeth: body, hex mounting flange on a bracket, connector and cable."""
    x = -0.104
    parts = []
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.011, depth=0.055, location=(0, 0, 0))
    body = bpy.context.object
    body.name = "Wheel speed sensor body"
    body.data.materials.append(body_m)
    body.parent, body.location = fixed, (x, 0.0, -0.145)
    bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=0.017, depth=0.010, location=(0, 0, 0))
    hexf = bpy.context.object
    hexf.name = "Sensor hex flange"
    hexf.data.materials.append(hex_m)
    hexf.parent, hexf.location = fixed, (x, 0.0, -0.165)
    bracket = rounded_box("Sensor bracket", (x + 0.02, 0.0, -0.170), (0.05, 0.04, 0.006), hex_m, fixed, bevel=0.003)
    bolt = cylinder_x("Sensor bracket bolt", 0.006, x + 0.03, x + 0.05, 0.0, -0.166, hex_m, fixed, n=6)
    bolt.rotation_euler = (0, math.radians(90), 0)
    tip = rounded_box("Sensor tip", (x, 0.0, -0.1185), (0.016, 0.016, 0.005), tip_m, fixed, bevel=0.002)
    conn = rounded_box("Sensor connector", (x, 0.0, -0.183), (0.018, 0.022, 0.020), body_m, fixed, bevel=0.003)
    cable = tube_curve("Sensor cable", [Vector((x, 0.0, -0.193)), Vector((x + 0.02, -0.04, -0.23)), Vector((x + 0.08, -0.12, -0.25)), Vector((x + 0.15, -0.25, -0.24))],
                       0.004, cable_m, fixed)
    parts += [body, hexf, bracket, bolt, tip, conn, cable]
    return parts, tip
