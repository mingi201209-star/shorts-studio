# Curious Mechanics EP.04 — Why Cars Are Designed to Crush
Status: production storyboard / pre-render plan; no render or upload authorized
Baseline: main fcd20fd78851b18c550b1e433bee46ee34313c1d (check again before code edits). Prior episode: speed bump 1000020417.mp4.

## Core promise
Show how a front crumple zone deforms in a frontal collision and why increasing the stopping distance/time can reduce average deceleration and average force for the same change in momentum. Do not imply the occupant compartment should collapse; it must remain protective.

## English title candidates
- This Car Is Designed to Crush.
- Why Cars Are Built to Crumple in a Crash

## 30-second production storyboard
0.0–0.6: Immediate close 3/4 exterior shot of a generic car nose beginning a controlled frontal crash against a rigid barrier; no static title, no gratuitous gore.
0.6–2.0: Side-by-side synchronized comparison: simplified rigid front vs engineered crumple zone, equal initial speed and mass. Clearly label RIGID / CRUMPLE, but do not claim actual rigid-car safety performance.
2.0–4.5: X-ray reveal exposes front crush members, passenger safety cell, and a clearly separated restrained occupant schematic; make mechanism large enough on a phone.
4.5–10: Show progressive collapse of front crush structures, retaining passenger cell; physical deformation, not just mesh transparency.
10–16: Visualize stopping distance and time on synchronized timelines; illustrative comparative values only if validated by computation and identified as hypothetical.
16–22: Explain average force via momentum change over stopping time; no absolute claims about real crash injuries or peak forces.
22–27: Return to exterior; replay collision with overlay tracing deformation vs protected passenger cell. Mention seat belts and airbags are complementary restraints, not substitutes.
27–30: Clear takeaway, no new unsupported claims, channel identity.

## Narration draft (must time against audio before production)
"Cars are designed to crush. Watch the front end collapse in a crash. That damage is doing a job. Hidden structures fold, increasing the distance and time over which the car slows down. For the same change in momentum, more stopping time can mean less average force. The passenger compartment is built to stay protective, while seat belts and airbags help protect the people inside. The front is meant to deform. The cabin isn't."

## Visual and physics requirements
- Keep equal initial speed, mass, barrier, and camera for comparisons. Do not present the rigid counterfactual as a measured crash test.
- Crumple deformation should visibly progress from nose rearward while avoiding arbitrary collapse of the safety cell.
- Wheel-ground contact and consistent perspective; no clipping/teleportation.
- Avoid inaccurate claims that crumple zones eliminate injury or always reduce peak force.
- If physical simulation is simplified, disclose in description; do not claim vehicle-specific crash ratings.
- Narration-to-visual correspondence, mobile subtitle safe area, no black opening, meaningful first 2s changes.
- X-ray/cutaway must show real geometry and motion; preserve external silhouette.

## Before expensive full render
1. Check main, active PRs, CI and current rendering interfaces; no main edits.
2. Produce low-cost 0–4.5s contiguous animatic, then 4.5–16s deformation proof and 22–30s end; validate by actual playback, not contact sheet only.
3. Review technical accuracy, typography, first 2s, sound, and motion with explicit evidence. No QA threshold weakening.
4. Only after gates pass, launch full GitHub Actions free-runner render if explicitly authorized. VPS never used for rendering.
5. Keep thumbnail/cover-frame candidates in production plan; never auto-upload. User approval required for publishing.
6. Compare to speed bump video on production quality; post-publication evaluate viewed-vs-swiped, retention, subscribers/1000 views at equivalent windows.

## Project departments
Planning: narrative and claims; Rendering: crumple-zone deformation and X-ray geometry; Editing: cuts/captions/audio; Evaluation: safety/physics and viewer comprehensibility; Management: costs, CI, regression and upload authorization.

## Explicit current limitations
This document is a production-ready brief, not implemented Blender geometry, generated video, or validated CI result. No paid resources, upload, or merge performed.
