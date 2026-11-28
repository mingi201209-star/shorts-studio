"""EP.37 elevator safety gear: 100 % 3D renderer (Blender, Cycles CPU). Started with EP.36 for its opening only (EP.36's teaser);
the rest of the film is added later without changing the opening's code path. A concrete hoistway cut away on one side, lit like
a set: a cool key through the cutaway, the car's own ceiling light behind its glass, warm light at the landing doors' seams, and
the sparks. Everything that moves comes from car_motion. No text anywhere."""
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
from benchmarks import hook_gate  # noqa: E402
from benchmarks.elevator_safety import car_motion as m  # noqa: E402
from benchmarks.elevator_safety import car_parts as cp  # noqa: E402
from benchmarks.elevator_safety import car_timeline as tl  # noqa: E402
from benchmarks.elevator_safety import more_parts as mp  # noqa: E402
from benchmarks.identity import dummy, xray  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402

FRAME = (1080, 1920)


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


def area(name, loc, target, size, energy, colour):
    bpy.ops.object.light_add(type="AREA", location=loc)
    ob = bpy.context.object
    ob.name = name
    ob.data.size = size
    ob.data.energy = energy
    ob.data.color = colour
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return ob


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
    scene.view_settings.exposure = 0.0
    scene.world = bpy.data.worlds.new("World")
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.02, 0.025, 0.035, 1)
    bg.inputs["Strength"].default_value = 1.0

    mt = cp.mats()
    shaft = cp.hoistway(mt)
    cw_root = cp.counterweight(mt, 5.5)
    car = cp.car(mt)
    gov_rope = cp.governor_rope(mt)
    spark_obs = cp.sparks(mt)
    key = area("Key", (5.5, -3.0, 3.5), (0.5, 0.0, 0.5), 4.0, 2200.0, (0.82, 0.9, 1.0))
    fill = area("Fill", (3.5, 2.5, -2.5), (0.0, 0.0, 0.5), 3.0, 500.0, (1.0, 0.75, 0.5))
    top = area("Top", (0.0, 0.0, 9.0), (0.0, 0.0, 0.0), 2.0, 900.0, (1.0, 0.95, 0.9))
    bpy.ops.object.light_add(type="POINT", location=(0.0, 0.0, cp.CAB_H - 0.25))
    cab_light = bpy.context.object
    cab_light.parent = car["root"]
    cab_light.data.energy = 120.0
    cab_light.data.color = (1.0, 0.9, 0.75)
    cab_light.data.shadow_soft_size = 0.4
    # the rest of the film (lines 2-8)
    ropes = mp.hoist_ropes(mt)
    gov = mp.machine_room(mt)
    marker = mp.drop_marker()
    otis = mp.otis_tower(mt)
    rope_glow = mp.glow("Rope glow", (1.0, 0.55, 0.12), 6.0)
    bpy.ops.object.light_add(type="SUN", location=(0, 0, 50))
    day = bpy.context.object
    day.data.energy = 4.0
    day.rotation_euler = (0.75, 0.2, 0.6)
    room_lamp = area("Room lamp", (mp.GOV[0] + 0.5, mp.GOV[1] - 1.0, mp.GOV[2] + 3.0), (mp.GOV[0], mp.GOV[1], mp.GOV[2] + 1.0), 2.0, 600.0, (1.0, 0.92, 0.8))
    shaft_obs = [o for o in scene.objects if o.type in ("MESH", "CURVE") and not o.name.startswith(("MR ", "Gov", "Flyweight", "Traction",
                                                                                                    "Machine", "Floor hole"))]
    gov_obs = gov["room"] + gov["parts"] + [c for f in gov["flyweights"] for c in f.children] + [gov["pawl"]] + gov["rope"]
    otis_obs = otis["static"] + otis["plat"] + [otis["rope"]] + list(otis["man"].children_recursive) + [otis["man"]] + \
        [o for p in otis["crowd"] for o in [p] + list(p.children_recursive)]
    shaft_obs = [o for o in shaft_obs if o not in set(gov_obs) | set(otis_obs)]
    mech = car["gear"] + [o for o in gov_rope]
    xr = xray.Xray(mechanism=mech, spared=[])
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    wedge_rest = [w.location.copy() for w in car["wedges"]]
    lever = next(o for o in car["gear"] if o.name == "Safety lever")
    lever_rest = lever.location.copy()

    def show(obs, on):
        for o in obs:
            o.hide_render = not on

    def render(sh, path):
        scene.render.resolution_x, scene.render.resolution_y = round(FRAME[0] * args.res_scale), round(FRAME[1] * args.res_scale)
        t = sh["t"]
        variant = sh["variant"]
        show(shaft_obs + [key, fill, top, cab_light] + car["stubs"] + spark_obs + ropes, variant == "car")
        show(gov_obs, variant == "gov")
        show(otis_obs, variant == "otis")
        show([day], variant in ("gov", "otis"))
        show([room_lamp], variant == "gov")
        show([marker], bool(sh.get("marker")))
        for r in ropes:
            r.material_slots[0].material = mt["rope"]
        xr.set(bool(sh.get("xray")), glow_strength=2.2)
        bg.inputs["Color"].default_value = (0.02, 0.025, 0.035, 1) if variant == "car" else (0.30, 0.33, 0.38, 1)
        if variant == "gov":
            return render_gov(sh, path)
        if variant == "otis":
            return render_otis(sh, path)
        st = m.state(t)
        cz = st["car_z"]
        car["root"].location = (0.0, 0.0, cz)
        for w, rest in zip(car["wedges"], wedge_rest):
            w.location = (rest.x, rest.y, rest.z + 0.07 * st["wedge"])
        slack = min(1.0, max(0.0, t / 0.35))
        for ob in car["stubs"]:
            cp.set_stub(ob, t, slack)
            ob.hide_render = t < 0                                       # before the break the ropes are whole
        mp.set_ropes(ropes, cz, t < 0)
        thick = 1.0 if sh["segment"] in ("A1-caught", "A2-wedge") else 2.2          # the frozen opening as it was rendered
        for g in gov_rope:
            g.scale = (thick, thick, 1.0)
        if sh.get("glow_rope"):
            ropes[2].material_slots[0].material = rope_glow
        lever.location = lever_rest
        lever.rotation_euler = (-0.55 * max(0.0, st["wedge"]), 0.0, 0.0)  # pulled up by the stopped governor rope
        if sh.get("marker"):
            z_stop = m.state(m.stop_time())["car_z"]
            marker.location = (cp.CAB_X + 0.25, -0.2, (m.SNAP_Z + z_stop) / 2)
            marker.scale = (1.0, 1.0, max(0.01, m.SNAP_Z - z_stop))
        wave = min(1.0, max(0.0, (t - 1.2) / 0.4)) if sh.get("wave") else 0.0
        lean = 0.12 * st["decel_g"] / m.DECEL_G if st["gripping"] else 0.0
        dummy.pose(car["bumper"], lean=-lean, seated=False, thumbs_up=wave)
        if wave > 0:
            car["bumper"]["elbow_R"].rotation_euler.x += 0.35 * math.sin(2 * math.pi * 1.6 * t) * wave
        for k, p in enumerate(car["people"]):
            torso = next(o for o in p.children if o.name.startswith("Crew torso"))
            torso.rotation_euler = (lean * (0.8 + 0.3 * k), 0.0, 0.0)
        n = 0
        on = st["gripping"] or (st["phase"] == "grip" and t < m.stop_time() + 0.08)
        for ob in spark_obs:
            if not on:
                ob.location = (0, 0, -50)
                continue
            age = ((ob["phase"] + t * 3.1) % 1.0) * 0.3
            sx = ob["side"]
            p0 = Vector((sx * (cp.SHAFT_X - 0.02 - 0.0775), 0.0, cz - 0.55))
            v = Vector(ob["v"])
            v.x *= -sx
            ob.location = p0 + v * age + Vector((0, 0, -4.9 * age * age))
            n += 1
        c = sh["cam"]
        loc, tgt = Vector(c["loc"]), Vector(c["target"])
        if c["rel"] == "car":
            loc.z += cz
            tgt.z += cz
        dd = cam.data
        dd.sensor_fit, dd.sensor_width, dd.lens, dd.clip_start, dd.clip_end = "HORIZONTAL", 36.0, c["lens"], 0.03, 400.0
        dd.dof.use_dof = True
        dd.dof.focus_distance = (tgt - loc).length
        dd.dof.aperture_fstop = c.get("fstop", 8.0)
        base.set_camera(cam, loc, tgt)
        bpy.context.view_layer.update()
        info = {"variant": sh["variant"], "t": round(t, 6), "car_z": round(cz, 4), "ropes_whole": t < 0, "glow_rope": bool(sh.get("glow_rope")),
                "xray": bool(sh.get("xray")), "marker": bool(sh.get("marker")), "wave": round(wave, 3), "lever": round(lever.rotation_euler.x, 4), "speed": round(st["speed"], 4), "decel_g": round(st["decel_g"], 4),
                "phase": st["phase"], "wedge": round(st["wedge"], 4), "gripping": bool(st["gripping"]), "sparks": n,
                "subject_box": hook_gate.project_box(scene, cam, Matrix.Identity(4), (-cp.SHAFT_X, -0.7, cz - 0.7), (cp.SHAFT_X, 0.7, cz + cp.CAB_H + 0.9))}
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        info["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        return info

    def place_cam(c, origin):
        loc, tgt = Vector(c["loc"]) + Vector(origin), Vector(c["target"]) + Vector(origin)
        dd = cam.data
        dd.sensor_fit, dd.sensor_width, dd.lens, dd.clip_start, dd.clip_end = "HORIZONTAL", 36.0, c["lens"], 0.03, 400.0
        dd.dof.use_dof = True
        dd.dof.focus_distance = (tgt - loc).length
        dd.dof.aperture_fstop = c.get("fstop", 8.0)
        base.set_camera(cam, loc, tgt)
        bpy.context.view_layer.update()

    def shoot(info, path):
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        info["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        return info

    def render_gov(sh, path):
        t = sh["t"]
        g = m.governor(t)
        gov["sheave"].rotation_euler = (g["angle"], 0.0, 0.0)
        for k, piv in enumerate(gov["flyweights"]):
            piv.rotation_euler = (k * math.pi + 0.0, 0.0, 0.0)
            piv.children[0].rotation_euler = (0.0, 0.0, 0.0)
            piv.rotation_euler.y = 0.0
            piv.children[0].location = (0.0, 0.0, 0.08 + 0.07 * g["fly"])
        ox, oy, oz = mp.GOV
        gov["pawl"].rotation_euler = (0.0, 0.0, 0.0) if g["locked"] else (0.0, -0.5, 0.0)
        gov["pawl"].location = (ox + 0.12, oy, oz + 1.15 + mp.GOV_R + (0.02 if g["locked"] else 0.12))
        place_cam(sh["cam"], mp.GOV)
        info = {"variant": "gov", "t": round(t, 6), "angle": round(g["angle"], 5), "fly": round(g["fly"], 4), "locked": g["locked"],
                "subject_box": hook_gate.project_box(scene, cam, Matrix.Identity(4), (ox - 0.4, oy - 0.4, oz), (ox + 0.4, oy + 0.4, oz + 1.6))}
        return shoot(info, path)

    def render_otis(sh, path):
        t = sh["t"]
        o = m.otis(t)
        mp.set_otis(otis, o["z"], o["cut"], max(0.0, t))
        place_cam(sh["cam"], mp.OTIS)
        ox, oy, oz = mp.OTIS
        info = {"variant": "otis", "t": round(t, 6), "platform_z": round(o["z"], 4), "cut": o["cut"], "caught": o["caught"],
                "subject_box": hook_gate.project_box(scene, cam, Matrix.Identity(4), (ox - 1.3, oy - 1.0, oz + o["z"]), (ox + 1.3, oy + 1.0, oz + o["z"] + 3.0))}
        return shoot(info, path)

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
        print("CAR_FRAME " + json.dumps(info), flush=True)
    (args.out / f"car-frames-{frames[0]:05d}.json").write_text(json.dumps({"renderer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                                                          "frames": out}, indent=1))


if __name__ == "__main__":
    main()
