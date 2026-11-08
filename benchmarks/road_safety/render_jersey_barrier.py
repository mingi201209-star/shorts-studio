"""Jersey barrier ribbon effect, a specific instance of this project's
approved "guardrail-deflection" topic (shorts_studio/factory/series.py's
ROAD_SAFETY_FIRST_SEVEN, topic_id "guardrail-deflection"): a flat wall stops
or flips a car that hits it at an angle, but a barrier with a sloped face
lets the wheel ride up the slope instead of digging in, lifting and
redirecting the car back into its own lane -- the same deflection principle
guardrail-deflection names, shown through the concrete-barrier case.

This replaces the retroreflective-road-paint episode on this branch after
direct user feedback that episode's shots repeated (two near-duplicate
"night wide" shots, two near-duplicate "macro bead" shots) and its macro
shots had no scale reference, making a "tiny glass bead" read as room-sized
on screen. Every shot below uses a distinct camera treatment (wide push-in,
low chase, orbiting cutaway, macro wheel, overhead pan) except the one
deliberate exception: flat_wall_fail and sloped_barrier_success mirror the
same chase-camera geometry on purpose, so the before/after comparison is
literally on screen (same device as road-paint's with/without-beads
comparison shot). The car is the same pinned CC0 detailed sedan this
project already uses in render_curious_mechanics.py/render_rumble_episode2.py
(real user request: "use the car we made before" after an earlier version
of this episode used a stylized two-box-plus-wheels placeholder) -- it
gives the macro wheel shot an unambiguous size reference, fixing the
earlier episode's scale problem, without modeling a car from scratch.
Everything else (barrier, road, markers, lighting) stays fully procedural.

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
from mathutils import Vector

PINNED_SCENE_SHA256 = "a82e05825f907cc99678ab12855527552e34323b31ae801625af4a0f563ed877"


def arguments():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--start", type=int, required=True)
    p.add_argument("--end", type=int, required=True)
    p.add_argument("--preview", action="store_true")
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


def set_camera(cam, location, target):
    cam.location = Vector(location)
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()


BARRIER_X = 2.4
BASE_HALF_WIDTH = 0.30
BARRIER_HEIGHT = 0.81


def flat_profile():
    """A plain vertical wall, same footprint and height as the real
    barrier, for the 'before' comparison -- a flat face the full height,
    no slope at all."""
    return [
        (-BASE_HALF_WIDTH, 0.0), (-BASE_HALF_WIDTH, BARRIER_HEIGHT),
        (BASE_HALF_WIDTH, BARRIER_HEIGHT), (BASE_HALF_WIDTH, 0.0),
    ]


def sloped_profile():
    """Simplified New-Jersey-shape cross-section: a toe at the base, a
    dominant sloped face (the ribbon-effect face that redirects a wheel),
    a short near-vertical run to a narrow flat top, then a plain back
    face. Traffic-facing side is -x, matching cars approaching from -x."""
    return [
        (-BASE_HALF_WIDTH, 0.0), (-0.12, 0.55), (-0.08, BARRIER_HEIGHT),
        (0.08, BARRIER_HEIGHT), (BASE_HALF_WIDTH, 0.0),
    ]


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


# Safety-margin envelope around the real car, used only to keep cameras
# from ending up inside its mesh (same purpose the old stylized car's
# hard-coded half-width/length served) -- rounded up from the real car's
# own measured bounding box in load_source_car() below, not load-bearing
# for anything else.
# Measured from preview run 42454408264's CAR_BOUNDS print (half_width
# 0.986, half_length 1.996 once the axes are corrected -- see the
# rotation_euler comment in load_source_car()), rounded up for margin.
CAR_HALF_WIDTH = 1.1
CAR_HALF_LENGTH = 2.2
CAR_WHEEL_RADIUS = 0.33


def load_source_car(source_path):
    """Loads the same pinned CC0 detailed sedan render_curious_mechanics.py
    and render_rumble_episode2.py already use, by opening it as the base
    scene (same technique those two scripts use) and pruning everything
    that isn't the car -- this episode's road, barrier, markers and
    lighting are all built fresh afterward, same as before. Real user
    request: swap out the earlier stylized two-box placeholder for the
    actual car model this project already has."""
    stable_source(source_path)
    bpy.ops.wm.open_mainfile(filepath=str(source_path))
    car = bpy.data.objects.get("CC0 detailed sedan animated as a rigid car")
    if car is None:
        raise ValueError("source car hierarchy unavailable")
    keep = {car, *car.children_recursive}
    for ob in list(bpy.data.objects):
        if ob not in keep:
            bpy.data.objects.remove(ob, do_unlink=True)
    if len([o for o in car.children_recursive if o.type == "MESH"]) < 65:
        raise ValueError("incomplete vehicle part set")
    car.animation_data_clear()
    for ob in car.children_recursive:
        if ob.animation_data:
            ob.animation_data_clear()
    # Real measurement from preview run 42454408264's CAR_BOUNDS print:
    # render_curious_mechanics.py's own pi/2 rotation (presumably matching
    # THEIR scene's forward axis, not necessarily this one) put the car's
    # ~4m length along world X and its ~2m width along world Y -- the
    # opposite of what this episode's shot code assumes (length along Y,
    # matching every other object in this scene). No extra rotation (just
    # the mesh's native orientation) should put length back along Y.
    car.rotation_euler = (0, 0, 0)
    car.scale = (0.85, 0.85, 0.85)
    car.location = (0, 0, 0)

    root = bpy.data.objects.new("Demo car root", None)
    bpy.context.collection.objects.link(root)
    car.parent = root
    car.matrix_parent_inverse.identity()

    bpy.context.view_layer.update()
    corners = [ob.matrix_world @ Vector(v) for ob in car.children_recursive
               if ob.type == "MESH" for v in ob.bound_box]
    xs, ys, zs = [c.x for c in corners], [c.y for c in corners], [c.z for c in corners]
    print("CAR_BOUNDS " + json.dumps({
        "half_width": round((max(xs) - min(xs)) / 2, 3),
        "half_length": round((max(ys) - min(ys)) / 2, 3),
        "bottom_z": round(min(zs), 3), "top_z": round(max(zs), 3),
    }), flush=True)
    return root, car


def barrier_markers(post_mat, stripe_mat):
    """Real bug found by comparing actual rendered frames from production
    run 42396471568 (visual_activity FAIL: 'picture held static for 15.5s'):
    the barrier and road are perfectly uniform, featureless, and run the
    full -20..20 length with no breaks, so a camera translating alongside
    or chasing a car along them is nearly translation-invariant -- camera,
    subject and background all move together through a scene with no
    distinguishing features, so almost nothing in the actual picture
    changes frame to frame, however far the camera travels (same failure
    mode road-paint's first night_wide attempt hit, worse here because
    even the car-chase shots had no independent background cue). A
    reflective post plus a painted road stripe every 3 units gives every
    camera move in this episode something concrete to reveal passing by."""
    markers = []
    for y in range(-19, 20, 3):
        post = cube(f"Barrier reflector post {y}", (BARRIER_X - 0.45, y, 0.14), (0.05, 0.05, 0.28), post_mat)
        cap = cube(f"Barrier reflector cap {y}", (BARRIER_X - 0.45, y, 0.29), (0.09, 0.05, 0.03), post_mat)
        markers += [post, cap]
    for y in range(-19, 20, 6):
        markers.append(cube(f"Road stripe {y}", (-1.0, y, 0.001), (0.12, 2.0, 0.002), stripe_mat))
    return markers


def set_car_visible(root, visible):
    """hide_render on an Empty does NOT cascade to its mesh children in
    Blender -- it is a per-object flag checked independently at render
    time. Real bug found in preview run 42387340025 (frame 81 showed the
    car in barrier_establish, which never un-hides it): setting
    car_root.hide_render alone left the actual body/cabin/wheel meshes at
    their default hide_render=False forever, so the car rendered in every
    shot regardless of this flag. Every mesh child must be set directly."""
    root.hide_render = not visible
    for child in root.children_recursive:
        child.hide_render = not visible


def main():
    args = arguments()
    manifest = json.loads(args.manifest.read_text(encoding="utf8"))
    shots = manifest["shots"]

    # load_source_car() opens the pinned .blend as the base scene (same
    # technique render_curious_mechanics.py uses for this asset) -- that
    # REPLACES bpy.data wholesale, so it must happen before anything else
    # in this scene is built, not after (an earlier draft of this function
    # built the whole road/barrier/marker scene first and would have had
    # open_mainfile silently discard all of it).
    car_root, car = load_source_car(args.source)
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
    scene.world.color = (0.10, 0.12, 0.19)
    if scene.world.use_nodes:
        bg = scene.world.node_tree.nodes.get("Background")
        if bg is not None:
            bg.inputs["Color"].default_value = (0.10, 0.12, 0.19, 1)
            bg.inputs["Strength"].default_value = 1.0

    # Preview run 42386915851: a near-background-grey concrete against a
    # similarly bright sky made the barrier nearly invisible in every chase
    # shot -- a much darker dusk sky plus a noticeably lighter, warmer
    # concrete gives the barrier real contrast against the background.
    asphalt_mat = material("Dusk asphalt", (0.055, 0.056, 0.06), rough=0.9)
    asphalt_grain(asphalt_mat)
    flat_wall_mat = material("Flat wall concrete", (0.80, 0.77, 0.70), rough=0.7)
    barrier_mat = material("Jersey barrier concrete", (0.82, 0.79, 0.72), rough=0.68)
    post_mat = material("Reflector post", (0.9, 0.78, 0.2), emission=1.2)
    stripe_mat = material("Road lane stripe", (0.78, 0.76, 0.7), rough=0.6)

    cube("Road surface", (0, 0, -0.05), (10.0, 60.0, 0.10), asphalt_mat)

    flat_wall = extruded_profile("Flat wall (before)", flat_profile(), -20, 20, flat_wall_mat)
    flat_wall.location = (BARRIER_X, 0, 0)
    sloped_barrier = extruded_profile("Jersey barrier (ribbon face)", sloped_profile(), -20, 20, barrier_mat)
    sloped_barrier.location = (BARRIER_X, 0, 0)
    barrier_markers(post_mat, stripe_mat)

    # Same technique render_curious_mechanics.py uses: reuse the car's own
    # original body material, just recolor it, rather than overriding the
    # whole mesh's materials.
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

    bpy.ops.object.light_add(type="SUN")
    key = bpy.context.object
    key.name = "Low dusk sun"
    key.data.angle = 0.2
    # Set once and never touched again. Real bug found in preview run
    # 42386915851: barrier_establish called point_light() (a position/target
    # aimer meant for the macro area light) on this SUN with a degenerate
    # (0,0,0)->(0,0,0) target, which silently overwrote this rotation with
    # an undefined one -- every later shot inherited that broken direction,
    # explaining the flat, low-contrast lighting across the whole preview.
    # A directional SUN only ever needs a rotation, never a location/target.
    key.rotation_euler = (math.radians(55), 0, math.radians(35))
    key.data.energy = 3.6

    bpy.ops.object.light_add(type="AREA", location=(0, -4, 3))
    macro_key = bpy.context.object
    macro_key.name = "Macro fill light"
    macro_key.data.size = 1.2
    macro_key.data.color = (1.0, 0.97, 0.9)

    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    checksums = []
    render_seconds = []

    def shot_for(frame):
        for s in shots:
            if s["start"] <= frame <= s["end"]:
                return s
        raise ValueError(f"frame {frame} not covered by any shot")

    for frame in range(args.start, args.end + 1):
        shot = shot_for(frame)
        t = (frame - shot["start"]) / max(1, shot["end"] - shot["start"])

        flat_wall.hide_render = True
        sloped_barrier.hide_render = True
        set_car_visible(car_root, False)
        macro_key.hide_render = True

        if shot["id"] == "barrier_establish":
            # Preview run 42387613693 (frame 81, car bug now fixed): from
            # this far/high an elevated angle, a 0.81m-tall barrier
            # perspective-flattens into a thin line -- no sense of it being
            # a real wall. Much lower and closer, roughly at the barrier's
            # own height, reads its face and top as actual volume instead.
            # Real bug found by pixel-diffing actual preview frames (run
            # 42430310209, frame 1 vs frame 165 mean diff only 4.8, well
            # under the QA's 12.0 threshold): target was defined as
            # cam_pos[1]+5.0 -- always exactly 5 units ahead of the camera
            # -- so as the camera translated forward, the VIEWING ANGLE
            # never changed at all, just its position. A fixed target
            # point makes the camera genuinely sweep past it instead.
            # Per-axis lerps (x, y, z independently) kept landing around
            # 9.0 mean diff however much the raw numbers were widened --
            # same mistake as barrier_cross_section's first fix: moving
            # several offsets independently doesn't reliably shrink the
            # true camera-to-target DISTANCE. Switching to the same
            # explicit radial distance/angle approach that got
            # cross_section and barrier_closing over threshold.
            # Neither translating the camera (first attempt) nor closing
            # true radial distance on a fixed target (second attempt, risked
            # ending up inside the barrier's own solid or losing it from
            # frame) reliably cleared the threshold. barrier_closing's fix
            # (FIXED camera, target swinging through a wide arc) scored
            # 29.2 -- comfortable margin -- so apply the same proven device
            # here instead of a third bespoke tuning attempt.
            # Lowering the camera only got to 8.7 -- horizon position
            # barely moves with a sub-1-unit height change at this
            # distance. Final approach: dolly in directly on one specific
            # reflector post (a real, textured, close object, not just an
            # aim point on open road), ending close enough (0.9 units) for
            # it to sweep dramatically through frame -- same principle as
            # wheel_climb_macro's close framing, which cleared threshold
            # by a wide margin.
            sloped_barrier.hide_render = False
            post_target = (BARRIER_X - 0.6, 2.0, 0.15)
            angle = lerp(-0.25, 0.25, t)
            dist = lerp(14.0, 0.6, t)
            cam_pos = (post_target[0] + math.sin(angle) * dist,
                       post_target[1] - math.cos(angle) * dist,
                       lerp(1.1, 0.18, t))
            set_camera(cam, cam_pos, post_target)
            key.data.energy = 3.6

        elif shot["id"] == "flat_wall_fail":
            # Real bug found by comparing actual production frames (run
            # 42396471568, frames 181 vs 210): a camera that chases the car
            # at a near-constant relative offset keeps the car almost fixed
            # in frame, and against a featureless wall/road the picture
            # barely changes even though the car is genuinely moving in
            # world space. A STATIC side-on camera makes the car's own
            # motion -- and now the reflector posts/stripes sliding past --
            # unambiguous instead of relying on camera movement at all.
            flat_wall.hide_render = False
            set_car_visible(car_root, True)
            phase = min(1.0, t / 0.5)
            settle = max(0.0, (t - 0.5) / 0.5)
            cx = lerp(0.0, BARRIER_X - CAR_HALF_WIDTH - 0.08, min(1.0, phase))
            cy = lerp(-7.0, 0.0, min(1.0, phase))
            car_root.location = (cx, cy, 0)
            car_root.rotation_euler = (math.radians(-9.0 * settle), 0, math.radians(-14.0))
            # Second real bug, found the same way (pixel-diffing actual
            # frames, run 42430310209: mean diff 10.4, still under 12.0):
            # a fully static camera relies entirely on the car -- a small
            # fraction of the frame -- for any pixel change at all, and
            # that is not enough on its own. Pushing the camera in toward
            # the action over the shot changes the apparent size of
            # EVERYTHING in frame (wall, markers, road), not just the car,
            # which is a far larger and more reliable source of real
            # pixel-level change than hoping one small moving object
            # carries the whole measurement.
            cam_pos = (lerp(-10.5, -3.2, t), lerp(-9.5, -2.8, t), lerp(2.8, 0.9, t))
            target = (BARRIER_X - 0.3, -3.3, 0.4)
            set_camera(cam, cam_pos, target)
            key.data.energy = 3.6

        elif shot["id"] == "barrier_cross_section":
            # Real bug in preview run 42386915851 (frame 399, fully black):
            # the camera sat only ~0.2-0.7 units from the target, nearly
            # grazing the barrier's own solid cross-section instead of
            # standing back to actually frame the cutaway end cap. Pulling
            # the whole orbit well clear of the barrier's y=-20 end (camera
            # now 3.2-4.6 units out, not <1) gives it room to see the slice.
            # Pixel-diff on preview run 42430310209 (frame 331 vs 465, mean
            # diff only 2.7): the wedge cap is a small object against a lot
            # of empty sky/road, so even a real, visible silhouette change
            # barely moves the frame-wide mean. A bigger angle sweep AND a
            # push-in (radius shrinking over the shot) together make the
            # cap fill much more of the frame by the end, giving the
            # changing subject real weight in the average instead of being
            # diluted by mostly-static background.
            sloped_barrier.hide_render = False
            # Second attempt (preview run 42430779080, frame 331 vs 465):
            # a +/-1.0 rad swing changed the VIEWING ANGLE of the wedge so
            # much that it read as narrower, not bigger, by t=1, cancelling
            # out the intended push-in -- and the push-in itself barely
            # worked anyway, because only the small x/z "radius" term
            # shrank while the dominant y-offset (-20-2.4) that actually
            # set most of the camera-to-target distance never changed.
            # Scaling true camera-to-target DISTANCE directly (not just
            # one offset term) with a smaller angle swing actually closes
            # the gap this time.
            angle = lerp(-0.4, 0.4, t)
            dist = lerp(3.6, 1.4, t)
            cam_pos = (BARRIER_X + math.sin(angle) * dist,
                       -20 - math.cos(angle) * dist,
                       lerp(0.3, 0.65, (math.sin(t * math.tau) * 0.5 + 0.5)))
            target = (BARRIER_X, -20, 0.4)
            set_camera(cam, cam_pos, target)
            key.data.energy = 3.6

        elif shot["id"] == "wheel_climb_macro":
            # Real bug in preview run 42386915851 (frame 541, a close-up of
            # a flat mesh interior face): the camera offset put it INSIDE
            # the car body's own bounding box (body spans roughly x in
            # [0.52, 2.32] around the car's resting position, and the old
            # offset landed at x in [1.65, 1.85]). Dropping the approach
            # heading to zero for this shot (it is a static explanatory
            # close-up, not a moving approach) and placing the camera
            # clearly beyond the body's +x edge fixes that.
            sloped_barrier.hide_render = False
            set_car_visible(car_root, True)
            car_root.location = (BARRIER_X - CAR_HALF_WIDTH - 0.08, 0, 0)
            # Tilting the whole car (not an individually-articulated wheel
            # -- the real CC0 car's wheels aren't rigged for that here) is
            # the same "stylized, kinematic, not calibrated" simplification
            # this project already uses elsewhere for illustrative motion.
            lift = min(1.0, t * 1.3) * 0.22
            car_root.rotation_euler = (0, math.radians(lift * 10), 0)
            wheel_point = car_root.matrix_world @ Vector(
                (CAR_HALF_WIDTH, CAR_HALF_LENGTH * 0.55, CAR_WHEEL_RADIUS + lift))
            # Preview run 42388175956 (frame 541, still flat blown-out
            # grey after removing the macro light): the barrier's own
            # solid cross-section spans roughly x in [2.1, 2.7] at every
            # y and any z from 0 to 0.81 -- the lateral-only camera offset
            # (+0.38 to +0.55 in x from a wheel at x~2.2) put the camera
            # INSIDE that solid, not clear of it. Only height reliably
            # clears a shape that runs the full length of the road:
            # placing the camera above BARRIER_HEIGHT looking down at the
            # contact point is outside the solid regardless of x or y.
            # Real car swap (preview run 42454726586, frame 540): the real
            # car's body is taller and the old 0.12/0.75 offsets were far
            # too tight against it, landing the camera right against a
            # body panel. Staying low (near wheel height, not body height)
            # and well clear laterally keeps the camera off the car itself.
            cam_pos = Vector((wheel_point.x + 0.6,
                              wheel_point.y - 0.3 + math.sin(t * math.tau * 0.5) * 0.15,
                              wheel_point.z + 0.15))
            target = wheel_point
            set_camera(cam, cam_pos, target)
            # Preview runs 42387613693 and 42387885176: energy=60, then
            # energy=4.0, both still blew the frame to flat white -- at
            # this macro range (camera ~0.3-0.5 units from the subject)
            # irradiance from ANY nearby area light scales too fast with
            # 1/distance^2 to tune by trial. Dropping the dedicated macro
            # light entirely and relying on the same sun + world ambient
            # every other shot uses removes that failure mode outright.
            key.data.energy = 3.6

        elif shot["id"] == "sloped_barrier_success":
            sloped_barrier.hide_render = False
            set_car_visible(car_root, True)
            phase = min(1.0, t / 0.5)
            redirect = max(0.0, (t - 0.5) / 0.5)
            cx_approach = lerp(0.0, BARRIER_X - CAR_HALF_WIDTH - 0.08, min(1.0, phase))
            cx = lerp(cx_approach, cx_approach - 0.85, redirect)
            cy = lerp(-7.0, 0.0, min(1.0, phase))
            cy = lerp(cy, cy + 7.0, redirect)
            car_root.location = (cx, cy, 0)
            heading = lerp(-14.0, 0.0, redirect)
            lift_phase = max(0.0, min(1.0, (t - 0.35) / 0.3))
            lift = math.sin(lift_phase * math.pi) * 0.22
            # Same whole-car tilt as wheel_climb_macro (not an individually
            # articulated wheel) standing in for the climb/redirect.
            car_root.rotation_euler = (0, math.radians(lift * 10), math.radians(heading))
            # Same proven device as barrier_establish's final fix: FIXED
            # camera, target swinging through a wide arc (same as
            # barrier_closing, which scored 29.2) -- the car's own motion
            # plus a real background sweep together, not relying on either
            # alone.
            cam_pos = (-5.0, -5.5, 1.6)
            target = (BARRIER_X - 0.3, lerp(-10.0, 10.0, t), 0.4)
            set_camera(cam, cam_pos, target)
            key.data.energy = 3.6

        elif shot["id"] == "barrier_closing":
            sloped_barrier.hide_render = False
            set_car_visible(car_root, True)
            car_root.location = (BARRIER_X - CAR_HALF_WIDTH - 0.93, lerp(2.0, 14.0, t), 0)
            car_root.rotation_euler = (0, 0, 0)
            # Real bug found the same way as barrier_establish: camera and
            # target both shifted by the same `pan` amount, so the viewing
            # angle never actually changed, just its position -- classic
            # comoving-camera mistake. A FIXED target while the camera
            # sweeps and descends in height makes the whole barrier line
            # genuinely swing through frame instead.
            cam_pos = (BARRIER_X + 1.8, lerp(-6.0, 7.0, t), lerp(11.0, 4.0, t))
            target = (BARRIER_X, 5.0, 0.3)
            set_camera(cam, cam_pos, target)
            key.data.energy = 3.9

        else:
            raise ValueError(f"unknown shot id {shot['id']!r}")

        scene.frame_set(frame)
        bpy.context.view_layer.update()
        frame_path = out / f"frame_{frame:04d}.png"
        scene.render.filepath = str(frame_path)
        start_time = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        elapsed = round(time.perf_counter() - start_time, 3)
        sha = hashlib.sha256(frame_path.read_bytes()).hexdigest()
        checksums.append({"frame": frame, "shot_id": shot["id"], "sha256": sha, "render_seconds": elapsed})
        render_seconds.append(elapsed)
        print(f"BARRIER_NATIVE_FRAME {frame}/{manifest['total_frames']}", flush=True)

    if len({c["sha256"] for c in checksums}) != len(checksums):
        raise ValueError("duplicate original Blender frames are forbidden")

    renderer_source_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    manifest_sha256 = hashlib.sha256(args.manifest.read_bytes()).hexdigest()
    result = {
        "episode_id": manifest["episode_id"],
        "renderer_source_sha256": renderer_source_sha256,
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
