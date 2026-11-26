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
