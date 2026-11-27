# EP.35 plan: how do you stop a jet doing 150 mph? (carrier arresting wire)

Owner, 2026-11-27: "without our own character the channel gets buried"; the voice: "특이한 목소리로" then option B, a designed voice,
and pick 2B; "ㅇ" to parts 4-6 of "Built to Get Hit" and a part-four teaser on EP.34. EP.35 is the first film with the whole
identity (playbook section 11): Bumper's voice, Bumper on screen, the x-ray reveal look, the caption look.

## Facts (sources in the publish kit's claims check)
- Mk 7 Mod 3: up to 50,000 lb at 130 knots (~150 mph), about 340 ft. A football field is 360 ft.
- The engine is hydropneumatic: purchase cables reeved over sheaves to a crosshead and ram, oil through the constant-runout valve.
- Four wires about 50 ft apart; pilots aim for the third.
- Full power at touchdown in case of a bolter.
- 125 arrestments per cross-deck pendant.
- "Two seconds" is popular but does not square with 340 ft at 150 mph (about 3 s); the film gives the distance, not a time.

## Narration (Bumper, ElevenLabs eleven_multilingual_v2; 111 words, 35.0 s, 190 wpm; examples/episodes/ep35-audio)
1. How do you stop a jet doing a hundred fifty miles an hour?
2. The deck is far too short to brake, so the jet drops a hook.
3. It snags one of four steel cables stretched across the deck.
4. Below deck, the cable runs around pulleys to a giant hydraulic piston.
5. As the jet drags the cable out, the piston forces oil through a valve, turning speed into heat.
6. It stops a fifty-thousand-pound jet in about the length of a football field.
7. The pilot hits full throttle anyway, in case the hook misses.
8. That's me in the cockpit, by the way.
9. And after a hundred twenty-five landings, the cable gets thrown away.

Capture note: the service pins the first character of a take to 0 s even when the take starts with silence (up to 1.2 s here).
benchmarks/voice/eleven.py now moves the first word to where the sound starts, so trims, captions and cuts line up.

## Shots (benchmarks/carrier_wire/wire_timeline.py)
| Row | Line | Shot |
|---|---|---|
| A1-caught | 1 | Behind-left of the jet, tracking: already on the third wire, the wire in a V, sparks, plumes. Slow motion, cut at 3.6 s. |
| B1-short-deck | 2 | Chasing the jet in over the sea, the carrier's short deck ahead. |
| B2-hook-down | 2, from "the jet" | Beside the tail: the striped hook swings down. |
| C-snags-third | 3 | Low on the deck past four wires: the hook skips, snags the third. |
| D-below-deck (reveal) | 4 | X-ray: deck blueprint blue, the cable glowing orange down to the engine, the channel's sting. |
| E1-piston | 5 | X-ray below deck: the crosshead drives the ram into the oil cylinder. |
| E2-valve-heat | 5, from "forces" | X-ray: oil pulses through the valve and line, the valve glowing hotter. |
| F-football-field | 6 | Straight down: a see-through football field over the runout, the jet stopping at its far end. |
| G-full-throttle | 7 | Behind the jet: both nozzles blazing while it is held. |
| H-thats-me | 8 | The cockpit: Bumper thrown forward in the straps, then a thumbs up once stopped. |
| I1-worn-wire | 9 | The deck crew (green jerseys) unhooking the wire. |
| I2-thrown-away | 9, from "the cable" | The crew dragging the worn wire off toward the deck edge. |

No loop: the end belongs to the part-five teaser once part five is rendered (playbook section 10).

## Model (benchmarks/carrier_wire/wire_motion.py)
- A 50,000 lb jet engages at 130 knots with 26,000 lbf thrust.
- The pull builds over 9 m to the level that stops it in 340 ft: 2.94 s, peak 2.46 g.
- The engine takes 62.7 MJ (about 64 MJ in the Mk 7's description).
- Wire tension up to 140,000 lbf per half; 289 ft of cable paid out at each sheave.

## Storyboard notes
- First pass: the scene was washed out and the wire hair-thin. Darker deck, lower exposure, thicker bright wires.
- The x-ray fogged up under the hull's many see-through layers. In x-ray shots the hull, island and hangar deck are hidden; the
  deck, jet and wires turn blue and the engine glows.
- Bumper was buried inside the solid fuselage. He now sits higher, head and shoulders above the canopy rail, under nearly clear
  glass, with a close camera.

## Local and CI
Local low-res (845 frames at 162x288, 3 samples, composed to 1080x1920): every gate PASS on the first run:
- physics, pace (20.4 cuts a minute, 190 wpm, 35.2 s), opening hook (jet 89 % of the width, 94 % in frame);
- line alignment, telemetry, visible action, no scene text, smoothness, black opening;
- captions in the new look (widest line 843 px of 900);
- audio -15.3 LUFS, true peak -1.9 dBFS, speech 8.9 dB over the effects.
After the sheet, the snag shot became a tracking shot on the hook (the jet had crossed the fixed camera too fast to read).
