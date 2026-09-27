# Meaningful visual changes — Issue 29

Baseline: `d425b5b36f2354f524f00cdfa25372473b7378e6`.
Design audit posted before implementation in Issue 29, comment 5853684225.

The old contract combines authored gaps <=3.5s with actual media-box pixel
difference >=12 at 2fps and static holds <=5s. Crop/zoom changes can satisfy
both without adding information. Filename families do not recognize all
wide/close_a/close_b variants. An info_role string cannot fix that.

This opt-in contract is additive: no old check or threshold is removed,
relaxed, or conditionally skipped. A beat declares concept/state/framing,
concept and state identity, a literal narration cue, added information, and
an exact source SHA-256. Declarations are audited before synthesis; real TTS
word boundaries resolve the visual timestamps. Frame timing is never inferred
from a constant cut interval. Older manifests retain their original path.

Post-render evidence comes from the actual final MP4 media box: pinned-source
comparison, identical-content rejection, affine crop/zoom equivalence and
replay detection, short-state diagnostics, and an observed first-5s change.
SIFT registration is negative evidence, not a semantic judge. Repetitive or
feature-poor images can evade a geometric classifier; new IDs, labels, and
hashes are never proof of semantic novelty. A PASS only means delivery and
negative checks passed. The report requires manual review against narration,
independent of the existing CLIP semantic QA, which remains required in the
pilot workflow. No claim of automated understanding or entertainment success.

Train Wheels keeps all 14 scenes, narration, factual guardrails and PEC graph.
Purpose-built staged schematics replace crop loops: the established view
stays fixed while new explanatory geometry is revealed. The drawings are
schematic, with exaggerated geometry and no invented numeric measurements.
No duration cap; no YouTube upload.

Review the actual MP4 and every state, especially the opening, rolling-radius
explanation and flange-contact condition. Reject duplicate information even
when the geometry detector misses it. Preserve the last green main until the
candidate has passed regression, all CI and actual visual review.
