"""EP.21 sound design (pure numpy, deterministic), built like EP.13-EP.20's: every sound is placed from the model and the timeline.
- the boulder rumbling and tumbling down the slope, a thud where it hops off the bump;
- the hit: a deep thud, a crunch and the jangle of thousands of steel rings when the rock meets the net;
- the net and ropes groaning and the rings jingling while it stretches (from the model's speed);
- the brakes: a grinding screech whose loudness follows the power the brakes turn into heat;
- chips and pebbles landing after the hit; the red car passing on the road; tools ticking in the clean-up time-lapse;
- mountain wind, a whoosh on every cut and a low pulse.
Ducks under the narration; mixed to -15 LUFS with a peak limiter (helpers shared with EP.13-EP.20)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from benchmarks.guardrail_end.terminal_sfx import SR, _band_noise, _env, _place, db, impact, limit, lufs, pitch_of, read_wav, whoosh, write_wav
from benchmarks.rock_net import rocknet_motion as rm
from benchmarks.rock_net import rocknet_timeline as tl


def film_time_of(seg: dict, sim: float) -> float | None:
    lo_s, hi_s = min(seg["sim0"], seg["sim1"]), max(seg["sim0"], seg["sim1"])
    if not lo_s <= sim <= hi_s or hi_s - lo_s < 1e-9:
        return None
    lo, hi = seg["t0"], seg["t1"]
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if tl.sim_time(seg, mid) < sim:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def jangle(rng, p=1.0, dur=0.9):
    n = int(dur * SR / max(p, 0.4))
    t = np.arange(n) / SR
    tones = sum(np.sin(2 * np.pi * f * p * t + ph) * np.exp(-t / (0.12 + 0.3 * rng.random()))
                for f, ph in zip(rng.uniform(1800, 7000, 14), rng.uniform(0, 6.28, 14)))
    return (0.15 * tones + 0.6 * _band_noise(n, 2500 * p, 11000, rng) * np.exp(-t / 0.18)) * _env(n, 0.001, 0.5 / max(p, 0.4))


def thud(rng, p=1.0):
    n = int(0.6 * SR / max(p, 0.4))
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * np.cumsum(70 * p * np.exp(-t / 0.15) + 30) / SR) + 0.4 * _band_noise(n, 60, 900 * p, rng)) * _env(n, 0.002, 0.16 / max(p, 0.4))


def pebble(rng, p=1.0):
    n = int(0.05 * SR)
    return _band_noise(n, 1500 * p, 9000, rng) * _env(n, 0.0005, 0.01)


def render_sfx(n_samples: int, narration: np.ndarray | None = None) -> tuple[np.ndarray, list]:
    rng = np.random.default_rng(2121)
    segs = tl.segments()
    t_film = np.arange(n_samples) / SR
    bed = np.zeros(n_samples)
    hits = np.zeros(n_samples)
    events = []

    def ev(at, sound, seg):
        events.append({"film_s": round(at, 3), "sound": sound, "segment": seg})

    p_ref = max(rm.brake_power(x) for x in np.linspace(0.0, rm.stop_time(), 200)) + 1e-9
    for s in segs:
        v = s["variant"]
        i0, i1 = int(s["t0"] * SR), int(min(s["t1"] * SR, n_samples))
        if i1 <= i0:
            continue
        seg_t = t_film[i0:i1]
        sub = seg_t[::480]
        sim_sub = np.array([tl.sim_time(s, x) for x in sub])
        idx = np.arange(i1 - i0)
        grid = np.arange(0, i1 - i0, 480)[:len(sim_sub)]
        p = pitch_of(abs(s["time_scale"])) if v == "catch" else 1.0
        if v == "catch":
            rolling = np.interp(idx, grid, [1.0 if x < -rm.ROLL_T else 0.0 for x in sim_sub])
            bed[i0:i1] += db(-20) * rolling * _band_noise(i1 - i0, 25 * p + 10, 260 * p + 40, rng) * (0.6 + 0.4 * np.sin(2 * np.pi * 3.1 * seg_t) ** 2)
            for x, name, snd, g in ((-rm.ROLL_T, "rock hops off the bump", thud(rng, p), -10), (0.0, "rock hits the net", impact(p, rng, heavy=0.9), -10)):
                ft = film_time_of(s, x)
                if ft is not None:
                    _place(hits, ft, snd, db(g))
                    if x == 0.0:
                        _place(hits, ft, jangle(rng, p), db(-9))
                    ev(ft, name, s["label"])
            stretch = np.interp(idx, grid, [rm.rock_speed(x) / rm.V0 if 0.0 < x < rm.stop_time() else 0.0 for x in sim_sub])
            if stretch.any():
                creak = _band_noise(i1 - i0, 300 * p, 2400 * p, rng) * (0.5 + 0.5 * np.sin(2 * np.pi * 11 * seg_t) ** 2)
                chain = _band_noise(i1 - i0, 3000 * p, 11000, rng) * (np.sin(2 * np.pi * 23 * seg_t) > 0.6)
                bed[i0:i1] += db(-21) * stretch * creak + db(-25) * stretch * chain
                ev(s["t0"], "net stretching", s["label"])
            heat = np.interp(idx, grid, [min(1.0, rm.brake_power(x) / p_ref) for x in sim_sub])
            if heat.any():
                screech = np.sin(2 * np.pi * (1650 * p) * seg_t + 4 * np.sin(2 * np.pi * 9 * seg_t))
                bed[i0:i1] += db(-24) * heat * (0.7 * screech + _band_noise(i1 - i0, 700 * p, 4500 * p, rng))
                ev(s["t0"], "brakes grinding", s["label"])
            for k in range(14):                                                  # chips landing after the hit
                x = 0.35 + 0.09 * k + 0.05 * math.sin(k * 2.3)
                ft = film_time_of(s, x)
                if ft is not None and s["t0"] <= ft < s["t1"]:
                    _place(hits, ft, pebble(rng, p), db(-24))
            if s["flags"].get("car"):
                c = s["flags"]["car"]
                ys = np.interp(idx, grid, [c["y0"] + c["v"] * (x - s["sim0"]) for x in sim_sub])
                near = np.exp(-(ys / 25.0) ** 2)
                bed[i0:i1] += db(-27) * near * _band_noise(i1 - i0, 60, 1800, rng)
                ev(s["t0"], "car passing", s["label"])
        else:                                                                  # clean-up time-lapse
            for k in range(10):
                _place(hits, s["t0"] + 0.4 + 0.3 * k, pebble(rng, 0.6), db(-22))
            bed[i0:i1] += db(-30) * _band_noise(i1 - i0, 200, 2000, rng)
            ev(s["t0"], "clean-up", s["label"])
    for s in segs[1:]:
        _place(bed, s["t0"] - 0.21, whoosh(rng), db(-26))
        ev(s["t0"], "cut whoosh", s["label"])
    wind = _band_noise(n_samples, 40, 700, rng) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.09 * t_film + 1.0) ** 2)
    bed += db(-33) * wind
    beat = 60.0 / 96.0
    pulse = np.zeros(n_samples)
    kn = int(0.35 * SR)
    kick = np.sin(2 * np.pi * np.cumsum(55 * np.exp(-np.arange(kn) / SR / 0.08) + 42) / SR) * _env(kn, 0.003, 0.12)
    kk = 0.0
    while kk < t_film[-1]:
        _place(pulse, kk, kick, 1.0)
        kk += beat
    build = 0.55 + 0.45 * np.clip(t_film / t_film[-1], 0, 1)
    drone = (np.sin(2 * np.pi * 55 * t_film) + 0.6 * np.sin(2 * np.pi * 82.4 * t_film + 0.5)) * (0.7 + 0.3 * np.sin(2 * np.pi * 0.2 * t_film))
    bed += db(-34) * build * (0.8 * pulse + 0.35 * drone)

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
    print(json.dumps(build(root / "examples/episodes/ep21-audio/narration.wav", out, tl.total_seconds()), indent=1))
