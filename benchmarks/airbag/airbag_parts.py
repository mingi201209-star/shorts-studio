"""EP.08 detailed airbag parts (Blender side, procedural; no scene text). Everything except the crash sensor lives in the STEERING-WHEEL
frame: an empty at the wheel centre with the wheel's tilt, local z pointing from the driver toward the dashboard (so the bag grows along -z,
toward the driver).
- Hub cover in two flaps that split along a moulded tear seam and swing open toward the driver.
- Folded bag: a stack of pleats behind the cover (shown until the bag is a third full).
- Inflator: a steel canister with a ring of gas ports, and the igniter (squib) at its back with its two wires.
- Bag: a cushion that grows from the hub, with two vent holes on its sides; it flattens where the head presses and shrinks as gas escapes.
- Crash sensor: the airbag control unit on the floor tunnel with its accelerometer chip; it flashes when it decides to fire."""
from __future__ import annotations

import math

import bpy
from mathutils import Vector

from benchmarks.abs_brake import abs_parts as ap
from benchmarks.esc_stability.esc_parts import material


def _empty(name, parent, loc=(0, 0, 0), rot=(0, 0, 0)):
    e = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(e)
    e.parent, e.location, e.rotation_euler = parent, loc, rot
    return e


class AirbagModule:
    def __init__(self, root, wheel_centre, wheel_tilt_deg=-58.0):
        self.frame = _empty("Steering wheel frame", root, wheel_centre, (math.radians(wheel_tilt_deg), 0, 0))
        f = self.frame
        cover_m = material("Hub cover", (0.05, 0.05, 0.055), rough=0.55)
        seam_m = material("Tear seam", (0.015, 0.015, 0.018), rough=0.8)
        fabric = material("Airbag fabric", (0.86, 0.86, 0.82), rough=0.75)
        steel = material("Inflator steel", (0.45, 0.46, 0.48), metal=1.0, rough=0.35)
        dark = material("Port", (0.02, 0.02, 0.025), rough=0.6)
        self.port_glow = material("Port gas", (1.0, 0.75, 0.35), emission=0.0)
        self.flash = material("Igniter flash", (1.0, 0.55, 0.15), emission=0.0)
        wire_m = material("Igniter wire", (0.70, 0.15, 0.10), rough=0.5)
        self.objs = []
        self.cover_parts = []
        self.objs.append(ap.rounded_box("Hub housing", (0, 0, -0.012), (0.17, 0.13, 0.03), cover_m, f, bevel=0.010))
        self.flaps = []
        for side in (1, -1):                                    # top and bottom flaps, hinged on their outer edges
            hinge = _empty(f"Flap hinge {side}", f, (0, side * 0.062, -0.032))
            flap = ap.rounded_box(f"Hub flap {side}", (0, -side * 0.030, -0.006), (0.16, 0.058, 0.012), cover_m, hinge, bevel=0.005)
            self.flaps.append((hinge, side))
            self.objs.append(flap)
            self.cover_parts.append(flap)
        self.cover_parts.append(self.objs[0])
        self.objs.append(ap.rounded_box("Tear seam", (0, 0, -0.039), (0.15, 0.004, 0.002), seam_m, f, bevel=0.0008))
        for k in (-1, 1):
            self.objs.append(ap.rounded_box(f"Tear seam end {k}", (k * 0.075, 0, -0.039), (0.004, 0.10, 0.002), seam_m, f, bevel=0.0008))
        self.cover_parts += [o for o in self.objs if o.name.startswith("Tear seam")]
        self.pleats = []
        for k in range(6):                                       # the folded bag, as a stack of pleats
            p = ap.rounded_box(f"Bag pleat {k}", (0, 0.004 * (k % 2), -0.010 - 0.004 * k), (0.14 - 0.006 * k, 0.10, 0.004), fabric, f, bevel=0.0015)
            self.pleats.append(p)
        self.objs += self.pleats
        bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.042, depth=0.032, location=(0, 0, 0))
        can = bpy.context.object
        can.name = "Inflator canister"
        can.data.materials.append(steel)
        can.parent, can.location = f, (0, 0, 0.018)
        self.objs.append(can)
        for k in range(10):                                      # gas ports around the canister rim
            a = 2 * math.pi * k / 10
            port = ap.cylinder_x(f"Inflator port {k}", 0.005, -0.003, 0.003, 0, 0, self.port_glow, f, n=12)
            port.location = (0.043 * math.cos(a), 0.043 * math.sin(a), 0.020)
            port.rotation_euler = (0, 0, a)
            self.objs.append(port)
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.010, depth=0.018, location=(0, 0, 0))
        ig = bpy.context.object
        ig.name = "Igniter"
        ig.data.materials.append(self.flash)
        ig.parent, ig.location = f, (0, 0, 0.040)
        self.objs.append(ig)
        for k in (-1, 1):
            self.objs.append(ap.tube_curve(f"Igniter wire {k}", [Vector((k * 0.004, 0, 0.049)), Vector((k * 0.010, 0.02, 0.08)), Vector((k * 0.012, 0.06, 0.14))], 0.0018, wire_m, f))
        bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=1.0, location=(0, 0, 0))
        self.bag = bpy.context.object
        self.bag.name = "Airbag cushion"
        self.bag.data.materials.append(fabric)
        for p in self.bag.data.polygons:
            p.use_smooth = True
        self.bag.parent = f
        self.vents = []
        for k in (-1, 1):                                        # vent holes on the sides of the cushion (children of the bag: they follow its shape)
            bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.12, depth=0.04, location=(0, 0, 0))
            v = bpy.context.object
            v.name = f"Bag vent {k}"
            v.data.materials.append(dark)
            v.parent, v.location, v.rotation_euler = self.bag, (k * 0.97, 0.0, 0.15), (0, math.radians(90), 0)
            self.vents.append(v)
        self.objs += [self.bag] + self.vents

    def update(self, fill, bag, press_m, fired):
        """fill: 0..1 how far the bag has deployed; bag: 0..1 its current size after venting; press_m: how far the head pushes into it."""
        opened = min(1.0, fill / 0.25)
        for hinge, side in self.flaps:
            hinge.rotation_euler = (side * math.radians(105) * opened, 0, 0)
        for p in self.pleats:
            p.hide_render = fill > 0.35
        R = 0.30 * min(1.0, (fill / 0.6) ** 0.5) if fill > 0 else 0.0
        D = 0.30 * bag
        depth = max(0.01, D - 0.6 * press_m)
        self.bag.hide_render = fill <= 0.0
        for v in self.vents:
            v.hide_render = fill < 0.7
        self.bag.scale = (max(R, 0.02), max(R * 0.82, 0.02), max(depth / 2, 0.01))
        self.bag.location = (0, 0, -0.04 - depth / 2)
        g = self.flash.node_tree.nodes.get("Principled BSDF")
        g.inputs["Emission Strength"].default_value = 30.0 * max(0.0, 1.0 - fill * 3) if fired else 0.0
        pg = self.port_glow.node_tree.nodes.get("Principled BSDF")
        pg.inputs["Emission Strength"].default_value = 18.0 if fired and fill < 1.0 else 0.0      # hot gas jets from the ports while the bag fills

    def cutaway(self, on):
        """Section view of the hub: cover and folded bag hidden so the inflator and igniter show."""
        for ob in self.cover_parts + self.pleats:
            ob.hide_render = on or ob.hide_render

    def set_visible(self, on):
        for ob in self.objs:
            ob.hide_render = not on


class CrashSensor:
    """Airbag control unit on the floor tunnel: housing, connector and the accelerometer chip; flashes when it fires the igniter."""
    AT = Vector((0.0, 0.30, 0.30))

    def __init__(self, root):
        p = _empty("Airbag control unit", root, self.AT)
        housing = material("ACU housing", (0.10, 0.11, 0.12), rough=0.45)
        lid = material("ACU lid", (0.80, 0.88, 1.0), rough=0.05, transmission=1.0)
        chip = material("Accelerometer chip", (0.08, 0.10, 0.16), metal=0.3, rough=0.3)
        self.flash = material("ACU flash", (1.0, 0.25, 0.1), emission=0.0)
        self.objs = [ap.rounded_box("ACU base", (0, 0, 0.012), (0.16, 0.11, 0.024), housing, p, bevel=0.006),
                     ap.rounded_box("ACU lid", (0, 0, 0.040), (0.15, 0.10, 0.032), lid, p, bevel=0.008),
                     ap.rounded_box("ACU connector", (0.095, 0, 0.018), (0.04, 0.05, 0.028), housing, p, bevel=0.004),
                     ap.rounded_box("Accelerometer", (-0.02, 0, 0.030), (0.04, 0.04, 0.006), chip, p, bevel=0.002),
                     ap.rounded_box("Decision LED", (0.03, 0.02, 0.031), (0.012, 0.012, 0.005), self.flash, p, bevel=0.002)]
        self.mass = ap.rounded_box("Sensing mass", (-0.02, 0, 0.036), (0.012, 0.012, 0.004), material("Proof mass", (0.75, 0.75, 0.8), metal=1.0, rough=0.2), p, bevel=0.001)
        self.objs.append(self.mass)

    def update(self, car_decel_g, fired):
        self.mass.location = (-0.02 + min(0.012, 0.0004 * car_decel_g), 0, 0.036)      # the proof mass is pushed forward by the deceleration
        g = self.flash.node_tree.nodes.get("Principled BSDF")
        g.inputs["Emission Strength"].default_value = 20.0 if fired else 0.0

    def set_visible(self, on):
        for ob in self.objs:
            ob.hide_render = not on
