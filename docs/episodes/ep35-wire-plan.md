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
CI run 46014566989 (sha e7e3d67, 71 frame jobs at 720x1280 / 16 samples + final, 32 min): every gate PASS on the first attempt:
- opening hook: jet 89 % of the width, 94 % in frame;
- captions in the new look, widest line 843 px;
- audio -15.3 LUFS, true peak -1.9 dBFS, speech 8.9 dB over the effects;
- no frozen frame.
Film wire-film-1080x1920.mp4 sha256 94c9553b616f70c78c18ee6807f1e5206be6530491c4cb2c29b83ea04fea7ad6 (1080x1920, 845 frames,
35.208 s), copied to ep05-review/EP35-carrier-arresting-wire.mp4. Its first 97 frames are EP.34 v2's part-four teaser. Not
verified: the new voice and the mix by ear, a human first view.

## v2: the detail pass (owner, 2026-11-27: "근데 좀 디테일이 사라졌어", the detail went missing)
Not uploaded yet, so the whole film is rendered again; EP.34 v2's teaser is rebuilt from the new opening.

What was wrong:
- The main cause was a sky-strength override. Every outdoor frame set the sky to 1.0, about four times the house style's
  0.24-0.30 (EP.32-34), so the fill light flattened every shadow and the film read pale and flat. The fix restores the house
  style: sky 0.26, dust 0.7, sun 6.5, exposure +0.15.
- The scene itself was plain: box island, flat deck, a simple jet, block crew.

What is new (benchmarks/carrier_wire/detail.py):
- The fighter:
  - a lofted fuselage under a subdivision surface, in two-tone grey with panel lines;
  - strakes, intakes, canted fins with a red band, petalled nozzles, landing gear, lights;
  - a framed canopy with an instrument panel.
- The deck: fine grain, tyre rubber laid down along the centre line, oil stains, catapult tracks, elevators, foul stripes.
- The deck edge: catwalks with safety nets and life-raft canisters.
- The island: built up in tiers, with a lattice mast, radars and radomes.
- Parked jets with folded wings and coloured bands, tow tractors.
- The deck crew: float vests with reflective bands over their jerseys, cranial helmets with goggles and ear defenders, gloves and
  boots. The arresting-gear crew wears green.
- The hull: near-vertical sides with a boot-top band at the waterline, hangar doors with lamps, the fantail, galleries.
- The sea: the wake as streaked foam over turquoise prop wash, and an escort on the horizon.

Storyboard fixes:
- The bow catapults' blast deflectors first stood in the landing runout, where the jet would hit them, and filled the full-throttle
  shot. A ray-cast from every outdoor camera found them. They now stand past the end of the runout, as on a real deck.
- The first deck texture was stripey. The rubber is now soft and only near the centre line.
- The first wake read as clouds. It is now foam streaks over turquoise prop wash.
- The hull read white in the sky fill. It is now a darker haze grey.
- The crew shot I2 now tracks the crew from closer.
- In the cockpit shot the canopy bow was a solid disc, so Bumper looked as if he sat on top of the jet in front of a grey
  dome. The bow and a windscreen arch are now open rings. The ejection seat sits right behind his back, and the glass reflects
  the sky toward its edges (Fresnel), so he reads as inside the canopy.
- The full-power exhaust was a solid peach cone. It is now a flame: white-hot at the nozzle, thinning to orange and nothing at
  the tip, with shock diamonds and soft edges.

Captions: a little tracking (spacing 1.5), so the heavy face's word spaces read at phone size.
