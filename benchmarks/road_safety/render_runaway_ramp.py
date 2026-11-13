"""Runaway-truck-ramp episode renderer (gravel arrester bed).

What the film claims, and only this (see runaway_ramp_motion.py): a 20 t truck
without brakes enters a level gravel bed at 90 km/h; the tyres sink and push
stones aside; the bed's rolling resistance (assumed 0.25 g, against an assumed
0.01 g on pavement) stops it in about 130 m where pavement would take over
three kilometres. Every pose and every stone comes from runaway_ramp_motion;
only cameras are hand-keyed. The truck is built from primitives (no truck asset
is available under a free licence in this repository), is not deformed, and
this is not a validated simulation ("physically_calibrated": False).

Every frame records TELEMETRY (which conditions hold in the simulated state and
whether the place where they happen is in the visible, unoccluded picture);
assemble_runaway_ramp.py checks the narration against it sentence by sentence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import sys
import time
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_crash_cushion as cc  # noqa: E402  (HUD pass, primitives)
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402
from benchmarks.road_safety import runaway_ramp_motion as motion  # noqa: E402

material, cube, lerp = base.material, base.cube, base.lerp
PICTURE_BOTTOM_ROW = base.PICTURE_BOTTOM_ROW
BED_Y1, BED_HALF = 170.0, 3.6
HIGHWAY_X = -13.0
CUT_Y = 230.0
TRUCK_LEN = 14.8
PRE_ROLL = 0.0


def arguments():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--start", type=int, required=True)
    p.add_argument("--end", type=int, required=True)
    p.add_argument("--source", type=Path, default=None, help="unused (no external assets); accepted for workflow parity")
    p.add_argument("--preview", action="store_true")
    p.add_argument("--telemetry-only", action="store_true")
    p.add_argument("--step", type=int, default=1)
    p.add_argument("--look", choices=("standard", "cinematic"), default=None)
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return p.parse_args(argv)


#: film frame -> simulated time (s since the first tyre touches gravel), per shot.
SIM_RANGE = {"gravel_hook": (-0.30, 3.2), "tyres_sink": (3.2, 5.6), "bed_cutaway": (5.6, 5.6),
             "drag_numbers": (5.6, 10.4), "stop_distance": (10.4, 12.0), "ramp_beside_road": (12.0, 12.0)}


def truck_nose(states, sim_t):
    """Nose position along the bed (m): constant speed on the approach, simulated inside."""
    if sim_t < 0.0:
        return motion.SPEED0 * sim_t, motion.SPEED0, 0.0
    i = min(int(sim_t * motion.FPS), len(states) - 1)
    f = sim_t * motion.FPS - i
    a, b = states[i], states[min(i + 1, len(states) - 1)]
    return lerp(a["x"], b["x"], f), lerp(a["v"], b["v"], f), lerp(a["a"], b["a"], f)


def build_truck(mats):
    root = bpy.data.objects.new("Truck", None)
    bpy.context.collection.objects.link(root)
    parts, wheels = [], []

    def box(name, c, d, mat):
        ob = cube(name, c, d, mat)
        cc.parent_to(ob, root)
        return ob

    box("Chassis", (0, -7.4, 0.95), (2.1, 14.0, 0.3), mats["black"])
    box("Cab", (0, -1.6, 2.15), (2.45, 3.0, 2.2), mats["cab"])
    box("Windscreen", (0, -0.12, 2.55), (2.0, 0.06, 0.9), mats["glass"])
    box("Grille", (0, 0.02, 1.55), (1.8, 0.06, 0.6), mats["black"])
    box("Bumper", (0, 0.1, 1.05), (2.5, 0.35, 0.35), mats["black"])
    box("Trailer", (0, -8.35, 2.55), (2.55, 10.6, 2.9), mats["trailer"])
    for k in range(7):
        box(f"Rib {k}", (0, -3.7 - k * 1.55, 2.55), (2.62, 0.08, 2.95), mats["rib"])
    for sx in (-1, 1):
        box(f"Mirror {sx}", (sx * 1.4, -0.7, 2.7), (0.1, 0.18, 0.6), mats["black"])
    for ay in motion.AXLES_Y:
        for wx in motion.WHEEL_X:
            bpy.ops.mesh.primitive_cylinder_add(vertices=28, radius=motion.WHEEL_R, depth=0.34, location=(0, 0, 0))
            w = bpy.context.object
            w.name = "Wheel"
            w.data.materials.append(mats["rubber"])
            w.rotation_mode = "XYZ"
            w.rotation_euler = (0, math.radians(90), 0)
            hub = cc.cylinder("Hub", 0.2, 0.36, (0, 0, 0), mats["hub"], vertices=16)
            hub.rotation_euler = (0, math.radians(90), 0)
            spin = bpy.data.objects.new("Wheel spin", None)
            bpy.context.collection.objects.link(spin)
            spin.parent = root
            spin.location = (wx, ay, motion.WHEEL_R)
            cc.parent_to(w, spin)
            cc.parent_to(hub, spin)
            # lug marks so rotation is visible
            for k in range(5):
                lug = cube("Lug", (0, 0, 0), (0.37, 0.05, 0.08), mats["rim"])
                lug.location = (0.0, 0.0, 0.0)
                lug.rotation_euler = (math.radians(k * 36.0), 0, 0)
                lug.parent = spin
                lug.location = (0.0, 0.0, 0.0)
            wheels.append(spin)
    return root, wheels


def main():
    args = arguments()
    manifest = json.loads(args.manifest.read_text(encoding="utf8"))
    shots = manifest["shots"]
    if [s["id"] for s in shots] != list(SIM_RANGE):
        raise ValueError("manifest shots do not match the renderer's shot list")
    states = motion.simulate()
    summary = motion.summary(states)
    summary["paved_stop_distance_m"] = round(motion.stop_distance(motion.PAVED_C), 0)
    summary["energy_ratio"] = round(motion.audit_energy(states)["ratio"], 4)
    gravel = motion.build_gravel(states)
    dust = motion.build_dust(states)
    summary["gravel_grains"] = len(gravel)
    stop_x = states[-1]["x"]
    print("RAMP_MOTION_SUMMARY " + json.dumps(summary), flush=True)

    scene = bpy.context.scene
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.world = bpy.data.worlds.new("World")
    scene.world.use_nodes = True
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    look = args.look or manifest.get("look", cinematic.LOOK_STANDARD)
    scene.cycles.samples = 7 if args.preview else manifest["cycles_samples"]
    if os.environ.get("CUSHION_DEV_SAMPLES"):
        scene.cycles.samples = int(os.environ["CUSHION_DEV_SAMPLES"])
    scene.cycles.use_denoising = True
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 4
    width, height = (360, 640) if args.preview else tuple(manifest["resolution"])
    if os.environ.get("CUSHION_DEV_RES"):
        width, height = (int(v) for v in os.environ["CUSHION_DEV_RES"].split("x"))
    scene.render.resolution_x, scene.render.resolution_y = width, height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.view_settings.view_transform = "AgX"

    asphalt = material("Asphalt", (0.07, 0.07, 0.075), rough=0.9)
    base.asphalt_grain(asphalt)
    line_mat = material("Road line", (0.8, 0.78, 0.72), rough=0.6)
    earth = material("Hillside", (0.17, 0.15, 0.085), rough=1.0)
    forest = material("Forest", (0.06, 0.12, 0.06), rough=1.0)
    gravel_slab = material("Gravel bed", (0.55, 0.50, 0.42), rough=0.95)
    gnodes = gravel_slab.node_tree.nodes
    noise = gnodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 70
    noise.inputs["Detail"].default_value = 6
    geo = gnodes.new("ShaderNodeNewGeometry")
    bump = gnodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.9
    bump.inputs["Distance"].default_value = 0.03
    ramp = gnodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.48, 0.38, 0.26, 1)
    ramp.color_ramp.elements[1].color = (0.98, 0.80, 0.52, 1)
    gl = gravel_slab.node_tree.links
    gl.new(geo.outputs["Position"], noise.inputs["Vector"])
    gl.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    gl.new(ramp.outputs["Color"], gnodes.get("Principled BSDF").inputs["Base Color"])
    gl.new(noise.outputs["Fac"], bump.inputs["Height"])
    gl.new(bump.outputs["Normal"], gnodes.get("Principled BSDF").inputs["Normal"])
    mats = {"black": material("Truck black", (0.02, 0.02, 0.02), rough=0.6),
            "cab": material("Cab", (0.62, 0.07, 0.05), metal=0.2, rough=0.35),
            "trailer": material("Trailer", (0.86, 0.86, 0.84), rough=0.5),
            "rib": material("Trailer rib", (0.6, 0.6, 0.6), rough=0.5),
            "glass": material("Glass", (0.05, 0.07, 0.09), metal=0.4, rough=0.1),
            "rubber": material("Tyre", (0.015, 0.015, 0.015), rough=0.8),
            "hub": material("Hub", (0.55, 0.55, 0.57), metal=0.8, rough=0.3),
            "rim": material("Lug", (0.9, 0.9, 0.92), rough=0.5)}
    tick_mat = material("Distance tick", (0.9, 0.9, 0.85), rough=0.6)
    green = material("Actual stopping bar", (0.15, 0.9, 0.3), rough=0.5, emission=2.5)
    orange = material("Pavement coast bar", (1.0, 0.36, 0.04), rough=0.5, emission=2.5)

    # ----- terrain, highway, ramp -----------------------------------------
    cube("Terrain", (0, 120, -0.06), (700, 900, 0.1), earth)
    rng = random.Random(3)
    for k in range(14):
        x = rng.choice((-1, 1)) * rng.uniform(70, 180)
        y = rng.uniform(-80, 360)
        bpy.ops.mesh.primitive_cone_add(vertices=7, radius1=rng.uniform(25, 55), radius2=rng.uniform(2, 8),
                                        depth=rng.uniform(30, 70), location=(x, y, 15))
        bpy.context.object.data.materials.append(forest)
    cube("Highway", (HIGHWAY_X, 120, -0.02), (8.0, 900, 0.1), asphalt)
    for y in range(-300, 600, 12):
        cube(f"Dash {y}", (HIGHWAY_X, y, 0.04), (0.14, 5.0, 0.01), line_mat)
    cube("Approach", (0, -140, -0.02), (7.2, 280, 0.1), asphalt)
    for y in range(-280, 0, 10):
        cube(f"Edge L {y}", (-3.35, y + 2.5, 0.04), (0.12, 5.0, 0.01), line_mat)
        cube(f"Edge R {y}", (3.35, y + 2.5, 0.04), (0.12, 5.0, 0.01), line_mat)
    bed = cube("Gravel bed", (0, BED_Y1 / 2, -0.04), (2 * BED_HALF, BED_Y1, 0.1), gravel_slab)
    # a berm only on the far (left) side: a berm on the camera side hides the bed from low cameras
    cube("Berm", (-(BED_HALF + 0.9), BED_Y1 / 2, 0.35), (1.6, BED_Y1, 0.8), earth)
    cube("Bed end berm", (0, BED_Y1 + 3.0, 1.0), (10.0, 6.0, 2.0), earth)
    ticks = []
    for m in range(0, int(BED_Y1) + 1, 10):
        long_tick = m % 50 == 0
        ticks.append(cube(f"Tick {m}", (BED_HALF + 0.3, m, 0.02), (0.6 + (0.9 if long_tick else 0.0), 0.12, 0.04), tick_mat))

    # static stones for close shots (a point cloud, like the sand episode)
    def point_cloud(name, positions, radii, mat):
        mesh = bpy.data.meshes.new(name)
        mesh.vertices.add(len(positions))
        mesh.vertices.foreach_set("co", [c for p in positions for c in p])
        mesh.attributes.new("grain_radius", "FLOAT", "POINT")
        mesh.attributes["grain_radius"].data.foreach_set("value", radii)
        mesh.update()
        ob = bpy.data.objects.new(name, mesh)
        bpy.context.collection.objects.link(ob)
        group = bpy.data.node_groups.new(name + " points", "GeometryNodeTree")
        group.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        group.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
        n_in, n_out = group.nodes.new("NodeGroupInput"), group.nodes.new("NodeGroupOutput")
        to_points = group.nodes.new("GeometryNodeMeshToPoints")
        to_points.mode = "VERTICES"
        named = group.nodes.new("GeometryNodeInputNamedAttribute")
        named.data_type = "FLOAT"
        named.inputs["Name"].default_value = "grain_radius"
        set_mat = group.nodes.new("GeometryNodeSetMaterial")
        set_mat.inputs["Material"].default_value = mat
        group.links.new(n_in.outputs[0], to_points.inputs["Mesh"])
        group.links.new(named.outputs["Attribute"], to_points.inputs["Radius"])
        group.links.new(to_points.outputs["Points"], set_mat.inputs["Geometry"])
        group.links.new(set_mat.outputs["Geometry"], n_out.inputs[0])
        mod = ob.modifiers.new(name + " points", "NODES")
        mod.node_group = group
        return ob, mesh

    stone_mat = material("Stone", (0.55, 0.5, 0.42), rough=0.9)
    sn = stone_mat.node_tree.nodes
    pinfo = sn.new("ShaderNodePointInfo")
    sramp = sn.new("ShaderNodeValToRGB")
    sramp.color_ramp.elements[0].color = (0.50, 0.38, 0.24, 1)
    sramp.color_ramp.elements[1].color = (1.0, 0.80, 0.50, 1)
    stone_mat.node_tree.links.new(pinfo.outputs["Random"], sramp.inputs["Fac"])
    stone_mat.node_tree.links.new(sramp.outputs["Color"], sn.get("Principled BSDF").inputs["Base Color"])
    WINDOW_ROWS, STONES_PER_CELL = 44, 190          # 1 m rows along the bed, 7 cells across
    CELLS_ACROSS = int(2 * BED_HALF)

    def window_stones(first_row):
        """Stones of a 44 m stretch of the bed starting at row `first_row`. Each 1 m cell
        draws its stones from its own seed, so a stone stays where it is whichever
        window it appears in."""
        pos, radii = [], []
        for row in range(first_row, first_row + WINDOW_ROWS):
            for col in range(CELLS_ACROSS):
                r = random.Random(row * 977 + col * 31 + 5)
                for _ in range(STONES_PER_CELL):
                    rad = r.uniform(0.014, 0.032)
                    pos.append((-BED_HALF + col + r.random(), row + r.random(), rad * 0.6))
                    radii.append(rad)
        return pos, radii

    static_pos, static_r = window_stones(0)
    static_ob, static_mesh = point_cloud("Static stones", static_pos, static_r, stone_mat)
    static_ob.hide_viewport = True
    window_state = {"row": 0}
    srng = random.Random(11)

    grains_ob, grains_mesh = point_cloud("Flying stones", [(0, 0, -5)] * len(gravel), [0.02] * len(gravel), stone_mat)
    grains_mesh.attributes["grain_radius"].data.foreach_set("value", [g["r"] for g in gravel])
    grains_ob.hide_viewport = True
    dust_mat = material("Dust", (0.74, 0.66, 0.50), rough=1.0)
    dust_ob, dust_mesh = point_cloud("Dust", [(0, 0, -5)] * len(dust), [d["r"] for d in dust], dust_mat)
    dust_ob.hide_viewport = True

    # ----- cutaway slice of the bed (shot 3) ------------------------------
    SLAB_D = 0.6
    slab = cube("Cut slab", (0, CUT_Y + 0.8, SLAB_D / 2), (2.6, 1.6, SLAB_D), gravel_slab)
    face_pos, face_r = [], []
    for _ in range(7000):
        r = srng.uniform(0.02, 0.05)
        face_pos.append((srng.uniform(-1.3, 1.3), CUT_Y + 0.0 - r * 0.2, srng.uniform(r * 0.5, SLAB_D - r * 0.5)))
        face_r.append(r)
    face_ob, _ = point_cloud("Cut face stones", face_pos, face_r, stone_mat)
    face_ob.hide_viewport = True
    CUT_YC = CUT_Y + 0.8                       # the wheel rolls across the middle of the slab, axle along y
    cut_spin = bpy.data.objects.new("Cut wheel spin", None)
    bpy.context.collection.objects.link(cut_spin)
    cut_spin.location = (motion.CUT_ROLL_X[0], CUT_YC, motion.CUT_SLAB_D + motion.WHEEL_R)
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=motion.WHEEL_R, depth=0.34, location=cut_spin.location)
    cut_tyre = bpy.context.object
    cut_tyre.rotation_euler = (math.radians(90), 0, 0)
    cut_tyre.data.materials.append(mats["rubber"])
    cut_hub = cc.cylinder("Cut hub", 0.2, 0.36, cut_spin.location, mats["hub"], vertices=16)
    cut_hub.rotation_euler = (math.radians(90), 0, 0)
    for part in (cut_tyre, cut_hub):
        cc.parent_to(part, cut_spin)
    for k in range(4):                          # white marks on the sidewall so the spin shows
        ang = math.radians(k * 90.0)
        mark = cube("Cut sidewall mark", (0, 0, 0), (0.09, 0.02, 0.09), mats["rim"])
        mark.location = (cut_spin.location.x + 0.33 * math.sin(ang), cut_spin.location.y - 0.175,
                         cut_spin.location.z + 0.33 * math.cos(ang))
        cc.parent_to(mark, cut_spin)
    cut_seconds = (shots[2]["end"] - shots[2]["start"] + 1) / manifest["fps"]
    cut_grains = motion.build_cut_grains(cut_seconds, CUT_YC)
    cut_stones_ob, cut_stones_mesh = point_cloud("Cut stones", [(0, 0, -5)] * len(cut_grains),
                                                 [g["r"] for g in cut_grains], stone_mat)
    cut_stones_ob.hide_viewport = True
    cut_objs = [slab, face_ob, cut_stones_ob, cut_spin, *cut_spin.children_recursive]

    truck, wheels = build_truck(mats)

    # ----- text -----------------------------------------------------------
    def label(name, body, size, mat, location, flat):
        curve = bpy.data.curves.new(name, "FONT")
        curve.body, curve.size, curve.align_x, curve.extrude = body, size, "CENTER", 0.02
        ob = bpy.data.objects.new(name, curve)
        bpy.context.collection.objects.link(ob)
        ob.data.materials.append(mat)
        ob.location = location
        ob.rotation_euler = (0, 0, 0) if flat else (math.radians(90.0), 0, 0)
        return ob

    flat_labels = [label("Tick 50", "50 m", 2.0, tick_mat, (BED_HALF + 2.6, 50.0, 0.05), True),
                   label("Tick 100", "100 m", 2.0, tick_mat, (BED_HALF + 2.9, 100.0, 0.05), True),
                   label("Tick 150", "150 m", 2.0, tick_mat, (BED_HALF + 2.9, 150.0, 0.05), True)]
    stop_label = label("Stop label", "STOPS ~130 m", 3.0, green, (4.2, stop_x * 0.5, 0.06), True)
    stop_label.rotation_euler = (0, 0, math.radians(-90))
    paved_label = label("Pavement label", "PAVEMENT: OVER 3 km", 3.0, orange, (-4.2, 70, 0.06), True)
    paved_label.rotation_euler = (0, 0, math.radians(90))
    bar_green = cube("Stop bar", (2.6, stop_x / 2, 0.06), (0.9, stop_x, 0.1), green)
    bar_orange = cube("Pavement bar", (-2.6, 450.0, 0.06), (0.9, 900.0, 0.1), orange)
    label_objs = [*flat_labels, stop_label, paved_label, bar_green, bar_orange]
    cut_label = label("Cut label", "BED DEPTH ~0.6 m (DRAWN)", 0.12, tick_mat, (0.0, CUT_Y - 0.9, 0.12), False)

    # ----- HUD ------------------------------------------------------------
    hud_curve = bpy.data.curves.new("Speed read-out", "FONT")
    hud_curve.body, hud_curve.align_x, hud_curve.size = "SPEED 90 km/h", "CENTER", 1.0
    hud2_curve = bpy.data.curves.new("Read-out note", "FONT")
    hud2_curve.body, hud2_curve.align_x, hud2_curve.size = "SIMULATION | 20,000 kg TRUCK | NO BRAKES", "CENTER", 1.0
    hud_mat = material("Read-out text", (1.0, 1.0, 1.0), rough=0.5, emission=3.0)
    plate_mat = material("Read-out plate", (0.02, 0.02, 0.03), rough=0.9)
    plate_mat.node_tree.nodes.get("Principled BSDF").inputs["Alpha"].default_value = 0.6
    HUD_DEPTH = 0.3

    bpy.ops.object.camera_add(location=(0, -8, 2.0))
    cam = bpy.context.object
    scene.camera = cam
    cam.data.sensor_fit, cam.data.sensor_width, cam.data.lens = "HORIZONTAL", 36, 32
    cam.data.shift_y = -260.0 / 1080.0
    cam.data.clip_start, cam.data.clip_end = 0.05, 2000.0
    hud = bpy.data.objects.new("Speed read-out", hud_curve)
    hud2 = bpy.data.objects.new("Read-out note", hud2_curve)
    for ob in (hud, hud2):
        bpy.context.collection.objects.link(ob)
        ob.data.materials.append(hud_mat)
        ob.parent = cam
        ob.visible_shadow = False
    hud_plate = cube("Speed read-out plate", (0, 0, 0), (1.0, 1.0, 0.001), plate_mat)
    hud_plate.parent = cam
    hud_plate.visible_shadow = False
    hud4_curve = bpy.data.curves.new("Brake warning", "FONT")
    hud4_curve.body, hud4_curve.align_x, hud4_curve.size = "BRAKES FAILED", "CENTER", 1.0
    warn_mat = material("Warning text", (1.0, 0.12, 0.05), rough=0.5, emission=4.0)
    warn_plate_mat = material("Warning plate", (0.03, 0.0, 0.0), rough=0.9)
    hud4 = bpy.data.objects.new("Brake warning", hud4_curve)
    bpy.context.collection.objects.link(hud4)
    hud4.data.materials.append(warn_mat)
    hud4.parent = cam
    hud4.visible_shadow = False
    hud4_plate = cube("Brake warning plate", (0, 0, 0), (1.0, 1.0, 0.001), warn_plate_mat)
    hud4_plate.parent = cam
    hud4_plate.visible_shadow = False
    hud3_curve = bpy.data.curves.new("Drag note", "FONT")
    hud3_curve.body, hud3_curve.align_x, hud3_curve.size = "GRAVEL 0.25 g   |   PAVEMENT 0.01 g (ASSUMED)", "CENTER", 1.0
    hud3 = bpy.data.objects.new("Drag note", hud3_curve)
    bpy.context.collection.objects.link(hud3)
    hud3.data.materials.append(hud_mat)
    hud3.parent = cam
    hud3.visible_shadow = False

    def sun(name, direction, energy, angle):
        bpy.ops.object.light_add(type="SUN")
        ob = bpy.context.object
        ob.name = name
        ob.data.energy, ob.data.angle = energy, angle
        ob.rotation_euler = Vector(direction).to_track_quat("-Z", "Y").to_euler()
        return ob

    if look == cinematic.LOOK_CINEMATIC:
        sun_to = cinematic.sun_vector((-0.55, 0.8), 26.0)
        cinematic.apply_sky(scene, sun_to, strength=0.14, dust=0.6)
        key = sun("Low sun", cinematic.light_direction(sun_to), 3.6, 0.03)
        key.data.color = (1.0, 0.82, 0.62)
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.exposure = -0.55
    else:
        sun("Sun", (0.45, -0.55, -0.7), 5.0, 0.2)
        sun("Fill", (0.2, 0.7, -0.6), 2.4, 0.6)

    # second, passing truck on the highway (closing shot only)
    mats_orange = dict(mats, cab=material("Cab orange", (1.0, 0.36, 0.04), metal=0.2, rough=0.35))
    other, other_wheels = build_truck(mats_orange)

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
        return truck.matrix_world @ Vector(local)

    def visibility(point, tolerance=0.4, min_px=40.0):
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
        top = max(seen, key=lambda v: (v["visible"], v["px_per_30cm"])) if seen else {
            "in_frame": False, "clear": False, "px_per_30cm": 0.0, "visible": False}
        return {**top, "visible": count >= need, "visible_points": count, "needed": need}

    def pose(root, wheel_nodes, y, sink_m, spin, pitch):
        root.location = (0.0, y, -sink_m)
        root.rotation_euler = (pitch, 0, 0)
        for w in wheel_nodes:
            w.rotation_euler = (-spin, 0, 0)

    frames = range(args.start, args.end + 1, max(1, args.step))
    for frame in frames:
        shot = shot_for(frame)
        sid = shot["id"]
        t = (frame - shot["start"]) / max(1, shot["end"] - shot["start"])
        s_a, s_b = SIM_RANGE[sid]
        loop_back = False
        if sid == "ramp_beside_road":
            local_s = (frame - shot["start"]) / fps
            total_s = (shot["end"] - shot["start"]) / fps
            loop_back = local_s >= total_s - 2.0
            u = min(1.0, max(0.0, (local_s - (total_s - 2.0)) / 2.0))
            # the last frame sits one hook-frame (one frame step of the opening shot) before the first frame
            first_step = (SIM_RANGE["gravel_hook"][1] - SIM_RANGE["gravel_hook"][0]) / (shots[0]["end"] - shots[0]["start"])
            sim_t = lerp(-1.5, SIM_RANGE["gravel_hook"][0] - first_step, u) if loop_back else -1.5
        else:
            sim_t = lerp(s_a, s_b, t)
        x, v, a = truck_nose(states, sim_t)
        distance = max(x, 0.0)
        sink_m = motion.sink(distance)
        pitch = -math.radians(1.6) * min(1.0, a / (motion.GRAVEL_C * motion.G)) if x > 0 else 0.0
        if sid == "bed_cutaway":
            truck.hide_render = truck.hide_viewport = True
            for ob in truck.children_recursive:
                ob.hide_render = ob.hide_viewport = True
        else:
            for ob in (truck, *truck.children_recursive):
                ob.hide_render = ob.hide_viewport = False
            pose(truck, wheels, x, sink_m, x / motion.WHEEL_R, pitch)
        # second truck (closing shot, on the highway)
        ty = lerp(-60.0, 120.0, t)       # the passing highway truck's position (only used in the closing shot)
        show_other = (sid == "ramp_beside_road" and not loop_back) or sid == "stop_distance"
        for ob in (other, *other.children_recursive):
            ob.hide_render = ob.hide_viewport = not show_other
        if sid == "stop_distance":
            # the same truck coasting on pavement at constant speed (illustration, real-time): it keeps going
            ty = -45.0 + motion.SPEED0 * ((frame - shot["start"]) / fps)
        if show_other:
            other.location = (HIGHWAY_X + 2.0, ty, 0.0)
            other.rotation_euler = (0, 0, 0)
            for w in other_wheels:
                w.rotation_euler = (-ty / motion.WHEEL_R, 0, 0)

        want_row = int(max(0, min(BED_Y1 - WINDOW_ROWS, (x if sid != "stop_distance" else stop_x) - 28.0)))
        if want_row != window_state["row"] and sid != "bed_cutaway":
            pos_w, rad_w = window_stones(want_row)
            static_mesh.vertices.foreach_set("co", [c for p in pos_w for c in p])
            static_mesh.attributes["grain_radius"].data.foreach_set("value", rad_w)
            static_mesh.update()
            window_state["row"] = want_row
        # flying stones: positions at sim time (stones only exist for sim_t >= 0)
        grain_positions = []
        if sid in ("gravel_hook", "tyres_sink", "drag_numbers", "stop_distance") and sim_t > 0:
            for g in gravel:
                p = motion.grain_position(g, sim_t)
                grain_positions.append(p if p is not None else (0.0, 0.0, -5.0))
        else:
            grain_positions = [(0.0, 0.0, -5.0)] * len(gravel)
        dust_positions = []
        if sid in ("gravel_hook", "tyres_sink", "drag_numbers", "stop_distance") and sim_t > 0:
            for d in dust:
                p = motion.grain_position(d, sim_t)
                dust_positions.append(p if p is not None else (0.0, 0.0, -5.0))
        else:
            dust_positions = [(0.0, 0.0, -5.0)] * len(dust)
        dust_mesh.vertices.foreach_set("co", [c for p in dust_positions for c in p])
        dust_mesh.update()
        dust_ob.hide_render = False
        flat = [c for p in grain_positions for c in p]
        grains_mesh.vertices.foreach_set("co", flat)
        grains_mesh.update()
        grains_ob.hide_render = False
        grains_ob.hide_viewport = True
        static_ob.hide_render = sid == "bed_cutaway"
        for ob in (*cut_objs, cut_label):
            ob.hide_render = ob.hide_viewport = sid != "bed_cutaway"
        face_ob.hide_viewport = True
        cut_stones_ob.hide_viewport = True
        cut_w = motion.cut_wheel_state(t)
        if sid == "bed_cutaway":
            cut_spin.location = (cut_w["x"], CUT_YC, cut_w["z"])
            cut_spin.rotation_euler = (0, -cut_w["spin"], 0)
            local_cut = (frame - shot["start"]) / fps
            cut_stones_mesh.vertices.foreach_set("co", [c for g in cut_grains for c in (
                motion.grain_position(g, local_cut) or (0.0, 0.0, -5.0))])
            cut_stones_mesh.update()
        for ob in label_objs:
            ob.hide_render = ob.hide_viewport = sid != "stop_distance"

        # ----- cameras ------------------------------------------------
        cc.AIM.clear()

        def set_cam(loc, tgt, lens=None):
            if lens:
                cam.data.lens = lens
            base.set_camera(cam, loc, tgt)
            cc.AIM["target"] = Vector(tgt)

        nose_y = x

        def seg(*edges):
            return sum(1 for e in edges if t >= e)

        def hook_camera(ny):
            """The opening view: a low camera beside the bed entrance whose aim rides the near
            front tyre and then drifts back along the truck. The closing shot returns to it."""
            follow = min(1.0, max(0.0, (ny - 5.0) / 10.0))
            set_cam((4.1, max(5.0, ny - 8.0), 1.0), (0.6, lerp(ny - 1.4, ny - 7.0, follow), 0.9), 24)

        if sid == "gravel_hook":
            k = seg(0.42, 0.72)
            if k == 0:
                hook_camera(nose_y)
            elif k == 1:      # a dolly ahead of the truck, looking back at its nose and tyres
                set_cam((-3.2, nose_y + 11.0, 0.7), (0.3, nose_y - 3.0, 1.3), 28)
            else:             # side-on to the rear wheels, stones and dust thrown toward the lens
                set_cam((4.1, nose_y - 9.0, 1.0), (1.05, nose_y - 9.0, 0.6), 28)
        elif sid == "tyres_sink":
            k = seg(0.40, 0.72)
            if k == 0:
                set_cam((3.4, nose_y - 6.9 + lerp(1.4, -1.0, t), 0.8), (1.05, nose_y - 6.9, 0.45), 30)
            elif k == 1:      # low, ahead of the front tyre
                set_cam((1.9, nose_y + 3.6, 0.45), (1.05, nose_y - 1.4, 0.45), 30)
            else:             # raised over the rear tandem
                set_cam((3.3, nose_y - 11.0, 3.6), (1.0, nose_y - 12.2, 0.2), 30)
        elif sid == "bed_cutaway":
            ang = math.radians(lerp(-35.0, 30.0, t))
            r = lerp(4.6, 3.2, t)
            set_cam((math.sin(ang) * r, CUT_Y + 0.8 - math.cos(ang) * r, lerp(1.7, 1.0, t)), (0.0, CUT_Y + 0.3, 0.35), 32)
        elif sid == "drag_numbers":
            k = seg(0.36, 0.70)
            if k == 0:
                set_cam((3.1, nose_y - 15.0 + lerp(0.0, 3.0, t), 3.0), (0.0, nose_y - 4.0, 0.9), 32)
            elif k == 1:
                set_cam((-3.4, nose_y + 10.0, 0.9), (0.0, nose_y - 2.0, 1.3), 26)
            else:
                set_cam((3.8, nose_y - 8.0, 5.5), (0.5, nose_y - 8.0, 0.5), 30)
        elif sid == "stop_distance":
            k = seg(0.30, 0.78)
            if k == 0:
                set_cam((0.0, stop_x - 12.0, 52.0), (0.0, stop_x - 11.99, 0.0), 32)
            elif k == 1:
                set_cam((0.0, 72.0, lerp(95.0, 108.0, t)), (0.0, 72.01, 0.0), 32)
            else:
                set_cam((9.0, stop_x - 24.0, 3.5), (0.0, stop_x - 8.0, 0.8), 28)
        elif sid == "ramp_beside_road":
            local = (frame - shot["start"]) / fps
            total = (shot["end"] - shot["start"]) / fps
            if loop_back:
                hook_camera(nose_y)
            elif local < 2.0:
                set_cam((-28.0, lerp(-32.0, -22.0, local / 2.0), 6.0), (-6.0, 8.0, 1.0), 28)
            else:
                u = (local - 2.0) / max(0.1, total - 4.0)
                set_cam((lerp(-13.0, -11.0, u), lerp(-14.0, -8.0, u), lerp(15.0, 19.0, u)), (-5.0, lerp(24.0, 34.0, u), 0.0), 30)
        if look == cinematic.LOOK_CINEMATIC and "target" in cc.AIM:
            cinematic.apply_dof(cam, (cc.AIM["target"] - cam.location).length, fstop=2.4 if sid != "stop_distance" else 11.0)

        hud_on = sid in ("gravel_hook", "tyres_sink", "drag_numbers", "stop_distance")
        warn_on = sid == "gravel_hook" and (frame - shot["start"]) / fps <= 2.4
        hud_objects = ((hud, hud2, hud_plate) + ((hud3,) if sid == "drag_numbers" else ())
                       + ((hud4, hud4_plate) if warn_on else ()))
        for ob in (hud, hud2, hud_plate, hud3, hud4, hud4_plate):
            ob.hide_render = (ob not in hud_objects) or (not hud_on) or look == cinematic.LOOK_CINEMATIC
            ob.hide_viewport = True
        if hud_on:
            hud_curve.body = f"SPEED {max(v, 0.0) * 3.6:.0f} km/h"
            span = HUD_DEPTH * cam.data.sensor_width / cam.data.lens
            k = 0.60 * span / 7.4
            hud.scale = (k, k, k)
            y_off = span * (530.0 / 1080.0)
            hud.location = (0.0, y_off + 0.012 * span - 0.45 * k, -HUD_DEPTH)
            hud2.scale = (0.30 * k, 0.30 * k, 0.30 * k)
            hud2.location = (0.0, y_off - 0.058 * span, -HUD_DEPTH)
            hud_plate.scale = (0.78 * span, 0.215 * span, 1.0)
            hud_plate.location = (0.0, y_off - 0.012 * span, -HUD_DEPTH - 0.0005)
            hud3.scale = (0.30 * k, 0.30 * k, 0.30 * k)
            hud3.location = (0.0, y_off - 0.100 * span, -HUD_DEPTH)
            pulse = 1.0 + 0.07 * math.sin(frame * 0.9)
            hud4.scale = (0.62 * k * pulse, 0.62 * k * pulse, 0.62 * k * pulse)
            hud4.location = (0.0, y_off - 0.205 * span - 0.2 * k, -HUD_DEPTH)
            hud4_plate.scale = (0.56 * span * pulse, 0.12 * span * pulse, 1.0)
            hud4_plate.location = (0.0, y_off - 0.175 * span, -HUD_DEPTH - 0.004)   # well behind the text: coplanar faces z-fight
            if sid == "drag_numbers":
                hud_plate.scale = (0.9 * span, 0.28 * span, 1.0)
                hud_plate.location = (0.0, y_off - 0.040 * span, -HUD_DEPTH - 0.0005)
        bpy.context.view_layer.update()
        scene.frame_set(frame)
        bpy.context.view_layer.update()

        # ----- telemetry ----------------------------------------------
        events = {}
        in_bed = x > 0.0
        airborne_n = motion.airborne(gravel, sim_t) if sim_t > 0 and sid != "bed_cutaway" else 0
        airborne_pts = []
        if airborne_n:
            for g in gravel:
                tau = sim_t - g["t0"]
                if tau >= 0 and g["p0"][2] + g["v0"][2] * tau - 0.5 * motion.G * tau * tau > g["r"] + 0.02:
                    airborne_pts.append(motion.grain_position(g, sim_t))
        # check the stones nearest to where the camera is looking, not an arbitrary sample of all of them
        aim = cc.AIM.get("target")
        if aim is not None and airborne_pts:
            airborne_pts = sorted(airborne_pts, key=lambda q: (Vector(q) - aim).length)
            step_pts = airborne_pts[:8]
        else:
            step_pts = airborne_pts[::max(1, len(airborne_pts) // 8)][:8]
        if sid != "bed_cutaway":
            events["gravel_spray"] = (airborne_n >= 12, step_pts, 4, 8.0)
            events["gravel_cloud"] = (airborne_n >= 120, step_pts, 4, 8.0)
            wheel_pts = [world((wx, ay, 0.45)) for ay in motion.AXLES_Y for wx in motion.WHEEL_X]
            body_pts = [world((sx * 1.28, yy, 2.4)) for sx in (-1, 1) for yy in (-3.0, -6.0, -9.0, -12.0)]
            events["tyres_digging"] = (in_bed and sink_m > 0.10 and sid != "ramp_beside_road", wheel_pts, 2, 15.0)
            events["truck_decelerating"] = (in_bed and a > 1.5 and v > 1.0 and sid != "ramp_beside_road",
                                            wheel_pts + body_pts, 2, 15.0)
            if hud_on:
                events["speed_readout_visible"] = (True, [], 0, 0.0)
            if sid == "drag_numbers":
                events["drag_label_visible"] = (True, [], 0, 0.0)
            if sid == "stop_distance":
                events["paved_truck_moving_visible"] = (True, [other.matrix_world @ Vector(q) for q in
                                                               ((0, -0.2, 1.6), (0, -7.0, 4.0), (0, -12.0, 2.5))], 1, 1.0)   # a 14 m truck seen from above: 30 cm is ~3 px
                events["truck_stopped"] = (v <= motion.STOPPED_SPEED, [world((0, -0.2, 1.6)), world((0, -7.0, 4.0)), world((0, -12.0, 2.5))], 1, 3.0)
                events["stop_bars_visible"] = (True, [(2.6, stop_x, 0.1), (2.6, stop_x - 20.0, 0.1), (2.6, stop_x - 40.0, 0.1),
                                                  (-2.6, stop_x - 20.0, 0.1), (-2.6, stop_x - 40.0, 0.1)], 3, 1.5)
        else:
            events["wheel_rolling_visible"] = (True, [(cut_w["x"], CUT_YC, motion.CUT_SLAB_D + motion.WHEEL_R),
                                                      (cut_w["x"], CUT_YC - 0.17, motion.CUT_SLAB_D + motion.WHEEL_R + 0.3)], 1, 25.0)
            events["bed_cutaway_visible"] = (True, [(0.0, CUT_Y, SLAB_D * 0.5), (0.9, CUT_Y, SLAB_D * 0.3), (-0.9, CUT_Y, SLAB_D * 0.7),
                                                    (0.3, CUT_Y + 0.8, SLAB_D + 0.4)], 3, 25.0)
        if sid == "ramp_beside_road":
            events["ramp_beside_road_visible"] = (not loop_back, [(0.0, 5.0, 0.05), (0.0, 40.0, 0.05), (HIGHWAY_X, 20.0, 0.05),
                                                                    (HIGHWAY_X + 2.0, ty, 1.5)], 3, 2.0)
            events["truck_arriving_again"] = (loop_back and x < -2.0, [world((0, -0.2, 1.6)), world((0, -7.0, 4.0))], 1, 3.0)
        record = {"frame": frame, "shot_id": sid, "sim_t": round(sim_t, 4), "speed_mps": round(v, 3),
                  "nose_m": round(x, 3), "events": {}}
        for name, spec in events.items():
            active, points = spec[0], spec[1]
            need = spec[2] if len(spec) > 2 else 1
            min_px = spec[3] if len(spec) > 3 else 40.0
            if active and need == 0:
                seen = {"visible": True}
            else:
                seen = best(points, need, min_px) if active else {"visible": False}
            record["events"][name] = {"active": bool(active), **seen}
        telemetry.append(record)
        if args.telemetry_only:
            continue

        frame_path = out / f"frame_{frame:04d}.png"
        scene.render.filepath = str(frame_path)
        t0 = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        if look == cinematic.LOOK_CINEMATIC and hud_on:
            cc.composite_hud_pass(scene, cam, hud_objects, frame_path, out)
        elapsed = round(time.perf_counter() - t0, 3)
        sha = hashlib.sha256(frame_path.read_bytes()).hexdigest()
        checksums.append({"frame": frame, "shot_id": sid, "sha256": sha, "render_seconds": elapsed})
        render_seconds.append(elapsed)
        print(f"RAMP_NATIVE_FRAME {frame}/{manifest['total_frames']}", flush=True)

    if args.telemetry_only:
        (out / "ramp-telemetry.json").write_text(json.dumps({"motion_summary": summary, "telemetry": telemetry}, indent=1))
        print("RAMP_TELEMETRY_DONE " + json.dumps({"frames": len(telemetry)}), flush=True)
        return

    if len({c["sha256"] for c in checksums}) != len(checksums):
        seen_sha, pairs = {}, []
        for c in checksums:
            if c["sha256"] in seen_sha:
                pairs.append([seen_sha[c["sha256"]], c["frame"]])
            else:
                seen_sha[c["sha256"]] = c["frame"]
        print("RAMP_DUPLICATE_SOURCE_FRAMES " + json.dumps(pairs), flush=True)
        if not args.preview:
            raise ValueError("duplicate original Blender frames are forbidden")

    result = {
        "episode_id": manifest["episode_id"],
        "renderer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "motion_source_sha256": hashlib.sha256(Path(motion.__file__).read_bytes()).hexdigest(),
        "motion_summary": summary, "telemetry": telemetry,
        "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "renderer": "CYCLES", "blender_version": bpy.app.version_string,
        "preview_only": args.preview, "frames": len(checksums),
        "first_frame": checksums[0]["frame"], "last_frame": checksums[-1]["frame"],
        "frame_numbers": [c["frame"] for c in checksums], "fps": manifest["fps"],
        "resolution": [scene.render.resolution_x, scene.render.resolution_y],
        "cycles_samples": scene.cycles.samples, "render_seconds": render_seconds,
        "checksums": checksums, "physically_calibrated": False, "upload_ready": False,
    }
    if not args.preview and (result["resolution"] != manifest["resolution"]
                             or result["cycles_samples"] != manifest["cycles_samples"]):
        raise ValueError("production frame quality cannot differ from approved manifest")
    (out / "ramp-proof.json").write_text(json.dumps(result, indent=2))
    print("RAMP_SHARD_DONE " + json.dumps({"frame_count": len(checksums), "first": checksums[0]["frame"],
                                           "last": checksums[-1]["frame"], "preview_only": args.preview,
                                           "render_seconds_total": round(sum(render_seconds), 3)}), flush=True)


if __name__ == "__main__":
    main()
