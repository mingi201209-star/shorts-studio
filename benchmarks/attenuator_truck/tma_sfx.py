"""EP.32 sound design (pure numpy, deterministic), built like EP.13-EP.31's: every sound is placed from the model and the timeline.
- the car (and the test pickup): engine and tyre roar while it drives in, the crash at first touch (deep boom, metal crunch, glass);
- the cushion: a crackling crunch while the honeycomb crushes, louder for each stiffer row, and a heavy clunk where each row starts;
- the truck: a tyre screech while its braked wheels are shoved along the road (the marks shots);
- the deploy shot: a hydraulic whine while the cushion swings down and a clank when it locks level;
- the reveal shot: the channel's signature sting (benchmarks/signature_sting.py) lands on the cut;
- glass and plastic landing, a whoosh on every cut, wind and a low pulse.
Ducks under the narration; mixed to -15 LUFS with a peak limiter (helpers shared with EP.13-EP.31)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from benchmarks.attenuator_truck import tma_motion as m
from benchmarks.attenuator_truck import tma_timeline as tl
from benchmarks.guardrail_end.terminal_sfx import SR, _band_noise, _env, _place, db, glass, impact, limit, lufs, pitch_of, read_wav, whoosh, write_wav
from benchmarks.signature_sting import RISE_S, reveal_sting
from benchmarks.tempered_glass.glass_sfx import film_time_of, mix_sigs


def clank(rng, p=1.0, heavy=1.0):
    n = int(0.6 * SR)
    t = np.arange(n) / SR
    ring = sum(a * np.sin(2 * np.pi * f * p / heavy * t) * np.exp(-t / d) for f, a, d in ((150, 0.9, 0.16), (440, 0.5, 0.11), (1020, 0.3, 0.06)))
    return ring + 0.6 * _band_noise(n, 150, 3500, rng) * _env(n, 0.001, 0.02)


def tinkle(rng, p=1.0):
    n = int(0.15 * SR)
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * rng.uniform(2500, 6000) * p * t) * np.exp(-t / 0.03) * rng.uniform(0.4, 1.0)


def crackle(n, rng, p, density):
    """Crushing aluminum: dense little cracks (impulses through a band) on a gritty bed."""
    out = 0.35 * _band_noise(n, 300 * p + 100, 5000 * p + 500, rng)
    k = int(density * n / SR)
    for i in rng.integers(0, max(1, n - 400), size=max(k, 1)):
        L = int(rng.integers(80, 400))
        out[i:i + L] += rng.uniform(0.6, 1.4) * _band_noise(L, 900 * p, 7000 * p + 600, rng) * np.exp(-np.arange(L) / (L / 4))
    return out


def screech(n, rng, p, t):
    """A tyre squeal: a wavering tone over a band of noise."""
    f = (900 + 140 * np.sin(2 * np.pi * 7.0 * t)) * p
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR)
    return 0.5 * tone + 0.6 * _band_noise(n, 1200 * p, 4200 * p + 300, rng)


def render_sfx(n_samples: int, narration: np.ndarray | None = None) -> tuple[np.ndarray, list]:
    rng = np.random.default_rng(3232)
    segs = tl.segments()
    t_film = np.arange(n_samples) / SR
    bed = np.zeros(n_samples)
    hits = np.zeros(n_samples)
    events = []
    edges = m.stage_edges()

    def ev(at, sound, seg):
        events.append({"film_s": round(at, 3), "sound": sound, "segment": seg})

    for s in segs:
        i0, i1 = int(s["t0"] * SR), int(min(s["t1"] * SR, n_samples))
        seg_t = t_film[i0:i1]
        sub = seg_t[::480]
        sim = np.interp(seg_t, sub, np.array([tl.sim_time(s, x) for x in sub]))
        p = pitch_of(abs(s["time_scale"]))
        v = s["variant"]
        if v == "deploy":
            moving = ((sim > m.FOLD_START) & (sim < m.FOLD_START + m.FOLD_TIME)).astype(float)
            bed[i0:i1] += db(-19) * moving * (_band_noise(i1 - i0, 2200, 8000, rng) * 0.6 + 0.5 * np.sin(2 * np.pi * 380 * seg_t))
            lock = film_time_of(s, m.FOLD_START + m.FOLD_TIME)
            if lock is not None:
                _place(hits, lock, clank(rng, 1.0), db(-9))
                ev(lock, "cushion locks level", s["label"])
            continue
        pick = v == "pickup"
        rows, t_crush = m.pickup_crash() if pick else m.car_crash()
        t_stop = rows[-1][0]
        before = (sim < 0).astype(float)
        bed[i0:i1] += db(-23) * before * (_band_noise(i1 - i0, 50 * p + 20, 1400 * p + 100, rng) + 0.4 * np.sin(2 * np.pi * np.cumsum(np.full(i1 - i0, 95 * p)) / SR))
        at = film_time_of(s, 0.0)
        if at is not None and s["t0"] - 1e-6 <= at < s["t1"]:
            _place(hits, at, mix_sigs((1.0, impact(p * (0.8 if pick else 1.0), rng, heavy=1.25 if pick else 1.0)), (0.6, glass(p, rng))), db(-3))
            ev(at, "pickup crash" if pick else "crash", s["label"])
        elif s["sim0"] > 0 and s["label"] == "A1-slam":
            _place(hits, 0.0, mix_sigs((1.0, impact(p, rng)), (0.6, glass(p, rng))), db(-4))
            ev(0.0, "crash (already happening)", s["label"])
        # the honeycomb crushing: a crackle while it crushes, louder for each stiffer row, a clunk as each row starts
        crushing = ((sim > 0) & (sim < t_crush)).astype(float)
        if crushing.any():
            c_now = np.array([m.vehicle_state(float(x), pick)["crush"] for x in sub])
            c_now = np.interp(seg_t, sub, c_now)
            stage = np.searchsorted(np.array(edges[1:-1]), c_now)
            loud = np.choose(np.clip(stage, 0, 2), [db(-15), db(-12), db(-9)])
            bed[i0:i1] += crushing * loud * crackle(i1 - i0, rng, p, 900.0 / max(p, 0.5))
            for k, e in enumerate(edges[1:-1], 1):
                ts = next((r[0] for r in rows if r[1] - r[2] >= e), None)
                ft = film_time_of(s, ts) if ts is not None else None
                if ft is not None and s["t0"] <= ft < s["t1"]:
                    _place(hits, ft, clank(rng, p, heavy=1.2), db(-11))
                    ev(ft, f"row {k + 1} starts crushing", s["label"])
        # the braked truck shoved along: tyre screech while it slides
        sliding = ((sim > 0.0) & (sim < t_stop)).astype(float)
        if sliding.any() and (s["flags"].get("skid") or s["label"] in ("A1-slam", "H-pickup")):
            fade = np.clip((t_stop - sim) / 0.15, 0, 1)
            bed[i0:i1] += db(-18) * sliding * fade * screech(i1 - i0, rng, p, seg_t)
            ev(s["t0"], "tyre screech", s["label"])
        if not pick:
            for k, (tb, p0, v0, size, _, kind) in enumerate(m.debris()):
                if kind == "foil":
                    continue
                vz, z0 = v0[2], p0[2] - size[2] / 2
                land = tb + (vz + math.sqrt(vz * vz + 2 * m.G * z0)) / m.G
                ft = film_time_of(s, land)
                if ft is not None and s["t0"] <= ft < s["t1"]:
                    _place(hits, ft, tinkle(rng, max(p, 0.5)), db(-19))
        if s["flags"].get("reveal"):
            _place(hits, s["t0"] - RISE_S, reveal_sting(SR), db(-8))
            ev(s["t0"], "signature reveal sting", s["label"])

    for s in segs[1:]:
        if s["flags"].get("reveal"):
            continue                                            # the sting is this cut's sound
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
    print(json.dumps(build(root / "examples/episodes/ep32-audio/narration.wav", out, tl.total_seconds()), indent=1))
