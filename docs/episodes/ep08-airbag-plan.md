# EP.08: airbag (why airbags have holes)

- Opening: labelled split (AIRBAG ON / AIRBAG OFF, SAME CRASH · 64 km/h · SAME BELT), see-through car already 25 ms into the EP.04 crash;
  the top bag is visibly opening in the first second; the bare head hits the wheel at 1.46 s of film time.
- Model (benchmarks/airbag/airbag_motion.py, gate `airbag_physics`): head on a springy neck over EP.05's belted torso; without an airbag
  the head hits the hub (peak about 440 g in this model), with one the bag is full 40 ms after contact and vents (peak about 43 g).
- Parts (airbag_parts.py): hub cover with a tear seam and two flaps, folded pleats, inflator with gas ports, igniter with wires, venting
  cushion with two vent holes, airbag control unit with accelerometer and proof mass.
- Run 44631108709: every gate PASS (airbag_physics, scene_alignment, telemetry_matches_model, visible_action, no_scene_text, loop_closes,
  smoothness, black_opening, captions_visible). 935 frames, 39.0 s.
- Weak spot: the crash-sensor shots (lines 4-5, about 7 s) are a small grey box seen through the glass floor; the least lively part.
- NOT verified: voice pronunciation, sound-off readability, human first view. The owner uploads.

## v3 (2026-11-20): stylised driver
Owner: "make the person better" then "not realistic, easy to look at". benchmarks/airbag/human.py (Human, a drop-in for rb.Dummy with the
same rig): big round head, glossy oval eyes with a highlight, small nose and mouth, hair cap, simple ears, capsule limbs, mitten hands with
a thumb on the rim, matte colours. Run 44687752272: every gate PASS, 935 frames, 39.0 s. Default driver for later episodes.
