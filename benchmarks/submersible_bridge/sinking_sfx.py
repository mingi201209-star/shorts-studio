"""EP.27 sound design (pure numpy, deterministic), built like EP.13-EP.26's: every sound is placed from the model and the timeline.
- the coast: small waves lapping at the quays, wind, cicadas, now and then a gull; under water all of it muffled and a low hum;
- the warning bell while the gates come down, and the gates' motor;
- the bridge's machinery while the deck moves (a hydraulic whine and rumble that follow the deck's speed), a clunk as it starts and
  as it settles;
- water: a rush as the sea floods over the road, bubbles while the deck sinks (louder under water), water pouring off its edges and
  dripping as it comes back up;
- the ship: a diesel throb that grows as it nears the bridge and one long horn blast before it reaches the mouth;
- a whoosh on every cut and a quiet low pulse.
Ducks under the narration; mixed to -15 LUFS with a peak limiter (helpers shared with EP.13-EP.26)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from benchmarks.guardrail_end.terminal_sfx import SR, _band_noise, _env, _place, db, limit, lufs, read_wav, whoosh, write_wav
from benchmarks.submersible_bridge import sinking_motion as sm
from benchmarks.submersible_bridge import sinking_timeline as tl

HORN_T = 52.0                                       # the ship sounds its horn far out, coming in (heard in the aerial)


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


def lowpass(x: np.ndarray, n: int = 40) -> np.ndarray:
    return np.convolve(x, np.ones(n) / n, mode="same")


def clunk(rng, size=1.0):
    n = int(1.0 * SR)
    t = np.arange(n) / SR
    body = np.sin(2 * np.pi * np.cumsum(60 / size * np.exp(-t / 0.25) + 30) / SR) * np.exp(-t / 0.4)
    ring = 0.3 * np.sin(2 * np.pi * 280 / size * t) * np.exp(-t / 0.3)
    return (body + ring + 0.4 * _band_noise(n, 60, 2000, rng) * np.exp(-t / 0.03)) * _env(n, 0.002, 0.9)


def bell(n_rings):
    one = int(0.5 * SR)
    t = np.arange(one) / SR
    d = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t / tau) for f, a, tau in ((1180, 1.0, 0.25), (2950, 0.5, 0.12), (4400, 0.25, 0.06)))
    return np.tile(d, n_rings)


def horn(dur=2.6):
    n = int(dur * SR)
    t = np.arange(n) / SR
    tone = sum(a * np.sin(2 * np.pi * f * t + 0.25 * np.sin(2 * np.pi * 4 * t)) for f, a in ((147, 1.0), (294, 0.55), (441, 0.3), (588, 0.15)))
    return tone * _env(n, 0.1, 0.4)


def gull(rng):
    n = int(0.55 * SR)
    t = np.arange(n) / SR
    f = 1500 + 700 * np.exp(-t / 0.12) * np.sin(2 * np.pi * 3 * t) ** 2
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.03, 0.2) * (0.6 + 0.4 * np.sin(2 * np.pi * 9 * t))


def bubble(rng):
    n = int(0.08 * SR)
    t = np.arange(n) / SR
    f0 = rng.uniform(350, 900)
    return np.sin(2 * np.pi * np.cumsum(f0 * (1 + 2.5 * t / 0.08)) / SR) * np.exp(-t / 0.025)


def render_sfx(n_samples: int, narration: np.ndarray | None = None) -> tuple[np.ndarray, list]:
    rng = np.random.default_rng(2727)
    segs = tl.segments()
    t_film = np.arange(n_samples) / SR
    bed = np.zeros(n_samples)
    hits = np.zeros(n_samples)
    events = []

    def ev(at, sound, seg):
        events.append({"film_s": round(at, 3), "sound": sound, "segment": seg})

    t_land = sm.T_DOWN0 + sm.move_time()
    for s in segs:
        i0, i1 = int(s["t0"] * SR), int(min(s["t1"] * SR, n_samples))
        if i1 <= i0:
            continue
        n = i1 - i0
        seg_t = t_film[i0:i1]
        under = bool(s["flags"].get("under"))
        idx = np.arange(n)
        grid = np.arange(0, n, 240)
        sims = np.array([tl.sim_time(s, seg_t[0] + g / SR) for g in grid])
        speed = np.interp(idx, grid, [abs(sm.deck_speed(float(x))) / sm.V_SINK for x in sims])
        layer = np.zeros(n)
        whine_f = 180.0 + 60.0 * speed
        whine = np.sin(2 * np.pi * np.cumsum(whine_f) / SR) * (0.6 + 0.4 * np.sin(2 * np.pi * 7 * seg_t) ** 2)
        layer += db(-27) * speed * (0.5 * whine + _band_noise(n, 40, 300, rng))
        if speed.max() > 0.05:
            ev(s["t0"], "bridge machinery running", s["label"])
        flood = np.interp(idx, grid, [math.exp(-((sm.deck_z(float(x)) - 0.02) / 0.28) ** 2) if sm.deck_speed(float(x)) < 0 else 0.0 for x in sims])
        layer += db(-22) * flood * _band_noise(n, 200, 5000, rng)
        if flood.max() > 0.3:
            ev(s["t0"] + float(np.argmax(flood > 0.3)) / SR, "sea flooding over the road", s["label"])
        pour = np.interp(idx, grid, [math.exp(-max(0.0, float(x) - sm.t_out()) / 9.0) if (float(x) > sm.t_out() and sm.deck_z(float(x)) > 0.02) else 0.0
                                     for x in sims])
        layer += db(-23) * pour * _band_noise(n, 300, 6000, rng)
        if pour.max() > 0.3:
            ev(s["t0"] + float(np.argmax(pour > 0.3)) / SR, "water pouring off the deck", s["label"])
        sinking = np.interp(idx, grid, [1.0 if (sm.T_DOWN0 + 8.0 < float(x) < t_land + 15.0 and sm.deck_z(float(x)) < -0.3) else 0.0 for x in sims])
        if sinking.max() > 0.5:
            n_b = int((s["t1"] - s["t0"]) * (9 if under else 3))
            for _ in range(n_b):
                at = s["t0"] + rng.uniform(0, s["t1"] - s["t0"])
                if sinking[min(n - 1, int((at - s["t0"]) * SR))] > 0.5:
                    _place(hits, at, bubble(rng), db(-24 if under else -34))
            ev(s["t0"], "bubbles from the girders", s["label"])
        dist = np.interp(idx, grid, [abs(sm.ship_bow_y(float(x)) - sm.SHIP_L / 2) for x in sims])
        throb = np.sin(2 * np.pi * 38 * seg_t) * (0.6 + 0.4 * np.sin(2 * np.pi * 6.3 * seg_t) ** 2) + 0.5 * _band_noise(n, 30, 160, rng)
        layer += db(-24) * throb / (1.0 + dist / 30.0)
        for x, name in ((sm.T_DOWN0 + 0.2, "deck starts down"), (t_land - 0.2, "deck settles"), (sm.T_UP0 + 0.2, "deck starts up"),
                        (sm.T_UP0 + sm.move_time() - 0.2, "deck locks at the top")):
            ft = film_time_of(s, x)
            if ft is not None:
                _place(hits, ft, clunk(rng), db(-15 if under else -18))
                ev(ft, name, s["label"])
        ft0, ft1 = film_time_of(s, max(sm.T_GATES_CLOSE - 8.0, s["sim0"])), film_time_of(s, min(sm.T_GATES_CLOSE + 8.0, s["sim1"]))
        if ft0 is not None and ft1 is not None and ft1 - ft0 > 0.3:
            b = bell(int((ft1 - ft0) / 0.5) + 1)
            _place(hits, ft0, b[: int((ft1 - ft0) * SR)], db(-23))
            ev(ft0, "warning bell", s["label"])
        ft = film_time_of(s, HORN_T)
        if ft is not None:
            _place(hits, ft, horn(), db(-18))
            ev(ft, "ship's horn", s["label"])
        if under:
            layer = lowpass(layer, 60) * 1.6 + db(-32) * _band_noise(n, 30, 200, rng)
        bed[i0:i1] += layer
    for s in segs[1:]:
        _place(bed, s["t0"] - 0.21, whoosh(rng), db(-28))
        ev(s["t0"], "cut whoosh", s["label"])
    lap = _band_noise(n_samples, 150, 1800, rng) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.45 * t_film) ** 2)
    wind = _band_noise(n_samples, 80, 1200, rng) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.07 * t_film + 1.0) ** 2)
    cic = _band_noise(n_samples, 4200, 6500, rng) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 21 * t_film))) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.3 * t_film) ** 2)
    amb = db(-36) * lap + db(-40) * wind + db(-46) * cic
    under_mask = np.zeros(n_samples)
    for s in segs:
        if s["flags"].get("under"):
            under_mask[int(s["t0"] * SR):int(s["t1"] * SR)] = 1.0
    amb = amb * (1.0 - under_mask) + lowpass(amb, 80) * 0.5 * under_mask
    bed += amb
    for _ in range(6):
        at = rng.uniform(0.5, t_film[-1] - 0.6)
        if under_mask[int(at * SR)] < 0.5:
            _place(bed, at, gull(rng), db(-38))
    beat = 60.0 / 92.0
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
    print(json.dumps(build(root / "examples/episodes/ep27-audio/narration.wav", out, tl.total_seconds()), indent=1))
