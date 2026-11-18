"""EP.04 crumple zone: 100 % 3D renderer (Blender, Cycles CPU). The pinned CC0 sedan drives into a rigid barrier; its nose is deformed per frame from the simulation
(crumple_motion.crush_map), the front wheels are pushed back with the structure, and the passenger cell never moves. X-ray: a scan line turns the body into a ghost and shows
the crush rails, the bumper beam and the passenger safety cell (3D objects deformed by the same map). Layouts: "full" (1080x1920) and "stack" (two 1080x960 panels,
CRUMPLE on top, RIGID below). Not calibrated; see crumple_motion."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from benchmarks.crumple_zone import crumple_cameras as ccams  # noqa: E402
from benchmarks.crumple_zone import crumple_motion as cm  # noqa: E402
from benchmarks.crumple_zone import dummy_motion  # noqa: E402
from benchmarks.crumple_zone import structure_geometry as sg  # noqa: E402
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402

material, cube = base.material, base.cube
SIZES = {"full": (1080, 1920)}
PAINT = {"crumple": (1.0, 1.0, 1.0), "rigid": (0.45, 0.8, 1.7)}      # body paint multiplier: the rigid-front car is blue, the crumple car keeps the original silver


def arguments():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--end", type=int, default=0)
    p.add_argument("--preview", action="store_true")
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return p.parse_args(argv)


def tube(name, p0, p1, radius, mat, parent, n_seg=48, n_ring=8):
    """Tube mesh between two car-frame points with many rings along its length (so the crush map can fold it). Returns (object, rest vertices (N, 3))."""
    verts = sg.tube_vertices(p0, p1, radius, n_seg, n_ring)
    faces = sg.tube_faces(n_seg, n_ring)
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([tuple(v) for v in verts], [], faces)
    mesh.update()
    mesh.polygons.foreach_set("use_smooth", [True] * len(faces))
    mesh.materials.append(mat)
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(ob)
    ob.parent = parent
    return ob, verts


class Dummy:
    """The driver as a crash-test-dummy style figure (plain shapes, no face, no text): belted in the driver's seat, parented to the car so that it moves with the cabin. The torso hinges
    forward at the hip and the head swings on the neck, driven by dummy_motion (forward travel and chest load of the simulated crash). Chest and head turn from green through yellow to red
    with the peak chest load: the colour is the only 'damage' indicator."""
    HIP = (-0.36, 0.08, 0.40)
    WHEEL = (-0.36, 0.60, 0.88)
    GREEN, YELLOW, RED = (0.15, 0.75, 0.22), (0.95, 0.80, 0.08), (0.95, 0.07, 0.04)

    def __init__(self, root):
        hx, hy, hz = self.HIP
        # Same driver as the Rumble episode (benchmarks/road_safety/render_driver_insert.py): blue shirt, brown skin, dark hair, eyes, brows, nose, ears,
        # arms on the wheel; proportions of that figure scaled by SC and mirrored so that it faces the car's nose (+Y).
        SC = 0.5
        self.shirt_base = (0.035, 0.28, 0.47)
        self.skin = material("Driver shirt", self.shirt_base, rough=0.65)
        skin = material("Driver skin", (0.52, 0.28, 0.15), rough=0.65)
        dark = material("Driver hair", (0.018, 0.025, 0.035), rough=0.65)
        white = material("Driver eyes", (0.90, 0.94, 0.97), rough=0.5)
        limb = skin
        self.pivot = bpy.data.objects.new("Driver torso pivot", None)
        bpy.context.collection.objects.link(self.pivot)
        self.pivot.parent, self.pivot.location = root, (hx, hy, hz)
        self.neck = bpy.data.objects.new("Driver neck pivot", None)
        bpy.context.collection.objects.link(self.neck)
        self.neck.parent, self.neck.location = self.pivot, (0.0, 0.0, 0.55)

        def shape(kind, name, loc, scale, mat, parent):
            if kind == "sphere":
                bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=24, ring_count=16, location=(0, 0, 0))
            else:
                bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0))
            ob = bpy.context.object
            ob.name, ob.scale, ob.location = name, scale, loc
            ob.data.materials.append(mat)
            ob.parent = parent
            for p in ob.data.polygons:
                p.use_smooth = kind == "sphere"
            return ob

        shape("sphere", "Driver chest", (0.0, 0.0, 0.25), (0.185, 0.115, 0.245), self.skin, self.pivot)
        shape("sphere", "Driver neck", (0.0, 0.0, -0.07), (0.06, 0.06, 0.085), skin, self.neck)
        hc = 0.07
        shape("sphere", "Driver head", (0.0, 0.0, hc), (0.128, 0.115, 0.16), skin, self.neck)
        shape("sphere", "Driver hair", (0.0, -0.018, hc + 0.10), (0.13, 0.115, 0.075), dark, self.neck)
        shape("sphere", "Driver nose", (0.0, 0.12, hc - 0.007), (0.022, 0.037, 0.027), skin, self.neck)
        for sx in (-1, 1):
            shape("sphere", "Driver eye", (sx * 0.048, 0.107, hc + 0.033), (0.032, 0.018, 0.022), white, self.neck)
            shape("sphere", "Driver pupil", (sx * 0.048, 0.124, hc + 0.033), (0.0125, 0.007, 0.0135), dark, self.neck)
            shape("sphere", "Driver brow", (sx * 0.048, 0.108, hc + 0.07), (0.037, 0.011, 0.008), dark, self.neck)
            shape("sphere", "Driver ear", (sx * 0.127, -0.007, hc - 0.002), (0.022, 0.037, 0.042), skin, self.neck)
        shape("sphere", "Driver mouth", (0.0, 0.109, hc - 0.065), (0.033, 0.009, 0.006), dark, self.neck)
        shape("cube", "Driver pelvis", (hx, hy, hz - 0.02), (0.34, 0.27, 0.16), material("Driver trousers", (0.055, 0.085, 0.12), rough=0.7), root)
        trousers = bpy.data.materials["Driver trousers"]
        for sx in (-1, 1):
            tube(f"Driver thigh {sx}", (hx + 0.09 * sx, hy, hz), (hx + 0.09 * sx, hy + 0.46, hz + 0.05), 0.075, trousers, root, n_seg=16, n_ring=2)
            tube(f"Driver shin {sx}", (hx + 0.09 * sx, hy + 0.46, hz + 0.05), (hx + 0.09 * sx, hy + 0.52, hz - 0.36), 0.06, trousers, root, n_seg=16, n_ring=2)
            tube(f"Driver upper arm {sx}", (0.19 * sx, 0.0, 0.47), (0.20 * sx, 0.15, 0.32), 0.078, self.skin, self.pivot, n_seg=16, n_ring=8)
            tube(f"Driver forearm {sx}", (0.20 * sx, 0.15, 0.32), (0.16 * sx, 0.40, 0.44), 0.066, skin, self.pivot, n_seg=16, n_ring=8)
        wheel = material("Steering wheel", (0.05, 0.05, 0.055), rough=0.5)
        bpy.ops.mesh.primitive_torus_add(major_radius=0.18, minor_radius=0.018, location=self.WHEEL, rotation=(math.radians(-58), 0, 0))
        wob = bpy.context.object
        wob.name = "Steering wheel"
        wob.data.materials.append(wheel)
        wob.parent = root
        self.head = self.neck

    def colour(self, injury):
        a, b, t = (self.GREEN, self.YELLOW, injury * 2.0) if injury < 0.5 else (self.YELLOW, self.RED, injury * 2.0 - 1.0)
        c = tuple(a[i] + (b[i] - a[i]) * t for i in range(3))
        c = tuple(self.shirt_base[i] + (c[i] - self.shirt_base[i]) * min(1.0, injury * 3.0) for i in range(3))   # the shirt is blue until the load is felt
        bsdf = self.skin.node_tree.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = (*c, 1.0)
        bsdf.inputs["Emission Color"].default_value = (*c, 1.0)
        return c

    def pose(self, panel, sim_time):
        st = dummy_motion.at(panel, sim_time)
        hx, hy, hz = self.HIP
        self.pivot.location = (hx, hy + 0.25 * st["travel_m"], hz)
        self.pivot.rotation_euler = (-dummy_motion.pitch_rad(st["travel_m"]), 0.0, 0.0)
        self.neck.rotation_euler = (-dummy_motion.head_extra_rad(st["chest_g"]), 0.0, 0.0)
        st["colour"] = self.colour(st["injury"])
        return st


def build_interior(root):
    """The cabin set for the interior shots (car frame, parented to the car): driver and passenger seats, dashboard, steering column, door panels, pillars, roof liner, floor. In the interior shots the car body
    is not rendered at all (like the earlier driver insert of the Rumble episode); this set and the driver are what the camera sees. Returns the list of objects."""
    seat = material("Interior seat", (0.16, 0.26, 0.40), rough=0.7)
    trim = material("Interior trim", (0.34, 0.42, 0.52), rough=0.6)
    dark = material("Interior dark", (0.09, 0.10, 0.13), rough=0.8)
    liner = material("Interior liner", (0.12, 0.14, 0.18), rough=0.9)      # the roof lining must not blow out white at the top of the forward view
    out = []

    def box(name, loc, size, mat):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
        ob = bpy.context.object
        ob.name, ob.scale = name, size
        ob.data.materials.append(mat)
        ob.parent = root
        out.append(ob)
        return ob

    for sx, who in ((-0.36, "driver"), (0.36, "passenger")):
        box(f"Interior {who} seat cushion", (sx, 0.02, 0.30), (0.52, 0.58, 0.14), seat)
        box(f"Interior {who} seat back", (sx, -0.34, 0.72), (0.52, 0.14, 0.78), seat)
        box(f"Interior {who} headrest", (sx, -0.36, 1.20), (0.28, 0.10, 0.22), seat)
    box("Interior dashboard", (0.0, 1.00, 0.66), (1.56, 0.42, 0.30), trim)
    box("Interior dashboard top", (0.0, 0.86, 0.84), (1.56, 0.30, 0.08), dark)
    box("Interior steering column", (-0.36, 0.78, 0.78), (0.07, 0.40, 0.07), dark)
    box("Interior centre console", (0.0, 0.25, 0.40), (0.22, 1.1, 0.26), trim)
    box("Interior floor", (0.0, 0.2, 0.17), (1.56, 2.2, 0.05), dark)
    for sx in (-1, 1):
        box(f"Interior door panel {sx}", (0.78 * sx, 0.20, 0.62), (0.07, 1.5, 0.62), trim)
        box(f"Interior B pillar {sx}", (0.78 * sx, -0.42, 1.0), (0.08, 0.12, 0.62), trim)
        ob, _ = tube(f"Interior A pillar {sx}", (0.76 * sx, 0.98, 0.84), (0.76 * sx, 0.36, 1.24), 0.045, trim, root, n_seg=10, n_ring=2)
        out.append(ob)
    box("Interior roof header", (0.0, 0.36, 1.25), (1.56, 0.08, 0.06), liner)
    box("Interior roof liner", (0.0, 0.30, 1.27), (1.56, 1.8, 0.04), liner)      # reaches over the windscreen top so no open sky shows above the wall
    bpy.ops.object.light_add(type="AREA", location=(0.0, 0.25, 1.18))      # interior fill light: the cabin shots are lit from inside (the car body that would let the sun in is not rendered)
    lamp = bpy.context.object
    lamp.name = "Interior fill light"
    lamp.data.energy, lamp.data.shape, lamp.data.size, lamp.data.size_y = 70.0, "RECTANGLE", 1.3, 1.1
    lamp.rotation_euler = (math.pi, 0.0, 0.0)
    lamp.parent = root
    out.append(lamp)
    for ob in out:
        ob.hide_render = True
    return out


class Ghost:
    """Body materials copied with a world-space scan line: everything the line has passed turns almost transparent with a bright blue rim; the line itself flares."""
    SOFT = 0.35

    def __init__(self, parts):
        self.wipes, seen, self.paints = [], {}, []
        for o in parts:
            for i, m in enumerate(o.data.materials):
                if m is None:
                    continue
                if m.name not in seen:
                    seen[m.name] = self._material(m)
                o.data.materials[i] = seen[m.name]

    def _material(self, m):
        c = m.copy()
        c.name = m.name + " ghost"
        nt = c.node_tree
        bsdf = nt.nodes.get("Principled BSDF")
        alpha0 = bsdf.inputs["Alpha"].default_value
        base = bsdf.inputs["Base Color"]
        col = tuple(base.default_value)
        lum = 0.2126 * col[0] + 0.7152 * col[1] + 0.0722 * col[2]
        if not base.is_linked and alpha0 >= 0.99 and 0.12 < lum < 0.95:
            self.paints.append((bsdf, col))      # body paint: the rigid-front car gets a different colour so the two crashes are told apart without any text

        def node(kind, **kw):
            n = nt.nodes.new(kind)
            for k, v in kw.items():
                setattr(n, k, v)
            return n

        def op(o, a=None, b=None, clamp=False):
            n = node("ShaderNodeMath", operation=o, use_clamp=clamp)
            for i, v in enumerate((a, b)):
                if v is None:
                    continue
                if isinstance(v, (int, float)):
                    n.inputs[i].default_value = v
                else:
                    nt.links.new(v, n.inputs[i])
            return n.outputs[0]

        geo = node("ShaderNodeNewGeometry")
        sep = node("ShaderNodeSeparateXYZ")
        nt.links.new(geo.outputs["Position"], sep.inputs[0])
        wipe = node("ShaderNodeValue")
        self.wipes.append(wipe)
        mask = op("MULTIPLY", op("SUBTRACT", sep.outputs[1], wipe.outputs[0]), 1.0 / self.SOFT, clamp=True)
        nt.links.new(op("ADD", op("MULTIPLY", mask, -0.8 * alpha0), alpha0), bsdf.inputs["Alpha"])
        lw = node("ShaderNodeLayerWeight")
        lw.inputs["Blend"].default_value = 0.35
        edge = op("MULTIPLY", op("MULTIPLY", lw.outputs["Facing"], mask), 8.0)
        flare = op("MULTIPLY", op("MULTIPLY", mask, op("SUBTRACT", 1.0, mask)), 28.0)
        nt.links.new(op("ADD", edge, flare), bsdf.inputs["Emission Strength"])
        bsdf.inputs["Emission Color"].default_value = (0.25, 0.65, 1.0, 1.0)
        return c

    def set_tint(self, mult):
        for bsdf, col in self.paints:
            bsdf.inputs["Base Color"].default_value = (min(1.0, col[0] * mult[0]), min(1.0, col[1] * mult[1]), min(1.0, col[2] * mult[2]), col[3])

    def set_factor(self, xf, y_nose, car_length, y_floor=-1e9):
        wipe = max(y_floor, y_nose + 0.6 - (0.6 + car_length + 0.4) * xf)        # the line runs from just ahead of the nose back to the passenger cell (y_floor): the cabin is never made see-through
        for w in self.wipes:
            w.outputs[0].default_value = wipe


class Deformable:
    """A mesh whose vertices are driven by the crush map: rest positions in the car frame, the object's own matrix to go back to local coordinates."""

    def __init__(self, ob, nose, local_is_car_frame=False, mapper=None):
        self.mapper = mapper or cm.crush_map
        mesh = ob.data
        if mesh.users > 1:
            ob.data = mesh = mesh.copy()
        self.ob, self.mesh = ob, mesh
        n = len(mesh.vertices)
        co = np.zeros(n * 3)
        mesh.vertices.foreach_get("co", co)
        self.local0 = co.reshape(n, 3)
        if local_is_car_frame:
            self.m3, self.t = np.eye(3), np.zeros(3)
        else:
            m = np.array(ob.matrix_world)
            self.m3, self.t = m[:3, :3], m[:3, 3]
        self.p0 = self.local0 @ self.m3.T + self.t
        self.minv = np.linalg.inv(self.m3)
        self.idx = np.where(self.p0[:, 1] > nose - cm.CRUSH_LENGTH - 1e-6)[0]

    def apply(self, s, nose):
        """Poses the vertices for crush stroke s; returns the deformed car-frame points of the affected vertices."""
        self.sub = self.p0[:0]
        if len(self.idx) == 0:
            return self.sub
        sub = self.mapper(self.p0[self.idx], s, nose)
        self.sub = sub
        out = self.local0.copy()
        out[self.idx] = (sub - self.t) @ self.minv.T
        self.mesh.vertices.foreach_set("co", out.ravel())
        self.mesh.update()
        return sub


def place_camera(cam, kind, frame):
    c = ccams.camera(kind, frame)
    d = cam.data
    d.sensor_fit, d.sensor_width = "HORIZONTAL", ccams.SENSOR_W
    d.lens, d.shift_y = c["lens"], c["shift_y"]
    base.set_camera(cam, c["loc"], c["target"])


def main():
    args = arguments()
    args.out.mkdir(parents=True, exist_ok=True)
    root, body, wheels, geom = base.load_source_car(args.source)
    scene = bpy.context.scene
    scene.name = "panels"
    k = 3 if args.preview else 1
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 7 if args.preview else 24
    scene.cycles.use_denoising = True
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.exposure = -1.3
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    sun_to = cinematic.sun_vector((-0.5, -0.8), 36.0)
    cinematic.apply_sky(scene, sun_to, strength=0.25, dust=0.5)
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    sun.data.energy, sun.data.angle = 3.4, 0.03
    sun.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()
    road = material("Asphalt", (0.07, 0.07, 0.075), rough=0.85)
    base.asphalt_grain(road)
    cube("Road", (0, -10, -0.05), (14.0, 60, 0.1), road)
    concrete = material("Barrier", (0.12, 0.12, 0.115), rough=0.9)
    cube("Barrier", (0, 0.5, 1.0), (9.0, 1.0, 2.0), concrete)       # front face at y = 0
    cube("Barrier stripe", (0, -0.002, 0.5), (9.0, 0.004, 0.18), material("Stripe", (0.9, 0.62, 0.05), rough=0.5))
    nose, front_axle = geom["nose"], geom["front_axle"]
    TAIL["m"] = geom["tail"]
    car_len = geom["nose"] + geom["tail"]
    print("CRUMPLE_GEOMETRY " + json.dumps(geom), flush=True)

    wheel_nodes = {w["node"] for w in wheels.values()}
    parts = [o for o in root.children_recursive if o.type == "MESH" and not any(p in wheel_nodes for p in _ancestors(o))]
    bpy.context.view_layer.update()
    assert root.location.length < 1e-9 and tuple(round(a, 6) for a in root.rotation_euler) == (0.0, 0.0, 0.0), "car root is not at the identity pose"
    deformables = [Deformable(o, nose) for o in parts]
    total_verts = sum(len(d.mesh.vertices) for d in deformables)
    active = sum(1 for d in deformables if len(d.idx))
    for dm in deformables:
        if len(dm.idx):
            print("CRUMPLE_PART " + json.dumps({"name": dm.ob.name, "verts": len(dm.mesh.vertices), "y_min": round(float(dm.p0[:, 1].min()), 3), "y_max": round(float(dm.p0[:, 1].max()), 3),
                                                "in_zone": int(len(dm.idx)), "parent": dm.ob.parent.name if dm.ob.parent else None}), flush=True)
    print("CRUMPLE_PROBE " + json.dumps({"body_meshes": len(parts), "vertices": total_verts, "meshes_in_crush_zone": active,
                                          "zone_vertices": int(sum(len(d.idx) for d in deformables)), "nose": nose, "front_axle": front_axle,
                                          "half_width": geom["body_half_width"], "roof": geom["roof"]}), flush=True)

    # X-ray structure: crush rails, bumper beam (amber), passenger safety cell (green-cyan); all in car-frame coordinates
    cabin_y = nose - cm.CRUSH_LENGTH
    rail_mat = material("Crush rail", (1.0, 0.45, 0.05), rough=0.4, emission=2.0)
    cell_mat = material("Safety cell", (0.1, 1.0, 0.55), rough=0.4, emission=1.6)
    structure, cell_objs = [], []
    for name, it in sg.structure(nose).items():
        ob, v0 = tube(name, it["p0"], it["p1"], it["radius"], rail_mat if it["deforms"] else cell_mat, root, n_seg=it["n_seg"])
        (structure if it["deforms"] else cell_objs).append(ob if not it["deforms"] else (ob, v0))
    hx, y1, y0, z0, z1 = 0.74, cabin_y - 0.05, cabin_y - 1.95, 0.40, 1.22
    cell_y0, cell_y1 = y0, y1
    structure_def = [Deformable(ob, nose, local_is_car_frame=True, mapper=cm.rail_fold) for ob, _ in structure]      # the rails fold like an accordion
    ghost = Ghost([o for o in parts])
    dummy = Dummy(root)
    interior = build_interior(root)
    wheel_objs = [o for w in wheels.values() for o in [w["node"], *w["node"].children_recursive]]
    all_body = list(parts) + wheel_objs

    # no scene text of any kind (owner decision): the only words in the film are the narration captions burned in at assembly
    body_mats = {}
    for o in parts:
        for m in o.data.materials:
            if m is not None and m.name not in body_mats:
                body_mats[m.name] = m
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam

    recs = {kind: cm.simulate(kind) for kind in cm.PROFILES}
    wheel_r = geom["tyre_radius"]
    result, checks, evidence = [], [], {}
    for f in range(args.start, args.end + 1):
        t0 = time.time()
        seg = cm.segment_at(f)
        w, h = SIZES[seg["layout"]]
        scene.render.resolution_x, scene.render.resolution_y = w // k, h // k
        t = cm.frame_time(f)
        xf = cm.xray_factor(f)
        info = {"frame": f, "segment": seg["id"], "camera": seg["camera"], "layout": seg["layout"], "sim_time": round(t, 5), "xray": round(xf, 3)}
        for panel in cm.visible_panels(f):
            rec = recs[panel]
            ps = cm.sample(rec, t)
            d, s = ps["d"], ps["s"]
            root.location = (0.0, -cm.LEAD_SIM + d - nose, 0.0)
            deformed = [dm.apply(s, nose) for dm in deformables]
            for dm in structure_def:
                dm.apply(s, nose)
            nose_world = root.location.y + max(float(p[:, 1].max()) for p in deformed if len(p))
            top_parts = sorted(((round(root.location.y + float(dm.sub[:, 1].max()), 3), dm.ob.name) for dm in deformables if len(dm.sub)), reverse=True)[:3]
            for key, wh in wheels.items():
                base_pt = np.array([[wh["base"].x, wh["base"].y, wh["base"].z]])
                y_new = cm.wheel_y(float(wh["base"].y), s, nose, wheel_r) if key.startswith("front") else float(wh["base"].y)
                wh["node"].location = (wh["base"].x, y_new, wh["base"].z)
                wh["node"].rotation_euler = (-d / wheel_r, 0, 0)
            show = xf > 0.02      # both crashes get the same see-through front: the rails of the first car fold, the rails of the rigid car stay straight
            for ob, _ in structure:
                ob.hide_render = not show
            for ob in cell_objs:
                ob.hide_render = True      # no box of any kind: the cabin is simply left solid while the front is see-through
            cf = cm.cabin_xray_factor(f)      # the cabin turns see-through after the front: the driver can be seen
            ghost.set_factor(xf, root.location.y + nose, car_len, root.location.y + cabin_y + 0.04 - cf * (car_len + 0.8))
            dst = dummy.pose(panel, t)
            ghost.set_tint(PAINT[panel])
            place_camera(cam, seg["camera"], f)
            cam.data.clip_start = 0.03
            inside_cabin = bool(ccams.camera(seg["camera"], f)["interior"])      # interior shot: no car body, only the cabin set and the driver
            for ob in all_body:
                ob.hide_render = inside_cabin
            for ob, _ in structure:
                ob.hide_render = inside_cabin or not show
            for ob in interior:
                ob.hide_render = not inside_cabin
            bpy.context.view_layer.update()  # the evidence below projects through cam.matrix_world: without this it lags one frame (first frame of a shard saw the previous camera)
            ev = measure_evidence(scene, cam, root, deformables, structure_def, nose, cabin_y, s, xf, seg, panel, (cell_y0, cell_y1))
            evidence.setdefault(f, {"metrics": {}, "in_view": {}})
            em, ev_view = evidence[f]["metrics"], evidence[f]["in_view"]
            em[f"{panel}.stroke_m"] = s
            em["nose.world_y_m"] = nose_world
            em["final_pose.front_crush_m"] = min(s / cm.COMPACTION, cm.CRUSH_LENGTH) if seg["id"] == "C" else 0.0
            em["xray.factor"] = xf
            em["film.speed_vs_real"] = cm.film_speed(f)
            em["cabin.xray_factor"] = cf
            head_co = world_to_camera_view(scene, cam, dummy.head.matrix_world @ Vector((0.0, 0.02, 0.12)))      # where the driver's head lands in the picture
            driver_seen = bool((cf >= 0.5 or inside_cabin) and head_co.z > 0 and 0.03 < head_co.x < 0.97 and 0.03 < head_co.y < 0.97)
            if inside_cabin:      # the car body is not in the picture: nothing of it can be counted as seen; the caption rows are checked against the driver's head
                ev["in_view"].update({"car_front": False, "crush_rails": False, "bumper_beam": False, "safety_cell": False})
                ev["whole_car"] = False
                head_row = (1.0 - head_co.y) * 1920.0
                ev["caption_overlap"] = 1.0 if CAPTION_ROWS[0] <= head_row <= CAPTION_ROWS[1] else 0.0
            em[f"{panel}.dummy_peak_chest_g"] = dst["peak_chest_g"]
            em[f"{panel}.dummy_injury"] = dst["injury"]
            em[f"{panel}.dummy_travel_m"] = dst["travel_m"]
            ev_view["driver" if panel == "crumple" else "rigid_driver"] = driver_seen
            em["nose.penetration_mm"] = max(em.get("nose.penetration_mm", 0.0), round(1000 * max(0.0, nose_world), 2))
            em["cell.max_displacement_mm"] = max(em.get("cell.max_displacement_mm", 0.0), ev["cell_mm"])
            em["caption.overlap"] = max(em.get("caption.overlap", 0.0), ev["caption_overlap"])
            if panel == "crumple":
                em["body.max_rise_m"] = ev["rise_m"]
                em["wheels.pushback_m"] = float(wheels["front_right"]["base"].y) - float(wheels["front_right"]["node"].location.y)
                em["rails.shortening_m"] = ev["rail_shortening"]
                em["crumple.crushed_depth_m"] = min(s / cm.COMPACTION, cm.CRUSH_LENGTH)
                for name in ("car_front", "crush_rails", "bumper_beam", "safety_cell"):
                    ev_view[name] = ev["in_view"][name]
                ev_view["whole_car"] = ev["whole_car"]
            else:
                ev_view["rigid_car_front"] = ev["in_view"]["car_front"]
                ev_view["rigid_whole_car"] = ev["whole_car"]
                ev_view["rigid_crush_rails"] = ev["in_view"]["crush_rails"]
                em["rigid.rails_shortening_m"] = ev["rail_shortening"]
                em["rigid.speed_away_mps"] = max(0.0, -ps["v"])
                em["rigid.rebound_m"] = cm.rebound_distance(d, s)
            ev_view["barrier"] = ev_view.get("barrier", False) or ev["in_view"]["barrier"]
            path = args.out / f"frame_{f:04d}_{panel}.png"
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            checks.append({"frame": f, "panel": panel, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            front_wheel = wheels["front_right"]["node"].location
            info[panel] = {"cabin_advance_m": round(d, 4), "stroke_m": round(s, 4), "decel_g": round(ps["g"], 2),
                           "nose_world_y_mm": round(1000 * nose_world, 2), "top_parts": top_parts, "root_y": round(root.location.y, 3), "nose_penetration_mm": round(1000 * max(0.0, nose_world), 2),
                           "front_wheel_y": round(float(front_wheel.y), 3), "wheel_z_gap_mm": round(1000 * abs(front_wheel.z - wheels["front_right"]["base"].z), 3)}
        info["render_seconds"] = round(time.time() - t0, 1)
        result.append(info)
        print("CRUMPLE_FRAME " + json.dumps(info), flush=True)
    proof = {"renderer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "geometry": geom, "preview": bool(args.preview), "checksums": checks,
             "telemetry": result, "evidence": {str(k): v for k, v in evidence.items()}, "physically_calibrated": False, "all_3d": True, "overlays": "none", "film": cm.FILM}
    (args.out / "crumple-proof.json").write_text(json.dumps(proof, indent=1))


CAPTION_ROWS = (1408, 1540)       # rows of the 1080x1920 frame where the captions sit
PANEL_ROWS = {"full": {"crumple": (0, 1920), "rigid": (0, 1920)}}
TAIL = {"m": 2.065}      # set from the measured geometry in main()


def measure_evidence(scene, cam, root, deformables, structure_def, nose, cabin_y, s, xf, seg, panel, cell_span):
    """What the picture of this panel really contains, measured from the deformed geometry and the camera: used by the narration-visual alignment check."""
    shift = Vector(root.location)

    def project(p):
        co = world_to_camera_view(scene, cam, Vector((p[0], p[1], p[2])) + shift)
        return co.x, co.y, co.z

    def inside(p, margin=0.03):
        x, y, z = project(p)
        return bool(z > 0 and margin < x < 1 - margin and margin < y < 1 - margin)

    rail, beam = structure_def[0], structure_def[2]
    rail_full = rail.p0.copy()
    rail_full[rail.idx] = rail.sub
    beam_full = beam.p0.copy()
    beam_full[beam.idx] = beam.sub
    rail_len0 = float(rail.p0[:, 1].max() - rail.p0[:, 1].min())
    shortening = rail_len0 - float(rail_full[:, 1].max() - rail_full[:, 1].min())
    cell_mm = 0.0
    rise = 0.0
    pts = []
    for dm in deformables:
        if len(dm.idx) == 0:
            continue
        behind = dm.p0[dm.idx, 1] <= cabin_y
        if behind.any():
            cell_mm = max(cell_mm, 1000 * float(np.abs(dm.sub[behind] - dm.p0[dm.idx][behind]).max()))
        rise = max(rise, float((dm.sub[:, 2] - dm.p0[dm.idx][:, 2]).max()))
        pts.append(dm.sub[:: max(1, len(dm.sub) // 300)])
    zone = np.vstack(pts) if pts else np.zeros((1, 3))
    proj = np.array([project(p)[:2] for p in zone])
    y0_, y1_ = float(proj[:, 1].min()), float(proj[:, 1].max())
    off, h = PANEL_ROWS[seg["layout"]][panel]
    top, bottom = off + (1 - y1_) * h, off + (1 - y0_) * h
    overlap = max(0.0, min(bottom, CAPTION_ROWS[1]) - max(top, CAPTION_ROWS[0])) / max(1.0, bottom - top)
    ghost_on = xf >= 0.5
    cell_c = (0.0, 0.5 * (cell_span[0] + cell_span[1]), 0.8)
    whole = all(inside((0.0, y, 0.5)) for y in (nose - s, -TAIL["m"]))
    return {"cell_mm": cell_mm, "rise_m": rise, "whole_car": whole, "rail_shortening": shortening, "caption_overlap": round(overlap, 3),
            "in_view": {"car_front": inside((0.0, nose - s, 0.5)), "barrier": bool(project((0.0, -shift.y, 1.0))[2] > 0 and 0.0 < project((0.0, -shift.y, 1.0))[0] < 1.0),
                        "crush_rails": ghost_on and inside(rail_full.mean(axis=0)), "bumper_beam": ghost_on and inside(beam_full.mean(axis=0)),
                        "safety_cell": ghost_on and inside(cell_c)}}


def _ancestors(ob):
    p = ob.parent
    while p is not None:
        yield p
        p = p.parent


main()
