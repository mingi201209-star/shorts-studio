"""EP.06 ABS: 100 % 3D renderer (Blender, Cycles CPU). Same CC0 sedan as earlier episodes (load_source_car), a straight two-lane road, a cardboard box in
the lane, and for the macro shots a see-through front-left wheel: brake disc, caliper with pads, ABS tone ring and wheel-speed sensor.
Everything that moves comes from abs_motion (car pose, wheel spin, steering, brake pressure, box). Shots come from abs_shots.py. No scene text."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from benchmarks.abs_brake import abs_motion as am  # noqa: E402
from benchmarks.abs_brake import abs_shots as shots  # noqa: E402
from benchmarks.abs_brake import abs_timeline as tl  # noqa: E402
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402

material, cube = base.material, base.cube
LANE_W = 3.6


def arguments():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--shots", default="all")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--res-scale", type=float, default=0.5)
    p.add_argument("--samples", type=int, default=16)
    p.add_argument("--film", action="store_true", help="render film frames (abs_timeline) instead of storyboard shots")
    p.add_argument("--frames", default="0-0")
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return p.parse_args(argv)


def build_road():
    road = material("Asphalt", (0.07, 0.07, 0.075), rough=0.85)
    base.asphalt_grain(road)
    cube("Road", (-LANE_W / 2, 30, -0.05), (LANE_W * 2 + 3.0, 140, 0.1), road)
    grass = material("Verge", (0.10, 0.16, 0.06), rough=0.95)
    cube("Verge right", (LANE_W / 2 + 1.5 + 10, 30, -0.06), (20, 140, 0.1), grass)
    cube("Verge left", (-1.5 * LANE_W - 1.5 - 10, 30, -0.06), (20, 140, 0.1), grass)
    white = material("Line paint", (0.85, 0.85, 0.82), rough=0.6)
    cube("Edge line right", (LANE_W / 2 + 0.1, 30, 0.002), (0.15, 140, 0.004), white)
    cube("Edge line left", (-1.5 * LANE_W - 0.1, 30, 0.002), (0.15, 140, 0.004), white)
    for i in range(-10, 30):
        cube(f"Dash {i}", (-LANE_W / 2, i * 4.0, 0.002), (0.13, 2.0, 0.004), white)


def build_box():
    card = material("Cardboard", (0.42, 0.26, 0.11), rough=0.85)
    tape = material("Box tape", (0.62, 0.50, 0.30), rough=0.4)
    hx, hy, hz = am.BOX_HALF
    root = bpy.data.objects.new("Box root", None)
    bpy.context.collection.objects.link(root)
    for ob in (cube("Box", (0, 0, 0), (2 * hx, 2 * hy, 2 * hz), card), cube("Box tape", (0, 0, hz + 0.002), (0.10, 2 * hy + 0.004, 0.006), tape)):
        ob.parent = root
    return root


class Skid:
    """Dark rubber marks behind the locked car's four tyres: from the moment the wheels lock to the car's current position (straight, because it slides straight)."""

    def __init__(self, wheels):
        self.mat = material("Skid rubber", (0.012, 0.012, 0.014), rough=0.9)
        self.obs = []
        for key, w in wheels.items():
            ob = cube(f"Skid {key}", (0, 0, 0), (0.20, 1.0, 0.003), self.mat)
            self.obs.append((ob, float(w["base"].x), float(w["base"].y)))

    def update(self, variant, t):
        lock = am.at(variant, am.LOCK_TIME_S)
        now = am.at(variant, t)
        for ob, wx, wy in self.obs:
            y0, y1 = lock["y"] + wy, now["y"] + wy
            show = variant == "locked" and t > am.LOCK_TIME_S + 0.02 and y1 - y0 > 0.05
            ob.hide_render = not show
            if show:
                ob.location = (now["x"] + wx, (y0 + y1) / 2, 0.003)
                ob.scale = (1.0, y1 - y0, 1.0)


class BrakeCutaway:
    """Front-left wheel internals for the macro shots, in the wheel node's frame (x = axle, outward is -x for the left wheel).
    Disc and tone ring turn with the wheel; caliper, pads and sensor do not (they are parented to the car root at the wheel centre)."""

    def __init__(self, root, wheel):
        node = wheel["node"]
        c = Vector(wheel["base"])
        self.node = node
        steel = material("Brake disc", (0.42, 0.42, 0.44), metal=1.0, rough=0.35)
        ring_m = material("Tone ring", (0.75, 0.55, 0.20), metal=1.0, rough=0.3)
        self.cal_m = material("Caliper", (0.70, 0.05, 0.04), rough=0.4, emission=0.0)
        pad_m = material("Brake pad", (0.10, 0.10, 0.11), rough=0.9)
        sens_m = material("Wheel speed sensor", (0.05, 0.05, 0.06), rough=0.5)
        self.glow = material("Sensor pulse", (0.15, 0.85, 1.0), rough=0.4, emission=0.0)
        self.parts_spin, self.parts_fixed = [], []
        bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.19, depth=0.022, location=(0, 0, 0), rotation=(0, math.radians(90), 0))
        disc = bpy.context.object
        disc.name = "Brake disc"
        disc.data.materials.append(steel)
        disc.parent, disc.location = node, (-0.06, 0, 0)
        self.parts_spin.append(disc)
        n_teeth = 36
        for i in range(n_teeth):
            a = 2 * math.pi * i / n_teeth
            t = cube(f"Tone ring tooth {i}", (0, 0, 0), (0.018, 0.022, 0.026), ring_m)
            t.parent = node
            t.location = (-0.105, 0.105 * math.cos(a), 0.105 * math.sin(a))
            t.rotation_euler = (a, 0, 0)
            self.parts_spin.append(t)
        bpy.ops.mesh.primitive_torus_add(major_radius=0.092, minor_radius=0.008, location=(0, 0, 0), rotation=(0, math.radians(90), 0))
        band = bpy.context.object
        band.name = "Tone ring band"
        band.data.materials.append(ring_m)
        band.parent, band.location = node, (-0.105, 0, 0)
        self.parts_spin.append(band)
        self.fixed = bpy.data.objects.new("Brake fixed parts", None)
        bpy.context.collection.objects.link(self.fixed)
        self.fixed.parent, self.fixed.location = root, c
        cal = cube("Caliper", (0, 0, 0), (0.075, 0.15, 0.075), self.cal_m)
        cal.parent, cal.location = self.fixed, (-0.06, -0.085, 0.135)
        cal.rotation_euler = (math.radians(32), 0, 0)
        self.pads = []
        for side in (-1, 1):
            pad = cube(f"Brake pad {side}", (0, 0, 0), (0.012, 0.13, 0.07), pad_m)
            pad.parent = self.fixed
            pad.rotation_euler = (math.radians(32), 0, 0)
            self.pads.append((pad, side))
        self.parts_fixed += [cal] + [p for p, _ in self.pads]
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.014, depth=0.07, location=(0, 0, 0))
        sens = bpy.context.object
        sens.name = "Wheel speed sensor"
        sens.data.materials.append(sens_m)
        sens.parent, sens.location = self.fixed, (-0.105, 0.0, -0.16)
        tip = cube("Sensor tip", (0, 0, 0), (0.02, 0.02, 0.012), self.glow)
        tip.parent, tip.location = self.fixed, (-0.105, 0.0, -0.126)
        cable = cube("Sensor cable", (0, 0, 0), (0.008, 0.008, 0.25), sens_m)
        cable.parent, cable.location = self.fixed, (-0.105, -0.06, -0.30)
        cable.rotation_euler = (math.radians(25), 0, 0)
        self.parts_fixed += [sens, tip, cable]

    def update(self, pressure, wheel_angle, steer, n_teeth=36):
        self.fixed.rotation_euler = (0, 0, steer)
        gap = 0.004 + 0.010 * (1.0 - pressure)               # pads clamp the disc as the pressure rises (gap exaggerated x5 to be visible)
        for pad, side in self.pads:
            pad.location = (-0.06 + side * (0.011 + 0.006 + gap), -0.085, 0.135)
        cal = self.cal_m.node_tree.nodes.get("Principled BSDF")
        cal.inputs["Emission Color"].default_value = (1.0, 0.25, 0.05, 1.0)
        cal.inputs["Emission Strength"].default_value = 3.0 * pressure
        phase = (wheel_angle * n_teeth / (2 * math.pi)) % 1.0     # the sensor sees a tooth pass: pulse brightness follows the tooth under the tip
        g = self.glow.node_tree.nodes.get("Principled BSDF")
        g.inputs["Emission Color"].default_value = (0.15, 0.85, 1.0, 1.0)
        g.inputs["Emission Strength"].default_value = 6.0 * (1.0 if phase < 0.5 else 0.15)

    def set_visible(self, on):
        for ob in self.parts_spin + self.parts_fixed:
            ob.hide_render = not on


PEDAL_AT = Vector((0.0, -400.0, 0.0))     # the footwell set stands far behind the start, out of every road shot


class Pedal:
    """Insert for the last line: driver's shoe on the brake pedal in a dark footwell. The pedal is pushed down by the brake pressure and, while ABS
    eases and reapplies the pressure, it kicks back against the foot (the 'buzz'). Same pressure signal as the caliper glow."""

    def __init__(self):
        self.objs = []
        dark = material("Footwell", (0.035, 0.037, 0.045), rough=0.9)
        carpet = material("Carpet", (0.06, 0.06, 0.07), rough=1.0)
        metal = material("Pedal arm", (0.25, 0.25, 0.27), metal=1.0, rough=0.4)
        rubber = material("Pedal pad", (0.02, 0.02, 0.02), rough=0.8)
        shoe_m = material("Shoe", (0.30, 0.17, 0.08), rough=0.6)
        sole_m = material("Sole", (0.85, 0.85, 0.82), rough=0.7)
        P = PEDAL_AT
        for name, c, d, m in (("Footwell floor", (0, 0.1, -0.02), (1.4, 1.4, 0.04), carpet), ("Firewall", (0, 0.55, 0.4), (1.4, 0.04, 1.0), dark),
                              ("Footwell side", (-0.45, 0.1, 0.4), (0.04, 1.4, 1.0), dark), ("Footwell roof", (0, 0.1, 0.85), (1.4, 1.4, 0.04), dark)):
            ob = cube(name, P + Vector(c), d, m)
            self.objs.append(ob)
        self.pivot = bpy.data.objects.new("Pedal pivot", None)
        bpy.context.collection.objects.link(self.pivot)
        self.pivot.location = P + Vector((0, 0.45, 0.62))
        tilt = math.radians(30)                                  # pad face tilted back toward the driver
        arm = cube("Pedal arm", (0, 0, 0), (0.03, 0.03, 0.46), metal)
        arm.parent, arm.location = self.pivot, (0, -0.05, -0.23)
        arm.rotation_euler = (math.radians(-12), 0, 0)          # leans toward the driver so its foot meets the pad
        pad_c = Vector((0, -0.10, -0.47))
        pad = cube("Pedal pad", (0, 0, 0), (0.13, 0.03, 0.09), rubber)
        pad.parent, pad.location, pad.rotation_euler = self.pivot, pad_c, (tilt, 0, 0)
        n = Vector((0, -math.cos(tilt), -math.sin(tilt)))        # the pad's -Y face after the X rotation: its normal points at the foot
        along = Vector((0, math.sin(tilt), -math.cos(tilt)))     # the pad's -Z axis after the rotation: down the pad face
        sole = cube("Sole", (0, 0, 0), (0.11, 0.028, 0.29), sole_m)
        sole.parent, sole.location, sole.rotation_euler = self.pivot, pad_c + n * 0.029 + along * 0.06, (tilt, 0, 0)
        shoe = cube("Shoe", (0, 0, 0), (0.105, 0.09, 0.27), shoe_m)
        shoe.parent, shoe.location, shoe.rotation_euler = self.pivot, pad_c + n * 0.087 + along * 0.07, (tilt, 0, 0)
        heel = pad_c + n * 0.09 + along * 0.17
        shin = Vector((0, -math.sin(math.radians(55)), math.cos(math.radians(55))))      # from the heel back toward the seat and up
        leg = cube("Trouser leg", (0, 0, 0), (0.10, 0.10, 0.55), material("Trousers", (0.05, 0.07, 0.11), rough=0.8))
        leg.parent, leg.location, leg.rotation_euler = self.pivot, heel + n * 0.10 + shin * 0.30, (math.radians(55), 0, 0)
        self.objs += [arm, pad, shoe, sole, leg]
        bpy.ops.object.light_add(type="AREA", location=P + Vector((0.4, -0.5, 0.7)))
        lamp = bpy.context.object
        lamp.data.energy, lamp.data.size = 60.0, 0.6
        lamp.rotation_euler = Vector((-0.4, 0.5, -0.6)).to_track_quat("-Z", "Y").to_euler()
        self.objs.append(lamp)

    def update(self, pressure):
        self.pivot.rotation_euler = (math.radians(-(10.0 + 2.5 * pressure)), 0, 0)     # held down; a small kick back each time ABS eases the pressure

    def set_visible(self, on):
        for ob in self.objs:
            ob.hide_render = not on


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
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.exposure = -1.3
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    sun_to = cinematic.sun_vector((-0.5, -0.8), 38.0)
    cinematic.apply_sky(scene, sun_to, strength=0.25, dust=0.5)
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    sun.data.energy, sun.data.angle = 3.4, 0.03
    sun.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()
    build_road()
    box = build_box()
    skid = Skid(wheels)
    cut = BrakeCutaway(root, wheels["front_left"])
    world_objs = [o for o in bpy.data.objects if o.type in ("MESH", "LIGHT") and o.name != sun.name]
    pedal = Pedal()
    fl_parts = [o for o in wheels["front_left"]["node"].children if o not in cut.parts_spin]
    car_meshes = [o for o in root.children_recursive if o.type == "MESH" and o not in cut.parts_spin + cut.parts_fixed]
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam

    def render(sh, variant, path, size):
        st = am.at(variant, sh["t"])
        scene.render.resolution_x, scene.render.resolution_y = round(size[0] * args.res_scale), round(size[1] * args.res_scale)
        root.location = (st["x"], st["y"], 0.0)
        root.rotation_euler = (0, 0, st["heading"])
        pitch = 0.012 * min(1.0, max(0.0, st["t"]) / 0.15) if st["speed"] > 0.3 else 0.0      # nose dips under braking
        body.rotation_euler = (-pitch, 0, 0)
        for key, wh in wheels.items():
            wh["node"].rotation_mode = "ZXY"
            wh["node"].rotation_euler = (-st["wheel_angle"], 0, st["steer"] if key.startswith("front") else 0.0)
        bx = st["box"]
        box.location = (bx["x"], bx["y"], bx["z"])
        box.rotation_euler = (bx["rx"], 0, 0)
        skid.update(variant, sh["t"])
        cut.update(st["pressure"], st["wheel_angle"], st["steer"])
        pedal.update(st["pressure"])
        macro, in_pedal = bool(sh.get("macro")), bool(sh.get("pedal"))
        for ob in world_objs:
            ob.hide_render = in_pedal
        pedal.set_visible(in_pedal)
        sun.hide_render = in_pedal
        if not in_pedal:
            cut.set_visible(macro)
            skid.update(variant, sh["t"])
            for ob in fl_parts:
                ob.hide_render = macro and ob.type == "MESH"
        c = sh["cam"]
        origin = {"car": Vector((st["x"], st["y"], 0.0)), "chase": Vector((0, st["y"], 0)), "pedal": PEDAL_AT}.get(c["rel"], Vector((0, 0, 0)))
        dd = cam.data
        dd.sensor_fit, dd.sensor_width, dd.lens, dd.clip_start = "HORIZONTAL", 36.0, c["lens"], 0.02
        base.set_camera(cam, origin + Vector(c["loc"]), origin + Vector(c["target"]))
        bpy.context.view_layer.update()
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        return {"variant": variant, "t": round(sh["t"], 5), "x": round(st["x"], 3), "y": round(st["y"], 3), "heading_deg": round(math.degrees(st["heading"]), 2),
                "speed_kmh": round(st["speed"] * 3.6, 1), "wheel_rpm": round(st["wheel_omega"] * 60 / (2 * math.pi), 1), "steer_deg": round(math.degrees(st["steer"]), 2),
                "pressure": round(st["pressure"], 3), "box_hit": bx["hit"], "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    out = []
    if args.film:
        segs = tl.segments()
        a, b = (int(x) for x in args.frames.split("-"))
        for f in range(a, b + 1):
            t0 = time.time()
            sh = tl.frame_state(f, segs)
            if sh.get("split"):
                parts = [render(sh, "abs", args.out / f"frame_{f:05d}_top.png", shots.HALF), render(sh, "locked", args.out / f"frame_{f:05d}_bot.png", shots.HALF)]
            else:
                parts = [render(sh, sh["variant"], args.out / f"frame_{f:05d}.png", shots.FRAME)]
            info = {"frame": f, "segment": sh["segment"], "split": bool(sh.get("split")), "parts": parts, "render_seconds": round(time.time() - t0, 1)}
            out.append(info)
            print("ABS_FRAME " + json.dumps(info), flush=True)
        (args.out / f"abs-frames-{a:05d}.json").write_text(json.dumps({"renderer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "frames": out}, indent=1))
        return
    names = list(shots.SHOTS) if args.shots == "all" else args.shots.split(",")
    for name in names:
        t0 = time.time()
        sh = shots.SHOTS[name]
        info = {"shot": name, **render(sh, sh["variant"], args.out / f"{name}.png", sh.get("frame", shots.FRAME)), "render_seconds": round(time.time() - t0, 1)}
        out.append(info)
        print("ABS_SHOT " + json.dumps(info), flush=True)
    (args.out / "abs-shots.json").write_text(json.dumps({"renderer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "shots": out, "abs_gate": am.abs_physics()}, indent=1))


if __name__ == "__main__":
    main()
