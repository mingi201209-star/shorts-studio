"""EP.17 sound design (pure numpy, deterministic), built like EP.13-EP.16's: every sound is placed from the model and the timeline.
- the machine: a diesel drone and a hydraulic whine whenever it is in shot's world (day and night shots);
- a heavy concrete clunk each time a block is picked up at the machine's front and each time one is set down at its rear
  (2.2 a second at 5 mph), and a steel rattle from the conveyor wheels in between;
- a whoosh for every traffic car passing the camera; a dense traffic bed in the rush-hour shot; beacon ticks at night;
- a whoosh on every cut, wind and a low pulse.
Ducks under the narration; mixed to -15 LUFS with a peak limiter (helpers shared with EP.13-EP.16)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from benchmarks.guardrail_end.terminal_sfx import SR, _band_noise, _env, _place, db, limit, lufs, read_wav, whoosh, write_wav
from benchmarks.road_zipper import zipper_motion as zm
from benchmarks.road_zipper import zipper_timeline as tl
from benchmarks.tempered_glass.glass_sfx import film_time_of


def clunk(rng):
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    low = np.sin(2 * np.pi * (70 + rng.uniform(-8, 8)) * t) * _env(n, 0.002, 0.09)
    knock = _band_noise(n, 300, 2500, rng) * _env(n, 0.001, 0.025)
    ring = 0.25 * np.sin(2 * np.pi * 820 * t) * np.exp(-t / 0.08)
    return low + 0.6 * knock + ring


def tick(rng):
    n = int(0.05 * SR)
    return _band_noise(n, 2000, 9000, rng) * _env(n, 0.0005, 0.008)


def render_sfx(n_samples: int, narration: np.ndarray | None = None) -> tuple[np.ndarray, list]:
    rng = np.random.default_rng(1717)
    segs = tl.segments()
    t_film = np.arange(n_samples) / SR
    bed = np.zeros(n_samples)
    hits = np.zeros(n_samples)
    events = []

    def ev(at, sound, seg):
        events.append({"film_s": round(at, 3), "sound": sound, "segment": seg})

    for s in segs:
        i0, i1 = int(s["t0"] * SR), int(min(s["t1"] * SR, n_samples))
        tt = t_film[i0:i1]
        if s["variant"] in ("day", "night"):
            rpm = 28 + 4 * np.sin(2 * np.pi * 0.3 * tt)
            diesel = (np.sin(2 * np.pi * np.cumsum(rpm) / SR) + 0.5 * np.sin(2 * np.pi * np.cumsum(2 * rpm) / SR)) * (0.7 + 0.3 * np.abs(_band_noise(i1 - i0, 15, 60, rng)))
            near = 1.0 if abs(s["cam_a"]["loc"][0]) < 8 and abs(s["cam_a"]["loc"][1]) < 16 else 0.5
            bed[i0:i1] += db(-22) * near * diesel + db(-30) * near * np.sin(2 * np.pi * 640 * tt) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.7 * tt))
            bed[i0:i1] += db(-29) * near * _band_noise(i1 - i0, 1500, 6000, rng) * (0.5 + 0.5 * np.abs(np.sin(2 * np.pi * 9 * tt)))
            # a clunk for each block picked up (front) and set down (rear)
            n_c = 0
            for yb in zm.BLOCK_Y:
                for edge, gain in ((zm.LT / 2, -14), (-zm.LT / 2, -16)):
                    sim = (yb - edge) / zm.VM                    # when the machine's front / rear passes this block
                    ft = film_time_of(s, sim)
                    if ft is not None and s["t0"] <= ft < s["t1"]:
                        _place(hits, ft, clunk(rng), db(gain) * near)
                        n_c += 1
            ev(s["t0"], f"{n_c} block clunks", s["label"])
            if s["variant"] == "night":
                k = s["t0"]
                while k < s["t1"]:
                    _place(hits, k, tick(rng), db(-24))
                    k += 1 / 1.5
        if s["variant"] == "morning":
            bed[i0:i1] += db(-20) * _band_noise(i1 - i0, 60, 1500, rng)
        # cars passing the camera
        cam_y = s["cam_a"]["loc"][1]
        x = s["sim0"]
        prev = None
        while x <= s["sim1"]:
            ym = zm.machine_y(x) if s["variant"] != "morning" and s["cam_a"]["rel"] == "machine" else 0.0
            cur = [y - (ym + cam_y) for _, y, _ in zm.traffic(x, s["variant"])]
            if prev is not None:
                for a, b in zip(prev, cur):
                    if a * b < 0 and abs(a - b) < 20:
                        ft = film_time_of(s, x)
                        if ft is not None:
                            _place(bed, ft - 0.2, whoosh(rng), db(-16))
                            ev(ft, "car passes", s["label"])
            prev = cur
            x += 0.05

    for s in segs[1:]:
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
    print(json.dumps(build(root / "examples/episodes/ep17-audio/narration.wav", out, tl.total_seconds()), indent=1))
