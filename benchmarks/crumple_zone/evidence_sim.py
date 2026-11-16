"""EP.04: the renderer's per-frame evidence computed in pure Python from the simulation, the real sedan vertices (fixture), the camera data and the structure geometry. Same
definitions as render_crumple_3d.measure_evidence, so mesh / wall / caption / timing problems are found by a test in seconds instead of by a 17-minute preview."""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np

from benchmarks.crumple_zone import crumple_cameras as ccams
from benchmarks.crumple_zone import crumple_motion as cm
from benchmarks.crumple_zone import structure_geometry as sg

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sedan_mesh.json.gz"
CAPTION_ROWS = (1408, 1540)
PANEL_ROWS = {"full": {"crumple": (0, 1920)}, "stack": {"crumple": (0, 960), "rigid": (960, 960)}}
TYRE_RADIUS = 0.281


def load_fixture(path: Path = FIXTURE) -> dict:
    return json.loads(gzip.decompress(path.read_bytes()))


class Car:
    def __init__(self, fixture: dict):
        self.geom = fixture["geometry"]
        self.nose = self.geom["nose"]
        self.cabin_y = self.nose - cm.CRUSH_LENGTH
        self.wheels = {k: np.array(v) for k, v in fixture["wheels"].items()}
        body = [np.array(p["verts"]) for p in fixture["parts"] if p["wheel"] is None]
        self.body = [v for v in body if len(v)]
        self.zone = [v[v[:, 1] > self.nose - cm.CRUSH_LENGTH - 1e-6] for v in self.body]
        self.zone = [z for z in self.zone if len(z)]
        self.wheel_parts = {}
        for p in fixture["parts"]:
            if p["wheel"] is not None:
                self.wheel_parts.setdefault(p["wheel"], []).append(np.array(p["verts"]))
        self.structure = sg.structure(self.nose)
        self.tubes = {n: sg.tube_vertices(i["p0"], i["p1"], i["radius"], i["n_seg"]) for n, i in self.structure.items()}


def deformed_geometry(car: Car, s: float) -> dict:
    """Everything the crash moves, in the car frame, for crush stroke s."""
    zone = [cm.crush_map(z, s, car.nose) for z in car.zone]
    tubes = {n: (cm.crush_map(v, s, car.nose) if car.structure[n]["deforms"] else v) for n, v in car.tubes.items()}
    wheels = {}
    for key, base in car.wheels.items():
        y_new = cm.wheel_y(float(base[1]), s, car.nose, TYRE_RADIUS) if key.startswith("front") else float(base[1])
        shift = y_new - float(base[1])
        wheels[key] = [v + np.array([0.0, shift, 0.0]) for v in car.wheel_parts.get(key, [])]
    return {"zone": zone, "tubes": tubes, "wheels": wheels}


def frame_evidence(car: Car, recs: dict, frame: int) -> dict:
    seg = cm.segment_at(frame)
    t = cm.frame_time(frame)
    xf = cm.xray_factor(frame)
    cam = ccams.camera(seg["camera"], frame)
    metrics, in_view, panels = {"xray.factor": xf}, {}, {}
    for panel in seg["panels"]:
        rec = recs[panel]
        i = min(int(round(t * cm.RENDER_HZ)), len(rec["t"]) - 1)
        d, s = float(rec["d"][i]), float(rec["s"][i])
        root_y = -cm.LEAD_SIM + d - car.nose
        g = deformed_geometry(car, s)
        zone_all = np.vstack(g["zone"])
        nose_world = root_y + float(zone_all[:, 1].max())
        wheel_front = root_y + max(float(v[:, 1].max()) for parts in g["wheels"].values() for v in parts if len(v)) if any(g["wheels"].values()) else -1e9
        cell_mm = 0.0
        for z0, z1 in zip(car.zone, g["zone"]):
            behind = z0[:, 1] <= car.cabin_y
            if behind.any():
                cell_mm = max(cell_mm, 1000 * float(np.abs(z1[behind] - z0[behind]).max()))
        shift = np.array([0.0, root_y, 0.0])
        sample = zone_all[:: max(1, len(zone_all) // 300)] + shift
        pr = ccams.project(sample, cam, seg["layout"])
        y0, y1 = float(pr[:, 1].min()), float(pr[:, 1].max())
        off, h = PANEL_ROWS[seg["layout"]][panel]
        top, bottom = off + (1 - y1) * h, off + (1 - y0) * h
        overlap = max(0.0, min(bottom, CAPTION_ROWS[1]) - max(top, CAPTION_ROWS[0])) / max(1.0, bottom - top)

        def inside(p, margin=0.03):
            q = ccams.project(np.array([p], float) + shift, cam, seg["layout"])[0]
            return bool(q[2] > 0 and margin < q[0] < 1 - margin and margin < q[1] < 1 - margin)

        ghost_on = xf >= 0.5 and panel == "crumple"
        rail = g["tubes"]["rail -0.38"]
        rail0 = car.tubes["rail -0.38"]
        shortening = float(rail0[:, 1].max() - rail0[:, 1].min()) - float(rail[:, 1].max() - rail[:, 1].min())
        cell_c = (0.0, car.cabin_y - 1.0, 0.8)
        wall = ccams.project(np.array([[0.0, 0.0, 1.0]]), cam, seg["layout"])[0]
        views = {"car_front": inside((0.0, car.nose - s, 0.5)), "barrier": bool(wall[2] > 0 and 0 < wall[0] < 1),
                 "crush_rails": ghost_on and inside(rail.mean(axis=0)), "bumper_beam": ghost_on and inside(g["tubes"]["bumper beam"].mean(axis=0)),
                 "safety_cell": ghost_on and inside(cell_c)}
        panels[panel] = {"stroke_m": s, "nose_world_y_mm": 1000 * nose_world, "wheel_front_world_y_mm": 1000 * wheel_front, "caption_overlap": overlap, "cell_mm": cell_mm,
                         "rail_shortening": shortening, "in_view": views}
        metrics[f"{panel}.stroke_m"] = s
        metrics["nose.penetration_mm"] = max(metrics.get("nose.penetration_mm", 0.0), 1000 * max(0.0, nose_world, wheel_front))
        metrics["cell.max_displacement_mm"] = max(metrics.get("cell.max_displacement_mm", 0.0), cell_mm)
        metrics["caption.overlap"] = max(metrics.get("caption.overlap", 0.0), overlap)
        if panel == "crumple":
            metrics["rails.shortening_m"] = shortening
            metrics["crumple.crushed_depth_m"] = min(s / cm.COMPACTION, cm.CRUSH_LENGTH)
            for name in ("car_front", "crush_rails", "bumper_beam", "safety_cell"):
                in_view[name] = views[name]
        else:
            in_view["rigid_car_front"] = views["car_front"]
        in_view["barrier"] = in_view.get("barrier", False) or views["barrier"]
    return {"metrics": metrics, "in_view": in_view, "panels": panels}


def timeline_evidence(car: Car, frames=range(1, cm.TOTAL_FRAMES + 1)) -> dict[int, dict]:
    recs = {k: cm.simulate(k) for k in cm.PROFILES}
    return {f: frame_evidence(car, recs, f) for f in frames}


def sky_backed_fraction(car: Car, frame: int, root_y: float) -> float:
    """Share of the body's vertices that the camera sees against the SKY (the view ray through the vertex leaves the scene without meeting the road or the barrier). The ghost
    body must stand against the road and the barrier: pure geometry, no pixels, so the answer does not depend on the ghost's own light-blue colour."""
    seg = cm.segment_at(frame)
    cam = ccams.camera(seg["camera"], frame)
    loc = np.array(cam["loc"], float)
    pts = np.vstack(car.body)
    pts = pts[:: max(1, len(pts) // 1500)] + np.array([0.0, root_y, 0.0])
    d = pts - loc
    sky = 0
    for p, v in zip(pts, d):
        if v[2] >= 0:                                   # looking up or level: the ground can never be hit
            t_wall = (0.0 - p[1]) / v[1] if v[1] > 0 else None     # the barrier face (y = 0) behind the vertex, 4.5 m half width, 2 m high
            hit_wall = t_wall is not None and t_wall > 0 and abs(p[0] + v[0] * t_wall) <= 4.5 and 0 <= p[2] + v[2] * t_wall <= 2.0
            sky += 0 if hit_wall else 1
    return sky / len(pts)
