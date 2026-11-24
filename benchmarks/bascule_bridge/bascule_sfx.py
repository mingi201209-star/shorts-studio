"""EP.25 sound design (pure numpy, deterministic), built like EP.13-EP.24's: every sound is placed from the model and the timeline.
- the city: traffic hum, wind, the river lapping at the walls;
- the warning bell while the gates come down, and the gates' motor;
- the bridge machinery while a leaf moves (from the model's angular speed): the electric motor's hum rising with the speed, the
  gears' rumble, steel creaking; a heavy clunk as the leaves unlock and start, and another as they stop at full open;
- the sailboat's engine (louder as it nears the camera's side) and one long blast of its horn as it comes up to the bridge;
- a whoosh on every cut and a quiet low pulse. Time-lapse shots keep the machinery's sound at its normal pitch.
Ducks under the narration; mixed to -15 LUFS with a peak limiter (helpers shared with EP.13-EP.24)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from benchmarks.bascule_bridge import bascule_motion as bm
from benchmarks.bascule_bridge import bascule_timeline as tl
from benchmarks.guardrail_end.terminal_sfx import SR, _band_noise, _env, _place, db, limit, lufs, read_wav, whoosh, write_wav

HORN_T = 101.2


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


def clunk(rng, size=1.0):
    n = int(1.2 * SR)
    t = np.arange(n) / SR
    body = np.sin(2 * np.pi * np.cumsum(55 / size * np.exp(-t / 0.3) + 28) / SR) * np.exp(-t / 0.5)
    ring = 0.35 * np.sin(2 * np.pi * 310 / size * t) * np.exp(-t / 0.35) + 0.2 * np.sin(2 * np.pi * 790 / size * t) * np.exp(-t / 0.2)
    return (body + ring + 0.5 * _band_noise(n, 60, 2500, rng) * np.exp(-t / 0.03)) * _env(n, 0.002, 1.0)


def bell(rng, n_rings):
    one = int(0.5 * SR)
    t = np.arange(one) / SR
    d = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t / tau) for f, a, tau in ((1180, 1.0, 0.25), (2950, 0.5, 0.12), (4400, 0.25, 0.06)))
    out = np.zeros(one * n_rings)
    for k in range(n_rings):
        out[k * one:(k + 1) * one] += d
    return out


def horn(rng, dur=2.4):
    n = int(dur * SR)
    t = np.arange(n) / SR
    tone = sum(a * np.sin(2 * np.pi * f * t + 0.3 * np.sin(2 * np.pi * 5 * t)) for f, a in ((233, 1.0), (466, 0.5), (699, 0.3), (932, 0.15)))
    return tone * _env(n, 0.08, 0.3)


def creak(rng):
    n = int(0.6 * SR)
    t = np.arange(n) / SR
    f0 = rng.uniform(90, 160)
    return np.sin(2 * np.pi * np.cumsum(f0 * (1 + 0.3 * np.sin(2 * np.pi * 7 * t))) / SR) * _env(n, 0.08, 0.35) * (0.6 + 0.4 * _band_noise(n, 80, 600, rng))


def render_sfx(n_samples: int, narration: np.ndarray | None = None) -> tuple[np.ndarray, list]:
    rng = np.random.default_rng(2525)
    segs = tl.segments()
    t_film = np.arange(n_samples) / SR
    bed = np.zeros(n_samples)
    hits = np.zeros(n_samples)
    events = []

    def ev(at, sound, seg):
        events.append({"film_s": round(at, 3), "sound": sound, "segment": seg})

    w_max = max(abs(bm.angular_speed(x)) for x in np.linspace(0, bm.T_OPEN, 200))
    for s in segs:
        i0, i1 = int(s["t0"] * SR), int(min(s["t1"] * SR, n_samples))
        if i1 <= i0:
            continue
        n = i1 - i0
        seg_t = t_film[i0:i1]
        sub = seg_t[::480]
        sims = np.array([tl.sim_time(s, x) for x in sub])
        idx = np.arange(n)
        grid = np.arange(0, n, 480)[:len(sims)]
        moving = np.interp(idx, grid, [abs(bm.angular_speed(float(x))) / w_max for x in sims])
        section = bool(s["flags"].get("section"))
        near = 1.4 if section else 1.0
        hum_f = 115.0
        hum = sum(a * np.sin(2 * np.pi * hum_f * k * seg_t) for k, a in ((1, 1.0), (2, 0.5), (3, 0.3), (5, 0.12)))
        bed[i0:i1] += db(-27) * near * moving * hum + db(-25) * near * moving * _band_noise(n, 35, 320, rng)
        if moving.max() > 0.05:
            ev(s["t0"], "bridge machinery running", s["label"])
            n_creak = int(max(1, (s["t1"] - s["t0"]) * 1.2))
            for k in range(n_creak):
                at = s["t0"] + (k + rng.uniform(0.2, 0.8)) * (s["t1"] - s["t0"]) / n_creak
                if abs(bm.angular_speed(tl.sim_time(s, at))) > 0.003:
                    _place(hits, at, creak(rng), db(-26))
        for x, name in ((bm.T_UP + 0.05, "leaves unlock and start"), (bm.T_UP + bm.T_OPEN - 0.3, "leaves stop at full open")):
            ft = film_time_of(s, x)
            if ft is not None:
                _place(hits, ft, clunk(rng), db(-13 if section else -17))
                ev(ft, name, s["label"])
        ft0, ft1 = film_time_of(s, max(bm.T_GATES, s["sim0"])), film_time_of(s, min(bm.T_GATES + 20.0, s["sim1"]))
        if ft0 is not None and ft1 is not None and ft1 - ft0 > 0.3:
            b = bell(rng, int((ft1 - ft0) / 0.5) + 1)
            _place(hits, ft0, b[: int((ft1 - ft0) * SR)], db(-25))
            ev(ft0, "warning bell", s["label"])
        ships = np.interp(idx, grid, [1.0 if bm.T_SHIP[0] < x < bm.T_SHIP[1] else 0.0 for x in sims])
        dist = np.interp(idx, grid, [abs(bm.ship_y(float(x))) for x in sims])
        eng = (_band_noise(n, 40, 400, rng) * (0.6 + 0.4 * np.sin(2 * np.pi * 9.0 * seg_t) ** 2))
        bed[i0:i1] += db(-30) * ships * eng / (1.0 + dist / 50.0)
        ft = film_time_of(s, HORN_T)
        if ft is not None:
            _place(hits, ft, horn(rng), db(-19))
            ev(ft, "sailboat horn", s["label"])
    for s in segs[1:]:
        _place(bed, s["t0"] - 0.21, whoosh(rng), db(-28))
        ev(s["t0"], "cut whoosh", s["label"])
    city = _band_noise(n_samples, 40, 500, rng) * (0.7 + 0.3 * np.sin(2 * np.pi * 0.05 * t_film) ** 2)
    lap = _band_noise(n_samples, 300, 2200, rng) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.6 * t_film) ** 2)
    wind = _band_noise(n_samples, 100, 1200, rng) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.08 * t_film + 1.0) ** 2)
    bed += db(-34) * city + db(-40) * lap + db(-39) * wind
    beat = 60.0 / 90.0
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
    print(json.dumps(build(root / "examples/episodes/ep25-audio/narration.wav", out, tl.total_seconds()), indent=1))
