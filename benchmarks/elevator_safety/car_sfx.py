"""EP.37 sound design (pure numpy, deterministic), built like EP.13-EP.36's. For now the opening only (it is EP.36's teaser):
- the broken hoist rope ends whipping and twanging above the car;
- the safety gear's wedges grinding down the guide rails, sparks crackling, both following the car's speed (pitched down with the
  slow motion);
- the car brought to a stop with a heavy steel clunk, then the frame creaking and cooling ticks;
- the channel's low pulse and drone under it all.
The rest of the film's sound is added with the rest of the film, without changing the opening's."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from benchmarks.elevator_safety import car_motion as m
from benchmarks.elevator_safety import car_timeline as tl
from benchmarks.guardrail_end.terminal_sfx import SR, _band_noise, _env, _place, db, impact, pitch_of, write_wav


def twang(rng, p=1.0):
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    ring = sum(a * np.sin(2 * np.pi * f * p * (1.0 - 0.25 * t) * t) * np.exp(-t / d) for f, a, d in ((95, 0.9, 0.3), (260, 0.5, 0.18), (700, 0.3, 0.08)))
    return 0.7 * ring + 0.6 * _band_noise(n, 1200 * p, 7000 * p + 400, rng) * _env(n, 0.0005, 0.02)


def render_opening(n_samples: int) -> tuple[np.ndarray, list]:
    rng = np.random.default_rng(3737)
    segs = tl.segments(opening_only=True)
    t_film = np.arange(n_samples) / SR
    bed = np.zeros(n_samples)
    hits = np.zeros(n_samples)
    events = []
    rows = m.fall()
    ts = np.array([r[0] for r in rows])
    vs = np.array([r[2] for r in rows])
    grip_t = next(r[0] for r in rows if r[4] == "grip")
    for s in segs:
        i0, i1 = int(s["t0"] * SR), int(min(s["t1"] * SR, n_samples))
        if i1 <= i0:
            continue
        seg_t = t_film[i0:i1]
        scale = (s["sim1"] - s["sim0"]) / (s["t1"] - s["t0"])
        p = pitch_of(abs(scale))
        sim = s["sim0"] + (seg_t - s["t0"]) * scale
        v = np.interp(sim, ts, vs, right=0.0)
        grip = ((sim >= grip_t) & (v > 0)).astype(float)
        u = np.clip(v / 3.2, 0, 1)
        grind = _band_noise(i1 - i0, 500 * p + 80, 5500 * p + 400, rng) * (0.6 + 0.4 * np.abs(np.sin(2 * np.pi * 23 * seg_t)))
        crackle = _band_noise(i1 - i0, 2500, 10000, rng) * (rng.random(i1 - i0) < 0.015)
        bed[i0:i1] += grip * np.sqrt(u) * (db(-15) * grind + db(-19) * crackle * 6)
        air = _band_noise(i1 - i0, 120 * p + 40, 1500 * p + 200, rng)
        bed[i0:i1] += db(-24) * u * air
        if grip.any():
            events.append({"film_s": round(s["t0"], 3), "sound": "the wedges grind down the guide rails, sparks crackle", "segment": s["label"]})
        if s["label"] == "A1-caught":
            for k, at in enumerate((0.0, 0.35, 0.8)):
                _place(hits, at, twang(rng, max(p, 0.5) * (1.0 + 0.1 * k)), db(-14 - 3 * k))
            events.append({"film_s": 0.0, "sound": "the broken rope ends whip and twang", "segment": s["label"]})
            at = s["t0"] + (m.stop_time() - s["sim0"]) / scale
            if at < s["t1"]:
                _place(hits, at, impact(0.55, rng, heavy=1.8), db(-10))
                events.append({"film_s": round(at, 3), "sound": "the car stops with a heavy clunk", "segment": s["label"]})
        else:
            for k in range(5):
                _place(hits, s["t0"] + 0.1 + 0.17 * k, _band_noise(int(0.04 * SR), 3000, 9000, rng) * _env(int(0.04 * SR), 0.001, 0.01), db(-28))
            events.append({"film_s": round(s["t0"], 3), "sound": "the frame creaks, metal ticks as it cools", "segment": s["label"]})
    beat = 60.0 / 96.0
    pulse = np.zeros(n_samples)
    kn = int(0.35 * SR)
    kick = np.sin(2 * np.pi * np.cumsum(55 * np.exp(-np.arange(kn) / SR / 0.08) + 42) / SR) * _env(kn, 0.003, 0.12)
    k = 0.0
    while k < t_film[-1]:
        _place(pulse, k, kick, 1.0)
        k += beat
    drone = (np.sin(2 * np.pi * 55 * t_film) + 0.6 * np.sin(2 * np.pi * 82.4 * t_film + 0.5)) * (0.7 + 0.3 * np.sin(2 * np.pi * 0.2 * t_film))
    bed += db(-31) * 0.6 * (0.8 * pulse + 0.35 * drone)
    out = bed + hits
    peak = np.max(np.abs(out)) + 1e-9
    if peak > db(-3):
        out *= db(-3) / peak
    return out, events


def build_opening(out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    n = int(round(tl.opening_seconds() * SR))
    fx, events = render_opening(n)
    write_wav(out_dir / "sfx.wav", fx)
    (out_dir / "sfx-events.json").write_text(json.dumps(events, indent=1))
    return {"seconds": round(n / SR, 3), "events": len(events)}


if __name__ == "__main__":
    import sys
    print(json.dumps(build_opening(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("sfx-out")), indent=1))
