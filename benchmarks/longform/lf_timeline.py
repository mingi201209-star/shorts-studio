"""Long-form films built from the channel's 3D episodes (pure Python): every shot is a shot of an existing episode (its world, its
model, its flags) re-framed for 16:9 and re-timed to the long-form narration. The layout places each shot on the long film's timeline
(cut on the narration line, or on a word inside it, where the picture must change: show exactly what each line says); for rendering,
each episode gets a virtual timeline holding only its own shots back to back, built from a fresh copy of the episode's own timeline
module (its segments() and frame_state() are reused unchanged), so the episode's renderer and sound module run on it as they are."""
from __future__ import annotations

import importlib.util
import inspect
import json
from pathlib import Path

FPS = 24
FRAME = (1920, 1080)
ROOT = Path(__file__).resolve().parents[2]

# key: (timeline module, renderer module, sound module, frame log tag, frames json prefix, physics module, physics function)
EPISODES = {
    "terminal": ("benchmarks.guardrail_end.terminal_timeline", "benchmarks.guardrail_end.render_terminal_3d", "benchmarks.guardrail_end.terminal_sfx",
                 "TERMINAL_FRAME", "terminal-frames-", "benchmarks.guardrail_end.terminal_motion", "terminal_physics"),
    "cable": ("benchmarks.cable_barrier.cable_timeline", "benchmarks.cable_barrier.render_cable_3d", "benchmarks.cable_barrier.cable_sfx",
              "CABLE_FRAME", "cable-frames-", "benchmarks.cable_barrier.cable_motion", "cable_physics"),
    "roller": ("benchmarks.roller_barrier.roller_timeline", "benchmarks.roller_barrier.render_roller_3d", "benchmarks.roller_barrier.roller_sfx",
               "ROLLER_FRAME", "roller-frames-", "benchmarks.roller_barrier.roller_motion", "roller_physics"),
    "spike": ("benchmarks.spike_strip.spike_timeline", "benchmarks.spike_strip.render_spike_3d", "benchmarks.spike_strip.spike_sfx",
              "SPIKE_FRAME", "spike-frames-", "benchmarks.spike_strip.spike_motion", "spike_physics"),
    "wedge": ("benchmarks.wedge_barrier.wedge_timeline", "benchmarks.wedge_barrier.render_wedge_3d", "benchmarks.wedge_barrier.wedge_sfx",
              "WEDGE_FRAME", "wedge-frames-", "benchmarks.wedge_barrier.wedge_motion", "wedge_physics"),
    "rocknet": ("benchmarks.rock_net.rocknet_timeline", "benchmarks.rock_net.render_rocknet_3d", "benchmarks.rock_net.rocknet_sfx",
                "ROCKNET_FRAME", "rocknet-frames-", "benchmarks.rock_net.rocknet_motion", "rocknet_physics"),
    "emas": ("benchmarks.runway_emas.emas_timeline", "benchmarks.runway_emas.render_emas_3d", "benchmarks.runway_emas.emas_sfx",
             "EMAS_FRAME", "emas-frames-", "benchmarks.runway_emas.emas_motion", "emas_physics"),
}


def fresh_module(name: str):
    """A new copy of a module (its own globals), so overriding them does not touch the episode's own film."""
    spec = importlib.util.find_spec(name)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _row_layout(row) -> tuple[int, int]:
    """(index of cam_a, index of flags): EP.13's rows carry a story start and end instead of knots."""
    return (5, 7) if len(row) == 9 else (4, 6)


def landscape(cam: dict, scale: float) -> dict:
    """A portrait camera re-framed for 16:9: same place and aim, a wider lens (the frame loses height, so it keeps some width)."""
    c = dict(cam)
    c["lens"] = round(cam["lens"] * scale, 3)
    return c


def episode_timeline(key: str, shots: list[dict]):
    """The episode's timeline module with its rows replaced by `shots` (each: row label, frames, optional lens_scale / cam overrides /
    story knots), laid back to back from virtual time 0. Where the episode times its story knots in seconds from the shot's start,
    they are stretched to the new shot's length, so each shot still shows its whole action (the rise, the hit, the stop) whatever the
    long film's line length."""
    mod = fresh_module(EPISODES[key][0])
    base = {r[0]: r for r in mod.ROWS}
    own = {sg["label"]: sg["t1"] - sg["t0"] for sg in mod.segments()}
    seconds_knots = "u * span" not in inspect.getsource(mod.segments)
    rows, starts, t = [], [], 0.0
    for i, sh in enumerate(shots, 1):
        r = list(base[sh["row"]])
        ci, fi = _row_layout(r)
        r[2] = i
        sc = sh.get("lens_scale", 0.85)
        r[ci] = sh.get("cam_a") or landscape(r[ci], sc)
        r[ci + 1] = sh.get("cam_b") or landscape(r[ci + 1], sc)
        flags = dict(r[fi])
        flags.pop("loop", None)
        r[fi] = flags
        if "knots" in sh and len(r) == 8:
            r[3] = [tuple(k) for k in sh["knots"]]
        elif len(r) == 8 and seconds_knots:
            k = sh["frames"] / FPS / own[sh["row"]]
            r[3] = [(round(a * k, 6), v) for a, v in r[3]]
        rows.append(tuple(r))
        starts.append(t)
        t += sh["frames"] / FPS
    total = t
    n = sum(sh["frames"] for sh in shots)
    mod.ROWS = rows
    mod.line_starts = lambda: list(starts)
    mod.total_seconds = lambda: total
    mod.frame_count = lambda: n
    mod.LF_SHOTS = shots
    return mod


def resolve_cut(spec, beat: dict, cues: list[dict]) -> float:
    """Where inside a line a shot starts, as seconds from the line's start: a fraction of the line, or ("word", w) for the start of the
    caption cue that opens with the word w (cue times come from the narration's own word timings), else the word's share of the line."""
    span = beat["end"] - beat["start"]
    if isinstance(spec, (int, float)):
        return float(spec) * span
    word, nth = spec[1], (spec[2] if len(spec) > 2 else 1)
    seen = 0
    for c in cues:
        if beat["start"] - 1e-6 <= c["start"] < beat["end"] and c["text"].split()[0].strip(".,!?").lower() == word.lower():
            seen += 1
            if seen == nth:
                return c["start"] - beat["start"]
    words = [w.strip(".,!?").lower() for w in beat["narration_en"].split()]
    idx = [i for i, x in enumerate(words) if x == word.lower()]
    if len(idx) >= nth:
        return span * idx[nth - 1] / len(words)
    raise ValueError(f"word {word!r} (#{nth}) not in line {beat['narration_en']!r}")


def build_layout(blocks: list[dict], audio_root: Path, tail_s: float = 0.6) -> dict:
    """blocks: [{"id": narration variant, "lines": [[(episode, row, cut), ...] per narration line]}]. Returns the long film's layout:
    the narration blocks with their offsets, every shot with its final frames, and each episode's shots (virtual timeline order)."""
    t, blocks_out, shots = 0.0, [], []
    for b in blocks:
        a = json.loads((audio_root / b["id"] / "audio-validation.json").read_text())
        beats = a["beats"]
        if len(beats) != len(b["lines"]):
            raise ValueError(f"{b['id']}: {len(beats)} narration lines, {len(b['lines'])} shot lists")
        dur = a["seconds"] + tail_s
        blocks_out.append({"id": b["id"], "t0": round(t, 4), "seconds": round(dur, 4), "speech_seconds": a["seconds"]})
        line_t = [t + bt["start"] for bt in beats] + [t + dur]
        for i, (bt, plan) in enumerate(zip(beats, b["lines"])):
            l0 = t if i == 0 else line_t[i]
            l1 = line_t[i + 1]
            cuts = [l0] + [line_t[i] + resolve_cut(c, bt, a.get("cues", [])) for (_, _, c) in plan[1:]]
            for j, (ep, row, _) in enumerate(plan):
                s0, s1 = cuts[j], (cuts[j + 1] if j + 1 < len(plan) else l1)
                if s1 - s0 < 0.25:
                    raise ValueError(f"{b['id']} line {i + 1}: shot {row} would last {s1 - s0:.2f} s")
                shots.append({"episode": ep, "row": row, "block": b["id"], "line": i + 1, "text": bt["narration_en"], "t0": s0, "t1": s1})
        t += dur
    total_frames = int(round(t * FPS))
    for k, sh in enumerate(shots):
        sh["f0"] = int(round(sh["t0"] * FPS))
        sh["f1"] = int(round(shots[k + 1]["t0"] * FPS)) if k + 1 < len(shots) else total_frames
        sh["frames"] = sh["f1"] - sh["f0"]
    per_ep: dict[str, list] = {}
    for sh in shots:
        lst = per_ep.setdefault(sh["episode"], [])
        sh["v0"] = sum(x["frames"] for x in lst)
        sh["index_in_episode"] = len(lst)
        lst.append(sh)
    return {"fps": FPS, "frame": FRAME, "seconds": round(t, 4), "frames": total_frames, "blocks": blocks_out, "shots": shots,
            "episodes": {k: [{"row": s["row"], "frames": s["frames"]} for s in v] for k, v in per_ep.items()}}


def layout_episode_timeline(layout: dict, key: str, overrides: dict | None = None):
    """The episode's virtual timeline from a layout (with per-row camera / lens overrides from the film's config)."""
    shots = []
    for s in layout["episodes"][key]:
        sh = dict(s)
        sh.update((overrides or {}).get((key, s["row"]), {}))
        shots.append(sh)
    return episode_timeline(key, shots)
