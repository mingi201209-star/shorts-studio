"""Production gate: no full render before every scene is specified, implementable and has passed its low-cost preview checks.

The registry (JSON, committed next to the spec) records the best preview verdict per scene. `full_render_allowed` is the single question the full-render workflow asks; it never
relaxes a check: a FAIL, a missing capability, a scene without preview evidence or an invalid spec all answer "no" with the reasons."""
from __future__ import annotations

import json
from pathlib import Path

from .spec import EpisodeSpec, production_blockers, validate

READY_VERDICTS = ("PASS", "AUTO_PASS_HUMAN_REVIEW_PENDING")


def update_registry(path: str | Path, episode: str, preview_id: str, report: dict) -> dict:
    p = Path(path)
    reg = json.loads(p.read_text(encoding="utf8")) if p.exists() else {"episode": episode, "scenes": {}, "previews": []}
    reg["previews"].append({"preview": preview_id, "overall": report["overall"], "covered_seconds": report["covered_seconds"]})
    for sid, r in report["scenes"].items():
        cur = reg["scenes"].get(sid)
        # a newer evaluation replaces an older one only when it is at least as informative (a verdict from real frames beats PENDING)
        if cur is None or r["verdict"] != "PENDING_MORE_FRAMES" or cur.get("verdict") == "PENDING_MORE_FRAMES":
            reg["scenes"][sid] = {"verdict": r["verdict"], "preview": preview_id, "criteria": r["criteria"]}
    p.write_text(json.dumps(reg, indent=2), encoding="utf8")
    return reg


def full_render_allowed(spec: EpisodeSpec, registry: dict, capabilities: dict[str, bool], speech_plan_beats: list[str]) -> tuple[bool, list[str]]:
    reasons = [f"spec: {m}" for m in validate(spec, speech_plan_beats)]
    reasons += production_blockers(spec, capabilities)
    for s in spec.scenes:
        r = registry.get("scenes", {}).get(s.id)
        if r is None:
            reasons.append(f"scene {s.id}: no low-cost preview evidence")
        elif r["verdict"] not in READY_VERDICTS:
            reasons.append(f"scene {s.id}: preview verdict {r['verdict']}")
    return (not reasons, reasons)
