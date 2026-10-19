"""Opt-in visual pilot: reuse a previously audited CC0 sedan in a rumble-strip scene.

Requires a hash-pinned source Blender scene. It is not production-approved.
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
from mathutils import Matrix, Vector

PINNED_SCENE_SHA256 = "a82e05825f907cc99678ab12855527552e34323b31ae801625af4a0f563ed877"


def arguments():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--frames", type=int, default=4)
    p.add_argument("--preview", action="store_true")
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--start", type=int)
    p.add_argument("--end", type=int)
    p.add_argument("--frame-list", help="Sparse visual QA only: comma-separated absolute 30fps frame indices")

    p.add_argument("--view", choices=("hero", "contact"), default="hero")
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return p.parse_args(argv)


def stable_source(path):
    if not path.is_file():
        raise FileNotFoundError(path)
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    if h != PINNED_SCENE_SHA256:
        raise ValueError(f"pinned car scene SHA mismatch: {h}")
    return h


def grey_mat(name, col, rough=0.9):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*col, 1)
    m.use_nodes = True
    shader = m.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*col, 1)
    shader.inputs["Roughness"].default_value = rough
    return m


def cube(name, center, size, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    ob = bpy.context.object
    ob.name = name
    ob.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    ob.data.materials.append(mat)
    return ob


def bump_road(mat):
    s = mat.node_tree.nodes.get("Principled BSDF")
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 120
    noise.inputs["Detail"].default_value = 3
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = .11
    bump.inputs["Distance"].default_value = .006
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], s.inputs["Normal"])


def railbed_road(asphalt, groove, depth=.016):
    # Cut an actual mesh profile. Grooves lie below grade, not above it.
    def top(x):
        for i in range(-14, 15):
            p = abs(x - i*.34)
            if p < .085:
                return -depth
            if p < .115:
                return -depth * (.115-p)/.03
        return 0.
    cuts = {-7.0, 7.0}
    for i in range(-14,15):
        c = i*.34
        for v in (-.116,-.115,-.086,-.085,-.04,0,.04,.085,.086,.115,.116):
            cuts.add(c+v)
    xs = sorted(x for x in cuts if -7 <= x <= 7)
    # FHWA-style longitudinal shoulder rumble: the driver-side lanes stay
    # smooth, while ONLY the near-side tyre crosses a narrow milled band.
    # A full-lane dark stripe pattern is NOT a rumble strip.
    y_positions=(-3.2,-1.35,-1.3499,-.7001,-.70,2.4)
    cross_count=len(y_positions)
    vertices=[(x,y,top(x) if -1.3499<=y<=-.7001 else 0.0)
              for x in xs for y in y_positions]
    faces=[]
    for k in range(len(xs)-1):
        for j in range(cross_count-1):
            faces.append((cross_count*k+j,cross_count*(k+1)+j,
                          cross_count*(k+1)+j+1,cross_count*k+j+1))
    mesh=bpy.data.meshes.new("Narrow actual milling grooves only under shoulder tyre")
    mesh.from_pydata(vertices,[],faces)
    mesh.materials.append(asphalt)
    mesh.materials.append(groove)
    mesh.update()
    ob=bpy.data.objects.new("Milled shoulder band; traffic lane stays flat",mesh)
    bpy.context.collection.objects.link(ob)
    for k in range(len(xs)-1):
        mid=(xs[k]+xs[k+1])/2
        for j in range(cross_count-1):
            poly=mesh.polygons[k*(cross_count-1)+j]
            poly.material_index=int(j==2 and top(mid)<-depth*.6)
    return ob


def main():
    args = arguments()
    # Blender's Python environment need not contain the standalone Python app's
    # optional runtime dependencies. Import ONLY the pure-stdlib timeline.
    import importlib.util
    spec=importlib.util.spec_from_file_location(
        "approved_rumble_episode2",
        Path(__file__).resolve().parents[2]/"shorts_studio/factory/rumble_episode2.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load approved episode2 timeline")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    episode=module.load_episode(args.manifest)
    if args.frame_list:
        if args.start is not None or args.end is not None:
            raise ValueError("cannot mix sparse preview list with contiguous production shard")
        absolute_frames=[int(v.strip()) for v in args.frame_list.split(",")]
        if (not args.preview or not 1 <= len(absolute_frames) <= 12
                or sorted(set(absolute_frames)) != absolute_frames):
            raise ValueError("sparse frames are preview only, sorted and unique, max 12")
        for frame in absolute_frames:
            module.shot_for_frame(episode,frame)
    else:
        if args.start is None or args.end is None:
            raise ValueError("production requires explicit absolute --start and --end")
        absolute_frames=module.render_slice(args.start,args.end)

    source_sha = stable_source(args.source)
    bpy.ops.wm.open_mainfile(filepath=str(args.source))
    scene = bpy.context.scene
    car = bpy.data.objects.get("CC0 detailed sedan animated as a rigid car")
    if not car:
        raise ValueError("source car hierarchy unavailable")
    children = {car, *car.children_recursive}
    retained = {o for o in bpy.data.objects if o.type == "LIGHT"}
    for ob in list(bpy.data.objects):
        if ob not in children and ob not in retained:
            bpy.data.objects.remove(ob, do_unlink=True)

    scene.frame_set(1)
    car.animation_data_clear()
    # Original detailed CC0 car is kept intact; no parts/crop cheats.
    if len([o for o in car.children_recursive if o.type=="MESH"]) < 65:
        raise ValueError("incomplete vehicle part set")
    car.rotation_euler = (0,0,math.pi/2)
    car.scale = (.85,.85,.85)
    car.location = (0,-.3,0)
    for ob in car.children_recursive:
        if ob.animation_data:
            # Wheel motion must be explicitly authored later; avoid inheriting
            # out-of-scope crash animation from a different topic.
            ob.animation_data_clear()

    # Reuse all original CC0 body meshes, but give their existing blue material
    # readable sapphire paint. Tyres/glass/chrome stay on their source materials.
    body_paint=bpy.data.materials.get("blue")
    if body_paint is None:
        raise ValueError("missing original CC0 blue body material")
    body_paint.use_nodes=True
    paint_shader=body_paint.node_tree.nodes.get("Principled BSDF")
    if paint_shader is None:
        raise ValueError("source body material has no Principled BSDF")
    paint_color=(.018,.16,.51,1)
    paint_shader.inputs["Base Color"].default_value=paint_color
    paint_shader.inputs["Metallic"].default_value=.25
    paint_shader.inputs["Roughness"].default_value=.32
    body_paint.diffuse_color=paint_color

    # Group every tyre, rim and wheel spoke beneath its true local wheel hub.
    # The entire wheel assembly must rotate; the car body must NOT rotate.
    wheels = [o for o in car.children_recursive
              if o.name in ("Front_tire", "Front_tire.001", "Rear_tire", "Rear_tire.001")]
    if len(wheels) != 4:
        raise ValueError("four source tires required")
    centers, radii = {}, {}
    for o in wheels:
        verts=[o.matrix_local@Vector(v) for v in o.bound_box]
        center=sum(verts,Vector())/len(verts)
        centers[o.name]=center
        radii[o.name]=(max(v.z for v in verts)-min(v.z for v in verts))/2
        if not .24 < radii[o.name] < .42:
            raise ValueError(f"impossible wheel radius: {o.name}")
    groups={n:[] for n in centers}
    candidates=[o for o in car.children_recursive if o.type=="MESH"
                and o.name.startswith(("Front_","Rear_"))]
    for ob in candidates:
        verts=[ob.matrix_local@Vector(v) for v in ob.bound_box]
        center=sum(verts,Vector())/len(verts)
        name=min(centers,key=lambda key:(center-centers[key]).length)
        if (center-centers[name]).length > .42:
            raise ValueError(f"wheel component detached: {ob.name}")
        groups[name].append(ob)
    pivots=[]
    for idx,name in enumerate(centers):
        pivot=bpy.data.objects.new(f"True rolling wheel pivot {idx}",None)
        bpy.context.collection.objects.link(pivot)
        pivot.parent=car
        pivot.location=centers[name]
        pivot.matrix_parent_inverse.identity()
        for ob in groups[name]:
            old=ob.matrix_local.copy()
            ob.parent=pivot
            ob.matrix_parent_inverse.identity()
            ob.matrix_basis=Matrix.Translation(-centers[name])@old
        tyre=bpy.data.objects[name]
        if tyre.parent != pivot or len(groups[name]) < 5:
            raise ValueError("tyre component pivot incomplete")
        pivots.append((pivot,radii[name]))
    if len(pivots)!=4:
        raise ValueError("lost wheel pivots")


    asphalt = grey_mat("dark real-grain asphalt", (.09,.091,.087))
    bump_road(asphalt)
    groove = grey_mat("recessed dark groove", (.060,.062,.065))
    background = grey_mat("shoulder gravel", (.19,.16,.12))
    yellow = grey_mat("road shoulder stripe", (.73,.68,.49))
    railbed_road(asphalt,groove)
    # Keep the underlying slab BELOW the deepest cut, never occluding the groove.
    cube("road substrate", (0,0,-.27), (14,7,.44), asphalt)
    cube("lane edge marking",(0,-.53,.007),(14,.060,.006),yellow)
    cube("dry roadside earth",(0,3.18,-.12),(14,2.5,.19),background)

    bpy.ops.object.camera_add(location=(2.1,-8.4,5.9))
    cam=bpy.context.object
    cam.rotation_euler=(Vector((0,-.25,.53))-cam.location).to_track_quat("-Z","Y").to_euler()
    cam.data.type="ORTHO"
    cam.data.ortho_scale=9.2
    if args.view == "contact":
        # Main mechanism insert: wheel, actual pocket and visible body panel.
        tyres=[o for o in car.children_recursive if o.name in ("Front_tire","Front_tire.001")]
        if len(tyres) != 2:
            raise ValueError("missing CC0 front tire pair")
        bpy.context.view_layer.update()
        o=tyres[0]
        wheel_points=[o.matrix_world @ Vector(v) for v in o.bound_box]
        front_center=sum(wheel_points,Vector())/len(wheel_points)
        cam.location=front_center + Vector((1.7,-3.2,2.2))
        cam.rotation_euler=(front_center+Vector((0,0,-.06))-cam.location).to_track_quat("-Z","Y").to_euler()
        cam.data.ortho_scale=2.85
    scene.camera=cam
    if scene.world:
        scene.world.color=(.018,.018,.019)
        if scene.world.use_nodes:
            bg=scene.world.node_tree.nodes.get("Background")
            if bg: bg.inputs["Color"].default_value=(.028,.030,.032,1)
    bpy.ops.object.light_add(type="AREA",location=(-4,-5,8))
    ob=bpy.context.object
    ob.data.energy=1650
    ob.data.shape="DISK"
    ob.data.size=6
    bpy.ops.object.light_add(type="AREA",location=(3,2,6))
    bpy.context.object.data.energy=950
    bpy.context.object.data.size=5

    scene.render.engine="CYCLES"
    scene.cycles.device="CPU"
    scene.cycles.samples=7 if args.preview else 32
    scene.cycles.use_denoising=True
    scene.render.threads_mode="FIXED"
    scene.render.threads=4
    scene.render.resolution_x=450 if args.preview else 1080
    scene.render.resolution_y=800 if args.preview else 1920
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format="PNG"
    scene.render.image_settings.color_mode="RGB"
    scene.view_settings.view_transform="AgX"

    out=args.out
    out.mkdir(parents=True,exist_ok=True)
    all_times=[]
    checksums=[]
    camera_proofs={}
    previous_shot=None
    for i, absolute_frame in enumerate(absolute_frames):
        # Over the longer real pilot, one tire traverses several physical grooves.
        # Small displacement only, not a realistic tire/suspension solver.
        shot=module.shot_for_frame(episode,absolute_frame)
        x=module.travel_x(absolute_frame)
        # Motion is a global deterministic x coordinate, not a per-shard reset.
        car.location=(x,-.30+module.lane_return_offset(absolute_frame),.03+module.rumble_displacement(absolute_frame))
        car.rotation_euler[2]=math.pi/2+module.lane_return_heading(absolute_frame)
        for pivot,radius in pivots:
            pivot.rotation_euler[0]=(x-module.travel_x(1))/(.85*radius)
        scene.frame_set(absolute_frame)
        bpy.context.view_layer.update()
        if shot["id"]!=previous_shot:
            # Camera is fitted to a shot's *global* midpoint, regardless of
            # whether this worker renders its first/middle/last 30 frames.
            middle=(shot["start"]+shot["end"])//2
            centre_x=module.travel_x(middle)
            car.location=(centre_x,-.30+module.lane_return_offset(middle),.03)
            car.rotation_euler[2]=math.pi/2+module.lane_return_heading(middle)
            bpy.context.view_layer.update()
            front=bpy.data.objects["Front_tire"]
            rear=bpy.data.objects["Rear_tire"]
            obj=front if shot["id"]!="rumble_mechanism" else rear
            points=[obj.matrix_world@Vector(v) for v in obj.bound_box]
            wheel=sum(points,Vector())/len(points)
            if shot["id"]=="hook_warning":
                # Opening shows physical impact, not another distant moving car.
                target=wheel+Vector((0,0,-.11))
                offset=Vector((1.55,-3.2,2.2))
                scale=3.95
            elif shot["id"]=="road_cut":
                # From above, real grooves contrast with the adjacent flat lane.
                target=wheel+Vector((0,0,-.18))
                offset=Vector((.1,-3.4,4.15))
                scale=4.15
            elif shot["id"]=="tire_contact":
                # Low profile exposes tire and recessed contact change.
                target=wheel+Vector((0,0,-.08))
                offset=Vector((2.5,-2.1,1.4))
                scale=3.95
            elif shot["id"]=="rumble_mechanism":
                target=wheel+Vector((0,0,-.13))
                offset=Vector((-1.2,-3.4,1.9))
                scale=4.15
            elif shot["id"]=="shoulder_location":
                target=Vector((centre_x,-.1,.45))
                offset=Vector((.7,-5.3,8.2))
                scale=11.0
            else:
                target=Vector((centre_x,-.25,.55))
                offset=Vector((4.0,-7.7,5.4))
                scale=11.6
            cam.location=target+offset
            cam.rotation_euler=(target-cam.location).to_track_quat("-Z","Y").to_euler()
            cam.data.ortho_scale=scale
            bpy.context.view_layer.update()
            camera_proofs[shot["id"]]=[
                [round(v,6) for v in cam.location],
                [round(v,6) for v in cam.rotation_euler],
                round(cam.data.ortho_scale,6),
            ]
            previous_shot=shot["id"]
            car.location=(x,-.30+module.lane_return_offset(absolute_frame),.03+module.rumble_displacement(absolute_frame))
            car.rotation_euler[2]=math.pi/2+module.lane_return_heading(absolute_frame)
            bpy.context.view_layer.update()
        frame_path=out/f"frame_{absolute_frame:04d}.png"
        scene.render.filepath=str(frame_path)
        start=time.perf_counter()
        bpy.ops.render.render(write_still=True)
        elapsed=round(time.perf_counter()-start,3)
        sha=hashlib.sha256(frame_path.read_bytes()).hexdigest()
        checksums.append({"frame":absolute_frame,"shot_id":shot["id"],
                          "absolute_x_m":round(x,7),"sha256":sha,
                          "render_seconds":elapsed})
        all_times.append(elapsed)
        print(f"RUMBLE_EPISODE2_NATIVE_FRAME {absolute_frame}/900",flush=True)
    if len({x["sha256"] for x in checksums})!=len(checksums):
        raise ValueError("duplicate original Blender frames are forbidden")
    result={"episode_id":episode["episode_id"],"source_sha256":source_sha,
       "renderer_source_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
       "renderer":"CYCLES",
       "preview_only":args.preview,"frames":len(absolute_frames),
       "first_frame":absolute_frames[0],"last_frame":absolute_frames[-1],
       "frame_numbers":absolute_frames,"fps":30,
       "resolution":[scene.render.resolution_x,scene.render.resolution_y],
       "cycles_samples":scene.cycles.samples,"render_seconds":all_times,
       "camera_by_shot":camera_proofs,"original_frame_records":checksums,
       "car_mesh_parts":len([o for o in car.children_recursive if o.type=="MESH"]),
       "rotating_wheel_pivots":len(pivots),
       "physically_calibrated":False,"upload_ready":False}
    if not args.preview and (
        result["resolution"]!=episode["resolution"]
        or result["cycles_samples"]!=episode["cycles_samples"]
    ):
        raise ValueError("production frame quality cannot differ from approved manifest")
    (out/"episode-proof.json").write_text(json.dumps(result,indent=2))
    print("RUMBLE_EPISODE2_SHARD_DONE "+json.dumps({
        "frame_count":len(checksums),"first":checksums[0]["frame"],
        "last":checksums[-1]["frame"],"preview_only":args.preview,
        "render_seconds_total":round(sum(all_times),3),
        "upload_ready":False,
    }),flush=True)

if __name__=="__main__":
    main()
