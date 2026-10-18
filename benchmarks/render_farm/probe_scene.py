"""Deterministic, experimental road-rumble Blender render-farm probe.

A/B platform comparison only; 320x576 Cycles6 != release quality.
Each shard renders distinct frames; no static holds or upscaling.
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

TOTAL_FRAMES = 6
FRAMES_PER_SHARD = 3


def material(name, rgb, roughness=0.7):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    bsdf.inputs["Roughness"].default_value = roughness
    return m


def make_road(asphalt, slot):
    def height(x):
        for i in range(-8, 9):
            d = abs(x - i * 0.38)
            if d < 0.08:
                return -0.025
            if d < 0.11:
                return -0.025 * (0.11-d) / 0.03
        return 0.0

    cuts = {-4.5, 4.5}
    for i in range(-8, 9):
        pos = i * 0.38
        for d in (-0.111, -0.110, -0.081, -0.08, 0.0, 0.08, 0.081, 0.110, 0.111):
            cuts.add(pos+d)
    xs = sorted(x for x in cuts if -4.5 <= x <= 4.5)
    verts = [(x, y, height(x)) for x in xs for y in (-1.4, 1.4)]
    faces = [(2*i, 2*i+2, 2*i+3, 2*i+1) for i in range(len(xs)-1)]
    mesh = bpy.data.meshes.new("Genuine recessed road pockets")
    mesh.from_pydata(verts, [], faces)
    mesh.materials.append(asphalt)
    mesh.materials.append(slot)
    mesh.update()
    road = bpy.data.objects.new("Rumble profile", mesh)
    bpy.context.collection.objects.link(road)
    for n, polygon in enumerate(mesh.polygons):
        mid = (xs[n] + xs[n+1]) / 2
        polygon.material_index = int(height(mid) < -0.012)


def build_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    sc=bpy.context.scene
    sc.render.engine="CYCLES"
    sc.cycles.device="CPU"
    sc.cycles.samples=6
    sc.cycles.seed=12
    sc.cycles.use_denoising=True
    sc.render.resolution_x=320
    sc.render.resolution_y=576
    sc.render.resolution_percentage=100
    sc.render.image_settings.file_format="PNG"
    sc.render.image_settings.color_mode="RGB"
    sc.render.threads_mode="FIXED"
    sc.render.threads=2
    sc.render.fps=30
    asphalt=material("Dry pavement", (.115, .117, .120), 0.92)
    slot=material("Recess interior", (.027, .029, .032), 0.9)
    tire=material("Dark rubber", (.015, .016, .018), 0.95)
    metal=material("Hub metal", (.47, .53, .56), .27)
    make_road(asphalt,slot)
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=.52, depth=.30,
                                         rotation=(math.pi/2,0,0))
    wheel=bpy.context.object
    wheel.name="3D rolling tyre"
    wheel.data.materials.append(tire)
    bpy.ops.mesh.primitive_cylinder_add(vertices=36,radius=.34,depth=.035,
                                       rotation=(math.pi/2,0,0))
    hub=bpy.context.object
    hub.name="3D machined rim"
    hub.data.materials.append(metal)
    hub.parent=wheel
    hub.location=(0,0,-.16)
    bpy.ops.object.camera_add(location=(1.85,-4.4,2.8))
    cam=bpy.context.object
    cam.rotation_euler=(Vector((0,0,.13))-cam.location).to_track_quat("-Z","Y").to_euler()
    cam.data.type="ORTHO"
    cam.data.ortho_scale=4.9
    sc.camera=cam
    bpy.ops.object.light_add(type="AREA",location=(-2.1,-3.2,5.8))
    bpy.context.object.data.energy=850
    bpy.context.object.data.size=4.2
    sc.view_settings.view_transform="AgX"
    return sc,wheel


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--shard",type=int,choices=(0,1),required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
    scene,wheel=build_scene()
    args.out.mkdir(parents=True,exist_ok=True)
    records=[]
    for frame_index in range(args.shard*FRAMES_PER_SHARD,
                             (args.shard+1)*FRAMES_PER_SHARD):
        x=-1.0+2.0*frame_index/(TOTAL_FRAMES-1)
        wheel.location=(x,0,.52+.010*math.sin(frame_index*1.7))
        wheel.rotation_euler[1]=x/.52
        scene.frame_set(frame_index+1)
        output=args.out/f"frame_{frame_index+1:04d}.png"
        scene.render.filepath=str(output)
        started=time.perf_counter()
        bpy.ops.render.render(write_still=True)
        seconds=time.perf_counter()-started
        digest=hashlib.sha256(output.read_bytes()).hexdigest()
        records.append({"frame":frame_index+1,"sha256":digest,
                        "render_seconds":round(seconds,3),
                        "bytes":output.stat().st_size})
        print("RENDERED_NATIVE_PROBE",frame_index+1,digest,flush=True)
    assert len(records)==FRAMES_PER_SHARD
    assert len({x["sha256"] for x in records})==FRAMES_PER_SHARD
    result={"schema_version":1,"shard":args.shard,
            "renderer_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "scene":"road-rumble-procedural-probe","resolution":[320,576],
            "samples":6,"fps":30,"blender_version":bpy.app.version_string,
            "native_unique_frames":True,"upload_ready":False,"frames":records}
    (args.out/"proof.json").write_text(json.dumps(result,indent=2),encoding="utf8")
    print("PROOF_DONE",json.dumps(result,sort_keys=True),flush=True)


if __name__=="__main__":
    main()
