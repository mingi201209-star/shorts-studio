"""EP.31 sound design (pure numpy, deterministic), built like EP.13-EP.30's: every sound is placed from the world model and the timeline.
- the snowy street: the hush of falling snow (a soft low bed), a little wind, a far road;
- the jets: a hiss and the patter of drops on the water film, louder the closer the camera is to the nearest nozzle (from the camera
  of every frame); none on the newer road (only a quiet trickle in the pipes);
- the car: its tyres swishing through the water and a low engine, from the car's distance to the camera;
- the water running to the gutter (a gurgle near the road edge);
- under the street: the pump's hum and the rush of water in the pipe (section shots); a deep groan and creaks while the ground sinks;
- a whoosh on every cut and a quiet low pulse.
Ducks under the narration; mixed to -15 LUFS with a peak limiter (helpers shared with EP.13-EP.30)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from benchmarks.guardrail_end.terminal_sfx import SR, _band_noise, _env, _place, db, limit, lufs, read_wav, whoosh, write_wav
from benchmarks.snowmelt_road import snowmelt_timeline as tl
from benchmarks.snowmelt_road import snowmelt_world as w


def frame_track(n_samples: int) -> dict:
    """Per-sample curves from the per-frame states: distance to the nearest nozzle, to the car, to the road edge; the shot's flags."""
    segs = tl.segments()
    n_frames = tl.frame_count()
    noz, car, edge, sec, pipes, sink = [], [], [], [], [], []
    for f in range(n_frames):
        sh = tl.frame_state(f, segs)
        x, y, z = sh["cam"]["loc"]
        d = np.sqrt(x * x + (w.NOZZLE_Y - y) ** 2 + z * z).min()
        noz.append(99.0 if sh.get("pipes") else float(d))
        cy = w.car_y(sh["t"])
        car.append(99.0 if (cy is None or sh.get("section")) else math.dist((x, y, z), (w.LANE_X, cy, 0.6)))
        edge.append(abs(abs(x) - w.ROAD_HALF) + max(0.0, z))
        sec.append(1.0 if sh.get("section") else 0.0)
        pipes.append(1.0 if sh.get("pipes") else 0.0)
        sink.append(sh["sink"] if sh.get("sinking") else -1.0)
    ft = np.arange(n_frames) / tl.FPS
    ts = np.arange(n_samples) / SR
    return {k: np.interp(ts, ft, np.asarray(v)) for k, v in (("noz", noz), ("car", car), ("edge", edge), ("sec", sec), ("pipes", pipes), ("sink", sink))}


def level(d, near, far):
    """1 near, falling off to 0 far (log distance)."""
    return np.clip((np.log(far) - np.log(np.maximum(d, near))) / (np.log(far) - np.log(near)), 0.0, 1.0)


def creak(rng, dur=0.5):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 70 + 40 * rng.random() + 30 * np.sin(2 * np.pi * 3 * t)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * (0.6 + 0.4 * _band_noise(n, 5, 40, rng)) * _env(n, 0.05, 0.3)


def render_sfx(n_samples: int, narration: np.ndarray | None = None) -> tuple[np.ndarray, list]:
    rng = np.random.default_rng(3131)
    segs = tl.segments()
    t_film = np.arange(n_samples) / SR
    tr = frame_track(n_samples)
    bed = np.zeros(n_samples)
    hits = np.zeros(n_samples)
    events = []

    def ev(at, sound, seg):
        events.append({"film_s": round(at, 3), "sound": sound, "segment": seg})

    above = 1.0 - tr["sec"]
    spray = level(tr["noz"], 0.8, 40.0) * (1.0 - tr["pipes"])
    hiss = _band_noise(n_samples, 2500, 9000, rng) + 0.5 * _band_noise(n_samples, 900, 2500, rng)
    bed += db(-24) * (0.25 + 0.75 * spray) * spray * hiss
    patter = np.zeros(n_samples)
    k = int(0.012 * SR)
    drop = _band_noise(k, 1500, 7000, rng) * _env(k, 0.0005, 0.25)
    for at in np.sort(rng.uniform(0, t_film[-1], int(t_film[-1] * 70))):
        _place(patter, at, drop * rng.uniform(0.3, 1.0), 1.0)
    bed += db(-26) * spray * patter
    carl = level(tr["car"], 2.0, 60.0)
    swish = _band_noise(n_samples, 300, 3500, rng) * (0.8 + 0.2 * np.sin(2 * np.pi * 9 * t_film))
    engine = np.sin(2 * np.pi * np.cumsum(np.full(n_samples, 48.0)) / SR) + 0.5 * _band_noise(n_samples, 40, 160, rng)
    bed += db(-20) * carl ** 2 * swish + db(-30) * carl * engine
    gurgle = _band_noise(n_samples, 200, 1200, rng) * (0.5 + 0.5 * np.abs(np.sin(2 * np.pi * 2.3 * t_film + 2 * _band_noise(n_samples, 1, 4, rng))))
    bed += db(-30) * level(tr["edge"], 0.3, 4.0) * above * (1.0 - tr["pipes"]) * gurgle
    trickle = _band_noise(n_samples, 300, 900, rng) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.7 * t_film))
    bed += db(-34) * tr["pipes"] * trickle
    pump = np.sin(2 * np.pi * 100 * t_film) + 0.5 * np.sin(2 * np.pi * 200 * t_film) + 0.4 * _band_noise(n_samples, 60, 300, rng)
    rush = _band_noise(n_samples, 150, 1500, rng)
    bed += tr["sec"] * (db(-30) * pump + db(-27) * rush)
    sinking = (tr["sink"] >= 0).astype(float)
    groan = np.sin(2 * np.pi * np.cumsum(32.0 + 8.0 * np.sin(2 * np.pi * 0.4 * t_film)) / SR) * (0.6 + 0.4 * _band_noise(n_samples, 1, 8, rng))
    bed += db(-18) * sinking * groan
    for s in segs:
        if s["flags"].get("sink"):
            for j in range(4):
                at = s["t0"] + (j + 0.5) * (s["t1"] - s["t0"]) / 4
                _place(hits, at, creak(rng), db(-20))
                ev(at, "ground creaks", s["label"])
        if s["flags"].get("section"):
            ev(s["t0"], "pump hum and water rushing up the pipe", s["label"])
        if s["flags"].get("pipes"):
            ev(s["t0"], "water trickling in the pipes", s["label"])
    passing = np.nonzero((carl[1:] > 0.6) & (carl[:-1] <= 0.6))[0]
    for i in passing:
        ev(i / SR, "car swishes past through the water", next((s["label"] for s in segs if s["t0"] <= i / SR < s["t1"]), ""))
    hush = _band_noise(n_samples, 60, 500, rng) * (0.7 + 0.3 * np.sin(2 * np.pi * 0.05 * t_film) ** 2)
    wind = _band_noise(n_samples, 300, 1800, rng) * (0.4 + 0.6 * np.abs(np.sin(2 * np.pi * 0.11 * t_film)))
    bed += above * (db(-36) * hush + db(-40) * wind)
    for s in segs[1:]:
        _place(bed, s["t0"] - 0.21, whoosh(rng), db(-28))
        ev(s["t0"], "cut whoosh", s["label"])
    beat = 60.0 / 90.0
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
    print(json.dumps(build(root / "examples/episodes/ep31-audio/narration.wav", out, tl.total_seconds()), indent=1))
