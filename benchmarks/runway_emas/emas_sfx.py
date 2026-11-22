"""EP.22 sound design (pure numpy, deterministic), built like EP.13-EP.21's: every sound is placed from the model and the timeline.
- the jet's engines (whine and roar, reverse thrust while it rolls) and the tyres on the runway;
- a deep thump as the nose gear and then the main gear drop into the bed;
- the bed crunching under the wheels, louder and brighter the faster the jet moves (from the model's speed), with chunks rattling;
- the engines spooling down after the stop; the tug and its reverse beeper in the clean-up time-lapse;
- wind off the bay, a whoosh on every cut and a low pulse.
Ducks under the narration; mixed to -15 LUFS with a peak limiter (helpers shared with EP.13-EP.21)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from benchmarks.guardrail_end.terminal_sfx import SR, _band_noise, _env, _place, db, limit, lufs, pitch_of, read_wav, whoosh, write_wav
from benchmarks.runway_emas import emas_motion as em
from benchmarks.runway_emas import emas_timeline as tl


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


def thump(rng, p=1.0):
    n = int(0.7 * SR / max(p, 0.4))
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * np.cumsum(60 * p * np.exp(-t / 0.18) + 28) / SR) + 0.5 * _band_noise(n, 80, 1500 * p, rng)) * _env(n, 0.003, 0.2 / max(p, 0.4))


def tick(rng, p=1.0):
    n = int(0.04 * SR)
    return _band_noise(n, 1200 * p, 8000, rng) * _env(n, 0.0005, 0.008)


def render_sfx(n_samples: int, narration: np.ndarray | None = None) -> tuple[np.ndarray, list]:
    rng = np.random.default_rng(2222)
    segs = tl.segments()
    t_film = np.arange(n_samples) / SR
    bed = np.zeros(n_samples)
    hits = np.zeros(n_samples)
    events = []

    def ev(at, sound, seg):
        events.append({"film_s": round(at, 3), "sound": sound, "segment": seg})

    t_nose = em.time_at(em.Y_BED - em.WHEELBASE)
    t_main = em.time_at(em.Y_BED)
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
        if v == "overrun":
            p = pitch_of(abs(s["time_scale"]))
            spd = np.interp(idx, grid, [em.speed(float(x)) / em.V0 for x in sim_sub])
            after = np.interp(idx, grid, [1.0 if x > em.stop_time() else 0.0 for x in sim_sub])
            spool = np.interp(idx, grid, [math.exp(-max(0.0, x - em.stop_time()) / 2.5) for x in sim_sub])
            whine = np.sin(2 * np.pi * (2600 * p * (0.55 + 0.45 * spool)) * seg_t) * 0.25
            roar = _band_noise(i1 - i0, 60 * p, 3000 * p, rng)
            bed[i0:i1] += db(-24) * (0.4 + 0.6 * spd) * (roar + whine) * (1 - after) + db(-28) * after * spool * (roar + whine)
            in_bed = np.interp(idx, grid, [1.0 if em.Y_BED <= em.main_y(float(x)) + em.WHEELBASE and em.speed(float(x)) > 0 else 0.0 for x in sim_sub])
            crunch = _band_noise(i1 - i0, 200 * p, 7000 * p, rng) * (0.5 + 0.5 * (np.sin(2 * np.pi * 17 * seg_t) > 0.2))
            bed[i0:i1] += db(-20) * in_bed * spd * crunch + db(-25) * in_bed * spd * _band_noise(i1 - i0, 40, 300 * p, rng)
            if in_bed.any():
                ev(s["t0"], "bed crunching", s["label"])
            for x, name in ((t_nose, "nose gear into the bed"), (t_main, "main gear into the bed")):
                ft = film_time_of(s, x)
                if ft is not None:
                    _place(hits, ft, thump(rng, p), db(-12))
                    ev(ft, name, s["label"])
            k = 0
            for x in np.arange(max(t_nose, s["sim0"]), min(em.stop_time(), s["sim1"]), 0.045):
                ft = film_time_of(s, float(x))
                if ft is not None and s["t0"] <= ft < s["t1"] and rng.random() < em.speed(float(x)) / em.V0:
                    _place(hits, ft, tick(rng, p), db(-25))
                    k += 1
            on_runway = np.interp(idx, grid, [1.0 if em.main_y(float(x)) + em.WHEELBASE < em.Y_BED else 0.0 for x in sim_sub])
            bed[i0:i1] += db(-26) * on_runway * spd * _band_noise(i1 - i0, 80, 900, rng)
        else:
            tug = _band_noise(i1 - i0, 50, 400, rng) + 0.3 * np.sin(2 * np.pi * 90 * seg_t)
            bed[i0:i1] += db(-28) * tug
            beep = (np.sin(2 * np.pi * 1000 * seg_t) * ((seg_t * 1.6) % 1.0 < 0.35))
            bed[i0:i1] += db(-34) * beep
            ev(s["t0"], "tug and beeper", s["label"])
    for s in segs[1:]:
        _place(bed, s["t0"] - 0.21, whoosh(rng), db(-26))
        ev(s["t0"], "cut whoosh", s["label"])
    wind = _band_noise(n_samples, 40, 600, rng) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.08 * t_film + 1.0) ** 2)
    bed += db(-35) * wind
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
    print(json.dumps(build(root / "examples/episodes/ep22-audio/narration.wav", out, tl.total_seconds()), indent=1))
