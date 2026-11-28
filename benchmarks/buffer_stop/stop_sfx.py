"""EP.36 sound design (pure numpy, deterministic), built like EP.13-EP.35's. Every sound is placed from the model and the timeline:
- the train: traction motors whining and wheels drumming over the rail joints, both following its speed;
- the hit: a heavy steel thump as the buffers meet, the hydraulic buffers hissing as they squash;
- the slide: the shoes grinding along the rails and sparks crackling while the stop moves, then a settling clunk;
- the what-if: a crash into concrete with a rain of debris;
- the comparison: the car's tyres screeching under a hard stop;
- afterwards: wrench ratchets, the rail tractor's diesel and the clunk as it meets the stop;
- the reveal: the channel's signature sting on the cut;
- a whoosh on every other cut, station air and a low pulse.
Ducks under the narration; mixed to -15 LUFS with a peak limiter (helpers shared with EP.13-EP.35)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from benchmarks.buffer_stop import stop_motion as m
from benchmarks.buffer_stop import stop_timeline as tl
from benchmarks.guardrail_end.terminal_sfx import SR, _band_noise, _env, _place, db, impact, limit, lufs, pitch_of, read_wav, whoosh, write_wav
from benchmarks.signature_sting import RISE_S, reveal_sting
from benchmarks.tempered_glass.glass_sfx import film_time_of


def clunk(rng, p=1.0, dur=0.6):
    n = int(dur * SR)
    t = np.arange(n) / SR
    ring = sum(a * np.sin(2 * np.pi * f * p * t) * np.exp(-t / d) for f, a, d in ((62, 1.0, 0.18), (148, 0.6, 0.1), (420, 0.35, 0.05)))
    return ring + 0.6 * _band_noise(n, 60, 2500, rng) * _env(n, 0.001, 0.05)


def hiss(rng, dur=0.9, p=1.0):
    n = int(dur * SR)
    return _band_noise(n, 1800 * p, 9000 * p + 300, rng) * _env(n, 0.01, dur * 0.45)


def ratchet(rng, clicks=7, rate=11.0):
    n = int((clicks / rate + 0.1) * SR)
    out = np.zeros(n)
    for k in range(clicks):
        _place(out, k / rate, _band_noise(int(0.02 * SR), 2500, 9000, rng) * _env(int(0.02 * SR), 0.0005, 0.006), 1.0)
    return out


def _sim_of(seg, seg_t):
    sub = seg_t[::480]
    return np.interp(seg_t, sub, np.array([tl.sim_time(seg, x) for x in sub]))


def _train_speed(sim):
    rows = m.impact()
    ts = np.array([r[0] for r in rows][::40])
    v = np.array([r[2] for r in rows][::40])
    stop_v = np.array([r[5] for r in rows][::40])
    return np.where(sim < 0, m.V0, np.interp(sim, ts, v, right=0.0)), np.where(sim < 0, 0.0, np.interp(sim, ts, stop_v, right=0.0))


def render_sfx(n_samples: int, narration: np.ndarray | None = None) -> tuple[np.ndarray, list]:
    rng = np.random.default_rng(3636)
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
        seg_t = t_film[i0:i1]
        p = pitch_of(abs(s["time_scale"]))
        v = s["variant"]
        if v in ("train", "split"):
            sim = _sim_of(s, seg_t)
            speed, stop_v = _train_speed(sim)
            u = np.clip(speed / m.V0, 0, 1)
            whine = np.sin(2 * np.pi * np.cumsum((380 + 520 * u) * p) / SR)
            rumble = _band_noise(i1 - i0, 30 * p + 15, 500 * p + 60, rng)
            gain = 0.6 if v == "split" else 1.0
            bed[i0:i1] += gain * u * (db(-30) * whine + db(-24) * rumble)
            # wheels over the rail joints (every 18 m, two bogies close together)
            joint = np.zeros(i1 - i0)
            phase = np.cumsum(speed * p) / SR / 18.0
            ticks = np.nonzero(np.diff(np.floor(phase)) > 0)[0]
            for k in ticks:
                for dt in (0.0, 0.11):
                    _place(joint, k / SR + dt, clunk(rng, 1.6 * p, 0.15), db(-24) * float(u[min(k, len(u) - 1)]))
            bed[i0:i1] += gain * joint
            slide = np.clip(stop_v / m.V0, 0, 1)
            if slide.any():
                grind = _band_noise(i1 - i0, 600 * p + 100, 6000 * p + 400, rng) * (0.65 + 0.35 * np.abs(np.sin(2 * np.pi * 31 * seg_t)))
                crackle = _band_noise(i1 - i0, 3000, 11000, rng) * (rng.random(i1 - i0) < 0.012)
                bed[i0:i1] += gain * np.sqrt(slide) * (db(-17) * grind + db(-20) * crackle * 6)
                ev(s["t0"], "the shoes grind along the rails, sparks crackle", s["label"])
            for when, what, sig, g in ((0.0, "the buffers meet with a heavy thump", impact(p * 0.6, rng, heavy=1.6), db(-11)),
                                       (0.004, "the hydraulic buffers hiss as they squash", hiss(rng, 0.9, max(p, 0.5)), db(-17)),
                                       (m.stop_time(), "the stop settles", clunk(rng, max(p, 0.6)), db(-16))):
                at = film_time_of(s, when)
                if at is not None and s["t0"] - 1e-6 <= at < s["t1"]:
                    _place(hits, at, sig, g * (0.6 if v == "split" else 1.0))
                    ev(at, what, s["label"])
            if s["label"] == "A1-slides":
                _place(hits, 0.0, impact(0.6, rng, heavy=1.6), db(-12))
                ev(0.0, "the hit (already happening)", s["label"])
            if v == "split":
                car_t = sim - 0.25
                t_stop = m.CAR_V0 / (m.CAR_DECEL_G * m.G)
                screech = ((car_t >= 0) & (car_t < t_stop)).astype(float)
                tone = np.sin(2 * np.pi * np.cumsum(1900 + 140 * np.sin(2 * np.pi * 7 * seg_t)) / SR)
                bed[i0:i1] += screech * (db(-17) * _band_noise(i1 - i0, 1200, 6000, rng) + db(-22) * tone)
                ev(s["t0"] + 0.25, "the car's tyres screech", s["label"])
                at = s["t0"] + 0.25 + t_stop
                if at < s["t1"]:
                    _place(hits, at, clunk(rng, 1.3, 0.3), db(-19))
        elif v == "wall":
            sim = _sim_of(s, seg_t)
            u = (sim < 0).astype(float)
            bed[i0:i1] += u * (db(-24) * _band_noise(i1 - i0, 30 * p + 15, 500 * p + 60, rng) +
                               db(-30) * np.sin(2 * np.pi * np.cumsum((900 * np.ones(i1 - i0)) * p) / SR))
            at = film_time_of(s, 0.0)
            if at is not None:
                _place(hits, at, impact(0.5, rng, heavy=2.2), db(-8))
                _place(hits, at, _band_noise(int(1.2 * SR), 80, 5000, rng) * _env(int(1.2 * SR), 0.002, 0.35), db(-13))
                for k in range(14):
                    _place(hits, at + 0.15 + 0.07 * k + 0.05 * rng.random(), clunk(rng, 2.5 + rng.random(), 0.12), db(-26))
                ev(at, "the crash into the wall, debris raining down", s["label"])
        else:                                                           # crew
            for k, at in enumerate((0.25, 0.95, 1.7)):
                _place(hits, s["t0"] + at, ratchet(rng), db(-20))
            if s["flags"].get("push"):
                diesel = _band_noise(i1 - i0, 40, 900, rng) * (0.7 + 0.3 * np.sin(2 * np.pi * 14 * seg_t))
                bed[i0:i1] += db(-23) * diesel
                _place(hits, s["t0"] + 0.15, clunk(rng, 1.0), db(-18))
                ev(s["t0"], "the rail tractor pushes the stop back", s["label"])
            ev(s["t0"], "wrench ratchets on the shoe bolts", s["label"])
        if s["flags"].get("reveal"):
            _place(hits, s["t0"] - RISE_S, reveal_sting(SR), db(-8))
            ev(s["t0"], "signature reveal sting", s["label"])

    for k, s in enumerate(segs[1:]):
        if s["flags"].get("reveal") or k % 2:
            continue
        _place(bed, s["t0"] - 0.21, whoosh(rng), db(-26))
        ev(s["t0"], "cut whoosh", s["label"])
    air = _band_noise(n_samples, 50, 900, rng) * (0.7 + 0.3 * np.sin(2 * np.pi * 0.13 * t_film + 0.4) ** 2)
    bed += db(-34) * air
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


def build(narration_wav: Path, out_dir: Path, seconds: float, sfx_gain_db: float = -4.0, target_lufs: float = -15.0) -> dict:
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
    print(json.dumps(build(root / "examples/episodes/ep36-audio/narration.wav", out, tl.total_seconds()), indent=1))
