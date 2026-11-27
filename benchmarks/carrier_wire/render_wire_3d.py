"""EP.35 carrier arresting wire: 100 % 3D renderer (Blender, Cycles CPU), house style (golden light, depth of field), with the
channel's identity parts: Bumper the dummy at the controls, the x-ray reveal look, and (in assembly) the caption look.

The scene:
- An aircraft carrier at sea: flight deck, island, landing-area lines, four arresting wires across the deck on bow springs, deck
  sheaves at their ends.
- A generic navy fighter (not any real type) with its tailhook, landing gear and two engines, Bumper in the cockpit.
- Below deck, the arresting engine: purchase cables from the deck sheaves down to a fixed sheave set, a crosshead reeved to it, the
  ram driven into the oil cylinder, the valve and the line to the accumulator. It is hidden under the deck and seen in the x-ray
  shots, where everything else turns blueprint blue and the engine glows orange.
- The deck crew in green jerseys changing a worn wire.
Everything that moves comes from wire_motion. No text (the football field has lines, no numbers)."""
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
from benchmarks.carrier_wire import wire_motion as m  # noqa: E402
from benchmarks.carrier_wire import wire_timeline as tl  # noqa: E402
from benchmarks.identity import dummy, xray  # noqa: E402
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402

material, cube = base.material, base.cube
FRAME = (1080, 1920)
Y3 = tl.Y3
WY = m.wire_y()
DECK_Y = (-112.0, 222.0)
SEA_Z = -19.0
ENGINE_Z = -8.6
FIX_Y = Y3 - 6.0                 # fixed sheave set
CYL = (Y3 - 20.0, Y3 - 8.0)      # oil cylinder along y
CROSS0 = Y3 - 24.5               # crosshead at rest (moves toward +y by the ram travel)
VALVE_Y = Y3 - 7.4
ACC = (3.4, Y3 - 10.5)           # accumulator tank (x, y)
T_TD = -0.35                     # main wheels and hook on the deck
GLIDE = math.radians(3.5)
N_SPARK = 60


def arguments():
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--res-scale", type=float, default=0.5)
    p.add_argument("--samples", type=int, default=16)
    p.add_argument("--frames", default="0-0")
    p.add_argument("--list", default="")
    p.add_argument("--source", type=Path, default=None)
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return p.parse_args(argv)


def flat(ob):
    for poly in ob.data.polygons:
        poly.use_smooth = False
    return ob


def mesh_object(name, verts, faces, mat):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(mat)
    return flat(ob)


def cyl(name, r, depth, loc, mat, rot=(0.0, 0.0, 0.0), verts=24):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth, location=loc, rotation=rot)
    ob = bpy.context.object
    ob.name = name
    ob.data.materials.append(mat)
    return ob


def curve_object(name, mat, bevel):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = bevel
    cu.bevel_resolution = 2
    cu.fill_mode = "FULL"
    ob = bpy.data.objects.new(name, cu)
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(mat)
    return ob


def set_polylines(ob, lines):
    cu = ob.data
    cu.splines.clear()
    for pts in lines:
        sp = cu.splines.new("POLY")
        sp.points.add(len(pts) - 1)
        for p, q in zip(sp.points, pts):
            p.co = (float(q[0]), float(q[1]), float(q[2]), 1.0)


def noisy(name, colour, rough=0.85, scale=6.0, amount=0.25):
    mt = material(name, colour, rough=rough)
    nt = mt.node_tree
    b = nt.nodes.get("Principled BSDF")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = scale
    noise.inputs["Detail"].default_value = 6
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = tuple(c * (1 - amount) for c in colour) + (1,)
    ramp.color_ramp.elements[1].color = tuple(min(1, c * (1 + amount)) for c in colour) + (1,)
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    return mt


def sea_material():
    mt = material("Sea", (0.02, 0.07, 0.10), rough=0.08)
    nt = mt.node_tree
    b = nt.nodes.get("Principled BSDF")
    b.inputs["Specular IOR Level"].default_value = 0.6
    tc = nt.nodes.new("ShaderNodeTexCoord")
    n1 = nt.nodes.new("ShaderNodeTexNoise")
    n1.inputs["Scale"].default_value = 0.08
    n1.inputs["Detail"].default_value = 8.0
    nt.links.new(tc.outputs["Object"], n1.inputs["Vector"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.35
    bp.inputs["Distance"].default_value = 1.0
    nt.links.new(n1.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    return mt


def deck_outline():
    """The flight deck's plan outline (x, y), counter-clockwise: broad aft, the island side to starboard (+x), a narrowing bow."""
    return [(-30.0, DECK_Y[0]), (24.0, DECK_Y[0]), (38.0, -60.0), (38.0, 150.0), (22.0, 205.0), (10.0, DECK_Y[1]), (-10.0, DECK_Y[1]),
            (-24.0, 190.0), (-38.0, 120.0), (-40.0, -10.0)]


class Carrier:
    def __init__(self):
        deck_mt = noisy("Flight deck", (0.075, 0.078, 0.085), rough=0.92, scale=3.0, amount=0.25)
        hull_mt = noisy("Hull grey", (0.24, 0.26, 0.28), rough=0.7, scale=0.5, amount=0.1)
        white = material("Deck white", (0.86, 0.86, 0.82), rough=0.6)
        yellow = material("Deck yellow", (0.88, 0.70, 0.08), rough=0.6)
        dark = material("Carrier dark", (0.05, 0.05, 0.06), rough=0.6)
        outline = deck_outline()
        n = len(outline)
        top = [(x, y, 0.0) for x, y in outline]
        bot = [(x * 0.95, y, -0.6) for x, y in outline]
        keel = [(x * 0.52, y * 0.97 + 4.0, SEA_Z - 6.0) for x, y in outline]
        verts = top + bot + keel
        faces = [tuple(range(n))[::-1] if False else tuple(range(n))]
        faces += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
        faces += [(n + i, n + (i + 1) % n, 2 * n + (i + 1) % n, 2 * n + i) for i in range(n)]
        self.deck = mesh_object("Flight deck", top, [tuple(range(n))], deck_mt)
        self.hull = mesh_object("Hull", verts, faces[1:], hull_mt)
        # markings: landing-area edges and centre line (dashes), the foul lines, a yellow ramp edge at the stern
        for x in (-14.0, 14.0):
            y = DECK_Y[0] + 6
            while y < 150:
                cube(f"Edge dash {x} {y:.0f}", (x, y + 2.0, 0.006), (0.35, 4.0, 0.01), white)
                y += 8.0
        y = DECK_Y[0] + 4
        while y < 150:
            cube(f"Centre dash {y:.0f}", (0.0, y + 1.5, 0.006), (0.3, 3.0, 0.01), white)
            y += 7.0
        cube("Stern edge", (-3.0, DECK_Y[0] + 0.6, 0.006), (54.0, 0.6, 0.01), yellow)
        for x in (-17.6, 17.6):
            cube(f"Foul line {x}", (x, 50.0, 0.006), (0.25, 160.0, 0.01), yellow)
        # the island to starboard, with a mast and dark windows
        cube("Island", (30.5, 85.0, 9.0), (8.0, 30.0, 18.0), hull_mt)
        cube("Island top", (30.5, 82.0, 21.0), (6.5, 16.0, 6.0), hull_mt)
        cube("Island windows", (26.45, 84.0, 16.0), (0.1, 24.0, 1.6), dark)
        cube("Mast", (30.5, 80.0, 28.0), (0.8, 0.8, 10.0), hull_mt)
        cube("Radar", (30.5, 80.0, 30.5), (4.5, 0.4, 1.2), dark)
        self.parked = []


class Wires:
    """The four cross-deck pendants on bow springs, deck sheaves at their ends; the caught one follows the hook."""

    def __init__(self):
        self.mt = material("Wire steel", (0.72, 0.73, 0.74), metal=0.9, rough=0.3)
        spring = material("Bow spring", (0.75, 0.62, 0.10), metal=0.4, rough=0.5)
        housing = material("Sheave housing", (0.22, 0.23, 0.24), metal=0.6, rough=0.5)
        self.curves = [curve_object(f"Wire {i + 1}", self.mt, 0.04) for i in range(m.N_WIRES)]
        self.springs = []
        for i, y in enumerate(WY):
            for x in (-12.0, -6.0, 6.0, 12.0):
                self.springs.append(cube(f"Bow spring {i} {x}", (x, y, 0.06), (0.14, 0.5, 0.12), spring))
            for sx in (-1, 1):
                cube(f"Deck sheave {i} {sx}", (sx * m.SPAN, y, 0.05), (1.2, 0.8, 0.14), housing)
        self.rest = [[(-m.SPAN, y, 0.1), (0.0, y, 0.12), (m.SPAN, y, 0.1)] for y in WY]

    def set(self, d, crew_slack=None):
        for i, cv in enumerate(self.curves):
            if i == m.CAUGHT and crew_slack is not None:
                set_polylines(cv, [crew_slack])
            elif i == m.CAUGHT and d > 0.0:
                hook = (0.0, Y3 + d, 0.10)
                set_polylines(cv, [[(-m.SPAN, Y3, 0.1), hook, (m.SPAN, Y3, 0.1)]])
            else:
                set_polylines(cv, [self.rest[i]])


class Jet:
    """A generic twin-engine navy fighter. Local frame: origin at the tailhook's tip when the hook is down, +y forward, z up."""

    def __init__(self):
        self.root = bpy.data.objects.new("Jet root", None)
        bpy.context.collection.objects.link(self.root)
        paint = material("Jet grey", (0.40, 0.43, 0.46), metal=0.2, rough=0.45)
        darker = material("Jet dark grey", (0.24, 0.26, 0.28), metal=0.3, rough=0.5)
        black = material("Jet black", (0.03, 0.03, 0.035), rough=0.6)
        glass = material("Canopy", (0.25, 0.32, 0.36), rough=0.2)
        glass.node_tree.nodes.get("Principled BSDF").inputs["Alpha"].default_value = 0.10
        tyre = material("Jet tyre", (0.03, 0.03, 0.03), rough=0.85)
        self.nozzle_glow = material("Nozzle glow", (1.0, 0.45, 0.1), rough=0.4, emission=0.0)
        P = []
        P.append(cyl("Fuselage", 1.05, 13.0, (0.0, 9.0, 1.9), paint, rot=(math.pi / 2, 0, 0), verts=20))
        P[-1].scale = (1.0, 1.0, 1.0)
        bpy.ops.mesh.primitive_cone_add(vertices=20, radius1=1.05, radius2=0.08, depth=3.6, location=(0.0, 17.3, 1.9), rotation=(-math.pi / 2, 0, 0))
        nose = bpy.context.object
        nose.data.materials.append(paint)
        P.append(nose)
        for sx in (-1, 1):
            P.append(cube(f"Intake {sx}", (sx * 1.25, 11.0, 1.55), (0.7, 5.0, 1.0), darker))
            P.append(mesh_object(f"Wing {sx}", [(sx * 0.9, 5.6, 1.7), (sx * 0.9, 12.2, 1.7), (sx * 6.4, 10.2, 1.62), (sx * 6.4, 8.4, 1.62)],
                                 [(0, 1, 2, 3)], paint))
            P.append(mesh_object(f"Stabilizer {sx}", [(sx * 0.8, 0.6, 1.8), (sx * 0.8, 3.6, 1.8), (sx * 3.4, 2.0, 1.75), (sx * 3.4, 0.9, 1.75)],
                                 [(0, 1, 2, 3)], paint))
            P.append(mesh_object(f"Tail {sx}", [(sx * 1.0, 1.4, 2.6), (sx * 1.0, 5.2, 2.6), (sx * 1.55, 2.6, 5.0), (sx * 1.55, 1.6, 5.0)],
                                 [(0, 1, 2, 3)], darker))
            P.append(cyl(f"Nozzle {sx}", 0.52, 1.2, (sx * 0.62, 1.4, 1.75), black, rot=(math.pi / 2, 0, 0)))
            P.append(cyl(f"Nozzle fire {sx}", 0.40, 0.05, (sx * 0.62, 0.78, 1.75), self.nozzle_glow, rot=(math.pi / 2, 0, 0)))
            P.append(cyl(f"Main wheel {sx}", 0.45, 0.32, (sx * 1.7, 7.0, 0.45), tyre, rot=(0, math.pi / 2, 0)))
            P.append(cube(f"Main strut {sx}", (sx * 1.55, 7.0, 1.0), (0.14, 0.14, 1.2), darker))
        P.append(cyl("Nose wheel", 0.32, 0.22, (0.0, 14.6, 0.32), tyre, rot=(0, math.pi / 2, 0)))
        P.append(cube("Nose strut", (0.0, 14.6, 0.9), (0.12, 0.12, 1.2), darker))
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=1.0, location=(0.0, 14.9, 2.9))
        can = bpy.context.object
        can.scale = (0.66, 1.9, 0.72)
        can.data.materials.append(glass)
        P.append(can)
        P.append(cube("Cockpit tub", (0.0, 14.9, 1.75), (1.1, 2.8, 0.5), black))
        # exhaust plumes (full power)
        self.plume_mt = bpy.data.materials.new("Plume")
        self.plume_mt.use_nodes = True
        nt = self.plume_mt.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = (1.0, 0.55, 0.18, 1)
        em.inputs["Strength"].default_value = 6.0
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        mix.inputs["Fac"].default_value = 0.45
        nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
        nt.links.new(em.outputs["Emission"], mix.inputs[2])
        nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
        self.plumes = []
        for sx in (-1, 1):
            bpy.ops.mesh.primitive_cone_add(vertices=16, radius1=0.42, radius2=0.08, depth=3.2, location=(sx * 0.62, -0.9, 1.75), rotation=(math.pi / 2, 0, 0))
            pl = bpy.context.object
            pl.data.materials.append(self.plume_mt)
            self.plumes.append(pl)
            P.append(pl)
        # the tailhook: a bar from its pivot under the tail; the pivot holds it, angle set per frame
        self.hook_pivot = bpy.data.objects.new("Hook pivot", None)
        bpy.context.collection.objects.link(self.hook_pivot)
        self.hook_pivot.parent = self.root
        self.hook_pivot.location = (0.0, 2.35, 1.05)
        stripes = bpy.data.materials.new("Hook stripes")
        stripes.use_nodes = True
        snt = stripes.node_tree
        sb = snt.nodes.get("Principled BSDF")
        stc = snt.nodes.new("ShaderNodeTexCoord")
        ssep = snt.nodes.new("ShaderNodeSeparateXYZ")
        snt.links.new(stc.outputs["Object"], ssep.inputs["Vector"])
        smul = snt.nodes.new("ShaderNodeMath")
        smul.operation = "MULTIPLY"
        smul.inputs[1].default_value = 3.0
        snt.links.new(ssep.outputs["Y"], smul.inputs[0])
        sfr = snt.nodes.new("ShaderNodeMath")
        sfr.operation = "FRACT"
        snt.links.new(smul.outputs[0], sfr.inputs[0])
        sramp = snt.nodes.new("ShaderNodeValToRGB")
        sramp.color_ramp.interpolation = "CONSTANT"
        sramp.color_ramp.elements[0].color = (0.02, 0.02, 0.02, 1)
        sramp.color_ramp.elements[1].position = 0.5
        sramp.color_ramp.elements[1].color = (0.92, 0.92, 0.9, 1)
        snt.links.new(sfr.outputs[0], sramp.inputs["Fac"])
        snt.links.new(sramp.outputs["Color"], sb.inputs["Base Color"])
        bar = cube("Hook bar", (0.0, -1.18, 0.0), (0.16, 2.5, 0.16), stripes)
        tip = cube("Hook tip", (0.0, -2.42, -0.05), (0.36, 0.26, 0.16), black)
        for ob in (bar, tip):
            ob.parent = self.hook_pivot
        self.hook_down = math.atan2(1.0, 2.35)       # tip on the deck at the local origin
        for ob in P:
            ob.parent = self.root
        self.pilot = dummy.build("Bumper")
        self.pilot["root"].parent = self.root
        self.pilot["root"].location = (0.0, 14.75, 2.5)           # head and shoulders above the canopy rail, as a pilot sits
        self.pilot["root"].scale = (0.85, 0.85, 0.85)
        bpy.ops.object.light_add(type="POINT", location=(0.0, 15.8, 3.2))
        self.cockpit_light = bpy.context.object
        self.cockpit_light.parent = self.root
        self.cockpit_light.data.energy = 0.0
        self.cockpit_light.data.shadow_soft_size = 0.4
        self.parts = P

    def place(self, t, hook_drop_u=None):
        """Position from the model: the hook's tip at the wire's line plus d; before touchdown the jet is still on the glide slope."""
        st = m.jet_state(t)
        y = Y3 + st["d"]
        if t < T_TD:
            z = (T_TD - t) * m.V0 * math.tan(GLIDE)
            pitch = math.radians(7.0)
        else:
            z = 0.0
            pitch = math.radians(7.0) * max(0.0, 1.0 - (t - T_TD) / 0.45)
        self.root.location = (0.0, y, z)
        self.root.rotation_euler = (pitch, 0.0, 0.0)
        ang = self.hook_down if hook_drop_u is None else self.hook_down * (1.0 - (1.0 - hook_drop_u) ** 2) - (1 - hook_drop_u) * 0.35
        self.hook_pivot.rotation_euler = (ang - pitch if t >= T_TD else ang, 0.0, 0.0)
        return st, z, pitch


def sparks():
    """Sparks thrown back from the hook dragging on the deck: (spawn time, velocity, size)."""
    rng = np.random.default_rng(3535)
    out = []
    for k in range(N_SPARK):
        tb = float(rng.uniform(T_TD, 1.6))
        v = np.array([rng.uniform(-3.0, 3.0), -rng.uniform(4.0, 14.0), rng.uniform(1.0, 5.0)])
        out.append((tb, v, float(rng.uniform(0.04, 0.09))))
    return out


SPARKS = sparks()


def spark_pos(k, t):
    tb, v, s = SPARKS[k]
    tau = t - tb
    if tau < 0 or tau > 0.35 or t > m.stop_time():
        return None
    origin = np.array([0.0, Y3 + m.jet_state(tb)["d"], 0.05])
    p = origin + v * tau + np.array([0.0, 0.0, -0.5 * m.G * tau * tau])
    return p if p[2] > 0.0 else None


class Engine:
    """The arresting engine under the deck: purchase cables, the fixed sheave set, the crosshead, ram, cylinder, valve, oil line
    and accumulator. Seen in the x-ray shots."""

    def __init__(self):
        steel = material("Engine steel", (0.35, 0.36, 0.38), metal=0.8, rough=0.4)
        self.cable_mt = material("Purchase cable", (0.30, 0.31, 0.32), metal=0.9, rough=0.35)
        z = ENGINE_Z
        self.cables = curve_object("Purchase cables", self.cable_mt, 0.03)
        self.strands = curve_object("Reeved strands", self.cable_mt, 0.025)
        self.parts = [self.cables, self.strands]
        for sx in (-1, 1):
            for k in range(3):
                x = sx * (1.0 + 0.3 * k)
                self.parts.append(cyl(f"Fixed sheave {sx} {k}", 0.45, 0.12, (x, FIX_Y, z), steel, rot=(0, math.pi / 2, 0), verts=28))
            self.parts.append(cyl(f"Turn sheave {sx}", 0.6, 0.14, (sx * m.SPAN, Y3, z), steel, rot=(0, math.pi / 2, 0), verts=28))
        self.cylinder = cyl("Oil cylinder", 0.62, CYL[1] - CYL[0], (0.0, (CYL[0] + CYL[1]) / 2, z), steel, rot=(math.pi / 2, 0, 0), verts=32)
        self.ram = cyl("Ram", 0.26, 1.0, (0.0, 0.0, z), steel, rot=(math.pi / 2, 0, 0), verts=24)
        self.cross = bpy.data.objects.new("Crosshead", None)
        bpy.context.collection.objects.link(self.cross)
        xparts = [cube("Crosshead frame", (0.0, 0.0, 0.0), (3.8, 0.5, 1.3), steel)]
        for sx in (-1, 1):
            for k in range(3):
                xparts.append(cyl(f"Crosshead sheave {sx} {k}", 0.45, 0.12, (sx * (1.0 + 0.3 * k), -0.2, 0.0), steel, rot=(0, math.pi / 2, 0), verts=28))
        for ob in xparts:
            ob.parent = self.cross
        self.valve = cube("Valve", (0.0, VALVE_Y, z), (1.1, 0.8, 1.1), steel)
        self.pipe = curve_object("Oil line", steel, 0.16)
        set_polylines(self.pipe, [[(0.0, VALVE_Y, z), (0.0, VALVE_Y, z + 1.6), (ACC[0], VALVE_Y, z + 1.6), (ACC[0], ACC[1], z + 1.6)]])
        self.acc = cyl("Accumulator", 0.85, 4.2, (ACC[0], ACC[1], z + 0.6), steel, verts=32)
        self.parts += [self.cylinder, self.ram, self.valve, self.pipe, self.acc] + xparts
        self.oil = [cube(f"Oil pulse {k}", (0, 0, -60), (0.28, 0.28, 0.28), steel) for k in range(10)]
        self.parts += self.oil
        floor = material("Engine room floor", (0.2, 0.2, 0.22), rough=0.8)
        self.room = [cube("Engine room floor", (0.0, Y3 - 12.0, z - 1.4), (40.0, 34.0, 0.3), floor),
                     cube("Hangar deck", (0.0, 40.0, -6.6), (60.0, 260.0, 0.3), floor)]

    def set(self, st):
        z = ENGINE_Z
        ram = st["ram"]
        cy = CROSS0 + ram
        self.cross.location = (0.0, cy, z)
        L = CYL[0] - cy + 1.2
        self.ram.location = (0.0, cy + L / 2, z)
        self.ram.scale = (1.0, 1.0, L)
        lines = []
        for sx in (-1, 1):
            lines.append([(sx * m.SPAN, Y3, 0.05), (sx * m.SPAN, Y3, z + 0.6), (sx * m.SPAN, Y3 - 0.6, z), (sx * 1.6, FIX_Y + 0.4, z)])
        set_polylines(self.cables, lines)
        strands = []
        for sx in (-1, 1):
            for k in range(3):
                x = sx * (1.0 + 0.3 * k)
                strands.append([(x, FIX_Y - 0.45, z + (0.4 if k % 2 else -0.4)), (x, cy - 0.2, z + (0.4 if k % 2 else -0.4))])
        set_polylines(self.strands, strands)
        flow = st["speed"] * (st["d"] > 0)
        path = [(0.0, VALVE_Y, z), (0.0, VALVE_Y, z + 1.6), (ACC[0], VALVE_Y, z + 1.6), (ACC[0], ACC[1], z + 1.6)]
        seg = [math.dist(a, b) for a, b in zip(path[:-1], path[1:])]
        total = sum(seg)
        for k, ob in enumerate(self.oil):
            if flow <= 0.5:
                ob.location = (0, 0, -60)
                continue
            s = (k / len(self.oil) * total + st["payout"] * 0.35) % total
            acc, q = 0.0, 0
            while q < len(seg) - 1 and acc + seg[q] < s:
                acc += seg[q]
                q += 1
            f = (s - acc) / seg[q]
            a, b = path[q], path[q + 1]
            ob.location = tuple(a[i] + (b[i] - a[i]) * f for i in range(3))
        return flow


def football_field():
    """A football field (360 ft x 160 ft) laid along the runout from the caught wire: grass with the yard lines every ten yards and
    darker end zones; see-through so the deck and the jet show. No numbers."""
    L, Wd = 360 * m.FT, 160 * m.FT
    grass = bpy.data.materials.new("Field grass")
    grass.use_nodes = True
    b = grass.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (0.10, 0.42, 0.10, 1)
    b.inputs["Alpha"].default_value = 0.55
    b.inputs["Emission Color"].default_value = (0.10, 0.42, 0.10, 1)
    b.inputs["Emission Strength"].default_value = 0.35
    line_mt = material("Field lines", (0.95, 0.95, 0.95), rough=0.5, emission=0.8)
    end_mt = bpy.data.materials.new("End zone")
    end_mt.use_nodes = True
    e = end_mt.node_tree.nodes.get("Principled BSDF")
    e.inputs["Base Color"].default_value = (0.05, 0.26, 0.06, 1)
    e.inputs["Alpha"].default_value = 0.65
    parts = [cube("Field", (0.0, Y3 + L / 2, 0.03), (Wd, L, 0.01), grass)]
    ez = 10 * 0.9144
    parts += [cube("End zone a", (0.0, Y3 + ez / 2, 0.035), (Wd, ez, 0.01), end_mt), cube("End zone b", (0.0, Y3 + L - ez / 2, 0.035), (Wd, ez, 0.01), end_mt)]
    for k in range(13):
        y = Y3 + ez + k * 10 * 0.9144
        parts.append(cube(f"Yard line {k}", (0.0, y, 0.04), (Wd, 0.35, 0.01), line_mt))
    for sx in (-1, 1):
        parts.append(cube(f"Side line {sx}", (sx * Wd / 2, Y3 + L / 2, 0.04), (0.4, L, 0.01), line_mt))
    return parts


def crew_figure(k, colour=(0.10, 0.55, 0.15)):
    jersey = material(f"Jersey {k}", colour, rough=0.6)
    trousers = material(f"Crew trousers {k}", (0.12, 0.13, 0.12), rough=0.8)
    helmet = material(f"Cranial {k}", (0.92, 0.92, 0.9), rough=0.4)
    skin = material(f"Crew skin {k}", (0.55, 0.38, 0.27), rough=0.7)
    root = bpy.data.objects.new(f"Crew {k}", None)
    bpy.context.collection.objects.link(root)
    torso = bpy.data.objects.new(f"Crew torso {k}", None)
    bpy.context.collection.objects.link(torso)
    torso.parent = root
    torso.location = (0, 0, 0.9)
    legs = [cube(f"Crew leg L {k}", (-0.1, 0, 0.45), (0.16, 0.18, 0.9), trousers), cube(f"Crew leg R {k}", (0.1, 0, 0.45), (0.16, 0.18, 0.9), trousers)]
    up = [cube(f"Crew body {k}", (0, 0, 0.32), (0.44, 0.26, 0.62), jersey), cube(f"Crew arm L {k}", (-0.27, 0.15, 0.32), (0.11, 0.45, 0.12), jersey),
          cube(f"Crew arm R {k}", (0.27, 0.15, 0.32), (0.11, 0.45, 0.12), jersey)]
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=10, radius=0.12, location=(0, 0, 0.76))
    head = bpy.context.object
    head.data.materials.append(skin)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.145, location=(0, 0, 0.82))
    cap = bpy.context.object
    cap.scale = (1.0, 1.1, 0.75)
    cap.data.materials.append(helmet)
    for ob in up + [head, cap]:
        ob.parent = torso
    for ob in legs:
        ob.parent = root
    return root, torso


def main():
    args = arguments()
    args.out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_homefile(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    scene.cycles.transparent_max_bounces = 16
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Punchy"
    scene.view_settings.exposure = -0.25
    scene.world = bpy.data.worlds.new("World")
    sun_to = cinematic.sun_vector((-0.45, 0.9), 22.0)                  # low sun ahead-left of the landing jet: its left side lit
    cinematic.apply_sky(scene, sun_to, strength=0.2, dust=0.35)
    sky_nodes = [n for n in scene.world.node_tree.nodes if n.type == "BACKGROUND"]
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    sun.data.energy, sun.data.angle = 6.0, 0.02
    sun.data.color = (1.0, 0.78, 0.56)
    sun.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()
    sea_mt = sea_material()
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0.0, 0.0, SEA_Z))
    sea = bpy.context.object
    sea.scale = (8000.0, 8000.0, 1.0)
    sea.data.materials.append(sea_mt)
    carrier = Carrier()
    wires = Wires()
    jet = Jet()
    engine = Engine()
    field = football_field()
    spark_mt = material("Spark", (1.0, 0.7, 0.25), emission=12.0)
    spark_obs = [cube(f"Spark {k}", (0, 0, -50), (s, s * 2.5, s), spark_mt) for k, (_, _, s) in enumerate(SPARKS)]
    crew = [crew_figure(k) for k in range(4)]
    old_wire = curve_object("Old wire", material("Worn wire", (0.36, 0.33, 0.30), metal=0.6, rough=0.6), 0.024)
    mech = [wires.curves[m.CAUGHT]] + engine.parts + [bpy.data.objects[f"Deck sheave {m.CAUGHT} {sx}"] for sx in (-1, 1)]
    xr = xray.Xray(mechanism=mech, spared=[sea])
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam

    def render(sh, path):
        scene.render.resolution_x, scene.render.resolution_y = round(FRAME[0] * args.res_scale), round(FRAME[1] * args.res_scale)
        t, variant = sh["t"], sh["variant"]
        xr_on, heat, fld = bool(sh.get("xray")), bool(sh.get("heat")), bool(sh.get("field"))
        throttle, cockpit, drag = bool(sh.get("throttle")), bool(sh.get("cockpit")), bool(sh.get("drag"))
        crew_shot = variant == "crew"
        info = {"variant": variant, "t": round(t, 6), "xray": xr_on, "field": fld, "throttle": throttle, "cockpit": cockpit}
        if crew_shot:
            jet.root.location = (0.0, 400.0, -200.0)
            st = {"d": -1.0, "speed": 0.0, "payout": 0.0, "ram": 0.0, "decel_g": 0.0}
            u = sh["u"]
            # the worn wire: unhooked on the port side and dragged off by the crew toward the deck edge
            if drag:
                ex = -m.SPAN - 1.0 - 15.0 * min(1.0, u * 1.15)
                slack = [(ex, Y3 + 1.2, 0.05), (ex * 0.5, Y3 + 1.6 - 0.8 * u, 0.04), (0.0, Y3 + 0.8 - 0.6 * u, 0.04), (m.SPAN * (1 - u), Y3, 0.05)]
            else:
                ex = -m.SPAN - 1.0
                slack = [(ex, Y3 + 1.2, 0.05), (-8.0, Y3 + 0.4, 0.04), (0.0, Y3, 0.04), (m.SPAN, Y3, 0.05)]
            wires.set(-1.0, crew_slack=slack)
            for k, (root, torso) in enumerate(crew):
                root.hide_render = False
                for ob in root.children_recursive:
                    ob.hide_render = False
                root.location = (ex + 0.9 * k - 0.6, Y3 + 1.4 + 0.5 * (k % 2), 0.0)
                root.rotation_euler = (0.0, 0.0, math.pi / 2 if drag else -math.pi / 2)
                torso.rotation_euler = (0.55 if not drag else 0.35, 0.0, 0.0)
            info.update({"crew": True, "wire_end_x": round(ex, 3)})
        else:
            for root, torso in crew:
                root.hide_render = True
                for ob in root.children_recursive:
                    ob.hide_render = True
            hook_u = sh["u"] if sh.get("hook_drop") else None
            st, z, pitch = jet.place(t, hook_u)
            wires.set(st["d"])
            info.update({"hook_y": round(Y3 + st["d"], 4), "d": round(st["d"], 4), "speed": round(st["speed"], 4), "decel_g": round(st["decel_g"], 4),
                         "payout": round(st["payout"], 4), "ram": round(st["ram"], 4), "jet_z": round(z, 4), "crew": False})
            lean = 0.55 * max(0.0, st["decel_g"]) / 2.5
            stopped = t >= m.stop_time()
            thumbs = min(1.0, max(0.0, (t - m.stop_time() - 0.15) / 0.35)) if cockpit and stopped else 0.0
            dummy.pose(jet.pilot, lean=lean, thumbs_up=thumbs)
            info.update({"pilot_lean": round(lean, 4), "thumbs_up": round(thumbs, 3)})
            jet.cockpit_light.data.energy = 40.0 if cockpit else 0.0
            power = throttle or (T_TD <= t < m.stop_time() + 0.3)
            jet.nozzle_glow.node_tree.nodes.get("Principled BSDF").inputs["Emission Strength"].default_value = 18.0 if power else 0.0
            for pl in jet.plumes:
                pl.hide_render = not power
            info["full_power"] = bool(power)
        old_wire.hide_render = True
        flow = engine.set(st if not crew_shot else {"ram": 0.0, "speed": 0.0, "d": -1.0, "payout": 0.0})
        info["oil_flow"] = round(flow, 3)
        air = 0
        for k, ob in enumerate(spark_obs):
            p = None if crew_shot else spark_pos(k, t)
            if p is None:
                ob.location = (0, 0, -50)
                continue
            ob.location = tuple(p)
            air += 1
        info["sparks"] = air
        for ob in field:
            ob.hide_render = not fld
        for ob in [carrier.hull] + engine.room + [bpy.data.objects[n] for n in ("Island", "Island top", "Island windows", "Mast", "Radar")]:
            ob.hide_render = xr_on
        xr.set(xr_on, glow_strength=4.0 if heat else 2.2)
        for n in sky_nodes:
            n.inputs["Strength"].default_value = 0.06 if xr_on else 1.0
        sun.data.energy = 1.5 if xr_on else 6.0
        c = sh["cam"]
        loc, tgt = Vector(c["loc"]), Vector(c["target"])
        if c["rel"] == "hook":
            hy = Y3 + st["d"]
            loc.y += hy
            tgt.y += hy
            jz = jet.root.location.z
            loc.z += jz
            tgt.z += jz
        dd = cam.data
        dd.sensor_fit, dd.sensor_width, dd.lens, dd.clip_start = "HORIZONTAL", 36.0, c["lens"], 0.05
        dd.clip_end = 9000.0
        dd.dof.use_dof = True
        dd.dof.focus_distance = (tgt - loc).length
        dd.dof.aperture_fstop = c.get("fstop", 8.0)
        base.set_camera(cam, loc, tgt)
        bpy.context.view_layer.update()
        if crew_shot:
            info["subject_box"] = hook_gate.project_box(scene, cam, Matrix.Identity(4), (-m.SPAN - 18.0, Y3 - 1.0, 0.0), (-m.SPAN + 3.0, Y3 + 3.0, 2.0))
        else:
            info["subject_box"] = hook_gate.project_box(scene, cam, jet.root.matrix_world, (-6.4, 0.0, 0.0), (6.4, 19.2, 5.0))
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
        print("WIRE_FRAME " + json.dumps(info), flush=True)
    (args.out / f"wire-frames-{frames[0]:05d}.json").write_text(json.dumps({"renderer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                                                           "frames": out}, indent=1))


if __name__ == "__main__":
    main()
