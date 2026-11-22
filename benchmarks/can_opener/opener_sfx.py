"""EP.20 sound design (pure numpy, deterministic), built like EP.13-EP.19's: every sound is placed from the model and the timeline.
- the diesel and the tyres while the truck rolls (from the model's speed);
- the hit: boom, crunch and steel clang when the box meets the beam;
- the tearing of the roof skin while it peels (louder and brighter the faster the peel front runs);
- a tick for every rivet torn out of the top rails and a metallic clank for every roof bow that buckles, at the model's times;
- the brakes squealing from the moment the driver reacts until the truck stops;
- the freight train rumbling and its horn in the bridge shot; the detector's alarm, the flashing warning and the light changing in the
  sensor shot; hydraulic jacks humming in the raise time-lapse;
- a whoosh on every cut, wind and a low pulse.
Ducks under the narration; mixed to -15 LUFS with a peak limiter (helpers shared with EP.13-EP.19)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from benchmarks.can_opener import opener_motion as om
from benchmarks.can_opener import opener_timeline as tl
from benchmarks.guardrail_end.terminal_sfx import SR, _band_noise, _env, _place, db, impact, limit, lufs, pitch_of, read_wav, whoosh, write_wav


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


def tick(rng, p=1.0):
    n = int(0.05 * SR)
    t = np.arange(n) / SR
    return (_band_noise(n, 1800 * p + 400, 10000, rng) + 0.5 * np.sin(2 * np.pi * 3100 * p * t)) * _env(n, 0.0003, 0.006 / max(p, 0.3))


def clank(rng, p=1.0):
    n = int(0.5 * SR / max(p, 0.4))
    t = np.arange(n) / SR
    tone = sum(a * np.sin(2 * np.pi * f * p * t) for a, f in ((1.0, 410.0), (0.6, 1130.0), (0.35, 2270.0)))
    return (0.6 * tone + 0.8 * _band_noise(n, 300 * p, 6000 * p, rng)) * _env(n, 0.001, 0.08 / max(p, 0.3))


def horn(n, rng):
    t = np.arange(n) / SR
    chord = sum(np.sign(np.sin(2 * np.pi * f * t)) * 0.3 + 0.4 * np.sin(2 * np.pi * f * t) for f in (277.0, 349.0, 415.0))
    return chord * np.minimum(1.0, t / 0.05) * np.minimum(1.0, (t[-1] - t) / 0.12)


def render_sfx(n_samples: int, narration: np.ndarray | None = None) -> tuple[np.ndarray, list]:
    rng = np.random.default_rng(2020)
    segs = tl.segments()
    t_film = np.arange(n_samples) / SR
    bed = np.zeros(n_samples)
    hits = np.zeros(n_samples)
    events = []

    def ev(at, sound, seg):
        events.append({"film_s": round(at, 3), "sound": sound, "segment": seg})

    for s in segs:
        v = s["variant"]
        i0, i1 = int(s["t0"] * SR), int(min(s["t1"] * SR, n_samples))
        if i1 <= i0:
            continue
        seg_t = t_film[i0:i1]
        sub = seg_t[::480]
        sim_sub = np.array([tl.sim_time(s, x) for x in sub])
        p = pitch_of(abs(s["time_scale"])) if v != "raising" else 1.0
        idx = np.arange(i1 - i0)
        if v != "raising":
            spd = np.interp(idx, np.arange(0, i1 - i0, 480)[:len(sim_sub)], [om.speed(float(x), v) for x in sim_sub])
            roll = np.clip(spd / om.V0, 0, 1)
            bed[i0:i1] += db(-28) * (0.35 + 0.65 * roll) * _band_noise(i1 - i0, 35 * p + 15, 420 * p + 60, rng)
            bed[i0:i1] += db(-32) * roll * _band_noise(i1 - i0, 400 * p, 2500 * p, rng)
        if v in ("old", "raised"):
            ft = film_time_of(s, 0.0)
            if ft is not None:
                _place(hits, ft, impact(p, rng, heavy=1.0 if v == "old" else 0.6), db(-12 if v == "old" else -16))
                ev(ft, "beam hit", s["label"])
            peel_rate = np.zeros(i1 - i0)
            pr = []
            for x in sim_sub:
                pr.append(om.speed(float(x), v) if 0.0 < x < om._crash(v)["stop_t"] else 0.0)
            peel_rate = np.interp(idx, np.arange(0, i1 - i0, 480)[:len(pr)], pr)
            k = np.clip(peel_rate / om.V0, 0, 1)
            if k.any():
                tear = _band_noise(i1 - i0, 900 * p, 9000 * p, rng) * (0.6 + 0.4 * np.sin(2 * np.pi * 37 * seg_t) ** 2)
                bed[i0:i1] += db(-22) * k * tear + db(-27) * k * _band_noise(i1 - i0, 120 * p, 700 * p, rng)
                ev(s["t0"], "roof tearing", s["label"])
            for r in om.rivets():
                tp = om.pop_time(r, v)
                if tp is None:
                    continue
                ft = film_time_of(s, tp)
                if ft is not None and s["t0"] <= ft < s["t1"]:
                    for side in (0, 1):
                        _place(hits, ft + 0.004 * side, tick(rng, p), db(-19))
            for b in om.bows():
                tp = om.pop_time(b, v)
                if tp is None:
                    continue
                ft = film_time_of(s, tp)
                if ft is not None and s["t0"] <= ft < s["t1"]:
                    _place(hits, ft, clank(rng, p), db(-17))
                    ev(ft, "roof bow buckles", s["label"])
            stop = om._crash(v)["stop_t"]
            brake = np.array([1.0 if om.T_REACT <= x < stop else 0.0 for x in sim_sub])
            brake = np.interp(idx, np.arange(0, i1 - i0, 480)[:len(brake)], brake)
            if brake.any():
                sq = np.sin(2 * np.pi * (2300 * p) * seg_t + 3 * np.sin(2 * np.pi * 7 * seg_t))
                bed[i0:i1] += db(-31) * brake * (sq + 0.5 * _band_noise(i1 - i0, 1500 * p, 5000 * p, rng))
                ev(s["t0"], "brakes", s["label"])
        if v == "warned":
            for x0, x1, name in ((0.0, 3.4, "detector alarm"),):
                ft = film_time_of(s, x0)
                if ft is not None:
                    n = int(min(x1 - x0, s["t1"] - ft) * SR)
                    tt = np.arange(n) / SR
                    beep = np.sin(2 * np.pi * 1400 * tt) * (np.sin(2 * np.pi * 3.0 * tt) > 0)
                    _place(bed, ft, beep * np.minimum(1.0, tt / 0.01), db(-27))
                    ev(ft, name, s["label"])
            for x, name in ((om.SIGNAL_YELLOW[0], "signal to yellow"), (om.SIGNAL_YELLOW[1], "signal to red")):
                ft = film_time_of(s, x)
                if ft is not None:
                    _place(hits, ft, tick(rng, 0.6), db(-14))
                    ev(ft, name, s["label"])
            brake = np.array([1.0 if om.braking(float(x), "warned") else 0.0 for x in sim_sub])
            brake = np.interp(idx, np.arange(0, i1 - i0, 480)[:len(brake)], brake)
            bed[i0:i1] += db(-33) * brake * _band_noise(i1 - i0, 2000, 6000, rng)
        if s["flags"].get("train"):
            bed[i0:i1] += db(-19) * _band_noise(i1 - i0, 30, 300, rng) * (0.7 + 0.3 * np.sin(2 * np.pi * 1.6 * seg_t) ** 2)
            clack = np.zeros(i1 - i0)
            for c in np.arange(0.0, (i1 - i0) / SR, 0.21):
                _place(clack, c, _band_noise(int(0.04 * SR), 200, 3000, rng) * _env(int(0.04 * SR), 0.001, 0.012), 1.0)
            bed[i0:i1] += db(-24) * clack
            hn = int(min(1.3, (i1 - i0) / SR - 0.4) * SR)
            if hn > 0:
                _place(bed, s["t0"] + 0.3, horn(hn, rng), db(-27))
                ev(s["t0"] + 0.3, "train horn", s["label"])
        if v == "raising":
            hum = np.sin(2 * np.pi * 96 * seg_t) + 0.5 * np.sin(2 * np.pi * 192 * seg_t)
            ramp = np.clip((seg_t - s["t0"] - 0.4) / 0.3, 0, 1) * np.clip((s["t0"] + 3.25 - seg_t) / 0.3, 0, 1)
            bed[i0:i1] += db(-25) * ramp * (hum + 0.4 * _band_noise(i1 - i0, 200, 1200, rng))
            ev(s["t0"] + 0.4, "jacks lifting", s["label"])
    for s in segs[1:]:
        _place(bed, s["t0"] - 0.21, whoosh(rng), db(-26))
        ev(s["t0"], "cut whoosh", s["label"])
    wind = _band_noise(n_samples, 40, 500, rng) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.11 * t_film + 1.0) ** 2)
    bed += db(-39) * wind
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
    print(json.dumps(build(root / "examples/episodes/ep20-audio/narration.wav", out, tl.total_seconds()), indent=1))
