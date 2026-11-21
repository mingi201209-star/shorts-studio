"""EP.13 guardrail end terminal: 100 % 3D renderer (Blender, Cycles CPU). Golden-hour highway shoulder. Terminal site: a W-beam
guardrail on wooden posts with blockouts, ending in a steel head (yellow and black object marker on its face). The CC0 sedan (painted
red) hits the head at 60 mph; the head is pushed down the rail, the rail is consumed into it and comes out of the side slot as a flat
steel ribbon that coils away from the car (geometry from terminal_motion), sparks fly from the slot and the throat, the breakaway posts
are knocked over. Blunt-end site (far down the road): the same rail with a plain end; the car runs onto it and the rail goes into the
car (x-ray: the body turns see-through and the cabin set shows where the rail ends). Everything that moves comes from terminal_motion.
No text anywhere in the picture."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from benchmarks.belt_limiter import render_belt_3d as rb  # noqa: E402
from benchmarks.guardrail_end import terminal_motion as tm  # noqa: E402
from benchmarks.guardrail_end import terminal_timeline as tl  # noqa: E402
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402

material, cube = base.material, base.cube
FRAME = (1080, 1920)
RAIL_LEN = 46.0
PAINT = (1.75, 0.30, 0.24)          # body paint multiplier on the CC0 car's light paint: a red car reads well against grass and sky


def arguments():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--res-scale", type=float, default=0.5)
    p.add_argument("--samples", type=int, default=16)
    p.add_argument("--frames", default="0-0")
    p.add_argument("--film", action="store_true")
    p.add_argument("--list", default="")                     # comma-separated frames (storyboard checks) instead of a range
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return p.parse_args(argv)


def galvanised(name="Galvanised steel", tint=(0.62, 0.64, 0.66)):
    m = material(name, tint, metal=0.85, rough=0.32)
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 38.0
    ramp = nt.nodes.new("ShaderNodeMapRange")
    ramp.inputs["To Min"].default_value = 0.22
    ramp.inputs["To Max"].default_value = 0.48
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Value"])
    nt.links.new(ramp.outputs["Result"], bsdf.inputs["Roughness"])          # spangled zinc: patchy roughness
    return m


def marker_material():
    """Yellow and black diagonal stripes of a terminal's object marker (paint, not text)."""
    m = material("Object marker", (0.95, 0.72, 0.04), rough=0.35)
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type, wave.bands_direction = "BANDS", "DIAGONAL"
    wave.inputs["Scale"].default_value = 3.2
    wave.inputs["Distortion"].default_value = 0.0
    nt.links.new(tc.outputs["Object"], wave.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    ramp.color_ramp.elements[0].color = (0.95, 0.72, 0.04, 1)
    ramp.color_ramp.elements[1].position = 0.5
    ramp.color_ramp.elements[1].color = (0.02, 0.02, 0.02, 1)
    nt.links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    return m


def mesh_object(name, verts, faces, mat, parent=None, smooth=True, thickness=0.0):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.update()
    if smooth:
        me.polygons.foreach_set("use_smooth", [True] * len(faces))
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    me.materials.append(mat)
    if parent is not None:
        ob.parent = parent
    if thickness:
        mod = ob.modifiers.new("Thickness", "SOLIDIFY")
        mod.thickness, mod.offset = thickness, 0.0
    return ob


def beam_mesh(y0, length, step=0.1, nv=13):
    """W-beam from y0 to y0 + length along +y (world), corrugations toward traffic (-x)."""
    v = np.linspace(-0.5, 0.5, nv) * tm.BEAM_H
    rows = int(round(length / step)) + 1
    verts = []
    for i in range(rows):
        y = y0 + i * step
        for vv, d in zip(v, tm.w_profile(v)):
            verts.append((tm.RAIL_X - d, y, tm.RAIL_Z + vv))
    faces = [(i * nv + j, i * nv + j + 1, (i + 1) * nv + j + 1, (i + 1) * nv + j) for i in range(rows - 1) for j in range(nv - 1)]
    return np.array(verts), faces


class RailRun:
    """A guardrail run starting at y0: beam (its start can be pulled forward per frame, the consumed part collapses into the throat), posts
    with blockouts (the first few can be knocked over), end cap for the blunt end."""

    def __init__(self, name, y0, steel, wood, n_posts, breakable, first_post=0.30):
        verts, faces = beam_mesh(y0, RAIL_LEN)
        self.base = verts
        self.y0 = y0
        self.beam = mesh_object(f"{name} beam", verts, faces, steel, thickness=0.004)
        self.posts = []
        for k in range(n_posts):
            py = y0 + first_post + k * tm.POST_SPACING
            piv = bpy.data.objects.new(f"{name} post pivot {k}", None)
            bpy.context.collection.objects.link(piv)
            piv.location = (tm.POST_X + 0.10, py, 0.0)
            post = cube(f"{name} post {k}", (tm.POST_X, py, 0.53), (0.15, 0.20, 1.06), wood)
            block = cube(f"{name} blockout {k}", (0.085, py, tm.RAIL_Z), (0.17, 0.15, 0.36), wood)
            for ob in (post, block):
                mw = ob.matrix_world.copy()
                ob.parent = piv
                ob.matrix_world = mw
            self.posts.append(piv)
        self.breakable = breakable

    def highlight(self, mat):
        self.beam.data.materials[0] = mat

    def set_start(self, y_start):
        v = self.base.copy()
        v[:, 1] = np.maximum(v[:, 1], y_start)
        self.beam.data.vertices.foreach_set("co", v.ravel())
        self.beam.data.update()

    def set_posts(self, t):
        for k, piv in enumerate(self.posts):
            ang, kick = tm.post_fall(k, t) if (self.breakable and k < tm.N_POSTS) else (0.0, 0.0)
            piv.rotation_euler = (0.0, ang, 0.0)
            piv.location = (tm.POST_X + 0.10 + kick, piv.location.y, 0.0)


class Head:
    """Terminal head (frame origin: front face centre at rail height): box with a side slot for the ribbon, feeder chute along the rail,
    object marker on the face. The ribbon mesh is rebuilt per frame in this frame."""

    def __init__(self, steel, ribbon_mat):
        self.root = bpy.data.objects.new("Head", None)
        bpy.context.collection.objects.link(self.root)
        marker = marker_material()
        dark = material("Head steel dark", (0.22, 0.23, 0.24), metal=0.8, rough=0.4)
        L, hw, hh = tm.HEAD_L, 0.20, 0.31
        p = self.root

        def box(name, c, d, mat):
            ob = cube(name, c, d, mat)
            ob.parent = p
            return ob

        self.face = box("Head face", (0.0, -0.012, 0.0), (0.50, 0.024, 0.70), marker)
        self.open_side = []
        self.top = box("Head top", (0.0, L / 2, hh), (2 * hw + 0.02, L, 0.02), steel)
        self.bottom = box("Head bottom", (0.0, L / 2, -hh), (2 * hw + 0.02, L, 0.02), steel)
        box("Head traffic wall", (-hw, L / 2, 0.0), (0.02, L, 2 * hh), steel)
        self.open_side.append(box("Head slot wall rear", (hw, 0.41, 0.0), (0.02, 0.42, 2 * hh), steel))      # side wall behind the slot (slot: y 0.04 .. 0.20)
        self.open_side.append(box("Head slot wall front", (hw, 0.02, 0.0), (0.02, 0.04, 2 * hh), steel))
        for sz in (-1, 1):
            self.open_side.append(box(f"Head slot lip {sz}", (hw, 0.12, sz * 0.275), (0.02, 0.16, 0.07), steel))
            box(f"Feeder channel {sz}", (tm.RAIL_X - tm.HEAD_X - 0.02, L + 0.55, sz * 0.19), (0.10, 1.1, 0.03), dark)
        box("Feeder strap", (tm.RAIL_X - tm.HEAD_X + 0.05, L + 1.08, 0.0), (0.03, 0.04, 0.40), dark)
        self.ribbon_mat = ribbon_mat
        self.ribbon = None

    def set(self, y_front, head_d, cutaway=False):
        self.root.location = (tm.HEAD_X, y_front, tm.RAIL_Z)
        self.top.hide_render = cutaway
        for ob in self.open_side:
            ob.hide_render = cutaway
        verts, faces = tm.ribbon_mesh(head_d)
        old = self.ribbon
        self.ribbon = mesh_object("Ribbon", verts, faces, self.ribbon_mat, parent=self.root, thickness=0.004)
        if old is not None:
            me = old.data
            bpy.data.objects.remove(old)
            bpy.data.meshes.remove(me)


class Sparks:
    """Pool of small, very bright streaks placed from terminal_motion.spark_points each frame (deterministic)."""

    def __init__(self, n=220):
        hot = material("Spark", (1.0, 0.55, 0.12), rough=0.5, emission=0.0)
        s = hot.node_tree.nodes.get("Principled BSDF")
        s.inputs["Emission Color"].default_value = (1.0, 0.36, 0.05, 1)
        s.inputs["Emission Strength"].default_value = 22.0
        self.obs = []
        for k in range(n):
            ob = cube(f"Spark {k}", (0, 0, -10), (1.0, 1.0, 1.0), hot)
            ob.hide_render = True
            self.obs.append(ob)

    def update(self, pts, time_scale):
        stretch = min(0.03, 0.012 / max(0.05, time_scale) * 0.1)           # shutter streak: longer when the clock runs nearer real time
        for k, ob in enumerate(self.obs):
            if k >= len(pts):
                ob.hide_render = True
                continue
            pos, vel = pts[k]
            sp = float(np.linalg.norm(vel)) + 1e-6
            ob.hide_render = False
            ob.location = tuple(pos)
            ob.rotation_mode = "QUATERNION"
            ob.rotation_quaternion = Vector(tuple(vel / sp)).to_track_quat("Z", "Y")
            ob.scale = (0.006, 0.006, max(0.012, sp * stretch))


class Debris:
    """Bumper plastic and headlight glass thrown from a contact point (ballistic, lands and stays)."""

    def __init__(self, n=40):
        mats = [material("Debris plastic", (0.03, 0.03, 0.035), rough=0.45), material("Debris glass", (0.75, 0.82, 0.9), rough=0.05),
                material("Debris paint", (0.55, 0.06, 0.05), metal=0.3, rough=0.35)]
        rng = random.Random(7)
        self.items = []
        for k in range(n):
            s = rng.uniform(0.015, 0.05)
            ob = cube(f"Debris {k}", (0, 0, -10), (s, s * rng.uniform(0.5, 1.6), s * 0.4), mats[k % 3])
            vel = Vector((rng.uniform(-5.0, 1.5), rng.uniform(-1.0, 7.0), rng.uniform(1.0, 4.5)))
            spin = Vector((rng.uniform(-25, 25), rng.uniform(-25, 25), rng.uniform(-25, 25)))
            self.items.append((ob, vel, spin))

    def update(self, origin, t):
        for ob, vel, spin in self.items:
            if origin is None or t < 0:
                ob.hide_render = True
                continue
            t_land = (vel.z + math.sqrt(vel.z ** 2 + 2 * 9.81 * max(origin.z, 0.01))) / 9.81
            tau = min(t, t_land)
            p = origin + vel * tau + Vector((0.0, 0.0, -0.5 * 9.81 * tau * tau))
            p.z = max(p.z, 0.008)
            ob.hide_render = False
            ob.location = p
            ob.rotation_euler = tuple(spin * tau)


def build_world(seed=3):
    road = material("Asphalt", (0.07, 0.07, 0.075), rough=0.85)
    base.asphalt_grain(road)
    paint = material("Line paint", (0.85, 0.85, 0.80), rough=0.6)
    grass = material("Verge grass", (0.11, 0.21, 0.045), rough=0.95)
    gravel = material("Shoulder gravel", (0.20, 0.18, 0.15), rough=0.95)
    y_mid, y_len = 185.0, 760.0
    cube("Road", (-6.6, y_mid, -0.05), (12.0, y_len, 0.1), road)
    cube("Shoulder", (-0.3, y_mid, -0.052), (1.2, y_len, 0.1), gravel)
    cube("Verge right", (40.0, y_mid, -0.06), (80.0, y_len, 0.1), grass)
    cube("Verge left", (-52.6, y_mid, -0.06), (80.0, y_len, 0.1), grass)
    cube("Edge line", (-1.2, y_mid, 0.002), (0.15, y_len, 0.004), paint)
    for i in range(int(y_len / 12)):
        cube(f"Centre dash {i}", (-6.6, y_mid - y_len / 2 + 6 + i * 12, 0.002), (0.13, 3.0, 0.004), paint)
    bark = material("Bark", (0.10, 0.07, 0.05), rough=0.9)
    leaves = [material("Leaves a", (0.10, 0.17, 0.05), rough=0.85), material("Leaves b", (0.16, 0.19, 0.05), rough=0.85)]
    rng = random.Random(seed)
    for cy in (0.0, tm.Y_SPEAR):
        for k in range(26):
            x = rng.uniform(7, 55) if k % 4 else rng.uniform(-60, -16)
            y = cy + rng.uniform(-70, 70)
            h = rng.uniform(5, 11)
            bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.18, depth=h * 0.5, location=(x, y, h * 0.25))
            bpy.context.object.data.materials.append(bark)
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=h * 0.32, location=(x, y, h * 0.62))
            ob = bpy.context.object
            ob.scale = (1.0, 1.0, 1.25)
            ob.data.materials.append(leaves[k % 2])
    hill = material("Hills", (0.10, 0.14, 0.10), rough=1.0)
    for x, y, sx in ((260, 120, 180), (230, -160, 140), (-280, 60, 200), (300, 420, 200), (-260, 460, 160)):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=1.0, location=(x, y, -10))
        ob = bpy.context.object
        ob.scale = (sx, sx * 0.8, 45)
        ob.data.materials.append(hill)


def main():
    args = arguments()
    args.out.mkdir(parents=True, exist_ok=True)
    root, body, wheels, geom = base.load_source_car(args.source)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Punchy"
    scene.view_settings.exposure = 0.2
    if hasattr(scene.view_settings, "use_white_balance"):            # warm late-afternoon grade
        scene.view_settings.use_white_balance = True
        scene.view_settings.white_balance_temperature = 7600.0
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    sun_to = cinematic.sun_vector((0.55, 0.75), 15.0)          # low golden sun from behind the approaching car: long shadows, glinting steel
    cinematic.apply_sky(scene, sun_to, strength=0.24, dust=0.7)
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    sun.data.energy, sun.data.angle = 6.5, 0.02
    sun.data.color = (1.0, 0.74, 0.48)
    sun.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()
    build_world()
    steel = galvanised()
    ribbon_mat = galvanised("Ribbon steel", (0.72, 0.73, 0.74))
    wood = material("Post wood", (0.28, 0.19, 0.11), rough=0.85)
    term = RailRun("Terminal", tm.Y0 + tm.HEAD_L, steel, wood, tm.N_POSTS, breakable=True)
    spear = RailRun("Blunt", tm.Y_SPEAR, steel, wood, 22, breakable=False, first_post=1.2)      # the plain end sticks out past its first post
    hot_rail = material("X-ray rail", (1.0, 0.42, 0.05), rough=0.4, emission=3.0)
    head = Head(steel, ribbon_mat)
    sparks = Sparks()
    debris = Debris()

    nose, car_len = geom["nose"], geom["nose"] + geom["tail"]
    wheel_nodes = {w["node"] for w in wheels.values()}
    parts = [o for o in root.children_recursive if o.type == "MESH" and not any(p in wheel_nodes for p in rb._ancestors(o))]
    bpy.context.view_layer.update()
    deformables = [rb.Deformable(o, nose) for o in parts]
    ghost = rb.Ghost(parts)
    ghost.set_tint(PAINT)
    interior = rb.build_interior(root)
    open_cabin = [o for o in interior if o.name.startswith(("Interior door panel", "Interior B pillar", "Interior A pillar", "Interior roof"))]
    interior = [o for o in interior if o not in open_cabin]          # x-ray: seats, dash and floor only, so nothing solid hides the rail
    for o in open_cabin:
        o.hide_render = True
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam

    def render(sh, path):
        scene.render.resolution_x, scene.render.resolution_y = round(FRAME[0] * args.res_scale), round(FRAME[1] * args.res_scale)
        t, kind = sh["t"], sh["variant"]
        if kind == "terminal":
            st = tm.terminal_state(t)
            car_y = tm.Y0 - nose + st["x"]
            crush, head_d = st["crush"], st["head_d"]
            debris_origin = Vector((tm.HEAD_X - 0.25, tm.Y0 - 0.05, 0.55)) if st["contact"] else None
            pen = 0.0
        else:
            st = tm.spear_state(t)
            car_y = tm.Y_SPEAR - nose + st["x"]
            crush, head_d = min(0.05, st["p"]), 0.0
            debris_origin = Vector((tm.RAIL_X - 0.1, tm.Y_SPEAR - 0.05, 0.55)) if st["contact"] else None
            pen = st["p"]
        root.location = (tm.CAR_X, car_y, 0.0)
        for dm in deformables:
            dm.apply(crush, nose)
        for wh in wheels.values():
            wh["node"].rotation_mode = "ZXY"
            wh["node"].rotation_euler = (-(car_y + 100.0) / geom["tyre_radius"], 0, 0)
        y_front = tm.Y0 + head_d
        head.set(y_front, head_d, cutaway=bool(sh.get("cutaway")))
        term.set_start(y_front + tm.HEAD_L)
        term.set_posts(t if kind == "terminal" else -1.0)
        pts = tm.spark_points(t) if kind == "terminal" else []
        sparks.update(pts, abs(sh.get("time_scale", 0.1)))
        debris.update(None if sh.get("xray") else debris_origin, t)
        xray = bool(sh.get("xray"))
        spear.highlight(hot_rail if xray else steel)
        if xray:
            ghost.set_factor(1.0, car_y + nose, car_len, -1e9)
        else:
            ghost.set_factor(0.0, 1e4, car_len)
        for ob in interior:
            ob.hide_render = not xray
        c = sh["cam"]
        if c["rel"] == "head":
            o = Vector((tm.HEAD_X, y_front, 0.0))
        elif c["rel"] == "T":
            o = Vector((0.0, tm.Y0, 0.0))
        elif c["rel"] == "S":
            o = Vector((0.0, tm.Y_SPEAR, 0.0))
        else:
            o = Vector(root.location)
        loc, tgt = o + Vector(c["loc"]), o + Vector(c["target"])
        dd = cam.data
        dd.sensor_fit, dd.sensor_width, dd.lens, dd.clip_start = "HORIZONTAL", 36.0, c["lens"], 0.02
        dd.dof.use_dof = True
        dd.dof.focus_distance = (tgt - loc).length
        dd.dof.aperture_fstop = c.get("fstop", 8.0)
        base.set_camera(cam, loc, tgt)
        bpy.context.view_layer.update()
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        broken = sum(1 for k in range(tm.N_POSTS) if tm.post_fall(k, t)[0] > 0.0) if kind == "terminal" else 0
        return {"variant": kind, "t": round(t, 5), "car_y": round(car_y, 4), "head_d": round(head_d, 4), "crush": round(crush, 4), "penetration": round(pen, 4),
                "ribbon_m": round(tm.ribbon_length(head_d), 3), "posts_down": broken, "sparks": len(pts), "xray": xray, "cutaway": bool(sh.get("cutaway")),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    segs = tl.segments()
    scales = {s["label"]: s["time_scale"] for s in segs}
    a0, b0 = (int(v) for v in args.frames.split("-"))
    frames = [int(v) for v in args.list.split(",")] if args.list else list(range(a0, b0 + 1))
    a0 = frames[0]
    out = []
    for f in frames:
        t0 = time.time()
        sh = tl.frame_state(f, segs)
        sh["time_scale"] = scales[sh["segment"]]
        part = render(sh, args.out / f"frame_{f:05d}.png")
        info = {"frame": f, "segment": sh["segment"], "split": False, "parts": [part], "render_seconds": round(time.time() - t0, 1)}
        out.append(info)
        print("TERMINAL_FRAME " + json.dumps(info), flush=True)
    (args.out / f"terminal-frames-{a0:05d}.json").write_text(json.dumps({"renderer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                                                         "frames": out}, indent=1))


if __name__ == "__main__":
    main()
