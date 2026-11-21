"""EP.14 sound design (pure numpy, deterministic), built like EP.13's: every sound is placed from the model and the timeline.
- the burst: a deep slow-motion shatter on the opening frame and again when the hammer lands at the loop seam;
- a ping for every cube (and a clink for every shard) as it lands on the road, at the film moment it lands;
- furnace roar, and the hiss of the air knives while the pane is under them;
- slow creaks while the cross-section builds up its stress;
- a glassy thunk each time the steel ball bounces off the tempered pane;
- a low hum that swells while the pane glows with locked-in stress, a tick at the hammer's touch and a crackle that gets denser as the
  crack front runs, then a soft 'whump' as the diced pane lets go;
- a stone's tock and a short crackle on the windshield; hammer swings; a whoosh on every cut; wind and a low pulse.
Ducks under the narration; mixed to -15 LUFS with a peak limiter (helpers shared with EP.13)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from benchmarks.guardrail_end.terminal_sfx import SR, _band_noise, _env, _place, db, glass, impact, limit, lufs, pitch_of, read_wav, whoosh, write_wav
from benchmarks.tempered_glass import glass_motion as gm
from benchmarks.tempered_glass import glass_timeline as tl


def mix_sigs(*parts):
    """Sum signals of different lengths (each (gain, signal))."""
    n = max(len(sig) for _, sig in parts)
    out = np.zeros(n)
    for g, sig in parts:
        out[:len(sig)] += g * sig
    return out


def burst(p, rng):
    return mix_sigs((0.9, glass(p, rng)), (0.7, impact(p, rng, heavy=0.6)))


def ping(rng, p=1.0, f=None):
    n = int(0.12 * SR)
    t = np.arange(n) / SR
    f = (f or rng.uniform(3200, 7800)) * p
    return np.sin(2 * np.pi * f * t) * np.exp(-t / (0.035 / max(p, 0.4))) * rng.uniform(0.4, 1.0)


def clink(rng, p=1.0):
    n = int(0.4 * SR)
    t = np.arange(n) / SR
    out = sum(a * np.sin(2 * np.pi * f * p * t) * np.exp(-t / d) for f, a, d in ((2100, 0.6, 0.18), (3900, 0.4, 0.12), (6100, 0.25, 0.08)))
    return out + 0.4 * _band_noise(n, 2000, 9000, rng) * _env(n, 0.001, 0.02)


def thunk(rng):
    n = int(1.0 * SR)
    t = np.arange(n) / SR
    low = np.sin(2 * np.pi * 95 * t) * _env(n, 0.002, 0.09)
    ring = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t / d) for f, a, d in ((1130, 0.5, 0.45), (2610, 0.3, 0.3), (4330, 0.18, 0.2)))
    return 0.9 * low + 0.45 * ring + 0.2 * _band_noise(n, 800, 6000, rng) * _env(n, 0.001, 0.01)


def tick(rng):
    n = int(0.08 * SR)
    return _band_noise(n, 2500, 12000, rng) * _env(n, 0.0003, 0.006)


def landing_times() -> np.ndarray:
    """Simulated time at which each cube first reaches the road."""
    vel, _, start = gm._launch()
    z0, vz = start[:, 2] - gm.THICK, vel[:, 2]
    return gm.T_RELEASE + (vz + np.sqrt(vz * vz + 2 * gm.G * np.maximum(z0, 0.0))) / gm.G


def shard_landing_times() -> np.ndarray:
    vel, _, start = gm._shard_launch()
    z0, vz = start[:, 2] - 0.02, vel[:, 2]
    return gm.T_RELEASE + (vz + np.sqrt(vz * vz + 2 * gm.G * np.maximum(z0, 0.0))) / gm.G


def film_time_of(seg: dict, sim: float) -> float | None:
    lo_s, hi_s = min(seg["sim0"], seg["sim1"]), max(seg["sim0"], seg["sim1"])
    if not lo_s <= sim <= hi_s:
        return None
    lo, hi = seg["t0"], seg["t1"]
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if tl.sim_time(seg, mid) < sim:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def render_sfx(n_samples: int, narration: np.ndarray | None = None) -> tuple[np.ndarray, list]:
    rng = np.random.default_rng(1414)
    segs = tl.segments()
    t_film = np.arange(n_samples) / SR
    bed = np.zeros(n_samples)
    hits = np.zeros(n_samples)
    events = []
    by = {s["label"]: s for s in segs}

    def ev(at, sound, seg):
        events.append({"film_s": round(at, 3), "sound": sound, "segment": seg})

    # the burst on the opening frame and at the hammer's touch in the loop run-in
    p_open = pitch_of(abs(by["A1-burst"]["time_scale"]))
    _place(hits, 0.0, burst(p_open, rng), db(-5))
    ev(0.0, "burst", "A1-burst")
    n_seg = by["N-loop-run-in"]
    at = film_time_of(n_seg, 0.0)
    if at is not None:
        _place(hits, at, tick(rng), db(-8))
        _place(hits, at + 0.02, burst(p_open, rng), db(-7))
        ev(at, "hammer touch + burst", n_seg["label"])

    # cubes landing on the road; shards landing
    lt = landing_times()
    for name in ("A2-raining-cubes", "G1-blunt-cubes"):
        s = by[name]
        p = pitch_of(abs(s["time_scale"]))
        times = sorted(ft for ft in (film_time_of(s, x) for x in lt) if ft is not None)
        for ft in times[:: max(1, len(times) // 140)]:
            _place(hits, ft, ping(rng, p), db(-24))
        if times:
            ev(times[0], f"{len(times)} cubes land", name)
    s = by["G2-knife-shards"]
    for x in shard_landing_times():
        ft = film_time_of(s, x)
        if ft is not None:
            _place(hits, ft, clink(rng, pitch_of(abs(s["time_scale"]))), db(-14))
            ev(ft, "shard lands", s["label"])

    # tempering: furnace roar and the air knives
    s = by["B-tempering"]
    i0, i1 = int(s["t0"] * SR), int(s["t1"] * SR)
    seg_t = t_film[i0:i1]
    sim = np.array([tl.sim_time(s, x) for x in seg_t[::480]])
    sim = np.interp(seg_t, seg_t[::480], sim)
    bed[i0:i1] += db(-24) * _band_noise(i1 - i0, 50, 400, rng)
    air = np.clip((sim + 0.3) / 0.25, 0, 1)
    bed[i0:i1] += db(-20) * air * _band_noise(i1 - i0, 1800, 9000, rng)
    ev(film_time_of(s, -0.3) or s["t0"], "air knives on", s["label"])

    # stress: slow creaks in the cross-section
    for name in ("C1-surface-sets", "C2-core-squeezes"):
        s = by[name]
        t = s["t0"] + 0.3
        while t < s["t1"] - 0.2:
            n = int(0.25 * SR)
            cr = _band_noise(n, 150, 900, rng) * _env(n, 0.01, 0.07)
            _place(hits, t, cr, db(-22))
            t += rng.uniform(0.35, 0.7)

    # ball bounces
    s = by["D-four-times"]
    xs = np.arange(s["sim0"], s["sim1"], 0.0005)
    hs = np.array([gm.ball_state(float(x))[0] for x in xs])
    for i in range(1, len(xs) - 1):
        if hs[i] < 0.01 and hs[i] <= hs[i - 1] and hs[i] < hs[i + 1]:      # the ball's lowest point: a bounce
            ft = film_time_of(s, float(xs[i]))
            if ft is not None:
                _place(hits, ft, thunk(rng), db(-8))
                ev(ft, "ball bounces", s["label"])

    # locked-in energy: hum, then the touch and the crackle of the crack front, then the release
    s = by["E1-locked-in"]
    i0, i1 = int(s["t0"] * SR), int(s["t1"] * SR)
    tt = t_film[i0:i1] - s["t0"]
    f = 70 + 40 * tt / (s["t1"] - s["t0"])
    hum = np.sin(2 * np.pi * np.cumsum(f) / SR) * (0.5 + 0.5 * np.sin(2 * np.pi * 1.6 * (tt + s["t0"])) ** 2)
    bed[i0:i1] += db(-20) * hum * np.minimum(1, tt / 0.6)
    for name in ("E2-lets-go", "F-mile-per-second"):
        s = by[name]
        at = film_time_of(s, 0.0)
        if at is None:
            at = s["t0"]
        _place(hits, at, tick(rng), db(-6))
        t_end = film_time_of(s, gm.T_RELEASE - 1e-6) or s["t1"]
        t = at + 0.02
        while t < min(t_end, s["t1"]):
            frac = (t - at) / max(t_end - at, 1e-3)
            _place(hits, t, tick(rng), db(-20 + 8 * frac))
            t += max(0.012, 0.09 * (1 - frac) ** 2)
        ev(at, "touch + crackle", name)
        rel = film_time_of(s, gm.T_RELEASE)
        if rel is not None:
            n = int(0.8 * SR)
            whump = np.sin(2 * np.pi * np.cumsum(70 * np.exp(-np.arange(n) / SR / 0.2) + 30) / SR) * _env(n, 0.004, 0.25)
            _place(hits, rel, mix_sigs((1.0, whump), (0.4, _band_noise(n, 500, 6000, rng) * _env(n, 0.002, 0.08))), db(-9))
            ev(rel, "pane lets go", name)

    # windshield: stone tock and a short crackle
    s = by["H-windshield"]
    at = film_time_of(s, 0.0)
    if at is not None:
        n = int(0.6 * SR)
        tt = np.arange(n) / SR
        tock = np.sin(2 * np.pi * 620 * tt) * np.exp(-tt / 0.05) + 0.6 * _band_noise(n, 1500, 7000, rng) * _env(n, 0.0005, 0.02)
        _place(hits, at, tock, db(-8))
        t = at + 0.05
        while t < at + 1.6:
            _place(hits, t, tick(rng), db(-22))
            t += rng.uniform(0.03, 0.12)
        ev(at, "stone hits the windshield", s["label"])

    # hammer swings (the approach of the tip, in the shots that show it)
    for name in ("E1-locked-in", "I-hammer"):
        s = by[name]
        _place(bed, s["t1"] - 0.45, whoosh(rng), db(-18))

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
    print(json.dumps(build(root / "examples/episodes/ep14-audio/narration.wav", out, tl.total_seconds()), indent=1))
