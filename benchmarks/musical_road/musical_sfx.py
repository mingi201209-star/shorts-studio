"""EP.24 sound design (pure numpy, deterministic), built like EP.13-EP.23's, except that here the effects are the subject: the tune is
not a music track, it is synthesized from the model. Every time a tyre drops into a groove (musical_motion.hits: the front tyres,
and the rear tyres a wheelbase later) a short thump is placed at that moment's film time; hundreds of thumps a second overlap into a
buzzing note whose pitch is the thump rate, exactly as on the real road. Slowed shots therefore play separate thumps, and the shot
that speeds up turns them into a note; shots that show pitch run in real time.
Also: the tyres' roar on smooth asphalt and the wind as the car passes (louder near the camera), a soft tick as each measuring bar
appears, a whoosh on every cut and a quiet low pulse. Ducks under the narration; mixed to -15 LUFS with a peak limiter (helpers
shared with EP.13-EP.23)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from benchmarks.guardrail_end.terminal_sfx import SR, _band_noise, _env, _place, db, limit, lufs, read_wav, whoosh, write_wav
from benchmarks.musical_road import musical_motion as mm
from benchmarks.musical_road import musical_timeline as tl


def film_times(seg: dict, sims: np.ndarray) -> np.ndarray:
    """Film time of each simulated time inside the segment (NaN outside), by inverting the piecewise-linear knots."""
    out = np.full(len(sims), np.nan)
    k = seg["knots"]
    pairs = list(zip(k[:-1], k[1:]))
    (a, sa), (b, sb) = k[-2], k[-1]
    span = seg["t1"] - seg["t0"]
    pairs.append(((b, sb), (span, sb + (sb - sa) / (b - a) * (span - b))))
    for (a, sa), (b, sb) in pairs:
        if sb <= sa:
            continue
        sel = (sims >= sa) & (sims < sb)
        out[sel] = seg["t0"] + a + (sims[sel] - sa) * (b - a) / (sb - sa)
    out[(out < seg["t0"]) | (out >= seg["t1"])] = np.nan
    return out


def thump_kernel() -> np.ndarray:
    n = int(0.03 * SR)
    t = np.arange(n) / SR
    body = np.sin(2 * np.pi * 140 * t) * np.exp(-t / 0.006)
    slap = 0.55 * np.sin(2 * np.pi * 820 * t) * np.exp(-t / 0.0018)
    click = 0.35 * np.exp(-t / 0.0004) * np.cos(2 * np.pi * 3100 * t)
    return (body + slap + click) * (1 - np.exp(-t / 0.0002))


def tick(rng):
    n = int(0.06 * SR)
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * 1800 * t) * np.exp(-t / 0.012) + 0.3 * _band_noise(n, 2000, 9000, rng) * np.exp(-t / 0.003)


def _cam_gain(seg: dict, film_t: float, car_y: float) -> float:
    if seg["cam_a"]["rel"] == "car":
        return 1.0
    sh = tl.frame_state(int(round(film_t * tl.FPS)), tl.segments())
    x, y, z = sh["cam"]["loc"]
    d = math.dist((x, y, z), (mm.CAR_X + mm.TRACK / 2, car_y + mm.FRONT_AXLE, 0.0))
    return 1.0 / (1.0 + d / 6.0)


def render_sfx(n_samples: int, narration: np.ndarray | None = None, tune_out: list | None = None) -> tuple[np.ndarray, list]:
    rng = np.random.default_rng(2424)
    segs = tl.segments()
    t_film = np.arange(n_samples) / SR
    bed = np.zeros(n_samples)
    hits = np.zeros(n_samples)
    impulses = np.zeros(n_samples)
    events = []

    def ev(at, sound, seg):
        events.append({"film_s": round(at, 3), "sound": sound, "segment": seg})

    for s in segs:
        v = s["variant"]
        i0, i1 = int(s["t0"] * SR), int(min(s["t1"] * SR, n_samples))
        if i1 <= i0:
            continue
        n = i1 - i0
        seg_t = t_film[i0:i1]
        if v == "gap":
            for at, name in ((0.02, "plan bar"), (0.3, "crew bar")):
                ft = s["t0"] + at * (s["t1"] - s["t0"])
                _place(hits, ft, tick(rng), db(-24))
                ev(ft, f"tick: {name}", s["label"])
            continue
        version = "built" if v in ("built", "compare") else "design"
        speed = "slow" if v == "slow" else "design"
        vel = mm.V_SLOW if speed == "slow" else mm.V_DESIGN
        front, rear = mm.hits(version, speed)
        notes = set()
        k_hits = 0
        for times, amp in ((front, 1.0), (rear, 0.8)):
            ft = film_times(s, times)
            ok = np.isfinite(ft)
            for f_t, h in zip(ft[ok], times[ok]):
                idx = int(round(f_t * SR))
                if 0 <= idx < n_samples:
                    impulses[idx] += amp * _cam_gain(s, f_t, mm.car_y(float(h), vel))
                    k_hits += 1
        for x in np.linspace(s["sim0"], s["sim1"], 40):
            nm = mm.note_at(float(x), version, speed)
            if nm:
                notes.add(nm)
        if k_hits:
            ev(s["t0"], f"{k_hits} tyre thumps ({version} road, {'35' if speed == 'slow' else '55'} mph; notes {sorted(notes)})", s["label"])
        sims = np.array([tl.sim_time(s, x) for x in seg_t[::480]])
        car_ys = np.array([mm.car_y(float(x), vel) for x in sims])
        gains = np.array([_cam_gain(s, float(ft_), float(cy)) for ft_, cy in zip(seg_t[::480], car_ys)])
        g = np.interp(np.arange(n), np.arange(0, n, 480)[:len(gains)], gains)
        rate = abs(s["time_scale"])
        roar = _band_noise(n, 90 * max(rate, 0.05) ** 0.5, 2400 * max(rate, 0.05) ** 0.5, rng)
        bed[i0:i1] += db(-27) * min(1.0, rate) * g * roar
        bed[i0:i1] += db(-33) * min(1.0, rate) * g * _band_noise(n, 300, 5000, rng)
    tone = np.convolve(impulses, thump_kernel())[:n_samples]
    if tune_out is not None:
        tune_out.append(tone)
    for s in segs[1:]:
        _place(bed, s["t0"] - 0.21, whoosh(rng), db(-28))
        ev(s["t0"], "cut whoosh", s["label"])
    wind = _band_noise(n_samples, 60, 800, rng) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.07 * t_film + 1.0) ** 2)
    bed += db(-38) * wind
    beat = 60.0 / 75.0
    pulse = np.zeros(n_samples)
    kn = int(0.35 * SR)
    kick = np.sin(2 * np.pi * np.cumsum(50 * np.exp(-np.arange(kn) / SR / 0.08) + 41.2) / SR) * _env(kn, 0.003, 0.12)
    kk = 0.0
    while kk < t_film[-1]:
        _place(pulse, kk, kick, 1.0)
        kk += beat
    bed += db(-38) * pulse

    gain = np.ones(n_samples)
    if narration is not None:
        e = np.sqrt(np.convolve(narration[:n_samples] ** 2, np.ones(1440) / 1440, mode="same"))
        e = np.convolve(e, np.ones(9600) / 9600, mode="same")
        gain = 1.0 - 0.55 * np.clip(e / 0.03, 0, 1)
    out = bed * gain + db(-17.5) * tone * (0.35 + 0.65 * gain) + hits * (0.5 + 0.5 * gain)
    peak = np.max(np.abs(out)) + 1e-9
    if peak > db(-3):
        out *= db(-3) / peak
    return out, events


def build(narration_wav: Path, out_dir: Path, seconds: float, sfx_gain_db: float = -2.0, target_lufs: float = -15.0) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    narr = read_wav(narration_wav)
    n = int(round(seconds * SR))
    narr = np.pad(narr, (0, max(0, n - len(narr))))[:n]
    tune = []
    fx, events = render_sfx(n, narr, tune)
    write_wav(out_dir / "tune.wav", tune[0] / (np.max(np.abs(tune[0])) + 1e-9) * 0.5)
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
    print(json.dumps(build(root / "examples/episodes/ep24-audio/narration.wav", out, tl.total_seconds()), indent=1))
