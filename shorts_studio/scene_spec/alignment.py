"""Narration-Visual Alignment: decides, from real TTS cue timing and the telemetry the renderer actually wrote for every frame, whether what is spoken is what is on screen.

Six criteria per scene (owner's directive): (1) the named subjects are on screen, (2) they perform the described action, (3) at the right time, (4) understandable with the sound
off, (5) physically consistent, (6) not hidden by captions / camera / effects. Nothing is PASS because an object merely exists: criterion 2 needs a metric that moved. What
software cannot judge stays NOT_VERIFIED and needs a person to watch the continuous video. Pure functions, no Blender."""
from __future__ import annotations

from .spec import CRITERIA, Check, EpisodeSpec, Scene

FPS = 30


def resolve_windows(spec: EpisodeSpec, cues: list[dict], total_seconds: float) -> dict[str, dict]:
    """Scene id -> {"start": s, "end": s} from the measured caption cues. Scenes are ordered by beat then by the position of their cue words in the cue list."""
    texts = [c["text"].replace("\\N", " ") for c in cues]
    starts, cursor = {}, 0
    for s in spec.scenes:
        for i in range(cursor, len(texts)):
            if texts[i].startswith(s.cue):
                starts[s.id] = float(cues[i]["start"])
                cursor = i + 1
                break
        else:
            raise ValueError(f"scene {s.id}: no spoken cue starting with {s.cue!r} after the previous scene")
    ordered = list(spec.scenes)
    out = {}
    for k, s in enumerate(ordered):
        end = starts[ordered[k + 1].id] if k + 1 < len(ordered) else total_seconds
        out[s.id] = {"start": starts[s.id], "end": end}
    return out


def _frames(window: dict, last_frame: int) -> range:
    a = max(1, int(round(window["start"] * FPS)) + 1)
    b = min(last_frame, int(round(window["end"] * FPS)))
    return range(a, b + 1)


def _clip_window(check: Check, window: dict) -> dict:
    if check.window == "scene":
        return window
    n = float(check.window.split("_")[1].rstrip("s"))
    return {"start": window["start"], "end": window["start"] + n}      # an effect keeps going after the clause that names it was spoken


def _series(evidence: dict[int, dict], frames: range, metric: str) -> list[tuple[int, float]]:
    return [(f, float(evidence[f]["metrics"][metric])) for f in frames if f in evidence and metric in evidence[f]["metrics"]]


def onset_frame(evidence: dict[int, dict], metric: str, threshold: float, frames: range) -> int | None:
    for f, v in _series(evidence, frames, metric):
        if v > threshold:
            return f
    return None


def evaluate_check(check: Check, scene: Scene, window: dict, evidence: dict[int, dict], cue_start: float, last_frame: int) -> dict:
    row = {"check": check.id, "criterion": check.criterion, "description": check.description}
    if check.kind == "manual":
        return {**row, "status": "NOT_VERIFIED", "reason": "needs a person watching the continuous video"}
    w = _clip_window(check, window)
    onset_kind = check.kind in ("onset_near_cue", "onset_within_s")
    # an onset check only needs the evidence up to the cue (plus tolerance), not the whole window of the scene
    need_until = (cue_start + (check.value if check.kind == "onset_near_cue" else 0.0)) if onset_kind else w["end"]
    if int(round(need_until * FPS)) > last_frame:
        return {**row, "status": "NOT_EVALUATED_YET", "reason": f"window ends at {w['end']:.2f}s but the evidence covers only {last_frame / FPS:.2f}s"}
    frames = _frames(w, last_frame)
    if not frames:
        return {**row, "status": "FAIL", "reason": "empty window"}
    k = check.kind
    if k == "metric_increase":
        s = _series(evidence, frames, check.metric)
        if not s:
            return {**row, "status": "FAIL", "reason": f"no telemetry for {check.metric}"}
        delta = s[-1][1] - s[0][1]
        return {**row, "status": "PASS" if delta >= check.value else "FAIL", "measured": round(delta, 4), "required": check.value}
    if k == "metric_reaches":
        s = _series(evidence, frames, check.metric)
        if not s:
            return {**row, "status": "FAIL", "reason": f"no telemetry for {check.metric}"}
        best = max(v for _, v in s)
        return {**row, "status": "PASS" if best >= check.value else "FAIL", "measured": round(best, 4), "required": check.value}
    if k in ("metric_at_most", "metric_at_least"):
        s = _series(evidence, frames, check.metric)
        if not s:
            return {**row, "status": "FAIL", "reason": f"no telemetry for {check.metric}"}
        worst = max(v for _, v in s) if k == "metric_at_most" else min(v for _, v in s)
        ok = worst <= check.value if k == "metric_at_most" else worst >= check.value
        return {**row, "status": "PASS" if ok else "FAIL", "measured": round(worst, 4), "required": check.value, "rule": k}
    if k in ("onset_near_cue", "onset_within_s"):
        f = onset_frame(evidence, check.metric or scene.phenomenon.onset_metric, check.onset_threshold or scene.phenomenon.onset_threshold,
                        range(1, last_frame + 1))
        if f is None:
            return {**row, "status": "FAIL", "reason": "the phenomenon never starts in the evidence"}
        t = (f - 1) / FPS
        if k == "onset_near_cue":
            # a replayed crash starts the metric again: take the rising edge that is closest to the spoken cue
            thr = check.onset_threshold or scene.phenomenon.onset_threshold
            series = _series(evidence, range(1, last_frame + 1), check.metric or scene.phenomenon.onset_metric)
            edges = [fr for i, (fr, v) in enumerate(series) if v > thr and (i == 0 or series[i - 1][1] <= thr)]
            t = (min(edges, key=lambda fr: abs((fr - 1) / FPS - cue_start)) - 1) / FPS if edges else t
            delta = t - cue_start
            return {**row, "status": "PASS" if abs(delta) <= check.value else "FAIL", "onset_s": round(t, 3), "cue_s": round(cue_start, 3), "delta_s": round(delta, 3),
                    "tolerance_s": check.value}
        return {**row, "status": "PASS" if t <= check.value else "FAIL", "onset_s": round(t, 3), "limit_s": check.value}
    if k == "subjects_in_view":
        need = check.subjects or scene.subjects
        share = {}
        for name in need:
            vals = [bool(evidence[f]["in_view"].get(name, False)) for f in frames if f in evidence]
            share[name] = sum(vals) / len(vals) if vals else 0.0
        ok = all(v >= (check.value or 0.8) for v in share.values())
        return {**row, "status": "PASS" if ok else "FAIL", "in_view_share": {n: round(v, 2) for n, v in share.items()}, "required_share": check.value or 0.8}
    if k == "ordered_onsets":
        a = onset_frame(evidence, check.first, check.onset_threshold, range(1, last_frame + 1))
        b = onset_frame(evidence, check.second, check.onset_threshold, range(1, last_frame + 1))
        ok = a is not None and b is not None and a <= b
        return {**row, "status": "PASS" if ok else "FAIL", "first_onset_frame": a, "second_onset_frame": b, "order": f"{check.first} before {check.second}"}
    if k == "not_obscured":
        s = _series(evidence, frames, check.metric)
        if not s:
            return {**row, "status": "FAIL", "reason": f"no telemetry for {check.metric}"}
        worst = max(v for _, v in s)
        return {**row, "status": "PASS" if worst <= check.value else "FAIL", "measured": round(worst, 3), "required": check.value}
    return {**row, "status": "FAIL", "reason": f"unknown check kind {k}"}


def evaluate_episode(spec: EpisodeSpec, cues: list[dict], total_seconds: float, evidence: dict[int, dict], clip_seconds: float | None = None) -> dict:
    """evidence: film frame (1-based) -> {"metrics": {name: value}, "in_view": {subject: bool}}. clip_seconds: how much of the film the evidence covers (a preview)."""
    last = max(evidence) if evidence else 0
    windows = resolve_windows(spec, cues, total_seconds)
    scenes = {}
    for s in spec.scenes:
        w = windows[s.id]
        results = [evaluate_check(c, s, w, evidence, w["start"], last) for c in s.success]
        by_crit = {}
        for crit in CRITERIA:
            rs = [r for r in results if r["criterion"] == crit]
            if not rs:
                by_crit[crit] = "NOT_DEFINED"
            elif any(r["status"] == "FAIL" for r in rs):
                by_crit[crit] = "FAIL"
            elif any(r["status"] == "NOT_EVALUATED_YET" for r in rs):
                by_crit[crit] = "NOT_EVALUATED_YET"
            elif any(r["status"] == "NOT_VERIFIED" for r in rs):
                by_crit[crit] = "NOT_VERIFIED"
            else:
                by_crit[crit] = "PASS"
        if s.silent_readable and by_crit["sound_off_understandable"] in ("NOT_DEFINED",):
            by_crit["sound_off_understandable"] = "NOT_VERIFIED"
        auto = [r for r in results if r["status"] != "NOT_VERIFIED"]
        if any(r["status"] == "FAIL" for r in results):
            verdict = "FAIL"
        elif any(r["status"] == "NOT_EVALUATED_YET" for r in results):
            verdict = "PENDING_MORE_FRAMES"
        elif any(r["status"] == "NOT_VERIFIED" for r in results) or by_crit["sound_off_understandable"] == "NOT_VERIFIED":
            verdict = "AUTO_PASS_HUMAN_REVIEW_PENDING"
        else:
            verdict = "PASS"
        scenes[s.id] = {"window": {k: round(v, 3) for k, v in w.items()}, "verdict": verdict, "criteria": by_crit, "checks": results,
                        "automatic_checks": len(auto)}
    overall = ("FAIL" if any(v["verdict"] == "FAIL" for v in scenes.values())
               else "PENDING_MORE_FRAMES" if any(v["verdict"] == "PENDING_MORE_FRAMES" for v in scenes.values())
               else "AUTO_PASS_HUMAN_REVIEW_PENDING")
    return {"episode": spec.episode, "evidence_frames": last, "covered_seconds": round(last / FPS, 2), "overall": overall, "scenes": scenes,
            "note": "PASS is never given for what only a person can judge (sound-off comprehension, naturalness): those stay NOT_VERIFIED until the continuous video was watched"}
