"""EP.07 detailed ESC parts (Blender side, procedural; no scene text). All in the CAR frame (x right, y forward, z up, origin at the
reference point on the ground), parented to the car root so they move with it. Reuses the mesh helpers of abs_parts.
- Yaw-rate sensor: a module on the centre tunnel; its lid is glass so the vibrating sensing element (a tuning fork on a chip) is visible.
- Steering-angle sensor: a ring housing on the steering column with a slotted code disc that turns with the wheel and an optical reader.
- Hydraulic unit: aluminium valve block with twelve solenoid valve caps, pump motor, ECU cover with connector, brake lines to the four wheels."""
from __future__ import annotations

import math

import bpy
from mathutils import Vector

from benchmarks.abs_brake import abs_parts as ap


def _empty(name, parent, loc=(0, 0, 0)):
    e = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(e)
    e.parent, e.location = parent, loc
    return e


def material(name, color, metal=0.0, rough=0.5, emission=0.0, alpha=1.0, transmission=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    s = m.node_tree.nodes.get("Principled BSDF")
    s.inputs["Base Color"].default_value = (*color, 1)
    s.inputs["Metallic"].default_value = metal
    s.inputs["Roughness"].default_value = rough
    s.inputs["Emission Color"].default_value = (*color, 1)
    s.inputs["Emission Strength"].default_value = emission
    if transmission:
        s.inputs["Transmission Weight"].default_value = transmission
        s.inputs["IOR"].default_value = 1.45
    if alpha < 1.0:
        s.inputs["Alpha"].default_value = alpha
    return m


class YawSensor:
    """Yaw-rate sensor module on the centre tunnel. The sensing element is a small tuning fork on a chip; its tines vibrate, and when the
    car turns they are pushed sideways (the Coriolis effect), which is what the chip measures. The tines' sideways bend follows the yaw rate."""
    AT = Vector((0.0, 0.05, 0.36))

    def __init__(self, root):
        self.root = _empty("Yaw sensor", root, self.AT)
        alu = material("Sensor housing", (0.55, 0.56, 0.58), metal=1.0, rough=0.35)
        dark = material("Sensor dark", (0.04, 0.04, 0.05), rough=0.5)
        glass = material("Sensor lid", (0.85, 0.92, 1.0), rough=0.05, transmission=1.0)
        chip = material("Sensor chip", (0.10, 0.12, 0.18), metal=0.3, rough=0.3)
        si = material("Sensor fork", (0.70, 0.72, 0.80), metal=1.0, rough=0.2)
        self.glow = material("Sensor fork glow", (0.2, 0.8, 1.0), emission=0.0)
        p = self.root
        self.objs = [ap.rounded_box("Yaw sensor base", (0, 0, 0.012), (0.12, 0.09, 0.024), alu, p, bevel=0.006),
                     ap.rounded_box("Yaw sensor lid", (0, 0, 0.045), (0.11, 0.08, 0.040), glass, p, bevel=0.010),
                     ap.rounded_box("Yaw sensor connector", (0.075, 0, 0.018), (0.035, 0.040, 0.026), dark, p, bevel=0.004)]
        for k, (sx, sy) in enumerate(((-1, -1), (-1, 1), (1, -1), (1, 1))):
            self.objs.append(ap.rounded_box(f"Yaw sensor tab {k}", (sx * 0.072, sy * 0.050, 0.004), (0.03, 0.02, 0.006), alu, p, bevel=0.002))
            self.objs.append(ap.cylinder_x(f"Yaw sensor bolt {k}", 0.006, -0.004, 0.004, sy * 0.050, 0.010, alu, p, n=6))
            self.objs[-1].rotation_euler = (0, math.radians(90), 0)
            self.objs[-1].location = (sx * 0.078, 0, 0)
        self.objs.append(ap.rounded_box("Yaw sensor chip", (0, 0, 0.030), (0.05, 0.04, 0.006), chip, p, bevel=0.002))
        self.objs.append(ap.rounded_box("Fork stem", (0, -0.006, 0.040), (0.006, 0.012, 0.014), si, p, bevel=0.001))
        self.objs.append(ap.rounded_box("Fork bridge", (0, 0.002, 0.048), (0.022, 0.004, 0.004), si, p, bevel=0.001))
        self.tines = []
        for sx in (-1, 1):
            pivot = _empty(f"Fork tine pivot {sx}", p, (sx * 0.009, 0.002, 0.048))
            tine = ap.rounded_box(f"Fork tine {sx}", (0, 0.012, 0), (0.0035, 0.024, 0.0035), si, pivot, bevel=0.0008)
            tip = ap.rounded_box(f"Fork tine tip {sx}", (0, 0.024, 0), (0.005, 0.004, 0.005), self.glow, pivot, bevel=0.001)
            self.tines.append((pivot, sx))
            self.objs += [tine, tip]
        for k in range(6):                                     # bond wires / pads on the chip
            self.objs.append(ap.rounded_box(f"Chip pad {k}", (-0.020 + 0.008 * k, -0.016, 0.034), (0.004, 0.004, 0.001), si, p, bevel=0.0005))

    def update(self, t, yaw_rate):
        vib = 0.08 * math.sin(2 * math.pi * 7.0 * t)          # drive vibration (slowed down for the film)
        bend = max(-0.35, min(0.35, 0.9 * yaw_rate))           # Coriolis bend grows with the yaw rate
        for pivot, sx in self.tines:
            pivot.rotation_euler = (0, sx * vib * 0.0, sx * vib + bend)
        g = self.glow.node_tree.nodes.get("Principled BSDF")
        g.inputs["Emission Strength"].default_value = 2.0 + 25.0 * min(1.0, abs(yaw_rate))

    def set_visible(self, on):
        for ob in self.objs:
            ob.hide_render = not on


class SteeringSensor:
    """Steering wheel, column and the steering-angle sensor: a slotted code disc that turns with the column between an LED and a reader."""
    COLUMN_TOP = Vector((-0.36, 0.55, 0.92))
    COLUMN_BOTTOM = Vector((-0.36, 1.05, 0.55))
    RATIO = 15.0                                               # steering wheel turns 15x the road wheel angle

    def __init__(self, root):
        steel = material("Column steel", (0.40, 0.40, 0.42), metal=1.0, rough=0.35)
        black = material("Wheel rim", (0.03, 0.03, 0.035), rough=0.6)
        housing = material("Sensor ring housing", (0.08, 0.08, 0.09), rough=0.45, alpha=1.0)
        disc_m = material("Code disc", (0.75, 0.62, 0.25), metal=1.0, rough=0.25)
        self.led = material("Reader LED", (1.0, 0.25, 0.1), emission=6.0)
        d = (self.COLUMN_TOP - self.COLUMN_BOTTOM).normalized()
        rot = d.to_track_quat("Z", "Y").to_euler()
        self.col = _empty("Steering column", root, self.COLUMN_TOP)
        self.col.rotation_euler = rot
        self.spin = _empty("Steering spin", self.col)
        L = (self.COLUMN_TOP - self.COLUMN_BOTTOM).length
        bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.022, depth=L, location=(0, 0, 0))
        shaft = bpy.context.object
        shaft.name = "Steering shaft"
        shaft.data.materials.append(steel)
        shaft.parent, shaft.location = self.spin, (0, 0, -L / 2)
        bpy.ops.mesh.primitive_torus_add(major_radius=0.18, minor_radius=0.016, location=(0, 0, 0.02))
        rim = bpy.context.object
        rim.name = "Steering wheel rim"
        rim.data.materials.append(black)
        rim.parent = self.spin
        self.objs = [shaft, rim]
        for k, a in enumerate((math.radians(-90), math.radians(30), math.radians(150))):
            sp = ap.rounded_box(f"Steering spoke {k}", (0.09 * math.cos(a), 0.09 * math.sin(a), 0.02), (0.17, 0.035, 0.014), black, self.spin, bevel=0.005, rot=(0, 0, a))
            self.objs.append(sp)
        self.objs.append(ap.rounded_box("Steering hub", (0, 0, 0.025), (0.08, 0.08, 0.03), black, self.spin, bevel=0.012))
        self.objs.append(ap.rounded_box("Top mark", (0, 0.172, 0.02), (0.03, 0.012, 0.02), material("Top mark", (0.9, 0.5, 0.1)), self.spin, bevel=0.003))
        # sensor: housing ring fixed to the column tube, code disc turning with the shaft
        z = -0.16
        self.objs.append(ap.sector("Angle sensor housing", 0.050, 0.075, 0, 2 * math.pi, -0.012, 0.012, housing, None, n=48))
        self.objs[-1].parent, self.objs[-1].location, self.objs[-1].rotation_euler = self.col, (0, 0, z), (0, math.radians(90), 0)
        self.objs.append(ap.sector("Code disc ring", 0.026, 0.040, 0, 2 * math.pi, -0.0015, 0.0015, disc_m, None, n=64))
        self.objs[-1].parent, self.objs[-1].location, self.objs[-1].rotation_euler = self.spin, (0, 0, z), (0, math.radians(90), 0)
        for k in range(24):                                   # slots read by the optical reader
            a = 2 * math.pi * k / 24
            sl = ap.sector(f"Code slot {k}", 0.040, 0.062, a, a + 0.12, -0.0015, 0.0015, disc_m, None, n=1)
            sl.parent, sl.location, sl.rotation_euler = self.spin, (0, 0, z), (0, math.radians(90), 0)
            self.objs.append(sl)
        self.reader = ap.rounded_box("Optical reader", (0.06, 0, z), (0.024, 0.02, 0.03), housing, self.col, bevel=0.003)
        self.objs.append(self.reader)
        self.objs.append(ap.rounded_box("Reader LED", (0.05, 0, z + 0.010), (0.006, 0.006, 0.004), self.led, self.col, bevel=0.001))
        self.objs.append(ap.tube_curve("Sensor harness", [Vector((0.07, 0, z)), Vector((0.12, -0.02, z + 0.05)), Vector((0.16, -0.08, z + 0.10))], 0.004, black, self.col))

    def update(self, road_wheel_angle):
        self.spin.rotation_euler = (0, 0, -road_wheel_angle * self.RATIO)

    def set_visible(self, on):
        for ob in self.objs:
            ob.hide_render = not on


class HydraulicUnit:
    """ABS/ESC hydraulic unit in the engine bay: valve block, solenoid valve caps, pump motor, control-unit cover and brake lines to each
    wheel. The valve and line for the wheel being braked glow with the brake pressure."""
    AT = Vector((-0.40, 1.45, 0.62))

    def __init__(self, root, wheel_bases):
        alu = material("Valve block", (0.62, 0.63, 0.66), metal=1.0, rough=0.3)
        dark = material("ECU cover", (0.06, 0.06, 0.07), rough=0.5)
        motor_m = material("Pump motor", (0.12, 0.12, 0.13), metal=0.6, rough=0.4)
        cap = material("Valve cap", (0.30, 0.30, 0.32), metal=1.0, rough=0.35)
        line = material("Brake line", (0.55, 0.45, 0.30), metal=1.0, rough=0.3)
        p = _empty("Hydraulic unit", root, self.AT)
        self.objs = [ap.rounded_box("Valve block", (0, 0, 0), (0.14, 0.11, 0.10), alu, p, bevel=0.008),
                     ap.rounded_box("Control unit cover", (0, -0.075, 0), (0.15, 0.04, 0.11), dark, p, bevel=0.010),
                     ap.rounded_box("Connector", (0.0, -0.10, 0.03), (0.06, 0.02, 0.03), dark, p, bevel=0.004),
                     ap.cylinder_x("Pump motor", 0.035, 0.07, 0.15, 0.0, -0.01, motor_m, p, n=32),
                     ap.cylinder_x("Motor end cap", 0.030, 0.15, 0.16, 0.0, -0.01, cap, p, n=32)]
        self.valve_glow = {}
        for i in range(3):
            for j in range(4):
                vx, vy = -0.045 + 0.045 * i, -0.035 + 0.025 * j
                g = material(f"Valve glow {i}{j}", (1.0, 0.35, 0.08), emission=0.0)
                c = ap.cylinder_x(f"Valve cap {i}{j}", 0.009, 0, 0.026, 0, 0, cap, p, n=20)
                c.rotation_euler, c.location = (0, math.radians(-90), 0), (vx, vy, 0.05)
                top = ap.cylinder_x(f"Valve top {i}{j}", 0.0065, 0, 0.004, 0, 0, g, p, n=20)
                top.rotation_euler, top.location = (0, math.radians(-90), 0), (vx, vy, 0.076)
                self.objs += [c, top]
                self.valve_glow[(i, j)] = g
        self.lines = {}
        for k, (key, wb) in enumerate(sorted(wheel_bases.items())):
            port = Vector((-0.07, 0.03 - 0.02 * k, 0.02))
            start = self.AT + port
            end = Vector(wb) + Vector((0.0, -0.05, 0.18))
            mid = Vector(((start.x + end.x) / 2, (start.y + end.y) / 2, max(start.z, end.z) + 0.05))
            g = material(f"Line glow {key}", (0.55, 0.45, 0.30), metal=1.0, rough=0.3)
            c = ap.tube_curve(f"Brake line {key}", [start, mid, end], 0.004, g, root)
            fit = ap.cylinder_x(f"Line fitting {key}", 0.007, -0.08, -0.07, port.y, port.z, cap, p, n=6)
            self.objs += [c, fit]
            self.lines[key] = g
        self.key_valve = {"front_right": (2, 0), "front_left": (0, 0), "rear_right": (2, 3), "rear_left": (0, 3)}

    def update(self, braked_wheel, force_frac):
        for key, g in self.valve_glow.items():
            g.node_tree.nodes.get("Principled BSDF").inputs["Emission Strength"].default_value = 0.0
        for key, g in self.lines.items():
            b = g.node_tree.nodes.get("Principled BSDF")
            b.inputs["Emission Color"].default_value = (1.0, 0.3, 0.05, 1)
            b.inputs["Emission Strength"].default_value = 6.0 * force_frac if key == braked_wheel else 0.0
        if braked_wheel:
            g = self.valve_glow[self.key_valve[braked_wheel]]
            g.node_tree.nodes.get("Principled BSDF").inputs["Emission Strength"].default_value = 15.0 * force_frac

    def set_visible(self, on):
        for ob in self.objs:
            ob.hide_render = not on
