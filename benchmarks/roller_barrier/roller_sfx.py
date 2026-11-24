"""EP.26 sound design (pure numpy, deterministic), built like EP.13-EP.25's: every sound is placed from the model and the timeline.
- the mountain: wind in the trees, now and then a bird;
- the car: engine and tyre roar with its speed (quieter far away), the tyres squealing while the car slides (contact and the moment
  after it);
- the rolling barrier: a soft foam thump each time the car's side reaches another roller pair (roller_motion's spin-up times), a
  low heavy thud at first contact, and the rollers' whirr while they spin (spinning down after);
- the plain steel rail (shot C): a hard clang at first contact and metal grinding with crackles while the car scrapes it;
- a whoosh on every cut and a quiet low pulse.
Ducks under the narration; mixed to -15 LUFS with a peak limiter (helpers shared with EP.13-EP.25)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from benchmarks.guardrail_end.terminal_sfx import SR, _band_noise, _env, _place, db, limit, lufs, read_wav, whoosh, write_wav
from benchmarks.roller_barrier import roller_motion as rm
from benchmarks.roller_barrier import roller_timeline as tl


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


def foam_thump(rng, size=1.0):
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    body = np.sin(2 * np.pi * np.cumsum(70 / size * np.exp(-t / 0.06) + 38) / SR) * np.exp(-t / 0.12)
    return (body + 0.35 * _band_noise(n, 80, 900, rng) * np.exp(-t / 0.05)) * _env(n, 0.004, 0.3)


def clang(rng):
    n = int(1.4 * SR)
    t = np.arange(n) / SR
    ring = sum(a * np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) * np.exp(-t / tau) for f, a, tau in ((420, 1.0, 0.35), (1130, 0.6, 0.22),
                                                                                                    (2260, 0.4, 0.15), (3710, 0.25, 0.1)))
    thud = np.sin(2 * np.pi * np.cumsum(60 * np.exp(-t / 0.08) + 35) / SR) * np.exp(-t / 0.2)
    return (0.7 * ring + thud + 0.6 * _band_noise(n, 300, 6000, rng) * np.exp(-t / 0.04)) * _env(n, 0.001, 0.4)


def bird(rng):
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    f0 = rng.uniform(2600, 3600)
    return np.sin(2 * np.pi * np.cumsum(f0 * (1 + 0.15 * np.sin(2 * np.pi * rng.uniform(14, 22) * t))) / SR) * _env(n, 0.02, 0.12)


def render_sfx(n_samples: int, narration: np.ndarray | None = None) -> tuple[np.ndarray, list]:
    rng = np.random.default_rng(2626)
    segs = tl.segments()
    t_film = np.arange(n_samples) / SR
    bed = np.zeros(n_samples)
    hits = np.zeros(n_samples)
    events = []

    def ev(at, sound, seg):
        events.append({"film_s": round(at, 3), "sound": sound, "segment": seg})

    spun = rm.crash("roller")["spun"]
    c_end = {b: rm.crash(b)["contact_end"] for b in ("roller", "steel")}
    for s in segs:
        i0, i1 = int(s["t0"] * SR), int(min(s["t1"] * SR, n_samples))
        if i1 <= i0:
            continue
        n = i1 - i0
        seg_t = t_film[i0:i1]
        v = s["variant"]
        bar = "steel" if v == "steel" else "roller"
        idx = np.arange(n)
        grid = np.arange(0, n, 240)
        sims = np.array([tl.sim_time(s, seg_t[0] + g / SR) for g in grid])
        if v != "still":
            cam = np.array(tl.cam_world({"variant": v, "t": float(sims[len(sims) // 2]), "cam": s["cam_a"]}))
            speed, dist, slide, whirr = [], [], [], []
            for x in sims:
                p = rm.pose(float(x), bar)
                speed.append(p["speed"])
                dist.append(math.dist((p["x"], p["y"]), (cam[0], cam[1])))
                slide.append(1.0 if 0.0 <= x <= c_end[bar] + rm.REACT_S else 0.0)
                w = 0.0
                if bar == "roller":
                    for k, (tk, vk) in spun.items():
                        if x > tk:
                            w += vk / rm.ROLL_R * math.exp(-(x - tk) / rm.SPIN_TAU)
                whirr.append(w)
            speed = np.interp(idx, grid, speed) / rm.V0
            near = np.interp(idx, grid, [1.0 / (1.0 + d / 8.0) for d in dist])
            slide = np.interp(idx, grid, slide)
            whirr = np.interp(idx, grid, whirr) / (len(spun) * rm.V0 / rm.ROLL_R)
            eng_f = 70.0 + 60.0 * speed
            phase = 2 * np.pi * np.cumsum(eng_f) / SR
            engine = (np.sin(phase) + 0.5 * np.sin(2 * phase) + 0.25 * np.sin(3 * phase)) * (0.6 + 0.4 * speed)
            roar = _band_noise(n, 120, 1600, rng) * speed
            bed[i0:i1] += db(-24) * near * (0.7 * engine + roar)
            squeal_f = 1800 + 400 * np.sin(2 * np.pi * 3.1 * seg_t)
            squeal = np.sin(2 * np.pi * np.cumsum(squeal_f) / SR) * (0.6 + 0.4 * _band_noise(n, 5, 60, rng))
            bed[i0:i1] += db(-27) * slide * (0.5 * squeal + _band_noise(n, 1400, 4200, rng))
            if slide.max() > 0.5:
                ev(s["t0"] + float(np.argmax(slide > 0.5)) / SR, "tyres squealing", s["label"])
            if bar == "roller" and whirr.max() > 0.01:
                hum_f = 95.0 + 70.0 * np.clip(whirr * 3, 0, 1)
                hum = np.sin(2 * np.pi * np.cumsum(hum_f) / SR) * (0.6 + 0.4 * np.sin(2 * np.pi * 11 * seg_t) ** 2)
                bed[i0:i1] += db(-22) * np.clip(whirr * 3, 0, 1) * (0.6 * hum + _band_noise(n, 200, 1400, rng))
                ev(s["t0"], "rollers whirring", s["label"])
                for k, (tk, vk) in sorted(spun.items(), key=lambda kv: kv[1][0]):
                    ft = film_time_of(s, tk)
                    if ft is not None:
                        _place(hits, ft, foam_thump(rng, rng.uniform(0.9, 1.2)), db(-18))
                        ev(ft, f"foam thump (roller pair {k})", s["label"])
            if bar == "steel":
                scrape = np.interp(idx, grid, [1.0 if 0.0 <= x <= c_end["steel"] else 0.0 for x in sims])
                grind = _band_noise(n, 1800, 7000, rng) * (0.5 + 0.5 * _band_noise(n, 10, 80, rng) ** 2)
                bed[i0:i1] += db(-20) * scrape * grind
                for _ in range(int(scrape.sum() / SR * 40)):
                    at = s["t0"] + rng.uniform(0, n / SR)
                    if scrape[min(n - 1, int((at - s["t0"]) * SR))] > 0.5:
                        m = int(0.01 * SR)
                        _place(hits, at, _band_noise(m, 3000, 9000, rng) * _env(m, 0.0005, 0.6), db(-26))
                if scrape.max() > 0.5:
                    ev(s["t0"] + float(np.argmax(scrape > 0.5)) / SR, "metal grinding", s["label"])
            ft = film_time_of(s, 0.0005)
            if ft is not None:
                if bar == "steel":
                    _place(hits, ft, clang(rng), db(-14))
                    ev(ft, "steel rail clang", s["label"])
                else:
                    _place(hits, ft, foam_thump(rng, 1.8), db(-12))
                    ev(ft, "heavy thud at first contact", s["label"])
    for s in segs[1:]:
        _place(bed, s["t0"] - 0.21, whoosh(rng), db(-28))
        ev(s["t0"], "cut whoosh", s["label"])
    wind = _band_noise(n_samples, 80, 1400, rng) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.09 * t_film + 1.0) ** 2)
    leaves = _band_noise(n_samples, 2000, 6000, rng) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.23 * t_film) ** 2)
    bed += db(-33) * wind + db(-44) * leaves
    for _ in range(9):
        at = rng.uniform(0.5, t_film[-1] - 0.5)
        _place(bed, at, bird(rng), db(-40))
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
    print(json.dumps(build(root / "examples/episodes/ep26-audio/narration.wav", out, tl.total_seconds()), indent=1))
