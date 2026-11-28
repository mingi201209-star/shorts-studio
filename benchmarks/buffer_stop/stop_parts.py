"""EP.36 scene parts (Blender only), built with detail from the start (EP.35's lesson, owner 2026-11-27: "the detail went missing").

- Track: rails in a UIC60-like section (head, web, foot), concrete sleepers every 0.6 m with their fastening clips, a ballast bed.
- The terminus: a platform with its coping, yellow safety line and tactile strip, a canopy on columns with lights and benches,
  passengers; overhead line masts, contact and messenger wires with droppers; the concourse building beyond the end wall; an
  adjacent track with an old fixed stop and a parked train.
- The friction buffer stop: a red steel frame on both rails, a striped buffer beam, two hydraulic buffers (housing, chrome plunger,
  head), a red end lamp, and four friction shoes on each rail (jaws round the rail head, bronze inserts, two through-bolts with nuts).
- A generic six-car electric multiple unit (not any operator's): white body, blue band, yellow cab front, side buffers, windscreen,
  headlights, doors, windows, roof equipment and pantographs, bogies with wheels; a driver's cab with desk, screens and seat, and
  Bumper (the channel's dummy) at the controls.
- The comparisons: a solid concrete wall with debris and dust; a generic sedan on a road with a second dummy at the wheel.
- The crew in orange with wrenches, a yellow rail tractor, sparks, the slide marker and the polished rail.
No text, numbers or logos anywhere."""
from __future__ import annotations

import math
import random

import bpy

from benchmarks.buffer_stop import stop_motion as sm
from benchmarks.carrier_wire import detail as cw
from benchmarks.identity import dummy
from benchmarks.road_safety import render_jersey_barrier as base

material, cube = base.material, base.cube
_mesh, _cyl, _sphere, _rbox, glass, emissive = cw._mesh, cw._cyl, cw._sphere, cw._rbox, cw.glass, cw.emissive

RAIL_X = 0.7535                 # rail head centres (1435 mm gauge, 72 mm heads)
RAIL_H = 0.172
BUFFER_Z = 1.06
BUFFER_X = 0.875
TRACK_Y = (-178.0, 34.0)
ADJ_X = 4.8                     # the adjacent track's centre line
PLATFORM_EDGE = -1.65
PLATFORM_Z = 0.92
CAR_LEN = 22.4
CAR_GAP = 0.8
CAR_W = 2.85
CAB_LEN = 3.3
ROOF_Z = 3.85
BODY_Z0 = 1.05
SHOE_Y = (0.6, 1.6, 2.6, 3.6)   # shoes behind the stop's front plate, on each rail
FRAME_TO_FACE = 1.0             # the buffer heads' faces sit this far ahead of the frame's front plate when free
CAB_SIDE = [(0.1, 1.05), (0.1, 1.9), (0.5, 1.92), (1.6, 3.62), (1.6, ROOF_Z - 0.02), (CAB_LEN, ROOF_Z - 0.02), (CAB_LEN, 1.05)]
#                                 the cab sides' outline: (distance back from the cab face, height)


# ---------------------------------------------------------------------------------------------------------------------- materials
def _nodes_mat(name, colour, rough, metal=0.0):
    mt = bpy.data.materials.get(name)
    if mt is not None:
        return mt, None
    mt = material(name, colour, metal=metal, rough=rough)
    return mt, mt.node_tree


def concrete(name="Concrete", colour=(0.50, 0.49, 0.46), scale=3.0, bump=0.25):
    mt, nt = _nodes_mat(name, colour, 0.9)
    if nt is None:
        return mt
    b = nt.nodes.get("Principled BSDF")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    n1 = nt.nodes.new("ShaderNodeTexNoise")
    n1.inputs["Scale"].default_value = scale
    n1.inputs["Detail"].default_value = 8
    nt.links.new(tc.outputs["Object"], n1.inputs["Vector"])
    n2 = nt.nodes.new("ShaderNodeTexNoise")
    n2.inputs["Scale"].default_value = 60.0
    nt.links.new(tc.outputs["Object"], n2.inputs["Vector"])
    r = nt.nodes.new("ShaderNodeMapRange")
    r.inputs["To Min"].default_value, r.inputs["To Max"].default_value = 0.82, 1.12
    nt.links.new(n1.outputs["Fac"], r.inputs["Value"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = 1.0
    mix.inputs["A"].default_value = (*colour, 1)
    comb = nt.nodes.new("ShaderNodeCombineColor")
    for i in range(3):
        nt.links.new(r.outputs["Result"], comb.inputs[i])
    nt.links.new(comb.outputs["Color"], mix.inputs["B"])
    nt.links.new(mix.outputs["Result"], b.inputs["Base Color"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = bump
    bp.inputs["Distance"].default_value = 0.01
    nt.links.new(n2.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    return mt


def ballast_material():
    mt, nt = _nodes_mat("Ballast", (0.36, 0.34, 0.31), 0.95)
    if nt is None:
        return mt
    b = nt.nodes.get("Principled BSDF")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 18.0
    nt.links.new(tc.outputs["Object"], vor.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.20, 0.19, 0.18, 1)
    ramp.color_ramp.elements[1].color = (0.52, 0.50, 0.46, 1)
    nt.links.new(vor.outputs["Color"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    edge = nt.nodes.new("ShaderNodeTexVoronoi")
    edge.feature = "DISTANCE_TO_EDGE"
    edge.inputs["Scale"].default_value = 18.0
    nt.links.new(tc.outputs["Object"], edge.inputs["Vector"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.8
    bp.inputs["Distance"].default_value = 0.03
    nt.links.new(edge.outputs["Distance"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    return mt


def striped(name, a, b_col, scale=2.2, diagonal=True):
    """Hazard stripes in object space (diagonal by default), for the buffer beam and the tractor's push beam."""
    mt, nt = _nodes_mat(name, a, 0.5)
    if nt is None:
        return mt
    b = nt.nodes.get("Principled BSDF")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    add = nt.nodes.new("ShaderNodeMath")
    add.operation = "ADD" if diagonal else "MULTIPLY"
    nt.links.new(sep.outputs["X"], add.inputs[0])
    if diagonal:
        nt.links.new(sep.outputs["Z"], add.inputs[1])
    else:
        add.inputs[1].default_value = 1.0
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = scale
    nt.links.new(add.outputs[0], mul.inputs[0])
    fr = nt.nodes.new("ShaderNodeMath")
    fr.operation = "FRACT"
    nt.links.new(mul.outputs[0], fr.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    ramp.color_ramp.elements[0].color = (*a, 1)
    ramp.color_ramp.elements[1].position = 0.5
    ramp.color_ramp.elements[1].color = (*b_col, 1)
    nt.links.new(fr.outputs[0], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    return mt


def train_paint(name="Train white", colour=(0.80, 0.81, 0.82)):
    """Painted aluminium body: a faint panel grid (rectangular, frames along the car) and light grime toward the bottom."""
    mt, nt = _nodes_mat(name, colour, 0.35, metal=0.15)
    if nt is None:
        return mt
    b = nt.nodes.get("Principled BSDF")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])

    def m(op, x, y=None):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        for i, v in enumerate((x, y)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = float(v)
            else:
                nt.links.new(v, n.inputs[i])
        return n.outputs[0]

    f = m("FRACT", m("DIVIDE", sep.outputs["Y"], 1.6))
    d = m("MULTIPLY", m("SUBTRACT", 0.5, m("ABSOLUTE", m("SUBTRACT", f, 0.5))), 1.6)
    line = nt.nodes.new("ShaderNodeMapRange")
    line.inputs["From Min"].default_value, line.inputs["From Max"].default_value = 0.0, 0.01
    line.inputs["To Min"].default_value, line.inputs["To Max"].default_value = 0.86, 1.0
    nt.links.new(d, line.inputs["Value"])
    grime = nt.nodes.new("ShaderNodeMapRange")
    grime.inputs["From Min"].default_value, grime.inputs["From Max"].default_value = 1.0, 1.9
    grime.inputs["To Min"].default_value, grime.inputs["To Max"].default_value = 0.78, 1.0
    nt.links.new(sep.outputs["Z"], grime.inputs["Value"])
    k = m("MULTIPLY", line.outputs["Result"], grime.outputs["Result"])
    comb = nt.nodes.new("ShaderNodeCombineColor")
    for i, c in enumerate(colour):
        nt.links.new(m("MULTIPLY", k, c), comb.inputs[i])
    nt.links.new(comb.outputs["Color"], b.inputs["Base Color"])
    return mt


def mats():
    return {
        "steel": material("Dark steel", (0.10, 0.10, 0.11), metal=0.7, rough=0.45),
        "rail": material("Rail steel", (0.30, 0.28, 0.26), metal=0.85, rough=0.5),
        "railhead": material("Rail head", (0.62, 0.62, 0.64), metal=1.0, rough=0.22),
        "polished": material("Rail polished", (0.85, 0.85, 0.88), metal=1.0, rough=0.08),
        "sleeper": concrete("Sleeper concrete", (0.55, 0.54, 0.51), 6.0),
        "clip": material("Rail clip", (0.06, 0.06, 0.06), metal=0.5, rough=0.5),
        "ballast": ballast_material(),
        "platform": concrete("Platform concrete", (0.48, 0.47, 0.45), 2.0),
        "coping": concrete("Coping", (0.70, 0.69, 0.66), 5.0),
        "yellow": material("Safety yellow", (0.92, 0.72, 0.04), rough=0.6),
        "column": material("Canopy green", (0.10, 0.20, 0.16), metal=0.4, rough=0.5),
        "roof": material("Canopy roof", (0.30, 0.31, 0.32), metal=0.5, rough=0.45),
        "lamp": emissive("Canopy lamp", (1.0, 0.92, 0.75), 6.0),
        "wood": material("Bench wood", (0.36, 0.20, 0.10), rough=0.6),
        "mast": material("Mast grey", (0.38, 0.40, 0.41), metal=0.6, rough=0.5),
        "wire": material("Contact wire", (0.55, 0.36, 0.20), metal=1.0, rough=0.3),
        "stop_red": material("Stop red", (0.62, 0.05, 0.03), metal=0.3, rough=0.45),
        "beam": striped("Buffer beam stripes", (0.9, 0.9, 0.88), (0.62, 0.05, 0.03)),
        "chrome": material("Chrome", (0.9, 0.9, 0.92), metal=1.0, rough=0.08),
        "rubber": material("Buffer head black", (0.03, 0.03, 0.03), metal=0.4, rough=0.35),
        "shoe": material("Shoe steel", (0.16, 0.17, 0.18), metal=0.8, rough=0.4),
        "bronze": material("Bronze insert", (0.72, 0.45, 0.18), metal=1.0, rough=0.3),
        "bolt": material("Bolt zinc", (0.62, 0.63, 0.60), metal=1.0, rough=0.35),
        "redlamp": emissive("End lamp red", (1.0, 0.05, 0.02), 9.0),
        "white": train_paint(),
        "blue": material("Train blue", (0.03, 0.12, 0.42), metal=0.2, rough=0.35),
        "front": material("Cab yellow", (0.95, 0.70, 0.04), metal=0.15, rough=0.4),
        "glass": cw.canopy_glass("Train glass"),
        "window": material("Window dark", (0.02, 0.025, 0.03), metal=0.4, rough=0.08),
        "door": material("Door grey", (0.20, 0.21, 0.23), metal=0.3, rough=0.4),
        "under": material("Underframe", (0.05, 0.05, 0.055), metal=0.4, rough=0.6),
        "bogie": material("Bogie", (0.07, 0.07, 0.075), metal=0.5, rough=0.5),
        "wheel": material("Wheel steel", (0.35, 0.34, 0.33), metal=0.9, rough=0.35),
        "headlight": emissive("Headlight", (1.0, 0.95, 0.85), 14.0),
        "taillight": emissive("Tail light", (1.0, 0.04, 0.02), 6.0),
        "screen": emissive("Cab screen", (0.25, 0.75, 1.0), 3.0),
        "cabin": material("Cab interior", (0.12, 0.13, 0.14), rough=0.6),
        "seat": material("Seat blue", (0.05, 0.09, 0.22), rough=0.7),
        "concourse": material("Concourse glass", (0.05, 0.08, 0.10), metal=0.6, rough=0.1),
        "brick": concrete("End wall", (0.42, 0.24, 0.17), 1.5, 0.4),
        "wall": concrete("Wall concrete", (0.58, 0.57, 0.54), 1.2, 0.5),
        "dust": _dust_material(),
        "asphalt": concrete("Asphalt", (0.11, 0.11, 0.12), 8.0, 0.3),
        "grass": concrete("Grass", (0.10, 0.22, 0.06), 4.0, 0.3),
        "lane": material("Lane white", (0.85, 0.85, 0.82), rough=0.6),
        "car_paint": material("Sedan blue", (0.05, 0.16, 0.38), metal=0.6, rough=0.25),
        "car_glass": cw.canopy_glass("Sedan glass"),
        "brake": emissive("Brake light", (1.0, 0.03, 0.02), 2.0),
        "tractor": material("Tractor yellow", (0.92, 0.62, 0.03), metal=0.2, rough=0.45),
        "marker": _marker_material(),
        "spark": material("Spark", (1.0, 0.72, 0.3), emission=14.0),
        "orange": (0.95, 0.38, 0.03),
    }


def _dust_material():
    """Concrete dust as a volume, not a surface: thick in the middle, thinning to nothing at the rim, clumpy. A see-through surface
    drew hard circles at full size wherever a puff cut into the train or the wall; a volume has no edge there. The object's colour
    (set per frame) scales the density, so a puff thins out as it spreads."""
    mt = bpy.data.materials.get("Dust")
    if mt is not None:
        return mt
    mt = bpy.data.materials.new("Dust")
    mt.use_nodes = True
    nt = mt.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = (0.82, 0.79, 0.74, 1)
    vol.inputs["Anisotropy"].default_value = 0.25
    tc = nt.nodes.new("ShaderNodeTexCoord")
    r = nt.nodes.new("ShaderNodeVectorMath")
    r.operation = "LENGTH"
    nt.links.new(tc.outputs["Object"], r.inputs[0])
    rim = nt.nodes.new("ShaderNodeMapRange")                       # 1 inside 0.3 of the radius, 0 at the rim, smooth between
    rim.interpolation_type = "SMOOTHSTEP"
    rim.inputs["From Min"].default_value, rim.inputs["From Max"].default_value = 1.0, 0.3
    nt.links.new(r.outputs["Value"], rim.inputs["Value"])
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = 2.2
    n.inputs["Detail"].default_value = 5
    n.inputs["Roughness"].default_value = 0.6
    nt.links.new(tc.outputs["Object"], n.inputs["Vector"])
    clump = nt.nodes.new("ShaderNodeMapRange")
    clump.inputs["From Min"].default_value, clump.inputs["From Max"].default_value = 0.35, 0.72
    clump.inputs["To Min"].default_value, clump.inputs["To Max"].default_value = 0.1, 1.0
    nt.links.new(n.outputs["Fac"], clump.inputs["Value"])
    oi = nt.nodes.new("ShaderNodeObjectInfo")
    d1 = nt.nodes.new("ShaderNodeMath")
    d1.operation = "MULTIPLY"
    nt.links.new(rim.outputs["Result"], d1.inputs[0])
    nt.links.new(clump.outputs["Result"], d1.inputs[1])
    d2 = nt.nodes.new("ShaderNodeMath")
    d2.operation = "MULTIPLY"
    nt.links.new(d1.outputs[0], d2.inputs[0])
    nt.links.new(oi.outputs["Color"], d2.inputs[1])
    nt.links.new(d2.outputs[0], vol.inputs["Density"])
    glow = nt.nodes.new("ShaderNodeMath")                            # light from the many bounces inside a thick cloud
    glow.operation = "MULTIPLY"
    glow.inputs[1].default_value = 0.05
    nt.links.new(d2.outputs[0], glow.inputs[0])
    vol.inputs["Emission Color"].default_value = (0.80, 0.78, 0.74, 1)
    nt.links.new(glow.outputs[0], vol.inputs["Emission Strength"])
    nt.links.new(vol.outputs["Volume"], out.inputs["Volume"])
    return mt


def _marker_material():
    """The slide's length on the track: a see-through safety-yellow sheet."""
    mt = bpy.data.materials.get("Slide marker")
    if mt is not None:
        return mt
    mt = bpy.data.materials.new("Slide marker")
    mt.use_nodes = True
    nt = mt.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (1.0, 0.78, 0.05, 1)
    em.inputs["Strength"].default_value = 2.6
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = 0.6
    nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
    nt.links.new(em.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mt


# ---------------------------------------------------------------------------------------------------------------------- track
RAIL_SECTION = [(-0.075, -0.172), (0.075, -0.172), (0.075, -0.160), (0.010, -0.150), (0.008, -0.052), (0.036, -0.040),
                (0.036, 0.0), (-0.036, 0.0), (-0.036, -0.040), (-0.008, -0.052), (-0.010, -0.150), (-0.075, -0.160)]


def _extrude(name, section, y0, y1, x_c, mat, z0=0.0):
    """A closed x-z section swept straight along y (end caps included)."""
    n = len(section)
    verts = [(x_c + x, y0, z0 + z) for x, z in section] + [(x_c + x, y1, z0 + z) for x, z in section]
    faces = [tuple(range(n))[::-1], tuple(range(n, 2 * n))]
    faces += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    return _mesh(name, verts, faces, mat)


def track(m, name, x_c, y0, y1, sleepers=True):
    obs = []
    for sx in (-1, 1):
        x = x_c + sx * RAIL_X
        obs.append(_extrude(f"{name} rail {sx}", RAIL_SECTION, y0, y1, x, m["rail"]))
        obs.append(cube(f"{name} rail head {sx}", (x, (y0 + y1) / 2, -0.004), (0.073, y1 - y0, 0.009), m["railhead"]))
    if sleepers:
        verts, faces = [], []
        cverts, cfaces = [], []

        def box(vs, fs, cx, cy, cz, sx_, sy_, sz_):
            k = len(vs)
            for dz in (-sz_ / 2, sz_ / 2):
                for dy in (-sy_ / 2, sy_ / 2):
                    for dx in (-sx_ / 2, sx_ / 2):
                        vs.append((cx + dx, cy + dy, cz + dz))
            fs += [(k, k + 1, k + 3, k + 2), (k + 4, k + 6, k + 7, k + 5), (k, k + 4, k + 5, k + 1),
                   (k + 2, k + 3, k + 7, k + 6), (k, k + 2, k + 6, k + 4), (k + 1, k + 5, k + 7, k + 3)]

        y = y0 + 0.3
        while y < y1:
            box(verts, faces, x_c, y, -0.172 - 0.11, 2.6, 0.26, 0.22)
            for sx in (-1, 1):
                for side in (-1, 1):
                    box(cverts, cfaces, x_c + sx * RAIL_X + side * 0.085, y, -0.150, 0.05, 0.14, 0.05)
            y += 0.6
        obs.append(_mesh(f"{name} sleepers", verts, faces, m["sleeper"]))
        obs.append(_mesh(f"{name} clips", cverts, cfaces, m["clip"]))
    bed = [(x_c - 2.2, y0, -0.62), (x_c + 2.2, y0, -0.62), (x_c + 1.6, y0, -0.36), (x_c - 1.6, y0, -0.36)]
    bed2 = [(x, y1, z) for x, _, z in bed]
    obs.append(_mesh(f"{name} ballast", bed + bed2, [(0, 1, 2, 3)[::-1], (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)], m["ballast"]))
    return obs


# ---------------------------------------------------------------------------------------------------------------------- station
def passenger(k, colour, rng):
    """A waiting passenger: the crew figure's body without helmet, vest and tape, with hair."""
    root, torso = cw.crew_member(500 + k, colour)
    for ob in list(root.children_recursive):
        if any(w in ob.name for w in ("cranial", "goggles", "Crew ear", "tape", "vest")):
            bpy.data.objects.remove(ob)
    hair = _sphere(f"Hair {k}", 0.11, (0, -0.01, 0.74), material(f"Hair {k % 3}", ((0.05, 0.03, 0.02), (0.25, 0.15, 0.07), (0.6, 0.5, 0.3))[k % 3], rough=0.8),
                   scale=(1.0, 1.05, 0.7))
    hair.parent = torso
    torso.rotation_euler = (rng.uniform(-0.05, 0.05), 0.0, 0.0)
    return root


def station(m, seed=36):
    rng = random.Random(seed)
    obs, people = [], []
    y0, y1 = -150.0, 3.0
    x0, x1 = PLATFORM_EDGE, -10.0
    obs.append(cube("Platform", ((x0 + x1) / 2, (y0 + y1) / 2, PLATFORM_Z / 2 - 0.3), (x0 - x1, y1 - y0, PLATFORM_Z + 0.6), m["platform"]))
    obs.append(cube("Platform coping", (x0 - 0.3, (y0 + y1) / 2, PLATFORM_Z + 0.01), (0.62, y1 - y0, 0.04), m["coping"]))
    obs.append(cube("Safety line", (x0 - 0.68, (y0 + y1) / 2, PLATFORM_Z + 0.012), (0.1, y1 - y0, 0.03), m["yellow"]))
    obs.append(cube("Tactile strip", (x0 - 0.95, (y0 + y1) / 2, PLATFORM_Z + 0.008), (0.4, y1 - y0, 0.02), material("Tactile", (0.75, 0.62, 0.20), rough=0.8)))
    obs.append(cube("Platform end ramp", ((x0 + x1) / 2, y1 + 1.5, PLATFORM_Z / 2 - 0.3), (x0 - x1, 3.0, PLATFORM_Z + 0.4), m["platform"]))
    # canopy: columns down the middle of the platform, cantilevered roof with lights
    y = y0 + 4.0
    k = 0
    while y < y1 - 2:
        obs.append(cube(f"Canopy column {k}", (-5.6, y, PLATFORM_Z + 2.6), (0.28, 0.28, 5.2), m["column"]))
        obs.append(cube(f"Canopy arm {k}", (-5.0, y, PLATFORM_Z + 5.05), (6.6, 0.22, 0.32), m["column"]))
        obs.append(cube(f"Canopy lamp {k}", (-3.2, y + 4.5, PLATFORM_Z + 4.75), (0.18, 2.4, 0.06), m["lamp"]))
        if k % 2 == 0:
            for sx in (-0.9, 0.9):
                obs.append(cube(f"Bench seat {k} {sx}", (-7.2, y + sx * 1.6, PLATFORM_Z + 0.45), (0.55, 1.6, 0.06), m["wood"]))
                obs.append(cube(f"Bench back {k} {sx}", (-7.5, y + sx * 1.6, PLATFORM_Z + 0.75), (0.06, 1.6, 0.5), m["wood"]))
        k += 1
        y += 9.0
    obs.append(cube("Canopy roof", (-5.0, (y0 + y1) / 2 + 1.0, PLATFORM_Z + 5.35), (7.4, y1 - y0 - 2.0, 0.22), m["roof"]))
    obs.append(cube("Canopy fascia", (-1.4, (y0 + y1) / 2 + 1.0, PLATFORM_Z + 5.15), (0.12, y1 - y0 - 2.0, 0.6), m["column"]))
    jerseys = [(0.12, 0.14, 0.18), (0.55, 0.08, 0.10), (0.75, 0.72, 0.68), (0.10, 0.28, 0.20), (0.32, 0.22, 0.45), (0.80, 0.55, 0.20)]
    for i in range(14):
        p = passenger(i, jerseys[i % len(jerseys)], rng)
        p.location = (rng.uniform(-8.5, -3.0), rng.uniform(-95.0, -4.0), PLATFORM_Z)
        p.rotation_euler = (0, 0, rng.uniform(-0.6, 0.6) + (math.pi if rng.random() < 0.3 else 0.0))
        people.append(p)
    # the concourse beyond the end wall
    obs.append(cube("End wall", (0.5, 35.0, 1.6), (22.0, 1.0, 4.4), m["brick"]))
    obs.append(cube("Concourse", (0.5, 46.0, 7.0), (40.0, 20.0, 14.0), m["concourse"]))
    for i in range(-9, 10):
        obs.append(cube(f"Concourse mullion {i}", (0.5 + i * 2.1, 35.9, 7.0), (0.12, 0.2, 14.0), m["mast"]))
    for j in range(1, 6):
        obs.append(cube(f"Concourse floor {j}", (0.5, 35.9, j * 2.6), (40.0, 0.25, 0.14), m["mast"]))
    obs.append(cube("Concourse roof", (0.5, 46.0, 14.3), (42.0, 22.0, 0.6), m["roof"]))
    return obs, people


def overhead(m, xs=(0.0, ADJ_X), y0=-176.0, y1=30.0):
    """Masts beside the right track with cantilevers over both, a contact wire and a messenger wire over each track, droppers."""
    obs = []
    y = y0 + 2.0
    k = 0
    while y < y1:
        obs.append(cube(f"Mast {k}", (7.6, y, 3.3), (0.32, 0.22, 7.4), m["mast"]))
        obs.append(cube(f"Cantilever {k}", (3.5, y, 6.6), (8.6, 0.1, 0.12), m["mast"]))
        y += 27.0
        k += 1
    for i, x in enumerate(xs):
        obs.append(cube(f"Contact wire {i}", (x, (y0 + y1) / 2, 5.20), (0.014, y1 - y0, 0.014), m["wire"]))
        obs.append(cube(f"Messenger wire {i}", (x, (y0 + y1) / 2, 6.30), (0.016, y1 - y0, 0.016), m["wire"]))
        verts, faces = [], []
        yy = y0 + 4.0
        while yy < y1:
            kv = len(verts)
            verts += [(x - 0.004, yy, 5.21), (x + 0.004, yy, 5.21), (x + 0.004, yy, 6.29), (x - 0.004, yy, 6.29)]
            faces.append((kv, kv + 1, kv + 2, kv + 3))
            yy += 4.5
        obs.append(_mesh(f"Droppers {i}", verts, faces, m["wire"]))
    return obs


# ---------------------------------------------------------------------------------------------------------------------- the stop
def buffer_stop(m, name="Stop"):
    """Root at the frame's front plate (x = 0 on the track's centre line, z = 0 at the rails' top), facing -y (the train)."""
    root = bpy.data.objects.new(f"{name} root", None)
    bpy.context.collection.objects.link(root)
    frame, buffers, plungers, shoes, nuts = [], [], [], [], []

    def add(ob, lst):
        ob.parent = root
        lst.append(ob)
        return ob

    add(_rbox(f"{name} buffer beam", (0.0, 0.15, 1.07), (2.7, 0.3, 0.62), m["beam"], 0.02), frame)
    add(_rbox(f"{name} beam back", (0.0, 0.42, 1.07), (2.6, 0.24, 0.5), m["stop_red"], 0.02), frame)
    for sx in (-1, 1):
        x = sx * RAIL_X
        add(_rbox(f"{name} sole beam {sx}", (x, 2.15, 0.2), (0.2, 4.3, 0.22), m["stop_red"], 0.015), frame)
        add(_rbox(f"{name} post {sx}", (x, 0.3, 0.72), (0.22, 0.22, 0.95), m["stop_red"], 0.015), frame)
        strut = add(_rbox(f"{name} strut {sx}", (x, 1.85, 0.75), (0.18, 3.45, 0.16), m["stop_red"], 0.015), frame)
        strut.rotation_euler = (-math.atan2(1.0, 3.2), 0.0, 0.0)          # high at the beam, low at the back of the sole beam
        add(_rbox(f"{name} gusset {sx}", (x, 0.55, 0.45), (0.06, 0.6, 0.5), m["stop_red"], 0.01), frame)
        # the hydraulic buffer: housing on the beam, chrome plunger, black head
        bx = sx * BUFFER_X
        add(_cyl(f"{name} buffer housing {sx}", 0.19, 0.42, (bx, -0.21, BUFFER_Z), m["stop_red"], rot=(math.pi / 2, 0, 0), verts=32), buffers)
        add(_cyl(f"{name} housing flange {sx}", 0.26, 0.05, (bx, -0.02, BUFFER_Z), m["steel"], rot=(math.pi / 2, 0, 0), verts=32), buffers)
        pl = bpy.data.objects.new(f"{name} plunger {sx}", None)
        bpy.context.collection.objects.link(pl)
        pl.parent = root
        pl.location = (bx, 0.0, BUFFER_Z)
        plungers.append(pl)
        for ob in (_cyl(f"{name} plunger rod {sx}", 0.12, 0.62, (0.0, -0.62, 0.0), m["chrome"], rot=(math.pi / 2, 0, 0), verts=32),
                   _cyl(f"{name} buffer head {sx}", 0.24, 0.07, (0.0, -0.965, 0.0), m["rubber"], rot=(math.pi / 2, 0, 0), verts=40),
                   _cyl(f"{name} head rim {sx}", 0.26, 0.03, (0.0, -0.93, 0.0), m["steel"], rot=(math.pi / 2, 0, 0), verts=40)):
            ob.parent = pl
            buffers.append(ob)
        # four friction shoes on this rail: jaws hugging the rail head, bronze inserts pressed on its sides by two through-bolts
        # just above the head (squeezing the jaws together), a top plate the frame's sole beam rests on
        for k, y in enumerate(SHOE_Y):
            parts = [_rbox(f"{name} shoe plate {sx} {k}", (x, y, 0.075), (0.21, 0.46, 0.03), m["shoe"], 0.008)]
            for side in (-1, 1):
                parts.append(_rbox(f"{name} shoe jaw {sx} {k} {side}", (x + side * 0.072, y, 0.0075), (0.055, 0.46, 0.105), m["shoe"], 0.008))
                parts.append(cube(f"{name} shoe insert {sx} {k} {side}", (x + side * 0.0405, y, -0.02), (0.008, 0.42, 0.04), m["bronze"]))
            for j, dy in enumerate((-0.13, 0.13)):
                parts.append(_cyl(f"{name} bolt {sx} {k} {j}", 0.016, 0.27, (x, y + dy, 0.032), m["bolt"], rot=(0, math.pi / 2, 0), verts=12))
                for side in (-1, 1):
                    nut = _cyl(f"{name} nut {sx} {k} {j} {side}", 0.03, 0.028, (x + side * 0.113, y + dy, 0.032), m["bolt"], rot=(0, math.pi / 2, 0), verts=6, smooth=False)
                    nuts.append(nut)
                    parts.append(nut)
            for ob in parts:
                add(ob, shoes)
    for y in (1.6, 3.2):
        add(_rbox(f"{name} cross tie {y}", (0.0, y, 0.33), (1.7, 0.16, 0.14), m["stop_red"], 0.01), frame)
    add(_cyl(f"{name} lamp post", 0.04, 0.85, (0.0, 0.42, 1.75), m["steel"], verts=12), frame)
    add(_rbox(f"{name} lamp box", (0.0, 0.38, 2.24), (0.3, 0.22, 0.3), m["steel"], 0.02), frame)
    add(_cyl(f"{name} lamp lens", 0.1, 0.04, (0.0, 0.26, 2.24), m["redlamp"], rot=(math.pi / 2, 0, 0), verts=24), frame)
    return {"root": root, "frame": frame, "buffers": buffers, "plungers": plungers, "shoes": shoes, "nuts": nuts,
            "parts": frame + buffers + shoes}


def fixed_stop(m, x_c, y):
    """The old fixed stop on the adjacent track: a sleeper-built frame with two sprung buffers."""
    obs = [_rbox("Old stop beam", (x_c, y + 0.2, 1.07), (2.6, 0.4, 0.55), striped("Old beam", (0.95, 0.85, 0.05), (0.05, 0.05, 0.05)), 0.02),
           _rbox("Old stop block", (x_c, y + 1.4, 0.5), (2.4, 2.0, 1.2), m["wall"], 0.04)]
    for sx in (-1, 1):
        obs.append(_cyl(f"Old buffer {sx}", 0.2, 0.5, (x_c + sx * BUFFER_X, y - 0.25, BUFFER_Z), m["steel"], rot=(math.pi / 2, 0, 0), verts=24))
    return obs


# ---------------------------------------------------------------------------------------------------------------------- the train
def _car_body(m, name, length, cab_front=False, cab_rear=False):
    """One car, local frame: y from -length to 0 (the front end at 0), x across, z up from the rails' top."""
    parts = []
    w = CAR_W
    prof = []
    for i in range(9):                                   # rounded roof
        a = math.pi * i / 8
        prof.append((0.5 * w * math.cos(a) * 0.96, ROOF_Z - 0.32 + 0.32 * math.sin(a)))
    prof = [(w / 2, BODY_Z0 + 0.15), (w / 2, ROOF_Z - 0.32)] + prof[1:-1] + [(-w / 2, ROOF_Z - 0.32), (-w / 2, BODY_Z0 + 0.15),
                                                                            (-w / 2 + 0.12, BODY_Z0), (w / 2 - 0.12, BODY_Z0)]
    y_front = -CAB_LEN if cab_front else -0.05             # a cab end is built open by _cab_end (desk, seat, driver inside)
    y_back = -length + (CAB_LEN if cab_rear else 0.05)
    parts.append(_extrude(f"{name} body", [(x, z) for x, z in prof], y_back, y_front, 0.0, m["white"]))
    for sx in (-1, 1):                                   # window band, blue stripe, doors, under-skirt
        x = sx * (w / 2 + 0.004)
        parts.append(cube(f"{name} windows {sx}", (x, (y_front + y_back) / 2, 2.32), (0.01, (y_front - y_back) - 0.6, 0.62), m["window"]))
        parts.append(cube(f"{name} stripe {sx}", (x + sx * 0.002, (y_front + y_back) / 2, 1.72), (0.01, (y_front - y_back) - 0.2, 0.2), m["blue"]))
        for i in range(int((y_front - y_back) // 1.6)):
            yy = y_back + 0.8 + i * 1.6
            parts.append(cube(f"{name} pillar {sx} {i}", (x + sx * 0.003, yy, 2.32), (0.01, 0.09, 0.64), m["white"]))
        for f in (0.25, 0.75):
            yy = y_back + f * (y_front - y_back)
            parts.append(cube(f"{name} door {sx} {f}", (x + sx * 0.006, yy, 2.05), (0.012, 1.3, 2.0), m["door"]))
            parts.append(cube(f"{name} door window {sx} {f}", (x + sx * 0.01, yy, 2.45), (0.01, 1.1, 0.75), m["window"]))
            for e in (-1, 1):
                parts.append(cube(f"{name} door edge {sx} {f} {e}", (x + sx * 0.012, yy + e * 0.67, 2.05), (0.012, 0.05, 2.0), m["front"]))
        parts.append(cube(f"{name} skirt {sx}", (sx * (w / 2 - 0.08), (y_front + y_back) / 2, 0.82), (0.05, (y_front - y_back) - 6.5, 0.5), m["under"]))
    for i, yy in enumerate((y_back + 0.35 * (y_front - y_back), y_back + 0.62 * (y_front - y_back))):
        parts.append(_rbox(f"{name} equipment {i}", (0.0, yy, 0.82), (2.2, 3.2, 0.5), m["under"], 0.03))
    parts.append(_rbox(f"{name} roof unit", (0.0, (y_front + y_back) / 2, ROOF_Z + 0.12), (1.6, 3.6, 0.3), m["roof"], 0.04))
    wheels = []
    for b, yb in enumerate((y_back + 3.4, y_front - 3.4)):
        parts.append(_rbox(f"{name} bogie {b}", (0.0, yb, 0.55), (2.1, 3.0, 0.32), m["bogie"], 0.03))
        for sx in (-1, 1):
            parts.append(_cyl(f"{name} spring {b} {sx}", 0.09, 0.3, (sx * 0.95, yb, 0.85), m["bogie"], verts=12))
            for ax in (-1.25, 1.25):
                wh = _cyl(f"{name} wheel {b} {sx} {ax}", 0.42, 0.12, (sx * RAIL_X, yb + ax, 0.42), m["wheel"], rot=(0, math.pi / 2, 0), verts=28)
                wheels.append(wh)
                parts.append(wh)
                parts.append(_cyl(f"{name} axlebox {b} {sx} {ax}", 0.1, 0.18, (sx * 1.0, yb + ax, 0.42), m["bogie"], rot=(0, math.pi / 2, 0), verts=12))
    return parts, wheels


def _cab_end(m, name, y_face, facing, lead=False):
    """A cab end. y_face: the buffer faces' y; facing +1 for the front (toward +y), -1 for the rear. Side profile (y back from the
    face, z): the yellow nose up to the sill, the windscreen sloping back to the roof, the cab roof, the cab's side panels."""
    parts = []
    s = facing
    Y = lambda d: y_face - s * d                                          # noqa: E731  (d: distance back from the face)
    w = CAR_W / 2
    parts.append(_rbox(f"{name} nose", (0.0, Y(1.0), 1.47), (CAR_W - 0.05, 1.8, 0.87), m["front"], 0.12))
    parts.append(cube(f"{name} cab floor", (0.0, Y(2.2), 1.24), (CAR_W - 0.1, 2.2, 0.06), m["cabin"]))
    ws = [(-w + 0.1, Y(0.5), 1.92), (w - 0.1, Y(0.5), 1.92), (w - 0.12, Y(1.6), 3.62), (-w + 0.12, Y(1.6), 3.62)]
    parts.append(_mesh(f"{name} windscreen", ws, [(0, 1, 2, 3)], m["glass"]))
    for sx in (-1, 1):
        x = sx * (w - 0.02)
        verts = [(x, Y(d), z) for d, z in CAB_SIDE]
        parts.append(_mesh(f"{name} cab side {sx}", verts, [tuple(range(len(verts)))], m["white"]))        # white sides, yellow front mask
        parts.append(_mesh(f"{name} side window {sx}", [(x + sx * 0.006, Y(1.9), 2.2), (x + sx * 0.006, Y(3.0), 2.2), (x + sx * 0.006, Y(3.0), 3.0),
                                                       (x + sx * 0.006, Y(1.9), 3.0)], [(0, 1, 2, 3)], m["window"]))
        parts.append(cube(f"{name} cab stripe {sx}", (x + sx * 0.008, Y(2.4), 1.72), (0.01, 1.8, 0.2), m["blue"]))
        rail = cube(f"{name} screen pillar {sx}", (sx * (w - 0.1), Y(1.05), 2.77), (0.09, 0.07, 2.0), m["under"])
        rail.rotation_euler = (s * -math.atan2(1.1, 1.7), 0.0, 0.0)
        parts.append(rail)
    parts.append(_rbox(f"{name} roof cap", (0.0, Y(2.45), ROOF_Z - 0.1), (CAR_W - 0.04, 1.75, 0.22), m["front"], 0.1))
    parts.append(cube(f"{name} screen top", (0.0, Y(1.6), 3.64), (CAR_W - 0.24, 0.08, 0.06), m["under"]))
    parts.append(cube(f"{name} sill", (0.0, Y(0.5), 1.91), (CAR_W - 0.2, 0.1, 0.06), m["under"]))
    parts.append(cube(f"{name} wiper", (0.35, Y(0.62), 2.1), (0.7, 0.02, 0.02), m["under"]))
    for sx in (-1, 1):                                   # side buffers and lamps
        parts.append(_cyl(f"{name} buffer body {sx}", 0.17, 0.5, (sx * BUFFER_X, Y(0.3), BUFFER_Z), m["under"], rot=(math.pi / 2, 0, 0), verts=24))
        parts.append(_cyl(f"{name} buffer face {sx}", 0.22, 0.05, (sx * BUFFER_X, Y(0.025), BUFFER_Z), m["chrome"], rot=(math.pi / 2, 0, 0), verts=32))
        parts.append(_cyl(f"{name} headlight {sx}", 0.11, 0.04, (sx * 0.95, Y(0.08), 1.62), m["headlight"] if s > 0 else m["taillight"], rot=(math.pi / 2, 0, 0), verts=24))
        parts.append(_cyl(f"{name} marker {sx}", 0.05, 0.03, (sx * 1.05, Y(0.1), 1.82), m["headlight"] if s > 0 else m["taillight"], rot=(math.pi / 2, 0, 0), verts=16))
    parts.append(_rbox(f"{name} coupler cover", (0.0, Y(0.15), 0.95), (0.7, 0.3, 0.35), m["under"], 0.05))
    return parts


def train(m, name="Train", cars=6, bumper=True):
    """Root at the front buffer faces (y = 0), the cars stretching back along -y. Returns the parts the renderer moves or lights."""
    root = bpy.data.objects.new(f"{name} root", None)
    bpy.context.collection.objects.link(root)
    parts, wheels = [], []
    y = 0.0
    for c in range(cars):
        front, rear = c == 0, c == cars - 1
        body, wh = _car_body(m, f"{name} car {c}", CAR_LEN, cab_front=front, cab_rear=rear)
        for ob in body:
            ob.location.y += y
        parts += body
        wheels += wh
        if front:
            parts += _cab_end(m, f"{name} front", y, +1, lead=True)
        if rear:
            parts += _cab_end(m, f"{name} rear", y - CAR_LEN, -1)
        if not rear:
            parts.append(_rbox(f"{name} gangway {c}", (0.0, y - CAR_LEN - CAR_GAP / 2, 2.25), (1.6, CAR_GAP + 0.1, 2.4), m["under"], 0.05))
        if c in (1, cars - 2):                            # pantographs
            yp = y - CAR_LEN / 2
            parts.append(_rbox(f"{name} pan base {c}", (0.0, yp, ROOF_Z + 0.05), (1.2, 1.6, 0.12), m["mast"], 0.02))
            for k, (a, L) in enumerate(((0.75, 1.6), (-0.75, 1.6))):
                arm = cube(f"{name} pan arm {c} {k}", (0.0, yp + 0.0, ROOF_Z + 0.75), (0.05, L, 0.05), m["mast"])
                arm.rotation_euler = (a, 0.0, 0.0)
                parts.append(arm)
            parts.append(cube(f"{name} pan head {c}", (0.0, yp, 5.18), (1.7, 0.3, 0.04), m["mast"]))
        y -= CAR_LEN + CAR_GAP
    # the driver's cab: desk, screens, controller, seat; Bumper at the controls
    cab = [_rbox(f"{name} desk", (-0.15, -1.35, 1.85), (2.3, 0.7, 0.32), m["cabin"], 0.04),
           cube(f"{name} cab back wall", (0.0, -3.28, 2.5), (2.7, 0.06, 2.5), m["cabin"])]
    for k, x in enumerate((-0.75, -0.2, 0.35)):
        sc = cube(f"{name} screen {k}", (x, -1.15, 2.12), (0.42, 0.03, 0.26), m["screen"])
        sc.rotation_euler = (-0.5, 0.0, 0.0)
        cab.append(sc)
    cab.append(_cyl(f"{name} controller", 0.03, 0.22, (0.35, -1.55, 2.1), m["chrome"], verts=12))
    cab += [_rbox(f"{name} seat base", (-0.45, -2.3, 1.62), (0.6, 0.6, 0.12), m["seat"], 0.04),
            _rbox(f"{name} seat back", (-0.45, -2.65, 2.15), (0.6, 0.12, 0.9), m["seat"], 0.04)]
    parts += cab
    for ob in parts:
        if ob.parent is None:
            ob.parent = root
    out = {"root": root, "parts": parts, "wheels": wheels, "nose": [p for p in parts if p.name.startswith(f"{name} front")]}
    if bumper:
        d = dummy.build("Bumper")
        d["root"].parent = root
        d["root"].location = (-0.45, -2.25, 1.75)
        d["root"].scale = (0.9, 0.9, 0.9)
        out["bumper"] = d
        bpy.ops.object.light_add(type="POINT", location=(0.2, -1.6, 3.2))
        light = bpy.context.object
        light.parent = root
        light.data.energy = 0.0
        light.data.shadow_soft_size = 0.5
        out["cab_light"] = light
    return out


# ---------------------------------------------------------------------------------------------------------------------- comparisons
def wall(m):
    obs = [_rbox("Solid wall", (0.0, 1.6, 1.1), (3.1, 3.2, 2.9), m["wall"], 0.04)]          # as wide as the track bed
    rng = random.Random(3636)
    debris, dust = [], []
    for k in range(46):
        s = rng.uniform(0.05, 0.16)
        ob = cube(f"Debris {k}", (0, 0, -40), (s, s * rng.uniform(0.6, 1.4), s * rng.uniform(0.5, 1.2)), m["wall"])
        ob["v"] = (rng.uniform(-3.5, 3.5), rng.uniform(-4.5, -0.5), rng.uniform(1.0, 5.5))
        ob["at"] = (rng.uniform(-1.3, 1.3), rng.uniform(-0.1, 0.1), rng.uniform(0.8, 2.6))
        ob["spin"] = (rng.uniform(-9, 9), rng.uniform(-9, 9), rng.uniform(-9, 9))
        debris.append(ob)
    for k in range(9):
        ob = _sphere(f"Dust {k}", 1.0, (0, 0, -40), m["dust"])
        ob["at"] = (rng.uniform(-1.5, 1.2), rng.uniform(-0.2, 0.5), rng.uniform(1.6, 3.2))   # off the contact, rising over the wall
        ob["grow"] = rng.uniform(0.7, 1.3)
        dust.append(ob)
    return {"wall": obs, "debris": debris, "dust": dust}


def _side_top(d):
    """The cab side's top edge at d back from the face, over the folding zone (the sill, then the windscreen line)."""
    pts = CAB_SIDE[1:4]
    for (d0, z0), (d1, z1) in zip(pts, pts[1:]):
        if d0 <= d <= d1:
            return z0 + (z1 - z0) * (d - d0) / (d1 - d0)
    raise ValueError(d)


def wreck_sides(m):
    """The wall what-if's wreck: the lead cab's two sides rebuilt as one mesh each, a fixed back part and FOLD strips that share
    their hinge lines, so they fold like an accordion when the front crushes. Flat they are exactly the sides of _cab_end (the
    renderer swaps them in for the wall shot only). Vertices in the train's frame. Returns [(object, [(d, z) per vertex], side)]."""
    back, front, n = sm.FOLD
    w = (back - front) / n
    edges = [back - k * w for k in range(n + 1)]
    out = []
    for sx in (-1, 1):
        x0 = sx * (CAR_W / 2 - 0.02)
        dz = []

        def vert(d, z):
            dz.append((d, z))
            return len(dz) - 1

        bottom = [vert(e, 1.05) for e in edges]
        top = [vert(e, _side_top(e)) for e in edges]
        rest = [vert(d, z) for d, z in CAB_SIDE if d > back]
        faces = [[bottom[0], top[0]] + rest]
        for k in range(n):
            kinks = [vert(d, z) for d, z in CAB_SIDE[1:4] if edges[k + 1] < d < edges[k]]
            faces.append([bottom[k + 1], top[k + 1]] + kinks + [top[k], bottom[k]])
        ob = _mesh(f"Wreck cab side {sx}", [(x0, -d, z) for d, z in dz], faces, m["white"])
        out.append((ob, dz, sx))
    return out


def fold_sides(sides, crush):
    """Pose wreck_sides for a crush (m): the back part stays, the strips zig-zag out and in from the back hinge forward."""
    back, front, n = sm.FOLD
    w = (back - front) / n
    th = sm.fold_angles(crush)
    for ob, dz, sx in sides:
        x0 = sx * (CAR_W / 2 - 0.02)
        hinges = [(x0, -back)]
        for k in range(n):
            hx, hy = hinges[-1]
            o = 1.0 if k % 2 == 0 else -0.35                 # out, then back in a little (the skin buckles mostly outward)
            hinges.append((hx + sx * o * w * math.sin(th[k]), hy + w * math.cos(th[k])))
        co = []
        for d, z in dz:
            if d >= back - 1e-9:
                co += [x0, -d, z]
                continue
            k = min(n - 1, int((back - d) / w + 1e-9))
            hx, hy = hinges[k]
            t = (back - k * w) - d
            o = 1.0 if k % 2 == 0 else -0.35
            co += [hx + sx * o * t * math.sin(th[k]), hy + t * math.cos(th[k]), z]
        ob.data.vertices.foreach_set("co", co)
        ob.data.update()
    return th


def glass_shards(m, count=28, seed=3637):
    """Windscreen shards for the wall what-if: small bright slivers, each with a start near the windscreen's foot (train frame),
    a launch velocity (out, back and up) and a spin."""
    rng = random.Random(seed)
    shard = material("Glass shard", (0.78, 0.86, 0.92), metal=0.7, rough=0.04)
    out = []
    for k in range(count):
        a, b = rng.uniform(0.03, 0.08), rng.uniform(0.02, 0.06)
        ob = _mesh(f"Shard {k}", [(-a, 0.0, -b), (a, 0.0, -b * 0.4), (rng.uniform(-a, a), 0.0, b)], [(0, 1, 2)], shard)
        ob.location = (0, 0, -40)
        sx = rng.choice((-1, 1))
        ob["at"] = (sx * rng.uniform(0.2, 1.25), rng.uniform(-0.75, -0.45), rng.uniform(1.95, 2.5))
        ob["v"] = (sx * rng.uniform(0.6, 3.2), rng.uniform(-3.2, -0.6), rng.uniform(0.8, 3.8))
        ob["spin"] = (rng.uniform(-25, 25), rng.uniform(-25, 25), rng.uniform(-25, 25))
        out.append(ob)
    return out


def cracked(base, name="Cracked windscreen"):
    """The windscreen after the what-if's hit: the same glass, crazed white along Voronoi cell edges."""
    mt = bpy.data.materials.get(name)
    if mt is not None:
        return mt
    mt = base.copy()
    mt.name = name
    nt = mt.node_tree
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    src = out.inputs["Surface"].links[0].from_socket
    tc = nt.nodes.new("ShaderNodeTexCoord")
    warp = nt.nodes.new("ShaderNodeTexNoise")                       # wavy cracks, not a mosaic of straight cell edges
    warp.inputs["Scale"].default_value = 3.0
    warp.inputs["Detail"].default_value = 4
    nt.links.new(tc.outputs["Object"], warp.inputs["Vector"])
    bend = nt.nodes.new("ShaderNodeVectorMath")
    bend.operation = "MULTIPLY_ADD"
    bend.inputs[1].default_value = (0.12, 0.12, 0.12)
    nt.links.new(warp.outputs["Color"], bend.inputs[0])
    nt.links.new(tc.outputs["Object"], bend.inputs[2])
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.feature = "DISTANCE_TO_EDGE"
    vor.inputs["Scale"].default_value = 11.0
    nt.links.new(bend.outputs["Vector"], vor.inputs["Vector"])
    line = nt.nodes.new("ShaderNodeMapRange")
    line.inputs["From Min"].default_value, line.inputs["From Max"].default_value = 0.0, 0.018
    line.inputs["To Min"].default_value, line.inputs["To Max"].default_value = 1.0, 0.0
    nt.links.new(vor.outputs["Distance"], line.inputs["Value"])
    white = nt.nodes.new("ShaderNodeBsdfDiffuse")
    white.inputs["Color"].default_value = (0.86, 0.88, 0.9, 1)
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(line.outputs["Result"], mix.inputs["Fac"])
    nt.links.new(src, mix.inputs[1])
    nt.links.new(white.outputs["BSDF"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mt


CAR_ORIGIN = (2000.0, 0.0, 0.0)


def road_scene(m):
    """The comparison road, far from the station: asphalt, lane lines, verges, a hedge and trees behind."""
    ox, oy, oz = CAR_ORIGIN
    obs = [cube("Road", (ox, oy + 20, oz - 0.05), (8.0, 160.0, 0.1), m["asphalt"]),
           cube("Verge left", (ox - 14.0, oy + 20, oz - 0.08), (20.0, 160.0, 0.1), m["grass"]),
           cube("Verge right", (ox + 14.0, oy + 20, oz - 0.08), (20.0, 160.0, 0.1), m["grass"]),
           cube("Hedge", (ox - 7.5, oy + 20, oz + 1.0), (1.6, 160.0, 2.0), concrete("Hedge green", (0.05, 0.14, 0.04), 3.0, 0.6))]
    y = oy - 55
    while y < oy + 95:
        obs.append(cube(f"Lane dash {y:.0f}", (ox, y, oz + 0.002), (0.14, 3.0, 0.01), m["lane"]))
        y += 9.0
    for sx in (-1, 1):
        obs.append(cube(f"Edge line {sx}", (ox + sx * 3.7, oy + 20, oz + 0.002), (0.12, 160.0, 0.01), m["lane"]))
    rng = random.Random(77)
    leaf = concrete("Leaves", (0.06, 0.16, 0.05), 2.0, 0.6)
    bark = material("Bark", (0.18, 0.11, 0.06), rough=0.9)
    for k in range(18):
        x = ox - rng.uniform(10.0, 18.0)
        y = oy + rng.uniform(-40.0, 80.0)
        h = rng.uniform(5.0, 8.0)
        obs.append(_cyl(f"Trunk {k}", 0.18, h * 0.5, (x, y, h * 0.25), bark, verts=10))
        obs.append(_sphere(f"Crown {k}", h * 0.32, (x, y, h * 0.62), leaf, scale=(1.0, 1.0, 1.25)))
    return obs


def sedan(m):
    """A generic sedan, root at its centre on the ground, facing +y; a second dummy at the wheel (left-hand drive)."""
    root = bpy.data.objects.new("Sedan root", None)
    bpy.context.collection.objects.link(root)
    body = bpy.data.objects.new("Sedan body", None)            # pitches about the root when braking
    bpy.context.collection.objects.link(body)
    body.parent = root
    parts = [_rbox("Sedan lower", (0.0, 0.0, 0.62), (1.82, 4.6, 0.62), m["car_paint"], 0.12),
             _rbox("Sedan hood", (0.0, 1.45, 0.98), (1.76, 1.6, 0.14), m["car_paint"], 0.08),
             _rbox("Sedan trunk", (0.0, -1.75, 0.98), (1.76, 1.0, 0.14), m["car_paint"], 0.08),
             _rbox("Sedan roof", (0.0, -0.35, 1.48), (1.5, 1.6, 0.06), m["car_paint"], 0.04)]
    glass_house = _mesh("Sedan glass", [(-0.78, 0.65, 1.03), (0.78, 0.65, 1.03), (0.74, -1.3, 1.03), (-0.74, -1.3, 1.03),
                                        (-0.70, 0.40, 1.46), (0.70, 0.40, 1.46), (0.70, -1.1, 1.46), (-0.70, -1.1, 1.46)],
                        [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)], m["car_glass"])
    parts.append(glass_house)
    parts.append(cube("Sedan seat", (-0.38, -0.3, 0.62), (0.55, 0.55, 0.12), m["seat"]))
    parts.append(cube("Sedan seat back", (-0.38, -0.62, 0.98), (0.55, 0.1, 0.7), m["seat"]))
    parts.append(_cyl("Sedan wheel rim", 0.17, 0.04, (-0.38, 0.35, 1.0), m["under"], rot=(1.1, 0, 0), verts=24))
    for sx in (-1, 1):
        parts.append(cube(f"Sedan brake light {sx}", (sx * 0.72, -2.31, 0.85), (0.32, 0.03, 0.1), m["brake"]))
        parts.append(cube(f"Sedan headlight {sx}", (sx * 0.68, 2.31, 0.78), (0.32, 0.03, 0.1), m["headlight"]))
    for ob in parts:
        ob.parent = body
    wheels = []
    tyre = material("Tyre", (0.03, 0.03, 0.03), rough=0.8)
    for sx in (-1, 1):
        for sy in (-1.4, 1.4):
            wh = _cyl(f"Sedan tyre {sx} {sy}", 0.33, 0.22, (sx * 0.8, sy, 0.33), tyre, rot=(0, math.pi / 2, 0), verts=24)
            wh.parent = root
            wheels.append(wh)
    d = dummy.build("Bumper car")
    d["root"].parent = body
    d["root"].location = (-0.38, -0.25, 0.72)
    d["root"].scale = (0.9, 0.9, 0.9)
    belt = cube("Sedan belt", (-0.38, -0.12, 1.12), (0.06, 0.02, 0.7), material("Belt grey", (0.12, 0.12, 0.13), rough=0.7))
    belt.rotation_euler = (0.0, 0.55, 0.0)
    belt.parent = d["torso"]
    belt.location = (0.0, 0.11, 0.33)
    return {"root": root, "body": body, "parts": parts + wheels, "dummy": d, "wheels": wheels}


# ---------------------------------------------------------------------------------------------------------------------- afterwards
def tractor(m):
    """A yellow rail tractor with a push beam (facing -y, toward the stop), root at its push beam face."""
    root = bpy.data.objects.new("Tractor root", None)
    bpy.context.collection.objects.link(root)
    parts = [_rbox("Tractor body", (0.0, 2.4, 1.0), (2.3, 3.6, 1.2), m["tractor"], 0.08),
             _rbox("Tractor cab", (0.0, 3.2, 2.25), (1.9, 1.6, 1.4), m["tractor"], 0.08),
             cube("Tractor cab glass", (0.0, 2.38, 2.35), (1.6, 0.03, 0.9), m["window"]),
             _rbox("Tractor push beam", (0.0, 0.35, 1.06), (2.4, 0.3, 0.45), striped("Push beam", (0.95, 0.75, 0.04), (0.05, 0.05, 0.05), 3.0), 0.02),
             _cyl("Tractor beacon", 0.09, 0.12, (0.6, 3.6, 3.02), emissive("Beacon amber", (1.0, 0.5, 0.02), 8.0), verts=16)]
    for sx in (-1, 1):
        parts.append(_cyl(f"Tractor pad {sx}", 0.2, 0.06, (sx * BUFFER_X, 0.18, BUFFER_Z), m["rubber"], rot=(math.pi / 2, 0, 0), verts=24))
        for sy in (1.3, 3.4):
            parts.append(_cyl(f"Tractor wheel {sx} {sy}", 0.36, 0.12, (sx * RAIL_X, sy, 0.36), m["wheel"], rot=(0, math.pi / 2, 0), verts=24))
    for ob in parts:
        ob.parent = root
    return {"root": root, "parts": parts}


def wrench(m, name):
    """A long torque wrench: handle and head (the head at the local origin, handle along +x)."""
    root = bpy.data.objects.new(f"{name} root", None)
    bpy.context.collection.objects.link(root)
    for ob in (cube(f"{name} handle", (0.32, 0.0, 0.0), (0.62, 0.035, 0.035), m["bolt"]), _cyl(f"{name} head", 0.04, 0.05, (0.0, 0.0, 0.0), m["steel"], verts=12),
               cube(f"{name} grip", (0.58, 0.0, 0.0), (0.14, 0.045, 0.045), material("Grip red", (0.6, 0.05, 0.04), rough=0.6))):
        ob.parent = root
    return root


def fence(m):
    """A palisade fence beyond the platform's end, along the left of the slide zone, and a service path."""
    obs = [cube("Service path", (-4.2, 20.0, -0.36), (3.0, 28.0, 0.06), concrete("Path", (0.42, 0.41, 0.39), 4.0))]
    verts, faces = [], []
    y = 6.5
    while y < 34.0:
        k = len(verts)
        verts += [(-6.0, y, -0.36), (-6.0, y + 0.06, -0.36), (-6.0, y + 0.06, 1.6), (-6.0, y, 1.6)]
        faces.append((k, k + 1, k + 2, k + 3))
        y += 0.16
    obs.append(_mesh("Palisade", verts, faces, material("Fence green", (0.06, 0.16, 0.10), metal=0.4, rough=0.5)))
    for z in (0.2, 1.3):
        obs.append(cube(f"Fence rail {z}", (-6.0, 20.0, z), (0.05, 27.5, 0.06), material("Fence green", (0.06, 0.16, 0.10))))
    return obs


def sparks(m, n=90, seed=36):
    rng = random.Random(seed)
    obs = []
    for k in range(n):
        s = rng.uniform(0.018, 0.04)
        ob = cube(f"Spark {k}", (0, 0, -50), (s, s * 4.0, s), m["spark"])
        ob["phase"] = rng.random()
        ob["v"] = (rng.uniform(-2.0, 2.0), rng.uniform(-4.5, -1.0), rng.uniform(0.6, 3.0))
        ob["shoe"] = rng.randrange(8)
        obs.append(ob)
    return obs


def slide_marker(m, length):
    """The slide's length on the track: a see-through yellow sheet between the rails from the start mark, and bright bars at the
    start and the end marks."""
    sheet = cube("Slide sheet", (0.0, length / 2, 0.03), (2.6, length, 0.01), m["marker"])
    marks = [cube(f"Slide mark {k}", (0.0, y, 0.04), (3.6, 0.28, 0.03), emissive("Mark yellow", (1.0, 0.8, 0.1), 10.0)) for k, y in enumerate((0.0, length))]
    return [sheet] + marks


def polished_strips(m):
    """Bright strips on both rail heads where the shoes have slid (scaled per frame from the first shoe's start to its current
    position)."""
    return [cube(f"Polished {sx}", (sx * RAIL_X, 0.0, 0.0015), (0.07, 1.0, 0.004), m["polished"]) for sx in (-1, 1)]
