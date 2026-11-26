"""EP.34 sound design (pure numpy, deterministic), built like EP.13-EP.33's. Every sound is placed from the model and the timeline:
- the runaway: a big diesel roaring and tyres humming, pitched by the truck's speed;
- each net it picks up: a steel twang and a snap of cables at the moment its front reaches the net;
- the absorbers: a gritty metallic buzz while the tapes run through the pins, its rate set by how fast the tape pays out (louder in
  the cut-away close-ups); the coils ticking round in the cut-away;
- the stop: the last creak of the nets and an air-brake hiss;
- the crew: a few clanks as the fresh coil goes in;
- the reveal: the channel's signature sting on the cut;
- a whoosh on every other cut, mountain wind and a low pulse.
Ducks under the narration; mixed to -15 LUFS with a peak limiter (helpers shared with EP.13-EP.33)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from benchmarks.guardrail_end.terminal_sfx import SR, _band_noise, _env, _place, db, impact, limit, lufs, pitch_of, read_wav, whoosh, write_wav
from benchmarks.signature_sting import RISE_S, reveal_sting
from benchmarks.tempered_glass.glass_sfx import film_time_of
from benchmarks.truck_net import net_motion as m
from benchmarks.truck_net import net_timeline as tl


def twang(rng, p=1.0):
    """A steel net snapping taut: a falling inharmonic ring with a crack of cable on the front."""
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    ring = sum(a * np.sin(2 * np.pi * f * p * (1.0 - 0.25 * t) * t) * np.exp(-t / d) for f, a, d in ((210, 0.8, 0.25), (520, 0.5, 0.16), (1310, 0.35, 0.08)))
    crack = _band_noise(n, 1500 * p, 9000 * p + 500, rng) * _env(n, 0.0005, 0.018)
    return 0.7 * ring + 0.9 * crack


def clank(rng, p=1.0):
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    ring = sum(a * np.sin(2 * np.pi * f * p * t) * np.exp(-t / d) for f, a, d in ((180, 0.9, 0.14), (470, 0.5, 0.09), (1150, 0.3, 0.05)))
    return ring + 0.5 * _band_noise(n, 150, 3500, rng) * _env(n, 0.001, 0.02)


def hiss(rng):
    n = int(1.1 * SR)
    return _band_noise(n, 2500, 9000, rng) * _env(n, 0.01, 0.35)


def states(sim: np.ndarray, variant: str) -> dict:
    """The model along a stretch of simulated time: speed, tape speed summed over the engaged nets, engaged count."""
    rating = variant == "rating"
    v = np.zeros(len(sim))
    tape = np.zeros(len(sim))
    eng = np.zeros(len(sim))
    for k, s in enumerate(sim):
        st = m.truck_state(float(s), rating)
        v[k] = st["speed"]
        tape[k] = sum(d / math.hypot(m.S_SIDE, d) * st["speed"] for d in st["d"] if d > 0.0)
        eng[k] = st["engaged"]
    return {"speed": v, "tape": tape, "engaged": eng}


def engage_times(rating: bool) -> list[float]:
    """Simulated time at which the front reaches each net."""
    rows = m.catch(*((m.RATING_LB, m.RATING_MPH) if rating else (m.TRUCK_LB, m.V0_MPH)))
    out = []
    for y in m.NET_Y:
        hit = next((r[0] for r in rows if r[1] >= y), None)
        out.append(hit)
    return out


def render_sfx(n_samples: int, narration: np.ndarray | None = None) -> tuple[np.ndarray, list]:
    rng = np.random.default_rng(3434)
    segs = tl.segments()
    t_film = np.arange(n_samples) / SR
    bed = np.zeros(n_samples)
    hits = np.zeros(n_samples)
    events = []

    def ev(at, sound, seg):
        events.append({"film_s": round(at, 3), "sound": sound, "segment": seg})

    for s in segs:
        i0, i1 = int(s["t0"] * SR), int(min(s["t1"] * SR, n_samples))
        if i1 <= i0:
            continue
        seg_t = t_film[i0:i1]
        p = pitch_of(abs(s["time_scale"]))
        variant = s["variant"]
        if variant != "reset":
            sub = seg_t[::480]
            sim_sub = np.array([tl.sim_time(s, x) for x in sub])
            stx = states(sim_sub, variant)
            speed = np.interp(seg_t, sub, stx["speed"])
            tape = np.interp(seg_t, sub, stx["tape"])
            moving = np.clip(speed / 8.0, 0, 1)
            # the runaway's diesel and tyres, pitched by speed (and by slow motion)
            f_eng = (38.0 + 1.6 * speed) * p
            eng = np.sin(2 * np.pi * np.cumsum(f_eng) / SR) + 0.5 * np.sin(2 * np.pi * np.cumsum(2.02 * f_eng) / SR)
            roar = _band_noise(i1 - i0, 60 * p + 20, 700 * p + 100, rng)
            bed[i0:i1] += moving * (db(-24) * eng + db(-26) * roar)
            # the absorbers: a gritty buzz at the pins' rate (tape speed / pin spacing)
            rate = tape / 0.13 * p
            buzz = _band_noise(i1 - i0, 700 * p + 100, 5200 * p + 400, rng) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * np.cumsum(rate) / SR)))
            amount = np.clip(tape / 12.0, 0, 1)
            close = 1.4 if s["flags"].get("cut") else 1.0
            bed[i0:i1] += db(-19) * close * amount * buzz
            if amount.max() > 0.05:
                ev(s["t0"], "tapes buzz through the pins", s["label"])
            # each net picked up: a twang and a snap at the moment the front reaches it
            for k, te in enumerate(engage_times(variant == "rating")):
                if te is None:
                    continue
                at = film_time_of(s, te)
                if at is not None and s["t0"] - 1e-6 <= at < s["t1"]:
                    _place(hits, at, twang(rng, max(p, 0.5)), db(-7))
                    _place(hits, at, impact(p * 0.8, rng, heavy=1.1), db(-14))
                    ev(at, f"net {k + 1} snaps on", s["label"])
            if s["label"] == "A1-net-grabs":
                _place(hits, 0.0, twang(rng, max(p, 0.5)), db(-8))
                _place(hits, 0.0, impact(p * 0.8, rng, heavy=1.3), db(-11))
                ev(0.0, "net 1 snaps on (already happening)", s["label"])
            # the stop: the nets' last creak and an air-brake hiss
            t_stop = m.stop_time(*((m.RATING_LB, m.RATING_MPH) if variant == "rating" else (m.TRUCK_LB, m.V0_MPH)))
            at = film_time_of(s, t_stop)
            if at is not None and s["t0"] <= at < s["t1"]:
                _place(hits, at + 0.05, hiss(rng), db(-20))
                ev(at, "stopped: air-brake hiss", s["label"])
        else:
            for k, at in enumerate((0.35, 1.25, 1.9)):
                _place(hits, s["t0"] + at, clank(rng, 1.0 - 0.1 * k), db(-16))
            ev(s["t0"], "fresh coil clanks in", s["label"])
        if s["flags"].get("reveal"):
            _place(hits, s["t0"] - RISE_S, reveal_sting(SR), db(-8))
            ev(s["t0"], "signature reveal sting", s["label"])

    for k, s in enumerate(segs[1:]):
        if s["flags"].get("reveal") or k % 2:
            continue
        _place(bed, s["t0"] - 0.21, whoosh(rng), db(-26))
        ev(s["t0"], "cut whoosh", s["label"])
    wind = _band_noise(n_samples, 40, 600, rng) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.13 * t_film + 0.7) ** 2)
    bed += db(-34) * wind
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
    print(json.dumps(build(root / "examples/episodes/ep34-audio/narration.wav", out, tl.total_seconds()), indent=1))
