"""EP.28 sound design (pure numpy, deterministic), built like EP.13-EP.27's: every sound is placed from the model and the timeline.
- outside: a park in the evening (wind, birds, a distant town); inside the silo: a ventilation hum; in the tunnel: a low rumble and
  the carriers clicking over rail joints;
- the hero carriage: an electric drive whose whine follows its climbing speed, a softer whir while it turns, the fork's servo while
  it reaches out and back, a clunk each time a car is set down or lifted off its rails;
- a whoosh on every cut and a quiet low pulse.
Ducks under the narration; mixed to -15 LUFS with a peak limiter (helpers shared with EP.13-EP.27)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from benchmarks.car_tower import tower_motion as tm
from benchmarks.car_tower import tower_timeline as tl
from benchmarks.guardrail_end.terminal_sfx import SR, _band_noise, _env, _place, db, limit, lufs, read_wav, whoosh, write_wav


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
    n = int(0.6 * SR)
    t = np.arange(n) / SR
    body = np.sin(2 * np.pi * np.cumsum(90 * np.exp(-t / 0.08) + 50) / SR) * np.exp(-t / 0.15)
    ring = 0.3 * np.sin(2 * np.pi * 620 * t) * np.exp(-t / 0.12)
    return (body + ring + 0.4 * _band_noise(n, 200, 4000, rng) * np.exp(-t / 0.02)) * _env(n, 0.002, 0.4)


def bird(rng):
    n = int(0.3 * SR)
    t = np.arange(n) / SR
    f0 = rng.uniform(2800, 4200)
    return np.sin(2 * np.pi * np.cumsum(f0 * (1 + 0.12 * np.sin(2 * np.pi * rng.uniform(15, 25) * t))) / SR) * _env(n, 0.02, 0.1)


def speeds(t: float) -> tuple[float, float, float]:
    """The hero carriage's climbing speed (m/s), turning speed (rad/s) and fork speed (m/s) at story time t."""
    a, b = tm.carriage(t - 0.05), tm.carriage(t + 0.05)
    return abs(b["z"] - a["z"]) / 0.1, abs(b["th"] - a["th"]) / 0.1, abs(b["r"] - a["r"]) / 0.1


def render_sfx(n_samples: int, narration: np.ndarray | None = None) -> tuple[np.ndarray, list]:
    rng = np.random.default_rng(2828)
    segs = tl.segments()
    t_film = np.arange(n_samples) / SR
    bed = np.zeros(n_samples)
    hits = np.zeros(n_samples)
    events = []

    def ev(at, sound, seg):
        events.append({"film_s": round(at, 3), "sound": sound, "segment": seg})

    hands = [m["hand"] for m in tm.schedule() if "hand" in m]
    for s in segs:
        i0, i1 = int(s["t0"] * SR), int(min(s["t1"] * SR, n_samples))
        if i1 <= i0:
            continue
        n = i1 - i0
        seg_t = t_film[i0:i1]
        idx = np.arange(n)
        grid = np.arange(0, n, 240)
        sims = np.array([tl.sim_time(s, seg_t[0] + g / SR) for g in grid])
        sp = np.array([speeds(float(x)) for x in sims])
        climb = np.interp(idx, grid, sp[:, 0] / tm.V_LIFT)
        turn = np.interp(idx, grid, sp[:, 1] / tm.W_TURN)
        fork = np.interp(idx, grid, sp[:, 2] / tm.V_FORK)
        cam = tl.cam_world({"cam": s["cam_a"], "t": float(sims[0])})
        inside = math.hypot(cam[0], cam[1]) < tm.R_GLASS + 0.5 or cam[2] < -0.3
        near = 1.0 if inside else 0.45
        whine = np.sin(2 * np.pi * np.cumsum(220.0 + 260.0 * climb) / SR) + 0.4 * np.sin(2 * np.pi * np.cumsum(440.0 + 520.0 * climb) / SR)
        bed[i0:i1] += db(-26) * near * climb * (0.6 * whine + _band_noise(n, 60, 500, rng))
        whir = np.sin(2 * np.pi * np.cumsum(130.0 + 60.0 * turn) / SR)
        bed[i0:i1] += db(-30) * near * turn * (0.6 * whir + _band_noise(n, 100, 900, rng))
        servo = np.sin(2 * np.pi * np.cumsum(520.0 + 180.0 * fork) / SR)
        bed[i0:i1] += db(-29) * near * fork * (0.6 * servo + _band_noise(n, 400, 2500, rng))
        if climb.max() > 0.2:
            ev(s["t0"], "carriage drive", s["label"])
        if fork.max() > 0.2:
            ev(s["t0"], "fork servo", s["label"])
        for h in hands:
            ft = film_time_of(s, h)
            if ft is not None:
                _place(hits, ft, clunk(rng), db(-17 if inside else -24))
                ev(ft, "car set down / lifted", s["label"])
        if cam[2] < -0.3:
            rumble = _band_noise(n, 30, 220, rng)
            bed[i0:i1] += db(-30) * rumble
            for k in range(int((s["t1"] - s["t0"]) * 2.2)):
                m = int(0.03 * SR)
                _place(hits, s["t0"] + (k + 0.3) / 2.2, _band_noise(m, 800, 5000, rng) * _env(m, 0.001, 0.4), db(-30))
            ev(s["t0"], "tunnel rumble", s["label"])
        if inside:
            bed[i0:i1] += db(-36) * _band_noise(n, 60, 700, rng)
        else:
            bed[i0:i1] += db(-37) * _band_noise(n, 80, 1200, rng) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.1 * seg_t) ** 2)
            for _ in range(int((s["t1"] - s["t0"]) * 0.8)):
                _place(bed, s["t0"] + rng.uniform(0, s["t1"] - s["t0"]), bird(rng), db(-40))
    for s in segs[1:]:
        _place(bed, s["t0"] - 0.21, whoosh(rng), db(-28))
        ev(s["t0"], "cut whoosh", s["label"])
    beat = 60.0 / 100.0
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
    print(json.dumps(build(root / "examples/episodes/ep28-audio/narration.wav", out, tl.total_seconds()), indent=1))
