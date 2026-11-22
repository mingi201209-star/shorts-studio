"""EP.19 tyre-deflation spike strip: 100 % 3D renderer (Blender, Cycles CPU), house style of EP.13-EP.18. The EP.16 highway and
procedural front-left tyre (sidewall bend, sipes, cut-away window) are reused; new here: the strip (a folding plastic lattice with four
rows of holders), hollow steel quills with a hypodermic bevel that shows the bore, the quills the tyres take (they leave their holders
at the moment of contact and turn with the tyre), jets of air out of each quill whose length follows the model's vent speed, the
front tyre squashing as it deflates and the rear wheel settling on its rim. Everything that moves comes from spike_motion. No text."""
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
from benchmarks.belt_limiter import render_belt_3d as rb  # noqa: E402
from benchmarks.guardrail_end.render_terminal_3d import mesh_object  # noqa: E402
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402
from benchmarks.spike_strip import spike_motion as sm  # noqa: E402
from benchmarks.spike_strip import spike_timeline as tl  # noqa: E402
from benchmarks.tire_blowout import render_blowout_3d as rbm  # noqa: E402

material, cube = base.material, base.cube
FRAME = (1080, 1920)
PAINT = (1.75, 0.30, 0.24)
QUILL_L, QUILL_R, QUILL_BORE = 0.07, 0.005, 0.0032        # drawn about three times life size so they read on a phone
TILT = math.radians(25)                                   # quills lean toward oncoming traffic
N_JET = 9


def arguments():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--res-scale", type=float, default=0.5)
    p.add_argument("--samples", type=int, default=16)
    p.add_argument("--frames", default="0-0")
    p.add_argument("--list", default="")
    p.add_argument("--film", action="store_true")
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return p.parse_args(argv)


def quill_mesh(mat):
    """Hollow tube along +z from 0 to QUILL_L with its top cut on a steep bevel (a hypodermic point) so the bore shows."""
    n = 18
    verts, faces = [], []
    for r in (QUILL_R, QUILL_BORE):
        for z_top in (False, True):
            for k in range(n):
                a = 2 * math.pi * k / n
                x, y = r * math.cos(a), r * math.sin(a)
                z = QUILL_L - 2.2 * (QUILL_R - x) if z_top else 0.0
                verts.append((x, y, z))
    ob_, ib_, ot, it = 0, n, 2 * n, 3 * n            # outer bottom, outer top, inner bottom, inner top
    ob_, ot, ib_, it = 0, n, 2 * n, 3 * n
    for k in range(n):
        j = (k + 1) % n
        faces.append((ob_ + k, ob_ + j, ot + j, ot + k))      # outer wall
        faces.append((ib_ + j, ib_ + k, it + k, it + j))      # bore wall
        faces.append((ot + k, ot + j, it + j, it + k))        # bevel face
        faces.append((ob_ + j, ob_ + k, ib_ + k, ib_ + j))    # base
    return mesh_object("Quill proto", verts, faces, mat, smooth=False)


class Strip:
    def __init__(self, quill_proto):
        plastic = material("Strip plastic", (0.05, 0.05, 0.055), rough=0.6)
        orange = material("Strip end", (0.95, 0.45, 0.05), rough=0.5)
        holder_m = material("Holder", (0.10, 0.10, 0.11), rough=0.5)
        x0, x1 = sm.STRIP_X
        self.quills = {}
        pitch = 0.24
        for k, x in enumerate(np.arange(x0, x1, pitch)):
            for sgn in (-1, 1):                                # scissor slats
                ob = cube(f"Slat {k} {sgn}", (x + pitch / 2, sm.STRIP_W / 2, 0.008), (0.035, 0.62, 0.014), plastic)
                ob.rotation_euler = (0.0, 0.0, sgn * math.atan2(pitch, sm.STRIP_W))
        for xe in (x0 - 0.05, x1 + 0.05):
            cube(f"Strip end {xe}", (xe, sm.STRIP_W / 2, 0.02), (0.10, sm.STRIP_W, 0.04), orange)
        for row, ry in enumerate(sm.ROWS_Y):
            for x in sm.quill_xs(row):
                cube(f"Holder {row} {x:.2f}", (float(x), ry, 0.018), (0.024, 0.024, 0.02), holder_m)
                q = quill_proto.copy()
                bpy.context.collection.objects.link(q)
                q.location = (float(x), ry, 0.026)
                q.rotation_euler = (TILT, 0.0, 0.0)           # leans toward -y, the way the tyres come from
                self.quills[(row, round(float(x), 4))] = q
        quill_proto.location = (0, 0, -30)

    def set(self, t):
        on = 0
        for c in sm.captured():
            q = self.quills.get((c["row"], round(c["x"], 4)))
            if q is not None:
                q.hide_render = t >= c["t"]
        for q in self.quills.values():
            on += not q.hide_render
        return on


class Jets:
    """Short-lived streaks of air out of a quill's open end: length and opacity from the vent speed."""

    def __init__(self, n_sources):
        m = bpy.data.materials.new("Air jet")
        m.use_nodes = True
        nt = m.node_tree
        bsdf = nt.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = (0.92, 0.93, 0.95, 1.0)
        bsdf.inputs["Roughness"].default_value = 1.0
        info = nt.nodes.new("ShaderNodeObjectInfo")
        nt.links.new(info.outputs["Alpha"], bsdf.inputs["Alpha"])
        self.obs = []
        for s in range(n_sources):
            row = []
            for k in range(N_JET):
                bpy.ops.mesh.primitive_uv_sphere_add(segments=10, ring_count=6, radius=1.0, location=(0, 0, -30))
                ob = bpy.context.object
                ob.data.materials.append(m)
                row.append(ob)
            self.obs.append(row)

    def set(self, s, tip: Vector, direction: Vector, speed: float, film_t: float):
        strength = min(1.0, speed / 343.0) ** 0.5
        for k, ob in enumerate(self.obs[s]):
            if speed <= 0.5:
                ob.hide_render = True
                continue
            u = (film_t * 3.0 + k / N_JET + 0.37 * s) % 1.0
            length = 0.12 + 0.40 * strength
            ob.hide_render = False
            ob.location = tip + direction * (u * length)
            r = 0.008 + 0.035 * u
            ob.scale = (r, r, r * 2.2)
            ob.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
            ob.color = (1, 1, 1, 0.75 * strength * (1 - u) ** 0.7)


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
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Punchy"
    scene.view_settings.exposure = 0.2
    if hasattr(scene.view_settings, "use_white_balance"):
        scene.view_settings.use_white_balance = True
        scene.view_settings.white_balance_temperature = 7600.0
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    sun_to = cinematic.sun_vector((0.6, -0.7), 15.0)
    cinematic.apply_sky(scene, sun_to, strength=0.24, dust=0.7)
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    sun.data.energy, sun.data.angle = 6.5, 0.02
    sun.data.color = (1.0, 0.74, 0.48)
    sun.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()
    rbm.Y_RANGE = (-260.0, 520.0)
    rbm.build_highway()
    bark = material("Bark far", (0.10, 0.07, 0.05), rough=0.9)
    leaves = material("Leaves far", (0.12, 0.18, 0.05), rough=0.85)
    rng = random.Random(19)
    for k in range(30):                                        # more trees along the stretch where the car rolls to a stop
        x = rng.choice((-1, 1)) * rng.uniform(13, 50)
        y = rng.uniform(240, 500)
        h = rng.uniform(5, 11)
        bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.18, depth=h * 0.5, location=(x, y, h * 0.25))
        bpy.context.object.data.materials.append(bark)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=h * 0.32, location=(x, y, h * 0.62))
        bpy.context.object.scale = (1.0, 1.0, 1.25)
        bpy.context.object.data.materials.append(leaves)
    wheel_nodes = {w["node"] for w in wheels.values()}
    parts = [o for o in root.children_recursive if o.type == "MESH" and not any(p in wheel_nodes for p in rb._ancestors(o))]
    ghost = rb.Ghost(parts)
    ghost.set_tint(PAINT)
    ghost.set_factor(0.0, 1e4, 4.0)
    fl, rl = wheels["front_left"], wheels["rear_left"]
    for o in fl["node"].children_recursive:
        if "tire" in o.name:
            o.hide_render = True
    rubber = rbm.glow_material("Tyre rubber", (0.035, 0.035, 0.04), rough=0.75)
    belt = material("Steel belt", (0.80, 0.80, 0.82), metal=0.9, rough=0.3)
    cap = rbm.glow_material("Tyre section", (0.30, 0.29, 0.28), rough=0.9)
    glue = rbm.glow_material("Belt bond", (0.20, 0.12, 0.06), rough=0.8)
    tyre = rbm.Tyre(rubber, belt, cap, glue)
    rim = material("Rim barrel", (0.30, 0.30, 0.32), metal=0.8, rough=0.35)
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=rbm.bm.RIM_R + 0.004, depth=rbm.bm.W - 0.03)
    barrel = bpy.context.object
    barrel.data.materials.append(rim)
    steel = material("Quill steel", (0.92, 0.93, 0.95), metal=1.0, rough=0.12)
    proto = quill_mesh(steel)
    strip = Strip(proto)
    caps = sm.captured()
    front_caps = [c for c in caps if c["axle"] == "front"]
    rear_caps = [c for c in caps if c["axle"] == "rear"]
    tyre_quills = []
    for c in front_caps:
        q = proto.copy()
        bpy.context.collection.objects.link(q)
        tyre_quills.append(q)
    rl_base = rl["node"].location.copy()
    rear_quills = []
    bpy.context.view_layer.update()
    for c in rear_caps:                                       # parented to the rear wheel at the angle where it went in
        q = proto.copy()
        bpy.context.collection.objects.link(q)
        q.parent = rl["node"]
        a = c["dist"] / geom["tyre_radius"]
        w = c["w"]
        local = Matrix.Rotation(a, 4, "X") @ Matrix.Translation((w, 0.0, -(geom["tyre_radius"] - 0.022)))
        q.matrix_parent_inverse = Matrix.Identity(4)
        q.matrix_basis = local @ Matrix.Rotation(math.pi, 4, "X")          # pointing out of the tread
        rear_quills.append((c, q))
    jets = Jets(len(front_caps) + len(rear_caps))
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    r_t = geom["tyre_radius"]
    fl_base = fl["node"].location.copy()

    def render(sh, path):
        scene.render.resolution_x, scene.render.resolution_y = round(FRAME[0] * args.res_scale), round(FRAME[1] * args.res_scale)
        t, pt, film_t = sh["t"], sh["pose_t"], sh["film_t"]
        st, pose = sm.state(t), sm.state(pt)
        root.location = (pose["x"], pose["y"], 0.0)
        root.rotation_euler = (0.0, 0.0, 0.0)
        spin = pose["dist"] / r_t
        for wh in wheels.values():
            wh["node"].rotation_mode = "ZXY"
            wh["node"].rotation_euler = (-spin, 0, 0)
        sq0 = sm.squash(-1.0, "rear")
        rl["node"].location = (rl_base.x, rl_base.y, rl_base.z - (st["squash_rear"] - sq0) * 0.9)
        fl["node"].location = (fl_base.x, fl_base.y, fl_base.z - (st["squash"] - sm.squash(-1.0)) * 0.6)
        bpy.context.view_layer.update()
        wc = fl["node"].matrix_world.translation.copy()
        tst = {"t": t, "sep": 0.0, "peel_span": 0.0, "peel_lift": 0.0, "burst": False}
        tyre.set(tst, spin, st["squash"], cut=sh.get("cut"))
        for ob in tyre.obs:
            ob.location, ob.rotation_euler = wc, (0.0, 0.0, 0.0)
        barrel.location = wc
        barrel.rotation_euler = (0.0, math.pi / 2, 0.0)
        on_strip = strip.set(t)
        on_tyre = 0
        v_front, v_rear = sm.vent_speed(t, "front"), sm.vent_speed(t, "rear")
        for s, (c, q) in enumerate(zip(front_caps, tyre_quills)):
            if t < c["t"]:
                q.hide_render = True
                jets.set(s, Vector(), Vector((0, 0, 1)), 0.0, film_t)
                continue
            on_tyre += 1
            q.hide_render = False
            a_mat = c["dist"] / r_t
            a_world = a_mat - spin
            base_pt = Vector(tyre._point(c["w"], rbm.bm.R, "tread", 0.0, a_world, a_mat, tst, st["squash"], False))
            d = Vector((0.0, math.sin(a_world), -math.cos(a_world)))
            q.location = wc + base_pt - d * 0.025
            q.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
            jets.set(s, wc + base_pt + d * (QUILL_L - 0.025), d, v_front, film_t)
        for k, (c, q) in enumerate(rear_quills):
            q.hide_render = t < c["t"]
            on_tyre += t >= c["t"]
            mw = q.matrix_world
            tip = mw @ Vector((0, 0, QUILL_L))
            d = (mw.to_3x3() @ Vector((0, 0, 1))).normalized()
            jets.set(len(front_caps) + k, tip, d, v_rear if t >= c["t"] else 0.0, film_t)
        c = sh["cam"]
        o = Vector((0.0, 0.0, 0.0))
        if c["rel"] == "car":
            o = Vector(root.location)
        elif c["rel"] == "wheel":
            o = Vector(wc)
        loc, tgt = o + Vector(c["loc"]), o + Vector(c["target"])
        dd = cam.data
        dd.sensor_fit, dd.sensor_width, dd.lens, dd.clip_start = "HORIZONTAL", 36.0, c["lens"], 0.005
        dd.dof.use_dof = True
        dd.dof.focus_distance = (tgt - loc).length
        dd.dof.aperture_fstop = c.get("fstop", 8.0)
        base.set_camera(cam, loc, tgt)
        bpy.context.view_layer.update()
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        return {"variant": sh["variant"], "t": round(t, 6), "pose_t": round(pt, 6), "car_y": round(pose["y"], 4),
                "gauge_front_psi": round(st["gauge_front_psi"], 3), "gauge_rear_psi": round(st["gauge_rear_psi"], 3),
                "squash": round(st["squash"], 5), "quills_on_tyres": on_tyre, "quills_on_strip": on_strip,
                "vent_front_mps": round(v_front, 2), "cut": sh.get("cut"), "wheel_x": round(wc.x, 4), "wheel_y": round(wc.y, 4),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

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
        print("SPIKE_FRAME " + json.dumps(info), flush=True)
    (args.out / f"spike-frames-{frames[0]:05d}.json").write_text(json.dumps({"renderer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                                                            "frames": out}, indent=1))


if __name__ == "__main__":
    main()
