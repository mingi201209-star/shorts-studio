"""EP.33 sound design (pure numpy, deterministic), built like EP.13-EP.32's: every sound is placed from the model and the timeline.
- the bay: water lapping, now and then a gull, a ship's diesel drone while it is under way;
- the hit: a deep boom and a steel crunch at first touch, then grinding steel and crunching rock while the bow and the ring give,
  and spray falling back into the water;
- the force shot: a deep rumble while the load goes into the bed; the reveal: the channel's signature sting on the cut;
- a whoosh on every other cut, wind and a low pulse.
Ducks under the narration; mixed to -15 LUFS with a peak limiter (helpers shared with EP.13-EP.32)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from benchmarks.guardrail_end.terminal_sfx import SR, _band_noise, _env, _place, db, impact, limit, lufs, pitch_of, read_wav, whoosh, write_wav
from benchmarks.ship_dolphin import dolphin_motion as m
from benchmarks.ship_dolphin import dolphin_timeline as tl
from benchmarks.signature_sting import RISE_S, reveal_sting
from benchmarks.tempered_glass.glass_sfx import film_time_of


def splash(rng, p=1.0):
    n = int(0.5 * SR)
    return _band_noise(n, 300 * p, 6000 * p + 400, rng) * _env(n, 0.005, 0.12)


def gull(rng):
    n = int(0.6 * SR)
    t = np.arange(n) / SR
    f = 1400 + 500 * np.sin(np.pi * t / t[-1]) - 300 * t
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / t[-1]) ** 2 * 0.6


def render_sfx(n_samples: int, narration: np.ndarray | None = None) -> tuple[np.ndarray, list]:
    rng = np.random.default_rng(3333)
    segs = tl.segments()
    t_film = np.arange(n_samples) / SR
    bed = np.zeros(n_samples)
    hits = np.zeros(n_samples)
    events = []
    t_stop = m.collision()[-1][0]

    def ev(at, sound, seg):
        events.append({"film_s": round(at, 3), "sound": sound, "segment": seg})

    for s in segs:
        i0, i1 = int(s["t0"] * SR), int(min(s["t1"] * SR, n_samples))
        seg_t = t_film[i0:i1]
        sub = seg_t[::480]
        sim = np.interp(seg_t, sub, np.array([tl.sim_time(s, x) for x in sub]))
        p = pitch_of(abs(s["time_scale"]))
        under_way = (sim < t_stop).astype(float)
        bed[i0:i1] += db(-27) * under_way * (np.sin(2 * np.pi * 38 * seg_t) * 0.7 + _band_noise(i1 - i0, 30, 220, rng))
        at = film_time_of(s, 0.0)
        if at is not None and s["t0"] - 1e-6 <= at < s["t1"]:
            _place(hits, at, impact(p * 0.6, rng, heavy=1.8), db(-3))
            ev(at, "bow hits the dolphin", s["label"])
        elif s["sim0"] > 0 and s["label"] == "A1-bow-hits":
            _place(hits, 0.0, impact(p * 0.6, rng, heavy=1.8), db(-4))
            ev(0.0, "bow hits (already happening)", s["label"])
        giving = ((sim > 0) & (sim < t_stop)).astype(float)
        if giving.any():
            grind = _band_noise(i1 - i0, 60 * p + 20, 900 * p + 100, rng) * (0.6 + 0.4 * np.abs(np.sin(2 * np.pi * 3.3 * seg_t)))
            creak = np.sin(2 * np.pi * np.cumsum(140 * p + 40 * np.sin(2 * np.pi * 0.7 * seg_t)) / SR)
            bed[i0:i1] += giving * (db(-14) * grind + db(-22) * creak)
            if s["flags"].get("cut"):
                bed[i0:i1] += giving * db(-17) * _band_noise(i1 - i0, 400 * p, 5000 * p + 400, rng) * np.abs(_band_noise(i1 - i0, 4, 30, rng))
            ev(s["t0"], "steel grinds, rock crunches", s["label"])
        for k, (tb, p0, v0, size, kind) in enumerate(m.spray()):
            if kind != "water" or k % 4:
                continue
            land = tb + (v0[2] + math.sqrt(v0[2] ** 2 + 2 * m.G * max(p0[2] - size / 2, 0.0))) / m.G
            ft = film_time_of(s, land)
            if ft is not None and s["t0"] <= ft < s["t1"]:
                _place(hits, ft, splash(rng, max(p, 0.5)), db(-20))
        if s["flags"].get("force"):
            tt = seg_t - s["t0"]
            bed[i0:i1] += db(-15) * np.sin(2 * np.pi * 34 * tt) * (0.6 + 0.4 * np.abs(_band_noise(i1 - i0, 3, 12, rng))) * np.minimum(1, tt / 0.3)
            ev(s["t0"], "load rumbles into the bed", s["label"])
        if s["flags"].get("reveal"):
            _place(hits, s["t0"] - RISE_S, reveal_sting(SR), db(-8))
            ev(s["t0"], "signature reveal sting", s["label"])

    for s in segs[1:]:
        if s["flags"].get("reveal"):
            continue
        _place(bed, s["t0"] - 0.21, whoosh(rng), db(-26))
        ev(s["t0"], "cut whoosh", s["label"])
    lap = _band_noise(n_samples, 150, 1800, rng) * (0.5 + 0.5 * np.abs(np.sin(2 * np.pi * 0.35 * t_film)))
    bed += db(-33) * lap
    for at in (4.0, 15.5, 27.0):
        _place(bed, at, gull(rng), db(-30))
    wind = _band_noise(n_samples, 40, 500, rng) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.11 * t_film + 1.0) ** 2)
    bed += db(-37) * wind
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
    print(json.dumps(build(root / "examples/episodes/ep33-audio/narration.wav", out, tl.total_seconds()), indent=1))
