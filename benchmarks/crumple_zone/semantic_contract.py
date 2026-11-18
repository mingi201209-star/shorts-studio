"""EP04 narration/visual semantic audit. No Blender, network, or rendering.

This is a *conservative* contract: a camera change or object presence does not
prove the spoken physical action is visible. Never turn UNKNOWN into PASS.
Run: python -m benchmarks.crumple_zone.semantic_contract
"""
from __future__ import annotations

from dataclasses import dataclass
from benchmarks.crumple_zone.crumple_motion import SEGMENTS

@dataclass(frozen=True)
class Claim:
    phrase: str
    required_visible_action: str
    scene_ids: tuple[str, ...]
    evidence: str
    status: str = "NOT_VERIFIED"

# Scene existence is grounded in crumple_motion.SEGMENTS. The evidence field
# documents *what must be observed*, not an assertion that it was observed.
CLAIMS = (
    Claim("a car hits a wall", "The front visibly starts to crush at impact", ("K",),
          "Continuous playback of the first seconds: a tracked run-up, contact inside the first 1.5 s, then a visibly advancing crush"),
    Claim("hood buckles", "The hood folds upwards", ("K",), "Close view of the nose while the crush advances: the hood line rises"),
    Claim("front folds back", "The whole front is pushed rearwards", ("K",), "The nose line moves back while the camera stays close to the front"),
    Claim("hidden rails inside fold", "The body turns see-through during the same crash and the rails fold", ("K",),
          "The scan line passes while the crush is still running (no rewind); the rails are seen shortening"),
    Claim("longer stop", "The crush keeps going slowly until the car stops", ("K",), "The stroke grows to its maximum and the car comes to rest in the same shot"),
    Claim("keeps its whole shape", "Protective cabin remains intact while the front is crushed", ("K",), "The whole car with the green cage after the crush"),
    Claim("pillars doors and roof", "Pillars, doors and roof stay where they were", ("K",), "A slow orbit shows the cabin from other sides"),
    Claim("rigid front rolls toward the same wall", "A second car with a rigid front hits the same wall at the same speed", ("R",), "Sequential full-screen shot, same camera start, same time scale"),
    Claim("bounces back", "The rigid car moves away from the barrier after impact", ("R",), "Continuous playback shows the car stop at the barrier and reverse away"),
    Claim("front is meant to deform", "The crushed front is shown", ("C",), "The first car at rest with its crushed front (no replay)"),
    Claim("cabin is not", "The cabin visibly keeps its shape", ("C",), "The see-through body shows the cage unchanged"),
)

def audit() -> list[dict[str, object]]:
    known = {s["id"] for s in SEGMENTS}
    out = []
    for claim in CLAIMS:
        missing = sorted(set(claim.scene_ids) - known)
        out.append({
            "narration": claim.phrase,
            "required_action": claim.required_visible_action,
            "scenes": list(claim.scene_ids),
            "missing_scenes": missing,
            "evidence_needed": claim.evidence,
            "status": "FAIL" if missing else claim.status,
        })
    return out

def main() -> None:
    import json
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
    # Deliberately not a release PASS gate: actual playback is necessary.

if __name__ == "__main__":
    main()
