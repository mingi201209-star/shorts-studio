"""Jersey barrier episode renderer.

Topic: this project's approved "guardrail-deflection" topic
(shorts_studio/factory/series.py, ROAD_SAFETY_FIRST_SEVEN), shown through
the concrete safety-shape barrier.

What the film claims, and only this: in a shallow-angle hit the barrier-side
tyre reaches the sloped lower face before the body reaches the wall; the
tyre rides up, the suspension compresses, the slope's push steers the car
back, and the body stays clear. Against a flat wall the same hit lands on
the body. An earlier cut said a flat wall makes the car "stop dead" and
animated it that way; that is not what a shallow hit does and it is gone.

Every car pose comes from jersey_barrier_motion.simulate() (single-track
model, four quarter-car suspensions, slope force = tyre load x tan 55 deg).
Wheels are separate objects in the pinned CC0 sedan, so each wheel spins,
steers and travels in its arch independently of the body. Nothing is
hand-keyed except the cameras.

Each rendered frame also records TELEMETRY: which physical conditions are
true in the simulated state it was drawn from, and whether the point where
that condition happens is inside the visible picture, unoccluded and large
enough to read. assemble_jersey_barrier.py checks the narration against that
record sentence by sentence.

Not claimed: this is not a validated crash simulation (no tyre or body
deformation, linear tyres, generic parameters). "physically_calibrated"
stays False in the proof.

No frame holds, interpolation, or output upscaling. No upload or TTS.
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
from benchmarks.road_safety import jersey_barrier_motion as motion  # noqa: E402

PINNED_SCENE_SHA256 = "a82e05825f907cc99678ab12855527552e34323b31ae801625af4a0f563ed877"


def arguments():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--start", type=int, required=True)
    p.add_argument("--end", type=int, required=True)
    p.add_argument("--preview", action="store_true")
    p.add_argument("--telemetry-only", action="store_true",
                   help="pose every frame and record telemetry without rendering")
    p.add_argument("--step", type=int, default=1, help="render every Nth frame (local look-dev only)")
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return p.parse_args(argv)


def stable_source(path):
    if not path.is_file():
        raise FileNotFoundError(path)
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    if h != PINNED_SCENE_SHA256:
        raise ValueError(f"pinned car scene SHA mismatch: {h}")
    return h


def material(name, color, metal=0.0, rough=0.55, emission=0.0):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    s = m.node_tree.nodes.get("Principled BSDF")
    s.inputs["Base Color"].default_value = (*color, 1)
    s.inputs["Metallic"].default_value = metal
    s.inputs["Roughness"].default_value = rough
    if emission:
        s.inputs["Emission Color"].default_value = (*color, 1)
        s.inputs["Emission Strength"].default_value = emission
    return m


def cube(name, center, dimensions, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    ob = bpy.context.object
    ob.name = name
    ob.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    ob.data.materials.append(mat)
    return ob


def asphalt_grain(mat):
    """Same grain technique as render_road_paint.py's asphalt_grain(): world-
    space noise driving albedo variation and a bump normal, so a flat road
    plane still catches real grazing light instead of reading as an abstract
    plane."""
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    shader = nodes.get("Principled BSDF")
    geometry = nodes.new("ShaderNodeNewGeometry")
    coarse = nodes.new("ShaderNodeTexNoise")
    coarse.inputs["Scale"].default_value = 18
    coarse.inputs["Detail"].default_value = 3
    fine = nodes.new("ShaderNodeTexNoise")
    fine.inputs["Scale"].default_value = 140
    fine.inputs["Detail"].default_value = 2
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.25
    ramp.color_ramp.elements[0].color = (0.05, 0.051, 0.054, 1)
    ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.elements[1].color = (0.072, 0.073, 0.077, 1)
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.35
    bump.inputs["Distance"].default_value = 0.004
    links.new(geometry.outputs["Position"], coarse.inputs["Vector"])
    links.new(geometry.outputs["Position"], fine.inputs["Vector"])
    links.new(coarse.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], shader.inputs["Base Color"])
    links.new(fine.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], shader.inputs["Normal"])


def lerp(a, b, t):
    return a + (b - a) * t


def extruded_profile(name, profile_xz, y0, y1, mat):
    """Extrudes a closed (x, z) polygon along Y, with end caps at both
    ends -- the y0 cap is what barrier_cross_section's orbiting camera
    actually reads as the cutaway slice."""
    n = len(profile_xz)
    verts = [(x, y0, z) for x, z in profile_xz] + [(x, y1, z) for x, z in profile_xz]
    faces = []
    for i in range(n):
        a, b = i, (i + 1) % n
        c, d = n + (i + 1) % n, n + i
        faces.append((a, b, c, d))
    faces.append(tuple(range(n)))
    faces.append(tuple(reversed(range(n, 2 * n))))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    mesh.materials.append(mat)
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(ob)
    return ob



BARRIER_X = 2.4
FACE_X = BARRIER_X - motion.BASE_HALF_WIDTH   # the toe: sim x = 0
BARRIER_Y0, BARRIER_Y1 = -40.0, 70.0
PICTURE_BOTTOM_ROW = 1400                     # caption band starts here (of 1920)


def set_camera(cam, location, target):
    """No per-frame jitter: an earlier version added a few millimetres of
    sinusoidal offset to work around duplicate frames; the preflight showed
    those came from a camera inside the barrier, and on close shots the
    offset read as a shaking picture."""
    loc = Vector(location)
    cam.location = loc
    cam.rotation_euler = (Vector(target) - loc).to_track_quat("-Z", "Y").to_euler()


def set_visible(obj, visible):
    """hide_render does not cascade from an Empty to its children, so every
    object is set directly. hide_viewport is set too because the telemetry
    ray cast uses viewport visibility, not render visibility."""
    for ob in (obj, *obj.children_recursive):
        ob.hide_render = not visible
        ob.hide_viewport = not visible


def load_source_car(source_path):
    """Opens the pinned CC0 sedan as the base scene, prunes everything else,
    and re-rigs it: a root (position and heading), a body node (heave, roll,
    pitch) and four wheel nodes (suspension travel, spin, steer). Geometry
    the motion model needs is MEASURED from the mesh here."""
    stable_source(source_path)
    bpy.ops.wm.open_mainfile(filepath=str(source_path))
    car = bpy.data.objects.get("CC0 detailed sedan animated as a rigid car")
    if car is None:
        raise ValueError("source car hierarchy unavailable")
    keep = {car, *car.children_recursive}
    for ob in list(bpy.data.objects):
        if ob not in keep:
            bpy.data.objects.remove(ob, do_unlink=True)
    meshes = [o for o in car.children_recursive if o.type == "MESH"]
    if len(meshes) < 65:
        raise ValueError("incomplete vehicle part set")
    car.animation_data_clear()
    for ob in car.children_recursive:
        if ob.animation_data:
            ob.animation_data_clear()
    # Native orientation has the length along Y with the nose at -Y; half a
    # turn points the nose at +Y, the travel direction.
    car.rotation_euler = (0, 0, math.pi)
    car.scale = (0.85, 0.85, 0.85)
    car.location = (0, 0, 0)
    bpy.context.view_layer.update()

    def bounds(ob):
        pts = [ob.matrix_world @ Vector(v) for v in ob.bound_box]
        lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        return lo, hi

    wheel_parts = [o for o in meshes if o.name.startswith(("Front_", "Rear_"))]
    tyres = [o for o in wheel_parts if "tire" in o.name]
    if len(tyres) != 4:
        raise ValueError(f"expected 4 tyres, found {len(tyres)}")
    centres = {}
    for tyre in tyres:
        lo, hi = bounds(tyre)
        centres[tyre.name] = (lo + hi) / 2
    mid_x = sum(c.x for c in centres.values()) / 4
    mid_y = sum(c.y for c in centres.values()) / 4
    ground = min(bounds(t)[0].z for t in tyres)
    front_y = max(c.y for c in centres.values())
    rear_y = min(c.y for c in centres.values())
    wheelbase = front_y - rear_y
    # Reference point: 53% of the wheelbase ahead of the rear axle, a
    # typical front-engined centre of mass.
    ref = Vector((mid_x, rear_y + 0.53 * wheelbase, ground))
    car.location = -ref
    bpy.context.view_layer.update()

    root = bpy.data.objects.new("Demo car root", None)
    body = bpy.data.objects.new("Demo car body (heave/roll/pitch)", None)
    for node in (root, body):
        bpy.context.collection.objects.link(node)
    body.parent = root
    car.parent = body
    car.matrix_parent_inverse.identity()
    bpy.context.view_layer.update()

    wheels = {}
    tyre_outer = 0.0
    radius = 0.0
    for tyre in tyres:
        lo, hi = bounds(tyre)
        centre = (lo + hi) / 2
        key = ("front" if centre.y > 0 else "rear") + "_" + ("right" if centre.x > 0 else "left")
        node = bpy.data.objects.new(f"Wheel node {key}", None)
        bpy.context.collection.objects.link(node)
        node.parent = root
        node.location = centre
        node.rotation_mode = "XYZ"
        wheels[key] = {"node": node, "base": centre.copy()}
        tyre_outer = max(tyre_outer, abs(lo.x), abs(hi.x))
        radius = max(radius, (hi.z - lo.z) / 2)
    bpy.context.view_layer.update()
    for part in wheel_parts:
        lo, hi = bounds(part)
        centre = (lo + hi) / 2
        key = min(wheels, key=lambda k: (wheels[k]["base"] - centre).length)
        world = part.matrix_world.copy()
        part.parent = wheels[key]["node"]
        part.matrix_world = world
    bpy.context.view_layer.update()
    if set(wheels) != set(motion.WHEELS):
        raise ValueError(f"wheel nodes incomplete: {sorted(wheels)}")

    body_meshes = [o for o in meshes if o not in wheel_parts and not o.name.startswith("Mirror")]
    los, his = zip(*(bounds(o) for o in body_meshes))
    geometry = {
        "wheelbase": round(wheelbase, 3),
        "front_axle": round(front_y - ref.y, 3),
        "rear_axle": round(ref.y - rear_y, 3),
        "tyre_outer": round(tyre_outer, 3),
        "tyre_radius": round(radius, 3),
        "body_half_width": round(max(max(h.x for h in his), -min(l.x for l in los)), 3),
        "nose": round(max(h.y for h in his), 3),
        "tail": round(-min(l.y for l in los), 3),
        "roof": round(max(h.z for h in his), 3),
    }
    print("CAR_GEOMETRY " + json.dumps(geometry), flush=True)
    return root, body, wheels, geometry


def build_car_model(geometry):
    return motion.Car(
        front_axle=geometry["front_axle"], rear_axle=geometry["rear_axle"],
        tyre_outer=geometry["tyre_outer"], body_half_width=geometry["body_half_width"],
        nose=geometry["nose"], tail=geometry["tail"])


# One entry per shot: which wall, how much the film slows the simulation,
# where in the simulation the shot starts, and which simulated y is drawn at
# world y = 0. Slow motion is a property of the shot, stated here, not a
# change to the physics.
SHOT_PLAN = {
    "tyre_only_hook": {"wall": "jersey", "time_scale": 0.30, "sim_start": 0.20},
    "flat_wall_strike": {"wall": "flat", "time_scale": 0.13, "sim_start": 0.20},
    "barrier_cross_section": {"wall": "jersey", "time_scale": 0.0, "sim_start": 0.0},
    "wheel_climb_macro": {"wall": "jersey", "time_scale": 0.13, "sim_start": 0.31},
    "sloped_barrier_redirect": {"wall": "jersey", "time_scale": 0.42, "sim_start": 0.10},
    "barrier_closing": {"wall": "jersey", "time_scale": 0.0, "sim_start": 0.0},
}
APPROACH_DEG = 4.0
Y_REFERENCE = 4.3   # simulated y of first contact, drawn at world y = 0


def main():
    args = arguments()
    manifest = json.loads(args.manifest.read_text(encoding="utf8"))
    shots = manifest["shots"]
    if [s["id"] for s in shots] != list(SHOT_PLAN):
        raise ValueError("manifest shots do not match SHOT_PLAN")

    # open_mainfile replaces bpy.data wholesale, so the car loads first.
    car_root, car_body, wheels, geometry = load_source_car(args.source)
    car_model = build_car_model(geometry)
    scenarios = {wall: motion.Scenario(wall=wall, approach_deg=APPROACH_DEG) for wall in ("jersey", "flat")}
    runs = {wall: motion.simulate(sc, car_model) for wall, sc in scenarios.items()}
    summaries = {wall: motion.summary(states) for wall, states in runs.items()}
    print("BARRIER_MOTION_SUMMARY " + json.dumps(summaries), flush=True)
    # The film says the body stays clear of the Jersey barrier and that the
    # flat wall is met by the body. Refuse to draw anything else.
    if summaries["jersey"]["min_body_gap_m"] <= 0.02 or summaries["jersey"]["first_tyre_contact_s"] is None:
        raise ValueError("simulation no longer supports 'only the tyre touches'")
    if summaries["flat"]["first_body_contact_s"] is None:
        raise ValueError("simulation no longer supports 'the body meets the flat wall'")
    # Stretches of wall the body actually pressed on (contact force above
    # zero), as (first y, last y, sim time it started). Paint is left only
    # there, not along the whole pass.
    episodes = []
    for st in runs["flat"]:
        if st.body_force > 0.0:
            # The rear corner makes the second contact; take whichever end
            # of the car is nearer the wall.
            along = car_model.nose if st.heading > 0 else -car_model.tail
            y_here = st.y + along
            if episodes and st.t - episodes[-1][3] < 0.02:
                episodes[-1][1] = y_here
                episodes[-1][3] = st.t
            else:
                episodes.append([y_here, y_here, st.t, st.t])

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 7 if args.preview else manifest["cycles_samples"]
    scene.cycles.use_denoising = True
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 4
    width, height = (360, 640) if args.preview else tuple(manifest["resolution"])
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.view_settings.view_transform = "AgX"
    scene.world.color = (0.16, 0.19, 0.28)
    if scene.world.use_nodes:
        bg = scene.world.node_tree.nodes.get("Background")
        if bg is not None:
            bg.inputs["Color"].default_value = (0.16, 0.19, 0.28, 1)
            bg.inputs["Strength"].default_value = 1.0

    asphalt_mat = material("Dusk asphalt", (0.055, 0.056, 0.06), rough=0.9)
    asphalt_grain(asphalt_mat)
    flat_wall_mat = material("Flat wall concrete", (0.60, 0.58, 0.53), rough=0.8)
    barrier_mat = material("Jersey barrier concrete", (0.60, 0.58, 0.53), rough=0.8)
    post_mat = material("Reflector post", (0.9, 0.78, 0.2), emission=1.2)
    stripe_mat = material("Road lane stripe", (0.78, 0.76, 0.7), rough=0.6)
    slope_mat = material("Lower slope highlight", (1.0, 0.42, 0.05), rough=0.5, emission=2.2)
    scrape_mat = material("Paint scrape on concrete", (0.30, 0.05, 0.04), rough=0.85)

    cube("Road surface", (0, (BARRIER_Y0 + BARRIER_Y1) / 2, -0.05),
         (12.0, BARRIER_Y1 - BARRIER_Y0 + 30.0, 0.10), asphalt_mat)
    flat_wall = extruded_profile("Flat wall", motion.flat_profile(), BARRIER_Y0, BARRIER_Y1, flat_wall_mat)
    flat_wall.location = (BARRIER_X, 0, 0)
    jersey = extruded_profile("Jersey barrier", motion.jersey_profile(), BARRIER_Y0, BARRIER_Y1, barrier_mat)
    jersey.location = (BARRIER_X, 0, 0)
    jersey_parts = [jersey]     # everything shown/hidden with the full barrier
    # Reflector posts on the barrier top and lane stripes every few metres:
    # fixed references that make speed and direction readable.
    post_y = int(BARRIER_Y0) + 1
    while post_y < BARRIER_Y1:
        post = cube(f"Reflector post {post_y}", (BARRIER_X, post_y, motion.BARRIER_HEIGHT + 0.06),
                    (0.06, 0.06, 0.12), post_mat)
        jersey_parts.append(post)
        post_y += 3
    stripe_y = int(BARRIER_Y0)
    while stripe_y < BARRIER_Y1:
        cube(f"Lane stripe {stripe_y}", (FACE_X - 3.4, stripe_y, 0.001), (0.12, 2.0, 0.002), stripe_mat)
        stripe_y += 6
    # The lower sloped face, picked out in colour for the cross-section
    # shot: a thin slab lying on the last metres of the slope.
    run = motion.SLOPE_RUN
    rise = motion.SLOPE_TOP_HEIGHT - motion.REVEAL_HEIGHT
    slope_len = math.hypot(run, rise)
    slope_mark = cube("Lower slope highlight", (0, 0, 0), (slope_len, 6.0, 0.012), slope_mat)
    slope_mark.location = (FACE_X + run / 2 - 0.006, BARRIER_Y1 - 3.0 + 0.01,
                           motion.REVEAL_HEIGHT + rise / 2 + 0.004)
    slope_mark.rotation_euler = (0, -math.atan2(rise, run), 0)
    scrapes = [cube(f"Scrape mark {i}", (0, 0, 0), (0.01, 1.0, 0.10), scrape_mat) for i in range(len(episodes))]
    # Road grime and tyre scuffs darken the lower slope of real barriers;
    # here that same band is what lets the eye separate the sloped lower
    # face from the near-vertical upper face under flat light.
    scuff_mat = material("Scuffed lower slope", (0.27, 0.26, 0.24), rough=0.9)
    scuff = cube("Lower slope scuff band", (0, 0, 0), (slope_len, BARRIER_Y1 - BARRIER_Y0 - 0.02, 0.006), scuff_mat)
    scuff.location = (FACE_X + run / 2 - 0.003, (BARRIER_Y0 + BARRIER_Y1) / 2, motion.REVEAL_HEIGHT + rise / 2 + 0.002)
    scuff.rotation_euler = (0, -math.atan2(rise, run), 0)
    jersey_parts.append(scuff)
    # Ghost material for the wheel close-up: the body is drawn see-through
    # so the tyre on the slope and its travel inside the arch are visible
    # from the road side. Stated as a cutaway device in the manifest.
    ghost_mat = material("Ghosted body", (0.75, 0.16, 0.12), rough=0.5)
    ghost_mat.node_tree.nodes.get("Principled BSDF").inputs["Alpha"].default_value = 0.16
    scene.cycles.transparent_max_bounces = 24

    # Reuse the car's own body material, recoloured.
    body_paint = bpy.data.materials.get("blue")
    if body_paint is None:
        raise ValueError("missing original CC0 blue body material")
    body_paint.use_nodes = True
    paint_shader = body_paint.node_tree.nodes.get("Principled BSDF")
    if paint_shader is None:
        raise ValueError("source body material has no Principled BSDF")
    paint_shader.inputs["Base Color"].default_value = (0.72, 0.1, 0.08, 1)
    paint_shader.inputs["Metallic"].default_value = 0.3
    paint_shader.inputs["Roughness"].default_value = 0.35
    body_paint.diffuse_color = (0.72, 0.1, 0.08, 1)

    bpy.ops.object.camera_add(location=(0, -8, 2.0))
    cam = bpy.context.object
    scene.camera = cam
    cam.data.sensor_fit = "HORIZONTAL"
    cam.data.sensor_width = 36
    cam.data.lens = 32
    # The caption band covers rows 1400-1919, so the visible picture's
    # centre is row 700, not the render's row 960. Shift the view so the
    # camera's aim point lands in the middle of the visible picture.
    cam.data.shift_y = -260.0 / 1080.0

    bpy.ops.object.light_add(type="SUN")
    key = bpy.context.object
    key.name = "Low dusk sun"
    key.data.angle = 0.2
    # The light travels toward +X/-Y: onto the barrier's road-side face and
    # the front and left of the car.
    key.rotation_euler = (math.radians(55), 0, math.radians(-120))
    key.data.energy = 5.0
    # A soft fill from the road side so the wheel arch and the gap between
    # body and barrier are readable instead of a black hole.
    bpy.ops.object.light_add(type="SUN")
    fill = bpy.context.object
    fill.name = "Gap fill"
    fill.data.angle = 0.6
    fill.rotation_euler = (math.radians(75), 0, math.radians(-30))
    fill.data.energy = 2.2

    body_materials = {ob: [slot.material for slot in ob.material_slots]
                      for ob in car_body.children_recursive if ob.type == "MESH"}

    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    checksums = []
    render_seconds = []
    telemetry = []
    fps = manifest["fps"]
    radius = geometry["tyre_radius"]
    half_track = geometry["tyre_outer"]

    def shot_for(frame):
        for s in shots:
            if s["start"] <= frame <= s["end"]:
                return s
        raise ValueError(f"frame {frame} not covered by any shot")

    def pose_car(state):
        """Draw one simulated state: root carries position and heading, the
        body node carries heave/roll/pitch from the four sprung corners, and
        each wheel node carries its own travel, spin and steer."""
        car_root.location = (FACE_X + state.x, state.y - Y_REFERENCE, 0.0)
        car_root.rotation_euler = (0, 0, -state.heading)
        cz = state.corner_z
        right = (cz["front_right"] + cz["rear_right"]) / 2
        left = (cz["front_left"] + cz["rear_left"]) / 2
        front = (cz["front_right"] + cz["front_left"]) / 2
        rear = (cz["rear_right"] + cz["rear_left"]) / 2
        car_body.location = (0, 0, (right + left) / 2)
        car_body.rotation_euler = (math.atan2(front - rear, geometry["wheelbase"]),
                                   -math.atan2(right - left, 2 * half_track), 0)
        for name, wheel in wheels.items():
            node = wheel["node"]
            node.location = wheel["base"] + Vector((0, 0, state.wheel_z[name]))
            steer = -state.steer if name.startswith("front") else 0.0
            node.rotation_euler = (-state.distance / radius, 0, steer)

    def world(local):
        return car_root.matrix_world @ Vector(local)

    def visibility(point, tolerance=0.35):
        """Is this world point inside the visible picture (above the caption
        band), not hidden behind something, and how many output pixels does
        30 cm cover at its distance?"""
        point = Vector(point)
        ndc = world_to_camera_view(scene, cam, point)
        row = (1.0 - ndc.y) * 1920.0
        in_frame = 0.03 <= ndc.x <= 0.97 and 20.0 <= row <= PICTURE_BOTTOM_ROW - 20.0 and ndc.z > 0.1
        origin = cam.matrix_world.translation
        direction = (point - origin)
        distance = direction.length
        hit, location, *_ = scene.ray_cast(bpy.context.evaluated_depsgraph_get(), origin, direction.normalized())
        clear = (not hit) or (location - origin).length >= distance - tolerance
        px_per_30cm = 0.30 / max(0.01, ndc.z) * cam.data.lens / cam.data.sensor_width * 1080.0
        return {"in_frame": bool(in_frame), "clear": bool(clear), "px_per_30cm": round(px_per_30cm, 1),
                "visible": bool(in_frame and clear and px_per_30cm >= 45.0)}

    def best(points):
        seen = [visibility(p) for p in points]
        return max(seen, key=lambda v: (v["visible"], v["px_per_30cm"])) if seen else {"visible": False}

    frames = range(args.start, args.end + 1, max(1, args.step))
    for frame in frames:
        shot = shot_for(frame)
        plan = SHOT_PLAN[shot["id"]]
        t = (frame - shot["start"]) / max(1, shot["end"] - shot["start"])
        s = (frame - shot["start"]) / fps          # seconds into the shot
        wall = plan["wall"]
        scenario = scenarios[wall]
        sim_t = plan["sim_start"] + s * plan["time_scale"]
        state = motion.sample(runs[wall], sim_t, scenario.dt)

        set_visible(flat_wall, wall == "flat")
        for part in jersey_parts:
            set_visible(part, wall == "jersey")
        ghost = shot["id"] == "wheel_climb_macro" and s < 2.8
        for mesh, slots in body_materials.items():
            for index, original in enumerate(slots):
                mesh.material_slots[index].material = ghost_mat if ghost else original
        set_visible(car_root, True)
        set_visible(slope_mark, False)
        for mark in scrapes:
            set_visible(mark, False)
        key.data.energy = 5.0
        pose_car(state)
        bpy.context.view_layer.update()
        fr_wheel = world(wheels["front_right"]["base"])
        rr_wheel = world(wheels["rear_right"]["base"])
        centre = Vector(car_root.location)
        shot_events = {}

        if shot["id"] == "tyre_only_hook":
            # Setup A looks back along the toe of the barrier at the
            # barrier-side front tyre: the slope is edge-on, so the tyre
            # meeting it, rising, and the gap that stays open between body
            # and wall are all in one view. The camera travels with the car
            # along the road only; sideways drift, lift and yaw are the
            # car's own.
            if s < 2.4:
                cam_pos = (FACE_X - 0.40, fr_wheel.y + 2.5, 0.34)
                target = (FACE_X - 0.22, fr_wheel.y, 0.32)
            else:
                # Setup B, from behind on the same line: the rear tyre is
                # now on the slope and daylight shows between the body side
                # and the upper wall.
                cam_pos = (FACE_X - 0.50, rr_wheel.y - 2.6, 0.50)
                target = (FACE_X - 0.20, rr_wheel.y + 0.6, 0.38)
            set_camera(cam, cam_pos, target)

        elif shot["id"] == "flat_wall_strike":
            # Same car, same approach, same two viewpoints as the hook, on a
            # flat wall: nothing lifts, the front body corner strikes, the
            # car is turned, and the rear corner follows it in.
            for mark, (y0, y1, t0, _t1) in zip(scrapes, episodes):
                if sim_t >= t0:
                    along = car_model.nose if y1 >= y0 and t0 < 0.5 else -car_model.tail
                    reach = min(y1, state.y + along) if y1 >= y0 else y1
                    length = max(0.03, reach - y0)
                    mark.scale = (1.0, length, 1.0)
                    mark.location = (FACE_X - 0.004, y0 - Y_REFERENCE + length / 2, 0.44)
                    set_visible(mark, True)
            if s < 2.8:
                cam_pos = (FACE_X - 0.40, fr_wheel.y + 2.5, 0.34)
                target = (FACE_X - 0.22, fr_wheel.y, 0.32)
            else:
                cam_pos = (FACE_X - 0.50, rr_wheel.y - 2.6, 0.50)
                target = (FACE_X - 0.20, rr_wheel.y + 0.6, 0.38)
            set_camera(cam, cam_pos, target)

        elif shot["id"] == "barrier_cross_section":
            # The cut end of the barrier, no car: the profile itself. The
            # lower sloped face lights up as the narration names it.
            set_visible(car_root, False)
            # Two setups: a wide orbit that shows it is the same wall, then
            # close and nearly head-on, where the profile reads as a shape
            # and the lower slope lights up as the narration reaches it.
            lit = s >= 2.7
            set_visible(slope_mark, lit)
            if not lit:
                u = s / 2.7
                angle, dist, height = lerp(-0.95, -0.55, u), lerp(5.2, 3.4, u), lerp(1.7, 1.1, u)
            else:
                u = min(1.0, (s - 2.7) / 2.7)
                angle, dist, height = lerp(-0.22, -0.08, u), lerp(1.9, 1.5, u), 0.45
            cam_pos = (BARRIER_X + math.sin(angle) * dist, BARRIER_Y1 + math.cos(angle) * dist, height)
            set_camera(cam, cam_pos, (BARRIER_X, BARRIER_Y1, 0.4))
            slope_point = (FACE_X + run / 2, BARRIER_Y1, motion.REVEAL_HEIGHT + rise / 2)
            shot_events["slope_highlighted"] = (lit, [slope_point])

        elif shot["id"] == "wheel_climb_macro":
            if ghost:
                # Ghosted body, front three-quarter from the road side, while
                # the suspension is doing its work: the tyre rides onto the
                # slope and is pushed up into its arch before the body
                # follows.
                cam_pos = (FACE_X - 1.5, fr_wheel.y + 1.5, 0.5)
                target = (FACE_X - 0.15, fr_wheel.y, 0.36)
                for ob in body_materials:
                    ob.hide_viewport = True   # telemetry rays see through the ghost
            else:
                # Then solid again, close and low along the toe: the tyre
                # running along the slope with the body held off the wall.
                cam_pos = (FACE_X - 0.30, fr_wheel.y + 1.55, 0.20)
                target = (FACE_X - 0.10, fr_wheel.y, 0.22)
            set_camera(cam, cam_pos, target)

        elif shot["id"] == "sloped_barrier_redirect":
            if s < 3.0:
                # From above the barrier line: the barrier-side tyres on the
                # foot of the wall, then the car peeling away from it.
                cam_pos = (FACE_X + 0.6, centre.y - 3.5, 4.6)
                target = (FACE_X - 0.6, centre.y + 0.8, 0.2)
            else:
                cam_pos = (FACE_X - 2.2, centre.y + 6.0, 1.6)
                target = (FACE_X - 0.9, centre.y, 0.5)
            set_camera(cam, cam_pos, target)

        elif shot["id"] == "barrier_closing":
            # Steady cruise in lane beside the barrier; no contact.
            cruise = motion.sample(runs["jersey"], 0.0, scenario.dt)
            cruise = motion.State(
                t=0.0, x=-(scenario.lane_offset + half_track), y=Y_REFERENCE + lerp(2.0, 14.0, t),
                heading=0.0, speed=scenario.speed, yaw_rate=0.0, steer=0.0,
                wheel_z=dict(cruise.wheel_z), corner_z=dict(cruise.corner_z),
                compression=dict(cruise.compression), incursion={w: 0.0 for w in motion.WHEELS},
                tyre_force={w: 0.0 for w in motion.WHEELS}, body_gap=scenario.lane_offset,
                distance=lerp(2.0, 14.0, t))
            state = cruise
            pose_car(state)
            cam_pos = (BARRIER_X + 1.8, lerp(-6.0, 7.0, t), lerp(11.0, 4.0, t))
            set_camera(cam, cam_pos, (BARRIER_X, 5.0, 0.3))
            key.data.energy = 5.4
            shot_events["barrier_beside_road"] = (True, [(FACE_X, y, 0.4) for y in (-5.0, 0.0, 5.0, 10.0)])

        else:
            raise ValueError(f"unknown shot id {shot['id']!r}")

        scene.frame_set(frame)
        bpy.context.view_layer.update()

        # ---- telemetry: what is physically true in this frame, and can the
        # viewer see where it happens? -----------------------------------
        car_visible = not car_root.hide_render
        wheel_local = {name: wheels[name]["base"] for name in motion.WHEELS}

        def tyre_edge(name):
            base = wheel_local[name]
            return world((base.x + (half_track - abs(base.x)), base.y, state.wheel_z[name] + 0.02))

        def tyre_top(name):
            base = wheel_local[name]
            return world((base.x, base.y, base.z + radius + state.wheel_z[name]))

        body_side = [world((geometry["body_half_width"], y, 0.45))
                     for y in (geometry["nose"] - 0.25, 0.0, -geometry["tail"] + 0.25)]
        on_slope = [w for w in ("front_right", "rear_right") if state.incursion.get(w, 0.0) > 0.005]
        squeezed = [w for w in motion.WHEELS if state.compression[w] > 0.02]
        events = {}
        if car_visible and shot["id"] != "barrier_closing":
            events["tyre_on_slope"] = (bool(on_slope), [tyre_edge(w) for w in on_slope])
            events["tyre_only_contact"] = (bool(on_slope) and state.body_gap > 0.02,
                                           [tyre_edge(w) for w in on_slope])
            events["body_gap_open"] = (bool(on_slope) and state.body_gap > 0.02, body_side)
            events["front_tyre_climbing"] = (state.wheel_z["front_right"] > 0.03, [tyre_edge("front_right")])
            events["suspension_compressed"] = (bool(squeezed), [tyre_top(w) for w in squeezed])
            events["body_on_wall"] = (state.body_force > 500.0, body_side)
            events["body_lifted"] = (state.corner_z["front_right"] > 0.05,
                                     [world((geometry["body_half_width"] - 0.1, geometry["nose"] - 0.05, 0.6))])
            events["steered_away"] = (state.heading < math.radians(-0.4) and wall == "jersey",
                                      [world((0, 0, geometry["roof"])),
                                       world((0, geometry["nose"], 0.55)), world((0, -geometry["tail"], 0.6))])
        events.update(shot_events)
        record = {"frame": frame, "shot_id": shot["id"], "sim_t": round(sim_t, 4), "wall": wall,
                  "heading_deg": round(math.degrees(state.heading), 3),
                  "body_gap_m": round(state.body_gap, 4),
                  "front_right": {"lift_m": round(state.wheel_z["front_right"], 4),
                                  "compression_m": round(state.compression["front_right"], 4),
                                  "incursion_m": round(state.incursion.get("front_right", 0.0), 4)},
                  "events": {}}
        for name, (active, points) in events.items():
            seen = best(points) if active else {"visible": False}
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
        checksums.append({"frame": frame, "shot_id": shot["id"], "sha256": sha, "render_seconds": elapsed})
        render_seconds.append(elapsed)
        print(f"BARRIER_NATIVE_FRAME {frame}/{manifest['total_frames']}", flush=True)

    if args.telemetry_only:
        (out / "barrier-telemetry.json").write_text(json.dumps(
            {"geometry": geometry, "motion_summary": summaries, "telemetry": telemetry}, indent=1))
        print("BARRIER_TELEMETRY_DONE " + json.dumps({"frames": len(telemetry)}), flush=True)
        return

    if len({c["sha256"] for c in checksums}) != len(checksums):
        first_seen: dict[str, int] = {}
        pairs = []
        for c in checksums:
            if c["sha256"] in first_seen:
                pairs.append([first_seen[c["sha256"]], c["frame"]])
            else:
                first_seen[c["sha256"]] = c["frame"]
        print("BARRIER_DUPLICATE_SOURCE_FRAMES " + json.dumps(pairs), flush=True)
        # A preview shard reports duplicates and carries on so the preflight
        # can list every problem in one pass; production still fails closed.
        if not args.preview:
            raise ValueError("duplicate original Blender frames are forbidden")

    renderer_source_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    manifest_sha256 = hashlib.sha256(args.manifest.read_bytes()).hexdigest()
    result = {
        "episode_id": manifest["episode_id"],
        "renderer_source_sha256": renderer_source_sha256,
        "motion_source_sha256": hashlib.sha256(Path(motion.__file__).read_bytes()).hexdigest(),
        "car_geometry": geometry,
        "motion_summary": summaries,
        "approach_deg": APPROACH_DEG,
        "telemetry": telemetry,
        "manifest_sha256": manifest_sha256,
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
    if not args.preview and (
        result["resolution"] != manifest["resolution"]
        or result["cycles_samples"] != manifest["cycles_samples"]
    ):
        raise ValueError("production frame quality cannot differ from approved manifest")
    (out / "barrier-proof.json").write_text(json.dumps(result, indent=2))
    print("BARRIER_SHARD_DONE " + json.dumps({
        "frame_count": len(checksums), "first": checksums[0]["frame"],
        "last": checksums[-1]["frame"], "preview_only": args.preview,
        "render_seconds_total": round(sum(render_seconds), 3),
    }), flush=True)


if __name__ == "__main__":
    main()
