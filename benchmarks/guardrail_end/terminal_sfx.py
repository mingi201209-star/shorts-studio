"""EP.13 sound design (pure numpy, deterministic): the earlier films were narration only. Every sound here is placed from the model and
the timeline, so it lands on the picture:
- impact boom + crunch + steel clang when a shot shows a car touching the head or the blunt rail end (the opening frame starts on one);
- the grind of the rail being squeezed and bent while the head moves (louder with speed), with sparks hiss;
- a sharp crack each time a breakaway post snaps on screen;
- crunch, glass and a metal scrape for the blunt end going into the car;
- a rising tyre/engine roar while a car approaches on screen;
- a soft whoosh on every cut, light wind, and a low pulse that builds under the film.
Slow-motion shots play their sounds deeper and longer, the way slow motion sounds in films (pitch x sqrt(time scale), floored).
The effects bed ducks under the narration so every word stays clear. Output: 48 kHz mono float in [-1, 1]."""
from __future__ import annotations

import json
import math
import wave
from pathlib import Path

import numpy as np

from benchmarks.guardrail_end import terminal_motion as tm
from benchmarks.guardrail_end import terminal_timeline as tl

SR = 48000
SPEAR_SEGS = ("B1-blunt-end", "B2-into-the-cabin")


def db(x: float) -> float:
    return 10 ** (x / 20)


def _env(n, attack, decay):
    t = np.arange(n) / SR
    return np.minimum(1.0, t / max(attack, 1e-4)) * np.exp(-t / decay)


def _band_noise(n, lo, hi, rng):
    """White noise band-limited in the frequency domain (no scipy on the runners)."""
    x = rng.standard_normal(n)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    X[(f < lo) | (f > hi)] = 0.0
    y = np.fft.irfft(X, n)
    return y / (np.std(y) + 1e-9)


def _place(buf, start_s, sig, gain):
    i = int(round(start_s * SR))
    if i >= len(buf) or i + len(sig) <= 0:
        return
    j0 = max(0, -i)
    i0 = max(0, i)
    n = min(len(sig) - j0, len(buf) - i0)
    buf[i0:i0 + n] += gain * sig[j0:j0 + n]


def pitch_of(time_scale: float) -> float:
    return float(np.clip(math.sqrt(max(time_scale, 1e-3)) * 1.25, 0.42, 1.0))


def impact(p, rng, heavy=1.0):
    """Boom (sub sweep), crunch (band noise) and a steel clang (inharmonic partials); p < 1 = slow motion: lower and longer."""
    dur = 2.4
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = (72 * p) * np.exp(-t / 0.35) + 34 * p
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.004, 0.42 / p)
    crunch = _band_noise(n, 250 * p, 3600 * p, rng) * _env(n, 0.002, 0.16 / p)
    clang = sum(a * np.sin(2 * np.pi * fr * p * t + ph) * np.exp(-t / (dc / p))
                for fr, a, dc, ph in ((517, 0.5, 0.9, 0.3), (1283, 0.35, 0.55, 1.1), (2311, 0.22, 0.35, 2.0), (3577, 0.12, 0.22, 0.7)))
    return heavy * (1.0 * boom + 0.55 * crunch) + 0.35 * clang


def post_crack(p, rng):
    n = int(0.6 * SR)
    t = np.arange(n) / SR
    crack = _band_noise(n, 1400 * p, 9000 * p, rng) * _env(n, 0.0008, 0.035 / p)
    thunk = np.sin(2 * np.pi * 150 * p * t) * _env(n, 0.002, 0.11 / p)
    return 0.8 * crack + 0.6 * thunk


def glass(p, rng):
    n = int(0.9 * SR)
    out = np.zeros(n)
    for _ in range(26):
        i = int(rng.uniform(0, 0.35) * SR)
        f = rng.uniform(2800, 7500) * p
        m = int(rng.uniform(0.04, 0.16) / p * SR)
        m = min(m, n - i)
        tt = np.arange(m) / SR
        out[i:i + m] += rng.uniform(0.2, 0.6) * np.sin(2 * np.pi * f * tt) * np.exp(-tt / (0.03 / p))
    return out


def whoosh(rng):
    n = int(0.42 * SR)
    t = np.arange(n) / SR
    env = np.sin(np.pi * t / t[-1]) ** 2
    return _band_noise(n, 300, 2600, rng) * env


def render_sfx(n_samples: int, narration: np.ndarray | None = None) -> tuple[np.ndarray, list]:
    rng = np.random.default_rng(1313)
    segs = tl.segments()
    t_film = np.arange(n_samples) / SR
    bed = np.zeros(n_samples)        # continuous sounds (ducked under speech)
    hits = np.zeros(n_samples)       # impacts and cracks (ducked less)
    events = []

    # per-sample simulated time, segment index and pitch
    seg_idx = np.zeros(n_samples, int)
    for k, s in enumerate(segs):
        seg_idx[(t_film >= s["t0"]) & (t_film < s["t1"])] = k
    seg_idx[t_film >= segs[-1]["t1"]] = len(segs) - 1
    sim = np.array([tl.sim_time(segs[k], tf) for k, tf in zip(seg_idx[::48], t_film[::48])])
    sim = np.interp(t_film, t_film[::48], sim)
    pitch = np.array([pitch_of(abs(segs[k]["time_scale"])) for k in seg_idx])

    # grind of the rail in the head (terminal shots, head moving) and a scrape for the blunt end
    speed = np.zeros(n_samples)
    scrape = np.zeros(n_samples)
    for i in range(0, n_samples, 480):
        s = segs[seg_idx[i]]
        j = slice(i, min(n_samples, i + 480))
        if s["label"] in SPEAR_SEGS:
            st = tm.spear_state(sim[i])
            scrape[j] = (st["v"] / tm.V0) if st["contact"] else 0.0
        else:
            st = tm.terminal_state(sim[i])
            speed[j] = (st["v"] / tm.V0) if st["contact"] else 0.0
    sm = np.convolve(speed, np.ones(960) / 960, mode="same")
    noise_lo = _band_noise(n_samples, 90, 700, rng)
    # steel resonances: narrow noise bands, a high set for real-time shots and a lower set for slow motion, cross-faded by pitch
    hi_set = sum(_band_noise(n_samples, f * 0.96, f * 1.04, rng) * a for f, a in ((1120, 1.0), (2330, 0.7), (3710, 0.45)))
    lo_set = sum(_band_noise(n_samples, f * 0.96, f * 1.04, rng) * a for f, a in ((560, 1.0), (1160, 0.7), (1850, 0.45)))
    mixk = np.clip((pitch - 0.42) / 0.58, 0.0, 1.0)
    ring = (mixk * hi_set + (1 - mixk) * lo_set) / 2.0
    jitter = 1 + 0.06 * np.sin(2 * np.pi * 7.3 * t_film) + 0.04 * np.sin(2 * np.pi * 13.1 * t_film)
    inst = (320 + 260 * sm) * pitch * jitter               # screech partial: falls with speed and in slow motion (wobble on the frequency)
    phase = 2 * np.pi * np.cumsum(inst) / SR
    screech = np.sin(phase) + 0.5 * np.sin(2.71 * phase) + 0.3 * np.sin(4.13 * phase)
    grind = sm ** 0.7 * (0.55 * noise_lo + 0.45 * ring + 0.18 * screech)
    bed += db(-17) * grind
    sc = np.convolve(scrape, np.ones(960) / 960, mode="same")
    bed += db(-19) * sc ** 0.7 * (0.7 * noise_lo + 0.25 * np.sin(2 * np.pi * np.cumsum(180 * pitch) / SR))

    # approaching car: tyre roar rising as it closes on the impact point (shots before contact)
    approach = np.zeros(n_samples)
    for i in range(0, n_samples, 480):
        s = segs[seg_idx[i]]
        if sim[i] < 0 and s["label"] in ("B1-blunt-end", "C-steel-head", "H-waiting"):
            d = -sim[i] * tm.V0
            approach[i:i + 480] = 1.0 / (1.0 + d / 6.0)
    ap = np.convolve(approach, np.ones(2400) / 2400, mode="same")
    bed += db(-16) * ap * _band_noise(n_samples, 70, 1500, rng)

    # impacts: a contact inside a shot, or a shot that opens just after one (the first frame)
    for s in segs:
        p = pitch_of(abs(s["time_scale"]))
        at = None
        if s["sim0"] < 0 <= s["sim1"]:
            at = tl.film_time_of(s, 0.0)
        elif s["label"] == "A-ribbon":
            at = 0.0
        if at is not None:
            spear = s["label"] in SPEAR_SEGS
            _place(hits, at, impact(p, rng, heavy=1.2 if spear else 1.0), db(-4))
            if spear:
                _place(hits, at + 0.01, glass(p, rng), db(-10))
            events.append({"film_s": round(at, 3), "sound": "impact", "segment": s["label"], "pitch": round(p, 2)})
        if s["label"] not in SPEAR_SEGS:
            for k, tk in enumerate(tm.post_break_times()):
                if tk is not None:
                    ft = tl.film_time_of(s, tk)
                    if ft is not None and ft > s["t0"] + 0.02:
                        _place(hits, ft, post_crack(p, rng), db(-9))
                        events.append({"film_s": round(ft, 3), "sound": f"post {k} snaps", "segment": s["label"]})
    for s in segs[1:]:
        _place(bed, s["t0"] - 0.21, whoosh(rng), db(-24))
        events.append({"film_s": round(s["t0"], 3), "sound": "cut whoosh", "segment": s["label"]})

    # wind and a low pulse that builds toward the end (loops back into the opening hit)
    wind = _band_noise(n_samples, 40, 500, rng)
    wind *= 0.6 + 0.4 * np.sin(2 * np.pi * 0.11 * t_film + 1.0) ** 2
    bed += db(-36) * wind
    beat = 60.0 / 92.0
    pulse = np.zeros(n_samples)
    kick = np.sin(2 * np.pi * np.cumsum(55 * np.exp(-np.arange(int(0.35 * SR)) / SR / 0.08) + 42) / SR) * _env(int(0.35 * SR), 0.003, 0.12)
    k = 0.0
    while k < t_film[-1]:
        _place(pulse, k, kick, 1.0)
        k += beat
    build = 0.55 + 0.45 * np.clip(t_film / t_film[-1], 0, 1)
    drone = (np.sin(2 * np.pi * 55 * t_film) + 0.6 * np.sin(2 * np.pi * 82.4 * t_film + 0.5)) * (0.7 + 0.3 * np.sin(2 * np.pi * 0.2 * t_film))
    bed += db(-30) * build * (0.8 * pulse + 0.35 * drone)

    # duck under the narration
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


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        assert w.getframerate() == SR and w.getnchannels() == 1, "narration must be 48 kHz mono"
        raw = w.readframes(w.getnframes())
        width = w.getsampwidth()
    if width == 2:
        return np.frombuffer(raw, "<i2").astype(np.float64) / 32768.0
    if width == 4:
        return np.frombuffer(raw, "<i4").astype(np.float64) / 2147483648.0
    raise ValueError(f"unsupported sample width {width}")


def write_wav(path: Path, x: np.ndarray) -> None:
    y = np.clip(x, -1.0, 1.0)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((y * 32767).astype("<i2").tobytes())


def limit(x: np.ndarray, ceiling_db: float = -1.5, release_s: float = 0.08) -> np.ndarray:
    """Look-ahead peak limiter: gain is the minimum needed over a 5 ms window around each block, released smoothly."""
    c = db(ceiling_db)
    blk = 240
    n = len(x)
    nb = (n + blk - 1) // blk
    pad = np.pad(np.abs(x), (0, nb * blk - n)).reshape(nb, blk).max(axis=1)
    need = np.minimum(1.0, c / np.maximum(pad, 1e-9))
    need = np.minimum(need, np.minimum(np.roll(need, -1), np.roll(need, 1)))
    g = np.empty(nb)
    cur, k = 1.0, math.exp(-blk / SR / release_s)
    for i in range(nb):
        cur = need[i] if need[i] < cur else need[i] + (cur - need[i]) * k
        g[i] = cur
    gs = np.interp(np.arange(n), np.arange(nb) * blk + blk / 2, g)
    return x * gs


def lufs(path: Path) -> tuple[float, float]:
    """Integrated loudness and true peak, measured by ffmpeg's ebur128 (the same meter the other gates use)."""
    import re
    import subprocess
    err = subprocess.run(["ffmpeg", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    tail = err[err.rindex("Integrated loudness"):]
    i = float(re.search(r"I:\s+(-?\d+\.\d+)\s+LUFS", tail).group(1))
    tp = float(re.search(r"Peak:\s+(-?\d+\.\d+)\s+dBFS", tail).group(1))
    return i, tp


def build(narration_wav: Path, out_dir: Path, seconds: float, sfx_gain_db: float = -2.0, target_lufs: float = -15.0) -> dict:
    """Writes sfx.wav (effects alone), mix.wav (narration + effects) and sfx-events.json; returns level facts for the gate."""
    out_dir.mkdir(parents=True, exist_ok=True)
    narr = read_wav(narration_wav)
    n = int(round(seconds * SR))
    narr = np.pad(narr, (0, max(0, n - len(narr))))[:n]
    sfx, events = render_sfx(n, narr)
    mix = limit(narr + db(sfx_gain_db) * sfx)
    write_wav(out_dir / "mix.wav", mix)
    for _ in range(3):                                   # bring the mix to the target loudness, limiting the peaks it adds
        i_lufs, _tp = lufs(out_dir / "mix.wav")
        if abs(i_lufs - target_lufs) < 0.3:
            break
        mix = limit(mix * db(target_lufs - i_lufs), ceiling_db=-2.0)
        write_wav(out_dir / "mix.wav", mix)
    i_lufs, tp = lufs(out_dir / "mix.wav")
    write_wav(out_dir / "sfx.wav", sfx)
    (out_dir / "sfx-events.json").write_text(json.dumps(events, indent=1))
    # speech clarity: effects RMS while a line is spoken vs the narration RMS there
    beats = json.loads(tl.AUDIO.read_text())["beats"]
    worst = 99.0
    for b in beats:
        i0, i1 = int(b["start"] * SR), int(b["end"] * SR)
        r_n = np.sqrt(np.mean(narr[i0:i1] ** 2)) + 1e-9
        r_s = np.sqrt(np.mean((db(sfx_gain_db) * sfx[i0:i1]) ** 2)) + 1e-9
        worst = min(worst, 20 * math.log10(r_n / r_s))
    return {"events": len(events), "speech_over_effects_db_min": round(worst, 1), "mix_lufs": i_lufs, "mix_true_peak_dbfs": tp,
            "mix_peak_dbfs": round(20 * math.log10(np.max(np.abs(mix)) + 1e-9), 2)}


if __name__ == "__main__":
    import sys
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("sfx-out")
    root = Path(__file__).resolve().parents[2]
    print(json.dumps(build(root / "examples/episodes/ep13-audio/narration.wav", out, tl.total_seconds()), indent=1))
