"""Wireframe contact sheet of chosen film frames from the sedan fixture, the simulation and the camera data: the car's real vertices (grey), the folded rails and beam (orange), the
safety cell (green) and the barrier face, with the caption rows and the mobile safe area drawn. Pure Python/PIL, ~0.3 s per frame, no Blender: used to design and check
camera moves before any render."""
from __future__ import annotations

import sys

import numpy as np
from PIL import Image, ImageDraw

from benchmarks.crumple_zone import crumple_cameras as ccams
from benchmarks.crumple_zone import crumple_motion as cm
from benchmarks.crumple_zone import evidence_sim as es

W, H = 1080, 1920


def frame_image(car: es.Car, frame: int, scale: float = 0.25) -> Image.Image:
    seg = cm.segment_at(frame)
    cam = ccams.camera(seg["camera"], frame)
    panel = seg["panels"][0]
    ps = cm.pose(frame, panel)
    root_y = -cm.LEAD_SIM + ps["d"] - car.nose
    g = es.deformed_geometry(car, ps["s"])
    im = Image.new("RGB", (int(W * scale), int(H * scale)), (20, 24, 34))
    dr = ImageDraw.Draw(im)

    def dots(pts, color, r=1):
        pr = ccams.project(np.asarray(pts, float) + np.array([0.0, root_y, 0.0]), cam)
        for x, y, z in pr:
            if z > 0:
                px, py = x * W * scale, (1 - y) * H * scale
                dr.ellipse([px - r, py - r, px + r, py + r], fill=color)

    # road grid and barrier face
    for yy in np.arange(-30, 0.1, 2.0):
        a = ccams.project(np.array([[-5, yy, 0], [5, yy, 0]], float), cam)
        if (a[:, 2] > 0).all():
            dr.line([(a[0, 0] * W * scale, (1 - a[0, 1]) * H * scale), (a[1, 0] * W * scale, (1 - a[1, 1]) * H * scale)], fill=(45, 50, 60))
    bar = ccams.project(np.array([[-4.5, 0, 0], [4.5, 0, 0], [4.5, 0, 2], [-4.5, 0, 2]], float), cam)
    if (bar[:, 2] > 0).all():
        dr.polygon([(x * W * scale, (1 - y) * H * scale) for x, y, _ in bar], outline=(200, 160, 40))
    body = np.vstack(car.body)
    body = body[:: max(1, len(body) // 2500)]
    zone = np.vstack(g["zone"])[:: 4]
    far = body[body[:, 1] <= car.nose - cm.CRUSH_LENGTH]
    dots(far, (150, 155, 165))
    dots(zone, (190, 195, 205))
    xf = cm.xray_factor(frame)
    if xf >= 0.5:
        for name, v in g["tubes"].items():
            dots(v[:: 3], (255, 140, 30) if car.structure[name]["deforms"] else (40, 230, 140), 1)
    for _, v in g["wheels"].items():
        for part in v:
            dots(part[:: 6], (90, 90, 100))
    for rows, col in ((ccams.CAPTION_ROWS, (200, 60, 60)),):
        dr.rectangle([0, rows[0] * scale, W * scale, rows[1] * scale], outline=col)
    s = ccams.SAFE
    dr.rectangle([s["left"] * scale, s["top"] * scale, s["right"] * scale, s["bottom"] * scale], outline=(70, 110, 70))
    dr.text((4, 4), f"{frame} {seg['id']} s={ps['s']:.2f} x={xf:.1f}", fill=(255, 255, 255))
    return im


def sheet(frames: list[int], cols: int = 6, scale: float = 0.2) -> Image.Image:
    car = es.Car(es.load_fixture())
    ims = [frame_image(car, f, scale) for f in frames]
    w, h = ims[0].size
    rows = (len(ims) + cols - 1) // cols
    out = Image.new("RGB", (w * cols, h * rows), (0, 0, 0))
    for i, im in enumerate(ims):
        out.paste(im, ((i % cols) * w, (i // cols) * h))
    return out


if __name__ == "__main__":
    frames = [int(x) for x in sys.argv[2:]]
    sheet(frames).save(sys.argv[1])
