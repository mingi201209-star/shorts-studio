"""EP.03 speed bumps: 100 % 3D renderer. The picture contains ONLY the 3D scene: the CC0 sedan, the two bumps, the road and the sky. No graphs, no text, no
overlay plates; the explanation is the 3D model plus the narration (and the burned-in captions of the narration).

One real car model is posed twice per frame (long-hump simulation, short-bump simulation): literally the same car at the same speed. Five camera set-ups
(rear 3/4, side, front 3/4, front-wheel close-up, top) give real cuts. Layout "stack": hump above, short bump below (1080x700 each); layout "side": hump left,
short bump right (540x1400 each). Poses come from speed_bump_motion with the car's MEASURED wheelbase; not calibrated ("physically_calibrated": False).
Slow motion is a property of the shot.
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
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402
from benchmarks.speed_bump import speed_bump_motion as sim  # noqa: E402
from benchmarks.speed_bump.speed_bump_timeline import Timeline  # noqa: E402

material, cube = base.material, base.cube
SIZES = {"stack": (1080, 960), "side": (540, 1920)}


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


def spring_curve(name, bottom, top, mat, turns=7, radius=0.07):
    """Helical coil spring as a beveled curve between two points."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions, cu.bevel_depth, cu.bevel_resolution = "3D", 0.011, 2
    sp = cu.splines.new("POLY")
    n = turns * 16
    sp.points.add(n)
    for i, pt in enumerate(sp.points):
        t = i / n
        a = 2 * math.pi * turns * t
        pt.co = (bottom[0] + radius * math.cos(a), bottom[1] + radius * math.sin(a), bottom[2] + (top[2] - bottom[2]) * t, 1)
    ob = bpy.data.objects.new(name, cu)
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(mat)
    return ob


class XRay:
    """Translucent body (the sedan's body materials copied) with a scan-line reveal: a plane sweeps from the front of the car to the rear (in world space, so it
    follows the car); everything the sweep has passed turns almost transparent with a blue edge glow, and the sweep line itself flares. A spring + damper per
    wheel follow the simulation (spring bottom on the wheel hub, top on the body mount); the spring glows hotter the more it is compressed. Wheels, tyres and
    brakes stay solid. A generic suspension drawing."""

    SOFT = 0.35      # width (m) of the sweep line
    FRONT = 1.6      # sweep position ahead of the front axle when nothing is translucent yet
    REAR = 4.3       # ... and behind it when the whole body is translucent

    def __init__(self, root, wheels):
        self.wheels = wheels
        wheel_parts = set()
        for w in wheels.values():
            wheel_parts.update(o.name for o in w["node"].children_recursive)
        self.wipes = []
        seen = {}
        for o in [m for m in root.children_recursive if m.type == "MESH"]:
            if o.name in wheel_parts:
                continue
            for i, m in enumerate(o.data.materials):
                if m is None:
                    continue
                if m.name not in seen:
                    seen[m.name] = self._reveal_material(m)
                o.data.materials[i] = seen[m.name]
        self.live = []
        self.live_mats = []
        self.mark = material("Rest mark", (0.95, 0.95, 1.0), rough=0.4, emission=3.0)
        self.peak_mat = material("Peak mark", (1.0, 0.1, 0.1), rough=0.4, emission=6.0)

    def _reveal_material(self, m):
        c = m.copy()
        c.name = m.name + " reveal"
        nt = c.node_tree
        bsdf = nt.nodes.get("Principled BSDF")
        alpha0 = bsdf.inputs["Alpha"].default_value

        def node(kind, **kw):
            n = nt.nodes.new(kind)
            for k, v in kw.items():
                setattr(n, k, v)
            return n

        def math(op, a=None, b=None, clamp=False):
            n = node("ShaderNodeMath", operation=op, use_clamp=clamp)
            for i, v in enumerate((a, b)):
                if v is None:
                    continue
                if isinstance(v, (int, float)):
                    n.inputs[i].default_value = v
                else:
                    nt.links.new(v, n.inputs[i])
            return n.outputs[0]

        geo = node("ShaderNodeNewGeometry")
        sep = node("ShaderNodeSeparateXYZ")
        nt.links.new(geo.outputs["Position"], sep.inputs[0])
        wipe = node("ShaderNodeValue")
        self.wipes.append(wipe)
        mask = math("MULTIPLY", math("SUBTRACT", sep.outputs[1], wipe.outputs[0]), 1.0 / self.SOFT, clamp=True)
        nt.links.new(math("ADD", math("MULTIPLY", mask, -0.8 * alpha0), alpha0), bsdf.inputs["Alpha"])
        lw = node("ShaderNodeLayerWeight")
        lw.inputs["Blend"].default_value = 0.35
        edge = math("MULTIPLY", math("MULTIPLY", lw.outputs["Facing"], mask), 8.0)
        flare = math("MULTIPLY", math("MULTIPLY", mask, math("SUBTRACT", 1.0, mask)), 28.0)
        nt.links.new(math("ADD", edge, flare), bsdf.inputs["Emission Strength"])
        bsdf.inputs["Emission Color"].default_value = (0.25, 0.65, 1.0, 1.0)
        return c

    def set_factor(self, xf, y_front):
        wipe = y_front + self.FRONT - (self.FRONT + self.REAR) * xf
        for w in self.wipes:
            w.outputs[0].default_value = wipe

    def clear(self):
        for ob in self.live:
            bpy.data.objects.remove(ob, do_unlink=True)
        for m in self.live_mats:
            bpy.data.materials.remove(m)
        self.live, self.live_mats = [], []

    def build(self, body, xf, comp, road_dz, mount_dz, peak):
        """comp: spring compression (m, signed) of the front and the rear axle at this frame."""
        self.clear()
        if xf < 0.02:
            return
        bpy.context.view_layer.update()
        damper = material("Damper", (0.2, 0.8, 1.0), rough=0.4, emission=0.4)
        self.live_mats.append(damper)
        for wkey, w in self.wheels.items():
            side = 1.0 if w["base"].x > 0 else -1.0
            hub = w["node"].matrix_world.translation
            mount = body.matrix_world @ Vector((w["base"].x - 0.05 * side, w["base"].y, w["base"].z + 0.42))
            dx = 0.12 * side
            heat = min(1.0, abs(comp["front" if wkey.startswith("front") else "rear"]))      # comp = spring squeeze rate / the short bump's peak rate
            spring = material("Spring " + wkey, (1.0, 0.25 + 0.45 * heat, 0.05 + 0.1 * heat), rough=0.4, emission=0.8 + 3.0 * heat)   # stays orange-yellow (never white) at the peak
            self.live_mats.append(spring)
            self.live.append(spring_curve(f"spring {wkey}", (hub.x + dx, hub.y, hub.z + 0.05), (mount.x + dx, mount.y, mount.z), spring))
            bpy.ops.mesh.primitive_cylinder_add(radius=0.022, depth=1.0, location=((hub.x + mount.x) / 2 + dx, hub.y + 0.1, (hub.z + mount.z) / 2))
            rod = bpy.context.object
            rod.scale = (1, 1, max(0.05, mount.z - hub.z))
            rod.data.materials.append(damper)
            self.live.append(rod)
            # rest-length marks (in the scene, not an overlay): a thin white ruler beside the live spring that spans the spring's length at rest, a tick at the
            # body's rest mount height, and (after the peak) a red tick at the height the body mount reached at the peak compression
            rest_bottom = hub.z - road_dz[wkey] + 0.05
            rest_top = mount.z - mount_dz[wkey]
            ruler_y = hub.y - 0.2
            bpy.ops.mesh.primitive_cylinder_add(radius=0.007, depth=1.0, location=(hub.x + dx, ruler_y, (rest_bottom + rest_top) / 2))
            ruler = bpy.context.object
            ruler.scale = (1, 1, max(0.05, rest_top - rest_bottom))
            ruler.data.materials.append(self.mark)
            self.live.append(ruler)
            for zt in (rest_bottom, rest_top):
                bpy.ops.mesh.primitive_cube_add(size=1.0, location=(hub.x + dx, ruler_y, zt))
                tick = bpy.context.object
                tick.scale = (0.05, 0.12, 0.008)
                tick.data.materials.append(self.mark)
                self.live.append(tick)
            if peak["active"][wkey]:
                bpy.ops.mesh.primitive_cube_add(size=1.0, location=(hub.x + dx, ruler_y, rest_top + peak["dz"][wkey]))
                pk = bpy.context.object
                pk.scale = (0.05, 0.2, 0.012)
                pk.data.materials.append(self.peak_mat)
                self.live.append(pk)


class Trail:
    """A glowing 3D tube drawn behind a moving point (the front wheel hub, or the roof of the car): the path that point has travelled so far in this pass."""

    def __init__(self, name, color):
        self.mat = material(name, color, rough=0.3, emission=9.0)
        self.cu = bpy.data.curves.new(name, "CURVE")
        self.cu.dimensions, self.cu.bevel_depth, self.cu.bevel_resolution = "3D", 0.03, 2
        self.ob = bpy.data.objects.new(name, self.cu)
        bpy.context.collection.objects.link(self.ob)
        self.ob.data.materials.append(self.mat)

    def set(self, pts):
        self.cu.splines.clear()
        self.ob.hide_render = len(pts) < 2
        if len(pts) < 2:
            return
        sp = self.cu.splines.new("POLY")
        sp.points.add(len(pts) - 1)
        for pt, co in zip(sp.points, pts):
            pt.co = (co[0], co[1], co[2], 1)


def spring_rate(rec, key, idx, span=6):
    """How fast the spring is being squeezed or released (m/s, signed) around sample idx."""
    a, b = max(0, idx - span), min(len(rec[key]) - 1, idx + span)
    return float(rec[key][b] - rec[key][a]) / float(rec["t"][b] - rec["t"][a]) if b > a else 0.0


def pose_car(root, body, wheels, geom, rec, idx, gaps=None, road_dz=None):
    gaps = {} if gaps is None else gaps
    y_front = float(rec["x"][idx])
    root.location = (0.0, y_front - geom["front_axle"], 0.0)
    body.location = (0, 0, float(0.5 * (rec["zf"][idx] + rec["zr"][idx])))
    body.rotation_euler = (float(rec["pitch"][idx]), 0, 0)
    for wkey, w in wheels.items():
        front = wkey.startswith("front")
        # unsprung (wheel) displacement, drawn on the rigid tyre envelope (+-4 mm): the tyre never cuts into the bump and never floats
        road_z = sim.visual_wheel_z(rec["uf"][idx] if front else rec["ur"][idx], rec["wf"][idx] if front else rec["wr"][idx])
        gaps[wkey] = road_z - float(rec["wf"][idx] if front else rec["wr"][idx])
        w["node"].location = (w["base"].x, w["base"].y, w["base"].z + road_z)
        if road_dz is not None:
            road_dz[wkey] = road_z
        w["node"].rotation_euler = (-(y_front - geom["front_axle"] + w["base"].y) / geom["tyre_radius"], 0, 0)
    return y_front


#: lens shift (in sensor widths) per camera kind in the tall 540x1920 "side" layout: the subject sits low in a very tall panel, so the view is moved down
#: to put the car in the middle of the panel instead of under two thirds of sky
SIDE_SHIFT = {"front3q": -0.85, "rear3q": -0.85, "high3q": -0.5, "wheel": -0.4, "tyre": -0.4, "low3q": -0.7, "spring": -0.4}


def place_camera(cam, kind, y, layout="stack"):
    """y: the front axle's position along the road. Travel is +Y."""
    d = cam.data
    d.sensor_fit, d.sensor_width = "HORIZONTAL", 36
    d.shift_y = SIDE_SHIFT.get(kind, 0.0) if layout == "side" else 0.0
    if kind == "side":                      # low side view, travel left to right
        d.lens = 42
        base.set_camera(cam, (6.2, y - 1.0, 0.95), (0.0, y - 1.0, 0.62))
    elif kind == "rear3q":                  # behind and to the left, looking ahead along the bump
        d.lens = 40
        base.set_camera(cam, (-3.0, y - 4.9, 1.5), (0.35, y + 0.1, 0.5))
    elif kind == "front3q":                 # ahead of the car, looking back at it
        d.lens = 38
        base.set_camera(cam, (2.0, y + 3.7, 0.95), (0.0, y - 0.5, 0.5))
    elif kind == "wheel":                   # close on the front wheel
        d.lens = 45
        base.set_camera(cam, (3.6, y - 0.1, 0.5), (0.5, y + 0.35, 0.3))
    elif kind == "profile":                 # low side view that keeps the wheel and the path it has just travelled in frame
        d.lens = 38
        base.set_camera(cam, (5.2, y - 0.4, 0.5), (0.0, y - 0.9, 0.38))
    elif kind == "tyre":                    # very close on the front tyre climbing the face of the bump
        d.lens = 38
        base.set_camera(cam, (2.4, y + 0.5, 0.3), (0.0, y + 0.05, 0.28))
    elif kind == "high3q":                  # high front 3/4 looking down on the car and the bump
        d.lens = 38
        base.set_camera(cam, (3.0, y + 3.0, 2.4), (0.0, y - 0.3, 0.4))
    elif kind == "low3q":                   # low front 3/4 close to the bump: the car fills the panel
        d.lens = 36
        base.set_camera(cam, (3.6, y + 2.2, 0.75), (0.0, y - 0.4, 0.5))
    elif kind == "spring":                  # tight on the front wheel arch, looking slightly down so the ghost body is seen against the road, not the sky
        d.lens = 40
        base.set_camera(cam, (3.3, y + 0.05, 1.0), (0.0, y + 0.05, 0.28))
    elif kind == "front3q_hi":              # raised front 3/4 looking down: asphalt behind the ghost body
        d.lens = 38
        base.set_camera(cam, (2.3, y + 3.3, 2.3), (0.0, y - 0.5, 0.3))
    elif kind == "left":                    # low view from the other side: body heave and pitch against the hub path
        d.lens = 38
        base.set_camera(cam, (-5.2, y - 0.9, 1.5), (0.0, y - 0.9, 0.4))
    elif kind == "side_xray":               # wide side view, raised and looking down: car, ghost body and the spring marks in one frame
        d.lens = 34
        base.set_camera(cam, (5.0, y - 0.9, 1.9), (0.0, y - 0.9, 0.3))
    elif kind == "side_far":                # side view from further back and higher: both bumps and the whole pass
        d.lens = 32
        base.set_camera(cam, (8.0, y - 1.2, 2.2), (0.0, y - 1.2, 0.35))
    elif kind == "top":                     # straight down, travel up the screen
        d.lens = 45
        cam.location = (0.0, y - 0.6, 8.5)
        cam.rotation_euler = (0.0, 0.0, 0.0)
    else:
        raise ValueError(kind)


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
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.exposure = -1.3
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    sun_to = cinematic.sun_vector((-0.5, -0.8), 36.0)
    cinematic.apply_sky(scene, sun_to, strength=0.25, dust=0.5)
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    sun.data.energy, sun.data.angle = 3.4, 0.03
    sun.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()
    road = material("Asphalt", (0.07, 0.07, 0.075), rough=0.85)
    base.asphalt_grain(road)
    cube("Road", (0, 10, -0.05), (12.0, 80, 0.1), road)
    cube("Verge L", (-7.2, 10, -0.06), (2.4, 80, 0.1), material("Verge", (0.22, 0.2, 0.14), rough=1.0))
    cube("Verge R", (7.2, 10, -0.06), (2.4, 80, 0.1), material("Verge2", (0.22, 0.2, 0.14), rough=1.0))
    cube("Centre line", (-3.0, 10, 0.002), (0.12, 80, 0.004), material("Line", (0.8, 0.8, 0.78), rough=0.6))
    yellow = material("Bump paint", (0.9, 0.62, 0.05), rough=0.5)
    bumps = {}
    for kb, b in sim.BUMPS.items():
        n = 40
        pts = [(i / n * b["length"], b["height"] * math.sin(math.pi * i / n)) for i in range(n + 1)] + [(b["length"], 0.0)]
        ob = base.extruded_profile(f"Bump {kb}", pts, -1.4, 1.4, yellow)
        ob.rotation_euler = (0, 0, math.pi / 2)
        bumps[kb] = ob
    sign = material("Sign", (0.45, 1.0, 0.15), rough=0.5, emission=1.0)
    labels = {}
    for kb, text in (("hump", "LONG"), ("short", "SHORT")):
        cu = bpy.data.curves.new("Sign " + kb, "FONT")
        cu.body, cu.size, cu.extrude, cu.align_x, cu.align_y = text, 0.4, 0.03, "CENTER", "CENTER"
        ob = bpy.data.objects.new("Sign " + kb, cu)
        bpy.context.collection.objects.link(ob)
        ob.data.materials.append(sign)
        labels[kb] = ob
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam

    tl = Timeline(geom["wheelbase"], hz=sim.RENDER_HZ)
    xray = XRay(root, wheels) if sim.FILM in ("xray", "explain", "reveal", "final") else None
    hub_trail, roof_trail = Trail("Hub trail", (0.2, 0.9, 1.0)), Trail("Roof trail", (1.0, 0.7, 0.1))
    hub_key = next(k for k in wheels if k.startswith("front") and wheels[k]["base"].x > 0)
    bpy.context.view_layer.update()
    corners = [body.matrix_world @ Vector(c) for o in body.children_recursive if o.type == "MESH" for c in o.bound_box] or [body.matrix_world.translation]
    roof_world0 = Vector((sum(c.x for c in corners) / len(corners), sum(c.y for c in corners) / len(corners), max(c.z for c in corners)))
    roof_local = body.matrix_world.inverted() @ roof_world0
    step = max(1, sim.RENDER_HZ // 100)
    rate_ref = max(v["short"]["peak_spring_rate_ms"] for v in tl.peaks.values())
    frames = [int(x) for x in args.frames.split(",")] if args.frames else list(range(args.start, args.end + 1))
    result, checks = [], []
    for f in frames:
        t_start = time.time()
        seg, t_sim = sim.frame_to_pass(f)
        kind, layout = sim.shot_at(f)
        w, h = SIZES[layout]
        scene.render.resolution_x, scene.render.resolution_y = w // k, h // k
        info = {"frame": f, "segment": seg["id"], "camera": kind, "layout": layout, "sim_time": round(t_sim, 4)}
        for panel in ("hump", "short"):
            for kb, ob in bumps.items():
                base.set_visible(ob, kb == panel)
            rec = tl.recs[(seg["id"], panel)]
            idx = min(int(round(t_sim * sim.RENDER_HZ)), len(rec["t"]) - 1)
            gaps, road_dz = {}, {}
            y_front = pose_car(root, body, wheels, geom, rec, idx, gaps, road_dz)
            if xray is not None:
                xf = sim.xray_factor(f)
                xray.set_factor(xf, y_front)
                mount_dz = {k: float(rec["zf"][idx] if k.startswith("front") else rec["zr"][idx]) for k in wheels}
                ip_f, ip_r = int(np.argmin(rec["df"])), int(np.argmin(rec["dr"]))       # peak compression (spring deflection most negative)
                peak = {"dz": {k: float(rec["zf"][ip_f] if k.startswith("front") else rec["zr"][ip_r]) for k in wheels},
                        "active": {k: bool(idx >= (ip_f if k.startswith("front") else ip_r)) for k in wheels}}
                xray.build(body, xf, {"front": spring_rate(rec, "df", idx) / rate_ref, "rear": spring_rate(rec, "dr", idx) / rate_ref}, road_dz, mount_dz, peak)
            hub_trail.set([]), roof_trail.set([])
            mode = sim.trail_mode(f)
            if mode:
                bpy.context.view_layer.update()
                j0 = max(0, int((sim.SIM_LEAD_M - seg["lead_m"]) / (seg["kmh"] / 3.6) * sim.RENDER_HZ))
                js = list(range(j0, idx + 1, step)) + ([idx] if (idx - j0) % step else [])
                if mode in ("hub", "both"):
                    h = wheels[hub_key]["node"].matrix_world.translation
                    hub_trail.set([(h.x + 0.2, h.y + float(rec["x"][j] - rec["x"][idx]), h.z + float(rec["wf"][j] - rec["wf"][idx])) for j in js])
                if mode in ("roof", "both"):
                    r = body.matrix_world @ roof_local
                    roof_trail.set([(r.x, r.y + float(rec["x"][j] - rec["x"][idx]),
                                     r.z + float(0.5 * (rec["zf"][j] + rec["zr"][j]) - 0.5 * (rec["zf"][idx] + rec["zr"][idx])) + roof_local.y * float(rec["pitch"][j] - rec["pitch"][idx]))
                                    for j in js])
            place_camera(cam, kind, y_front, layout)
            for kb, lab in labels.items():                      # the LONG / SHORT sign of this panel: a 3D sign beside the bump, turned to the camera
                lab.hide_render = kb != panel
            lab = labels[panel]
            lab.location = (math.copysign(2.0, cam.location.x if abs(cam.location.x) > 0.1 else 1.0), sim.BUMPS[panel]["length"] / 2, 0.75)
            lab.rotation_euler = (cam.location - Vector(lab.location)).to_track_quat("Z", "Y").to_euler()
            bpy.context.view_layer.update()
            co = world_to_camera_view(scene, cam, Vector(lab.location))
            sign_in_view = bool(co.z > 0 and 0.08 < co.x < 0.92 and 0.08 < co.y < 0.92)
            path = args.out / f"frame_{f:04d}_{panel}.png"
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            checks.append({"frame": f, "panel": panel, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            info[panel] = {"y_front": round(y_front, 3), "body_rise_cm": round(100 * float(0.5 * (rec["zf"][idx] + rec["zr"][idx])), 2),
                           "pitch_deg": round(math.degrees(float(rec["pitch"][idx])), 2), "accel_g": round(float(rec["gf"][idx]), 3),
                           "wheel_gap_mm": round(1000 * max(abs(g) for g in gaps.values()), 2), "sign_in_view": sign_in_view}
        info["render_seconds"] = round(time.time() - t_start, 1)
        result.append(info)
        print("BUMP_FRAME " + json.dumps(info), flush=True)
    proof = {"renderer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "geometry": geom, "preview": bool(args.preview),
             "checksums": checks, "telemetry": result, "physically_calibrated": False, "all_3d": True, "overlays": "none", "film": sim.FILM}
    (args.out / "bump-proof.json").write_text(json.dumps(proof, indent=1))


main()
