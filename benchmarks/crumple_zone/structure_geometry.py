"""EP.04 X-ray structure geometry as pure numpy (used by the Blender renderer and by the Python tests): crush rails, bumper beam and the passenger safety cell, in the car frame."""
from __future__ import annotations

import math

import numpy as np

from benchmarks.crumple_zone import crumple_motion as cm


def tube_vertices(p0, p1, radius: float, n_seg: int = 48, n_ring: int = 8) -> np.ndarray:
    a, b = np.array(p0, float), np.array(p1, float)
    axis = b - a
    length = float(np.linalg.norm(axis))
    axis /= length
    helper = np.array([0.0, 0.0, 1.0]) if abs(axis[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    e1 = np.cross(axis, helper)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(axis, e1)
    verts = []
    for i in range(n_seg + 1):
        c = a + axis * length * i / n_seg
        for j in range(n_ring):
            ang = 2 * math.pi * j / n_ring
            verts.append(c + radius * (math.cos(ang) * e1 + math.sin(ang) * e2))
    return np.array(verts)


def tube_faces(n_seg: int, n_ring: int = 8) -> list[tuple]:
    return [(i * n_ring + j, i * n_ring + (j + 1) % n_ring, (i + 1) * n_ring + (j + 1) % n_ring, (i + 1) * n_ring + j) for i in range(n_seg) for j in range(n_ring)]


def structure(nose: float) -> dict:
    """name -> {'p0', 'p1', 'radius', 'n_seg'} for the deforming structure and the rigid cell edges."""
    cabin_y = nose - cm.CRUSH_LENGTH
    items = {}
    for sx in (-0.38, 0.38):
        items[f"rail {sx}"] = {"p0": (sx, nose - 0.10, 0.47), "p1": (sx, cabin_y - 0.55, 0.47), "radius": 0.05, "n_seg": 64, "deforms": True}
    items["bumper beam"] = {"p0": (-0.62, nose - 0.12, 0.50), "p1": (0.62, nose - 0.12, 0.50), "radius": 0.055, "n_seg": 24, "deforms": True}
    hx, y1, y0, z0, z1 = 0.74, cabin_y - 0.05, cabin_y - 1.95, 0.40, 1.22
    k = 0
    for xs in (-hx, hx):
        for zs in (z0, z1):
            items[f"cell {k}"] = {"p0": (xs, y0, zs), "p1": (xs, y1, zs), "radius": 0.028, "n_seg": 2, "deforms": False}
            k += 1
        for ys in (y0, y1):
            items[f"cell {k}"] = {"p0": (xs, ys, z0), "p1": (xs, ys, z1), "radius": 0.028, "n_seg": 2, "deforms": False}
            k += 1
    for zs in (z0, z1):
        for ys in (y0, y1):
            items[f"cell {k}"] = {"p0": (-hx, ys, zs), "p1": (hx, ys, zs), "radius": 0.028, "n_seg": 2, "deforms": False}
            k += 1
    return items
