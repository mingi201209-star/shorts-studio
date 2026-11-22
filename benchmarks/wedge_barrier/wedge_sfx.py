"""EP.18 sound design (pure numpy, deterministic), built like EP.13-EP.17's: every sound is placed from the model and the timeline.
- the plate: a hydraulic hiss and whine while it swings up and a heavy steel clank when it locks at the top;
- the car: engine and tyre roar while it drives in, then the crash at the moment of contact (deep boom, metal crunch, glass), a
  tinkle for every piece of glass and plastic that lands, the car's rear dropping back onto its wheels;
- the truck: a lower, longer crash; the force shot: a deep rumble while the load goes into the foundation;
- a whoosh on every cut, wind and a low pulse.
Ducks under the narration; mixed to -15 LUFS with a peak limiter (helpers shared with EP.13-EP.17)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from benchmarks.guardrail_end.terminal_sfx import SR, _band_noise, _env, _place, db, glass, impact, limit, lufs, pitch_of, read_wav, whoosh, write_wav
from benchmarks.tempered_glass.glass_sfx import film_time_of, mix_sigs
from benchmarks.wedge_barrier import wedge_motion as wm
from benchmarks.wedge_barrier import wedge_timeline as tl


def clank(rng, p=1.0):
    n = int(0.7 * SR)
    t = np.arange(n) / SR
    ring = sum(a * np.sin(2 * np.pi * f * p * t) * np.exp(-t / d) for f, a, d in ((180, 0.9, 0.18), (530, 0.5, 0.12), (1240, 0.3, 0.07)))
    return ring + 0.6 * _band_noise(n, 200, 4000, rng) * _env(n, 0.001, 0.02)


def tinkle(rng, p=1.0):
    n = int(0.15 * SR)
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * rng.uniform(2500, 6000) * p * t) * np.exp(-t / 0.03) * rng.uniform(0.4, 1.0)


def crash(rng, p=1.0, heavy=1.0):
    return mix_sigs((1.0, impact(p, rng, heavy=heavy)), (0.7, glass(p, rng)))


def render_sfx(n_samples: int, narration: np.ndarray | None = None) -> tuple[np.ndarray, list]:
    rng = np.random.default_rng(1818)
    segs = tl.segments()
    t_film = np.arange(n_samples) / SR
    bed = np.zeros(n_samples)
    hits = np.zeros(n_samples)
    events = []

    def ev(at, sound, seg):
        events.append({"film_s": round(at, 3), "sound": sound, "segment": seg})

    for s in segs:
        i0, i1 = int(s["t0"] * SR), int(min(s["t1"] * SR, n_samples))
        seg_t = t_film[i0:i1]
        sub = seg_t[::480]
        sim = np.interp(seg_t, sub, np.array([tl.sim_time(s, x) for x in sub]))
        p = pitch_of(abs(s["time_scale"]))
        truck = s["variant"] == "truck"
        # hydraulics while the plate rises
        rising = ((sim > wm.RISE_START) & (sim < wm.RISE_START + wm.RISE_TIME)).astype(float)
        if rising.any():
            bed[i0:i1] += db(-20) * rising * (_band_noise(i1 - i0, 2500 * p + 300, 9000 * p + 800, rng) + 0.5 * np.sin(2 * np.pi * 420 * p * seg_t))
        lock = film_time_of(s, wm.RISE_START + wm.RISE_TIME)
        if lock is not None and s["t0"] <= lock < s["t1"]:
            _place(hits, lock, clank(rng, p), db(-10))
            ev(lock, "plate locks", s["label"])
        # vehicle roar before the crash
        before = (sim < 0).astype(float)
        bed[i0:i1] += db(-23) * before * (_band_noise(i1 - i0, 50 * p + 20, 1400 * p + 100, rng) + 0.4 * np.sin(2 * np.pi * np.cumsum(np.full(i1 - i0, 95 * p)) / SR))
        # the crash
        at = film_time_of(s, 0.0)
        if at is not None and s["t0"] - 1e-6 <= at < s["t1"]:
            _place(hits, at, crash(rng, p * (0.7 if truck else 1.0), heavy=1.4 if truck else 1.0), db(-3))
            ev(at, "truck crash" if truck else "crash", s["label"])
        elif s["sim0"] > 0 and s["label"] == "A1-slam":
            _place(hits, 0.0, crash(rng, p), db(-4))
            ev(0.0, "crash (already happening)", s["label"])
        if not truck:
            for k, (tb, p0, v0, size, _, kind) in enumerate(wm.debris()):
                if kind == "spark":
                    continue
                vz, z0 = v0[2], p0[2] - size[2] / 2
                land = tb + (vz + math.sqrt(vz * vz + 2 * wm.G * z0)) / wm.G
                ft = film_time_of(s, land)
                if ft is not None and s["t0"] <= ft < s["t1"]:
                    _place(hits, ft, tinkle(rng, max(p, 0.5)), db(-19))
            rows, _, _ = wm.car_crash()
            th = [r[3] for r in rows]
            land_t = next((rows[i][0] for i in range(1, len(th)) if th[i - 1] > 0.01 and th[i] <= 1e-6), None)
            if land_t is not None:
                ft = film_time_of(s, land_t)
                if ft is not None and s["t0"] <= ft < s["t1"]:
                    _place(hits, ft, impact(p, rng, heavy=0.4), db(-9))
                    ev(ft, "rear drops back", s["label"])
        if s["flags"].get("force"):
            tt = seg_t - s["t0"]
            bed[i0:i1] += db(-16) * np.sin(2 * np.pi * 38 * tt) * (0.6 + 0.4 * np.abs(_band_noise(i1 - i0, 3, 12, rng))) * np.minimum(1, tt / 0.3)
            ev(s["t0"], "foundation rumble", s["label"])

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
    print(json.dumps(build(root / "examples/episodes/ep18-audio/narration.wav", out, tl.total_seconds()), indent=1))
