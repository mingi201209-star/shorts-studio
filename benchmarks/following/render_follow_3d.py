"""EP.10 following distance: 100 % 3D renderer (Blender, Cycles CPU). A straight road with a roadside sign; the follower is the CC0 sedan
(blue) with the stylised driver inside; the car ahead is a copy of it painted red whose brake lights glow while it brakes; the follower's
brake lights glow after the reaction time; at the impact (1-second gap only) plastic debris flies. Everything that moves comes from
follow_motion. No scene text (numbers and labels are added in assembly)."""
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
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from benchmarks.abs_brake import abs_parts as ap  # noqa: E402
from benchmarks.airbag import human  # noqa: E402
from benchmarks.belt_limiter import render_belt_3d as rb  # noqa: E402
from benchmarks.esc_stability.esc_parts import material as mat2  # noqa: E402
from benchmarks.following import follow_motion as fm  # noqa: E402
from benchmarks.following import follow_timeline as tl  # noqa: E402
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402

material, cube = base.material, base.cube
FRAME, HALF = (1080, 1920), (1080, 960)
Y0 = -60.0                       # road y of the follower's nose at t = 0
LANE_W = 3.6
SIGN_Y = Y0 + fm.V0 * (tl.SIGN_PASS_LEAD_S + fm.GAP_S["three"])      # the lead car's tail passes it at SIGN_PASS_LEAD_S (3-second case)


def arguments():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--res-scale", type=float, default=0.5)
    p.add_argument("--samples", type=int, default=16)
    p.add_argument("--frames", default="0-0")
    p.add_argument("--film", action="store_true")
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return p.parse_args(argv)


def build_road():
    road = material("Asphalt", (0.07, 0.07, 0.075), rough=0.85)
    base.asphalt_grain(road)
    paint = material("Line paint", (0.85, 0.85, 0.82), rough=0.6)
    grass = material("Verge", (0.10, 0.16, 0.06), rough=0.95)
    cube("Road", (-LANE_W / 2, 20, -0.05), (LANE_W * 2 + 3.0, 400, 0.1), road)
    cube("Verge right", (LANE_W / 2 + 1.5 + 30, 20, -0.06), (60, 400, 0.1), grass)
    cube("Verge left", (-1.5 * LANE_W - 1.5 - 30, 20, -0.06), (60, 400, 0.1), grass)
    cube("Edge line right", (LANE_W / 2 + 0.1, 20, 0.002), (0.15, 400, 0.004), paint)
    cube("Edge line left", (-1.5 * LANE_W - 0.1, 20, 0.002), (0.15, 400, 0.004), paint)
    for i in range(-45, 55):
        cube(f"Dash {i}", (-LANE_W / 2, i * 4.0, 0.002), (0.13, 2.0, 0.004), paint)
    post = material("Sign post", (0.55, 0.56, 0.58), metal=1.0, rough=0.35)
    face = material("Sign face", (0.05, 0.35, 0.15), rough=0.5)
    rim = material("Sign rim", (0.92, 0.92, 0.9), rough=0.5)
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.05, depth=2.6, location=(LANE_W / 2 + 1.2, SIGN_Y, 1.3))
    bpy.context.object.data.materials.append(post)
    cube("Sign rim", (LANE_W / 2 + 1.2, SIGN_Y - 0.03, 2.75), (1.6, 0.04, 1.0), rim)
    cube("Sign face", (LANE_W / 2 + 1.2, SIGN_Y - 0.06, 2.75), (1.48, 0.04, 0.88), face)


def duplicate_car(root, wheels, colour):
    """A full copy of the car hierarchy (body, wheels, glass, lamps) with its own paint and tail-lamp materials."""
    paint = material("Lead paint", colour, metal=0.3, rough=0.35)
    tail = material("Lead tail", (0.6, 0.02, 0.02), rough=0.3)
    mapping = {}

    def copy(ob, parent):
        new = ob.copy()
        if ob.type == "MESH":
            new.data = ob.data.copy()
            for i, m in enumerate(new.data.materials):
                if m and m.name.startswith("blue"):
                    new.data.materials[i] = paint
                elif m and m.name.startswith("tail"):
                    new.data.materials[i] = tail
        bpy.context.collection.objects.link(new)
        new.parent = parent
        new.matrix_parent_inverse = ob.matrix_parent_inverse.copy()
        mapping[ob] = new
        for ch in ob.children:
            copy(ch, new)
        return new

    keep = [o for o in root.children if not o.name.startswith(("Driver", "Steering", "Interior"))]
    new_root = bpy.data.objects.new("Lead car root", None)
    bpy.context.collection.objects.link(new_root)
    for ob in keep:
        copy(ob, new_root)
    new_wheels = {k: {"node": mapping[w["node"]], "base": w["base"]} for k, w in wheels.items()}
    body = next(mapping[o] for o in root.children if o.name.startswith("Demo car body"))
    return new_root, body, new_wheels, tail


def set_tail(mat, on):
    s = mat.node_tree.nodes.get("Principled BSDF")
    s.inputs["Emission Color"].default_value = (1.0, 0.05, 0.03, 1)
    s.inputs["Emission Strength"].default_value = 40.0 if on else 0.0


class Debris:
    """Plastic and glass shards thrown out of the impact point for a second after the hit (ballistic, deterministic)."""

    def __init__(self):
        self.mats = [material("Debris red", (0.6, 0.05, 0.04), rough=0.4), material("Debris dark", (0.04, 0.04, 0.05), rough=0.5)]
        self.obs = []
        rng = random.Random(3)
        for k in range(60):
            s = rng.uniform(0.02, 0.07)
            ob = cube(f"Debris {k}", (0, 0, -5), (s, s * rng.uniform(0.4, 1.5), s * 0.5), self.mats[k % 2])
            v = Vector((rng.uniform(-4, 4), rng.uniform(-3, 6), rng.uniform(1.5, 5.0)))
            spin = Vector((rng.uniform(-20, 20), rng.uniform(-20, 20), rng.uniform(-20, 20)))
            self.obs.append((ob, v, spin))

    def update(self, origin, since_hit, carry_v):
        for ob, v, spin in self.obs:
            if since_hit is None or since_hit > 1.6:
                ob.hide_render = True
                continue
            a = since_hit
            p = origin + Vector((v.x, v.y + carry_v, v.z)) * a + Vector((0, 0, -0.5 * 9.81 * a * a))
            if p.z < 0.01:
                p.z = 0.01
            ob.hide_render = False
            ob.location = p
            ob.rotation_euler = tuple(spin * a)


class Phone:
    """A phone in the driver's right hand at lap height, screen lit (for the 'two second look' shot)."""

    def __init__(self, root):
        self.p = bpy.data.objects.new("Phone", None)
        bpy.context.collection.objects.link(self.p)
        self.p.parent, self.p.location = root, (-0.24, 0.42, 0.86)          # held up between the wheel and the face
        self.p.rotation_euler = (math.radians(-60), 0, math.radians(10))
        self.objs = [ap.rounded_box("Phone body", (0, 0, 0), (0.075, 0.155, 0.009), material("Phone body", (0.03, 0.03, 0.035), rough=0.3), self.p, bevel=0.008),
                     ap.rounded_box("Phone screen", (0, 0, 0.0047), (0.068, 0.145, 0.001), mat2("Phone screen", (0.55, 0.75, 1.0), emission=4.0), self.p, bevel=0.006)]

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
    sun_to = cinematic.sun_vector((-0.5, -0.8), 34.0)
    cinematic.apply_sky(scene, sun_to, strength=0.25, dust=0.8)
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    sun.data.energy, sun.data.angle = 3.2, 0.04
    sun.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()
    build_road()
    fol_tail = next((m for m in bpy.data.materials if m.name.startswith("tail")), None)
    lead_root, lead_body, lead_wheels, lead_tail = duplicate_car(root, wheels, (0.62, 0.05, 0.04))
    interior = rb.build_interior(root)
    driver = human.Human(root)
    phone = Phone(root)
    debris = Debris()
    wheel_nodes = {w["node"] for w in wheels.values()}
    fol_body = [o for o in root.children_recursive if o.type == "MESH" and not any(p in wheel_nodes for p in rb._ancestors(o))
                and o not in interior and not o.name.startswith(("Driver", "Steering", "Phone"))]
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    nose = geom["nose"]

    def place(r, b, whl, nose_y, v, braking):
        r.location = (0.0, Y0 + nose_y - nose, 0.0)
        b.rotation_euler = (-0.02 if braking and v > 0.3 else 0.0, 0, 0)       # nose dips under braking
        for wh in whl.values():
            wh["node"].rotation_mode = "ZXY"
            wh["node"].rotation_euler = (-(nose_y) / geom["tyre_radius"], 0, 0)

    def render(sh, gap, path, size):
        st = fm.at(gap, sh["t"])
        scene.render.resolution_x, scene.render.resolution_y = round(size[0] * args.res_scale), round(size[1] * args.res_scale)
        place(root, body, wheels, st["fol_x"], st["fol_v"], st["fol_braking"])
        place(lead_root, lead_body, lead_wheels, st["lead_x"], st["lead_v"], st["lead_braking"])
        set_tail(lead_tail, st["lead_braking"])
        if fol_tail:
            set_tail(fol_tail, st["fol_braking"])
        debris.update(Vector((0.0, Y0 + st["fol_x"], 0.6)), st["since_hit"], st["fol_v"])
        inside = bool(sh.get("interior"))
        for ob in fol_body:
            ob.hide_render = inside
        for ob in interior:
            ob.hide_render = not inside
        phone.set_visible(bool(sh.get("phone")))
        driver.neck.rotation_euler = (-0.55 if sh.get("phone") else 0.0, 0, 0)    # looking down at the phone
        c = sh["cam"]
        if c["rel"] == "fol":
            o = Vector((0.0, Y0 + st["fol_x"], 0.0))
        elif c["rel"] == "lead":
            o = Vector((0.0, Y0 + st["lead_x"], 0.0))
        elif c["rel"] == "sign":
            o = Vector((0.0, SIGN_Y, 0.0))
        elif c["rel"] == "car":
            o = Vector(root.location)
        else:
            o = Vector((0.0, 0.0, 0.0))
        dd = cam.data
        dd.sensor_fit, dd.sensor_width, dd.lens, dd.clip_start = "HORIZONTAL", 36.0, c["lens"], 0.02
        base.set_camera(cam, o + Vector(c["loc"]), o + Vector(c["target"]))
        bpy.context.view_layer.update()
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        return {"variant": gap, "t": round(sh["t"], 5), "fol_x": round(st["fol_x"], 3), "lead_x": round(st["lead_x"], 3), "fol_mph": round(st["fol_v"] / fm.MPH, 1),
                "lead_mph": round(st["lead_v"] / fm.MPH, 1), "gap_m": round(st["gap_m"], 2), "fol_braking": st["fol_braking"], "lead_braking": st["lead_braking"],
                "hit": st["hit"], "sign_y_rel": round(SIGN_Y - Y0, 3), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    segs = tl.segments()
    a0, b0 = (int(x) for x in args.frames.split("-"))
    out = []
    for f in range(a0, b0 + 1):
        t0 = time.time()
        sh = tl.frame_state(f, segs)
        if sh.get("split"):
            prts = [render(sh, "three", args.out / f"frame_{f:05d}_top.png", HALF), render(sh, "one", args.out / f"frame_{f:05d}_bot.png", HALF)]
        else:
            prts = [render(sh, sh["variant"], args.out / f"frame_{f:05d}.png", FRAME)]
        info = {"frame": f, "segment": sh["segment"], "split": bool(sh.get("split")), "parts": prts, "render_seconds": round(time.time() - t0, 1)}
        out.append(info)
        print("FOLLOW_FRAME " + json.dumps(info), flush=True)
    (args.out / f"follow-frames-{a0:05d}.json").write_text(json.dumps({"renderer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "frames": out}, indent=1))


if __name__ == "__main__":
    main()
