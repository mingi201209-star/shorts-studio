"""Narration-versus-picture table of the EP.04 film: for every scene the spoken words with their measured time code, the film frame, which part/action the picture must show, and the
measured values of the render evidence at that moment (model or Blender). Markdown for the report; nothing in it is a pass/fail decision (the alignment checks decide)."""
from __future__ import annotations

import json
from pathlib import Path

from benchmarks.crumple_zone import crumple_motion as cm
from shorts_studio.scene_spec import load_spec, resolve_windows

ROOT = Path(__file__).resolve().parents[2]
KEYS = ("crumple.stroke_m", "body.max_rise_m", "rails.shortening_m", "xray.factor", "rigid.stroke_m", "rigid.rebound_m", "cell.max_displacement_mm", "film.speed_vs_real")


def table(evidence: dict[int, dict], cues: list[dict] | None = None, total_seconds: float | None = None) -> str:
    cues = cues or cm._cues()["cues"]
    total_seconds = total_seconds or cm._cues()["target_seconds"]
    spec = load_spec(ROOT / "examples/episodes/ep04-crumple-zone-scene-spec.json")
    windows = resolve_windows(spec, cues, total_seconds)
    rows = ["| scene | spoken | time (s) | frames | segment | picture must show | evidence at the cue / at the end of the words |", "|---|---|---|---|---|---|---|"]
    for s in spec.scenes:
        w = windows[s.id]
        f0, f1 = cm.frame_of(w["start"]), min(cm.TOTAL_FRAMES, int(round(w["end"] * cm.FPS)))
        at = lambda f: ", ".join(f"{k.split('.')[-1]}={evidence[f]['metrics'][k]:.3g}" for k in KEYS if f in evidence and k in evidence[f]["metrics"] and abs(evidence[f]["metrics"][k]) > 1e-9)
        rows.append(f"| {s.id} | {s.narration} | {w['start']:.2f}-{w['end']:.2f} | {f0}-{f1} | {cm.segment_at(f0)['id']} | {s.phenomenon.description} | start: {at(f0)} ; end: {at(f1)} |")
    return "\n".join(rows)


if __name__ == "__main__":
    from benchmarks.crumple_zone import evidence_sim as es
    print(table(es.timeline_evidence(es.Car(es.load_fixture()))))
