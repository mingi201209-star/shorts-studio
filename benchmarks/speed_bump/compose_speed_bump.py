"""EP.03 speed bumps: stacks the rendered 3D images into the 1080x1920 film frames. Nothing is drawn here (no text, no graphs): hump and short-bump renders
are placed next to each other. Layout "stack": hump (0,0) and short bump (0,700), 1080x700 each; layout "side": hump (0,0) and short bump (540,0), 540x1400
each. The black band below row 1400 is the caption area."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image

from benchmarks.speed_bump import speed_bump_motion as sim
from benchmarks.speed_bump.speed_bump_timeline import Timeline

W, H = 1080, 1920
PLACE = {"stack": {"hump": (0, 0, 1080, 960), "short": (0, 960, 1080, 960)},
         "side": {"hump": (0, 0, 540, 1920), "short": (540, 0, 540, 1920)}}


def stack_frame(layout: str, images: dict[str, Path]) -> Image.Image:
    img = Image.new("RGB", (W, H), (0, 0, 0))
    for panel, path in images.items():
        x, y, w, h = PLACE[layout][panel]
        im = Image.open(path).convert("RGB")
        if im.size != (w, h):
            im = im.resize((w, h), Image.LANCZOS)      # preflight renders are smaller; production renders are exact
        img.paste(im, (x, y))
    return img


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--panels", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    proofs = sorted(args.panels.rglob("bump-proof.json"))
    if not proofs:
        raise SystemExit("no shards")
    sha = wheelbase = None
    signs, gap_mm = {}, 0.0
    index: dict[tuple[int, str], Path] = {}
    for pp in proofs:
        proof = json.loads(pp.read_text())
        if not proof.get("all_3d") or proof.get("overlays") != "none":
            raise SystemExit("shard was not produced by the overlay-free 3D renderer")
        if sha is None:
            sha, wheelbase = proof["renderer_source_sha256"], proof["geometry"]["wheelbase"]
        elif proof["renderer_source_sha256"] != sha or proof["geometry"]["wheelbase"] != wheelbase:
            raise SystemExit("mixed renderer/geometry across shards")
        for t in proof["telemetry"]:
            signs[t["frame"]] = {k: bool(t[k].get("sign_in_view")) for k in ("hump", "short")}
            gap_mm = max(gap_mm, t["hump"].get("wheel_gap_mm", 0.0), t["short"].get("wheel_gap_mm", 0.0))
        for c in proof["checksums"]:
            path = pp.parent / f"frame_{c['frame']:04d}_{c['panel']}.png"
            if hashlib.sha256(path.read_bytes()).hexdigest() != c["sha256"]:
                raise SystemExit(f"hash mismatch {path}")
            index[(c["frame"], c["panel"])] = path
    missing = [(f, k) for f in range(1, sim.TOTAL_FRAMES + 1) for k in ("hump", "short") if (f, k) not in index]
    if missing:
        raise SystemExit(f"MISSING_RENDERS {missing[:10]}")
    args.out.mkdir(parents=True, exist_ok=True)
    for f in range(1, sim.TOTAL_FRAMES + 1):
        _, layout = sim.shot_at(f)
        stack_frame(layout, {k: index[(f, k)] for k in ("hump", "short")}).save(args.out / f"frame_{f:04d}.png")
    tl = Timeline(wheelbase)
    (args.out / "compose-info.json").write_text(json.dumps({
        "renderer_source_sha256": sha, "wheelbase": wheelbase, "peaks": tl.peaks, "all_3d": True, "overlays": "none", "physically_calibrated": False,
        "sign_in_view": {str(k): v for k, v in sorted(signs.items())}, "rendered_wheel_gap_mm_max": gap_mm,
        "peak_time": {f"{a}:{b}": t for (a, b), t in tl.peak_time.items()}}, indent=1))
    print("SPEEDBUMP_COMPOSED", sim.TOTAL_FRAMES, flush=True)


if __name__ == "__main__":
    main()
