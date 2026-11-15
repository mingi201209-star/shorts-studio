"""EP.03 speed bumps: composes the 1080x1920 film frames from the two rendered panels plus overlays (labels, hook text, true-scale body-height trace).

Everything drawn is derived from speed_bump_motion (same simulation that posed the cars, with the car's measured wheelbase). The trace is drawn at 1:1
(centimetres), never magnified. Peak numbers are simulation outputs for an ASSUMED car, labelled as such on screen.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from benchmarks.speed_bump import speed_bump_motion as sim

W, H = 1080, 1920
PANEL_H = 560
TOP_Y, BOT_Y = 0, 570           # hump panel, short-bump panel
TRACE = (0, 1140, 1080, 1400)   # x0, y0, x1, y1 of the trace area
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
HOOK_SECONDS = 1.6
COLORS = {"hump": (90, 200, 255), "short": (255, 170, 60)}


def font(size):
    try:
        return ImageFont.truetype(FONT, size)
    except OSError:
        return ImageFont.load_default()


def plate(draw, box, alpha_fill=(10, 14, 22, 200)):
    draw.rounded_rectangle(box, radius=14, fill=alpha_fill)


def text_c(draw, xy, txt, f, fill=(255, 255, 255)):
    w = draw.textlength(txt, font=f)
    draw.text((xy[0] - w / 2, xy[1]), txt, font=f, fill=fill)


class Timeline:
    def __init__(self, wheelbase: float):
        self.car = dict(sim.CAR, wheelbase=wheelbase)
        self.recs = {(s["id"], k): sim.simulate(b, speed_kmh=s["kmh"], car=self.car) for s in sim.SEGMENTS for k, b in sim.BUMPS.items()}
        self.peaks = sim.pass_summaries(self.car)
        # per segment: the sim time range shown and the time of each bump's peak acceleration
        self.range = {}
        self.peak_time = {}
        start = 1
        for s in sim.SEGMENTS:
            _, t0 = sim.frame_to_pass(start)
            _, t1 = sim.frame_to_pass(start + s["frames"] - 1)
            self.range[s["id"]] = (t0, t1)
            for k in sim.BUMPS:
                g = np.abs(self.recs[(s["id"], k)]["gf"])
                self.peak_time[(s["id"], k)] = float(self.recs[(s["id"], k)]["t"][int(np.argmax(g))])
            start += s["frames"]

    def body_cm(self, seg_id: str, bump: str, t: float) -> float:
        r = self.recs[(seg_id, bump)]
        return 100.0 * float(np.interp(t, r["t"], r["body"]))


def draw_trace(img, tl: Timeline, seg, t_sim, frame):
    d = ImageDraw.Draw(img, "RGBA")
    x0, y0, x1, y1 = TRACE
    plate(d, (x0 + 20, y0 + 8, x1 - 20, y1 - 8))
    f = font(22)
    d.text((x0 + 40, y0 + 14), "BODY HEIGHT, TRUE SCALE (cm)", font=f, fill=(210, 220, 235))
    px0, px1, py0, py1 = x0 + 110, x1 - 50, y0 + 60, y1 - 38
    lo, hi = -2.0, 7.0                     # cm
    def Y(c): return py1 - (c - lo) / (hi - lo) * (py1 - py0)
    for c in (0, 2, 4, 6):
        d.line((px0, Y(c), px1, Y(c)), fill=(255, 255, 255, 50 if c else 120), width=1)
        d.text((px0 - 56, Y(c) - 12), f"{c}", font=font(20), fill=(200, 210, 225))
    ta, tb = tl.range[seg["id"]]
    def X(t): return px0 + (t - ta) / (tb - ta) * (px1 - px0)
    ts = np.linspace(ta, t_sim, 80)
    for k, col in COLORS.items():
        pts = [(X(t), Y(tl.body_cm(seg["id"], k, float(t)))) for t in ts]
        if len(pts) > 1:
            d.line(pts, fill=col + (255,), width=4)
        d.ellipse((pts[-1][0] - 6, pts[-1][1] - 6, pts[-1][0] + 6, pts[-1][1] + 6), fill=col + (255,))
    d.text((px0 + 8, py0 - 4), "LONG HUMP", font=font(22), fill=COLORS["hump"] + (255,))
    d.text((px0 + 200, py0 - 4), "SHORT BUMP", font=font(22), fill=COLORS["short"] + (255,))
    d.text((x0 + 40, y1 - 34), "SIMULATION, ASSUMED CAR - NOT A MEASUREMENT", font=font(18), fill=(190, 200, 215))


def compose_card(frame: int, tl: Timeline) -> Image.Image:
    """Frames after the last pass: bars of PEAK BODY ACCELERATION for both bumps at 10/20/30 km/h (simulation values, assumed car)."""
    n = frame - sim.PASS_FRAMES            # 1..320
    img = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle((0, 0, W, 1400), fill=(14, 20, 32))
    text_c(d, (W / 2, 70), "PEAK BODY ACCELERATION", font(54), fill=(255, 255, 255))
    text_c(d, (W / 2, 138), "same car, same 7.5 cm height (simulation, assumed values)", font(26), fill=(190, 200, 215))
    x_base, y_base, y_top, gmax = 120, 1180, 330, 1.2
    grow = min(1.0, n / 75.0)
    grow = 1 - (1 - grow) ** 3
    for gv in (0.0, 0.4, 0.8, 1.2):
        y = y_base - gv / gmax * (y_base - y_top)
        d.line((x_base - 20, y, W - 60, y), fill=(255, 255, 255, 60), width=1)
        d.text((40, y - 14), f"{gv:.1f} g", font=font(24), fill=(200, 210, 225))
    speeds = [("C", 10), ("A", 20), ("B", 30)]
    group_w = (W - 60 - x_base) / 3
    for i, (sid, kmh) in enumerate(speeds):
        gx = x_base + i * group_w
        for j, key in enumerate(("hump", "short")):
            val = tl.peaks[sid][key]["peak_body_g"]
            hgt = val / gmax * (y_base - y_top) * grow
            bx0 = gx + 40 + j * 150
            d.rectangle((bx0, y_base - hgt, bx0 + 120, y_base), fill=COLORS[key] + (255,))
            if grow >= 1.0:
                text_c(d, (bx0 + 60, y_base - hgt - 40), f"{val:.2f}", font(34), fill=(255, 255, 255))
        text_c(d, (gx + group_w / 2 - 10, y_base + 22), f"{kmh} km/h", font(38), fill=(255, 255, 255))
    plate(d, (120, 1272, 460, 1330))
    d.rectangle((140, 1290, 170, 1312), fill=COLORS["hump"] + (255,))
    d.text((184, 1286), "LONG HUMP 3.7 m", font=font(26), fill=(255, 255, 255))
    plate(d, (500, 1272, 1000, 1330))
    d.rectangle((520, 1290, 550, 1312), fill=COLORS["short"] + (255,))
    d.text((564, 1286), "SHORT BUMP 0.9 m", font=font(26), fill=(255, 255, 255))
    sweep = int((n * 7) % (W + 200)) - 100            # a thin moving highlight keeps every frame unique and the chart alive
    d.rectangle((sweep, 200, sweep + 3, 1200), fill=(255, 255, 255, 38))
    if frame >= 801:
        text_c(d, (W / 2, 1340), "SHAPE CHANGES THE RIDE", font(44), fill=(255, 220, 120))
    return img


def compose(frame: int, hump: Image.Image | None, short: Image.Image | None, tl: Timeline) -> Image.Image:
    if frame > sim.PASS_FRAMES:
        return compose_card(frame, tl)
    seg, t_sim = sim.frame_to_pass(frame)
    img = Image.new("RGB", (W, H), (0, 0, 0))
    img.paste(hump.resize((W, PANEL_H), Image.LANCZOS), (0, TOP_Y))
    img.paste(short.resize((W, PANEL_H), Image.LANCZOS), (0, BOT_Y))
    d = ImageDraw.Draw(img, "RGBA")
    for key, y in (("hump", TOP_Y), ("short", BOT_Y)):
        b = sim.BUMPS[key]
        plate(d, (24, y + 20, 24 + 520, y + 100))
        d.text((42, y + 26), b["label"], font=font(34), fill=COLORS[key] + (255,))
        d.text((42, y + 66), f"{b['length']:.1f} m long, {b['height'] * 100:.1f} cm high", font=font(22), fill=(225, 230, 240))
        if t_sim >= tl.peak_time[(seg["id"], key)]:
            peak = tl.peaks[seg["id"]][key]["peak_body_g"]
            plate(d, (W - 24 - 500, y + PANEL_H - 80, W - 24, y + PANEL_H - 16))
            d.text((W - 24 - 480, y + PANEL_H - 70), f"PEAK BODY ACCEL {peak:.2f} g", font=font(30), fill=COLORS[key] + (255,))
    plate(d, (W - 24 - 360, 20, W - 24, 100))
    d.text((W - 24 - 340, 24), f"{seg['kmh']:.0f} km/h", font=font(44), fill=(255, 255, 255))
    d.text((W - 24 - 340, 74), f"SLOW MOTION x{seg['slow']:.2f}", font=font(20), fill=(200, 210, 225))
    if frame <= int(HOOK_SECONDS * sim.FPS):
        fade = 1.0 if frame < int(HOOK_SECONDS * sim.FPS) - 8 else max(0.0, (int(HOOK_SECONDS * sim.FPS) - frame) / 8)
        plate(d, (40, 540, W - 40, 640), alpha_fill=(10, 14, 22, int(235 * fade)))
        text_c(d, (W / 2, 566), "SAME CAR. SAME SPEED.", font(58), fill=(255, 255, 255))
    draw_trace(img, tl, seg, t_sim, frame)
    return img


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--panels", type=Path, required=True, help="folder with shard subfolders holding bump-proof.json and the panel PNGs")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    proofs = sorted(args.panels.rglob("bump-proof.json"))
    if not proofs:
        raise SystemExit("no panel shards")
    sha = None
    wheelbase = None
    index: dict[tuple[int, str], Path] = {}
    import hashlib
    for pp in proofs:
        proof = json.loads(pp.read_text())
        if sha is None:
            sha, wheelbase = proof["renderer_source_sha256"], proof["geometry"]["wheelbase"]
        elif proof["renderer_source_sha256"] != sha or proof["geometry"]["wheelbase"] != wheelbase:
            raise SystemExit("mixed renderer/geometry across shards")
        for c in proof["checksums"]:
            path = pp.parent / f"frame_{c['frame']:04d}_{c['panel']}.png"
            if hashlib.sha256(path.read_bytes()).hexdigest() != c["sha256"]:
                raise SystemExit(f"panel hash mismatch {path}")
            index[(c["frame"], c["panel"])] = path
    missing = [f for f in range(1, sim.PASS_FRAMES + 1) if (f, "hump") not in index or (f, "short") not in index]
    if missing:
        raise SystemExit(f"MISSING_PANELS {missing[:10]}")
    tl = Timeline(wheelbase)
    args.out.mkdir(parents=True, exist_ok=True)
    for f in range(1, sim.TOTAL_FRAMES + 1):
        if f > sim.PASS_FRAMES:
            compose(f, None, None, tl).save(args.out / f"frame_{f:04d}.png")
        else:
            compose(f, Image.open(index[(f, "hump")]).convert("RGB"), Image.open(index[(f, "short")]).convert("RGB"), tl).save(args.out / f"frame_{f:04d}.png")
    (args.out / "compose-info.json").write_text(json.dumps({
        "renderer_source_sha256": sha, "wheelbase": wheelbase, "peaks": tl.peaks,
        "peak_time": {f"{a}:{b}": t for (a, b), t in tl.peak_time.items()}, "physically_calibrated": False}, indent=1))
    print("SPEEDBUMP_COMPOSED", len(index) // 2, flush=True)


if __name__ == "__main__":
    main()
