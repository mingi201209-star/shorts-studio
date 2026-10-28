"""Blender-only owned procedural wheel and native scene builder."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path


def projected_geometry_bounds(meshes, project):
    """Measure actual projected geometry and its lowest world-space point."""
    world_points = [obj.matrix_world @ vertex.co for obj in meshes for vertex in obj.data.vertices]
    points = [project(point) for point in world_points]
    if not points:
        raise ValueError("empty rendered geometry")
    return (
        [
            min(point.x for point in points),
            min(point.y for point in points),
            max(point.x for point in points),
            max(point.y for point in points),
        ],
        min(point.z for point in points),
        min(point[2] for point in world_points),
    )


def main():
    import bpy
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector

    parser = argparse.ArgumentParser()
    parser.add_argument("request", type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    request = json.loads(args.request.read_text())
    output = Path(request["output"])
    output.mkdir(parents=True, exist_ok=True)
    if bpy.app.version_string != "5.0.1":
        raise RuntimeError("proof renderer requires Blender 5.0.1")
    radius = 0.95

    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def material(name, color, metallic=0.0):
        value = bpy.data.materials.new(name)
        value.diffuse_color = (*color, 1)
        value.use_nodes = True
        principled = value.node_tree.nodes.get("Principled BSDF")
        principled.inputs["Base Color"].default_value = (*color, 1)
        principled.inputs["Metallic"].default_value = metallic
        principled.inputs["Roughness"].default_value = 0.38 if metallic else 0.7
        return value

    def aim(obj, point):
        obj.rotation_euler = (Vector(point) - obj.location).to_track_quat("-Z", "Y").to_euler()

    def stage():
        scene = bpy.context.scene
        scene.render.engine = "CYCLES"
        scene.cycles.samples = 32
        scene.cycles.use_denoising = True
        scene.cycles.seed = 42
        scene.cycles.device = "CPU"
        scene.render.resolution_x = 1080
        scene.render.resolution_y = 1920
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGBA"
        scene.render.film_transparent = False
        scene.render.threads_mode = "FIXED"
        scene.render.threads = 2
        scene.render.fps = 30
        scene.view_settings.view_transform = "AgX"
        scene.world.color = (0.15, 0.15, 0.15)
        bpy.ops.object.camera_add(location=(0, -10, 3.2))
        camera = bpy.context.object
        camera.name = "FixedProofCamera"
        aim(camera, (0, 0, 0.85))
        camera.data.type = "ORTHO"
        camera.data.ortho_scale = 5.2
        scene.camera = camera
        for name, location, energy, size in [
            ("Key", (-3, -4, 6), 900, 5),
            ("Rim", (3, 2, 4), 1100, 3),
        ]:
            bpy.ops.object.light_add(type="AREA", location=location)
            light = bpy.context.object
            light.name = name
            light.data.energy = energy
            light.data.shape = "DISK"
            light.data.size = size
            aim(light, (0, 0, 1))
        return scene

    if request["action"] == "asset":
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)
        rubber = material("OwnedRubber", (0.025, 0.035, 0.055))
        metal = material("OwnedAlloy", (0.25, 0.35, 0.48), 0.75)
        orange = material("OwnedMotionMarker", (1.0, 0.26, 0.035))
        bpy.ops.object.empty_add(type="PLAIN_AXES")
        rig = bpy.context.object
        rig.name = "WheelRig"
        rig["radius_m"] = radius

        def parent(obj, name, mat):
            obj.name = name
            obj.data.materials.append(mat)
            obj.parent = rig
            for polygon in obj.data.polygons:
                polygon.use_smooth = True
            return obj

        bpy.ops.mesh.primitive_torus_add(
            major_radius=0.75,
            minor_radius=0.2,
            major_segments=96,
            minor_segments=20,
            rotation=(math.pi / 2, 0, 0),
        )
        parent(bpy.context.object, "OwnedTire", rubber)
        bpy.ops.mesh.primitive_torus_add(
            major_radius=0.59,
            minor_radius=0.06,
            major_segments=96,
            minor_segments=12,
            rotation=(math.pi / 2, 0, 0),
        )
        parent(bpy.context.object, "OwnedRim", metal)
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=48, radius=0.16, depth=0.46, rotation=(math.pi / 2, 0, 0)
        )
        parent(bpy.context.object, "OwnedHub", metal)
        for number in range(7):
            angle = number * math.tau / 7
            bpy.ops.mesh.primitive_cube_add(
                size=1, location=(0.37 * math.cos(angle), -0.04, 0.37 * math.sin(angle))
            )
            obj = bpy.context.object
            obj.dimensions = (0.52, 0.14, 0.09)
            obj.rotation_euler[1] = -angle
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            parent(obj, f"OwnedSpoke{number}", orange if number == 0 else metal)
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=16, ring_count=8, radius=0.065, location=(0.86, -0.2, 0)
        )
        parent(bpy.context.object, "MotionMarker", orange)
        rig.location.z = radius
        scene = stage()
        scene.render.film_transparent = True
        scene.render.filepath = str(output / "frame.png")
        bpy.ops.render.render(write_still=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(output / "asset.blend"))
        source = Path(__file__).read_bytes()
        (output / "builder_source.py").write_bytes(source)
        source_hash = sha(output / "builder_source.py")
        provenance = {
            "license": "OWNED",
            "creator": "Shorts Studio procedural builder",
            "builder_source_sha256": source_hash,
            "external_assets": [],
            "blender_version": bpy.app.version_string,
        }
        (output / "provenance.json").write_text(json.dumps(provenance, indent=2))
        metadata = {
            "asset": "wheel",
            "view": "side",
            "source_sha256": source_hash,
            "object_names": [o.name for o in rig.children],
            "mesh_parts": len(rig.children),
            "renderer": "CYCLES",
            "samples": 32,
            "resolution": [1080, 1920],
            "transparent": True,
            "fixed_camera": True,
            "motion": "static_object_view",
            "image_sha256": sha(output / "frame.png"),
            "blend_sha256": sha(output / "asset.blend"),
            "editorial_approved": False,
            "interaction_physics_validated": False,
        }
        (output / "asset.json").write_text(json.dumps(metadata, indent=2))
        names = ("asset.blend", "asset.json", "frame.png", "builder_source.py", "provenance.json")
        outputs = {
            name: {"bytes": (output / name).stat().st_size, "sha256": sha(output / name)}
            for name in names
        }
        (output / "manifest.json").write_text(json.dumps({"outputs": outputs}, indent=2))
        return

    bpy.ops.wm.open_mainfile(filepath=request["blend_path"], load_ui=False, use_scripts=False)
    scene = bpy.context.scene
    scene.render.film_transparent = False
    rig = bpy.data.objects["WheelRig"]
    radius = float(rig["radius_m"])
    floor_mat = material("ProofRoad", (0.045, 0.075, 0.11))
    stripe_mat = material("ProofRoadMark", (0.44, 0.53, 0.61))
    bpy.ops.mesh.primitive_plane_add(size=200)
    floor = bpy.context.object
    floor.name = "ProofGround"
    floor.data.materials.append(floor_mat)
    for number in range(-12, 13):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(number * 0.4, 0, -0.009))
        obj = bpy.context.object
        obj.name = f"GroundReference{number}"
        obj.dimensions = (0.015, 4, 0.02)
        obj.data.materials.append(stripe_mat)
    frames = request["frames"]
    speed = 0.6 * 30 / max(frames - 1, 1)
    start = -0.3
    scene.frame_start = 1
    scene.frame_end = frames
    meshes = [o for o in rig.children if o.type == "MESH"]
    marker = bpy.data.objects["MotionMarker"]
    samples = []
    started = time.monotonic()
    for frame in range(1, frames + 1):
        scene.frame_set(frame)
        elapsed = (frame - 1) / 30
        rig.location = (start + speed * elapsed, 0, radius)
        rig.rotation_euler = (
            0,
            speed * elapsed / radius if request["motion"] == "rolling" else 0,
            0,
        )
        rig.keyframe_insert("location", frame=frame)
        rig.keyframe_insert("rotation_euler", frame=frame)
        bpy.context.view_layer.update()
        bbox, near_depth, lowest_world_z = projected_geometry_bounds(
            meshes, lambda point: world_to_camera_view(scene, scene.camera, point)
        )
        centre = rig.matrix_world.translation
        point = marker.matrix_world.translation
        samples.append(
            {
                "frame": frame,
                "x": centre.x,
                "z": centre.z,
                "angle": rig.rotation_euler.y,
                "marker_x": point.x,
                "marker_z": point.z,
                "bbox": bbox,
                "near_depth": near_depth,
                "lowest_world_z": lowest_world_z,
                "camera": [value for row in scene.camera.matrix_world for value in row],
            }
        )
        scene.render.filepath = str(output / f"frame_{frame:04}.png")
        bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "scene.blend"))
    (output / "motion.json").write_text(
        json.dumps(
            {
                "motion": request["motion"],
                "renderer": "CYCLES",
                "simulation": "kinematic",
                "geometry_bounds": "mesh_vertices",
                "radius": radius,
                "speed": speed,
                "start_x": start,
                "fps": 30,
                "frames": frames,
                "width": 1080,
                "height": 1920,
                "samples": 32,
                "seed": 42,
                "blender_version": bpy.app.version_string,
                "render_seconds": time.monotonic() - started,
                "frames_data": samples,
                "physics_validated": False,
                "production_approved": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
