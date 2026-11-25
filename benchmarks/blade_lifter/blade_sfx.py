"""EP.29 sound design (pure numpy, deterministic), built like EP.13-EP.28's: every sound is placed from the model and the timeline.
- the mountain in the morning: wind in the trees, birds; in the wind shot a gale with gusts howling past the raised blade;
- the football-field comparison: a referee's whistle, birds; no rig sounds;
- the rig: the tractor's diesel at a crawl (louder near the camera), the trailer's many tyres on the asphalt, the lifter's hydraulic
  whine while the blade tilts or swings (from blade_motion's tilt and swing rates), a soft creak from the blade;
- a whoosh on every cut and a quiet low pulse.
Ducks under the narration; mixed to -15 LUFS with a peak limiter (helpers shared with EP.13-EP.28)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from benchmarks.blade_lifter import blade_motion as bm
from benchmarks.blade_lifter import blade_timeline as tl
from benchmarks.guardrail_end.terminal_sfx import SR, _band_noise, _env, _place, db, limit, lufs, read_wav, whoosh, write_wav


def bird(rng):
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    f0 = rng.uniform(2500, 3800)
    return np.sin(2 * np.pi * np.cumsum(f0 * (1 + 0.15 * np.sin(2 * np.pi * rng.uniform(12, 22) * t))) / SR) * _env(n, 0.02, 0.12)


def creak(rng):
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    f0 = rng.uniform(70, 120)
    return np.sin(2 * np.pi * np.cumsum(f0 * (1 + 0.25 * np.sin(2 * np.pi * 6 * t))) / SR) * _env(n, 0.06, 0.3)


def render_sfx(n_samples: int, narration: np.ndarray | None = None) -> tuple[np.ndarray, list]:
    rng = np.random.default_rng(2929)
    segs = tl.segments()
    t_film = np.arange(n_samples) / SR
    bed = np.zeros(n_samples)
    hits = np.zeros(n_samples)
    events = []

    def ev(at, sound, seg):
        events.append({"film_s": round(at, 3), "sound": sound, "segment": seg})

    for s in segs:
        i0, i1 = int(s["t0"] * SR), int(min(s["t1"] * SR, n_samples))
        if i1 <= i0:
            continue
        n = i1 - i0
        seg_t = t_film[i0:i1]
        idx = np.arange(n)
        grid = np.arange(0, n, 480)
        sims = np.array([tl.sim_time(s, seg_t[0] + g / SR) for g in grid])
        wind = bool(s["flags"].get("wind"))
        cam = tl.cam_world({"cam": s["cam_a"], "t": float(sims[0]), "wind": wind})
        rates, dist = [], []
        for x in sims:
            sx = tl.WIND_S if wind else bm.s_of(float(x))
            a0, a1 = bm.alpha(sx - 0.3), bm.alpha(sx + 0.3)
            p0, p1 = bm.psi(sx - 0.3), bm.psi(sx + 0.3)
            rates.append(0.0 if wind else (abs(a1 - a0) + abs(p1 - p0)) / (0.6 / bm.V))
            p, _ = bm.at(sx)
            dist.append(math.dist((p[0], p[1]), (cam[0], cam[1])))
        rate = np.interp(idx, grid, np.clip(np.array(rates) / math.radians(4.0), 0, 1))
        near = np.interp(idx, grid, [1.0 / (1.0 + d / 20.0) for d in dist])
        moving = 0.0 if wind else 1.0
        diesel = (np.sin(2 * np.pi * 48 * seg_t) + 0.5 * np.sin(2 * np.pi * 96 * seg_t + 0.4)) * (0.7 + 0.3 * np.sin(2 * np.pi * 7.5 * seg_t) ** 2)
        bed[i0:i1] += db(-22) * near * (0.7 * diesel + 0.6 * _band_noise(n, 40, 300, rng)) * (0.6 + 0.4 * moving)
        bed[i0:i1] += db(-30) * near * moving * _band_noise(n, 300, 2500, rng)
        whine = np.sin(2 * np.pi * np.cumsum(300.0 + 200.0 * rate) / SR)
        bed[i0:i1] += db(-28) * near * rate * (0.6 * whine + _band_noise(n, 500, 3000, rng))
        if rate.max() > 0.3:
            ev(s["t0"] + float(np.argmax(rate > 0.3)) / SR, "lifter hydraulics", s["label"])
        if s["flags"].get("field"):                                         # the football field: a referee's whistle, no rig
            m_ = int(0.55 * SR)
            tw = np.arange(m_) / SR
            whistle = np.sin(2 * np.pi * np.cumsum(2900.0 + 60.0 * np.sign(np.sin(2 * np.pi * 28 * tw))) / SR) * _env(m_, 0.01, 0.08)
            _place(hits, s["t0"] + 0.35, whistle, db(-24))
            ev(s["t0"] + 0.35, "referee's whistle", s["label"])
        else:
            for _ in range(int((s["t1"] - s["t0"]) * 0.5)):
                _place(hits, s["t0"] + rng.uniform(0, s["t1"] - s["t0"]), creak(rng), db(-34))
        if wind:
            gust = 0.6 + 0.4 * np.sin(2 * np.pi * 0.35 * seg_t) ** 2
            howl = np.sin(2 * np.pi * np.cumsum(420.0 + 120.0 * np.sin(2 * np.pi * 0.35 * seg_t)) / SR)
            bed[i0:i1] += db(-22) * gust * (_band_noise(n, 100, 2500, rng) + 0.25 * howl)
            ev(s["t0"], "gale", s["label"])
        else:
            for _ in range(int((s["t1"] - s["t0"]) * 0.8)):
                _place(bed, s["t0"] + rng.uniform(0, s["t1"] - s["t0"]), bird(rng), db(-40))
    for s in segs[1:]:
        _place(bed, s["t0"] - 0.21, whoosh(rng), db(-28))
        ev(s["t0"], "cut whoosh", s["label"])
    bed += db(-38) * _band_noise(n_samples, 80, 1200, rng) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.08 * t_film + 1.0) ** 2)
    beat = 60.0 / 94.0
    pulse = np.zeros(n_samples)
    kn = int(0.35 * SR)
    kick = np.sin(2 * np.pi * np.cumsum(55 * np.exp(-np.arange(kn) / SR / 0.08) + 42) / SR) * _env(kn, 0.003, 0.12)
    kk = 0.0
    while kk < t_film[-1]:
        _place(pulse, kk, kick, 1.0)
        kk += beat
    build = 0.55 + 0.45 * np.clip(t_film / t_film[-1], 0, 1)
    drone = (np.sin(2 * np.pi * 55 * t_film) + 0.6 * np.sin(2 * np.pi * 82.4 * t_film + 0.5)) * (0.7 + 0.3 * np.sin(2 * np.pi * 0.2 * t_film))
    bed += db(-35) * build * (0.8 * pulse + 0.35 * drone)
    gain = np.ones(n_samples)
    if narration is not None:
        e = np.sqrt(np.convolve(narration[:n_samples] ** 2, np.ones(1440) / 1440, mode="same"))
        e = np.convolve(e, np.ones(9600) / 9600, mode="same")
        gain = 1.0 - 0.6 * np.clip(e / 0.03, 0, 1)
    out = bed * gain + hits * (0.55 + 0.45 * gain)
    peak = np.max(np.abs(out)) + 1e-9
    if peak > db(-3):
        out *= db(-3) / peak
    return out, events


def build(narration_wav: Path, out_dir: Path, seconds: float, sfx_gain_db: float = -2.0, target_lufs: float = -15.0) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    narr = read_wav(narration_wav)
    n = int(round(seconds * SR))
    narr = np.pad(narr, (0, max(0, n - len(narr))))[:n]
    fx, events = render_sfx(n, narr)
    mix = limit(narr + db(sfx_gain_db) * fx)
    write_wav(out_dir / "mix.wav", mix)
    for _ in range(3):
        i_lufs, _tp = lufs(out_dir / "mix.wav")
        if abs(i_lufs - target_lufs) < 0.3:
            break
        mix = limit(mix * db(target_lufs - i_lufs), ceiling_db=-2.0)
        write_wav(out_dir / "mix.wav", mix)
    i_lufs, tp = lufs(out_dir / "mix.wav")
    write_wav(out_dir / "sfx.wav", fx)
    (out_dir / "sfx-events.json").write_text(json.dumps(events, indent=1))
    beats = json.loads(tl.AUDIO.read_text())["beats"]
    worst = 99.0
    for b in beats:
        i0, i1 = int(b["start"] * SR), int(b["end"] * SR)
        r_n = np.sqrt(np.mean(narr[i0:i1] ** 2)) + 1e-9
        r_s = np.sqrt(np.mean((db(sfx_gain_db) * fx[i0:i1]) ** 2)) + 1e-9
        worst = min(worst, 20 * math.log10(r_n / r_s))
    return {"events": len(events), "speech_over_effects_db_min": round(worst, 1), "mix_lufs": i_lufs, "mix_true_peak_dbfs": tp,
            "mix_peak_dbfs": round(20 * math.log10(np.max(np.abs(mix)) + 1e-9), 2)}


if __name__ == "__main__":
    import sys
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("sfx-out")
    root = Path(__file__).resolve().parents[2]
    print(json.dumps(build(root / "examples/episodes/ep29-audio/narration.wav", out, tl.total_seconds()), indent=1))
