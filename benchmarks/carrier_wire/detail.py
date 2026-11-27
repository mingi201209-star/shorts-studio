"""EP.35 detail pass (owner, 2026-11-27: "the detail disappeared"): a smooth, panelled generic navy fighter (lofted fuselage under a
subdivision surface, strakes, intakes, canted tails with a coloured band, a framed canopy, petalled nozzles, landing gear, lights),
a weathered flight deck (non-skid grain, tyre streaks, oil stains, catapult tracks, blast deflectors, elevators), catwalks with
safety nets and life-raft canisters, a built-up island with a lattice mast and radars, parked jets with folded wings, tow tractors,
a deck crew in their coloured jerseys, the ship's wake and an escort on the horizon. Blender only. No text, numbers or insignia."""
from __future__ import annotations

import math
import random

import bpy

from benchmarks.road_safety import render_jersey_barrier as base

material, cube = base.material, base.cube


def _mesh(name, verts, faces, mat, smooth=False, subdiv=0):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = smooth
    if subdiv:
        mod = ob.modifiers.new("Smooth", "SUBSURF")
        mod.levels = 1
        mod.render_levels = subdiv
    return ob


def _cyl(name, r, depth, loc, mat, rot=(0.0, 0.0, 0.0), verts=24, smooth=True):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth, location=loc, rotation=rot)
    ob = bpy.context.object
    ob.name = name
    ob.data.materials.append(mat)
    for p in ob.data.polygons:
        p.use_smooth = smooth
    return ob


def _sphere(name, r, loc, mat, scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=r, location=loc)
    ob = bpy.context.object
    ob.name = name
    ob.scale = scale
    ob.data.materials.append(mat)
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


# ---------------------------------------------------------------------------------------------------------------------- materials

def navy_paint(name="Navy paint"):
    """Two-tone tactical grey (lighter underneath), fine panel lines and light weathering, in object space."""
    mt = bpy.data.materials.get(name)
    if mt is not None:
        return mt
    mt = material(name, (0.38, 0.41, 0.44), metal=0.15, rough=0.5)
    nt = mt.node_tree
    b = nt.nodes.get("Principled BSDF")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    under = nt.nodes.new("ShaderNodeMapRange")
    under.inputs["From Min"].default_value = 1.55
    under.inputs["From Max"].default_value = 1.95
    nt.links.new(sep.outputs["Z"], under.inputs["Value"])
    tone = nt.nodes.new("ShaderNodeMix")
    tone.data_type = "RGBA"
    tone.inputs[6].default_value = (0.60, 0.63, 0.66, 1)          # underside
    tone.inputs[7].default_value = (0.33, 0.36, 0.40, 1)          # top
    nt.links.new(under.outputs["Result"], tone.inputs[0])
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.feature = "DISTANCE_TO_EDGE"
    vor.inputs["Scale"].default_value = 1.1
    nt.links.new(tc.outputs["Object"], vor.inputs["Vector"])
    line = nt.nodes.new("ShaderNodeMapRange")
    line.inputs["From Min"].default_value = 0.0
    line.inputs["From Max"].default_value = 0.025
    line.inputs["To Min"].default_value = 0.72
    line.inputs["To Max"].default_value = 1.0
    nt.links.new(vor.outputs["Distance"], line.inputs["Value"])
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 3.0
    noise.inputs["Detail"].default_value = 6
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    wear = nt.nodes.new("ShaderNodeMapRange")
    wear.inputs["To Min"].default_value = 0.9
    wear.inputs["To Max"].default_value = 1.06
    nt.links.new(noise.outputs["Fac"], wear.inputs["Value"])
    m1 = nt.nodes.new("ShaderNodeMath")
    m1.operation = "MULTIPLY"
    nt.links.new(line.outputs["Result"], m1.inputs[0])
    nt.links.new(wear.outputs["Result"], m1.inputs[1])
    col = nt.nodes.new("ShaderNodeMix")
    col.data_type = "RGBA"
    col.blend_type = "MULTIPLY"
    col.inputs[0].default_value = 1.0
    nt.links.new(tone.outputs[2], col.inputs[6])
    comb = nt.nodes.new("ShaderNodeCombineColor")
    nt.links.new(m1.outputs[0], comb.inputs[0])
    nt.links.new(m1.outputs[0], comb.inputs[1])
    nt.links.new(m1.outputs[0], comb.inputs[2])
    nt.links.new(comb.outputs[0], col.inputs[7])
    nt.links.new(col.outputs[2], b.inputs["Base Color"])
    return mt


def deck_material(name="Flight deck"):
    """Non-skid deck: a fine dark grain, broad weathered patches, rubber from the tyres laid down along the landing area's middle
    (soft dark bands, densest near the centre line), and a few oil stains. Kept low in contrast so it reads as one worn surface."""
    mt = bpy.data.materials.get(name)
    if mt is not None:
        return mt
    mt = material(name, (0.08, 0.082, 0.088), rough=0.93)
    nt = mt.node_tree
    b = nt.nodes.get("Principled BSDF")
    tc = nt.nodes.new("ShaderNodeTexCoord")

    def noise(vec, scale, detail):
        n = nt.nodes.new("ShaderNodeTexNoise")
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = detail
        nt.links.new(vec, n.inputs["Vector"])
        return n.outputs["Fac"]

    def remap(value, lo, hi, to_lo, to_hi):
        r = nt.nodes.new("ShaderNodeMapRange")
        r.inputs["From Min"].default_value, r.inputs["From Max"].default_value = lo, hi
        r.inputs["To Min"].default_value, r.inputs["To Max"].default_value = to_lo, to_hi
        nt.links.new(value, r.inputs["Value"])
        return r.outputs["Result"]

    def mul(x, y):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = "MULTIPLY"
        nt.links.new(x, n.inputs[0])
        if isinstance(y, float):
            n.inputs[1].default_value = y
        else:
            nt.links.new(y, n.inputs[1])
        return n.outputs[0]

    obj = tc.outputs["Object"]
    grain = noise(obj, 60.0, 8)
    patches = remap(noise(obj, 0.05, 3), 0.40, 0.60, 0.92, 1.08)
    stains = remap(noise(obj, 0.09, 3), 0.60, 0.68, 1.0, 0.72)
    stretch = nt.nodes.new("ShaderNodeMapping")
    stretch.inputs["Scale"].default_value = (1.0, 0.025, 1.0)          # tyre rubber runs along y, the landing direction
    nt.links.new(obj, stretch.inputs["Vector"])
    rubber = remap(noise(stretch.outputs["Vector"], 1.2, 3), 0.45, 0.70, 0.0, 1.0)
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(obj, sep.inputs["Vector"])
    ax = nt.nodes.new("ShaderNodeMath")
    ax.operation = "ABSOLUTE"
    nt.links.new(sep.outputs["X"], ax.inputs[0])
    centre = remap(ax.outputs[0], 2.5, 10.0, 1.0, 0.0)                 # densest near the centre line, gone by the landing-area edge
    dark = remap(mul(rubber, centre), 0.0, 1.0, 1.0, 0.62)
    v = mul(mul(mul(remap(grain, 0.0, 1.0, 0.86, 1.14), patches), mul(stains, dark)), 0.085)
    comb = nt.nodes.new("ShaderNodeCombineColor")
    nt.links.new(v, comb.inputs[0])
    nt.links.new(v, comb.inputs[1])
    nt.links.new(mul(v, 1.07), comb.inputs[2])
    nt.links.new(comb.outputs[0], b.inputs["Base Color"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.25
    bump.inputs["Distance"].default_value = 0.01
    nt.links.new(grain, bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return mt


def hull_material(name="Hull grey", colour=(0.15, 0.16, 0.175)):
    """Haze-grey ship steel: welded plates (seams, a few metres across, rows about 2 m tall, laid out along the side and up the
    height, so the stern and both sides get them), faint grime streaks running down, and a little mottling."""
    mt = bpy.data.materials.get(name)
    if mt is not None:
        return mt
    mt = material(name, colour, rough=0.7)
    nt = mt.node_tree
    b = nt.nodes.get("Principled BSDF")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    along = nt.nodes.new("ShaderNodeMath")                 # x + y runs along the stern and both sides alike
    along.operation = "ADD"
    nt.links.new(sep.outputs["X"], along.inputs[0])
    nt.links.new(sep.outputs["Y"], along.inputs[1])
    uv = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(along.outputs[0], uv.inputs["X"])
    nt.links.new(sep.outputs["Z"], uv.inputs["Y"])
    brick = nt.nodes.new("ShaderNodeTexBrick")
    brick.inputs["Scale"].default_value = 0.125              # 8 m per texture unit: plates 4 m by 2 m
    brick.inputs["Mortar Size"].default_value = 0.004
    brick.inputs["Color1"].default_value = (*colour, 1)
    brick.inputs["Color2"].default_value = tuple(c * 0.95 for c in colour) + (1,)
    brick.inputs["Mortar"].default_value = tuple(c * 0.78 for c in colour) + (1,)     # seams faint: plating, not tiles
    nt.links.new(uv.outputs["Vector"], brick.inputs["Vector"])
    streak_v = nt.nodes.new("ShaderNodeCombineXYZ")          # streaks: fine along the side, long down the height
    m1 = nt.nodes.new("ShaderNodeMath")
    m1.operation = "MULTIPLY"
    m1.inputs[1].default_value = 1.2
    nt.links.new(along.outputs[0], m1.inputs[0])
    m2 = nt.nodes.new("ShaderNodeMath")
    m2.operation = "MULTIPLY"
    m2.inputs[1].default_value = 0.06
    nt.links.new(sep.outputs["Z"], m2.inputs[0])
    nt.links.new(m1.outputs[0], streak_v.inputs["X"])
    nt.links.new(m2.outputs[0], streak_v.inputs["Y"])
    streak = nt.nodes.new("ShaderNodeTexNoise")
    streak.inputs["Scale"].default_value = 1.0
    streak.inputs["Detail"].default_value = 4
    nt.links.new(streak_v.outputs["Vector"], streak.inputs["Vector"])
    grime = nt.nodes.new("ShaderNodeMapRange")
    grime.inputs["From Min"].default_value, grime.inputs["From Max"].default_value = 0.5, 0.75
    grime.inputs["To Min"].default_value, grime.inputs["To Max"].default_value = 1.0, 0.72
    nt.links.new(streak.outputs["Fac"], grime.inputs["Value"])
    mottle = nt.nodes.new("ShaderNodeTexNoise")
    mottle.inputs["Scale"].default_value = 0.3
    nt.links.new(tc.outputs["Object"], mottle.inputs["Vector"])
    mot = nt.nodes.new("ShaderNodeMapRange")
    mot.inputs["To Min"].default_value, mot.inputs["To Max"].default_value = 0.9, 1.1
    nt.links.new(mottle.outputs["Fac"], mot.inputs["Value"])
    k = nt.nodes.new("ShaderNodeMath")
    k.operation = "MULTIPLY"
    nt.links.new(grime.outputs["Result"], k.inputs[0])
    nt.links.new(mot.outputs["Result"], k.inputs[1])
    shade = nt.nodes.new("ShaderNodeMix")
    shade.data_type = "RGBA"
    shade.blend_type = "MULTIPLY"
    shade.inputs["Factor"].default_value = 1.0
    nt.links.new(brick.outputs["Color"], shade.inputs["A"])
    kc = nt.nodes.new("ShaderNodeCombineColor")
    for i in range(3):
        nt.links.new(k.outputs[0], kc.inputs[i])
    nt.links.new(kc.outputs["Color"], shade.inputs["B"])
    nt.links.new(shade.outputs["Result"], b.inputs["Base Color"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.2
    bump.inputs["Distance"].default_value = 0.02
    bump.invert = True                                       # the brick texture's Fac is 1 on the mortar: the seams sit in
    nt.links.new(brick.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return mt


def glass(name, colour=(0.10, 0.12, 0.13), alpha=0.85, rough=0.05):
    mt = bpy.data.materials.get(name)
    if mt is None:
        mt = material(name, colour, metal=0.3, rough=rough)
        mt.node_tree.nodes.get("Principled BSDF").inputs["Alpha"].default_value = alpha
    return mt


def canopy_glass(name="Canopy glass"):
    """Canopy glass that reads as a bubble: clear where you look straight through it, reflecting the sky toward its edges (the
    alpha follows a Fresnel weight), with a faint gold tint."""
    mt = bpy.data.materials.get(name)
    if mt is not None:
        return mt
    mt = material(name, (0.22, 0.20, 0.12), rough=0.03)
    nt = mt.node_tree
    b = nt.nodes.get("Principled BSDF")
    b.inputs["Specular IOR Level"].default_value = 1.0
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.35
    r = nt.nodes.new("ShaderNodeMapRange")
    r.inputs["To Min"].default_value, r.inputs["To Max"].default_value = 0.12, 0.95
    nt.links.new(lw.outputs["Fresnel"], r.inputs["Value"])
    nt.links.new(r.outputs["Result"], b.inputs["Alpha"])
    return mt


def emissive(name, colour, strength):
    mt = bpy.data.materials.get(name)
    if mt is None:
        mt = material(name, colour, rough=0.3)
        b = mt.node_tree.nodes.get("Principled BSDF")
        b.inputs["Emission Color"].default_value = (*colour, 1)
        b.inputs["Emission Strength"].default_value = strength
    return mt


# ---------------------------------------------------------------------------------------------------------------------- the fighter

STATIONS = [  # y, half-width, half-height, centre z (local frame: tailhook tip at the origin, +y forward)
    (0.9, 0.95, 0.52, 1.78), (1.6, 1.12, 0.58, 1.80), (2.6, 1.22, 0.62, 1.84), (4.0, 1.28, 0.64, 1.88), (5.5, 1.30, 0.66, 1.90),
    (7.0, 1.30, 0.66, 1.92), (8.5, 1.25, 0.66, 1.94), (10.0, 1.15, 0.66, 1.98), (11.5, 1.00, 0.66, 2.04), (12.8, 0.86, 0.64, 2.10),
    (13.8, 0.78, 0.62, 2.14), (14.8, 0.70, 0.58, 2.12), (15.8, 0.60, 0.50, 2.06), (16.8, 0.48, 0.40, 1.98), (17.7, 0.34, 0.30, 1.92),
    (18.5, 0.18, 0.17, 1.86), (19.2, 0.03, 0.03, 1.82)]


def _fuselage(name, mat):
    n = 28
    verts, faces = [], []
    for y, w, h, cz in STATIONS:
        for k in range(n):
            a = 2 * math.pi * k / n
            c, s = math.cos(a), math.sin(a)
            e = 2.6
            x = w * math.copysign(abs(c) ** (2 / e), c)
            z = cz + h * math.copysign(abs(s) ** (2 / e), s)
            verts.append((x, y, z))
    rings = len(STATIONS)
    for r in range(rings - 1):
        for k in range(n):
            a, b = r * n + k, r * n + (k + 1) % n
            faces.append((a, b, b + n, a + n))
    faces.append(tuple(range(n))[::-1])
    faces.append(tuple((rings - 1) * n + k for k in range(n)))
    return _mesh(name, verts, faces, mat, smooth=True, subdiv=2)


def _plate(name, root, tip, thick_root, thick_tip, mat, z_root, z_tip, subdiv=0):
    """A thin tapered surface (wing, stabilator, fin) from a root chord to a tip chord, with a lens-shaped section."""
    (xr, y0r, y1r), (xt, y0t, y1t) = root, tip
    verts = []
    for (x, y0, y1, t, z) in ((xr, y0r, y1r, thick_root, z_root), (xt, y0t, y1t, thick_tip, z_tip)):
        ym = y0 + 0.6 * (y1 - y0)
        verts += [(x, y1, z), (x, ym, z + t / 2), (x, y0, z), (x, ym, z - t / 2)]
    faces = [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (0, 3, 2, 1), (4, 5, 6, 7)]
    return _mesh(name, verts, faces, mat, smooth=False, subdiv=subdiv)


def fighter(name="Jet", band=(0.75, 0.08, 0.06), folded=False, simple=False):
    """Returns {root, parts, hook_pivot, hook_down, nozzle_glow, plumes, cockpit_origin}. The root is an empty at the tailhook tip."""
    root = bpy.data.objects.new(f"{name} root", None)
    bpy.context.collection.objects.link(root)
    paint = navy_paint()
    dark = material("Jet dark", (0.10, 0.11, 0.12), metal=0.4, rough=0.5)
    metal = material("Jet nozzle metal", (0.32, 0.30, 0.28), metal=0.9, rough=0.35)
    black = material("Jet black", (0.02, 0.02, 0.025), rough=0.6)
    tyre = material("Jet tyre", (0.03, 0.03, 0.03), rough=0.85)
    hubm = material("Jet hub", (0.65, 0.66, 0.66), metal=0.8, rough=0.3)
    band_mt = material(f"Tail band {band}", band, rough=0.45)
    canopy = canopy_glass()
    frame_mt = material("Canopy frame", (0.20, 0.21, 0.22), metal=0.4, rough=0.5)
    parts = [_fuselage(f"{name} fuselage", paint)]
    for sx in (-1, 1):
        lex = _mesh(f"{name} LEX {sx}", [(sx * 0.75, 10.4, 2.02), (sx * 1.55, 10.9, 2.0), (sx * 0.7, 16.2, 2.1), (sx * 0.55, 16.4, 2.1)],
                    [(0, 1, 2, 3)], paint)
        parts.append(lex)
        parts.append(_mesh(f"{name} intake {sx}", [(sx * 0.95, 11.0, 1.32), (sx * 1.55, 11.0, 1.32), (sx * 1.55, 11.0, 1.92), (sx * 0.95, 11.0, 1.92),
                                                   (sx * 0.95, 9.2, 1.35), (sx * 1.45, 9.2, 1.35), (sx * 1.45, 9.2, 1.9), (sx * 0.95, 9.2, 1.9)],
                           [(0, 1, 2, 3), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3)], paint))
        parts.append(_mesh(f"{name} intake mouth {sx}", [(sx * 1.0, 11.02, 1.38), (sx * 1.5, 11.02, 1.38), (sx * 1.5, 11.02, 1.86), (sx * 1.0, 11.02, 1.86)],
                           [(0, 1, 2, 3)], black))
        inner = 4.0
        wing_in = _plate(f"{name} wing {sx}", (sx * 1.15, 5.3, 11.0), (sx * inner, 6.7, 10.2), 0.22, 0.12, paint, 1.78, 1.76)
        wing_out = _plate(f"{name} outer wing {sx}", (sx * inner, 6.7, 10.2), (sx * 6.4, 7.8, 9.6), 0.12, 0.06, paint, 1.76, 1.74)
        parts.append(wing_in)
        if folded:
            pv = bpy.data.objects.new(f"{name} fold {sx}", None)
            bpy.context.collection.objects.link(pv)
            pv.parent = root
            pv.location = (sx * inner, 0.0, 1.76)
            wing_out.parent = pv
            wing_out.location = (-sx * inner, 0.0, -1.76)
            pv.rotation_euler = (0.0, sx * -math.radians(88), 0.0)
        else:
            parts.append(wing_out)
        rail = cube(f"{name} tip rail {sx}", (sx * 6.45, 8.6, 1.74), (0.08, 2.4, 0.1), dark)
        if folded:
            rail.parent = wing_out                                   # the outer wing's frame is the jet's own (its origin at the root)
        else:
            parts.append(rail)
        if not simple:
            light = _sphere(f"{name} nav {sx}", 0.07, (sx * 6.5, 9.6, 1.76), emissive("Nav red" if sx < 0 else "Nav green", (1, 0.05, 0.03) if sx < 0 else (0.05, 1, 0.2), 8.0))
            if folded:
                light.parent = wing_out
            else:
                parts.append(light)
        parts.append(_plate(f"{name} stabilator {sx}", (sx * 1.0, 0.5, 3.4), (sx * 3.6, 0.9, 2.2), 0.12, 0.05, paint, 1.86, 1.82))
        fin = _plate(f"{name} fin {sx}", (0.0, 1.3, 5.7), (0.0, 2.3, 3.7), 0.14, 0.06, paint, 0.0, 2.55)
        fin_band = _plate(f"{name} fin band {sx}", (0.0, 2.05, 4.0), (0.0, 2.3, 3.7), 0.09, 0.07, band_mt, 1.9, 2.56)
        for fb in (fin, fin_band):
            fb.rotation_euler = (0.0, sx * math.radians(20), 0.0)
            fb.location = (sx * 1.05, 0.0, 2.3)
            parts.append(fb)
        noz = _cyl(f"{name} nozzle {sx}", 0.50, 1.1, (sx * 0.62, 1.05, 1.78), metal, rot=(math.pi / 2, 0, 0), verts=28)
        parts.append(noz)
        if not simple:
            for p in range(14):
                a = 2 * math.pi * p / 14
                petal = cube(f"{name} petal {sx} {p}", (sx * 0.62 + 0.47 * math.cos(a), 0.42, 1.78 + 0.47 * math.sin(a)), (0.2, 0.32, 0.04), metal)
                petal.rotation_euler = (0.0, -a + math.pi / 2, 0.0)
                parts.append(petal)
        # main gear: strut, door, wheel
        parts.append(_cyl(f"{name} main strut {sx}", 0.08, 1.05, (sx * 1.62, 7.2, 0.95), dark, rot=(0, sx * 0.18, 0), verts=12))
        parts.append(cube(f"{name} main door {sx}", (sx * 1.35, 7.2, 1.0), (0.04, 1.4, 0.7), paint))
        parts.append(_cyl(f"{name} main tyre {sx}", 0.46, 0.3, (sx * 1.78, 7.2, 0.46), tyre, rot=(0, math.pi / 2, 0), verts=32))
        parts.append(_cyl(f"{name} main hub {sx}", 0.26, 0.32, (sx * 1.78, 7.2, 0.46), hubm, rot=(0, math.pi / 2, 0), verts=20))
    parts.append(_cyl(f"{name} nose strut", 0.06, 1.15, (0.0, 14.7, 0.9), dark, verts=12))
    for sx in (-1, 1):
        parts.append(_cyl(f"{name} nose tyre {sx}", 0.3, 0.18, (sx * 0.16, 14.7, 0.3), tyre, rot=(0, math.pi / 2, 0), verts=24))
    parts.append(cube(f"{name} launch bar", (0.0, 15.3, 0.55), (0.08, 1.1, 0.06), dark))
    # canopy, its frame, the cockpit inside
    parts.append(_sphere(f"{name} canopy", 1.0, (0.0, 15.0, 2.62), canopy, scale=(0.56, 1.75, 0.62)))
    # the frame: open arches that follow the bubble's section (the bow behind the pilot, the windscreen arch ahead of him)
    for label, y in (("canopy bow", 14.2), ("windscreen arch", 16.3)):
        f = math.sqrt(max(0.0, 1.0 - ((y - 15.0) / 1.75) ** 2))
        bpy.ops.mesh.primitive_torus_add(major_radius=0.56 * f, minor_radius=0.032, major_segments=40, minor_segments=8,
                                         location=(0.0, y, 2.62), rotation=(math.pi / 2, 0, 0))
        arch = bpy.context.object
        arch.name = f"{name} {label}"
        arch.scale = (1.0, 0.62 / 0.56, 1.0)                 # local y is world z after the quarter turn about x
        arch.data.materials.append(frame_mt)
        for poly in arch.data.polygons:
            poly.use_smooth = True
        parts.append(arch)
    if not simple:      # the ejection seat right behind the pilot's back (Bumper's chest is 0.115 m deep at 0.8 scale, root at y 14.85)
        parts.append(cube(f"{name} seat back", (0.0, 14.66, 2.7), (0.52, 0.12, 0.8), black))
        parts.append(cube(f"{name} head box", (0.0, 14.62, 3.18), (0.42, 0.2, 0.34), black))
        parts.append(_cyl(f"{name} seat handle", 0.014, 0.3, (0.0, 14.62, 3.37), emissive("Handle yellow", (0.9, 0.7, 0.05), 0.4),
                          rot=(0, math.pi / 2, 0), verts=8))
    for sx in (-1, 1):
        parts.append(cube(f"{name} canopy rail {sx}", (sx * 0.55, 15.0, 2.33), (0.05, 3.4, 0.05), frame_mt))
    parts.append(cube(f"{name} cockpit tub", (0.0, 15.0, 2.18), (0.95, 2.9, 0.3), black))
    if not simple:
        parts.append(cube(f"{name} instrument panel", (0.0, 16.25, 2.42), (0.8, 0.12, 0.32), black))
        for k, (sx_, c) in enumerate(((-0.2, (0.1, 0.9, 0.3)), (0.2, (1.0, 0.65, 0.1)))):
            parts.append(cube(f"{name} screen {k}", (sx_, 16.18, 2.46), (0.16, 0.02, 0.12), emissive(f"Screen {k}", c, 3.0)))
        parts.append(_sphere(f"{name} beacon", 0.08, (0.0, 9.0, 2.62), emissive("Beacon red", (1, 0.08, 0.05), 6.0)))
    for ob in parts:
        if ob.parent is None:
            ob.parent = root
    out = {"root": root, "parts": parts, "paint": paint}
    if not simple:
        glow = material("Nozzle glow", (1.0, 0.45, 0.1), rough=0.4, emission=0.0)
        out["nozzle_glow"] = glow
        for sx in (-1, 1):
            g = _cyl(f"{name} afterburner {sx}", 0.40, 0.05, (sx * 0.62, 0.5, 1.78), glow, rot=(math.pi / 2, 0, 0), verts=24)
            g.parent = root
            parts.append(g)
    return out


# ---------------------------------------------------------------------------------------------------------------------- the ship

def island(hull_mt):
    """A built-up island: tiers, window bands, the overhanging flight-control glass, a lattice mast with radars and domes."""
    dark = glass("Island glass", (0.04, 0.06, 0.08), alpha=1.0, rough=0.08)
    steel = material("Mast steel", (0.30, 0.32, 0.34), metal=0.5, rough=0.5)
    white = material("Radome white", (0.85, 0.86, 0.84), rough=0.5)
    obs = [cube("Island base", (30.5, 85.0, 7.0), (8.5, 32.0, 14.0), hull_mt), cube("Island tier", (30.8, 85.5, 16.5), (7.6, 26.0, 5.0), hull_mt),
           cube("Island bridge", (30.8, 84.0, 21.0), (7.2, 20.0, 4.0), hull_mt), cube("Island top", (31.0, 84.0, 24.0), (5.8, 14.0, 2.0), hull_mt),
           cube("Island window band 1", (26.48, 85.5, 17.6), (0.08, 25.0, 1.3), dark), cube("Island window band 2", (27.18, 84.0, 21.8), (0.08, 19.0, 1.2), dark),
           cube("Flight control glass", (25.9, 80.0, 19.6), (1.6, 8.0, 2.2), dark), cube("Flight control roof", (25.9, 80.0, 20.8), (1.8, 8.4, 0.2), hull_mt)]
    for x, y in ((29.0, 81.0), (33.0, 81.0), (29.0, 87.0), (33.0, 87.0)):
        leg = _cyl(f"Mast leg {x} {y}", 0.12, 15.0, (x + (31.0 - x) * 0.35, y + (84.0 - y) * 0.35, 32.0), steel, verts=8)
        leg.rotation_euler = (math.atan2(84.0 - y, 15.0) * 0.6, -math.atan2(31.0 - x, 15.0) * 0.6, 0.0)
        obs.append(leg)
    for z in (28.0, 32.0, 36.0):
        obs.append(cube(f"Mast brace {z}", (31.0, 84.0, z), (3.4 - (z - 28) * 0.25, 0.12, 0.12), steel))
        obs.append(cube(f"Mast brace b {z}", (31.0, 84.0, z), (0.12, 3.4 - (z - 28) * 0.25, 0.12), steel))
    obs += [cube("Mast yard", (31.0, 84.0, 34.0), (7.0, 0.15, 0.15), steel), cube("Radar panel 1", (31.0, 82.6, 30.0), (3.2, 0.25, 2.0), steel),
            cube("Radar panel 2", (31.0, 85.4, 26.5), (2.6, 0.25, 1.6), steel), _sphere("Radome 1", 1.1, (27.6, 90.5, 26.4), white),
            _sphere("Radome 2", 0.9, (34.2, 78.0, 26.2), white), _cyl("Mast top", 0.08, 4.0, (31.0, 84.0, 40.5), steel, verts=8)]
    for k, (x, y) in enumerate(((27.5, 96.5), (34.0, 94.0), (34.5, 73.0))):
        obs.append(_cyl(f"Island antenna {k}", 0.05, 6.0, (x, y, 28.0), steel, verts=6))
    return obs


def deck_furniture(deck_y, outline):
    """Catapult tracks and blast deflectors at the bow, elevator outlines, catwalks with safety nets and life-raft canisters."""
    track = material("Catapult track", (0.03, 0.03, 0.035), metal=0.6, rough=0.4)
    jbd = material("Blast deflector", (0.30, 0.32, 0.34), metal=0.6, rough=0.45)
    elev = material("Elevator edge", (0.16, 0.16, 0.17), rough=0.7)
    net = material("Safety net", (0.06, 0.06, 0.06), rough=0.8)
    raft = material("Raft canister", (0.88, 0.88, 0.84), rough=0.5)
    yellow = material("Deck yellow", (0.88, 0.70, 0.08), rough=0.6)
    red = material("Deck red", (0.75, 0.10, 0.08), rough=0.6)
    obs = []
    # the bow catapults start past the end of the landing runout (the hook stops near y 134, the nose near y 152), so their raised
    # blast deflectors stand clear of the landing jet, as on a real deck where the landing area is kept clear
    for x in (-6.0, 6.0):
        obs.append(cube(f"Catapult {x}", (x, 196.0, 0.004), (0.35, 50.0, 0.01), track))
        obs.append(cube(f"Shuttle {x}", (x, 186.0, 0.12), (0.6, 1.2, 0.25), jbd))
        d = cube(f"Blast deflector {x}", (x, 176.0, 1.5), (11.0, 0.3, 3.4), jbd)
        d.rotation_euler = (math.radians(-30), 0.0, 0.0)
        obs.append(d)
        y = 184.0
        while y < 216.0:
            obs.append(cube(f"Cat light {x} {y:.0f}", (x + 1.0, y, 0.006), (0.25, 0.25, 0.01), yellow))
            y += 6.0
    for k, (x0, x1, y0, y1) in enumerate(((28.0, 38.0, 30.0, 50.0), (28.0, 38.0, 110.0, 128.0), (-38.0, -28.0, 132.0, 150.0))):
        for (cx, cy, sx, sy) in (((x0 + x1) / 2, y0, x1 - x0, 0.2), ((x0 + x1) / 2, y1, x1 - x0, 0.2), (x0, (y0 + y1) / 2, 0.2, y1 - y0)):
            obs.append(cube(f"Elevator {k} {cx:.0f} {cy:.0f}", (cx, cy, 0.007), (sx, sy, 0.012), elev))
    for k in range(0, 40):
        y = deck_y[0] + 6 + k * 8.0
        obs.append(cube(f"Foul stripe {k}", (-17.6, y, 0.007), (0.4, 2.0, 0.012), red if k % 2 else yellow))
    # the optical landing aid on the port side, facing the approach: a lens column with the amber "ball" lit in its middle and a
    # bar of green datum lights either side (lit, so it reads in the approach and on-deck shots)
    housing = material("Lens housing", (0.10, 0.10, 0.11), rough=0.6)
    amber = material("Lens amber", (1.0, 0.55, 0.05), emission=6.0)
    green = material("Datum green", (0.15, 1.0, 0.25), emission=5.0)
    cell = material("Lens cell", (0.03, 0.03, 0.035), metal=0.4, rough=0.3)
    lx, ly = -24.0, 20.0
    obs.append(cube("Lens base", (lx, ly + 0.4, 0.6), (1.0, 1.0, 1.2), housing))
    obs.append(cube("Lens column", (lx, ly, 1.9), (0.9, 0.6, 1.9), housing))
    for j in range(5):
        obs.append(cube(f"Lens cell {j}", (lx, ly - 0.31, 1.2 + j * 0.34), (0.6, 0.04, 0.26), amber if j == 2 else cell))
    for sx in (-1, 1):
        obs.append(cube(f"Datum bar {sx}", (lx + sx * 2.1, ly, 1.88), (3.0, 0.25, 0.22), housing))
        for j in range(5):
            obs.append(cube(f"Datum light {sx} {j}", (lx + sx * (1.0 + j * 0.55), ly - 0.14, 1.88), (0.28, 0.04, 0.14), green))
    n = len(outline)
    for i in range(n):
        (xa, ya), (xb, yb) = outline[i], outline[(i + 1) % n]
        L = math.hypot(xb - xa, yb - ya)
        if L < 4:
            continue
        nx, ny = (yb - ya) / L, -(xb - xa) / L                      # outward normal (outline is counter-clockwise)
        cx, cy = (xa + xb) / 2 + nx * 1.0, (ya + yb) / 2 + ny * 1.0
        ang = math.atan2(-(xb - xa), yb - ya)
        walk = cube(f"Catwalk {i}", (cx, cy, -1.3), (1.6, L, 0.15), elev)
        walk.rotation_euler = (0.0, 0.0, ang)
        sn = cube(f"Safety net {i}", (cx + nx * 0.9, cy + ny * 0.9, -0.55), (0.04, L, 1.4), net)
        sn.rotation_euler = (0.0, 0.0, ang)
        obs += [walk, sn]
        for j in range(int(L // 12)):
            f = (j + 0.5) / max(1, int(L // 12))
            px, py = xa + (xb - xa) * f + nx * 1.1, ya + (yb - ya) * f + ny * 1.1
            obs.append(_cyl(f"Raft {i} {j}", 0.35, 1.2, (px, py, -0.9), raft, rot=(0, math.pi / 2, ang), verts=16))
    return obs


def _edge_x(outline, y, side):
    """The deck outline's x on one side (+1 starboard, -1 port) at y."""
    n = len(outline)
    for i in range(n):
        (xa, ya), (xb, yb) = outline[i], outline[(i + 1) % n]
        if min(ya, yb) <= y <= max(ya, yb) and ya != yb and (xa + xb) * side > 0:
            return xa + (xb - xa) * (y - ya) / (yb - ya)
    raise ValueError(f"no edge at y={y} on side {side}")


def hull_openings(outline, sea_z):
    """Dark openings in the hull under the flight deck: the hangar's elevator doors on both sides and the fantail across the stern,
    each a thin plate just proud of the near-vertical side (the side runs at 0.95 to 0.93 of the deck outline down to the sea), and
    sponson galleries along the port side under the deck edge."""
    dark = material("Hangar dark", (0.012, 0.012, 0.014), rough=0.9)
    lit = material("Hangar light", (1.0, 0.85, 0.6), emission=1.5)
    grey = material("Gallery grey", (0.20, 0.21, 0.22), rough=0.7)
    obs = []
    for k, (side, y0, y1) in enumerate(((1, 30.0, 50.0), (1, 110.0, 128.0), (-1, 36.0, 54.0))):   # under the elevators, and one to port
        x = _edge_x(outline, (y0 + y1) / 2, side) * 0.955
        obs.append(cube(f"Hangar door {k}", (x, (y0 + y1) / 2, -5.2), (0.12, y1 - y0 - 2.0, 7.6), dark))
        for j in range(3):
            obs.append(cube(f"Hangar lamp {k} {j}", (x - side * 0.05, y0 + 3.0 + j * (y1 - y0 - 6.0) / 2, -1.9), (0.1, 0.6, 0.12), lit))
    y_stern = min(y for _, y in outline)
    obs.append(cube("Fantail", (-3.0, y_stern - 0.15, -4.0), (34.0, 0.12, 4.8), dark))
    for j in range(5):
        obs.append(cube(f"Fantail lamp {j}", (-16.0 + j * 6.5, y_stern - 0.1, -2.0), (0.6, 0.1, 0.12), lit))
    for k, y in enumerate((-80.0, -20.0, 70.0, 160.0)):
        x = _edge_x(outline, y, -1)
        obs.append(cube(f"Gallery {k}", (x + 0.2, y, -2.2), (1.6, 14.0, 0.5), grey))
    return obs


def tow_tractor(k, loc, yaw):
    body = material("Tractor yellow", (0.85, 0.62, 0.06), rough=0.5)
    dark = material("Tractor dark", (0.05, 0.05, 0.05), rough=0.7)
    root = bpy.data.objects.new(f"Tow tractor {k}", None)
    bpy.context.collection.objects.link(root)
    parts = [cube(f"Tractor body {k}", (0, 0, 0.6), (1.8, 3.0, 0.7), body), cube(f"Tractor seat {k}", (0, -0.6, 1.2), (0.9, 0.8, 0.6), dark)]
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(_cyl(f"Tractor wheel {k} {sx} {sy}", 0.35, 0.3, (sx * 0.95, sy * 1.0, 0.35), dark, rot=(0, math.pi / 2, 0), verts=16))
    for ob in parts:
        ob.parent = root
    root.location = loc
    root.rotation_euler = (0, 0, yaw)
    return root


def _rbox(name, loc, size, mat, bevel=0.03, parent=None):
    ob = cube(name, loc, size, mat)
    mod = ob.modifiers.new("Round", "BEVEL")
    mod.width, mod.segments = bevel, 3
    for poly in ob.data.polygons:
        poly.use_smooth = True
    if parent is not None:
        ob.parent = parent
    return ob


def crew_member(k, colour):
    """A flight-deck crew member in the jersey colour of the job: float vest with reflective bands over the jersey, cranial helmet
    in the same colour with goggles and ear defenders, gloves, dark trousers and boots. Root at the feet, facing +y; the torso
    pivots at the hips (lean about x). Returns (root, torso)."""
    jersey = material(f"Jersey {k}", colour, rough=0.65)
    vest = material(f"Vest {k}", tuple(c * 0.82 for c in colour), rough=0.6)
    trousers = material(f"Crew trousers {k}", (0.16, 0.15, 0.12), rough=0.85)
    boots = material("Crew boots", (0.04, 0.035, 0.03), rough=0.6)
    tape = material("Reflective tape", (0.85, 0.86, 0.84), metal=0.3, rough=0.25)
    skin = material(f"Crew skin {k}", (0.55, 0.38, 0.27), rough=0.7)
    goggle = material("Goggles", (0.03, 0.04, 0.05), metal=0.5, rough=0.15)
    glove = material("Crew gloves", (0.30, 0.24, 0.16), rough=0.8)
    root = bpy.data.objects.new(f"Crew {k}", None)
    bpy.context.collection.objects.link(root)
    torso = bpy.data.objects.new(f"Crew torso {k}", None)
    bpy.context.collection.objects.link(torso)
    torso.parent = root
    torso.location = (0, 0, 0.92)
    for sx in (-1, 1):
        leg = _cyl(f"Crew leg {sx} {k}", 0.082, 0.84, (sx * 0.1, 0.0, 0.5), trousers, verts=12)
        leg.parent = root
        _rbox(f"Crew boot {sx} {k}", (sx * 0.1, 0.05, 0.055), (0.13, 0.29, 0.11), boots, 0.035, root)
    _rbox(f"Crew hips {k}", (0, 0, 0.02), (0.36, 0.22, 0.16), trousers, 0.05, torso)
    _rbox(f"Crew jersey {k}", (0, 0, 0.27), (0.40, 0.24, 0.52), jersey, 0.09, torso)
    _rbox(f"Crew vest {k}", (0, 0, 0.33), (0.45, 0.29, 0.34), vest, 0.07, torso)
    for z in (0.24, 0.42):
        _rbox(f"Crew tape {k} {z}", (0, 0, z), (0.46, 0.30, 0.035), tape, 0.012, torso)
    for sx in (-1, 1):
        arm = _cyl(f"Crew arm {sx} {k}", 0.052, 0.56, (sx * 0.25, 0.13, 0.30), jersey, rot=(0.95, 0.0, 0.0), verts=12)        # shoulder back-high, hand forward-low
        arm.parent = torso
        hand = _sphere(f"Crew glove {sx} {k}", 0.055, (sx * 0.25, 0.36, 0.13), glove)
        hand.parent = torso
    neck = _cyl(f"Crew neck {k}", 0.05, 0.1, (0, 0, 0.58), skin, verts=12)
    neck.parent = torso
    head = _sphere(f"Crew head {k}", 0.105, (0, 0.01, 0.69), skin)
    head.parent = torso
    helmet = _sphere(f"Crew cranial {k}", 0.125, (0, -0.01, 0.73), jersey, scale=(1.0, 1.1, 0.8))
    helmet.parent = torso
    _rbox(f"Crew goggles {k}", (0, 0.10, 0.715), (0.19, 0.04, 0.055), goggle, 0.015, torso)
    for sx in (-1, 1):
        cup = _cyl(f"Crew ear {sx} {k}", 0.048, 0.05, (sx * 0.125, 0.0, 0.69), jersey, rot=(0.0, math.pi / 2, 0.0), verts=12)
        cup.parent = torso
    return root, torso


JERSEYS = [(0.95, 0.80, 0.05), (0.10, 0.55, 0.15), (0.10, 0.25, 0.75), (0.80, 0.08, 0.06), (0.45, 0.12, 0.60), (0.92, 0.92, 0.90), (0.45, 0.28, 0.12)]


def crowd(crew_figure, n=18, seed=35):
    """The deck crew standing clear of the landing area: by the island and along the port edge, in their jersey colours."""
    rng = random.Random(seed)
    spots = [(rng.uniform(19.5, 25.0), rng.uniform(55.0, 110.0)) for _ in range(n // 2)] + \
            [(rng.uniform(-35.0, -30.0), rng.uniform(-10.0, 90.0)) for _ in range(n - n // 2)]
    out = []
    for k, (x, y) in enumerate(spots):
        root, torso = crew_figure(100 + k, JERSEYS[k % len(JERSEYS)])
        root.location = (x, y, 0.0)
        root.rotation_euler = (0, 0, math.pi / 2 if x > 0 else -math.pi / 2)
        out.append(root)
    return out


def wake(stern_y, sea_z, length=650.0, rows=40, cols=12):
    """The ship's wake: churned white water astern, broken into long streaks, densest at the stern and down the middle, thinning
    and widening as it trails away (a grid with u across and v along, so the fades follow the band)."""
    mt = bpy.data.materials.new("Wake foam")
    mt.use_nodes = True
    nt = mt.node_tree
    b = nt.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (0.80, 0.90, 0.92, 1)
    b.inputs["Roughness"].default_value = 0.6
    tc = nt.nodes.new("ShaderNodeTexCoord")

    def remap(value, lo, hi, to_lo, to_hi):
        r = nt.nodes.new("ShaderNodeMapRange")
        r.inputs["From Min"].default_value, r.inputs["From Max"].default_value = lo, hi
        r.inputs["To Min"].default_value, r.inputs["To Max"].default_value = to_lo, to_hi
        nt.links.new(value, r.inputs["Value"])
        return r.outputs["Result"]

    def mul(x, y):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = "MULTIPLY"
        nt.links.new(x, n.inputs[0])
        nt.links.new(y, n.inputs[1])
        return n.outputs[0]

    stretch = nt.nodes.new("ShaderNodeMapping")
    stretch.inputs["Scale"].default_value = (0.35, 0.02, 1.0)          # streaks run along the wake
    nt.links.new(tc.outputs["Object"], stretch.inputs["Vector"])
    streaks = nt.nodes.new("ShaderNodeTexNoise")
    streaks.inputs["Scale"].default_value = 1.4
    streaks.inputs["Detail"].default_value = 10
    streaks.inputs["Roughness"].default_value = 0.65
    nt.links.new(stretch.outputs["Vector"], streaks.inputs["Vector"])
    fine = nt.nodes.new("ShaderNodeTexNoise")
    fine.inputs["Scale"].default_value = 0.6
    fine.inputs["Detail"].default_value = 6
    nt.links.new(tc.outputs["Object"], fine.inputs["Vector"])
    uv = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["UV"], uv.inputs["Vector"])
    across = nt.nodes.new("ShaderNodeMath")                            # 1 down the middle, 0 at the edges
    across.operation = "PINGPONG"
    across.inputs[1].default_value = 0.5
    nt.links.new(uv.outputs["X"], across.inputs[0])
    edge = remap(across.outputs[0], 0.0, 0.5, 0.0, 1.0)
    along = remap(uv.outputs["Y"], 0.0, 1.0, 1.0, 0.0)                  # v = 0 at the stern
    density = mul(remap(edge, 0.0, 0.7, 0.0, 1.0), remap(along, 0.0, 1.0, 0.0, 1.0))
    threshold = remap(density, 0.0, 1.0, 0.70, 0.36)                    # thinner foam needs a higher streak value to show
    foam = nt.nodes.new("ShaderNodeMath")
    foam.operation = "SUBTRACT"
    nt.links.new(mul(streaks.outputs["Fac"], remap(fine.outputs["Fac"], 0.3, 0.7, 0.85, 1.15)), foam.inputs[0])
    nt.links.new(threshold, foam.inputs[1])
    alpha = mul(remap(foam.outputs[0], 0.0, 0.12, 0.0, 0.8), remap(along, 0.0, 0.35, 0.0, 1.0))
    nt.links.new(alpha, b.inputs["Alpha"])
    # under the foam, the churned water the screws throw up: a pale turquoise band, smooth, fading the same way
    wash = bpy.data.materials.new("Prop wash")
    wash.use_nodes = True
    wt = wash.node_tree
    wb = wt.nodes.get("Principled BSDF")
    wb.inputs["Base Color"].default_value = (0.05, 0.30, 0.33, 1)
    wb.inputs["Roughness"].default_value = 0.25
    wtc = wt.nodes.new("ShaderNodeTexCoord")
    wsep = wt.nodes.new("ShaderNodeSeparateXYZ")
    wt.links.new(wtc.outputs["UV"], wsep.inputs["Vector"])
    wpp = wt.nodes.new("ShaderNodeMath")
    wpp.operation = "PINGPONG"
    wpp.inputs[1].default_value = 0.5
    wt.links.new(wsep.outputs["X"], wpp.inputs[0])
    wr1 = wt.nodes.new("ShaderNodeMapRange")
    wr1.inputs["From Min"].default_value, wr1.inputs["From Max"].default_value = 0.05, 0.4
    wt.links.new(wpp.outputs[0], wr1.inputs["Value"])
    wr2 = wt.nodes.new("ShaderNodeMapRange")
    wr2.inputs["From Min"].default_value, wr2.inputs["From Max"].default_value = 0.0, 0.6
    wr2.inputs["To Min"].default_value, wr2.inputs["To Max"].default_value = 0.75, 0.0
    wt.links.new(wsep.outputs["Y"], wr2.inputs["Value"])
    wm = wt.nodes.new("ShaderNodeMath")
    wm.operation = "MULTIPLY"
    wt.links.new(wr1.outputs["Result"], wm.inputs[0])
    wt.links.new(wr2.outputs["Result"], wm.inputs[1])
    wt.links.new(wm.outputs[0], wb.inputs["Alpha"])
    verts, faces, uvs = [], [], []
    for j in range(rows + 1):
        v = j / rows
        y = stern_y + 5.0 - length * v
        half = 22.0 + 50.0 * v ** 0.8
        for i in range(cols + 1):
            u = i / cols
            verts.append((-half + 2 * half * u, y, sea_z + 0.1))
            uvs.append((u, v))
    for j in range(rows):
        for i in range(cols):
            k = j * (cols + 1) + i
            faces.append((k, k + 1, k + cols + 2, k + cols + 1))
    out = []
    for nm, mat, dz in (("Wake", mt, 0.1), ("Prop wash", wash, 0.04)):
        ob = _mesh(nm, [(x, y, z - 0.1 + dz) for x, y, z in verts], faces, mat)
        layer = ob.data.uv_layers.new(name="UVMap")
        for poly in ob.data.polygons:
            for li in poly.loop_indices:
                layer.data[li].uv = uvs[ob.data.loops[li].vertex_index]
        out.append(ob)
    return out


def escort(sea_z):
    hull = material("Escort grey", (0.32, 0.34, 0.36), rough=0.7)
    obs = [cube("Escort hull", (-520.0, 650.0, sea_z + 4.0), (17.0, 150.0, 8.0), hull), cube("Escort deckhouse", (-520.0, 660.0, sea_z + 12.0), (12.0, 40.0, 9.0), hull),
           cube("Escort mast", (-520.0, 662.0, sea_z + 22.0), (1.0, 1.0, 12.0), hull)]
    return obs
