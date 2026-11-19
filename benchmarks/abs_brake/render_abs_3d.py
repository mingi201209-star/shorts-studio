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
from benchmarks.abs_brake import abs_parts as parts  # noqa: E402
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
    Disc, hat and tone ring turn with the wheel; caliper, pads and sensor do not (they hang from a fixed node at the wheel centre that only steers).
    Detailed parts come from abs_parts."""

    def __init__(self, root, wheel):
        node = wheel["node"]
        self.node = node
        steel = material("Brake disc", (0.46, 0.46, 0.48), metal=1.0, rough=0.32)
        dark = material("Disc vane", (0.08, 0.08, 0.09), metal=0.6, rough=0.6)
        hat = material("Disc hat", (0.30, 0.30, 0.32), metal=1.0, rough=0.45)
        ring_m = material("Tone ring", (0.72, 0.52, 0.20), metal=1.0, rough=0.3)
        self.cal_m = material("Caliper", (0.70, 0.05, 0.04), rough=0.35)
        pad_m = material("Brake pad", (0.10, 0.10, 0.11), rough=0.95)
        back_m = material("Pad backing", (0.25, 0.26, 0.28), metal=1.0, rough=0.5)
        hose_m = material("Brake hose", (0.03, 0.03, 0.035), rough=0.6)
        rubber = material("Piston boot", (0.05, 0.05, 0.05), rough=0.8)
        sens_m = material("Wheel speed sensor", (0.05, 0.05, 0.06), rough=0.45)
        hex_m = material("Sensor flange", (0.40, 0.40, 0.42), metal=1.0, rough=0.4)
        self.glow = material("Sensor pulse", (0.15, 0.85, 1.0), rough=0.4, emission=0.0)
        self.parts_spin = parts.build_disc(node, steel, dark, hat) + parts.build_tone_ring(node, ring_m, self.N_TEETH)
        self.fixed = bpy.data.objects.new("Brake fixed parts", None)
        bpy.context.collection.objects.link(self.fixed)
        self.fixed.parent, self.fixed.location = root, Vector(wheel["base"])
        cal_parts, self.pads = parts.build_caliper(self.fixed, self.cal_m, steel, pad_m, back_m, hose_m, rubber)
        sens_parts, _tip = parts.build_sensor(self.fixed, sens_m, hex_m, hose_m, self.glow)
        self.parts_fixed = cal_parts + sens_parts + [p for fr, bk, _ in self.pads for p in (fr, bk)]

    N_TEETH = 44

    def update(self, pressure, wheel_angle, steer):
        self.fixed.rotation_euler = (0, 0, steer)
        gap = 0.0015 + 0.006 * (1.0 - pressure)               # pads clamp the disc as the pressure rises (gap exaggerated to be visible)
        half = 0.0125 + 0.004                                  # disc half thickness + friction thickness / 2
        for fr, bk, side in self.pads:
            x = -0.06 + side * (half + gap)
            fr.location = (x, 0, 0)
            bk.location = (x, 0, 0)
        cal = self.cal_m.node_tree.nodes.get("Principled BSDF")
        cal.inputs["Emission Color"].default_value = (1.0, 0.25, 0.05, 1.0)
        cal.inputs["Emission Strength"].default_value = 0.6 * pressure      # a warm glow with the pressure, weak enough to keep the shape readable
        phase = (wheel_angle * self.N_TEETH / (2 * math.pi)) % 1.0     # the sensor sees a tooth pass: pulse brightness follows the tooth under the tip
        g = self.glow.node_tree.nodes.get("Principled BSDF")
        g.inputs["Emission Color"].default_value = (0.15, 0.85, 1.0, 1.0)
        g.inputs["Emission Strength"].default_value = 6.0 * (1.0 if phase < 0.5 else 0.15)

    def set_visible(self, on):
        for ob in self.parts_spin + self.parts_fixed:
            ob.hide_render = not on


PEDAL_AT = Vector((0.0, -400.0, 0.0))     # the footwell set stands far behind the start, out of every road shot


class Pedal:
    """Insert for the last line: the driver's shoe on the brake pedal in a dark footwell. Pivot bracket on the firewall, a bent steel arm, a ribbed
    rubber pad, a return spring, a rounded shoe with a treaded sole and the trouser leg. The pedal is held down and kicks back a little each time
    ABS eases the pressure (same pressure signal as the caliper glow)."""

    def __init__(self):
        self.objs = []
        dark = material("Footwell", (0.035, 0.037, 0.045), rough=0.9)
        carpet = material("Carpet", (0.06, 0.06, 0.07), rough=1.0)
        metal = material("Pedal arm", (0.30, 0.30, 0.32), metal=1.0, rough=0.35)
        rubber = material("Pedal pad", (0.02, 0.02, 0.02), rough=0.8)
        shoe_m = material("Shoe", (0.30, 0.17, 0.08), rough=0.55)
        sole_m = material("Sole", (0.80, 0.80, 0.77), rough=0.7)
        trousers = material("Trousers", (0.05, 0.07, 0.11), rough=0.8)
        P = PEDAL_AT
        for name, c, d, m in (("Footwell floor", (0, 0.1, -0.02), (1.4, 1.4, 0.04), carpet), ("Firewall", (0, 0.55, 0.4), (1.4, 0.04, 1.0), dark),
                              ("Footwell side", (-0.45, 0.1, 0.4), (0.04, 1.4, 1.0), dark), ("Footwell roof", (0, 0.1, 0.85), (1.4, 1.4, 0.04), dark)):
            self.objs.append(cube(name, P + Vector(c), d, m))
        self.objs.append(parts.rounded_box("Pedal bracket", P + Vector((0, 0.50, 0.64)), (0.09, 0.06, 0.12), metal, bevel=0.008))
        self.pivot = bpy.data.objects.new("Pedal pivot", None)
        bpy.context.collection.objects.link(self.pivot)
        self.pivot.location = P + Vector((0, 0.45, 0.62))
        pv = self.pivot
        self.objs.append(parts.cylinder_x("Pedal pivot pin", 0.012, -0.055, 0.055, 0.0, 0.0, metal, pv, n=16))
        self.objs.append(parts.rounded_box("Pedal arm upper", (0, -0.015, -0.13), (0.026, 0.020, 0.27), metal, pv, bevel=0.006, rot=(math.radians(-6), 0, 0)))
        self.objs.append(parts.rounded_box("Pedal arm lower", (0, -0.065, -0.36), (0.026, 0.020, 0.22), metal, pv, bevel=0.006, rot=(math.radians(-22), 0, 0)))
        tilt = math.radians(30)
        pad_c = Vector((0, -0.10, -0.47))
        n = Vector((0, -math.cos(tilt), -math.sin(tilt)))         # the pad's -Y face after the X rotation: its normal points at the foot
        along = Vector((0, math.sin(tilt), -math.cos(tilt)))     # the pad's -Z axis after the rotation: down the pad face
        self.objs.append(parts.rounded_box("Pedal pad", pad_c, (0.13, 0.028, 0.095), rubber, pv, bevel=0.008, rot=(tilt, 0, 0)))
        for k in range(5):                                       # raised ribs on the rubber pad
            self.objs.append(parts.rounded_box(f"Pedal rib {k}", pad_c + n * 0.016 + along * (-0.036 + 0.018 * k), (0.11, 0.006, 0.006), rubber, pv,
                                               bevel=0.002, rot=(tilt, 0, 0)))
        coils = [Vector((0.0, -0.03 + 0.012 * math.cos(6 * math.pi * i / 40), -0.12 - 0.12 * i / 40 + 0.012 * math.sin(6 * math.pi * i / 40))) for i in range(41)]
        spring = parts.tube_curve("Pedal return spring", coils, 0.0025, metal, pv)
        spring.location = (0.02, 0, 0)
        self.objs.append(spring)
        self.objs.append(parts.rounded_box("Sole", pad_c + n * 0.030 + along * 0.06, (0.112, 0.024, 0.29), sole_m, pv, bevel=0.010, rot=(tilt, 0, 0)))
        for k in range(7):                                       # tread grooves on the sole edge
            self.objs.append(parts.rounded_box(f"Sole tread {k}", pad_c + n * 0.030 + along * (-0.06 + 0.04 * k) + Vector((0.057, 0, 0)), (0.004, 0.026, 0.012), rubber, pv,
                                               bevel=0.001, rot=(tilt, 0, 0)))
        self.objs.append(parts.rounded_box("Shoe", pad_c + n * 0.085 + along * 0.07, (0.106, 0.085, 0.27), shoe_m, pv, bevel=0.022, segments=5, rot=(tilt, 0, 0)))
        self.objs.append(parts.rounded_box("Shoe heel collar", pad_c + n * 0.11 + along * 0.16, (0.10, 0.07, 0.10), shoe_m, pv, bevel=0.018, segments=4, rot=(tilt, 0, 0)))
        heel = pad_c + n * 0.09 + along * 0.17
        shin = Vector((0, -math.sin(math.radians(55)), math.cos(math.radians(55))))
        ankle = heel + n * 0.10 - along * 0.07          # up the back of the shoe: the leg meets it at the ankle, not at the heel
        leg = parts.tube_curve("Trouser leg", [ankle, ankle + shin * 0.30, ankle + shin * 0.60], 0.052, trousers, pv)
        self.objs.append(leg)
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
