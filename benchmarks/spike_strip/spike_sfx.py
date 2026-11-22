"""EP.19 sound design (pure numpy, deterministic), built like EP.13-EP.18's: every sound is placed from the model and the timeline.
- tyre roar and engine while the car drives; a rattle as the tyres cross the strip;
- a sharp tick for every quill that punches into a tyre, at the moment it goes in;
- the hiss of air out of the quills, loud and high while the flow is choked, softer and lower as the pressure falls (from the model's
  vent speed), in every shot where the quills are in;
- a soft rhythmic thump of the deflated tyre as the car rolls to a stop;
- a whoosh on every cut, wind and a low pulse.
Ducks under the narration; mixed to -15 LUFS with a peak limiter (helpers shared with EP.13-EP.18)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from benchmarks.guardrail_end.terminal_sfx import SR, _band_noise, _env, _place, db, limit, lufs, pitch_of, read_wav, whoosh, write_wav
from benchmarks.spike_strip import spike_motion as sm
from benchmarks.spike_strip import spike_timeline as tl
from benchmarks.tempered_glass.glass_sfx import film_time_of


def tick(rng, p=1.0):
    n = int(0.12 * SR)
    t = np.arange(n) / SR
    return (_band_noise(n, 1500 * p + 300, 9000, rng) + 0.7 * np.sin(2 * np.pi * 2200 * p * t)) * _env(n, 0.0005, 0.012 / max(p, 0.3))


def render_sfx(n_samples: int, narration: np.ndarray | None = None) -> tuple[np.ndarray, list]:
    rng = np.random.default_rng(1919)
    segs = tl.segments()
    t_film = np.arange(n_samples) / SR
    bed = np.zeros(n_samples)
    hits = np.zeros(n_samples)
    events = []
    caps = sm.captured()

    def ev(at, sound, seg):
        events.append({"film_s": round(at, 3), "sound": sound, "segment": seg})

    for s in segs:
        i0, i1 = int(s["t0"] * SR), int(min(s["t1"] * SR, n_samples))
        seg_t = t_film[i0:i1]
        sub = seg_t[::480]
        sim = np.interp(seg_t, sub, np.array([tl.sim_time(s, x) for x in sub]))
        p = pitch_of(abs(s["time_scale"]))
        speed = np.array([sm.car_speed(float(x)) for x in sim[::480]])
        speed = np.interp(np.arange(i1 - i0), np.arange(0, i1 - i0, 480)[:len(speed)], speed)
        roar = np.clip(speed / sm.V0, 0, 1)
        if s["flags"].get("pose_rate"):
            roar = roar * 0.3
        bed[i0:i1] += db(-24) * roar * _band_noise(i1 - i0, 60 * p + 20, 1200 * p + 100, rng)
        for c in caps:
            ft = film_time_of(s, c["t"])
            if ft is not None and s["t0"] <= ft < s["t1"]:
                _place(hits, ft, tick(rng, p), db(-8))
                ev(ft, f"quill in ({c['axle']})", s["label"])
        over = film_time_of(s, 0.0)
        if over is not None and s["t0"] <= over < s["t1"]:
            n = int(0.25 * SR / max(p, 0.2))
            _place(hits, over, _band_noise(n, 400, 4000, rng) * _env(n, 0.002, 0.08 / max(p, 0.2)), db(-16))
        vent = np.array([max(sm.vent_speed(float(x), "front"), sm.vent_speed(float(x), "rear")) for x in sim[::480]])
        vent = np.interp(np.arange(i1 - i0), np.arange(0, i1 - i0, 480)[:len(vent)], vent)
        k = np.clip(vent / 343.0, 0, 1)
        if k.any():
            hiss = _band_noise(i1 - i0, 2500, 11000, rng) * k + 0.6 * _band_noise(i1 - i0, 900, 3000, rng) * k ** 2
            bed[i0:i1] += db(-18) * hiss
            ev(s["t0"], "air hiss", s["label"])
        if s["label"].startswith("H-"):
            x = s["sim0"]
            while x < s["sim1"]:
                ft = film_time_of(s, x)
                v = sm.car_speed(x)
                if ft is not None and v > 0.5:
                    n = int(0.1 * SR)
                    _place(hits, ft, np.sin(2 * np.pi * 70 * np.arange(n) / SR) * _env(n, 0.002, 0.03), db(-20))
                x += max(0.02, 2 * math.pi * sm.R / max(v, 0.5)) * 6
    for s in segs[1:]:
        _place(bed, s["t0"] - 0.21, whoosh(rng), db(-26))
        ev(s["t0"], "cut whoosh", s["label"])
    wind = _band_noise(n_samples, 40, 500, rng) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.11 * t_film + 1.0) ** 2)
    bed += db(-36) * wind
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
    print(json.dumps(build(root / "examples/episodes/ep19-audio/narration.wav", out, tl.total_seconds()), indent=1))
