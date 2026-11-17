"""EP.04 partial render check: only a few frames were rendered (the ones a change touched). Compares what Blender really produced for those frames (telemetry/evidence) with the
pure-Python model (evidence_sim) and builds a contact sheet for a person to look at. If Blender and the model agree, every numeric check that tests run on the model for the
WHOLE timeline can be trusted without rendering the whole timeline again."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path

from PIL import Image

from benchmarks.crumple_zone import crumple_motion as cm
from benchmarks.crumple_zone import evidence_sim as es

TOL = {"nose_mm": 3.0, "overlap": 0.05, "stroke_m": 1e-4}


import os
TILE_W = int(os.environ.get("EP04_SHEET_TILE", "180"))      # contact-sheet tile width in pixels (height = 16/9 of it)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--panels", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    car = es.Car(es.load_fixture())
    recs = {k: cm.simulate(k) for k in cm.PROFILES}
    paths, telemetry, evidence = {}, {}, {}
    for pp in sorted(a.panels.rglob("crumple-proof.json")):
        proof = json.loads(pp.read_text())
        for c in proof["checksums"]:
            path = pp.parent / f"frame_{c['frame']:04d}_{c['panel']}.png"
            assert hashlib.sha256(path.read_bytes()).hexdigest() == c["sha256"], path
            paths[(c["frame"], c["panel"])] = path
        for t in proof["telemetry"]:
            telemetry[t["frame"]] = t
        evidence.update({int(k): v for k, v in proof["evidence"].items()})
    problems, rows = [], []
    for f in sorted(evidence):
        model = es.frame_evidence(car, recs, f)
        blender = evidence[f]
        for panel, mp in model["panels"].items():
            t = telemetry[f][panel]
            d_nose = abs(t["nose_world_y_mm"] - mp["nose_world_y_mm"])
            d_stroke = abs(t["stroke_m"] - mp["stroke_m"])
            row = {"frame": f, "panel": panel, "nose_diff_mm": round(d_nose, 2), "stroke_diff_m": round(d_stroke, 6)}
            if d_nose > TOL["nose_mm"]:
                problems.append(f"frame {f} {panel}: nose position differs between Blender and the model by {d_nose:.1f} mm")
            if d_stroke > TOL["stroke_m"]:
                problems.append(f"frame {f} {panel}: stroke differs by {d_stroke:.5f} m")
            rows.append(row)
        for name, mv in model["in_view"].items():
            if name in blender["in_view"] and bool(blender["in_view"][name]) != bool(mv):
                problems.append(f"frame {f}: '{name}' in view: Blender {blender['in_view'][name]}, model {mv}")
        d_cap = abs(blender["metrics"]["caption.overlap"] - model["metrics"]["caption.overlap"])
        if d_cap > TOL["overlap"]:
            problems.append(f"frame {f}: caption overlap Blender {blender['metrics']['caption.overlap']} vs model {model['metrics']['caption.overlap']:.3f}")
        bad = max(blender["metrics"].get("nose.penetration_mm", 0.0), 0.0)
        if bad > 5.0:
            problems.append(f"frame {f}: Blender measured {bad:.1f} mm of penetration")
    # contact sheet of what was rendered (composed like the film: full layout, or stack with CRUMPLE on top)
    tiles = []
    for f in sorted(evidence):
        seg = cm.segment_at(f)
        im = Image.new("RGB", (360, 640))
        for panel in cm.visible_panels(f):
            src = Image.open(paths[(f, panel)]).convert("RGB")
            im.paste(src.resize((360, 640)), (0, 0))
        tiles.append(im.resize((TILE_W, TILE_W * 16 // 9)))
    cols = 8
    th = TILE_W * 16 // 9
    sheet = Image.new("RGB", (cols * TILE_W, ((len(tiles) + cols - 1) // cols) * th))
    for k, t in enumerate(tiles):
        sheet.paste(t, ((k % cols) * TILE_W, (k // cols) * th))
    sheet_path = a.out / "range-sheet.jpg"
    sheet.save(sheet_path, quality=80)
    report = {"status": "FAIL" if problems else "PASS", "problems": problems, "frames": sorted(evidence), "max_nose_diff_mm": max((r["nose_diff_mm"] for r in rows), default=0.0),
              "note": "partial render: Blender and the Python model agree on these frames" if not problems else "model and Blender disagree"}
    (a.out / "range-report.json").write_text(json.dumps(report, indent=1))
    print("RANGE_REPORT " + json.dumps(report), flush=True)
    print("SHEET_B64_START\n" + base64.b64encode(sheet_path.read_bytes()).decode() + "\nSHEET_B64_END", flush=True)
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
