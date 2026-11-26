# EP.32 plan: the truck that's built to get hit (truck-mounted attenuator)

Owner brief 2026-11-26: "숏폼으로 만들어" (make Shorts) after the retention plan; the first Short under docs/episode-playbook.md
section 9. Topic in the shape of EP.21 and EP.13 (big road hardware catching something huge by giving way); not an earlier upload
(sand barrels and the jersey barrier were made; a crash cushion on a parked work truck, its honeycomb rows and the roll-ahead are new).

## Script (31.6 s, 101 words, 192 wpm; voice -3 %, gap 0.12 s) and shots (show exactly what each line says)
| # | line | shot |
|---|---|---|
| 1 | Why would road crews park a truck right in your lane? | A1: the red car already crushing into the yellow cushion on the orange truck, pieces flying (held 2.64 s) |
| 2 | It's a shield, parked on purpose between traffic and the workers. | B: a driver's raised view: traffic passing in the open lane, the truck and its arrow board in the closed lane, the crew and roller beyond |
| 3 | On its back is a crash cushion that folds down like a tail. | C: side view: the cushion swings down from upright to level, clanks into place |
| 4 | Inside are blocks of thin aluminum honeycomb. | D (signature reveal, sting): the cushion opened from the back, straight into the hexagonal cells, out to the three blocks sliding apart |
| 5 | When a car hits, the honeycomb crushes row by row. | E: side, cut open: the back row crushes into a dark folded band, then the middle, then the front |
| 6 | So the car slows down over about eight feet of crushing metal. | F: high side: the glowing outline of the uncrushed cushion against the crushed one |
| 7 | The truck is heavy and braked, \| so it only rolls a few feet. | G1: the braked rear tandem shoved along, tyre marks; cut on "so" to G2: wide, the truck stopped, the crew far ahead |
| 8 | It's built to stop a five-thousand-pound pickup at sixty-two miles an hour. | H: the white test pickup into the cushion, stopped inside the stroke |
| 9 | In one state, drivers hit thirty-nine of them in under eight months. | I (end punch, loop): a driver who does not see the truck, into frame 1 |

## Model (benchmarks/attenuator_truck/tma_motion.py)
Car 1,400 kg at 62 mph; three honeycomb blocks crushing at 120 / 200 / 380 kN (back to front, strokes 1.0 / 1.0 / 1.2 m, 13.7 ft
cushion); truck 22,000 lb braked at 0.40 of its weight. Car crush 8.0 ft in 0.14 s, truck shoved 4.6 ft; the 5,000 lb pickup
crushes 10.1 ft of the 10.5 ft stroke. Sources and the claims check: examples/episodes/ep32-publish-kit/README.md.

## Storyboard notes
- Portrait frames with 24 mm read far too wide: every subject was a speck; cameras re-set with the projection check (the car at least
  a third of the frame width in the opening).
- A camera inside a tree went black (G2): trees now start 30 m from the road.
- The honeycomb seen side-on read as white boxes; the reveal now starts straight into the cells, with a dark diaphragm behind each block
  and bright rims on the cell ends, then pulls out as the blocks slide apart.
- Tyre smoke as grey spheres looked fake: dropped; the slide shows as tyre marks and locked wheels.

## Local and CI
Local low-res (765 frames at 162x288, 3 samples, composed to 1080x1920): every gate PASS on the first run (physics, pace 18.8 cuts a
minute / 192 wpm / 31.9 s, opening hook, line alignment, telemetry, visible action, no scene text, loop, smoothness, black opening,
captions, audio -15.2 LUFS / true peak -1.8 dBFS / speech 9.8 dB over the effects). The 1 fps sheet reads without sound.
CI run 45846376909 (sha 73a59d9, 64 frame jobs at 720x1280 / 16 samples + final, 30 min): every gate PASS (the same twelve as
local; audio -15.2 LUFS, true peak -1.8 dBFS, speech 9.8 dB over the effects). Film tma-film-1080x1920.mp4 sha256
3783e1c2345a5e92764e98bb50c2ce139e810b1f1c887107460a23e7fa09dc99 (1080x1920, 765 frames, 31.875 s), copied to
ep05-review/EP32-truck-built-to-get-hit.mp4. Checked at full size: frame 1, the honeycomb face (246), the blocks apart (300), the
uncrushed outline (450). Not verified: the voice and mix by ear, a human first view.

## v2: the series tail (owner, 2026-11-26)
Owner: "views are quite high but almost nobody subscribes", then yes to "series number + next-part teaser + subscribe line at the
end". EP.32 becomes part one of a run (part two EP.33, the ship dolphins; part three EP.34, the runaway-truck net). After the last
frame, 3.5 s of EP.33's opening shot (its clean rendered frames 0-83, no captions: the bow crushing into the dolphin, then the cut
to the wide shot of the dolphins around the pier), its effects ducked 6 dB under one line in the narration voice, "Subscribe for
part two: what stops a giant ship.", captioned like the film. The loop is given up for the teaser (accepted by the owner).
- Tool: benchmarks/series_tail.py (tests/test_series_tail.py). The line is frozen in examples/episodes/ep32-audio/tail/ (cta.wav
  48 kHz mono and cta.json with the measured word timings; edge-tts Andrew at -3 %, the films' voice and rate). "Subscribe" rather
  than "Follow": the word on YouTube's button.
- Inputs: the CI final outputs of run 45846376909 (tma-film-1080x1920.mp4 sha256 3783e1c2..., mix.wav, sfx.wav, film.ass) and of
  EP.33's run 45851558094 (panel shards 0-72 = frames 0-83, renderer 1bb9ef2b...; sfx.wav).
- Command: `python3 -m benchmarks.series_tail --film tma-film-1080x1920.mp4 --film-dir <EP.32 final> --narration
  examples/episodes/ep32-audio/narration.wav --next-panels <EP.33 panels 0-72> --next-sfx <EP.33 final>/sfx.wav --cta
  examples/episodes/ep32-audio/tail --out OUT --name tma-film-v2`
- Result: every gate PASS. 849 frames, 35.375 s; the film part re-encoded once (PSNR 54.45 dB against the input); the tail frames
  hash-checked as EP.33's (segments A1-bow-hits, B-guards); the captions say exactly the line and sit in the film's caption rows
  (1447-1498), the last one up to the last frame; mix -15.2 LUFS, true peak -1.4 dBFS, the line 19.7 dB over the effects; the film's
  own sound unchanged apart from a 0.2 dB trim; no frozen frame; no black opening. Film tma-film-v2-1080x1920.mp4 sha256
  f48a3bb31a7fa67b0b6ad46ccdb39edb5db370a39af7a960645d583f08da57c5, copied to ep05-review/EP32-truck-built-to-get-hit-v2.mp4 (upload
  this one). Not verified: the tail's sound by ear.

