"""Production Quality V2 structural contract.

This module deliberately does NOT claim to prove that a Short is entertaining.
It enforces production-shape constraints that make the known "teaching slide"
failure mode harder to ship: evidence/motion in the opening, no long streak of
explanatory cards, a second strong visual in the middle, a visual payoff, and
minimal internal prose.

The final human question remains separate:
    "Would I keep watching this for at least 10 seconds with sound off?"
A machine PASS here is only a precondition for that human review.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

CARD_KINDS = {"explanatory_diagram", "text_card"}
PREMIUM_KINDS = {"real_motion", "real_still", "physical_animation"}
MOTION_KINDS = {"real_motion", "physical_animation"}
MOVING_SUFFIXES = {".mp4", ".webm", ".mov", ".mkv", ".ogv", ".avi"}

MIN_PREMIUM_VISUAL_RATIO = 0.65
MIN_REAL_VISUAL_RATIO = 0.20
MID_HERO_START = 10.0
MID_HERO_END = 25.0
MIN_MID_HERO_SECONDS = 1.5


def _suffix(value: str | None) -> str:
    if not value:
        return ""
    parsed = urlparse(value)
    return Path(parsed.path).suffix.lower()


def _is_moving_beat(beat) -> bool:
    return _suffix(getattr(beat, "asset", None) or getattr(beat, "asset_url", None)) in MOVING_SUFFIXES


def build_visual_timeline(project, scene_windows: list[dict]) -> list[dict]:
    """Return the resolved, whole-video visual beat timeline.

    render() mutates strict meaningful-change projects to their measured
    narration-cue starts before this is called, so these are the starts the
    viewer actually receives rather than authored guesses.
    """
    windows = {w["scene"]: w for w in scene_windows}
    timeline: list[dict] = []
    for scene in project.scenes:
        window = windows.get(scene.id)
        if not window:
            continue
        beats = list(getattr(scene, "visual_beats", None) or [])
        if not beats:
            # Strict V2 will fail metadata completeness below. Keeping the
            # fallback in the timeline makes the reason visible in reports.
            timeline.append({
                "scene": scene.id,
                "beat_index": 0,
                "start": float(window["start"]),
                "end": float(window["start"]) + float(window["duration"]),
                "duration": float(window["duration"]),
                "presentation_kind": None,
                "hero_visual": False,
                "internal_text": None,
                "moving": _suffix(getattr(scene, "asset", None) or getattr(scene, "asset_url", None)) in MOVING_SUFFIXES,
            })
            continue

        for index, beat in enumerate(beats):
            local_start = max(0.0, min(float(window["duration"]), float(beat.start)))
            local_end = (
                max(local_start, min(float(window["duration"]), float(beats[index + 1].start)))
                if index + 1 < len(beats)
                else float(window["duration"])
            )
            if local_end - local_start <= 0.01:
                continue
            timeline.append({
                "scene": scene.id,
                "beat_index": index,
                "start": float(window["start"]) + local_start,
                "end": float(window["start"]) + local_end,
                "duration": local_end - local_start,
                "presentation_kind": getattr(beat, "presentation_kind", None),
                "hero_visual": bool(getattr(beat, "hero_visual", False)),
                "internal_text": getattr(beat, "internal_text", None),
                "moving": _is_moving_beat(beat),
            })
    return timeline


def _max_card_streak(timeline: list[dict]) -> int:
    best = current = 0
    for beat in timeline:
        if beat["presentation_kind"] in CARD_KINDS:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def _overlap_seconds(beat: dict, start: float, end: float) -> float:
    return max(0.0, min(beat["end"], end) - max(beat["start"], start))


def verify_production_quality_v2(project, scene_windows: list[dict], final_duration: float) -> dict:
    timeline = build_visual_timeline(project, scene_windows)
    failures: list[str] = []

    if not timeline:
        return {"status": "FAIL", "reason": "no visual timeline", "failures": ["no visual timeline"], "timeline": []}

    missing_meta = [
        f'{b["scene"]}/{b["beat_index"]}'
        for b in timeline
        if b["presentation_kind"] is None or b["internal_text"] is None
    ]
    if missing_meta:
        failures.append("every visual beat must declare presentation_kind and internal_text: " + ", ".join(missing_meta))

    first = timeline[0]
    if first["presentation_kind"] not in MOTION_KINDS or not first["moving"]:
        failures.append("the opening beat must be real motion or physical animation, backed by an actual moving asset")

    opening = [b for b in timeline if b["start"] < 5.0]
    opening_cards = [f'{b["scene"]}/{b["beat_index"]}' for b in opening if b["presentation_kind"] in CARD_KINDS]
    if opening_cards:
        failures.append("the first 5 seconds must show the phenomenon, not explanatory cards: " + ", ".join(opening_cards))

    card_streak = _max_card_streak(timeline)
    if card_streak > 1:
        failures.append(f"two or more explanatory-card beats appear consecutively (max streak={card_streak})")

    sentence_text = [
        f'{b["scene"]}/{b["beat_index"]}'
        for b in timeline
        if b["internal_text"] == "sentence"
    ]
    if sentence_text:
        failures.append("internal prose is not allowed in strict V2 visuals; use no text or short labels only: " + ", ".join(sentence_text))

    mid_heroes = [
        b for b in timeline
        if b["hero_visual"]
        and b["presentation_kind"] in MOTION_KINDS
        and b["moving"]
        and _overlap_seconds(b, MID_HERO_START, MID_HERO_END) >= MIN_MID_HERO_SECONDS
    ]
    if not mid_heroes:
        failures.append(
            f"a second moving hero visual lasting >= {MIN_MID_HERO_SECONDS:.1f}s is required in the {MID_HERO_START:.0f}-{MID_HERO_END:.0f}s window"
        )

    last = timeline[-1]
    if last["presentation_kind"] not in MOTION_KINDS or not last["moving"]:
        failures.append("the final visual must resolve on real motion or physical animation, not a static explanation card")

    duration = max(0.001, float(final_duration))
    premium_seconds = sum(b["duration"] for b in timeline if b["presentation_kind"] in PREMIUM_KINDS)
    real_seconds = sum(b["duration"] for b in timeline if b["presentation_kind"] in {"real_motion", "real_still"})
    premium_ratio = premium_seconds / duration
    real_ratio = real_seconds / duration
    if premium_ratio < MIN_PREMIUM_VISUAL_RATIO:
        failures.append(
            f"premium visual share {premium_ratio:.3f} < {MIN_PREMIUM_VISUAL_RATIO:.2f}; diagrams are still carrying too much of the video"
        )
    if real_ratio < MIN_REAL_VISUAL_RATIO:
        failures.append(
            f"real visual share {real_ratio:.3f} < {MIN_REAL_VISUAL_RATIO:.2f}; strict V2 requires real-world evidence to remain a visible part of the production"
        )

    first_10 = [b for b in timeline if b["start"] < 10.0]
    first_10_changes = max(0, len(first_10) - 1)
    silent_watch_proxy = (
        not opening_cards
        and first["presentation_kind"] in MOTION_KINDS
        and first["moving"]
        and first_10_changes >= 3
        and card_streak <= 1
    )

    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "metrics": {
            "premium_visual_ratio": premium_ratio,
            "real_visual_ratio": real_ratio,
            "max_consecutive_explanatory_cards": card_streak,
            "first_10s_visual_changes_from_declared_beats": first_10_changes,
            "mid_hero_count": len(mid_heroes),
            "silent_watch_proxy": "PASS" if silent_watch_proxy else "FAIL",
        },
        "human_silent_review": {
            "status": "REQUIRED",
            "question": "소리 없이 봐도 10초 이상 계속 보고 싶은가?",
            "note": "machine PASS is not permission to mark the render upload-ready without this human review",
        },
        "timeline": timeline,
    }
