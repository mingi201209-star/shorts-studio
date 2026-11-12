"""Sand-barrel crash cushion episode renderer.

Topic: this project's approved "sand-filled crash barrels" topic
(shorts_studio/factory/series.py, ROAD_SAFETY_FIRST_SEVEN).

What the film claims, and only this (see crash_cushion_motion.py for the
model): a car hits a wedge of sand-filled barrels at highway speed; every
barrel bursts as the nose reaches it; the sand it held is thrown forward at
about the car's speed, which takes momentum from the car; rows toward the
back hold more sand, so the car is slowed lightly at first and harder deeper
in; the stop takes about six metres where a rigid wall would allow about one.

Every pose comes from crash_cushion_motion.simulate(); sand grains and shell
chips are ballistic particles launched by that same simulation. Nothing is
hand-keyed except the cameras. Cutaway devices (a half-cut barrel, translucent
shells) are labelled in the manifest. The car body is not deformed: this is
not a validated crash simulation ("physically_calibrated": False).

Every rendered frame records TELEMETRY (which physical conditions are true in
the simulated state it was drawn from, and whether the place where they
happen is in the visible picture, unoccluded and large enough to read);
assemble_crash_cushion.py checks the narration against it sentence by
sentence. No frame holds, interpolation or output upscaling. No upload.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from benchmarks.road_safety import crash_cushion_motion as motion  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402  (car rig + helpers)

PICTURE_BOTTOM_ROW = base.PICTURE_BOTTOM_ROW
material, cube, lerp, set_camera, set_visible = base.material, base.cube, base.lerp, base.set_camera, base.set_visible

CONCRETE_END_Y = 10.2
CRUISE_X = -4.3
LANE_LINE_X = -2.6


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


CONTACT_LEAD = 1.0 / motion.SPEED     # start a slow-motion shot 1 m before contact


def segments_for(contact: float):
    """Per shot: segments of (until second, case, sim start, time scale).
    Slow motion is a property of the shot, stated here, not of the physics."""
    return {
        "barrels_burst_hook": [(99.0, "array", contact - 1.0 / motion.SPEED, 0.10)],
        "barrel_cutaway": [(99.0, "array", 0.0, 0.0)],
        "sand_takes_speed": [(99.0, "array", contact - 0.7 / motion.SPEED, 0.05)],
        "heavier_toward_back": [(99.0, "array", contact - 1.4 / motion.SPEED, 0.13)],
        "wall_vs_array": [(2.0, "wall", contact - 1.0 / motion.SPEED, 0.25),
                          (99.0, "array", contact - 1.0 / motion.SPEED, 0.25)],
        "guarding_a_hazard": [(99.0, "cruise", 0.0, 1.0)],
    }


# --------------------------------------------------------------- geometry


CUT_FROM, CUT_TO = math.radians(-125.0), math.radians(125.0)   # kept arc; the missing wedge faces -x


def _arc(radius, segments=36):
    return [(radius * math.cos(a), radius * math.sin(a))
            for a in (CUT_FROM + (CUT_TO - CUT_FROM) * i / segments for i in range(segments + 1))]


def half_cylinder(name, radius, z0, z1, mat, segments=36):
    """A vertical cylinder with a wedge cut out of the camera side: the two
    flat cut faces and the top surface show what is inside."""
    arc = _arc(radius, segments)
    n = len(arc)
    verts = [(0.0, 0.0, z0), (0.0, 0.0, z1)] + [(x, y, z0) for x, y in arc] + [(x, y, z1) for x, y in arc]
    lo, hi = 2, 2 + n
    faces = [(lo + i, lo + i + 1, hi + i + 1, hi + i) for i in range(n - 1)]
    faces.append((0, lo, hi, 1))                              # cut face at the start of the arc
    faces.append((1, hi + n - 1, lo + n - 1, 0))              # cut face at the end of the arc
    faces += [(1, hi + i, hi + i + 1) for i in range(n - 1)]  # top surface (fan from the axis)
    faces += [(0, lo + i + 1, lo + i) for i in range(n - 1)]  # bottom
    return _mesh_object(name, verts, faces, mat)


def half_shell(name, r_out, r_in, z0, z1, mat, segments=36):
    outer, inner = _arc(r_out, segments), _arc(r_in, segments)
    n = len(outer)
    verts = ([(x, y, z0) for x, y in outer] + [(x, y, z1) for x, y in outer]
             + [(x, y, z0) for x, y in inner] + [(x, y, z1) for x, y in inner])
    faces = []
    for i in range(n - 1):
        faces.append((i, i + 1, n + i + 1, n + i))                                    # outer wall
        faces.append((2 * n + i + 1, 2 * n + i, 3 * n + i, 3 * n + i + 1))            # inner wall
        faces.append((n + i, n + i + 1, 3 * n + i + 1, 3 * n + i))                    # top rim
        faces.append((i + 1, i, 2 * n + i, 2 * n + i + 1))                            # bottom rim
    faces.append((0, 2 * n, 3 * n, n))                                                # cut end at the arc start
    faces.append((n - 1, 2 * n - 1, 4 * n - 1, 3 * n - 1))                            # cut end at the arc end
    return _mesh_object(name, verts, faces, mat)


def _mesh_object(name, verts, faces, mat):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    mesh.materials.append(mat)
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(ob)
    return ob


def cylinder(name, radius, height, location, mat, vertices=36):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=height, location=location)
    ob = bpy.context.object
    ob.name = name
    ob.data.materials.append(mat)
    return ob


def parent_to(child, parent):
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()


def main():
    args = arguments()
    manifest = json.loads(args.manifest.read_text(encoding="utf8"))
    shots = manifest["shots"]
    if [s["id"] for s in shots] != list(segments_for(0.0)):
        raise ValueError("manifest shots do not match the renderer's shot list")

    car_root, car_body, wheels, geometry = base.load_source_car(args.source)
    runs = {case: motion.simulate(motion.Scenario(case=case)) for case in ("array", "wall")}
    summaries = {case: motion.summary(runs[case], case) for case in runs}
    print("CUSHION_MOTION_SUMMARY " + json.dumps(summaries), flush=True)
    contact = summaries["array"]["contact_s"]
    plans = segments_for(contact)
    burst = motion.burst_times(runs["array"])
    particles = motion.build_particles(runs["array"])
    stop = motion.stop_state(runs["array"])
    barrels = motion.barrels()
    nose_len = geometry["nose"]

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
    scene.world.color = (0.16, 0.19, 0.28)
    if scene.world.use_nodes:
        bg = scene.world.node_tree.nodes.get("Background")
        if bg is not None:
            bg.inputs["Color"].default_value = (0.16, 0.19, 0.28, 1)
            bg.inputs["Strength"].default_value = 1.1

    asphalt_mat = material("Dusk asphalt", (0.055, 0.056, 0.06), rough=0.9)
    base.asphalt_grain(asphalt_mat)
    stripe_mat = material("Road line", (0.78, 0.76, 0.7), rough=0.6)
    yellow = material("Barrel yellow", (0.95, 0.62, 0.04), rough=0.42)
    dark_yellow = material("Barrel band", (0.55, 0.30, 0.02), rough=0.5)
    sand_mat = material("Sand", (0.66, 0.50, 0.28), rough=0.95)
    sand_nodes = sand_mat.node_tree.nodes
    sand_noise = sand_nodes.new("ShaderNodeTexNoise")
    sand_noise.inputs["Scale"].default_value = 90
    sand_noise.inputs["Detail"].default_value = 3
    sand_geo = sand_nodes.new("ShaderNodeNewGeometry")
    sand_bump = sand_nodes.new("ShaderNodeBump")
    sand_bump.inputs["Strength"].default_value = 0.6
    sand_bump.inputs["Distance"].default_value = 0.01
    sand_ramp = sand_nodes.new("ShaderNodeValToRGB")
    sand_ramp.color_ramp.elements[0].color = (0.50, 0.36, 0.19, 1)
    sand_ramp.color_ramp.elements[1].color = (0.78, 0.62, 0.36, 1)
    sand_links = sand_mat.node_tree.links
    sand_links.new(sand_geo.outputs["Position"], sand_noise.inputs["Vector"])
    sand_links.new(sand_noise.outputs["Fac"], sand_ramp.inputs["Fac"])
    sand_links.new(sand_ramp.outputs["Color"], sand_nodes.get("Principled BSDF").inputs["Base Color"])
    sand_links.new(sand_noise.outputs["Fac"], sand_bump.inputs["Height"])
    sand_links.new(sand_bump.outputs["Normal"], sand_nodes.get("Principled BSDF").inputs["Normal"])
    chip_mat = material("Shell chip", (0.95, 0.62, 0.04), rough=0.5)
    concrete = material("Concrete", (0.60, 0.58, 0.53), rough=0.8)
    black = material("Hazard black", (0.02, 0.02, 0.02), rough=0.7)
    hazard_yellow = material("Hazard yellow", (0.95, 0.7, 0.05), rough=0.6)
    glass = material("Translucent shell", (0.95, 0.62, 0.04), rough=0.3)
    glass.node_tree.nodes.get("Principled BSDF").inputs["Alpha"].default_value = 0.22
    wall_line_mat = material("Rigid-wall stopping line", (1.0, 0.36, 0.04), rough=0.5, emission=2.5)
    stop_line_mat = material("Actual stopping line", (0.15, 0.9, 0.3), rough=0.5, emission=2.5)
    wall_panel_mat = material("Rigid-wall stopping plane", (1.0, 0.36, 0.04), rough=0.5, emission=1.2)
    wall_panel_mat.node_tree.nodes.get("Principled BSDF").inputs["Alpha"].default_value = 0.28
    tick_mat = material("Distance tick", (0.9, 0.9, 0.85), rough=0.6)

    y_lo, y_hi = -60.0, 40.0
    cube("Road surface", (0, (y_lo + y_hi) / 2, -0.05), (16.0, y_hi - y_lo, 0.10), asphalt_mat)
    y = y_lo
    while y < y_hi:
        cube(f"Lane dash {y}", (LANE_LINE_X, y, 0.001), (0.12, 2.4, 0.002), stripe_mat)
        y += 6.0
    # one-metre ticks beside the array, so distance along the stop is readable
    ticks = []
    for m in range(0, 9):
        long_tick = m % 5 == 0
        ticks.append(cube(f"Tick {m} m", (-1.95 - (0.15 if long_tick else 0.0), m, 0.002),
                          (0.5 + (0.3 if long_tick else 0.0), 0.06, 0.004), tick_mat))

    # ----- the array (intact barrels) ---------------------------------
    barrel_nodes = []
    for b in barrels:
        node = bpy.data.objects.new(f"Barrel {b['row']}:{b['x']:.2f}", None)
        bpy.context.collection.objects.link(node)
        node.location = (b["x"], b["y"], 0.0)
        shell = cylinder("Shell", motion.BARREL_D / 2, motion.BARREL_HEIGHT,
                         (b["x"], b["y"], motion.BARREL_HEIGHT / 2), yellow)
        bands = [cylinder("Band", motion.BARREL_D / 2 + 0.012, 0.06,
                          (b["x"], b["y"], z), dark_yellow) for z in (0.30, 0.62)]
        lid = cylinder("Lid", motion.BARREL_D / 2 - 0.02, 0.05,
                       (b["x"], b["y"], motion.BARREL_HEIGHT + 0.02), dark_yellow)
        fill_h = motion.fill_height_kg(b["kg"])
        fill = cylinder("Sand fill", motion.BARREL_D / 2 - 0.03, fill_h, (b["x"], b["y"], fill_h / 2), sand_mat)
        bpy.ops.mesh.primitive_cone_add(vertices=20, radius1=motion.pile_radius(b["kg"]), radius2=0.10, depth=0.22,
                                        location=(b["x"], b["y"], 0.11))
        pile = bpy.context.object
        pile.name = "Sand pile"
        pile.data.materials.append(sand_mat)
        pile.rotation_euler = (0, 0, 0)
        for part in (shell, *bands, lid, fill, pile):
            parent_to(part, node)
        barrel_nodes.append({"node": node, "shell_parts": [shell, *bands, lid], "fill": fill, "pile": pile,
                             "row": b["row"], "kg": b["kg"], "x": b["x"], "y": b["y"], "fill_h": fill_h})

    # ----- cutaway barrel for the "what is a barrel" shot ----------------
    cut_node = bpy.data.objects.new("Cutaway barrel", None)
    bpy.context.collection.objects.link(cut_node)
    cut_node.location = (0.0, 3.0, 0.0)
    cut_fill_h = motion.fill_height_kg(max(k for _, k in motion.ROWS))
    cut_parts = [
        half_shell("Cut shell", motion.BARREL_D / 2, motion.BARREL_D / 2 - 0.05, 0.0, motion.BARREL_HEIGHT, yellow),
        half_cylinder("Cut sand", motion.BARREL_D / 2 - 0.05, 0.0, cut_fill_h, sand_mat),
        half_cylinder("Cut lid", motion.BARREL_D / 2 - 0.02, motion.BARREL_HEIGHT, motion.BARREL_HEIGHT + 0.05, dark_yellow),
    ]
    for part in cut_parts:
        parent_to(part, cut_node)

    # ----- ballistic particles -------------------------------------------
    sand_mesh = bpy.data.meshes.new("Sand grain")
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=motion.PARTICLE_RADIUS)
    proto = bpy.context.object
    sand_mesh = proto.data
    sand_mesh.materials.append(sand_mat)
    bpy.data.objects.remove(proto, do_unlink=True)
    chip_mesh = bpy.data.meshes.new("Shell chip")
    chip_mesh.from_pydata([(-.05, -.03, -.006), (.05, -.03, -.006), (.05, .03, -.006), (-.05, .03, -.006),
                           (-.05, -.03, .006), (.05, -.03, .006), (.05, .03, .006), (-.05, .03, .006)], [],
                          [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)])
    chip_mesh.update()
    chip_mesh.materials.append(chip_mat)
    particle_objects = []
    for i, p in enumerate(particles):
        ob = bpy.data.objects.new(f"Particle {i}", sand_mesh if p.kind == "sand" else chip_mesh)
        bpy.context.collection.objects.link(ob)
        ob.rotation_mode = "AXIS_ANGLE"
        particle_objects.append(ob)

    # ----- reference lines -------------------------------------------------
    wall_line = cube("Rigid wall stop line", (0, motion.WALL_CRUSH, 0.004), (5.0, 0.07, 0.008), wall_line_mat)
    wall_panel = cube("Rigid wall stop plane", (0, motion.WALL_CRUSH + 0.03, 0.65), (5.0, 0.03, 1.3), wall_panel_mat)
    stop_line = cube("Actual stop line", (0, stop.nose, 0.004), (5.0, 0.07, 0.008), stop_line_mat)
    stop_panel = cube("Actual stop plane", (0, stop.nose + 0.03, 0.3), (5.0, 0.03, 0.6), wall_panel_mat)
    stop_panel.data.materials.clear()
    stop_panel.data.materials.append(material("Actual stopping plane", (0.15, 0.9, 0.3), rough=0.5, emission=1.2))
    stop_panel.data.materials[0].node_tree.nodes.get("Principled BSDF").inputs["Alpha"].default_value = 0.28
    marks = [wall_line, wall_panel, stop_line, stop_panel]

    # ----- the concrete end the array protects (closing shot only) ---------
    end_block = cube("Concrete barrier end", (0, CONCRETE_END_Y + 1.5, 0.6), (3.0, 3.0, 1.2), concrete)
    hazard = [end_block]
    for k in range(6):
        strip = cube(f"Hazard strip {k}", (-1.25 + k * 0.5, CONCRETE_END_Y - 0.01, 0.62),
                     (0.25, 0.02, 1.0), black if k % 2 == 0 else hazard_yellow)
        hazard.append(strip)

    body_paint = bpy.data.materials.get("blue")
    paint = body_paint.node_tree.nodes.get("Principled BSDF")
    paint.inputs["Base Color"].default_value = (0.72, 0.1, 0.08, 1)
    paint.inputs["Metallic"].default_value = 0.3
    paint.inputs["Roughness"].default_value = 0.35
    body_paint.diffuse_color = (0.72, 0.1, 0.08, 1)

    bpy.ops.object.camera_add(location=(0, -8, 2.0))
    cam = bpy.context.object
    scene.camera = cam
    cam.data.sensor_fit = "HORIZONTAL"
    cam.data.sensor_width = 36
    cam.data.lens = 32
    cam.data.shift_y = -260.0 / 1080.0      # picture centre sits at row 700 of 1920

    def sun(name, direction, energy, angle):
        bpy.ops.object.light_add(type="SUN")
        ob = bpy.context.object
        ob.name = name
        ob.data.energy, ob.data.angle = energy, angle
        ob.rotation_euler = Vector(direction).to_track_quat("-Z", "Y").to_euler()
        return ob

    key = sun("Low dusk sun", (0.45, -0.55, -0.7), 5.0, 0.2)     # travels toward +x, -y: lights fronts facing the car
    sun("Fill", (0.2, 0.7, -0.6), 2.4, 0.6)

    body_materials = {ob: [slot.material for slot in ob.material_slots]
                      for ob in car_body.children_recursive if ob.type == "MESH"}
    half_track = geometry["tyre_outer"]
    radius = geometry["tyre_radius"]
    fps = manifest["fps"]
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    checksums, render_seconds, telemetry = [], [], []

    def shot_for(frame):
        for s in shots:
            if s["start"] <= frame <= s["end"]:
                return s
        raise ValueError(f"frame {frame} not covered by any shot")

    def world(local):
        return car_root.matrix_world @ Vector(local)

    def pose_car(state, x=0.0):
        car_root.location = (x, state.nose - nose_len, 0.0)
        car_root.rotation_euler = (0, 0, 0)
        car_body.location = (0, 0, 0)
        car_body.rotation_euler = (-state.pitch, 0, 0)       # positive pitch = nose down
        for wheel in wheels.values():
            wheel["node"].location = wheel["base"]
            wheel["node"].rotation_euler = (-state.distance / radius, 0, 0)

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
        sid = shot["id"]
        t = (frame - shot["start"]) / max(1, shot["end"] - shot["start"])
        s = (frame - shot["start"]) / fps
        seg_start = 0.0
        for until, case, sim_start, scale in plans[sid]:
            if s < until:
                break
            seg_start = until
        sim_t = sim_start + (s - seg_start) * scale if case != "cruise" else 0.0
        translucent = sid == "heavier_toward_back"
        cut_view = sid == "barrel_cutaway"
        closing = sid == "guarding_a_hazard"
        events = {}

        if case == "cruise":
            base_state = motion.sample(runs["array"], 0.0)
            state = motion.State(t=0.0, nose=lerp(-6.0, 12.0, t) + nose_len, speed=motion.SPEED, accel=0.0, pitch=0.0,
                                 barrel=-1, distance=lerp(0.0, 18.0, t))
            del base_state
            sim_t_clamped = 0.0
        else:
            state = motion.sample(runs[case], sim_t)
            sim_t_clamped = sim_t

        pose_car(state, x=CRUISE_X if closing else 0.0)
        set_visible(car_root, not cut_view)
        array_on = case in ("array", "cruise") and not cut_view
        # barrels, piles
        for info in barrel_nodes:
            t_hit = burst[info["row"]]
            intact = array_on and (closing or sim_t_clamped < t_hit)
            burst_now = array_on and (not closing) and sim_t_clamped >= t_hit
            set_visible(info["node"], False)
            for part in info["shell_parts"]:
                open_top = translucent and part.name.startswith(("Band", "Lid"))
                part.hide_render = not intact or open_top
                part.hide_viewport = not intact or translucent
                part.data.materials.clear()
                part.data.materials.append(glass if translucent else (dark_yellow if part.name.startswith(("Band", "Lid")) else yellow))
                part.visible_shadow = not translucent
            info["fill"].hide_render = not (intact and (translucent or closing is False))
            info["fill"].hide_viewport = info["fill"].hide_render
            grow = max(0.0, min(1.0, (sim_t_clamped - t_hit - 0.04) / 0.25)) if burst_now else 0.0
            info["pile"].hide_render = grow <= 0.0
            info["pile"].hide_viewport = grow <= 0.0
            if grow > 0.0:
                info["pile"].scale = (0.5 + 0.5 * grow, 0.5 + 0.5 * grow, grow)
                info["pile"].location = (info["x"], info["y"], 0.11 * grow)
            info["node"].hide_render = False
        for part in cut_parts:
            part.hide_render = not cut_view
            part.hide_viewport = not cut_view
        cut_node.hide_render = not cut_view
        # particles
        airborne_sand, flying_ahead = [], []
        for p, ob in zip(particles, particle_objects):
            st = motion.particle_state(p, sim_t_clamped) if (array_on and not closing) else None
            if st is None:
                ob.hide_render = ob.hide_viewport = True
                continue
            pos, angle, airborne = st
            ob.hide_render = ob.hide_viewport = False
            ob.location = pos
            if p.kind == "chip":
                ob.rotation_axis_angle = (angle, *p.axis)
            if p.kind == "sand" and airborne:
                airborne_sand.append((p, pos))
                if pos[1] > state.nose + 0.1 and p.v0[1] >= 0.7 * max(state.speed, 1e-6):
                    flying_ahead.append(pos)
        # reference marks
        marks_on = sid == "wall_vs_array" or (sid == "heavier_toward_back" and False)
        for mark in marks:
            set_visible(mark, marks_on)
        for tk in ticks:
            set_visible(tk, not closing and not cut_view)
        for ob in hazard:
            set_visible(ob, closing)
        if sid == "wall_vs_array" and case == "wall":
            set_visible(stop_line, False)
            set_visible(stop_panel, False)
        key.data.energy = 5.0
        bpy.context.view_layer.update()

        nose_y = state.nose
        # -------------------------------------------------- cameras
        if sid == "barrels_burst_hook":
            n = max(-1.0, min(7.0, nose_y))
            if s < 2.4:
                set_camera(cam, (-4.4, n + 1.2, 2.3), (0.1, n + 0.3, 0.45))
            else:
                set_camera(cam, (-2.9, n - 5.0, 3.0), (0.0, n + 1.6, 0.35))
        elif sid == "barrel_cutaway":
            if s < 2.7:
                u = s / 2.7
                a, d, h = lerp(0.95, 0.45, u), lerp(3.4, 2.3, u), lerp(1.6, 1.1, u)
                set_camera(cam, (-math.cos(a) * d, 3.0 - math.sin(a) * d, h), (0.0, 3.0, 0.5))
            else:
                u = min(1.0, (s - 2.7) / 2.5)
                set_camera(cam, (lerp(-1.9, -1.35, u), 3.0 + lerp(0.15, -0.1, u), lerp(0.62, 0.55, u)),
                           (0.0, 3.0, 0.50))
        elif sid == "sand_takes_speed":
            n = max(-0.6, min(6.0, nose_y))
            if s < 2.8:
                set_camera(cam, (-2.3, n + 1.9, 0.5), (0.0, n + 0.2, 0.5))
            else:
                set_camera(cam, (-1.5, n - 1.8, 0.55), (0.1, n + 1.6, 0.5))
        elif sid == "heavier_toward_back":
            n = max(-1.0, min(7.0, nose_y))
            if s < 2.9:
                cy = lerp(2.6, 3.7, min(1.0, s / 2.9))
                set_camera(cam, (-5.6, cy, 1.0), (0.0, cy, 0.5))
                cam.data.lens = 24
            else:
                set_camera(cam, (-2.5, n - 6.5, 4.6), (0.0, n + 2.8, 0.4))
                cam.data.lens = 30
        elif sid == "wall_vs_array":
            # Straight down, +y up the screen: distance along the stop is the picture.
            cam.data.lens = 26
            yy = lerp(3.0, 3.4, t)
            set_camera(cam, (-0.35, yy - 1.0, 8.2), (0.0, yy, 0.0))
        elif sid == "guarding_a_hazard":
            if s < 2.7:
                u = s / 2.7
                set_camera(cam, (-11.0, lerp(-2.5, -1.0, u), 4.2), (0.0, 5.2, 0.7))
            else:
                u = min(1.0, (s - 2.7) / 2.7)
                set_camera(cam, (lerp(-2.4, -3.2, u), lerp(-10.0, -9.0, u), lerp(5.4, 6.4, u)), (0.0, 5.6, 0.5))
        if sid == "guarding_a_hazard":
            cam.data.lens = 28
        elif sid not in ("heavier_toward_back", "wall_vs_array"):
            cam.data.lens = 32
        bpy.context.view_layer.update()
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        if os.environ.get("CUSHION_DEBUG_OBJECTS"):
            for ob in bpy.data.objects:
                if not ob.hide_render and ob.type == "MESH" and not ob.name.startswith(("Particle", "Road", "Lane", "Tick")) \
                        and ob.parent is None:
                    print("DEBUG_OBJ", ob.name, [round(c, 2) for c in ob.matrix_world.translation])

        # ---------------------------------------------- telemetry
        def tyre_top():
            base_pos = wheels["front_right"]["base"]
            return world((base_pos.x, base_pos.y, base_pos.z + radius))

        if not closing and not cut_view:
            in_array = case == "array"
            cut_in = [b for b in barrel_nodes if 0.0 <= sim_t_clamped - burst[b["row"]] <= 0.06]
            events["barrel_burst"] = (in_array and bool(cut_in), [(b["x"], b["y"], 0.5) for b in cut_in])
            events["sand_in_air"] = (len(airborne_sand) >= 12, [pos for _p, pos in airborne_sand[::max(1, len(airborne_sand) // 8)]][:8])
            events["sand_sped_up"] = (len(flying_ahead) >= 10, flying_ahead[::max(1, len(flying_ahead) // 8)][:8])
            slowing = state.accel < -2.0 and state.speed > 1.0 and state.nose >= -0.01
            events["car_decelerating"] = (slowing, [world((0, nose_len - 0.1, 0.6)), world((0, 0, motion.CG_HEIGHT + 0.6)),
                                                    world((0, -geometry["tail"] + 0.1, 0.6))])
            events["nose_dive"] = (state.pitch > 0.012, [world((-geometry["body_half_width"], 1.2, 0.7)),
                                                         world((0, nose_len - 0.1, 0.55)), world((0, 0.2, geometry["roof"]))])
            if translucent:
                intact_barrels = [b for b in barrel_nodes if sim_t_clamped < burst[b["row"]]]
                events["fill_levels_visible"] = (len(intact_barrels) >= 4,
                                                 [(b["x"], b["y"], b["fill_h"]) for b in intact_barrels], 4, 30.0)
            if sid == "wall_vs_array":
                at_line = case == "wall" and state.speed <= motion.STOPPED_SPEED and abs(state.nose - motion.WALL_CRUSH) < 0.1
                events["wall_case_stop"] = (at_line, [world((0, nose_len, 0.5)), (0.0, motion.WALL_CRUSH, 0.65)], 1, 25.0)
                past = case == "array" and state.nose > motion.WALL_CRUSH + 0.15 and state.speed > motion.STOPPED_SPEED
                events["past_wall_line_still_moving"] = (past, [world((0, nose_len, 0.5)), (0.0, motion.WALL_CRUSH, 0.65)], 1, 25.0)
                events["stop_line_marks_visible"] = (case == "array",
                                                     [(sx, ly, 0.004) for sx in (-2.2, 2.2) for ly in (motion.WALL_CRUSH, stop.nose)], 3, 25.0)
        if cut_view:
            events["barrel_cutaway_visible"] = (True, [(0.25, 3.0, cut_fill_h * 0.5), (0.20, 3.0, cut_fill_h + 0.01),
                                                       (0.0, 3.0 - motion.BARREL_D / 2 + 0.015, 0.5)], 2)
        if closing:
            events["array_before_concrete"] = (True, [(0.0, CONCRETE_END_Y, 0.6), (0.0, 0.5, 0.9), (1.0, 3.5, 0.9)], 3, 12.0)

        record = {"frame": frame, "shot_id": sid, "case": case, "sim_t": round(sim_t_clamped, 4),
                  "speed_mps": round(state.speed, 3), "nose_m": round(state.nose, 3), "pitch_deg": round(math.degrees(state.pitch), 3),
                  "events": {}}
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
        checksums.append({"frame": frame, "shot_id": sid, "sha256": sha, "render_seconds": elapsed})
        render_seconds.append(elapsed)
        print(f"CUSHION_NATIVE_FRAME {frame}/{manifest['total_frames']}", flush=True)

    if args.telemetry_only:
        (out / "cushion-telemetry.json").write_text(json.dumps(
            {"geometry": geometry, "motion_summary": summaries, "telemetry": telemetry}, indent=1))
        print("CUSHION_TELEMETRY_DONE " + json.dumps({"frames": len(telemetry)}), flush=True)
        return

    if len({c["sha256"] for c in checksums}) != len(checksums):
        first_seen: dict[str, int] = {}
        pairs = []
        for c in checksums:
            if c["sha256"] in first_seen:
                pairs.append([first_seen[c["sha256"]], c["frame"]])
            else:
                first_seen[c["sha256"]] = c["frame"]
        print("CUSHION_DUPLICATE_SOURCE_FRAMES " + json.dumps(pairs), flush=True)
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
    (out / "cushion-proof.json").write_text(json.dumps(result, indent=2))
    print("CUSHION_SHARD_DONE " + json.dumps({
        "frame_count": len(checksums), "first": checksums[0]["frame"], "last": checksums[-1]["frame"],
        "preview_only": args.preview, "render_seconds_total": round(sum(render_seconds), 3)}), flush=True)


if __name__ == "__main__":
    main()
