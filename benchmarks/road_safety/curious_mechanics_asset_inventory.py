"""Read-only inventory of the pinned CC0 sedan scene's objects.

Does NOT render anything and does NOT modify the file. Prints every object
name/type/parent exactly as the source .blend ships them, before
render_curious_mechanics.py deletes everything outside the car hierarchy and
lights. Used to answer a concrete question: does this already-licensed CC0
asset contain any driver/interior/steering-wheel/seat geometry we could
reuse for a real action shot, without buying or rigging a new human model.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy

PINNED_SCENE_SHA256 = "a82e05825f907cc99678ab12855527552e34323b31ae801625af4a0f563ed877"


def arguments():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return p.parse_args(argv)


def main():
    args = arguments()
    digest = hashlib.sha256(args.source.read_bytes()).hexdigest()
    if digest != PINNED_SCENE_SHA256:
        raise ValueError(f"pinned car scene SHA mismatch: {digest}")
    bpy.ops.wm.open_mainfile(filepath=str(args.source))
    objects = []
    for ob in bpy.data.objects:
        objects.append({
            "name": ob.name,
            "type": ob.type,
            "parent": ob.parent.name if ob.parent else None,
            "mesh_vertices": len(ob.data.vertices) if ob.type == "MESH" and ob.data else None,
        })
    car = bpy.data.objects.get("CC0 detailed sedan animated as a rigid car")
    car_hierarchy = set()
    if car:
        car_hierarchy = {car.name, *(c.name for c in car.children_recursive)}
    outside_car = [o["name"] for o in objects if o["name"] not in car_hierarchy and o["type"] != "LIGHT"]
    interior_keywords = ("seat", "wheel", "dash", "steer", "interior", "cabin",
                          "human", "driver", "person", "figure", "body", "arm", "hand")
    candidates = sorted({
        o["name"] for o in objects
        if any(k in o["name"].lower() for k in interior_keywords)
        and o["name"] not in ("Front_tire", "Front_tire.001", "Rear_tire", "Rear_tire.001")
    })
    args.out.mkdir(parents=True, exist_ok=True)
    report = {
        "source_sha256": digest,
        "total_object_count": len(objects),
        "car_hierarchy_count": len(car_hierarchy),
        "objects_outside_car_hierarchy_and_not_light": outside_car,
        "name_matches_for_interior_or_human_keywords": candidates,
        "all_objects": objects,
    }
    (args.out / "asset-inventory.json").write_text(json.dumps(report, indent=2))
    print("ASSET_INVENTORY " + json.dumps({
        "total_object_count": report["total_object_count"],
        "outside_car_hierarchy": outside_car,
        "interior_or_human_keyword_matches": candidates,
    }), flush=True)


if __name__ == "__main__":
    main()
