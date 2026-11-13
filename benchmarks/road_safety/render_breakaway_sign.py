"""Breakaway sign post episode renderer.

Topic: this project's approved "breakaway road signs" topic
(shorts_studio/factory/series.py, ROAD_SAFETY_FIRST_SEVEN).

Two identical cars hit two identical-looking sign posts at the same instant:
the post in the "rigid" lane is fixed in the ground, the post in the
"breakaway" lane stands on a slip base. Every pose (both cars, the flying
post, the bolts) comes from breakaway_sign_motion; nothing is hand-keyed
except the cameras. Devices that are not literal are labelled in the
manifest: the exploded view of the base, the stroboscopic copies of the post,
the speed read-outs. The cars are not drawn deformed. Not a validated crash
simulation ("physically_calibrated": False).

Every rendered frame records TELEMETRY; assemble_breakaway_sign.py checks the
narration against it sentence by sentence. No frame holds, interpolation or
output upscaling. No upload.
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
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from benchmarks.road_safety import breakaway_sign_motion as motion  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402  (car rig + helpers)

PICTURE_BOTTOM_ROW = base.PICTURE_BOTTOM_ROW
material, cube, lerp, set_camera, set_visible = base.material, base.cube, base.lerp, base.set_camera, base.set_visible

LANE = {"rigid": -2.1, "breakaway": 2.1}
CRUISE_X = -6.2
HOOK_SCALE = 0.12
HOOK_LEAD = 1.0 / motion.SPEED          # the hook starts 1 m before contact
LOOP_FROM = 4.2
GHOST_INTERVAL = 0.06                   # s between stroboscopic copies of the post


def arguments():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--start", type=int, required=True)
    p.add_argument("--end", type=int, required=True)
    p.add_argument("--preview", action="store_true")
    p.add_argument("--telemetry-only", action="store_true")
    p.add_argument("--step", type=int, default=1, help="render every Nth frame (local look-dev only)")
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return p.parse_args(argv)


def segments_for(contact: float):
    """Per shot: segments of (until second, mode, sim start, time scale).
    Slow motion is a property of the shot, stated here, not of the physics.
    Order follows viewer-retention evidence from an earlier episode: action
    stays on screen after the hook, the static diagram comes third, the
    ending loops back to the first frame."""
    return {
        "two_posts_hook": [(99.0, "both", contact - HOOK_LEAD, HOOK_SCALE)],
        "base_lets_go": [(99.0, "both", contact - 0.15 / motion.SPEED, 0.008)],
        "slip_base_exploded": [(99.0, "exploded", 0.0, 0.0)],
        "post_over_roof": [(99.0, "both", contact - 0.5 / motion.SPEED, 0.14)],
        "rigid_vs_breakaway": [(99.0, "both", contact - HOOK_LEAD, 0.12)],
        "signs_stand_ready": [(LOOP_FROM, "cruise", 0.0, 1.0), (99.0, "loop", 0.0, 0.0)],
    }


def cylinder(name, radius, height, location, mat, vertices=24):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=height, location=location)
    ob = bpy.context.object
    ob.name = name
    ob.data.materials.append(mat)
    return ob


def parent_keep(child, parent):
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()


def duplicate_rig(root, body, wheels, paint_from, paint_to):
    """A second car: every object of the rig copied (mesh data shared), parents
    remapped, and the body paint swapped for a second colour."""
    originals = [root, *root.children_recursive]
    copies = {}
    for ob in originals:
        twin = ob.copy()
        bpy.context.collection.objects.link(twin)
        copies[ob] = twin
    for ob, twin in copies.items():
        if ob.parent in copies:
            twin.parent = copies[ob.parent]
            twin.matrix_parent_inverse = ob.matrix_parent_inverse.copy()
        if twin.type == "MESH":
            for slot in twin.material_slots:
                if slot.material == paint_from:
                    slot.link = "OBJECT"
                    slot.material = paint_to
    new_wheels = {k: {"node": copies[w["node"]], "base": w["base"].copy()} for k, w in wheels.items()}
    return copies[root], copies[body], new_wheels


def build_sign(name, x, mats, with_footing):
    """A steel post with a diamond warning sign. Returns the node at the
    centre of mass (so the simulation's pose can be applied directly) and its parts."""
    _m, cm, _i = motion.post_inertia()
    node = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(node)
    node.location = (x, 0.0, cm)
    bpy.context.view_layer.update()
    post = cube(f"{name} post", (x, 0.0, motion.SLIP_PLANE + motion.POST_LENGTH / 2), (0.10, 0.10, motion.POST_LENGTH), mats["steel"])
    # yellow on both faces with a black rim, so the sign reads as a sign from either side
    panel = cube(f"{name} panel", (x, -0.07, motion.PANEL_HEIGHT), (motion.PANEL_SIZE, 0.04, motion.PANEL_SIZE), mats["sign"])
    panel.rotation_euler = (0, math.radians(45), 0)
    border = cube(f"{name} border", (x, -0.07, motion.PANEL_HEIGHT), (motion.PANEL_SIZE + 0.08, 0.02, motion.PANEL_SIZE + 0.08), mats["black"])
    border.rotation_euler = (0, math.radians(45), 0)
    mark = cube(f"{name} mark", (x, -0.07, motion.PANEL_HEIGHT), (0.12, 0.05, 0.45), mats["black"])
    upper = cylinder(f"{name} upper plate", 0.24, 0.025, (x, 0.0, motion.SLIP_PLANE + 0.0125), mats["plate"], vertices=3)
    parts = [post, panel, border, mark, upper]
    bpy.context.view_layer.update()
    for part in parts:
        parent_keep(part, node)
    fixed = [cylinder(f"{name} lower plate", 0.24, 0.025, (x, 0.0, motion.SLIP_PLANE - 0.0125), mats["plate"], vertices=3),
             cube(f"{name} stub", (x, 0.0, (motion.SLIP_PLANE - 0.025) / 2), (0.10, 0.10, motion.SLIP_PLANE - 0.025), mats["steel"])]
    if with_footing:
        fixed.append(cube(f"{name} concrete footing", (x, 0.0, 0.09), (0.7, 0.7, 0.18), mats["concrete"]))
    return node, parts, fixed


def main():
    args = arguments()
    manifest = json.loads(args.manifest.read_text(encoding="utf8"))
    shots = manifest["shots"]
    if [s["id"] for s in shots] != list(segments_for(0.0)):
        raise ValueError("manifest shots do not match the renderer's shot list")

    car_root, car_body, wheels, geometry = base.load_source_car(args.source)
    summaries = motion.summary()
    print("SIGN_MOTION_SUMMARY " + json.dumps(summaries), flush=True)
    cars = {case: motion.simulate_car(case) for case in ("rigid", "breakaway")}
    post_run = motion.simulate_post(cars["breakaway"])
    contact = motion.contact_time(cars["breakaway"])
    plans = segments_for(contact)
    nose_len = geometry["nose"]
    radius = geometry["tyre_radius"]
    _pm, post_cm, _pi = motion.post_inertia()
    land_t = summaries["breakaway"]["post_landed_s"]

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 7 if args.preview else manifest["cycles_samples"]
    scene.cycles.use_denoising = True
    scene.cycles.transparent_max_bounces = 16
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 4
    width, height = (360, 640) if args.preview else tuple(manifest["resolution"])
    scene.render.resolution_x, scene.render.resolution_y = width, height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.view_settings.view_transform = "AgX"
    scene.world.color = (0.20, 0.25, 0.36)
    if scene.world.use_nodes:
        bg = scene.world.node_tree.nodes.get("Background")
        if bg is not None:
            bg.inputs["Color"].default_value = (0.20, 0.25, 0.36, 1)
            bg.inputs["Strength"].default_value = 1.15

    asphalt_mat = material("Asphalt", (0.055, 0.056, 0.06), rough=0.9)
    base.asphalt_grain(asphalt_mat)
    mats = {
        "steel": material("Galvanised steel", (0.55, 0.57, 0.60), metal=0.8, rough=0.35),
        "plate": material("Slip plate", (0.85, 0.42, 0.06), metal=0.3, rough=0.4),
        "sign": material("Warning yellow", (0.98, 0.72, 0.03), rough=0.5),
        "black": material("Sign black", (0.02, 0.02, 0.02), rough=0.6),
        "concrete": material("Concrete footing", (0.60, 0.58, 0.53), rough=0.8),
    }
    stripe_mat = material("Road line", (0.78, 0.76, 0.7), rough=0.6)
    bolt_mat = material("Bolt", (0.75, 0.76, 0.78), metal=0.9, rough=0.3)
    ghost_mat = material("Post position ghost", (0.98, 0.72, 0.03), rough=0.6, emission=0.6)
    ghost_mat.node_tree.nodes.get("Principled BSDF").inputs["Alpha"].default_value = 0.28
    blue_text = material("Rigid read-out", (0.45, 0.70, 1.0), rough=0.5, emission=3.0)
    red_text = material("Breakaway read-out", (1.0, 0.45, 0.38), rough=0.5, emission=3.0)
    white_text = material("Read-out note", (1.0, 1.0, 1.0), rough=0.5, emission=2.5)
    plate_mat = material("Read-out plate", (0.02, 0.02, 0.03), rough=0.9)
    plate_mat.node_tree.nodes.get("Principled BSDF").inputs["Alpha"].default_value = 0.6

    y_lo, y_hi = -70.0, 60.0
    cube("Road surface", (0, (y_lo + y_hi) / 2, -0.05), (22.0, y_hi - y_lo, 0.10), asphalt_mat)
    y = y_lo
    while y < y_hi:
        cube(f"Centre dash {y}", (0.0, y, 0.001), (0.12, 2.4, 0.002), stripe_mat)
        y += 6.0
    for x in (-4.2, 4.2):
        cube(f"Edge line {x}", (x, (y_lo + y_hi) / 2, 0.001), (0.12, y_hi - y_lo, 0.002), stripe_mat)

    # ----- cars: the pinned sedan twice, red (breakaway lane) and blue (rigid lane)
    red_paint = bpy.data.materials.get("blue")
    if red_paint is None:
        raise ValueError("missing original CC0 body material")
    blue_paint = red_paint.copy()
    blue_paint.name = "rigid lane paint"
    for mat, colour in ((red_paint, (0.72, 0.10, 0.08)), (blue_paint, (0.08, 0.22, 0.62))):
        shader = mat.node_tree.nodes.get("Principled BSDF")
        shader.inputs["Base Color"].default_value = (*colour, 1)
        shader.inputs["Metallic"].default_value = 0.3
        shader.inputs["Roughness"].default_value = 0.35
        mat.diffuse_color = (*colour, 1)
    rigs = {"breakaway": (car_root, car_body, wheels)}
    rigs["rigid"] = duplicate_rig(car_root, car_body, wheels, red_paint, blue_paint)

    # ----- the two signs ---------------------------------------------------
    rigid_node, _rigid_parts, _rigid_fixed = build_sign("Rigid sign", LANE["rigid"], mats, with_footing=True)
    post_node, post_parts, _b_fixed = build_sign("Breakaway sign", LANE["breakaway"], mats, with_footing=False)
    bolts = []
    for k in range(3):
        a = math.radians(90 + 120 * k)
        bx, by = LANE["breakaway"] + 0.19 * math.cos(a), 0.19 * math.sin(a)
        b = cylinder(f"Slip bolt {k}", 0.016, 0.11, (bx, by, motion.SLIP_PLANE), bolt_mat, vertices=10)
        bolts.append({"ob": b, "home": Vector((bx, by, motion.SLIP_PLANE)),
                      "v": Vector((1.6 * math.cos(a) + 0.4, 5.0 + 1.5 * k, 2.2 + 0.5 * k))})
    # stroboscopic copies of the flying post (a diagram device)
    ghosts = []
    k = 1
    while contact + k * GHOST_INTERVAL < land_t:
        tk = contact + k * GHOST_INTERVAL
        g_node = bpy.data.objects.new(f"Post ghost {k}", None)
        bpy.context.collection.objects.link(g_node)
        ps = motion.sample(post_run, tk)
        g_post = cube(f"Post ghost {k} post", (0, 0, motion.SLIP_PLANE + motion.POST_LENGTH / 2 - post_cm), (0.10, 0.10, motion.POST_LENGTH), ghost_mat)
        g_panel = cube(f"Post ghost {k} panel", (0, -0.06, motion.PANEL_HEIGHT - post_cm), (motion.PANEL_SIZE, 0.02, motion.PANEL_SIZE), ghost_mat)
        g_panel.rotation_euler = (0, math.radians(45), 0)
        for part in (g_post, g_panel):
            part.parent = g_node
            part.visible_shadow = False
        g_node.location = (LANE["breakaway"], ps.y, ps.z)
        g_node.rotation_euler = (ps.angle, 0, 0)
        ghosts.append((tk, g_node))
        k += 1
    # roadside signs for the closing shot
    roadside = []
    for i, sy in enumerate((-14.0, 2.0, 18.0)):
        node, parts, fixed = build_sign(f"Roadside sign {i}", 6.0, mats, with_footing=False)
        node.location = (6.0, sy, post_cm)
        for ob in fixed:
            ob.location.y += sy
        roadside.append((node, fixed))

    bpy.ops.object.camera_add(location=(0, -8, 2.0))
    cam = bpy.context.object
    scene.camera = cam
    cam.data.sensor_fit = "HORIZONTAL"
    cam.data.sensor_width = 36
    cam.data.lens = 32
    cam.data.shift_y = -260.0 / 1080.0      # picture centre sits at row 700 of 1920
    cam.data.clip_start = 0.05

    def text(name, mat):
        curve = bpy.data.curves.new(name, "FONT")
        curve.align_x = "CENTER"
        curve.size = 1.0
        ob = bpy.data.objects.new(name, curve)
        bpy.context.collection.objects.link(ob)
        ob.data.materials.append(mat)
        ob.parent = cam
        ob.visible_shadow = False
        return ob, curve

    hud_rigid, hud_rigid_curve = text("Rigid read-out", blue_text)
    hud_break, hud_break_curve = text("Breakaway read-out", red_text)
    hud_note, hud_note_curve = text("Read-out note", white_text)
    hud_note_curve.body = "SIMULATION | 1,500 kg CARS | 90 km/h HEAD-ON"
    hud_plate = cube("Read-out plate", (0, 0, 0), (1.0, 1.0, 0.001), plate_mat)
    hud_plate.parent = cam
    hud_plate.visible_shadow = False
    HUD_DEPTH = 0.3

    def sun(name, direction, energy, angle):
        bpy.ops.object.light_add(type="SUN")
        ob = bpy.context.object
        ob.name = name
        ob.data.energy, ob.data.angle = energy, angle
        ob.rotation_euler = Vector(direction).to_track_quat("-Z", "Y").to_euler()
        return ob

    sun("Low sun", (0.45, -0.55, -0.7), 5.0, 0.2)
    sun("Fill", (-0.3, 0.7, -0.6), 2.6, 0.6)

    fps = manifest["fps"]
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    checksums, render_seconds, telemetry = [], [], []

    def shot_for(frame):
        for s in shots:
            if s["start"] <= frame <= s["end"]:
                return s
        raise ValueError(f"frame {frame} not covered by any shot")

    def pose_car(rig, state, x):
        root, body, rig_wheels = rig
        root.location = (x, state.nose - nose_len, 0.0)
        root.rotation_euler = (0, 0, 0)
        body.location = (0, 0, 0)
        body.rotation_euler = (-state.pitch, 0, 0)
        for wheel in rig_wheels.values():
            wheel["node"].location = wheel["base"]
            wheel["node"].rotation_euler = (-state.distance / radius, 0, 0)

    def car_point(case, local):
        return rigs[case][0].matrix_world @ Vector(local)

    def visibility(point, tolerance=0.35, min_px=40.0):
        point = Vector(point)
        ndc = world_to_camera_view(scene, cam, point)
        row = (1.0 - ndc.y) * 1920.0
        in_frame = 0.03 <= ndc.x <= 0.97 and 20.0 <= row <= PICTURE_BOTTOM_ROW - 20.0 and ndc.z > 0.1
        origin = cam.matrix_world.translation
        direction = point - origin
        distance = direction.length
        hit, location, *_ = scene.ray_cast(bpy.context.evaluated_depsgraph_get(), origin, direction.normalized())
        clear = (not hit) or (location - origin).length >= distance - tolerance
        px = 0.30 / max(0.01, ndc.z) * cam.data.lens / cam.data.sensor_width * 1080.0
        return {"in_frame": bool(in_frame), "clear": bool(clear), "px_per_30cm": round(px, 1),
                "visible": bool(in_frame and clear and px >= min_px)}

    def best(points, need=1, min_px=40.0):
        seen = [visibility(p, min_px=min_px) for p in points]
        count = sum(1 for v in seen if v["visible"])
        top = max(seen, key=lambda v: (v["visible"], v["px_per_30cm"])) if seen else {"in_frame": False, "clear": False,
                                                                                    "px_per_30cm": 0.0, "visible": False}
        return {**top, "visible": count >= need, "visible_points": count, "needed": need}

    frames = range(args.start, args.end + 1, max(1, args.step))
    for frame in frames:
        shot = shot_for(frame)
        sid = record_sid = shot["id"]
        t = (frame - shot["start"]) / max(1, shot["end"] - shot["start"])
        s = (frame - shot["start"]) / fps
        seg_start = 0.0
        for until, mode, sim_start, scale in plans[sid]:
            if s < until:
                break
            seg_start = until
        sim_t = sim_start + (s - seg_start) * scale
        if mode == "loop":
            shot_len = (shot["end"] - shot["start"]) / fps
            sim_t = (contact - HOOK_LEAD) - HOOK_SCALE * (shot_len - s) - HOOK_SCALE / fps
            mode, sid, s = "both", "two_posts_hook", 0.0
        events = {}
        cruising = mode == "cruise"
        exploded = mode == "exploded"
        live = mode == "both"
        sim_now = sim_t if live else 0.0
        state = {case: motion.sample(cars[case], sim_now) for case in cars}
        post = motion.sample(post_run, sim_now)

        # cars
        if cruising:
            cruise = motion.CarState(0.0, lerp(-12.0, 16.0, t) + nose_len, motion.SPEED, 0.0, 0.0, lerp(0.0, 28.0, t))
            pose_car(rigs["rigid"], cruise, CRUISE_X)
            set_visible(rigs["rigid"][0], True)
            set_visible(rigs["breakaway"][0], False)
        else:
            for case in cars:
                pose_car(rigs[case], state[case], LANE[case])
                set_visible(rigs[case][0], not exploded)
        # breakaway post, bolts
        lift = 0.0
        if exploded:
            lift = 0.10 * (0.5 - 0.5 * math.cos(2.0 * math.pi * min(1.0, s / 3.2)))    # exploded view opens and closes
        post_node.location = (LANE["breakaway"], post.y, post.z + lift)
        post_node.rotation_euler = (post.angle, 0, 0)
        since = sim_now - contact
        for bolt in bolts:
            if live and since > 0.0:
                p = bolt["home"] + bolt["v"] * since + Vector((0, 0, -0.5 * motion.G * since * since))
                t_ground = (bolt["v"].z + math.sqrt(bolt["v"].z ** 2 + 2 * motion.G * bolt["home"].z)) / motion.G
                if since > t_ground:
                    p = bolt["home"] + bolt["v"] * t_ground
                    p.z = 0.016
                bolt["ob"].location = p
                bolt["ob"].rotation_euler = (min(since, t_ground) * 30.0, 0, 0)
            else:
                bolt["ob"].location = bolt["home"] + Vector((0, 0, lift / 2.0))
                bolt["ob"].rotation_euler = (0, 0, 0)
        ghosts_on = sid == "post_over_roof"
        shown_ghosts = []
        for tk, g_node in ghosts:
            on = ghosts_on and sim_now >= tk
            set_visible(g_node, on)
            for child in g_node.children:
                child.hide_viewport = True
            if on:
                shown_ghosts.append(g_node)
        for node, fixed in roadside:
            set_visible(node, cruising)
            for ob in fixed:
                set_visible(ob, cruising)
        bpy.context.view_layer.update()

        nb = max(-1.0, min(14.0, state["breakaway"].nose))
        bx = LANE["breakaway"]
        lens = 32
        if sid == "two_posts_hook":
            if s < 2.2:
                set_camera(cam, (0.0, 8.5, 2.9), (0.0, -0.8, 1.3))
                lens = 28
            elif s < 4.2:
                set_camera(cam, (bx + 7.5, nb * 0.45 + 0.5, 1.9), (0.0, nb * 0.45 + 0.8, 1.5))
                lens = 26
            else:
                set_camera(cam, (0.0, -9.5, 5.6), (0.0, 5.0, 0.9))
                lens = 28
        elif sid == "base_lets_go":
            foot = motion.post_points(post, 1)[0]
            if s < 2.2:
                set_camera(cam, (bx + 1.25, foot[0] * 0.5 + 0.55, 0.32), (bx, foot[0] * 0.5 + 0.05, 0.14))
            else:
                set_camera(cam, (bx - 0.95, foot[0] * 0.5 + 1.1, 0.42), (bx, foot[0] * 0.5 + 0.1, 0.14))
            lens = 40
        elif sid == "slip_base_exploded":
            a = lerp(0.5, 1.6, t)
            set_camera(cam, (bx + 0.95 * math.cos(a), -0.95 * math.sin(a), lerp(0.45, 0.32, t)), (bx, 0.0, 0.11))
            lens = 40
        elif sid == "post_over_roof":
            if s < 3.0:
                set_camera(cam, (bx + 9.0, lerp(2.2, 3.0, min(1.0, s / 3.0)), 1.9), (bx, lerp(2.2, 3.0, min(1.0, s / 3.0)), 1.9))
                lens = 24
            else:
                set_camera(cam, (bx + 2.2, -7.5, 3.4), (bx, 4.0, 1.3))
                lens = 30
        elif sid == "rigid_vs_breakaway":
            if s < 2.9:
                set_camera(cam, (0.0, -8.5, 4.4), (0.0, 3.5, 0.8))
                lens = 28
            else:
                set_camera(cam, (-7.5, lerp(0.5, 1.5, t), 2.2), (0.5, lerp(2.5, 4.0, t), 0.9))
                lens = 26
        elif sid == "signs_stand_ready":
            if s < 1.4:
                set_camera(cam, (-3.0, lerp(-13.0, -12.0, s / 1.4), 2.6), (5.5, 6.0, 2.2))
            elif s < 2.8:
                set_camera(cam, (6.0 + 1.6, lerp(0.2, 0.9, (s - 1.4) / 1.4), 0.5), (6.0, 2.0, 0.9))
                lens = 30
            else:
                set_camera(cam, (lerp(0.0, 1.0, (s - 2.8) / 1.4), -22.0, 7.5), (4.0, 6.0, 1.5))
                lens = 34
        cam.data.lens = lens

        hud_on = live and sid != "base_lets_go" or sid == "base_lets_go"
        hud_on = hud_on and not exploded and not cruising
        for ob in (hud_rigid, hud_break, hud_note, hud_plate):
            ob.hide_render = not hud_on
            ob.hide_viewport = True
        if hud_on:
            span = HUD_DEPTH * cam.data.sensor_width / cam.data.lens
            y_off = span * (520.0 / 1080.0)
            k = 0.052 * span
            hud_rigid_curve.body = f"FIXED POST  {state['rigid'].speed * 3.6:.0f} km/h"
            hud_break_curve.body = f"BREAKAWAY  {state['breakaway'].speed * 3.6:.0f} km/h"
            hud_rigid.scale = hud_break.scale = (k, k, k)
            hud_rigid.location = (0.0, y_off + 0.040 * span, -HUD_DEPTH)
            hud_break.location = (0.0, y_off - 0.022 * span, -HUD_DEPTH)
            hud_note.scale = (0.38 * k, 0.38 * k, 0.38 * k)
            hud_note.location = (0.0, y_off - 0.066 * span, -HUD_DEPTH)
            hud_plate.scale = (0.74 * span, 0.20 * span, 1.0)
            hud_plate.location = (0.0, y_off + 0.012 * span, -HUD_DEPTH - 0.0005)
        bpy.context.view_layer.update()
        scene.frame_set(frame)
        bpy.context.view_layer.update()

        # ---------------------------------------------- telemetry
        if record_sid != sid:
            arriving = state["breakaway"].nose < 0.0 and state["breakaway"].speed > 20.0
            events["cars_arriving_again"] = (arriving, [car_point("breakaway", (0, nose_len - 0.1, 0.6)),
                                                        car_point("rigid", (0, nose_len - 0.1, 0.6))], 2, 12.0)
        elif live:
            rs, bs = state["rigid"], state["breakaway"]
            pts = motion.post_points(post, 6)
            world_pts = [(bx, py, pz) for py, pz in pts]
            events["rigid_car_stopped"] = (rs.nose >= 0.0 and rs.speed <= motion.STOPPED_SPEED,
                                           [car_point("rigid", (0, nose_len - 0.3, 0.75)), car_point("rigid", (0, 0.2, geometry["roof"])),
                                            car_point("rigid", (-geometry["body_half_width"], 0.5, 0.8)),
                                            car_point("rigid", (geometry["body_half_width"], 0.5, 0.8))], 1, 10.0)
            events["breakaway_car_still_fast"] = (bs.nose > 0.3 and bs.speed > 0.9 * motion.SPEED,
                                                  [car_point("breakaway", (0, nose_len - 0.3, 0.75)), car_point("breakaway", (0, 0.2, geometry["roof"])),
                                                   car_point("breakaway", (geometry["body_half_width"], 0.5, 0.8)),
                                                   car_point("breakaway", (-geometry["body_half_width"], 0.5, 0.8)),
                                                   car_point("breakaway", (0, -geometry["tail"] + 0.2, 0.8))], 1, 10.0)
            events["post_released"] = (post.released and not post.landed, world_pts, 2, 25.0)
            foot_gap = math.hypot(pts[0][0], pts[0][1] - motion.SLIP_PLANE)
            events["base_separating"] = (post.released and 0.005 < foot_gap < 0.8, [world_pts[0], (bx, 0.0, motion.SLIP_PLANE)], 2)
            over = False
            if post.released and not post.landed:
                for py, pz in motion.post_points(post):
                    behind = bs.nose - py
                    if motion.FRONT_FACE <= behind <= motion.CAR_PROFILE[-1][0] and pz > motion.car_height(behind):
                        over = True
            events["post_over_car"] = (over, world_pts, 2, 20.0)
            events["post_landed_behind"] = (post.landed and bs.nose - motion.CAR_PROFILE[-1][0] > post.y,
                                            [(bx, post.y, max(0.1, post.z))], 1, 10.0)
            events["speed_readouts_visible"] = (hud_on, [], 0, 0.0)
            if ghosts_on and len(shown_ghosts) >= 3:
                events["post_arc_marks_visible"] = (True, [tuple(g.location) for g in shown_ghosts], 3, 15.0)
        if exploded:
            events["slip_base_exploded_visible"] = (lift > 0.02, [(bx, 0.0, motion.SLIP_PLANE + lift / 2.0),
                                                                  (bx + 0.19 * math.cos(math.radians(210)), 0.19 * math.sin(math.radians(210)), motion.SLIP_PLANE)], 1)
        if cruising:
            events["signs_along_road"] = (True, [(6.0, sy, motion.PANEL_HEIGHT) for sy in (-14.0, 2.0, 18.0)], 1, 10.0)

        record = {"frame": frame, "shot_id": record_sid, "mode": mode, "sim_t": round(sim_now, 4),
                  "rigid_speed_mps": round(state["rigid"].speed, 3), "breakaway_speed_mps": round(state["breakaway"].speed, 3),
                  "post_angle_deg": round(math.degrees(post.angle), 2), "events": {}}
        for name, spec in events.items():
            active, points = spec[0], spec[1]
            need = spec[2] if len(spec) > 2 else 1
            min_px = spec[3] if len(spec) > 3 else 40.0
            seen = best(points, need, min_px) if active else {"visible": False}
            record["events"][name] = {"active": bool(active), **seen}
        telemetry.append(record)
        if args.telemetry_only:
            continue

        frame_path = out / f"frame_{frame:04d}.png"
        scene.render.filepath = str(frame_path)
        start_time = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        elapsed = round(time.perf_counter() - start_time, 3)
        sha = hashlib.sha256(frame_path.read_bytes()).hexdigest()
        checksums.append({"frame": frame, "shot_id": record_sid, "sha256": sha, "render_seconds": elapsed})
        render_seconds.append(elapsed)
        print(f"SIGN_NATIVE_FRAME {frame}/{manifest['total_frames']}", flush=True)

    if args.telemetry_only:
        (out / "sign-telemetry.json").write_text(json.dumps(
            {"geometry": geometry, "motion_summary": summaries, "telemetry": telemetry}, indent=1))
        print("SIGN_TELEMETRY_DONE " + json.dumps({"frames": len(telemetry)}), flush=True)
        return

    if len({c["sha256"] for c in checksums}) != len(checksums):
        first_seen: dict[str, int] = {}
        pairs = []
        for c in checksums:
            if c["sha256"] in first_seen:
                pairs.append([first_seen[c["sha256"]], c["frame"]])
            else:
                first_seen[c["sha256"]] = c["frame"]
        print("SIGN_DUPLICATE_SOURCE_FRAMES " + json.dumps(pairs), flush=True)
        if not args.preview:
            raise ValueError("duplicate original Blender frames are forbidden")

    result = {
        "episode_id": manifest["episode_id"],
        "renderer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "motion_source_sha256": hashlib.sha256(Path(motion.__file__).read_bytes()).hexdigest(),
        "car_geometry": geometry,
        "motion_summary": summaries,
        "telemetry": telemetry,
        "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "renderer": "CYCLES",
        "blender_version": bpy.app.version_string,
        "blender_build": bpy.app.build_hash.decode(),
        "preview_only": args.preview,
        "frames": len(checksums),
        "first_frame": checksums[0]["frame"],
        "last_frame": checksums[-1]["frame"],
        "frame_numbers": [c["frame"] for c in checksums],
        "fps": manifest["fps"],
        "resolution": [scene.render.resolution_x, scene.render.resolution_y],
        "cycles_samples": scene.cycles.samples,
        "render_seconds": render_seconds,
        "checksums": checksums,
        "physically_calibrated": False,
        "upload_ready": False,
    }
    if not args.preview and (result["resolution"] != manifest["resolution"]
                             or result["cycles_samples"] != manifest["cycles_samples"]):
        raise ValueError("production frame quality cannot differ from approved manifest")
    (out / "sign-proof.json").write_text(json.dumps(result, indent=2))
    print("SIGN_SHARD_DONE " + json.dumps({
        "frame_count": len(checksums), "first": checksums[0]["frame"], "last": checksums[-1]["frame"],
        "preview_only": args.preview, "render_seconds_total": round(sum(render_seconds), 3)}), flush=True)


if __name__ == "__main__":
    main()
