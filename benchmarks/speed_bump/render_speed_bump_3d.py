"""EP.03 speed bumps: 100 % 3D renderer. Every picture element is a Blender object: the CC0 sedan, the bumps, the road, the labels, banners, peak read-outs,
the true-scale body-height trace (3D tubes) and the closing peak-acceleration comparison (3D bars and 3D text). Nothing is drawn in 2D afterwards:
the compose step only stacks the rendered images.

Per film frame 1..640: panel "hump" (1080x560), panel "short" (1080x560), panel "trace" (1080x260). Frames 641..960: one "card" render (1080x1400).
One real car model is posed twice (hump simulation, short-bump simulation): literally the same car. Poses come from speed_bump_motion with the car's
MEASURED wheelbase; not calibrated ("physically_calibrated": False). Slow motion is a property of the shot.
"""
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
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402
from benchmarks.speed_bump import speed_bump_motion as sim  # noqa: E402
from benchmarks.speed_bump.speed_bump_timeline import Timeline  # noqa: E402

material, cube = base.material, base.cube
PANEL = (1080, 560)
TRACE = (1080, 260)
CARD = (1080, 1400)
COLORS = {"hump": (0.35, 0.78, 1.0), "short": (1.0, 0.66, 0.24)}
WHITE, SOFT = (1.0, 1.0, 1.0), (0.82, 0.86, 0.92)
CHAR_W = 0.58          # average character width / size of the built-in font (used to size plates)


def arguments():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--end", type=int, default=0)
    p.add_argument("--frames", type=str, default="")
    p.add_argument("--preview", action="store_true")
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return p.parse_args(argv)


# ----------------------------------------------------------------------------- 3D text and plates
_MATS: dict = {}


def emissive(name, color, strength=1.0, alpha=1.0):
    key = (name, color, strength, alpha)
    if key not in _MATS:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        b = m.node_tree.nodes.get("Principled BSDF")
        b.inputs["Base Color"].default_value = (*color, 1)
        b.inputs["Emission Color"].default_value = (*color, 1)
        b.inputs["Emission Strength"].default_value = strength
        b.inputs["Roughness"].default_value = 1.0
        b.inputs["Alpha"].default_value = alpha
        _MATS[key] = m
    return _MATS[key]


def set_emissive(m, color, strength):
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Emission Color"].default_value = (*color, 1)
    b.inputs["Emission Strength"].default_value = strength


def text3d(scene, name, body, size, loc, color=WHITE, align="CENTER", parent=None, rot=(0, 0, 0), strength=1.0):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body, cu.size, cu.align_x, cu.align_y = body, size, align, "CENTER"
    cu.extrude = 0.0
    ob = bpy.data.objects.new(name, cu)
    scene.collection.objects.link(ob)
    ob.data.materials.append(emissive(name + " mat", color, strength))
    if parent is not None:
        ob.parent = parent
    ob.location, ob.rotation_euler = loc, rot
    ob.visible_shadow = False
    return ob


def plate3d(scene, name, center, size_xy, color=(0.04, 0.055, 0.085), alpha=0.86, parent=None, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    ob = bpy.context.object
    ob.name = name
    ob.scale = (size_xy[0], size_xy[1], 0.004)
    ob.data.materials.append(emissive(name + " mat", color, 0.35, alpha))
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    scene.collection.objects.link(ob)
    if parent is not None:
        ob.parent = parent
    ob.location, ob.rotation_euler = center, rot
    ob.visible_shadow = False
    return ob


def set_text(ob, body):
    if ob.data.body != body:
        ob.data.body = body


def show(ob, on):
    ob.hide_render = not on
    ob.hide_viewport = not on
    for ch in ob.children_recursive:
        ch.hide_render = not on
        ch.hide_viewport = not on


def new_scene(name, size, samples, preview, world_color):
    sc = bpy.data.scenes.new(name)
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 7 if preview else samples
    sc.cycles.use_denoising = True
    k = 3 if preview else 1
    sc.render.resolution_x, sc.render.resolution_y = size[0] // k, size[1] // k
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.view_transform = "Standard"
    sc.world = bpy.data.worlds.new(name + " world")
    sc.world.use_nodes = True
    bg = sc.world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (*world_color, 1)
    bg.inputs["Strength"].default_value = 1.0
    return sc


def render(scene, path):
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True, scene=scene.name)
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ----------------------------------------------------------------------------- panel scene (car, bumps, 3D HUD)
def build_hud(scene, cam, panel: str):
    """HUD items for one panel, parented to the camera 2 m in front (frame at that distance: 1.714 x 0.889 m)."""
    root = bpy.data.objects.new(f"HUD {panel}", None)
    scene.collection.objects.link(root)
    root.parent = cam
    root.location = (0, 0, -2.0)
    hud = {"root": root}
    col = COLORS[panel]
    b = sim.BUMPS[panel]
    ly = 0.36 if panel == "hump" else -0.36          # lower panel's label sits at its bottom so the centre banner never covers it
    plate3d(scene, f"label plate {panel}", (-0.60, ly, 0), (0.46, 0.125), parent=root)
    text3d(scene, f"label {panel}", b["label"], 0.054, (-0.82, ly + 0.026, 0.003), col, "LEFT", root)
    text3d(scene, f"dims {panel}", f"{b['length']:.1f} m long, {b['height'] * 100:.1f} cm high", 0.032, (-0.82, ly - 0.027, 0.003), SOFT, "LEFT", root)
    hud["peak_plate"] = plate3d(scene, f"peak plate {panel}", (0.455, -0.36 if panel == "hump" else -0.36, 0), (0.78, 0.095), parent=root)
    hud["peak"] = text3d(scene, f"peak {panel}", "", 0.046, (0.08, -0.36, 0.003), col, "LEFT", root)
    if panel == "hump":
        plate3d(scene, "speed plate", (0.57, 0.36, 0), (0.56, 0.125), parent=root)
        hud["speed"] = text3d(scene, "speed", "", 0.07, (0.36, 0.385, 0.003), WHITE, "LEFT", root)
        hud["slow"] = text3d(scene, "slow", "", 0.03, (0.36, 0.318, 0.003), SOFT, "LEFT", root)
    else:
        hud["banner_plate"] = plate3d(scene, "banner plate", (0, 0.355, 0), (1.52, 0.17), parent=root)
        hud["banner"] = text3d(scene, "banner", "", 0.082, (0, 0.355, 0.003), WHITE, "CENTER", root)
    return hud


def pose_car(root, body, wheels, geom, rec, idx, lane_x):
    y_front = float(rec["x"][idx])
    root.location = (lane_x, y_front - geom["front_axle"], 0.0)
    body.location = (0, 0, float(0.5 * (rec["zf"][idx] + rec["zr"][idx])))
    body.rotation_euler = (float(rec["pitch"][idx]), 0, 0)
    for wkey, w in wheels.items():
        front = wkey.startswith("front")
        road_z = float(rec["wf"][idx] if front else rec["wr"][idx])
        w["node"].location = (w["base"].x, w["base"].y, w["base"].z + road_z)
        w["node"].rotation_euler = (-(y_front - geom["front_axle"] + w["base"].y) / geom["tyre_radius"], 0, 0)
    return y_front


# ----------------------------------------------------------------------------- trace scene (3D tubes)
class TraceScene:
    X0, X1, Y_LO, Y_HI = -4.4, 4.9, -0.80, 0.62        # plot area in world units (1 unit = 100 px)
    LO, HI = -2.0, 7.0                                 # cm

    def __init__(self, preview):
        self.sc = new_scene("trace", TRACE, 24, preview, (0.02, 0.028, 0.045))
        cam = bpy.data.objects.new("TraceCam", bpy.data.cameras.new("TraceCam"))
        self.sc.collection.objects.link(cam)
        cam.location = (0, 0, 10)
        cam.data.type, cam.data.ortho_scale = "ORTHO", 10.8
        self.sc.camera = cam
        text3d(self.sc, "t title", "BODY HEIGHT, TRUE SCALE (cm)", 0.2, (-5.2, 1.02, 0), SOFT, "LEFT")
        text3d(self.sc, "t foot", "SIMULATION, ASSUMED CAR - NOT A MEASUREMENT", 0.16, (-5.2, -1.12, 0), (0.75, 0.8, 0.88), "LEFT")
        text3d(self.sc, "t l1", "LONG HUMP", 0.2, (-3.6, 0.82, 0), COLORS["hump"], "LEFT")
        text3d(self.sc, "t l2", "SHORT BUMP", 0.2, (-1.4, 0.82, 0), COLORS["short"], "LEFT")
        for c in (0, 2, 4, 6):
            y = self.y(c)
            line = cube(f"grid {c}", (0.25, y, -0.01), (self.X1 - self.X0 + 0.2, 0.012 if c else 0.025, 0.002), emissive(f"grid{c}", (0.55, 0.58, 0.65), 0.6))
            self._move(line)
            t = text3d(self.sc, f"tick {c}", f"{c}", 0.19, (self.X0 - 0.35, y, 0), SOFT, "CENTER")
        self.live = []

    def _move(self, ob):
        for c in list(ob.users_collection):
            c.objects.unlink(ob)
        self.sc.collection.objects.link(ob)

    def y(self, cm):
        return self.Y_LO + (cm - self.LO) / (self.HI - self.LO) * (self.Y_HI - self.Y_LO)

    def render(self, tl: Timeline, seg_id: str, t_sim: float, path):
        for ob in self.live:
            bpy.data.objects.remove(ob, do_unlink=True)
        self.live = []
        ta, tb = tl.range[seg_id]
        ts = np.linspace(ta, t_sim, 90)
        for k in ("hump", "short"):
            pts = [(self.X0 + (t - ta) / (tb - ta) * (self.X1 - self.X0), self.y(tl.body_cm(seg_id, k, float(t))), 0.0) for t in ts]
            cu = bpy.data.curves.new(f"trace {k}", "CURVE")
            cu.dimensions, cu.bevel_depth, cu.bevel_resolution = "3D", 0.035, 2
            sp = cu.splines.new("POLY")
            sp.points.add(len(pts) - 1)
            for p, (x, y, z) in zip(sp.points, pts):
                p.co = (x, y, z, 1)
            ob = bpy.data.objects.new(f"trace {k}", cu)
            self.sc.collection.objects.link(ob)
            ob.data.materials.append(emissive(f"trace {k} mat", COLORS[k], 1.0))
            self.live.append(ob)
            bpy.ops.mesh.primitive_uv_sphere_add(radius=0.07, location=pts[-1])
            dot = bpy.context.object
            dot.data.materials.append(emissive(f"dot {k} mat", COLORS[k], 1.0))
            self._move(dot)
            self.live.append(dot)
        return render(self.sc, path)


# ----------------------------------------------------------------------------- card scene (3D bars)
class CardScene:
    def __init__(self, tl: Timeline, preview):
        self.tl = tl
        self.sc = new_scene("card", CARD, 24, preview, (0.035, 0.05, 0.085))
        cam = bpy.data.objects.new("CardCam", bpy.data.cameras.new("CardCam"))
        self.sc.collection.objects.link(cam)
        cam.data.lens, cam.data.sensor_fit, cam.data.sensor_width = 34, "HORIZONTAL", 36
        self.sc.camera = cam
        self.cam = cam
        sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
        sun.data.energy = 2.6
        sun.rotation_euler = (math.radians(50), 0, math.radians(-25))
        self.sc.collection.objects.link(sun)
        floor = cube("card floor", (0, -1.5, -0.05), (18, 11, 0.1), material("card floor mat", (0.05, 0.06, 0.09), rough=0.6))
        self._move(floor)
        self.speeds = [("C", 10), ("A", 20), ("B", 30)]
        self.bars = {}
        for gi, (sid, kmh) in enumerate(self.speeds):
            gx = (gi - 1) * 3.5
            for j, key in enumerate(("hump", "short")):
                m = emissive(f"bar {sid}{key}", COLORS[key], 0.25)
                bar = cube(f"bar {sid}{key}", (gx + (-0.55 if j == 0 else 0.55), 0, 0.5), (1.0, 1.0, 1.0), m)
                self._move(bar)
                val = tl.peaks[sid][key]["peak_body_g"]
                lab = text3d(self.sc, f"val {sid}{key}", f"{val:.2f}", 0.42, (gx + (-0.55 if j == 0 else 0.55), -0.6, 1.0), WHITE, "CENTER", rot=(math.pi / 2, 0, 0))
                self.bars[(sid, key)] = (bar, m, lab, val)
            text3d(self.sc, f"kmh {sid}", f"{kmh} km/h", 0.5, (gx, -1.35, 0.02), WHITE, "CENTER", rot=(math.pi / 2, 0, 0))
        text3d(self.sc, "card title", "PEAK BODY ACCELERATION", 0.62, (0, 0, 6.9), WHITE, "CENTER", rot=(math.pi / 2, 0, 0))
        text3d(self.sc, "card sub", "same car, same 7.5 cm height (simulation, assumed values)", 0.27, (0, 0, 6.35), SOFT, "CENTER", rot=(math.pi / 2, 0, 0))
        self.spot = text3d(self.sc, "card spot", "", 0.4, (0, 0, 5.75), (1.0, 0.86, 0.47), "CENTER", rot=(math.pi / 2, 0, 0))
        self.how = text3d(self.sc, "card how", "IT IS HOW QUICKLY THE ROAD LIFTS YOUR CAR", 0.3, (0, 0, 5.75), WHITE, "CENTER", rot=(math.pi / 2, 0, 0))
        self.shape = text3d(self.sc, "card shape", "SHAPE CHANGES THE RIDE", 0.5, (0, 0, 5.15), (1.0, 0.86, 0.47), "CENTER", rot=(math.pi / 2, 0, 0))
        text3d(self.sc, "leg1", "LONG HUMP 3.7 m", 0.3, (-4.4, -2.9, 0.02), COLORS["hump"], "LEFT", rot=(math.pi / 2, 0, 0))
        text3d(self.sc, "leg2", "SHORT BUMP 0.9 m", 0.3, (0.4, -2.9, 0.02), COLORS["short"], "LEFT", rot=(math.pi / 2, 0, 0))
        self.progress = cube("progress", (0, -3.9, 0.05), (1.0, 0.12, 0.1), emissive("progress mat", (1.0, 0.86, 0.47), 1.0))
        self._move(self.progress)

    def _move(self, ob):
        for c in list(ob.users_collection):
            c.objects.unlink(ob)
        self.sc.collection.objects.link(ob)

    def render(self, frame: int, path):
        n = frame - sim.PASS_FRAMES              # 1..320
        grow = min(1.0, n / 75.0)
        grow = 1 - (1 - grow) ** 3
        lit = Timeline.spotlight(n)
        for gi, (sid, kmh) in enumerate(self.speeds):
            dim = 1.0 if lit is None or lit == gi else 0.2
            for key in ("hump", "short"):
                bar, m, lab, val = self.bars[(sid, key)]
                h = max(0.001, val / 1.2 * 4.2 * grow)
                bar.scale = (1.0, 1.0, h)
                bar.location.z = h / 2
                col = tuple(c * dim for c in COLORS[key])
                set_emissive(m, col, 0.25 + 0.0 * dim)
                lab.location.z = h + 0.42
                show(lab, grow >= 1.0)
                lab.data.materials[0].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = dim
        set_text(self.spot, self.tl.spotlight_text(n))
        show(self.spot, bool(self.tl.spotlight_text(n)))
        show(self.how, frame >= 880)
        show(self.shape, frame >= 801)
        w = 9.6 * n / 320.0
        self.progress.scale = (max(w, 0.01), 0.12, 0.1)
        self.progress.location.x = -4.8 + w / 2
        sway = 0.9 * math.sin(n / 320.0 * math.pi * 2 * 0.75)
        self.cam.location = (sway, -9.6, 6.4)
        self.cam.rotation_euler = (Vector((0, -0.4, 3.0)) - self.cam.location).to_track_quat("-Z", "Y").to_euler()
        return render(self.sc, path)


def main():
    args = arguments()
    args.out.mkdir(parents=True, exist_ok=True)
    root, body, wheels, geom = base.load_source_car(args.source)
    scene = bpy.context.scene
    scene.name = "panels"
    k = 3 if args.preview else 1
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 7 if args.preview else 24
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = PANEL[0] // k, PANEL[1] // k
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.exposure = -1.3
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    sun_to = cinematic.sun_vector((-0.5, -0.8), 36.0)
    cinematic.apply_sky(scene, sun_to, strength=0.25, dust=0.5)
    bpy.ops.object.light_add(type="SUN")
    key = bpy.context.object
    key.data.energy, key.data.angle = 3.4, 0.03
    key.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()
    road = material("Asphalt", (0.07, 0.07, 0.075), rough=0.85)
    base.asphalt_grain(road)
    cube("Road", (0, 10, -0.05), (12.0, 80, 0.1), road)
    cube("Verge L", (-7.2, 10, -0.06), (2.4, 80, 0.1), material("Verge", (0.22, 0.2, 0.14), rough=1.0))
    cube("Verge R", (7.2, 10, -0.06), (2.4, 80, 0.1), material("Verge2", (0.22, 0.2, 0.14), rough=1.0))
    yellow = material("Bump paint", (0.9, 0.62, 0.05), rough=0.5)
    bumps = {}
    for kb, b in sim.BUMPS.items():
        n = 40
        pts = [(i / n * b["length"], b["height"] * math.sin(math.pi * i / n)) for i in range(n + 1)] + [(b["length"], 0.0)]
        ob = base.extruded_profile(f"Bump {kb}", pts, -1.4, 1.4, yellow)
        ob.rotation_euler = (0, 0, math.pi / 2)
        bumps[kb] = ob
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.lens, cam.data.sensor_fit, cam.data.sensor_width = 42, "HORIZONTAL", 36
    huds = {p: build_hud(scene, cam, p) for p in ("hump", "short")}

    car_params = dict(sim.CAR, wheelbase=geom["wheelbase"])
    tl = Timeline(geom["wheelbase"])
    trace = TraceScene(args.preview)
    card = CardScene(tl, args.preview)
    LANE_X = 0.0
    frames = [int(x) for x in args.frames.split(",")] if args.frames else list(range(args.start, args.end + 1))
    result, checks = [], []
    for f in frames:
        t_start = time.time()
        info = {"frame": f}
        if f > sim.PASS_FRAMES:
            path = args.out / f"frame_{f:04d}_card.png"
            checks.append({"frame": f, "panel": "card", "sha256": card.render(f, path)})
        else:
            seg, t_sim = sim.frame_to_pass(f)
            info.update(segment=seg["id"], sim_time=round(t_sim, 4))
            banner = tl.banner_at(f)
            for panel in ("hump", "short"):
                for kb, ob in bumps.items():
                    base.set_visible(ob, kb == panel)
                for p, h in huds.items():
                    show(h["root"], p == panel)
                rec = tl.recs[(seg["id"], panel)]
                idx = min(int(t_sim * sim.FPS), len(rec["t"]) - 1)
                y_front = pose_car(root, body, wheels, geom, rec, idx, LANE_X)
                cy = y_front - 1.0
                base.set_camera(cam, (LANE_X + 6.2, cy, 0.95), (LANE_X, cy, 0.62))
                h = huds[panel]
                reached = t_sim >= tl.peak_time[(seg["id"], panel)]
                set_text(h["peak"], f"PEAK BODY ACCEL {tl.peaks[seg['id']][panel]['peak_body_g']:.2f} g" if reached else "")
                show(h["peak_plate"], reached)
                show(h["peak"], reached)
                if panel == "hump":
                    set_text(h["speed"], f"{seg['kmh']:.0f} km/h")
                    set_text(h["slow"], f"SLOW MOTION x{seg['slow']:.2f}")
                else:
                    show(h["banner_plate"], banner is not None)
                    show(h["banner"], banner is not None)
                    if banner:
                        set_text(h["banner"], banner[0])
                        h["banner_plate"].data.materials[0].node_tree.nodes["Principled BSDF"].inputs["Alpha"].default_value = 0.86 * banner[1]
                        h["banner"].data.materials[0].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = banner[1]
                path = args.out / f"frame_{f:04d}_{panel}.png"
                checks.append({"frame": f, "panel": panel, "sha256": render(scene, path)})
                info[panel] = {"y_front": round(y_front, 3), "body_rise_cm": round(100 * float(0.5 * (rec["zf"][idx] + rec["zr"][idx])), 2),
                               "pitch_deg": round(math.degrees(float(rec["pitch"][idx])), 2), "accel_g": round(float(rec["gf"][idx]), 3)}
            path = args.out / f"frame_{f:04d}_trace.png"
            checks.append({"frame": f, "panel": "trace", "sha256": trace.render(tl, seg["id"], t_sim, path)})
        info["render_seconds"] = round(time.time() - t_start, 1)
        result.append(info)
        print("BUMP_FRAME " + json.dumps(info), flush=True)
    proof = {"renderer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "geometry": geom, "preview": bool(args.preview),
             "checksums": checks, "telemetry": result, "physically_calibrated": False, "all_3d": True}
    (args.out / "bump-proof.json").write_text(json.dumps(proof, indent=1))


main()
