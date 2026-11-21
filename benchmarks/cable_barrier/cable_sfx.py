"""EP.15 sound design (pure numpy, deterministic), built like EP.14's: every sound is placed from the model and the timeline.
- the hit: a heavy body thud plus a deep steel 'twang' of the ropes at first contact (the opening frame lands just after it, so the
  opening gets the twang's tail; the loop run-in gets the whole hit);
- a metallic clank for every post as it folds over, at the film moment it folds;
- a low steel groan while the ropes stretch, and turf and tyre scrub while the car slides along the median;
- tyre roar on the approach shots, a pass-by swell for the oncoming car;
- a whoosh on every cut, wind and a low pulse.
Ducks under the narration; mixed to -15 LUFS with a peak limiter (helpers shared with EP.13/EP.14)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from benchmarks.cable_barrier import cable_motion as cm
from benchmarks.cable_barrier import cable_timeline as tl
from benchmarks.guardrail_end.terminal_sfx import SR, _band_noise, _env, _place, db, impact, limit, lufs, pitch_of, read_wav, whoosh, write_wav
from benchmarks.tempered_glass.glass_sfx import film_time_of, mix_sigs


def twang(rng, p=1.0):
    n = int(1.6 * SR)
    t = np.arange(n) / SR
    f0 = 62 * p
    wob = 1 + 0.03 * np.exp(-t / 0.3) * np.sin(2 * np.pi * 7 * t)
    ring = sum(a * np.sin(2 * np.pi * np.cumsum(f0 * k * wob) / SR) * np.exp(-t / d) for k, a, d in ((1, 1.0, 0.55), (2.03, 0.5, 0.4), (3.1, 0.3, 0.25), (5.2, 0.15, 0.15)))
    return ring + 0.3 * _band_noise(n, 1500, 7000, rng) * _env(n, 0.001, 0.03)


def clank(rng, p=1.0):
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    out = sum(a * np.sin(2 * np.pi * f * p * t) * np.exp(-t / d) for f, a, d in ((410, 0.7, 0.12), (1170, 0.45, 0.08), (2630, 0.25, 0.05)))
    return out + 0.5 * _band_noise(n, 300, 5000, rng) * _env(n, 0.001, 0.015)


def groan(n, rng):
    t = np.arange(n) / SR
    f = 48 + 10 * np.sin(2 * np.pi * 0.7 * t)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * (0.6 + 0.4 * _band_noise(n, 2, 12, rng) / 0.3) * 0.5 + 0.3 * _band_noise(n, 80, 400, rng)


def _sim_track(s, t_film):
    i0, i1 = int(s["t0"] * SR), int(s["t1"] * SR)
    seg_t = t_film[i0:i1]
    sub = seg_t[::480]
    sim = np.interp(seg_t, sub, np.array([tl.sim_time(s, x) for x in sub]))
    return i0, i1, sim


def render_sfx(n_samples: int, narration: np.ndarray | None = None) -> tuple[np.ndarray, list]:
    rng = np.random.default_rng(1515)
    segs = tl.segments()
    t_film = np.arange(n_samples) / SR
    bed = np.zeros(n_samples)
    hits = np.zeros(n_samples)
    events = []
    by = {s["label"]: s for s in segs}

    def ev(at, sound, seg):
        events.append({"film_s": round(at, 3), "sound": sound, "segment": seg})

    def hit(p):
        return mix_sigs((0.8, impact(p, rng, heavy=0.8)), (0.9, twang(rng, p)))

    # first contact: the opening lands on the ropes already taut (twang tail), the shots that show the moment get the whole hit
    p_open = pitch_of(abs(by["A1-caught"]["time_scale"]))
    _place(hits, 0.0, twang(rng, p_open), db(-7))
    ev(0.0, "rope twang", "A1-caught")
    for s in segs:
        if s["label"] == "A1-caught":
            continue
        at = film_time_of(s, 0.0)
        if at is not None and s["t0"] - 1e-6 <= at < s["t1"]:
            _place(hits, at, hit(pitch_of(abs(s["time_scale"]))), db(-6))
            ev(at, "car hits the ropes", s["label"])

    # posts fold
    folds = [f for f in cm.post_fold_times() if f is not None]
    for s in segs:
        p = pitch_of(abs(s["time_scale"]))
        for f in folds:
            ft = film_time_of(s, f)
            if ft is not None and s["t0"] <= ft < s["t1"]:
                _place(hits, ft, clank(rng, p), db(-13))
                ev(ft, "post folds", s["label"])

    # ropes stretching (groan) and the car scrubbing over the turf
    for s in segs:
        if s["sim1"] <= 0.0 and s["sim0"] <= 0.0:
            continue
        i0, i1, sim = _sim_track(s, t_film)
        depth = np.array([cm.state(float(x))["depth"] for x in sim[::480]])
        depth = np.interp(np.arange(i1 - i0), np.arange(0, i1 - i0, 480)[:len(depth)], depth)
        speed = np.array([math.hypot(cm.state(float(x))["vx"], cm.state(float(x))["vy"]) for x in sim[::480]])
        speed = np.interp(np.arange(i1 - i0), np.arange(0, i1 - i0, 480)[:len(speed)], speed)
        p = pitch_of(abs(s["time_scale"]))
        bed[i0:i1] += db(-17) * np.clip(depth / cm.D_MAX, 0, 1) * groan(i1 - i0, rng) * min(1.0, 1.0 / max(p, 0.3))
        on_grass = (sim > 0).astype(float)
        bed[i0:i1] += db(-22) * on_grass * np.clip(speed / 15, 0, 1) * _band_noise(i1 - i0, 200 * p + 60, 3000 * p + 500, rng)

    # approach: tyre roar while the car is driving (before contact)
    for s in segs:
        i0, i1, sim = _sim_track(s, t_film)
        before = (sim < 0).astype(float)
        if before.any():
            bed[i0:i1] += db(-24) * before * _band_noise(i1 - i0, 60, 1200, rng)

    # oncoming car passes: a swell in the shot that shows it
    s = by["B-oncoming"]
    n = int((s["t1"] - s["t0"]) * SR)
    tt = np.arange(n) / SR
    sw = np.exp(-((tt - 0.75 * (s["t1"] - s["t0"])) / 0.7) ** 2)
    _place(bed, s["t0"], db(-19) * sw * _band_noise(n, 90, 2500, rng), 1.0)
    ev(s["t0"] + 0.75 * (s["t1"] - s["t0"]), "oncoming pass-by", s["label"])

    # cut whooshes, wind, low pulse
    for s in segs[1:]:
        _place(bed, s["t0"] - 0.21, whoosh(rng), db(-26))
        ev(s["t0"], "cut whoosh", s["label"])
    wind = _band_noise(n_samples, 40, 500, rng) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.11 * t_film + 1.0) ** 2)
    bed += db(-36) * wind
    beat = 60.0 / 96.0
    pulse = np.zeros(n_samples)
    kn = int(0.35 * SR)
    kick = np.sin(2 * np.pi * np.cumsum(55 * np.exp(-np.arange(kn) / SR / 0.08) + 42) / SR) * _env(kn, 0.003, 0.12)
    k = 0.0
    while k < t_film[-1]:
        _place(pulse, k, kick, 1.0)
        k += beat
    build = 0.55 + 0.45 * np.clip(t_film / t_film[-1], 0, 1)
    drone = (np.sin(2 * np.pi * 55 * t_film) + 0.6 * np.sin(2 * np.pi * 82.4 * t_film + 0.5)) * (0.7 + 0.3 * np.sin(2 * np.pi * 0.2 * t_film))
    bed += db(-31) * build * (0.8 * pulse + 0.35 * drone)

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
    print(json.dumps(build(root / "examples/episodes/ep15-audio/narration.wav", out, tl.total_seconds()), indent=1))
