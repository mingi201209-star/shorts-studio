"""Visual Production Engine V2 contracts.

This module moves production quality upstream: a strict project must classify
EVERY actual visual state, not just nominate a few good frames after the fact.
The contract verifies shot grammar and then re-checks timing against the real
post-TTS render timeline.

Important: PASS is not a claim that a human will find the Short entertaining.
The muted-10-second question remains a human judgment and is surfaced through
Project.silent_interest_review. This module only blocks structural production
failures that the engine can verify deterministically.
"""
from __future__ import annotations

from collections import Counter

_REQUIRED_ROLES = ("hero", "evidence", "mechanism", "second_peak", "payoff")
_PHYSICAL_MODES = {"real_footage", "real_photo", "physical_animation"}
_ABSTRACT_MODES = {"evidence_graphic", "mechanism_overlay", "explainer_card"}
_MAX_CONSECUTIVE_ABSTRACT = 2
_MAX_EXPLAINER_RUNTIME_RATIO = 0.10
_MIN_PILOT_PHYSICAL_RUNTIME_RATIO = 0.30
_TARGET_PHYSICAL_RUNTIME_RATIO = 0.70


def _states(project):
    result = []
    for scene_index, scene in enumerate(project.scenes):
        if scene.visual_beats:
            for beat_index, beat in enumerate(scene.visual_beats):
                result.append({
                    "scene_index": scene_index,
                    "scene_id": scene.id,
                    "beat_index": beat_index,
                    "relative_start": float(beat.start),
                    "asset": beat.asset or beat.asset_url,
                    "production": getattr(beat, "production", None),
                })
        else:
            result.append({
                "scene_index": scene_index,
                "scene_id": scene.id,
                "beat_index": None,
                "relative_start": 0.0,
                "asset": scene.asset or scene.asset_url,
                "production": getattr(scene, "production", None),
            })
    return result


def verify_visual_production_structure(project) -> dict:
    if not getattr(project, "strict_visual_production_v2", False):
        return {"status": "NOT_EVALUATED", "reason": "strict_visual_production_v2 disabled"}

    states = _states(project)
    reasons = []
    if not (getattr(project, "observable_phenomenon", None) or "").strip():
        reasons.append("observable_phenomenon is required")
    if not (getattr(project, "silent_story", None) or "").strip():
        reasons.append("silent_story is required")
    if getattr(project, "silent_interest_review", "pending") == "fail":
        reasons.append("human silent-interest review is FAIL")

    missing = [
        f"{s['scene_id']}[{s['beat_index']}]" for s in states
        if s["production"] is None
    ]
    if missing:
        reasons.append(f"{len(missing)} visual state(s) missing production classification: {missing[:8]}")

    classified = [s for s in states if s["production"] is not None]
    if classified:
        if classified[0]["production"].role != "hero":
            reasons.append("the first actual visual state must be role=hero")

        role_positions = {}
        counts = Counter()
        added = []
        for i, state in enumerate(classified):
            tag = state["production"]
            counts[tag.role] += 1
            role_positions.setdefault(tag.role, i)
            added.append(tag.added_information)

        for role in _REQUIRED_ROLES:
            if counts[role] == 0:
                reasons.append(f"missing required production role: {role}")
        for role in ("hero", "second_peak", "payoff"):
            if counts[role] > 1:
                reasons.append(f"role={role} must appear exactly once, found {counts[role]}")

        if all(r in role_positions for r in _REQUIRED_ROLES):
            ordered = [role_positions[r] for r in _REQUIRED_ROLES]
            if ordered != sorted(ordered):
                reasons.append("required role order must be hero -> evidence -> mechanism -> second_peak -> payoff")

        hero = next((s for s in classified if s["production"].role == "hero"), None)
        evidence = next((s for s in classified if s["production"].role == "evidence"), None)
        mechanism = next((s for s in classified if s["production"].role == "mechanism"), None)
        second = next((s for s in classified if s["production"].role == "second_peak"), None)
        payoff = next((s for s in classified if s["production"].role == "payoff"), None)

        if hero and hero["production"].visual_mode not in _PHYSICAL_MODES:
            reasons.append("hero must be real footage/photo or semantic physical animation")
        if evidence and evidence["production"].visual_mode == "explainer_card":
            reasons.append("evidence role cannot be a text/explainer card")
        if mechanism and mechanism["production"].visual_mode not in (
            _PHYSICAL_MODES | {"mechanism_overlay", "evidence_graphic", "explainer_card"}
        ):
            reasons.append("mechanism role uses an unsupported visual_mode")
        if second and second["production"].visual_mode not in _PHYSICAL_MODES:
            reasons.append("second_peak must be real footage/photo or semantic physical animation")
        if payoff and payoff["production"].visual_mode not in _PHYSICAL_MODES:
            reasons.append("payoff must resolve on real footage/photo or semantic physical animation")

        if not any(s["production"].visual_mode in {"real_footage", "real_photo"} for s in classified):
            reasons.append("strict V2 requires at least one real footage/photo evidence state")

        for a, b in zip(classified, classified[1:]):
            if a["production"].visual_mode == b["production"].visual_mode == "explainer_card":
                reasons.append(
                    f"consecutive explainer cards: {a['scene_id']}[{a['beat_index']}] -> "
                    f"{b['scene_id']}[{b['beat_index']}]"
                )

        abstract_run = 0
        for state in classified:
            if state["production"].visual_mode in _ABSTRACT_MODES:
                abstract_run += 1
                if abstract_run > _MAX_CONSECUTIVE_ABSTRACT:
                    reasons.append(
                        f"more than {_MAX_CONSECUTIVE_ABSTRACT} consecutive non-physical states near "
                        f"{state['scene_id']}[{state['beat_index']}]"
                    )
                    break
            else:
                abstract_run = 0

        if len(added) != len(set(added)):
            reasons.append("production added_information labels must be unique per visual state")

        if hero and second and hero["asset"] == second["asset"]:
            reasons.append("second_peak must not reuse the exact hero asset")

    evidence = {
        "visual_state_count": len(states),
        "classified_state_count": len(classified),
        "role_counts": dict(Counter(s["production"].role for s in classified)),
        "mode_counts": dict(Counter(s["production"].visual_mode for s in classified)),
        "silent_interest_review": getattr(project, "silent_interest_review", "pending"),
        "human_interest_verified": getattr(project, "silent_interest_review", "pending") == "pass",
    }
    return {
        "status": "FAIL" if reasons else "PASS",
        "reason": "; ".join(reasons) if reasons else None,
        "evidence": evidence,
    }


def verify_visual_production_timeline(project, scene_windows: list[dict], final_duration: float) -> dict:
    structural = verify_visual_production_structure(project)
    if structural["status"] != "PASS":
        return structural

    windows = {w["scene"]: w for w in scene_windows}
    timeline = []
    for state in _states(project):
        window = windows.get(state["scene_id"])
        if window is None:
            return {"status": "FAIL", "reason": f"missing real scene window for {state['scene_id']}"}
        timeline.append({
            **state,
            "start": float(window["start"]) + float(state["relative_start"]),
        })
    timeline.sort(key=lambda x: x["start"])

    reasons = []
    hero = next(s for s in timeline if s["production"].role == "hero")
    second = next(s for s in timeline if s["production"].role == "second_peak")
    payoff = next(s for s in timeline if s["production"].role == "payoff")

    if hero["start"] > 0.5:
        reasons.append(f"hero starts too late at {hero['start']:.2f}s (must begin immediately)")
    if not (10.0 <= second["start"] <= 25.0):
        reasons.append(f"second_peak starts at {second['start']:.2f}s, outside 10-25s")
    if final_duration > 0 and payoff["start"] < max(0.0, final_duration - 8.0):
        reasons.append(
            f"payoff starts at {payoff['start']:.2f}s, too early for a {final_duration:.2f}s video"
        )

    first_card = next(
        (s for s in timeline if s["production"].visual_mode == "explainer_card"), None
    )
    if first_card and first_card["start"] < 5.0:
        reasons.append(f"explainer card appears before 5s at {first_card['start']:.2f}s")

    mode_seconds = Counter()
    for i, state in enumerate(timeline):
        end = timeline[i + 1]["start"] if i + 1 < len(timeline) else final_duration
        duration = max(0.0, end - state["start"])
        mode_seconds[state["production"].visual_mode] += duration

    total = max(final_duration, 1e-9)
    explainer_ratio = mode_seconds["explainer_card"] / total
    physical_ratio = sum(mode_seconds[m] for m in _PHYSICAL_MODES) / total
    if explainer_ratio > _MAX_EXPLAINER_RUNTIME_RATIO:
        reasons.append(
            f"explainer-card runtime ratio {explainer_ratio:.3f} exceeds {_MAX_EXPLAINER_RUNTIME_RATIO:.2f}"
        )
    if physical_ratio < _MIN_PILOT_PHYSICAL_RUNTIME_RATIO:
        reasons.append(
            f"real/physical runtime ratio {physical_ratio:.3f} below pilot floor "
            f"{_MIN_PILOT_PHYSICAL_RUNTIME_RATIO:.2f}"
        )

    evidence = {
        **structural["evidence"],
        "hero_start": hero["start"],
        "second_peak_start": second["start"],
        "payoff_start": payoff["start"],
        "explainer_runtime_ratio": explainer_ratio,
        "physical_runtime_ratio": physical_ratio,
        "physical_runtime_target": _TARGET_PHYSICAL_RUNTIME_RATIO,
        "timeline": [
            {
                "scene": s["scene_id"],
                "beat": s["beat_index"],
                "start": round(s["start"], 3),
                "role": s["production"].role,
                "visual_mode": s["production"].visual_mode,
                "added_information": s["production"].added_information,
            }
            for s in timeline
        ],
    }
    return {
        "status": "FAIL" if reasons else "PASS",
        "reason": "; ".join(reasons) if reasons else None,
        "evidence": evidence,
    }
