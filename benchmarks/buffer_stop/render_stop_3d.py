"""EP.36 friction buffer stop: 100 % 3D renderer (Blender, Cycles CPU), house style from the first frame (sky 0.26, sun 6.5,
exposure +0.15, golden light, depth of field), with the channel's identity parts: Bumper at the train's controls (and a second dummy
in the comparison car), the x-ray reveal look, and (in assembly) the caption look.

Everything that moves comes from stop_motion: the train's front, the stop's slide, the buffers' squash, the sparks while the shoes
slide, the slide's length on the track. The what-if wall and the comparison car have their own model states. No text anywhere."""
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
from benchmarks.buffer_stop import stop_motion as m  # noqa: E402
from benchmarks.buffer_stop import stop_parts as sp  # noqa: E402
from benchmarks.buffer_stop import stop_timeline as tl  # noqa: E402
from benchmarks.identity import dummy, xray  # noqa: E402
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402

FRAME = (1080, 1920)
HALF = (1080, 960)
SKY = 0.26                       # house-style sky fill (EP.32-35)
SUN = 6.5
SLID = m.impact()[-1][4]         # where the stop ends up (m past its mark)
HEAT_END = m.state(m.impact()[-1][0])["shoe_heat_kJ"]   # each shoe's friction heat by the end of the slide (kJ)
PARK_Y = -400.0                  # where the train waits when it is not in the shot
DUST_DENSITY = 6.0               # the wall what-if's dust: volume density x radius^1.6 (thick puffs that thin as they spread)


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


def reparent_keep(ob, parent):
    mw = ob.matrix_world.copy()
    ob.parent = parent
    ob.matrix_parent_inverse = parent.matrix_world.inverted()
    ob.matrix_world = mw


def smooth(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


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
    scene.view_settings.exposure = 0.15
    scene.world = bpy.data.worlds.new("World")
    sun_to = cinematic.sun_vector((0.5, 0.75), 22.0)                   # low sun ahead-right of the stop: the train's face lit
    cinematic.apply_sky(scene, sun_to, strength=SKY, dust=0.7)
    sky_nodes = [n for n in scene.world.node_tree.nodes if n.type == "BACKGROUND"]
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    sun.data.energy, sun.data.angle = SUN, 0.02
    sun.data.color = (1.0, 0.80, 0.60)
    sun.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()

    mt = sp.mats()
    ground = base.cube("Ground", (0.0, 0.0, -0.7), (4000.0, 4000.0, 0.1), sp.concrete("Yard ground", (0.20, 0.19, 0.17), 0.5, 0.2))
    tracks = sp.track(mt, "Main", 0.0, *sp.TRACK_Y) + sp.track(mt, "Side", sp.ADJ_X, sp.TRACK_Y[0], 0.0) + \
        sp.track(mt, "Siding", sp.ADJ_X * 2, *sp.TRACK_Y)
    fence = sp.fence(mt)
    station, people = sp.station(mt)
    wires = sp.overhead(mt)
    old_stop = sp.fixed_stop(mt, sp.ADJ_X, 0.6)
    parked = sp.train(mt, "Parked", cars=3, bumper=False)
    parked["root"].location = (sp.ADJ_X, -0.55, 0.0)
    stop = sp.buffer_stop(mt)
    hero = sp.train(mt, "Train", cars=6, bumper=True)
    pivot = bpy.data.objects.new("Front pivot", None)                  # the cab front crushes about this in the what-if
    bpy.context.collection.objects.link(pivot)
    pivot.parent = hero["root"]
    pivot.location = (0.0, -1.9, 0.0)
    bpy.context.view_layer.update()
    for ob in hero["nose"]:
        reparent_keep(ob, pivot)
    wl = sp.wall(mt)
    wreck = sp.wreck_sides(mt)                                       # the what-if's cab sides, folding with the crush (wall shot only)
    for ob, _dz, _sx in wreck:
        ob.parent = hero["root"]
    plain_sides = [ob for ob in hero["nose"] if " cab side " in ob.name]
    shards = sp.glass_shards(mt)
    screen = next(ob for ob in hero["nose"] if ob.name.endswith(" windscreen"))
    cracked = sp.cracked(mt["glass"])
    thermal = xray.thermal_material()
    shoe_glow = xray.glow_material("Xray glow shoes", colour=(1.0, 0.80, 0.10), strength=4.5)
    road = sp.road_scene(mt)
    car = sp.sedan(mt)
    trac = sp.tractor(mt)
    crew = []
    for k in range(3):
        root, torso = sp.cw.crew_member(k, mt["orange"])
        w = sp.wrench(mt, f"Wrench {k}")
        w.parent = torso
        w.location = (0.25, 0.34, 0.12)
        crew.append((root, torso, w))
    spark_obs = sp.sparks(mt)
    marker = sp.slide_marker(mt, m.impact()[-1][1] + 0.0)
    polish = sp.polished_strips(mt)

    def kids(objs):
        out = []
        for o in objs:
            out.append(o)
            out += list(o.children_recursive)
        return out

    clutter = station + wires + old_stop + fence + kids([p for p in people]) + kids([parked["root"]])
    comparison = kids([car["root"]]) + [o for o in road]
    wall_obs = wl["wall"] + wl["debris"] + wl["dust"] + shards
    crew_obs = kids([c[0] for c in crew]) + kids([trac["root"]])
    hero_obs = kids([hero["root"]])
    stop_obs = kids([stop["root"]])
    mech = stop["parts"]
    xr = xray.Xray(mechanism=mech, spared=[ground])
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    ox, oy, oz = sp.CAR_ORIGIN

    def show(objs, on):
        for ob in objs:
            ob.hide_render = not on

    def set_cam(c, rel_y=0.0, rel_x=0.0, shake=(0.0, 0.0, 0.0)):
        loc, tgt = Vector(c["loc"]), Vector(c["target"])
        loc.y += rel_y
        tgt.y += rel_y
        loc.x += rel_x
        tgt.x += rel_x
        loc += Vector(shake)
        dd = cam.data
        dd.sensor_fit, dd.sensor_width, dd.lens, dd.clip_start = "HORIZONTAL", 36.0, c["lens"], 0.05
        dd.clip_end = 9000.0
        dd.dof.use_dof = True
        dd.dof.focus_distance = (tgt - loc).length
        dd.dof.aperture_fstop = c.get("fstop", 8.0)
        base.set_camera(cam, loc, tgt)

    def place_stop(stop_y, comp):
        stop["root"].location = (0.0, stop_y + sp.FRAME_TO_FACE, 0.0)
        for pl in stop["plungers"]:
            pl.location.y = comp

    def place_sparks(st, t, on):
        n = 0
        for ob in spark_obs:
            if not on:
                ob.location = (0, 0, -50)
                continue
            age = ((ob["phase"] + t * 2.7) % 1.0) * 0.35
            k = ob["shoe"]
            sx = -1 if k < 4 else 1
            sy = sp.SHOE_Y[k % 4]
            p0 = Vector((sx * (sp.RAIL_X + 0.1), st["stop_y"] + sp.FRAME_TO_FACE + sy, 0.02))
            v = Vector(ob["v"])
            v.x *= sx
            ob.location = p0 + v * age + Vector((0, 0, -4.9 * age * age))
            n += 1
        return n

    def place_polish(stop_y):
        y0 = sp.FRAME_TO_FACE + sp.SHOE_Y[0] - 0.23
        y1 = sp.FRAME_TO_FACE + stop_y + sp.SHOE_Y[-1] + 0.23
        for ob in polish:
            ob.hide_render = stop_y < 0.05
            ob.location.y = (y0 + y1) / 2
            ob.scale.y = max(0.01, y1 - y0)

    def pose_driver(d, lean, wave=0.0, t=0.0):
        dummy.pose(d, lean=lean, thumbs_up=min(1.0, wave * 2.0))
        if wave > 0:
            d["elbow_R"].rotation_euler.x += 0.35 * math.sin(2 * math.pi * 1.6 * t) * min(1.0, wave * 2.0)

    def render_one(sh, path, panel=None):
        variant = sh["variant"] if panel is None else ("train" if panel == "top" else "car")
        res = HALF if panel else FRAME
        scene.render.resolution_x, scene.render.resolution_y = round(res[0] * args.res_scale), round(res[1] * args.res_scale)
        t = sh["t"]
        xr_on, heat, mark = bool(sh.get("xray")), bool(sh.get("heat")), bool(sh.get("marker"))
        info = {"variant": variant, "t": round(t, 6), "xray": xr_on, "marker": mark, "panel": panel}
        show(clutter, not xr_on and variant in ("train", "wall", "crew"))
        show(comparison, variant == "car")
        show(wall_obs, variant == "wall")
        show(crew_obs, variant == "crew")
        show(stop_obs, variant in ("train", "crew"))
        show(hero_obs, variant in ("train", "wall"))
        show(marker, mark)
        for ob in polish:
            ob.hide_render = True
        pivot.scale.y = 1.0
        for ob, _dz, _sx in wreck:                                     # the wall shot swaps the folding sides in for the plain ones
            ob.hide_render = variant != "wall"
        for ob in plain_sides:
            ob.hide_render = variant != "train"
        screen.material_slots[0].material = mt["glass"]
        scene.cycles.volume_bounces = 1 if variant == "wall" else 0      # the dust: light bounces inside the cloud (the only volume)
        hero["cab_light"].data.energy = 40.0 if sh.get("cab") else 0.0
        shake = (0.0, 0.0, 0.0)
        sparks_n = 0
        if variant == "train":
            st = m.state(t)
            hero["root"].location = (0.0, st["train_y"], 0.0)
            place_stop(st["stop_y"], st["compression"])
            sparks_n = place_sparks(st, t, st["stop_speed"] > 0.3 and not xr_on)
            place_polish(st["stop_y"])
            if xr_on:
                for ob in polish:
                    ob.hide_render = True
            lean = 0.6 * st["decel_g"] / 0.8
            wave = max(0.0, (t - m.stop_time() - 0.1) / 0.6) if sh.get("wave") else 0.0
            pose_driver(hero["bumper"], lean, wave, t)
            info.update({"train_y": round(st["train_y"], 4), "stop_y": round(st["stop_y"], 4), "compression": round(st["compression"], 4),
                         "decel_g": round(st["decel_g"], 4), "train_speed": round(st["train_speed"], 4), "sliding": bool(st["sliding"]),
                         "sparks": sparks_n, "driver_lean": round(lean, 4), "wave": round(min(1.0, wave * 2.0), 3), "cab": bool(sh.get("cab"))})
            rel_y = st["stop_y"] if sh["cam"].get("rel") == "stop" else (st["train_y"] if sh["cam"].get("rel") == "train" else 0.0)
            c = sh["cam"] if panel is None else sh["cam"]["top"]
            if panel:
                rel_y = st["train_y"]
            set_cam(c, rel_y)
        elif variant == "wall":
            ws = m.wall_state(t)
            hero["root"].location = (0.0, ws["train_y"], 0.0)
            pivot.scale.y = (1.9 - ws["crush"]) / 1.9
            folds = sp.fold_sides(wreck, ws["crush"])                  # the sides take the same crush, folding from the front back
            if ws["hit"]:
                screen.material_slots[0].material = cracked
            tau = t if ws["hit"] else -1.0
            for ob in shards:
                if tau < 0:
                    ob.location = (0, 0, -40)
                    continue
                at, v, sp_ = Vector(ob["at"]), Vector(ob["v"]), ob["spin"]
                at.y += ws["train_y"]
                ob.location = (at.x + v.x * tau, at.y + v.y * tau, max(0.02, at.z + v.z * tau - 4.9 * tau * tau))
                ob.rotation_euler = (sp_[0] * tau, sp_[1] * tau, sp_[2] * tau)
            for ob in wl["debris"]:
                if tau < 0:
                    ob.location = (0, 0, -40)
                    continue
                at, v, sp_ = Vector(ob["at"]), Vector(ob["v"]), ob["spin"]
                z = at.z + v.z * tau - 4.9 * tau * tau
                ob.location = (at.x + v.x * tau, at.y + v.y * tau, max(-0.15, z))
                ob.rotation_euler = (sp_[0] * tau, sp_[1] * tau, sp_[2] * tau)
            for ob in wl["dust"]:
                if tau < 0:
                    ob.location = (0, 0, -40)
                    continue
                s = ob["grow"] * min(1.0, 0.25 + tau * 2.2)
                at = Vector(ob["at"])
                ob.location = (at.x, at.y - 0.3 * tau, at.z + 0.9 * tau)
                ob.scale = (s, s, s * 0.8)
                d = DUST_DENSITY * min(1.0, tau / 0.03) / s ** 1.6      # the same dust spread wider: thinner (volume density)
                ob.color = (d, d, d, 1.0)
            jolt = 1.1 * math.exp(-max(0.0, tau) / 0.25) * (1.0 - math.exp(-max(0.0, tau) / 0.03)) if tau >= 0 else 0.0
            pose_driver(hero["bumper"], jolt)
            if tau >= 0:
                amp = 0.06 * math.exp(-tau / 0.18)
                shake = (amp * math.sin(97 * tau), amp * 0.5 * math.sin(71 * tau + 1.0), amp * math.sin(53 * tau + 2.0))
            info.update({"train_y": round(ws["train_y"], 4), "crush": round(ws["crush"], 4), "hit": bool(ws["hit"]), "decel_g": round(ws["decel_g"], 3),
                         "driver_lean": round(jolt, 4), "debris": sum(1 for ob in wl["debris"] if ob.location.z > -10),
                         "fold_deg": [round(math.degrees(a), 2) for a in folds], "shards": sum(1 for ob in shards if ob.location.z > -10)})
            set_cam(sh["cam"], 0.0, 0.0, shake)
        elif variant == "car":
            cs = m.car_state(t - 0.25)
            car["root"].location = (ox, oy + cs["x"], oz)
            braking = cs["decel_g"] > 0
            car["body"].rotation_euler = (-0.04 * cs["decel_g"] / m.CAR_DECEL_G, 0.0, 0.0)
            t_stop = m.CAR_V0 / (m.CAR_DECEL_G * m.G)
            tb = t - 0.25
            if tb < 0:
                lean = 0.0
            elif tb < t_stop:
                lean = 0.75 * smooth(tb / 0.18)
            else:
                lean = 0.75 * math.exp(-(tb - t_stop) / 0.22)
            pose_driver(car["dummy"], lean)
            mt["brake"].node_tree.nodes.get("Principled BSDF").inputs["Emission Strength"].default_value = 12.0 if braking else 1.5
            info.update({"car_x": round(cs["x"], 4), "car_speed": round(cs["speed"], 4), "car_decel_g": round(cs["decel_g"], 3), "car_lean": round(lean, 4),
                         "braking": braking})
            set_cam(sh["cam"]["bottom"], oy + cs["x"], ox)
        else:                                                              # crew: the train gone, the stop slid, then pushed back
            hero["root"].location = (0.0, PARK_Y, 0.0)
            u = sh["u"]
            pushing = bool(sh.get("push"))
            stop_y = SLID * (1.0 - smooth((u - 0.1) / 0.75)) if pushing else SLID
            place_stop(stop_y, 0.0)
            place_polish(SLID)
            trac["root"].location = (0.0, stop_y + sp.FRAME_TO_FACE + 4.35 + (0.0 if pushing else 3.5), 0.0)
            spin = (-1.0 if not pushing else 1.0) * 2.4 * u
            for k, nut in enumerate(stop["nuts"]):
                nut.rotation_mode = "ZYX"
                nut.rotation_euler = (0.0, math.pi / 2, spin if (k // 4) % 4 in (0, 1) else 0.0)
            spots = ((-sp.RAIL_X - 0.55, 1.6), (sp.RAIL_X + 0.55, 2.6), (-2.2, 4.4))
            for k, (root, torso, w) in enumerate(crew):
                x, dy = spots[k]
                root.location = (x, stop_y + sp.FRAME_TO_FACE + dy, 0.0)
                root.rotation_euler = (0.0, 0.0, -math.pi / 2 if x < 0 else math.pi / 2)
                torso.rotation_euler = (-0.75 if k < 2 else -0.1, 0.0, 0.0)
                w.rotation_euler = (0.0, 0.0, 0.5 * math.sin(2 * math.pi * 1.2 * sh["film_t"] + k)) if k < 2 else (0.0, 0.0, 0.0)
            info.update({"stop_y": round(stop_y, 4), "crew": True, "push": pushing, "nut_turn": round(spin, 3)})
            set_cam(sh["cam"], stop_y if sh["cam"].get("rel") == "stop" else 0.0)
        xr.set(xr_on, glow_strength=2.2)
        if xr_on and sh.get("reveal"):                 # the line is about the shoes: they and their bolts glow yellow-white on the orange frame
            for ob in stop["shoes"]:
                for slot in ob.material_slots:
                    slot.material = shoe_glow
            info["shoes_focus"] = True
        if xr_on and heat:                             # the friction's heat as a thermal camera shows it: the shoes and the rubbed rail
            hot = min(1.0, max(0.0, st["shoe_heat_kJ"] / HEAT_END))   # the share of each shoe's friction heat made so far (the model)
            blue = xray.blueprint_material()
            shoe_names = {ob.name for ob in stop["shoes"]}
            for ob in mech:
                if ob.name not in shoe_names:
                    for slot in ob.material_slots:
                        slot.material = blue
            for ob in stop["shoes"]:
                rubbing = " jaw " in ob.name or " insert " in ob.name
                ob.color = (hot * (1.0 if rubbing else 0.6), 0.0, 0.0, 1.0)
                for slot in ob.material_slots:
                    slot.material = thermal
            for ob in polish:
                ob.hide_render = st["stop_y"] < 0.05
                ob.color = (0.8 * hot, 1.0, 0.0, 1.0)
                for slot in ob.material_slots:
                    slot.material = thermal
            info["heat"] = round(hot, 4)
        for n in sky_nodes:
            n.inputs["Strength"].default_value = 0.06 if xr_on else SKY
        sun.data.energy = 1.5 if xr_on else SUN
        bpy.context.view_layer.update()
        if variant == "car":
            info["subject_box"] = hook_gate.project_box(scene, cam, car["root"].matrix_world, (-1.0, -2.4, 0.0), (1.0, 2.4, 1.6))
        elif variant == "crew":
            sy = stop["root"].location.y
            info["subject_box"] = hook_gate.project_box(scene, cam, Matrix.Identity(4), (-2.6, sy - 1.2, 0.0), (2.6, sy + 5.0, 2.4))
        else:
            fy = hero["root"].location.y               # the subject: the train's nose and the stop's buffers and beam (all in front of the
            info["subject_box"] = hook_gate.project_box(scene, cam, Matrix.Identity(4), (-1.6, fy - 3.0, 0.0), (1.6, fy + 1.4, 3.9))   # opening camera)
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        info["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        return info

    segs = tl.segments()
    a0, b0 = (int(v) for v in args.frames.split("-"))
    frames = [int(v) for v in args.list.split(",")] if args.list else list(range(a0, b0 + 1))
    out = []
    for f in frames:
        t0 = time.time()
        sh = tl.frame_state(f, segs)
        if sh["split"]:
            parts = [render_one(sh, args.out / f"frame_{f:05d}_top.png", "top"), render_one(sh, args.out / f"frame_{f:05d}_bot.png", "bottom")]
        else:
            parts = [render_one(sh, args.out / f"frame_{f:05d}.png")]
        info = {"frame": f, "segment": sh["segment"], "split": sh["split"], "parts": parts, "render_seconds": round(time.time() - t0, 1)}
        out.append(info)
        print("STOP_FRAME " + json.dumps(info), flush=True)
    (args.out / f"stop-frames-{frames[0]:05d}.json").write_text(json.dumps({"renderer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                                                           "frames": out}, indent=1))


if __name__ == "__main__":
    main()
