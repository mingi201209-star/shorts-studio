"""Opt-in visual pilot: retroreflective road paint (glass beads), topic #6 of the
approved 7-video "Hidden Engineering of American Roads" series
(shorts_studio/factory/series.py's ROAD_SAFETY_FIRST_SEVEN, topic_id
"retroreflective-road-paint").

Fully procedural (same no-external-asset style as shorts_studio/factory/
rumble_surface.py): a painted lane stripe with scattered glass-bead spheres,
lit either by a near-camera "headlight" light (bright retroreflective glint
toward the viewer) or an off-axis "ambient" light (same beads, dull) --
real Cycles light transport doing the actual physical work, not a shader
trick. The light-path illustration in the macro shot is explicitly
illustrative (three straight emissive segments showing enter/bend/exit),
not a traced ray -- same honesty convention as this project's existing
"stylized, kinematic visual demonstration, not a calibrated ... model"
disclaimers.

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


def sphere(name, center, radius, mat, segments=20, rings=12):
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=radius, location=center, segments=segments, ring_count=rings)
    ob = bpy.context.object
    ob.name = name
    ob.data.materials.append(mat)
    return ob


def cylinder(name, start, end, radius, mat):
    """A straight emissive tube from start to end -- used only for the
    illustrative light-path overlay in the macro shot."""
    start, end = Vector(start), Vector(end)
    mid = (start + end) / 2
    length = (end - start).length
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=16, radius=radius, depth=max(length, 1e-5), location=mid)
    ob = bpy.context.object
    ob.name = name
    direction = (end - start).normalized() if length > 1e-6 else Vector((0, 0, 1))
    ob.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    ob.data.materials.append(mat)
    return ob


def bead_positions(n, width, depth, seed=20261106):
    """Deterministic, reproducible bead layout -- never re-randomized per
    run, so pixel checksums stay comparable across shards/re-renders of the
    same shot."""
    rng_state = seed
    positions = []
    for i in range(n):
        rng_state = (1103515245 * rng_state + 12345) & 0x7FFFFFFF
        fx = (rng_state % 10000) / 10000
        rng_state = (1103515245 * rng_state + 12345) & 0x7FFFFFFF
        fy = (rng_state % 10000) / 10000
        rng_state = (1103515245 * rng_state + 12345) & 0x7FFFFFFF
        fr = (rng_state % 10000) / 10000
        x = (fx - 0.5) * width
        y = (fy - 0.5) * depth
        r = 0.010 + fr * 0.008
        positions.append((x, y, r))
    return positions


def build_scene(beads_mat, paint_mat, asphalt_mat):
    """One lane stripe embedded with glass beads, sitting in a dark asphalt
    plane. Shared by every shot; only camera/lighting change between them."""
    cube("Asphalt road surface", (0, 0, -0.05), (6.0, 40.0, 0.10), asphalt_mat)
    stripe = cube("Painted lane stripe", (0, 0, 0.0015), (0.42, 30.0, 0.003), paint_mat)
    beads = []
    for x, y, r in bead_positions(260, 0.40, 28.0):
        # segments=10/rings=7 read as faceted "golf balls" rather than smooth
        # glass under macro-shot lighting (real human_first_view feedback,
        # docs/quality/road-paint-retroreflective-human-review-20261107.json);
        # 22/14 is still cheap for 260 spheres but removes the visible facets.
        beads.append(sphere(f"Glass bead {len(beads)}", (x, y, 0.004 + r * 0.55), r, beads_mat, segments=22, rings=14))
    return stripe, beads


def hero_beads(beads, n=3):
    """A few beads near the macro-shot camera target (y=0), used for the ray overlay."""
    near = sorted(beads, key=lambda b: abs(b.location.y))[:n]
    return near


def lerp(a, b, t):
    return a + (b - a) * t


def set_camera(cam, location, target):
    cam.location = Vector(location)
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()


def point_light(light, location, target):
    """Spot/area lights point along local -Z by default; without this a
    light that only ever gets translated (never rotated) keeps illuminating
    whatever direction it started in -- the actual bug behind the first two
    previews' night_wide and macro shots being far too dark."""
    light.location = Vector(location)
    light.rotation_euler = (Vector(target) - light.location).to_track_quat("-Z", "Y").to_euler()


HEADLIGHT_REFERENCE_DISTANCE = 2.0
HEADLIGHT_REFERENCE_ENERGY = 420.0


def aim_headlight(light, location, target):
    """Same near-camera headlight across wildly different shot distances
    (3m wide shot down to 9cm macro): without compensating energy for
    distance, inverse-square falloff alone would make the same light either
    invisible at wide range or blown-out white at macro range."""
    point_light(light, location, target)
    distance = (Vector(target) - Vector(location)).length
    ratio = max(distance, 0.01) / HEADLIGHT_REFERENCE_DISTANCE
    light.data.energy = HEADLIGHT_REFERENCE_ENERGY * ratio * ratio


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
    scene.world.color = (0.008, 0.008, 0.012)
    if scene.world.use_nodes:
        bg = scene.world.node_tree.nodes.get("Background")
        if bg is not None:
            bg.inputs["Color"].default_value = (0.008, 0.008, 0.012, 1)
            bg.inputs["Strength"].default_value = 1.0

    asphalt_mat = material("Night asphalt", (0.022, 0.023, 0.025), rough=0.92)
    paint_mat = material("Lane paint base", (0.62, 0.60, 0.54), rough=0.55)
    beads_mat = material("Retroreflective glass bead", (0.92, 0.93, 0.95), rough=0.07)
    # Real human_first_view feedback (docs/quality/road-paint-retroreflective-
    # human-review-20261107.json): the single-color, thin (0.004 radius) ray
    # buried in a 260-bead macro field didn't read as "light goes in, comes
    # back out" to a viewer. Two distinct colors for the incoming headlight
    # beam vs. the outgoing retroreflected light, and a much thicker line,
    # are a legibility fix, not a physical claim about wavelength.
    ray_in_mat = material("Illustrative incoming ray", (0.55, 0.75, 1.0), rough=1.0, emission=7.0)
    ray_out_mat = material("Illustrative outgoing ray", (1.0, 0.75, 0.2), rough=1.0, emission=9.0)

    stripe, beads = build_scene(beads_mat, paint_mat, asphalt_mat)
    hero = hero_beads(beads)

    bpy.ops.object.camera_add(location=(0, -3, 0.6))
    cam = bpy.context.object
    scene.camera = cam
    # Explicit, known field of view: Blender's default "auto" sensor fit on a
    # PORTRAIT (1080x1920) render fits the sensor to the taller dimension,
    # which makes the effective horizontal FOV much narrower than a normal
    # 50mm lens suggests -- small objects at sub-metre distance filled almost
    # the whole frame in the first preview. Fixing sensor_fit=HORIZONTAL with
    # a known lens makes apparent size predictable across every shot.
    cam.data.sensor_fit = "HORIZONTAL"
    cam.data.sensor_width = 36
    cam.data.lens = 32

    bpy.ops.object.light_add(type="SPOT", location=(0.05, -2.9, 0.55))
    headlight = bpy.context.object
    headlight.name = "Near-camera headlight"
    headlight.data.energy = 420
    headlight.data.spot_size = 1.15
    headlight.data.spot_blend = 0.4
    headlight.data.color = (0.95, 0.96, 1.0)

    bpy.ops.object.light_add(type="AREA", location=(2.4, 0.5, 1.6))
    ambient = bpy.context.object
    ambient.name = "Off-axis ambient light"
    ambient.data.energy = 260
    ambient.data.size = 1.4
    ambient.data.color = (0.75, 0.80, 0.95)

    hb = hero[0] if hero else stripe
    entry = hb.location + Vector((-0.035, -0.012, 0.028))
    bend = hb.location + Vector((0.0, 0.0, 0.012))
    exitp = hb.location + Vector((0.035, -0.012, 0.028))
    ray_segments = [
        cylinder("Ray in", entry, bend, 0.009, ray_in_mat),
        cylinder("Ray out", bend, exitp, 0.009, ray_out_mat),
    ]
    for seg in ray_segments:
        seg.hide_render = True

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

        headlight.hide_render = True
        ambient.hide_render = True
        for seg in ray_segments:
            seg.hide_render = True

        if shot["id"] == "night_wide":
            # A pure forward dolly here is an almost perfect no-op on screen:
            # camera, headlight and target all translate together by the
            # same offset through a uniform stripe/asphalt with no unique
            # features, so the rendered picture is translation-invariant no
            # matter how far the camera travels. Widening the dolly distance
            # and adding a 0.65-unit height descent (measured in the
            # cheap diagnose run) still wasn't enough real signal -- a thin,
            # distant stripe against near-black asphalt barely moves the
            # full-frame mean pixel value even as the camera approaches.
            # Ending the dolly much closer (no longer matched to
            # paint_push_in's -1.6 start -- a hard cut into that shot is
            # fine) puts the glowing stripe much more prominently in frame
            # by the end, giving a real, unambiguous amount of change.
            cam_pos = (0, lerp(-4.8, -0.5, t), lerp(1.3, 0.3, t))
            target = (0, cam_pos[1] + 4.0, 0.01)
            set_camera(cam, cam_pos, target)
            headlight.hide_render = False
            aim_headlight(headlight, Vector(cam_pos) + Vector((0.05, 0.08, -0.03)), target)
        elif shot["id"] == "paint_push_in":
            cam_pos = (0, lerp(-1.6, -0.55, t), lerp(0.55, 0.22, t))
            target = (0, cam_pos[1] + 1.6, 0.005)
            set_camera(cam, cam_pos, target)
            headlight.hide_render = False
            aim_headlight(headlight, Vector(cam_pos) + Vector((0.03, 0.06, -0.01)), target)
        elif shot["id"] == "bead_macro_ray":
            # The old +/-0.02 sweep and a ray reveal that froze after t=0.6
            # left this shot's last ~7s with no real pixel change (measured
            # max_static_visual_seconds=7.0, the global max across the whole
            # video). A much wider lateral sweep plus a slow continuous
            # push-in keep real parallax moving across the bead field for
            # the full shot, not just its first third.
            # Real human_first_view feedback (road-paint-retroreflective-
            # human-review-20261107.json): the enter/bend/exit explanation
            # was lost among 260 background beads. Progressively closing the
            # distance onto the actual hero bead (not an approximate fixed
            # point) isolates it by the time the ray is fully revealed.
            distance = lerp(-0.14, -0.045, t)
            cam_pos = (lerp(-0.07, 0.07, math.sin(t * math.tau) * 0.5 + 0.5),
                       distance, lerp(0.034, 0.02, t))
            target = tuple(hb.location)
            set_camera(cam, cam_pos, target)
            headlight.hide_render = False
            aim_headlight(headlight, Vector(cam_pos) + Vector((0.01, 0.015, -0.005)), target)
            reveal = min(1.0, t / 0.6)
            for i, seg in enumerate(ray_segments):
                seg.hide_render = reveal <= 0.02
                seg.scale = (1, 1, min(1.0, max(0.02, reveal * 2 - i)))
        elif shot["id"] == "paint_dull_comparison":
            angle = lerp(-0.25, 0.25, t)
            cam_pos = (math.sin(angle) * 0.9, -0.55 + math.cos(angle) * -0.05, 0.22)
            target = (0, 1.0, 0.01)
            set_camera(cam, cam_pos, target)
            ambient.hide_render = False
            point_light(ambient, (2.4, 0.5, 1.6), target)
        elif shot["id"] == "night_wide_safety":
            cam_pos = (0, lerp(-2.6, -1.3, t), 0.58)
            target = (0, cam_pos[1] + 4.0, 0.01)
            set_camera(cam, cam_pos, target)
            headlight.hide_render = False
            aim_headlight(headlight, Vector(cam_pos) + Vector((0.05, 0.08, -0.03)), target)
        elif shot["id"] == "bead_macro_closing":
            # The +/-0.01 drift, and even a widened +/-0.06 drift with a
            # small 0.012-unit push-in, still measured as a fully static
            # 5.5s tail with no real pixel change: bead_macro_ray only
            # passed because of its bright animated ray reveal, not its
            # camera motion -- this shot has no such overlay by design
            # ("no ray overlay"), so the camera move itself has to do real
            # work. A much bigger height swoop (well above the beads down
            # to right at bead level) actually changes the viewing angle,
            # unlike a small depth nudge.
            drift = math.sin(t * math.tau * 0.5) * 0.06
            cam_pos = (drift, -0.11, lerp(0.07, 0.016, t))
            target = (0, 0.05, 0.012)
            set_camera(cam, cam_pos, target)
            headlight.hide_render = False
            aim_headlight(headlight, Vector(cam_pos) + Vector((0.01, 0.015, -0.005)), target)
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
        print(f"ROAD_PAINT_NATIVE_FRAME {frame}/{manifest['total_frames']}", flush=True)

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
    (out / "road-paint-proof.json").write_text(json.dumps(result, indent=2))
    print("ROAD_PAINT_SHARD_DONE " + json.dumps({
        "frame_count": len(checksums), "first": checksums[0]["frame"],
        "last": checksums[-1]["frame"], "preview_only": args.preview,
        "render_seconds_total": round(sum(render_seconds), 3),
    }), flush=True)


if __name__ == "__main__":
    main()
