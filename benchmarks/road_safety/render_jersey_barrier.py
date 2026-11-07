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
comparison shot). The car is a stylized two-box-plus-wheels silhouette, not
a photoreal model -- same honesty convention as this project's other
"stylized, kinematic visual demonstration, not a calibrated crash-physics
model" disclaimers. It gives the macro wheel shot an unambiguous size
reference, fixing the earlier episode's scale problem, without adding an
external asset dependency (same no-external-asset style as
render_road_paint.py).

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


def arguments():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--start", type=int, required=True)
    p.add_argument("--end", type=int, required=True)
    p.add_argument("--preview", action="store_true")
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return p.parse_args(argv)


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


def cylinder(name, start, end, radius, mat, vertices=24):
    start, end = Vector(start), Vector(end)
    mid = (start + end) / 2
    length = (end - start).length
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices, radius=radius, depth=max(length, 1e-5), location=mid)
    ob = bpy.context.object
    ob.name = name
    direction = (end - start).normalized() if length > 1e-6 else Vector((0, 0, 1))
    ob.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
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


def point_light(light, location, target):
    light.location = Vector(location)
    light.rotation_euler = (Vector(target) - light.location).to_track_quat("-Z", "Y").to_euler()


KEY_REFERENCE_DISTANCE = 4.0
KEY_REFERENCE_ENERGY = 900.0


def aim_key_light(light, location, target):
    """Same inverse-square compensation as render_road_paint.py's
    aim_headlight(): this single key light is reused from a 9m wide
    establishing shot down to a 0.3m macro wheel shot, so its energy has to
    scale with distance^2 or it would be invisible wide and blown out
    macro."""
    point_light(light, location, target)
    distance = (Vector(target) - Vector(location)).length
    ratio = max(distance, 0.01) / KEY_REFERENCE_DISTANCE
    light.data.energy = KEY_REFERENCE_ENERGY * ratio * ratio


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


CAR_WHEEL_RADIUS = 0.33
CAR_HALF_WIDTH = 0.90
CAR_HALF_LENGTH = 2.15
CAR_WHEEL_X = [-0.78, 0.78]
CAR_WHEEL_Y = [-1.55, 1.55]


def build_car(prefix, body_mat, glass_mat, wheel_mat):
    """A stylized two-box-plus-four-wheels silhouette: unambiguous as 'a
    car' at every shot distance in this episode, unlike an abstract
    primitive, without needing an external car asset. Everything is
    parented to a root empty at the world origin so the whole rig can be
    moved/rotated as one rigid body per shot."""
    root = bpy.data.objects.new(f"{prefix} root", None)
    bpy.context.collection.objects.link(root)
    body = cube(f"{prefix} body", (0, 0, CAR_WHEEL_RADIUS + 0.45),
                (CAR_HALF_WIDTH * 2, CAR_HALF_LENGTH * 2, 0.9), body_mat)
    body.parent = root
    cabin = cube(f"{prefix} cabin", (0, -0.25, CAR_WHEEL_RADIUS + 1.08),
                 (CAR_HALF_WIDTH * 1.7, CAR_HALF_LENGTH * 1.0, 0.56), glass_mat)
    cabin.parent = root
    wheels = []
    for wx in CAR_WHEEL_X:
        for wy in CAR_WHEEL_Y:
            w = cylinder(f"{prefix} wheel {wx}_{wy}",
                         (wx - 0.09, wy, CAR_WHEEL_RADIUS),
                         (wx + 0.09, wy, CAR_WHEEL_RADIUS),
                         CAR_WHEEL_RADIUS, wheel_mat)
            w.parent = root
            wheels.append(w)
    return root, wheels


def main():
    args = arguments()
    manifest = json.loads(args.manifest.read_text(encoding="utf8"))
    shots = manifest["shots"]

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
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
    scene.world.color = (0.30, 0.33, 0.40)
    if scene.world.use_nodes:
        bg = scene.world.node_tree.nodes.get("Background")
        if bg is not None:
            bg.inputs["Color"].default_value = (0.30, 0.33, 0.40, 1)
            bg.inputs["Strength"].default_value = 1.0

    asphalt_mat = material("Dusk asphalt", (0.07, 0.072, 0.078), rough=0.9)
    asphalt_grain(asphalt_mat)
    flat_wall_mat = material("Flat wall concrete", (0.62, 0.61, 0.58), rough=0.75)
    barrier_mat = material("Jersey barrier concrete", (0.64, 0.63, 0.60), rough=0.72)
    body_mat = material("Car body paint", (0.72, 0.1, 0.08), metal=0.3, rough=0.35)
    glass_mat = material("Car glass", (0.04, 0.05, 0.06), rough=0.15)
    wheel_mat = material("Car tyre", (0.015, 0.015, 0.016), rough=0.8)

    cube("Road surface", (0, 0, -0.05), (10.0, 60.0, 0.10), asphalt_mat)

    flat_wall = extruded_profile("Flat wall (before)", flat_profile(), -20, 20, flat_wall_mat)
    flat_wall.location = (BARRIER_X, 0, 0)
    sloped_barrier = extruded_profile("Jersey barrier (ribbon face)", sloped_profile(), -20, 20, barrier_mat)
    sloped_barrier.location = (BARRIER_X, 0, 0)

    car_root, wheels = build_car("Demo car", body_mat, glass_mat, wheel_mat)
    front_wheels = [w for w in wheels if w.location.x > 0]

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
    key.rotation_euler = (math.radians(68), 0, math.radians(35))
    key.data.energy = 2.6

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
        car_root.hide_render = True
        macro_key.hide_render = True
        for w in wheels:
            w.location.z = CAR_WHEEL_RADIUS

        if shot["id"] == "barrier_establish":
            sloped_barrier.hide_render = False
            cam_pos = (lerp(6.5, 4.2, t), lerp(-10.0, -6.0, t), lerp(3.4, 2.4, t))
            target = (BARRIER_X, cam_pos[1] + 7.0, 0.5)
            set_camera(cam, cam_pos, target)
            aim_key_light(key, Vector((0, 0, 0)), Vector((0, 0, 0)))
            key.data.energy = 2.6

        elif shot["id"] == "flat_wall_fail":
            flat_wall.hide_render = False
            car_root.hide_render = False
            phase = min(1.0, t / 0.5)
            settle = max(0.0, (t - 0.5) / 0.5)
            cx = lerp(0.0, BARRIER_X - CAR_HALF_WIDTH - 0.08, min(1.0, phase))
            cy = lerp(-7.0, 0.0, min(1.0, phase))
            car_root.location = (cx, cy, 0)
            car_root.rotation_euler = (math.radians(-9.0 * settle), 0, math.radians(-14.0))
            cam_pos = (cx - 1.4, cy - 4.6, 1.15)
            target = (BARRIER_X - 0.6, cy + 2.5, 0.5)
            set_camera(cam, cam_pos, target)
            key.data.energy = 2.6

        elif shot["id"] == "barrier_cross_section":
            sloped_barrier.hide_render = False
            angle = lerp(-0.55, 0.55, t)
            radius = 1.35
            cam_pos = (BARRIER_X + math.sin(angle) * radius, -19.3 + math.cos(angle) * -radius * 0.4,
                       lerp(0.35, 0.55, (math.sin(t * math.tau) * 0.5 + 0.5)))
            target = (BARRIER_X, -20, 0.4)
            set_camera(cam, cam_pos, target)
            key.data.energy = 2.6

        elif shot["id"] == "wheel_climb_macro":
            sloped_barrier.hide_render = False
            car_root.hide_render = False
            car_root.location = (BARRIER_X - CAR_HALF_WIDTH - 0.08, 0, 0)
            car_root.rotation_euler = (0, 0, math.radians(-14.0))
            lift = min(1.0, t * 1.3) * 0.22
            for w in front_wheels:
                w.location.z = CAR_WHEEL_RADIUS + lift
            wheel_point = car_root.matrix_world @ front_wheels[0].location
            cam_pos = Vector((wheel_point.x - lerp(0.55, 0.35, t),
                              wheel_point.y + math.sin(t * math.tau * 0.5) * 0.15,
                              wheel_point.z + 0.12))
            target = wheel_point
            set_camera(cam, cam_pos, target)
            macro_key.hide_render = False
            macro_key.location = Vector(cam_pos) + Vector((0.1, 0.2, 0.3))
            macro_key.data.energy = 40

        elif shot["id"] == "sloped_barrier_success":
            sloped_barrier.hide_render = False
            car_root.hide_render = False
            phase = min(1.0, t / 0.5)
            redirect = max(0.0, (t - 0.5) / 0.5)
            cx_approach = lerp(0.0, BARRIER_X - CAR_HALF_WIDTH - 0.08, min(1.0, phase))
            cx = lerp(cx_approach, cx_approach - 0.85, redirect)
            cy = lerp(-7.0, 0.0, min(1.0, phase))
            cy = lerp(cy, cy + 7.0, redirect)
            car_root.location = (cx, cy, 0)
            heading = lerp(-14.0, 0.0, redirect)
            car_root.rotation_euler = (0, 0, math.radians(heading))
            lift_phase = max(0.0, min(1.0, (t - 0.35) / 0.3))
            lift = math.sin(lift_phase * math.pi) * 0.22
            for w in front_wheels:
                w.location.z = CAR_WHEEL_RADIUS + lift
            cam_pos = (cx - 1.4, cy - 4.6, 1.15)
            target = (cx + 0.3, cy + 2.5, 0.5)
            set_camera(cam, cam_pos, target)
            key.data.energy = 2.6

        elif shot["id"] == "barrier_closing":
            sloped_barrier.hide_render = False
            car_root.hide_render = False
            car_root.location = (BARRIER_X - CAR_HALF_WIDTH - 0.93, lerp(2.0, 14.0, t), 0)
            car_root.rotation_euler = (0, 0, 0)
            pan = lerp(-3.5, 3.5, t)
            cam_pos = (BARRIER_X + 1.5, pan, 9.0)
            target = (BARRIER_X, pan + 6.0, 0.3)
            set_camera(cam, cam_pos, target)
            key.data.energy = 2.9

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
