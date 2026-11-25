"""EP.30 sound design (pure numpy, deterministic), built like EP.13-EP.29's: every sound is placed from the model and the timeline.
- the city's edge: distant traffic, wind, birds; the overhead wires' hum near the tracks;
- trains: the rumble, the wheels clicking over rail joints and the horn as one passes (before the window and after it);
- the turn: a deep groaning creak and the hydraulic jacks' pulse while the bridge moves (from the model's turning rate), a clunk as it
  starts and as it stops; time-lapse shots keep these at their normal pitch;
- the warning bell of the railway's window; a whoosh on every cut and a quiet low pulse.
Ducks under the narration; mixed to -15 LUFS with a peak limiter (helpers shared with EP.13-EP.29)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from benchmarks.guardrail_end.terminal_sfx import SR, _band_noise, _env, _place, db, limit, lufs, read_wav, whoosh, write_wav
from benchmarks.swivel_bridge import swivel_motion as sm
from benchmarks.swivel_bridge import swivel_timeline as tl


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


def clunk(rng):
    n = int(1.2 * SR)
    t = np.arange(n) / SR
    body = np.sin(2 * np.pi * np.cumsum(45 * np.exp(-t / 0.3) + 25) / SR) * np.exp(-t / 0.5)
    return (body + 0.4 * _band_noise(n, 50, 1500, rng) * np.exp(-t / 0.05)) * _env(n, 0.003, 1.0)


def horn(dur=1.6):
    n = int(dur * SR)
    t = np.arange(n) / SR
    tone = sum(a * np.sin(2 * np.pi * f * t) for f, a in ((311, 1.0), (392, 0.8), (622, 0.3)))
    return tone * _env(n, 0.05, 0.25)


def render_sfx(n_samples: int, narration: np.ndarray | None = None) -> tuple[np.ndarray, list]:
    rng = np.random.default_rng(3030)
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
        grid = np.arange(0, n, 240)
        sims = np.array([tl.sim_time(s, seg_t[0] + g / SR) for g in grid])
        rate = np.interp(idx, grid, [(sm.turned(float(x) + 5.0) - sm.turned(float(x) - 5.0)) / 10.0 / (sm.TURN / sm.T_TURN) for x in sims])
        rate = np.clip(rate, 0.0, 1.5)
        groan = np.sin(2 * np.pi * np.cumsum(38.0 + 10.0 * np.sin(2 * np.pi * 0.3 * seg_t)) / SR) * (0.6 + 0.4 * _band_noise(n, 1, 8, rng))
        pulse = (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 1.2 * seg_t))) * _band_noise(n, 200, 1200, rng)
        bed[i0:i1] += db(-25) * rate * (groan + 0.5 * pulse)
        if rate.max() > 0.2:
            ev(s["t0"], "bridge turning", s["label"])
        for x, name in ((1.0, "turn starts"), (sm.T_TURN - 1.0, "turn stops")):
            ft = film_time_of(s, x)
            if ft is not None:
                _place(hits, ft, clunk(rng), db(-16))
                ev(ft, name, s["label"])
        ft = film_time_of(s, sm.WINDOW[0] + 1.0)
        if ft is not None:
            ev(ft, "window bell", s["label"])
        for k in range(2):
            xs = [tl.train_x(k, float(x)) for x in sims]
            moving = np.interp(idx, grid, [0.0 if (x is None or (k == 1 and x == -420.0)) else 1.0 for x in xs])
            if moving.max() > 0.5:
                rumble = _band_noise(n, 30, 400, rng) + 0.5 * _band_noise(n, 800, 4000, rng)
                bed[i0:i1] += db(-20) * moving * rumble
                for j in range(int((s["t1"] - s["t0"]) * 6)):
                    m = int(0.02 * SR)
                    _place(hits, s["t0"] + (j + 0.5) / 6.0, _band_noise(m, 500, 6000, rng) * _env(m, 0.001, 0.4), db(-24))
                _place(hits, s["t0"] + 0.3, horn(), db(-20))
                ev(s["t0"], f"train {k} passing", s["label"])
    for s in segs[1:]:
        _place(bed, s["t0"] - 0.21, whoosh(rng), db(-28))
        ev(s["t0"], "cut whoosh", s["label"])
    city = _band_noise(n_samples, 40, 600, rng) * (0.7 + 0.3 * np.sin(2 * np.pi * 0.05 * t_film) ** 2)
    hum = np.sin(2 * np.pi * 100 * t_film) * 0.4 + _band_noise(n_samples, 90, 110, rng)
    bed += db(-34) * city + db(-44) * hum + db(-40) * _band_noise(n_samples, 100, 1200, rng)
    beat = 60.0 / 92.0
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
    print(json.dumps(build(root / "examples/episodes/ep30-audio/narration.wav", out, tl.total_seconds()), indent=1))
