"""Blender script: writes the pinned CC0 sedan's real geometry (as loaded and re-rigged by the EP.04 renderer) to a compact fixture so that mesh/crush/camera checks can run
as plain Python tests, without Blender: every mesh's vertices in the car frame (root space, +Y forward), whether it belongs to a wheel, the wheel centres and the measured geometry."""
from __future__ import annotations

import argparse
import base64
import gzip
import json
import sys
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    a = p.parse_args(argv)
    root, body, wheels, geom = base.load_source_car(a.source)
    bpy.context.view_layer.update()
    wheel_nodes = {w["node"]: k for k, w in wheels.items()}
    parts = []
    for ob in root.children_recursive:
        if ob.type != "MESH":
            continue
        anc, wheel = ob.parent, None
        while anc is not None:
            if anc in wheel_nodes:
                wheel = wheel_nodes[anc]
                break
            anc = anc.parent
        n = len(ob.data.vertices)
        co = np.zeros(n * 3)
        ob.data.vertices.foreach_get("co", co)
        m = np.array(ob.matrix_world)
        world = co.reshape(n, 3) @ m[:3, :3].T + m[:3, 3]
        parts.append({"name": ob.name, "wheel": wheel, "verts": np.round(world, 4).tolist()})
    fixture = {"geometry": geom, "wheels": {k: [round(float(w["base"].x), 4), round(float(w["base"].y), 4), round(float(w["base"].z), 4)] for k, w in wheels.items()},
               "parts": parts}
    blob = base64.b64encode(gzip.compress(json.dumps(fixture, separators=(",", ":")).encode(), 9)).decode()
    print("MESH_FIXTURE_START")
    for i in range(0, len(blob), 4000):
        print("MF " + blob[i:i + 4000])
    print("MESH_FIXTURE_END")
    print("MESH_FIXTURE_PARTS", len(parts), sum(len(q["verts"]) for q in parts), flush=True)


main()
