"""EP.23 sound design (pure numpy, deterministic), built like EP.13-EP.22's: every sound is placed from the model and the timeline.
- the street: traffic hum and wind; in the cut-open vault, meltwater drops hitting the cables (when the renderer's drops land);
- arcs: a buzz and crackle for every arc of the model's schedule that the shot shows; the insulation hissing as it smoulders;
- the blast: a deep boom at the spark, the roar of gas and flame through the opening (from the model's outflow), a clang as the cover
  leaves its frame, a whirr while it turns over, a heavy clang when it lands and on the bounce, then the rattle of the wobble speeding
  up like a dropped coin (one click per half turn of the model's wobble), slush pattering down, sparks fizzing, fire crackling;
- a latched cover: a muffled thump, the clank of the latches catching, the clank of it dropping back, the hiss of venting;
- a vented cover: smoke hissing softly out of the holes; a whoosh on every cut and a low pulse.
Ducks under the narration; mixed to -15 LUFS with a peak limiter (helpers shared with EP.13-EP.22)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from benchmarks.guardrail_end.terminal_sfx import SR, _band_noise, _env, _place, db, limit, lufs, pitch_of, read_wav, whoosh, write_wav
from benchmarks.manhole_blast import manhole_motion as mm
from benchmarks.manhole_blast import manhole_timeline as tl


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


def boom(rng, p=1.0):
    n = int(2.2 * SR)
    t = np.arange(n) / SR
    body = np.sin(2 * np.pi * np.cumsum(70 * p * np.exp(-t / 0.25) + 32 * p) / SR) * np.exp(-t / 0.9)
    crack = _band_noise(n, 200 * p, 6000 * p, rng) * np.exp(-t / 0.06)
    rumble = _band_noise(n, 25, 260 * p, rng) * np.exp(-t / 0.8)
    return (1.0 * body + 0.7 * crack + 0.6 * rumble) * _env(n, 0.002, 2.0)


def clang(rng, p=1.0, size=1.0, decay=0.9):
    n = int(decay * 1.6 * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for f, a, d in ((410, 1.0, 1.0), (1090, 0.6, 0.6), (2230, 0.35, 0.35), (3570, 0.2, 0.2), (180, 0.5, 0.8)):
        out += a * np.sin(2 * np.pi * f * p / size * t + rng.uniform(0, 6.28)) * np.exp(-t / (decay * d))
    hit = _band_noise(n, 300, 9000, rng) * np.exp(-t / 0.015)
    return (out + 0.8 * hit) * _env(n, 0.001, decay * 1.5)


def click(rng, p=1.0):
    n = int(0.05 * SR)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * 950 * p * t) * np.exp(-t / 0.012) + 0.5 * _band_noise(n, 1500, 9000, rng) * np.exp(-t / 0.004))


def plink(rng):
    n = int(0.12 * SR)
    t = np.arange(n) / SR
    f = rng.uniform(1200, 2600)
    return np.sin(2 * np.pi * np.cumsum(f * (1 + 0.6 * np.exp(-t / 0.01))) / SR) * np.exp(-t / 0.03)


def buzz(rng, dur, strength):
    n = max(int(0.04 * SR), int(dur * SR))
    t = np.arange(n) / SR
    tone = sum(np.sin(2 * np.pi * 120 * k * t) / k for k in (1, 2, 3, 5, 7))
    crackle = _band_noise(n, 800, 9000, rng) * (rng.random(n) < 0.08)
    return strength * (0.5 * tone + 1.4 * crackle + 0.6 * _band_noise(n, 2000, 8000, rng)) * _env(n, 0.002, min(0.03, dur / 3))


def render_sfx(n_samples: int, narration: np.ndarray | None = None) -> tuple[np.ndarray, list]:
    rng = np.random.default_rng(2323)
    segs = tl.segments()
    t_film = np.arange(n_samples) / SR
    bed = np.zeros(n_samples)
    hits = np.zeros(n_samples)
    events = []

    def ev(at, sound, seg):
        events.append({"film_s": round(at, 3), "sound": sound, "segment": seg})

    solid = mm._blast("solid")
    latched = mm._blast("latched")
    for s in segs:
        v = s["variant"]
        i0, i1 = int(s["t0"] * SR), int(min(s["t1"] * SR, n_samples))
        if i1 <= i0:
            continue
        seg_t = t_film[i0:i1]
        n = i1 - i0
        p = pitch_of(abs(s["time_scale"])) if v in ("blast", "latched") else 1.0
        sub = seg_t[::480]
        sim_sub = np.array([tl.sim_time(s, x) for x in sub])
        idx = np.arange(n)
        grid = np.arange(0, n, 480)[:len(sim_sub)]
        section = bool(s["flags"].get("section"))
        if v in ("smoulder", "vented"):
            if section:
                k = 0
                for d in mm.drips():
                    fall = math.sqrt(2 * (d[3] - d[4]) / mm.G)
                    hit_t = d[0] + fall
                    while hit_t < s["t1"]:
                        if hit_t >= s["t0"]:
                            _place(hits, hit_t, plink(rng), db(-27))
                            k += 1
                        hit_t += mm.DRIP_CYCLE
                if k:
                    ev(s["t0"], f"{k} drops on the cables", s["label"])
            for a, d, strength in mm.arcs():
                if a + d < s["sim0"] or a > s["sim1"]:
                    continue
                ft = film_time_of(s, max(a, s["sim0"]))
                if ft is None:
                    continue
                dur = min(0.5, max(0.03, d / max(abs(s["time_scale"]), 1e-6)))
                _place(hits, ft, buzz(rng, dur, strength), db(-16 if section else -26))
                ev(ft, "arc", s["label"])
            char = np.interp(idx, grid, [mm.char(float(x)) for x in sim_sub])
            bed[i0:i1] += db(-34) * char * _band_noise(n, 2500, 7000, rng)
            if v == "vented" and not section:
                bed[i0:i1] += db(-30) * char * _band_noise(n, 3000, 9000, rng)
                ev(s["t0"], "smoke hissing out of the holes", s["label"])
        else:
            res = solid if v == "blast" else latched
            kind = "solid" if v == "blast" else "latched"
            q = np.interp(idx, grid, [mm.outflow(float(x), kind) / 80.0 for x in sim_sub])
            bed[i0:i1] += db(-17) * np.clip(q, 0, 1.2) * _band_noise(n, 70 * p, 2200 * p, rng)
            if (q > 0.02).any():
                ev(s["t0"], "gas and flame roaring out", s["label"])
            ft = film_time_of(s, 0.0)
            if ft is not None:
                _place(hits, ft, boom(rng, p), db((-13 if s["flags"].get("loop") else -9) if v == "blast" else -14))
                ev(ft, "boom", s["label"])
            fa, fb_ = film_time_of(s, max(-0.05, s["sim0"])), film_time_of(s, min(0.0, s["sim1"]))
            if fa is not None and fb_ is not None and fb_ > fa:
                _place(hits, fa, buzz(rng, min(1.4, fb_ - fa), 1.0), db(-18))                  # the arc that lights the gas, as long as it is shown
                ev(fa, "the spark", s["label"])
            if v == "blast":
                ft = film_time_of(s, res["t_free"])
                if ft is not None:
                    _place(hits, ft, clang(rng, p, 1.0, 0.7), db(-14))
                    ev(ft, "cover leaves its frame", s["label"])
                fly = np.interp(idx, grid, [1.0 if res["t_free"] < x < res["t_land"] else 0.0 for x in sim_sub])
                spin = 0.5 + 0.5 * np.sin(2 * np.pi * np.interp(idx, grid, [mm.tumble(float(x)) / math.pi for x in sim_sub]))
                bed[i0:i1] += db(-30) * fly * spin * _band_noise(n, 300 * p, 3000 * p, rng)
                for k, x in enumerate((res["t_land"], res["t_land"] + 2 * mm.REST_E * 10.4 / mm.G)):
                    ft = film_time_of(s, x)
                    if ft is not None:
                        _place(hits, ft, clang(rng, p, 0.9, 1.1 if k == 0 else 0.6), db(-5 if k == 0 else -14))
                        ev(ft, "cover lands" if k == 0 else "bounce", s["label"])
                ts, tilt, phase = mm._wobble()
                half = np.searchsorted(phase, np.arange(math.pi, phase[-1], math.pi))
                kk = 0
                for i in half:
                    x = res["t_land"] + ts[min(i, len(ts) - 1)]
                    ft = film_time_of(s, float(x))
                    if ft is not None and tilt[min(i, len(ts) - 1)] > 0.004:
                        _place(hits, ft, click(rng, p), db(-20) * (0.4 + 6 * tilt[min(i, len(ts) - 1)]))
                        kk += 1
                if kk:
                    ev(film_time_of(s, res["t_land"] + 0.05) or s["t0"], f"wobble rattle ({kk} clicks)", s["label"])
                for x in np.arange(0.35, 1.6, 0.05):
                    ft = film_time_of(s, float(x))
                    if ft is not None and rng.random() < 0.5:
                        _place(hits, ft, click(rng, 1.6 * p), db(-30))
                after = np.interp(idx, grid, [1.0 if x > 0.2 else 0.0 for x in sim_sub])
                crackle = _band_noise(n, 1500, 8000, rng) * (rng.random(n) < 0.004)
                bed[i0:i1] += db(-22) * after * crackle + db(-30) * after * _band_noise(n, 60, 500, rng)
            else:
                for x, name in ((res["t_caught"], "latches catch"), (res["t_back"], "cover drops back")):
                    ft = film_time_of(s, x)
                    if ft is not None:
                        _place(hits, ft, clang(rng, p, 1.15, 0.45), db(-12))
                        ev(ft, name, s["label"])
    for s in segs[1:]:
        _place(bed, s["t0"] - 0.21, whoosh(rng), db(-26))
        ev(s["t0"], "cut whoosh", s["label"])
    traffic = _band_noise(n_samples, 35, 380, rng) * (0.7 + 0.3 * np.sin(2 * np.pi * 0.05 * t_film) ** 2)
    wind = _band_noise(n_samples, 150, 1500, rng) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.11 * t_film + 1.0) ** 2)
    bed += db(-34) * traffic + db(-38) * wind
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
    print(json.dumps(build(root / "examples/episodes/ep23-audio/narration.wav", out, tl.total_seconds()), indent=1))
