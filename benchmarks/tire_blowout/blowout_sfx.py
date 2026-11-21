"""EP.16 sound design (pure numpy, deterministic), built like EP.14/EP.15's: every sound is placed from the model and the timeline.
- the burst: a hard bang (deep boom + crack) at the moment the carcass gives way, in the shots that show it; the opening gets its tail;
- the loose tread strip slapping the wheel arch once per turn while it peels (15 a second, slowed with the picture);
- a thud for every rubber piece as it first lands on the road, at the film moment it lands;
- the bare rim grinding on the road after the burst; tyre roar on the highway shots;
- a rubbery creak with every turn in the slow-motion sidewall shots, a low hum that swells with the heat, a soft air hiss over the
  months the parked tyre leaks;
- a whoosh on every cut, wind and a low pulse.
Ducks under the narration; mixed to -15 LUFS with a peak limiter (helpers shared with EP.13-EP.15)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from benchmarks.guardrail_end.terminal_sfx import SR, _band_noise, _env, _place, db, impact, limit, lufs, pitch_of, read_wav, whoosh, write_wav
from benchmarks.tempered_glass.glass_sfx import film_time_of, mix_sigs
from benchmarks.tire_blowout import blowout_motion as bm
from benchmarks.tire_blowout import blowout_timeline as tl


def bang(rng, p=1.0):
    n = int(0.25 * SR)
    crack = _band_noise(n, 800, 12000, rng) * _env(n, 0.0005, 0.03)
    return mix_sigs((1.0, impact(p, rng, heavy=1.0)), (1.2, crack))


def slap(rng, p=1.0):
    n = int(0.09 * SR)
    t = np.arange(n) / SR
    return (_band_noise(n, 150 * p + 50, 2500 * p + 300, rng) + 0.6 * np.sin(2 * np.pi * 110 * p * t)) * _env(n, 0.001, 0.02 / max(p, 0.3))


def thud(rng, p=1.0):
    n = int(0.2 * SR)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * (90 + rng.uniform(-20, 30)) * p * t) + 0.5 * _band_noise(n, 200, 1800, rng)) * _env(n, 0.001, 0.035 / max(p, 0.3))


def creak(rng, p=1.0):
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    f = (180 + 60 * np.sin(2 * np.pi * 3 * t)) * p
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * (0.5 + 0.5 * np.abs(_band_noise(n, 20, 80, rng))) * _env(n, 0.03, 0.12)


def _sim_track(s, t_film):
    i0, i1 = int(s["t0"] * SR), int(min(s["t1"] * SR, len(t_film)))
    seg_t = t_film[i0:i1]
    sub = seg_t[::480]
    sim = np.interp(seg_t, sub, np.array([tl.sim_time(s, x) for x in sub]))
    return i0, i1, sim


def render_sfx(n_samples: int, narration: np.ndarray | None = None) -> tuple[np.ndarray, list]:
    rng = np.random.default_rng(1616)
    segs = tl.segments()
    t_film = np.arange(n_samples) / SR
    bed = np.zeros(n_samples)
    hits = np.zeros(n_samples)
    events = []
    by = {s["label"]: s for s in segs}

    def ev(at, sound, seg):
        events.append({"film_s": round(at, 3), "sound": sound, "segment": seg})

    road = [s for s in segs if s["variant"] == "road"]
    # the burst
    p_open = pitch_of(abs(by["A1-burst"]["time_scale"]))
    tail = bang(rng, p_open)
    _place(hits, 0.0, tail, db(-6))
    ev(0.0, "burst (tail)", "A1-burst")
    for s in road:
        at = film_time_of(s, 0.0)
        if at is not None and s["t0"] <= at < s["t1"]:
            _place(hits, at, bang(rng, pitch_of(abs(s["time_scale"]))), db(-4))
            ev(at, "burst", s["label"])
    # the loose strip slapping once per turn while it peels
    for s in road:
        lo, hi = max(min(s["sim0"], s["sim1"]), bm.PEEL_START), min(max(s["sim0"], s["sim1"]), 0.0)
        if lo >= hi or s["flags"].get("pose_rate"):
            continue
        p = pitch_of(abs(s["time_scale"]))
        x = lo
        while x < hi:
            ft = film_time_of(s, x)
            if ft is not None and s["t0"] <= ft < s["t1"]:
                u = (x - bm.PEEL_START) / -bm.PEEL_START
                _place(hits, ft, slap(rng, p), db(-20 + 9 * u))
            x += 1.0 / bm.revs_per_second()
        ev(film_time_of(s, lo) or s["t0"], "tread slapping", s["label"])
    # rubber pieces landing
    for s in road:
        p = pitch_of(abs(s["time_scale"]))
        n = 0
        for k, (tb, p0, v0, size, _, _) in enumerate(bm.debris()):
            vz, z0 = v0[2], p0[2] - size[2] / 2
            land = tb + (vz + math.sqrt(vz * vz + 2 * bm.G * z0)) / bm.G
            ft = film_time_of(s, land)
            if ft is not None and s["t0"] <= ft < s["t1"]:
                _place(hits, ft, thud(rng, p), db(-15 if k else -9))
                n += 1
        if n:
            ev(s["t0"], f"{n} pieces land", s["label"])
    # tyre roar before, rim grinding after the burst
    for s in road:
        i0, i1, sim = _sim_track(s, t_film)
        if s["flags"].get("pose_rate"):
            continue
        p = pitch_of(abs(s["time_scale"]))
        before = (sim < 0).astype(float)
        after = (sim >= 0).astype(float) * np.clip(1 - sim / 4.0, 0.3, 1.0)
        bed[i0:i1] += db(-25) * before * _band_noise(i1 - i0, 60 * p + 20, 900 * p + 100, rng)
        if after.any():
            grind = _band_noise(i1 - i0, 1500 * p + 200, 7000 * p + 500, rng) * (0.6 + 0.4 * np.abs(np.sin(2 * np.pi * 7 * t_film[i0:i1])))
            bed[i0:i1] += db(-21) * after * grind
    # slow-motion sidewall: a creak with every turn
    for name in ("C1-sidewall-bends", "C2-springs-back", "D2-fifteen-a-second"):
        s = by[name]
        p = pitch_of(abs(s["time_scale"]))
        x = s["sim0"]
        while x < s["sim1"]:
            ft = film_time_of(s, x)
            if ft is not None:
                _place(hits, ft, creak(rng, max(p, 0.5)), db(-19))
            x += 1.0 / bm.revs_per_second()
        ev(s["t0"], "sidewall creaks", name)
    # heat: a low hum that swells
    for name in ("E-heat", "F-cooks-the-glue"):
        s = by[name]
        i0, i1, sim = _sim_track(s, t_film)
        temp = np.array([bm.temperature(float(x)) for x in sim[::480]])
        temp = np.interp(np.arange(i1 - i0), np.arange(0, i1 - i0, 480)[:len(temp)], temp)
        k = np.clip((temp - 40) / (bm.temp_eq(bm.P_LOW) - 40), 0, 1)
        tt = t_film[i0:i1]
        hum = np.sin(2 * np.pi * (55 + 30 * k) * tt) + 0.4 * np.sin(2 * np.pi * (110 + 60 * k) * tt)
        bed[i0:i1] += db(-21) * k * hum
        ev(s["t0"], "heat hum", name)
    # parked: air seeping out over the months
    s = by["H-a-pound-a-month"]
    i0, i1 = int(s["t0"] * SR), int(s["t1"] * SR)
    bed[i0:i1] += db(-30) * _band_noise(i1 - i0, 3000, 9000, rng) * np.sin(np.linspace(0, np.pi, i1 - i0)) ** 0.5
    ev(s["t0"], "air hiss", s["label"])

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
    print(json.dumps(build(root / "examples/episodes/ep16-audio/narration.wav", out, tl.total_seconds()), indent=1))
