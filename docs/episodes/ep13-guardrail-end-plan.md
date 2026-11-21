# EP.13 plan: guardrail end terminal (after EP.12's 21.2 % viewed)

Owner direction 2026-11-21: "take the text out first, it's cluttered; make it interesting, make people want to watch it."

What changed, from the data (Road Signs 69.9 %, ESC spin 58.4 % vs cabin/person openings ~22 %):
- No text on the picture: no labels, read-outs or fact cards; only the narration captions (as in EP.04, the owner's earlier decision).
- Topic back to the hidden engineering of roads (the Road Signs kind), not safety advice. "Why guardrail ends curl away" was already
  offered to viewers in the runaway-ramp poll. The breakaway light pole was dropped: same mechanism as Road Signs (overlap rule).
- Road Signs' structure: a question as the first line, 8 short lines at +5 %, 29.6 s.
- Frame 1 is the money shot, outdoors: the car already on the head, the steel ribbon spiralling out, sparks, posts flying.
- Look: golden-hour sun, depth of field, red car, warm grade; slow motion on every hit.
- Sound design for the first time: impacts, steel grind, post cracks, glass, whooshes, a low pulse, ducked under the voice (model-placed).

Model: benchmarks/guardrail_end/terminal_motion.py (gate terminal_physics). Timeline terminal_timeline.py, renderer
render_terminal_3d.py, sound terminal_sfx.py, assembly assemble_terminal_film.py, CI .github/workflows/ep13-film.yml (request
examples/experiments/terminal-film-request.json), tests tests/test_ep13_guardrail.py, narration examples/episodes/ep13-audio.

## Audience data
(to be recorded after upload; compare with EP.12's 21.2 % and Road Signs' 69.9 %)

## Preview
CI run 44889681725 (commit 5336b78): every gate PASS (physics, alignment, telemetry, visible action, no text, loop, smoothness, black
opening, captions, audio mix), 716 frames, 29.8 s; mix -15.3 LUFS, true peak -2.0 dBFS, every line at least 10.2 dB above the effects.
The sound mix has not been listened to by a person.
