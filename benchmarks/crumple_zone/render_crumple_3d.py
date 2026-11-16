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
from benchmarks.crumple_zone import structure_geometry as sg  # noqa: E402
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402

material, cube = base.material, base.cube
SIZES = {"full": (1080, 1920), "stack": (1080, 960)}


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


class Ghost:
    """Body materials copied with a world-space scan line: everything the line has passed turns almost transparent with a bright blue rim; the line itself flares."""
    SOFT = 0.35

    def __init__(self, parts):
        self.wipes, seen = [], {}
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

    def set_factor(self, xf, y_nose, car_length):
        wipe = y_nose + 0.6 - (0.6 + car_length + 0.4) * xf        # the line runs from just ahead of the nose to behind the tail
        for w in self.wipes:
            w.outputs[0].default_value = wipe


class Deformable:
    """A mesh whose vertices are driven by the crush map: rest positions in the car frame, the object's own matrix to go back to local coordinates."""

    def __init__(self, ob, nose, local_is_car_frame=False):
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
        sub = cm.crush_map(self.p0[self.idx], s, nose)
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
    structure_def = [Deformable(ob, nose, local_is_car_frame=True) for ob, _ in structure]
    ghost = Ghost([o for o in parts])

    sign_mat = material("Sign", (0.45, 1.0, 0.15), rough=0.5, emission=1.0)
    labels = {}
    for kind, text in (("crumple", "CRUMPLE"), ("rigid", "RIGID")):
        cu = bpy.data.curves.new("Sign " + kind, "FONT")
        cu.body, cu.size, cu.extrude, cu.align_x, cu.align_y = text, 0.3, 0.02, "CENTER", "CENTER"
        ob = bpy.data.objects.new("Sign " + kind, cu)
        bpy.context.collection.objects.link(ob)
        ob.data.materials.append(sign_mat)
        labels[kind] = ob
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
        for panel in seg["panels"]:
            rec = recs[panel]
            i = min(int(round(t * cm.RENDER_HZ)), len(rec["t"]) - 1)
            d, s = float(rec["d"][i]), float(rec["s"][i])
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
            show = xf > 0.02 and panel == "crumple"
            for ob, _ in structure:
                ob.hide_render = not show
            for ob in cell_objs:
                ob.hide_render = not show
            ghost.set_factor(xf, root.location.y + nose, car_len)
            for kind, lab in labels.items():
                lab.hide_render = not (seg["layout"] == "stack" and kind == panel)
            sign_in_view = False
            place_camera(cam, seg["camera"], f)
            if seg["layout"] == "stack":
                lab = labels[panel]
                lab.location = (-1.55, -2.0, 0.25)
                lab.rotation_euler = (cam.location - Vector(lab.location)).to_track_quat("Z", "Y").to_euler()
                bpy.context.view_layer.update()
                co = world_to_camera_view(scene, cam, Vector(lab.location))
                sign_in_view = bool(co.z > 0 and 0.08 < co.x < 0.92 and 0.08 < co.y < 0.92)
            ev = measure_evidence(scene, cam, root, deformables, structure_def, nose, cabin_y, s, xf, seg, panel, (cell_y0, cell_y1))
            evidence.setdefault(f, {"metrics": {}, "in_view": {}})
            em, ev_view = evidence[f]["metrics"], evidence[f]["in_view"]
            em[f"{panel}.stroke_m"] = s
            em["xray.factor"] = xf
            em["nose.penetration_mm"] = max(em.get("nose.penetration_mm", 0.0), round(1000 * max(0.0, nose_world), 2))
            em["cell.max_displacement_mm"] = max(em.get("cell.max_displacement_mm", 0.0), ev["cell_mm"])
            em["caption.overlap"] = max(em.get("caption.overlap", 0.0), ev["caption_overlap"])
            if panel == "crumple":
                em["rails.shortening_m"] = ev["rail_shortening"]
                em["crumple.crushed_depth_m"] = min(s / cm.COMPACTION, cm.CRUSH_LENGTH)
                for name in ("car_front", "crush_rails", "bumper_beam", "safety_cell"):
                    ev_view[name] = ev["in_view"][name]
            else:
                ev_view["rigid_car_front"] = ev["in_view"]["car_front"]
            ev_view["barrier"] = ev_view.get("barrier", False) or ev["in_view"]["barrier"]
            path = args.out / f"frame_{f:04d}_{panel}.png"
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            checks.append({"frame": f, "panel": panel, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            front_wheel = wheels["front_right"]["node"].location
            info[panel] = {"cabin_advance_m": round(d, 4), "stroke_m": round(s, 4), "decel_g": round(float(rec["g"][i]), 2),
                           "nose_world_y_mm": round(1000 * nose_world, 2), "top_parts": top_parts, "root_y": round(root.location.y, 3), "nose_penetration_mm": round(1000 * max(0.0, nose_world), 2),
                           "front_wheel_y": round(float(front_wheel.y), 3), "wheel_z_gap_mm": round(1000 * abs(front_wheel.z - wheels["front_right"]["base"].z), 3),
                           "sign_in_view": sign_in_view}
        info["render_seconds"] = round(time.time() - t0, 1)
        result.append(info)
        print("CRUMPLE_FRAME " + json.dumps(info), flush=True)
    proof = {"renderer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "geometry": geom, "preview": bool(args.preview), "checksums": checks,
             "telemetry": result, "evidence": {str(k): v for k, v in evidence.items()}, "physically_calibrated": False, "all_3d": True, "overlays": "none", "film": cm.FILM}
    (args.out / "crumple-proof.json").write_text(json.dumps(proof, indent=1))


CAPTION_ROWS = (1408, 1540)       # rows of the 1080x1920 frame where the captions sit
PANEL_ROWS = {"full": {"crumple": (0, 1920)}, "stack": {"crumple": (0, 960), "rigid": (960, 960)}}


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
    pts = []
    for dm in deformables:
        if len(dm.idx) == 0:
            continue
        behind = dm.p0[dm.idx, 1] <= cabin_y
        if behind.any():
            cell_mm = max(cell_mm, 1000 * float(np.abs(dm.sub[behind] - dm.p0[dm.idx][behind]).max()))
        pts.append(dm.sub[:: max(1, len(dm.sub) // 300)])
    zone = np.vstack(pts) if pts else np.zeros((1, 3))
    proj = np.array([project(p)[:2] for p in zone])
    y0_, y1_ = float(proj[:, 1].min()), float(proj[:, 1].max())
    off, h = PANEL_ROWS[seg["layout"]][panel]
    top, bottom = off + (1 - y1_) * h, off + (1 - y0_) * h
    overlap = max(0.0, min(bottom, CAPTION_ROWS[1]) - max(top, CAPTION_ROWS[0])) / max(1.0, bottom - top)
    ghost_on = xf >= 0.5 and panel == "crumple"
    cell_c = (0.0, 0.5 * (cell_span[0] + cell_span[1]), 0.8)
    return {"cell_mm": cell_mm, "rail_shortening": shortening, "caption_overlap": round(overlap, 3),
            "in_view": {"car_front": inside((0.0, nose - s, 0.5)), "barrier": bool(project((0.0, -shift.y, 1.0))[2] > 0 and 0.0 < project((0.0, -shift.y, 1.0))[0] < 1.0),
                        "crush_rails": ghost_on and inside(rail_full.mean(axis=0)), "bumper_beam": ghost_on and inside(beam_full.mean(axis=0)),
                        "safety_cell": ghost_on and inside(cell_c)}}


def _ancestors(ob):
    p = ob.parent
    while p is not None:
        yield p
        p = p.parent


main()
