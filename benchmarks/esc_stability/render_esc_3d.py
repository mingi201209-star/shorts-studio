"""EP.07 ESC: 100 % 3D renderer (Blender, Cycles CPU). Same CC0 sedan, road and box as EP.06; a wet-looking road; skid marks from the rear
tyres while they slide; and the ESC hardware in the car: yaw-rate sensor, steering-angle sensor on the column, hydraulic unit with brake
lines, and the detailed brake of the outside front wheel (EP.06 parts, mirrored to the right wheel). The car body can be hidden ("xray") so the
hardware shows. Everything that moves comes from esc_motion. No scene text."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from benchmarks.abs_brake import render_abs_3d as abs_r  # noqa: E402
from benchmarks.esc_stability import esc_motion as em  # noqa: E402
from benchmarks.esc_stability import esc_parts as ep  # noqa: E402
from benchmarks.esc_stability import esc_shots as shots  # noqa: E402
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402

material = base.material
REAR = {"rear_left": (-0.709, -1.225), "rear_right": (0.709, -1.225)}


def arguments():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--shots", default="all")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--res-scale", type=float, default=0.5)
    p.add_argument("--samples", type=int, default=16)
    p.add_argument("--film", action="store_true")
    p.add_argument("--frames", default="0-0")
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return p.parse_args(argv)


class SkidRibbons:
    """Rubber marks behind both rear tyres while they slide sideways: a flat ribbon through the tyre positions, rebuilt every frame."""

    def __init__(self):
        self.mat = material("Skid rubber", (0.015, 0.015, 0.017), rough=0.9)
        self.obs = {}
        for key in REAR:
            mesh = bpy.data.meshes.new(f"Skid {key}")
            ob = bpy.data.objects.new(f"Skid {key}", mesh)
            bpy.context.collection.objects.link(ob)
            mesh.materials.append(self.mat)
            self.obs[key] = ob

    def update(self, variant, t):
        pts = em.trail(variant, t)
        for key, (wx, wy) in REAR.items():
            ob = self.obs[key]
            verts, faces = [], []
            prev = None
            for (_, x, y, h) in pts:
                c, s = math.cos(h), math.sin(h)
                px, py = x + wx * c - wy * s, y + wx * s + wy * c
                if prev is not None and math.hypot(px - prev[0], py - prev[1]) > 1.0:   # a gap in the sliding: start a new strip
                    prev = None
                if prev is not None:
                    dx, dy = px - prev[0], py - prev[1]
                    n = math.hypot(dx, dy) or 1.0
                    nx, ny = -dy / n * 0.10, dx / n * 0.10
                    i = len(verts)
                    verts += [(prev[0] + nx, prev[1] + ny, 0.003), (prev[0] - nx, prev[1] - ny, 0.003), (px - nx, py - ny, 0.003), (px + nx, py + ny, 0.003)]
                    faces.append((i, i + 1, i + 2, i + 3))
                prev = (px, py)
            mesh = bpy.data.meshes.new(f"Skid {key}")
            mesh.from_pydata(verts, [], faces)
            mesh.materials.append(self.mat)
            old = ob.data
            ob.data = mesh
            bpy.data.meshes.remove(old)


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
    sun_to = cinematic.sun_vector((-0.5, -0.8), 30.0)
    cinematic.apply_sky(scene, sun_to, strength=0.22, dust=1.5)        # overcast-ish: a wet day
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    sun.data.energy, sun.data.angle = 2.6, 0.08
    sun.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()
    abs_r.build_road()
    wet = bpy.data.materials.get("Asphalt")
    bsdf = wet.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = 0.35                   # wet asphalt: sheen and reflections
    box = abs_r.build_box()
    box.location = (0.0, em.BOX_Y + em.BOX_HALF[1], em.BOX_HALF[2])
    skid = SkidRibbons()
    fr = wheels["front_right"]
    spin_m = bpy.data.objects.new("Mirror spin", None)
    bpy.context.collection.objects.link(spin_m)
    spin_m.parent, spin_m.scale = fr["node"], (-1, 1, 1)               # EP.06 parts are built for the left wheel: mirror them to the right
    cut = abs_r.BrakeCutaway(root, {"node": spin_m, "base": fr["base"]})
    cut.fixed.scale = (-1, 1, 1)
    fr_parts = [o for o in fr["node"].children if o.type == "MESH"]
    yaw = ep.YawSensor(root)
    steer_s = ep.SteeringSensor(root)
    hcu = ep.HydraulicUnit(root, {k: w["base"] for k, w in wheels.items()})
    extras = set(cut.parts_spin + cut.parts_fixed + yaw.objs + steer_s.objs + hcu.objs)
    body_meshes = [o for o in root.children_recursive if o.type == "MESH" and o not in extras and not any(o in w["node"].children_recursive for w in wheels.values())]
    ghost = material("Ghost body", (0.75, 0.82, 0.95), rough=0.3)
    gb = ghost.node_tree.nodes.get("Principled BSDF")
    gb.inputs["Alpha"].default_value = 0.10
    gb.inputs["Emission Color"].default_value = (0.55, 0.70, 1.0, 1)
    gb.inputs["Emission Strength"].default_value = 0.15
    original = {ob: [sl.material for sl in ob.material_slots] for ob in body_meshes}

    def set_ghost(on):
        for ob, mats in original.items():
            for sl, m in zip(ob.material_slots, mats):
                sl.material = ghost if on else m

    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam

    def render(sh, variant, path, size):
        st = em.at(variant, sh["t"])
        scene.render.resolution_x, scene.render.resolution_y = round(size[0] * args.res_scale), round(size[1] * args.res_scale)
        root.location = (st["x"], st["y"], 0.0)
        root.rotation_euler = (0, 0, st["heading"])
        body.rotation_euler = (0, -0.02 * max(-1.5, min(1.5, st["yaw_rate"])), 0)        # a little roll in the turn
        for key, wh in wheels.items():
            wh["node"].rotation_mode = "ZXY"
            wh["node"].rotation_euler = (-st["wheel_angle"], 0, st["steer"] if key.startswith("front") else 0.0)
        skid.update(variant, sh["t"])
        force = st["esc_force"] / 1800.0
        braked = {1: "front_right", -1: "front_left"}.get(st["esc_side"]) if variant == "esc" else None
        cut.update(min(1.0, force) if braked == "front_right" else 0.0, st["wheel_angle"], st["steer"])
        yaw.update(sh["t"], st["yaw_rate"])
        steer_s.update(st["steer"])
        hcu.update(braked, min(1.0, force))
        xray, macro = bool(sh.get("xray")), bool(sh.get("macro"))
        set_ghost(xray)                      # x-ray: the body stays as a faint glass shell so the hardware sits visibly inside the car
        for group, on in ((yaw, xray), (steer_s, xray), (hcu, xray)):
            group.set_visible(on)
        cut.set_visible(macro)
        for ob in fr_parts:
            ob.hide_render = macro
        c = sh["cam"]
        h = st["heading"]
        rot = Matrix.Rotation(h, 3, "Z")
        if c["rel"] == "car":
            origin = Vector((st["x"], st["y"], 0.0))
            loc, tgt = origin + rot @ Vector(c["loc"]), origin + rot @ Vector(c["target"])
        elif c["rel"] == "follow":         # fixed direction, follows the car in x and y (keeps a sliding car in frame)
            origin = Vector((st["x"], st["y"], 0.0))
            loc, tgt = origin + Vector(c["loc"]), origin + Vector(c["target"])
        elif c["rel"] == "chase":
            origin = Vector((0.0, st["y"], 0.0))
            loc, tgt = origin + Vector(c["loc"]), origin + Vector(c["target"])
        else:
            loc, tgt = Vector(c["loc"]), Vector(c["target"])
        dd = cam.data
        dd.sensor_fit, dd.sensor_width, dd.lens, dd.clip_start = "HORIZONTAL", 36.0, c["lens"], 0.01
        base.set_camera(cam, loc, tgt)
        bpy.context.view_layer.update()
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        return {"variant": variant, "t": round(sh["t"], 5), "x": round(st["x"], 3), "y": round(st["y"], 3), "heading_deg": round(math.degrees(st["heading"]), 2),
                "yaw_rate": round(st["yaw_rate"], 4), "ref_yaw_rate": round(st["ref_yaw_rate"], 4), "speed_kmh": round(st["speed"] * 3.6, 1),
                "steer_deg": round(math.degrees(st["steer"]), 3), "esc_force_n": round(st["esc_force"], 1), "braked_wheel": braked, "rear_sliding": st["rear_sliding"],
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    out = []
    if args.film:
        from benchmarks.esc_stability import esc_timeline as tl
        segs = tl.segments()
        a, b = (int(x) for x in args.frames.split("-"))
        for f in range(a, b + 1):
            t0 = time.time()
            sh = tl.frame_state(f, segs)
            if sh.get("split"):
                parts = [render(sh, "esc", args.out / f"frame_{f:05d}_top.png", shots.HALF), render(sh, "off", args.out / f"frame_{f:05d}_bot.png", shots.HALF)]
            else:
                parts = [render(sh, sh["variant"], args.out / f"frame_{f:05d}.png", shots.FRAME)]
            info = {"frame": f, "segment": sh["segment"], "split": bool(sh.get("split")), "parts": parts, "render_seconds": round(time.time() - t0, 1)}
            out.append(info)
            print("ESC_FRAME " + json.dumps(info), flush=True)
        (args.out / f"esc-frames-{a:05d}.json").write_text(json.dumps({"renderer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "frames": out}, indent=1))
        return
    names = list(shots.SHOTS) if args.shots == "all" else args.shots.split(",")
    for name in names:
        t0 = time.time()
        sh = shots.SHOTS[name]
        info = {"shot": name, **render(sh, sh["variant"], args.out / f"{name}.png", sh.get("frame", shots.FRAME)), "render_seconds": round(time.time() - t0, 1)}
        out.append(info)
        print("ESC_SHOT " + json.dumps(info), flush=True)
    (args.out / "esc-shots.json").write_text(json.dumps({"renderer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "shots": out, "esc_gate": em.esc_physics()}, indent=1))


if __name__ == "__main__":
    main()
