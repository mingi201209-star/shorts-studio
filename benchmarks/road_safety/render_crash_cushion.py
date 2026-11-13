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
from benchmarks.road_safety import cinematic  # noqa: E402

PICTURE_BOTTOM_ROW = base.PICTURE_BOTTOM_ROW
material, cube, lerp, set_visible = base.material, base.cube, base.lerp, base.set_visible
AIM = {}


def set_camera(cam, location, target):
    """base.set_camera, remembering the aim point so depth of field can focus on it."""
    base.set_camera(cam, location, target)
    AIM["target"] = Vector(target)

CONCRETE_END_Y = 10.2
CRUISE_X = 4.3
LANE_LINE_X = 2.6


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
    p.add_argument("--look", choices=("standard", "cinematic"), default=None,
                   help="overrides the manifest's look (default: manifest, else standard)")
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return p.parse_args(argv)


CONTACT_LEAD = 1.0 / motion.SPEED     # start a slow-motion shot 1 m before contact
LOOP_FROM = 4.2                       # s into the closing shot where the loop-back begins
HOOK_SCALE = 0.10


def segments_for(contact: float):
    """Per shot: segments of (until second, case, sim start, time scale).
    Slow motion is a property of the shot, stated here, not of the physics."""
    return {
        "barrels_burst_hook": [(99.0, "array", contact - 1.0 / motion.SPEED, 0.10)],
        # Action stays on screen right after the hook: viewer-retention data from
        # an earlier episode showed the steepest drop at 3.5-6 s, where the
        # picture went from an event to an explanation.
        "sand_takes_speed": [(99.0, "array", contact - 0.7 / motion.SPEED, 0.05)],
        "barrel_cutaway": [(99.0, "array", 0.0, 0.0)],
        "heavier_toward_back": [(99.0, "array", contact - 1.4 / motion.SPEED, 0.13)],
        "wall_vs_array": [(2.0, "wall", contact - 1.0 / motion.SPEED, 0.30),
                          (99.0, "array", contact - 1.0 / motion.SPEED, 0.30)],
        # The last two seconds return to the hook's own camera with the car
        # arriving again, ending one frame before the film's first frame, so
        # the Short loops without a visible seam.
        "guarding_a_hazard": [(LOOP_FROM, "cruise", 0.0, 1.0), (99.0, "loop", 0.0, 0.0)],
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


def composite_hud_pass(scene, cam, hud_objects, frame_path, out):
    """Render the speed read-out alone on a transparent film (no depth of field,
    low samples) and lay it over the finished frame. The read-out is closer to
    the lens than the focus plane, so in the main pass it would be blurred."""
    from PIL import Image
    states = [(ob, ob.hide_render) for ob in bpy.data.objects]
    samples, transparent, dof = scene.cycles.samples, scene.render.film_transparent, cam.data.dof.use_dof
    colour_mode = scene.render.image_settings.color_mode
    hud_path = out / f"_hud_{frame_path.stem}.png"
    try:
        for ob, _ in states:
            ob.hide_render = ob not in hud_objects
        for ob in hud_objects:
            ob.hide_render = False
        scene.cycles.samples = 12
        scene.render.film_transparent = True
        scene.render.image_settings.color_mode = "RGBA"
        cam.data.dof.use_dof = False
        scene.render.filepath = str(hud_path)
        bpy.ops.render.render(write_still=True)
    finally:
        for ob, hidden in states:
            ob.hide_render = hidden
        scene.cycles.samples, scene.render.film_transparent = samples, transparent
        scene.render.image_settings.color_mode = colour_mode
        cam.data.dof.use_dof = dof
        scene.render.filepath = str(frame_path)
    base_image = Image.open(frame_path).convert("RGBA")
    hud_image = Image.open(hud_path).convert("RGBA")
    Image.alpha_composite(base_image, hud_image).convert("RGB").save(frame_path)
    hud_path.unlink()


def main():
    args = arguments()
    manifest = json.loads(args.manifest.read_text(encoding="utf8"))
    shots = manifest["shots"]
    if [s["id"] for s in shots] != list(segments_for(0.0)):
        raise ValueError("manifest shots do not match the renderer's shot list")

    car_root, car_body, wheels, geometry = base.load_source_car(args.source)
    runs = {case: motion.simulate(motion.Scenario(case=case)) for case in ("array", "wall")}
    summaries = {case: motion.summary(runs[case], case) for case in runs}
    particles = motion.build_particles(runs["array"])
    audit = motion.momentum_audit(runs["array"], particles)
    summaries["array"]["sand_momentum_ratio"] = audit["ratio"]
    summaries["array"]["momentum_audit"] = audit
    print("CUSHION_MOTION_SUMMARY " + json.dumps(summaries), flush=True)
    contact = summaries["array"]["contact_s"]
    plans = segments_for(contact)
    burst = motion.burst_times(runs["array"])
    stop = motion.stop_state(runs["array"])
    barrels = motion.barrels()
    nose_len = geometry["nose"]

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    look = args.look or manifest.get("look", cinematic.LOOK_STANDARD)
    scene.cycles.samples = 7 if args.preview else manifest["cycles_samples"]
    if os.environ.get("CUSHION_DEV_SAMPLES"):          # local look-dev only; never set in CI
        scene.cycles.samples = int(os.environ["CUSHION_DEV_SAMPLES"])
    scene.cycles.use_denoising = True
    scene.cycles.transparent_max_bounces = 16
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 4
    width, height = (360, 640) if args.preview else tuple(manifest["resolution"])
    if os.environ.get("CUSHION_DEV_RES"):               # local look-dev only; never set in CI
        width, height = (int(v) for v in os.environ["CUSHION_DEV_RES"].split("x"))
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

    # ----- sand: one point cloud for every grain and dust mote -----------
    # A mesh whose vertices are the grain positions, turned into render
    # points by a Geometry Nodes group (Mesh to Points, per-point radius from
    # the "grain_radius" attribute). One object instead of thousands.
    grains = [p for p in particles if p.kind != "chip"]
    chips = [p for p in particles if p.kind == "chip"]
    grain_mesh = bpy.data.meshes.new("Sand grains")
    grain_mesh.vertices.add(len(grains))
    grain_mesh.attributes.new("grain_radius", "FLOAT", "POINT")
    grain_obj = bpy.data.objects.new("Sand grains", grain_mesh)
    bpy.context.collection.objects.link(grain_obj)
    grain_mat = material("Sand grain", (0.66, 0.50, 0.28), rough=0.95)
    gn = grain_mat.node_tree.nodes
    point_info = gn.new("ShaderNodePointInfo")
    ramp = gn.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.46, 0.33, 0.17, 1)
    ramp.color_ramp.elements[1].color = (0.82, 0.66, 0.38, 1)
    grain_mat.node_tree.links.new(point_info.outputs["Random"], ramp.inputs["Fac"])
    grain_mat.node_tree.links.new(ramp.outputs["Color"], gn.get("Principled BSDF").inputs["Base Color"])
    group = bpy.data.node_groups.new("Sand points", "GeometryNodeTree")
    group.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    group.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    n_in, n_out = group.nodes.new("NodeGroupInput"), group.nodes.new("NodeGroupOutput")
    to_points = group.nodes.new("GeometryNodeMeshToPoints")
    to_points.mode = "VERTICES"
    named = group.nodes.new("GeometryNodeInputNamedAttribute")
    named.data_type = "FLOAT"
    named.inputs["Name"].default_value = "grain_radius"
    set_mat = group.nodes.new("GeometryNodeSetMaterial")
    set_mat.inputs["Material"].default_value = grain_mat
    links = group.links
    links.new(n_in.outputs[0], to_points.inputs["Mesh"])
    links.new(named.outputs["Attribute"], to_points.inputs["Radius"])
    links.new(to_points.outputs["Points"], set_mat.inputs["Geometry"])
    links.new(set_mat.outputs["Geometry"], n_out.inputs[0])
    modifier = grain_obj.modifiers.new("Sand points", "NODES")
    modifier.node_group = group
    grain_obj.visible_shadow = True
    grain_obj.hide_viewport = True      # telemetry rays pass through the sand

    chip_mesh = bpy.data.meshes.new("Shell chip")
    chip_mesh.from_pydata([(-.05, -.03, -.006), (.05, -.03, -.006), (.05, .03, -.006), (-.05, .03, -.006),
                           (-.05, -.03, .006), (.05, -.03, .006), (.05, .03, .006), (-.05, .03, .006)], [],
                          [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)])
    chip_mesh.update()
    chip_mesh.materials.append(chip_mat)
    chip_objects = []
    for i, p in enumerate(chips):
        ob = bpy.data.objects.new(f"Shell chip {i}", chip_mesh)
        bpy.context.collection.objects.link(ob)
        ob.rotation_mode = "AXIS_ANGLE"
        chip_objects.append(ob)
    hidden_xyz = (0.0, 0.0, -5.0)

    # ----- reference marks: stop lines and two labelled length bars ---------
    BAR_WALL_X, BAR_ARRAY_X = 2.8, 4.2
    wall_line = cube("Rigid wall stop line", (0.65, motion.WALL_CRUSH, 0.004), (6.2, 0.07, 0.008), wall_line_mat)
    stop_line = cube("Actual stop line", (0.65, stop.nose, 0.004), (6.2, 0.07, 0.008), stop_line_mat)
    bar_wall = cube("Wall stop length bar", (BAR_WALL_X, motion.WALL_CRUSH / 2, 0.006),
                    (0.24, motion.WALL_CRUSH, 0.012), wall_line_mat)
    bar_array = cube("Barrel stop length bar", (BAR_ARRAY_X, stop.nose / 2, 0.006),
                     (0.24, stop.nose, 0.012), stop_line_mat)
    base_ticks = [cube("Bar base", (x, 0.0, 0.006), (0.6, 0.07, 0.012), tick_mat) for x in (BAR_WALL_X, BAR_ARRAY_X)]

    def label(name, body, size, mat, location, upright):
        curve = bpy.data.curves.new(name, "FONT")
        curve.body = body
        curve.size = size
        curve.align_x = "CENTER"
        curve.extrude = 0.012
        ob = bpy.data.objects.new(name, curve)
        bpy.context.collection.objects.link(ob)
        ob.data.materials.append(mat)
        ob.location = location
        ob.rotation_euler = (math.radians(90.0), 0, 0) if upright else (0, 0, 0)
        return ob

    flat_labels = [label("Flat wall label", "WALL\n~1 m", 0.75, wall_line_mat, (BAR_WALL_X, motion.WALL_CRUSH + 1.25, 0.01), False),
                   label("Flat array label", "BARRELS\n~6 m", 0.75, stop_line_mat, (BAR_ARRAY_X, stop.nose + 1.25, 0.01), False)]
    up_labels = [label("Upright wall label", "WALL ~1 m", 0.8, wall_line_mat, (BAR_WALL_X, motion.WALL_CRUSH + 0.1, 0.55), True),
                 label("Upright array label", "BARRELS ~6 m", 0.8, stop_line_mat, (BAR_ARRAY_X, stop.nose + 0.1, 0.55), True)]
    marks = [wall_line, stop_line, bar_wall, bar_array, *base_ticks]

    # ----- speed read-out: a text object parented to the camera ------------
    hud_curve = bpy.data.curves.new("Speed read-out", "FONT")
    hud_curve.body = "SPEED 90 km/h"
    hud_curve.align_x = "CENTER"
    hud_curve.size = 1.0
    hud2_curve = bpy.data.curves.new("Read-out note", "FONT")
    hud2_curve.body = "SIMULATION | 1,500 kg CAR | HEAD-ON"
    hud2_curve.align_x = "CENTER"
    hud2_curve.size = 1.0
    hud_mat = material("Read-out text", (1.0, 1.0, 1.0), rough=0.5, emission=3.0)
    plate_mat = material("Read-out plate", (0.02, 0.02, 0.03), rough=0.9)
    plate_mat.node_tree.nodes.get("Principled BSDF").inputs["Alpha"].default_value = 0.6
    HUD_DEPTH = 0.3

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
    cam.data.clip_start = 0.05
    hud = bpy.data.objects.new("Speed read-out", hud_curve)
    bpy.context.collection.objects.link(hud)
    hud.data.materials.append(hud_mat)
    hud.parent = cam
    hud2 = bpy.data.objects.new("Read-out note", hud2_curve)
    bpy.context.collection.objects.link(hud2)
    hud2.data.materials.append(hud_mat)
    hud2.parent = cam
    hud2.visible_shadow = False
    hud_plate = cube("Speed read-out plate", (0, 0, 0), (1.0, 1.0, 0.001), plate_mat)
    hud_plate.parent = cam
    hud_plate.visible_shadow = False
    hud.visible_shadow = False

    def sun(name, direction, energy, angle):
        bpy.ops.object.light_add(type="SUN")
        ob = bpy.context.object
        ob.name = name
        ob.data.energy, ob.data.angle = energy, angle
        ob.rotation_euler = Vector(direction).to_track_quat("-Z", "Y").to_euler()
        return ob

    if look == cinematic.LOOK_CINEMATIC:
        sun_to = cinematic.sun_vector((-0.62, 0.75), 24.0)      # low, warm sun behind the camera side of the array
        tune = {"sky": 0.22, "sun": 2.4, "exposure": -1.2, "dust": 0.6, "transform": "Standard"}   # chosen from a four-way look-dev comparison
        if os.environ.get("CUSHION_DEV_LOOK"):            # local look-dev only
            tune.update(json.loads(os.environ["CUSHION_DEV_LOOK"]))
        cinematic.apply_sky(scene, sun_to, strength=tune["sky"], dust=tune["dust"])
        key = sun("Low sun", cinematic.light_direction(sun_to), tune["sun"], 0.03)
        key.data.color = (1.0, 0.82, 0.62)
        scene.view_settings.view_transform = tune["transform"]
        scene.view_settings.exposure = tune["exposure"]
    else:
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
        record_sid = sid
        if case == "loop":
            # Drawn exactly like the hook's opening view, timed to end one
            # frame before the hook's first frame.
            shot_len = (shot["end"] - shot["start"]) / fps
            sim_t = (contact - CONTACT_LEAD) - HOOK_SCALE * (shot_len - s) - HOOK_SCALE / fps
            case, sid, s = "array", "barrels_burst_hook", 0.0
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
            crush = motion.crush_fraction(state.nose, info["row"]) if (array_on and not closing and intact) else 0.0
            sy = 1.0 - motion.CRUSH_RATIO * crush
            info["node"].scale = (1.0, sy, 1.0)
            info["node"].location = (info["x"], info["y"] + motion.BARREL_D / 2.0 * (1.0 - sy), 0.0)
            info["crush"] = crush
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
        coords = [0.0] * (3 * len(grains))
        radii = [0.0] * len(grains)
        drawing = array_on and not closing
        for gi, p in enumerate(grains):
            st = motion.particle_state(p, sim_t_clamped) if drawing else None
            if st is None:
                coords[3 * gi:3 * gi + 3] = hidden_xyz
                continue
            pos = st[0]
            coords[3 * gi], coords[3 * gi + 1], coords[3 * gi + 2] = pos
            radii[gi] = p.radius
            if p.kind == "sand" and st[2]:
                airborne_sand.append((p, pos))
                if pos[1] > state.nose + 0.1 and p.v0[1] >= 0.7 * max(state.speed, 1e-6):
                    flying_ahead.append(pos)
        grain_mesh.vertices.foreach_set("co", coords)
        grain_mesh.attributes["grain_radius"].data.foreach_set("value", radii)
        grain_mesh.update()
        grain_obj.hide_render = not drawing
        for p, ob in zip(chips, chip_objects):
            st = motion.particle_state(p, sim_t_clamped) if drawing else None
            if st is None:
                ob.hide_render = ob.hide_viewport = True
                continue
            ob.hide_render = ob.hide_viewport = False
            ob.location = st[0]
            ob.rotation_axis_angle = (st[1], *p.axis)
        # reference marks
        marks_on = sid == "wall_vs_array"
        for mark in marks:
            set_visible(mark, marks_on)
        top_view = marks_on and case == "wall"
        raised_view = marks_on and case == "array"
        for ob in flat_labels:
            set_visible(ob, top_view)
        for ob in up_labels:
            set_visible(ob, raised_view)
        set_visible(flat_labels[1], False)
        if top_view:
            set_visible(bar_array, False)
            set_visible(stop_line, False)
            set_visible(base_ticks[1], False)
        for ob in hazard:
            set_visible(ob, closing)
        key.data.energy = 5.0
        bpy.context.view_layer.update()

        nose_y = state.nose
        # -------------------------------------------------- cameras
        if sid == "barrels_burst_hook":
            n = max(-1.0, min(7.0, nose_y))
            if s < 2.4:
                set_camera(cam, (-4.4, n + 1.2, 2.3), (0.1, n + 0.3, 0.45))
            elif s < 4.3:
                set_camera(cam, (-2.9, n - 5.0, 3.0), (0.0, n + 1.6, 0.35))
            else:
                # low, from ahead and to the side, looking back at the nose
                set_camera(cam, (-2.6, n + 3.4, 0.7), (0.0, n - 0.4, 0.55))
        elif sid == "barrel_cutaway":
            if s < 2.0:
                u = s / 2.0
                a, d, h = lerp(0.95, 0.45, u), lerp(2.6, 1.9, u), lerp(1.3, 0.95, u)
                set_camera(cam, (-math.cos(a) * d, 3.0 - math.sin(a) * d, h), (0.0, 3.0, 0.5))
            else:
                u = min(1.0, (s - 2.0) / 2.1)
                set_camera(cam, (lerp(-1.9, -1.35, u), 3.0 + lerp(0.15, -0.1, u), lerp(0.62, 0.55, u)),
                           (0.0, 3.0, 0.50))
        elif sid == "sand_takes_speed":
            n = max(-0.6, min(6.0, nose_y))
            if s < 2.2:
                set_camera(cam, (-2.3, n + 1.9, 0.5), (0.0, n + 0.2, 0.5))
            else:
                set_camera(cam, (-1.5, n - 1.8, 0.55), (0.1, n + 1.6, 0.5))
        elif sid == "heavier_toward_back":
            n = max(-1.0, min(7.0, nose_y))
            if s < 3.0:
                cy = lerp(3.5, 3.9, min(1.0, s / 3.0))
                set_camera(cam, (-5.6, cy, 1.0), (0.0, cy, 0.5))
                cam.data.lens = 24
            else:
                set_camera(cam, (-2.5, n - 6.5, 4.6), (0.0, n + 2.8, 0.4))
                cam.data.lens = 30
        elif sid == "wall_vs_array":
            # Straight down, +y up the screen: distance along the stop is the picture.
            if case == "wall":
                cam.data.lens = 26
                yy = lerp(3.0, 3.4, t)
                set_camera(cam, (-0.35, yy - 1.0, 8.2), (0.0, yy, 0.0))
            else:
                cam.data.lens = 30
                u = min(1.0, (s - 2.0) / 3.2)
                set_camera(cam, (-3.2, lerp(-5.0, 0.8, u), 4.4), (0.0, lerp(2.2, 4.8, u), 0.2))
        elif sid == "guarding_a_hazard":
            if s < 1.4:
                u = s / 1.4
                set_camera(cam, (-11.0, lerp(-2.5, -1.8, u), 4.2), (0.0, 5.2, 0.7))
            elif s < 2.8:
                # low and close: yellow barrels in front, the striped concrete end beyond
                u = (s - 1.4) / 1.4
                set_camera(cam, (lerp(-2.7, -2.3, u), lerp(-1.2, -0.2, u), 0.85), (0.0, 4.2, 0.8))
            else:
                u = min(1.0, (s - 2.8) / 1.4)
                set_camera(cam, (lerp(-2.4, -3.2, u), lerp(-10.0, -9.0, u), lerp(5.4, 6.4, u)), (0.0, 5.6, 0.5))
        if sid == "guarding_a_hazard":
            cam.data.lens = 28
        elif sid != "heavier_toward_back" and sid != "wall_vs_array":
            cam.data.lens = 32
        if look == cinematic.LOOK_CINEMATIC and "target" in AIM:
            cinematic.apply_dof(cam, (AIM["target"] - cam.location).length, fstop=2.4)
        hud_on = sid in ("barrels_burst_hook", "sand_takes_speed", "heavier_toward_back", "wall_vs_array")
        hud_objects = (hud, hud2, hud_plate)
        for ob in hud_objects:
            ob.hide_render = not hud_on or look == cinematic.LOOK_CINEMATIC   # cinematic: separate pass below
            ob.hide_viewport = True          # telemetry rays never see it
        if hud_on:
            hud_curve.body = f"SPEED {state.speed * 3.6:.0f} km/h"
            span = HUD_DEPTH * cam.data.sensor_width / cam.data.lens       # frame width at the read-out depth
            k = 0.60 * span / 7.4
            hud.scale = (k, k, k)
            y_off = span * (530.0 / 1080.0)
            hud.location = (0.0, y_off + 0.012 * span - 0.45 * k, -HUD_DEPTH)
            hud2_curve.body = ("STOP DISTANCE FROM FIRST CONTACT" if sid == "wall_vs_array"
                               else "SIMULATION | 1,500 kg CAR | HEAD-ON")
            hud2.scale = (0.34 * k, 0.34 * k, 0.34 * k)
            hud2.location = (0.0, y_off - 0.058 * span, -HUD_DEPTH)
            hud_plate.scale = (0.70 * span, 0.215 * span, 1.0)
            hud_plate.location = (0.0, y_off - 0.012 * span, -HUD_DEPTH - 0.0005)
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
            squashed = [b for b in barrel_nodes if b.get("crush", 0.0) > 0.12 and sim_t_clamped < burst[b["row"]]]
            events["barrel_crushing"] = (in_array and bool(squashed), [(b["x"], b["y"], 0.55) for b in squashed])
            events["sand_in_air"] = (len(airborne_sand) >= 12, [pos for _p, pos in airborne_sand[::max(1, len(airborne_sand) // 8)]][:8])
            events["sand_sped_up"] = (len(flying_ahead) >= 10, flying_ahead[::max(1, len(flying_ahead) // 8)][:8])
            slowing = state.accel < -2.0 and state.speed > 1.0 and state.nose >= -0.01
            events["car_decelerating"] = (slowing, [world((0, nose_len - 0.1, 0.6)), world((0, 0, motion.CG_HEIGHT + 0.6)),
                                                    world((0, -geometry["tail"] + 0.1, 0.6)),
                                                    world((-geometry["body_half_width"], 1.2, 0.7)),
                                                    world((-geometry["body_half_width"], 0.1, 0.9)),
                                                    world((-geometry["body_half_width"], -1.2, 0.7))])
            events["nose_dive"] = (state.pitch > 0.012, [world((-geometry["body_half_width"], 1.2, 0.7)),
                                                         world((0, nose_len - 0.1, 0.55)), world((0, 0.2, geometry["roof"]))])
            if hud_on:
                events["speed_readout_visible"] = (True, [], 0, 0.0)
            if translucent:
                intact_barrels = [b for b in barrel_nodes if sim_t_clamped < burst[b["row"]]]
                events["fill_levels_visible"] = (len(intact_barrels) >= 4,
                                                 [(b["x"], b["y"], b["fill_h"]) for b in intact_barrels], 4, 30.0)
            if sid == "wall_vs_array":
                at_line = case == "wall" and state.speed <= motion.STOPPED_SPEED and abs(state.nose - motion.WALL_CRUSH) < 0.1
                events["wall_case_stop"] = (at_line, [world((0, nose_len, 0.5)), (0.0, motion.WALL_CRUSH, 0.65)], 1, 25.0)
                past = case == "array" and state.nose > motion.WALL_CRUSH + 0.15 and state.speed > motion.STOPPED_SPEED
                events["past_wall_line_still_moving"] = (past, [world((0, nose_len, 0.5)), (0.0, motion.WALL_CRUSH, 0.65)], 1, 25.0)
                if case == "wall":
                    events["distance_bars_visible"] = (True, [(BAR_WALL_X, motion.WALL_CRUSH, 0.006),
                                                              (BAR_WALL_X, 0.05, 0.006),
                                                              (BAR_WALL_X, motion.WALL_CRUSH + 1.25, 0.05)], 2, 25.0)
                else:
                    events["distance_bars_visible"] = (True, [(BAR_WALL_X, motion.WALL_CRUSH, 0.006),
                                                              (BAR_ARRAY_X, stop.nose, 0.006),
                                                              (BAR_WALL_X, motion.WALL_CRUSH + 0.1, 0.55),
                                                              (BAR_ARRAY_X, stop.nose + 0.1, 0.55)], 3, 20.0)
        if cut_view:
            events["barrel_cutaway_visible"] = (True, [(0.25, 3.0, cut_fill_h * 0.5), (0.20, 3.0, cut_fill_h + 0.01),
                                                       (0.0, 3.0 - motion.BARREL_D / 2 + 0.015, 0.5)], 2)
        if closing:
            tops = [next(b for b in barrel_nodes if b["row"] == r) for r in (0, 3, 6)]
            events["array_before_concrete"] = (True, [(0.0, CONCRETE_END_Y, 1.1)] + [(b["x"], b["y"], 0.98) for b in tops], 3, 12.0)

        if record_sid != sid:
            events = {}
            events["car_arriving_again"] = (state.nose < 0.0 and state.speed > 20.0,
                                            [world((0, nose_len - 0.1, 0.6)), world((0, 0.2, geometry["roof"]))])
        record = {"frame": frame, "shot_id": record_sid, "case": case, "sim_t": round(sim_t_clamped, 4),
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
        if look == cinematic.LOOK_CINEMATIC and hud_on:
            composite_hud_pass(scene, cam, hud_objects, frame_path, out)
        elapsed = round(time.perf_counter() - start_time, 3)
        sha = hashlib.sha256(frame_path.read_bytes()).hexdigest()
        checksums.append({"frame": frame, "shot_id": record_sid, "sha256": sha, "render_seconds": elapsed})
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
