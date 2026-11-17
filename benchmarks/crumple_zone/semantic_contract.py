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
    Claim("designed to crush", "Front visibly collapses at impact", ("H", "C"),
          "Continuous 0-2 s playback: visibly advancing crush, not only a car touching a wall"),
    Claim("hidden structures fold", "Visible internal rails buckle progressively", ("X", "X2"),
          "Consecutive X-ray frames show rail deformation large enough to see on a phone"),
    Claim("longer distance and time", "Comparison visibly communicates longer deceleration", ("C2", "C3"),
          "Matched playback of two cars with distinct stop distances; labels alone are insufficient"),
    Claim("less average force", "Average force comparison is actually conveyed", ("X2", "C3"),
          "Inspect whether a viewer can distinguish *average force* from crush depth; don't infer it from labels"),
    Claim("rigid front stops", "Rigid and crumple cars visibly stop differently", ("C3",),
          "Matched rigid/crumple stop positions and timing in consecutive frames"),
    Claim("passenger compartment", "Protective cabin remains intact as front crushes", ("X3", "X5"),
          "Show deforming nose and intact cabin in the same continuous shot"),
    Claim("seat belts and airbags", "Restraint systems shown or narration revised accurately", ("X4",),
          "Current scene code lists only X-ray replay; do not claim belts or airbags are visualized"),
    Claim("front is meant to deform", "Front visibly deforms", ("H2",),
          "Visible front collapse during narrated line"),
    Claim("cabin isn't", "Cabin visibly retains its shape", ("X5",),
          "Continuous view makes contrast with deformed nose understandable"),
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
