"""EP.35 sound design (pure numpy, deterministic), built like EP.13-EP.34's. Every sound is placed from the model and the timeline:
- the jet: turbine whine and roar, louder and higher at full power from touchdown;
- touchdown: the tyres slam onto the deck; the hook scrapes and sparks until it catches;
- the catch: a steel twang as the wire snaps taut, then the purchase cable roaring out over its sheaves (pitched by its speed);
- below deck (the x-ray shots): oil rushing through the valve and a deep hydraulic groan, louder with the flow;
- the stop: the engines spooling down;
- the deck crew: clanks as the worn wire is unhooked and dragged;
- the reveal: the channel's signature sting on the cut;
- a whoosh on every other cut, sea wind and a low pulse.
Ducks under the narration; mixed to -15 LUFS with a peak limiter (helpers shared with EP.13-EP.34)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from benchmarks.carrier_wire import wire_motion as m
from benchmarks.carrier_wire import wire_timeline as tl
from benchmarks.guardrail_end.terminal_sfx import SR, _band_noise, _env, _place, db, impact, limit, lufs, pitch_of, read_wav, whoosh, write_wav
from benchmarks.signature_sting import RISE_S, reveal_sting
from benchmarks.tempered_glass.glass_sfx import film_time_of

T_TD = -0.35


def twang(rng, p=1.0):
    n = int(1.0 * SR)
    t = np.arange(n) / SR
    ring = sum(a * np.sin(2 * np.pi * f * p * (1.0 - 0.2 * t) * t) * np.exp(-t / d) for f, a, d in ((140, 0.9, 0.35), (380, 0.5, 0.2), (960, 0.3, 0.09)))
    crack = _band_noise(n, 1500 * p, 9000 * p + 500, rng) * _env(n, 0.0005, 0.02)
    return 0.75 * ring + 0.9 * crack


def clank(rng, p=1.0):
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    ring = sum(a * np.sin(2 * np.pi * f * p * t) * np.exp(-t / d) for f, a, d in ((210, 0.9, 0.12), (540, 0.5, 0.08), (1300, 0.3, 0.04)))
    return ring + 0.5 * _band_noise(n, 200, 4000, rng) * _env(n, 0.001, 0.02)


def render_sfx(n_samples: int, narration: np.ndarray | None = None) -> tuple[np.ndarray, list]:
    rng = np.random.default_rng(3535)
    segs = tl.segments()
    t_film = np.arange(n_samples) / SR
    bed = np.zeros(n_samples)
    hits = np.zeros(n_samples)
    events = []
    t_stop = m.stop_time()

    def ev(at, sound, seg):
        events.append({"film_s": round(at, 3), "sound": sound, "segment": seg})

    for s in segs:
        i0, i1 = int(s["t0"] * SR), int(min(s["t1"] * SR, n_samples))
        if i1 <= i0:
            continue
        seg_t = t_film[i0:i1]
        p = pitch_of(abs(s["time_scale"]))
        if s["variant"] == "jet":
            sub = seg_t[::480]
            sim = np.interp(seg_t, sub, np.array([tl.sim_time(s, x) for x in sub]))
            speed = np.interp(sim, [r[0] for r in m.arrest()][::200], [r[2] for r in m.arrest()][::200], left=m.V0, right=0.0)
            power = ((sim >= T_TD) & (sim < t_stop + 0.3)).astype(float)
            spool = np.clip(1.0 - (sim - t_stop - 0.3) / 1.2, 0.35, 1.0) * (sim > t_stop + 0.3) + power
            level = np.clip(0.55 + 0.45 * spool, 0, 1)
            whine = np.sin(2 * np.pi * np.cumsum((2400 + 900 * spool) * p) / SR)
            roar = _band_noise(i1 - i0, 50 * p + 20, 1400 * p + 200, rng)
            bed[i0:i1] += level * (db(-31) * whine + db(-22) * roar)
            scrape = ((sim >= T_TD) & (sim < 0)).astype(float)
            if scrape.any():
                bed[i0:i1] += scrape * db(-20) * _band_noise(i1 - i0, 900 * p + 200, 7000 * p + 600, rng)
                ev(s["t0"], "hook scrapes the deck", s["label"])
            pay = np.clip(speed / m.V0, 0, 1) * (sim > 0)
            if pay.any():
                rate = (60 + 140 * pay) * p
                whirr = _band_noise(i1 - i0, 40 * p + 20, 600 * p + 80, rng) * (0.6 + 0.4 * np.sin(2 * np.pi * np.cumsum(rate) / SR))
                bed[i0:i1] += db(-19) * pay * whirr
                if s["flags"].get("xray"):
                    rush = _band_noise(i1 - i0, 300 * p, 5000 * p + 300, rng) * (0.7 + 0.3 * np.abs(np.sin(2 * np.pi * 9 * seg_t)))
                    groan = np.sin(2 * np.pi * np.cumsum(55 * p + 20 * pay) / SR)
                    gain = 1.3 if s["flags"].get("heat") else 1.0
                    bed[i0:i1] += pay * gain * (db(-20) * rush + db(-22) * groan)
                    ev(s["t0"], "oil rushes through the valve", s["label"])
            for when, what, sig, g in ((T_TD, "tyres slam onto the deck", impact(p * 0.7, rng, heavy=1.4), db(-13)),
                                       (0.0, "the wire snaps taut", twang(rng, max(p, 0.5)), db(-10))):
                at = film_time_of(s, when)
                if at is not None and s["t0"] - 1e-6 <= at < s["t1"]:
                    _place(hits, at, sig, g)
                    ev(at, what, s["label"])
            if s["label"] == "A1-caught":
                _place(hits, 0.0, twang(rng, max(p, 0.5)), db(-12))
                ev(0.0, "the wire snaps taut (already happening)", s["label"])
        else:
            for k, at in enumerate((0.3, 0.9, 1.5)):
                _place(hits, s["t0"] + at, clank(rng, 1.0 - 0.08 * k), db(-16))
            if s["flags"].get("drag"):
                bed[i0:i1] += db(-22) * _band_noise(i1 - i0, 200, 3000, rng)
            ev(s["t0"], "crew handles the worn wire", s["label"])
        if s["flags"].get("reveal"):
            _place(hits, s["t0"] - RISE_S, reveal_sting(SR), db(-8))
            ev(s["t0"], "signature reveal sting", s["label"])

    for k, s in enumerate(segs[1:]):
        if s["flags"].get("reveal") or k % 2:
            continue
        _place(bed, s["t0"] - 0.21, whoosh(rng), db(-26))
        ev(s["t0"], "cut whoosh", s["label"])
    wind = _band_noise(n_samples, 40, 700, rng) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.15 * t_film + 0.4) ** 2)
    bed += db(-33) * wind
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
    print(json.dumps(build(root / "examples/episodes/ep35-audio/narration.wav", out, tl.total_seconds()), indent=1))
