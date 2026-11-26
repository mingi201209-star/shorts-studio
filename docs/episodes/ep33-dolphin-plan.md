# EP.33 plan: what stops a giant ship from knocking down a bridge (pier-protection dolphins)

Owner brief 2026-11-26: "숏폼으로 만들어" (make Shorts); the topic EP.32's pinned comment promised. Retention plan (playbook
section 9): reveal = the struck dolphin cut in half with the sting; end punch = the 1980 Skyway collapse; teaser in the pinned comment.

## Script (31.1 s, 101 words, 195 wpm; voice -3 %, gap 0.12 s) and shots (show exactly what each line says)
| # | line | shot |
|---|---|---|
| 1 | What stops a giant ship from knocking down a bridge? | A1: the bow already crushing into the dolphin, spray and chips, the bridge's tower behind (held 2.81 s) |
| 2 | A pier can't take that hit, so engineers put guards around it. | B: high: the bridge, the pier, the arc of dolphins in front of it, the ship coming |
| 3 | These round islands are called dolphins. | C: one dolphin close: a round island of steel and concrete |
| 4 | Each is a steel ring \| packed with up to six thousand seven hundred tons of crushed rock. | D1 (signature reveal, sting): cut in half: the ring down into the bed; cut on "with" to D2: the rock packed inside |
| 5 | When a ship hits, the ring bends and the rock packs tighter. | E: in section: the bow pushes, the ring dents in, the rock behind it shifts |
| 6 | The ship's bow crumples too, soaking up its energy. | F: the bow crumpling against the dolphin |
| 7 | So the ship stops before it ever touches the pier. | G: high side: the ship stopped at the dolphin, the pier and tower untouched |
| 8 | Each one can take nearly thirty million pounds of force. | H: in section, the load path glowing through ring, rock and bed |
| 9 | Florida built them after a ship knocked down its Sunshine Skyway bridge in nineteen eighty. | I (end punch, loop): the ship coming on toward the bridge, into frame 1 |

## Model (benchmarks/ship_dolphin/dolphin_motion.py)
87,000 t at 6 knots (414 MJ); push-back F = 125 MN (1 - exp(-d / 1.2 m)); 60 % of the give is the bow, 40 % the ring. Stops in 2.6 s
after 4.5 m (bow 2.7 m, ring 1.8 m), peak 27.4 million lb, 39.5 m short of the pier. Claims check: examples/episodes/ep33-publish-kit/README.md.

## Storyboard notes
- Cut-aways: the camera side of the section (the near half of the sea, bed and struck dolphin, and the other dolphins on that side)
  is dropped; a camera inside a neighbouring dolphin went black before that.
- The bed section is dark soil with the ring's cut walls drawn as two bars going down into it; the water in section is kept thin so
  the rock inside reads.
- Spray: bigger and more pieces, or the hit reads as a gentle bump at phone size.

## Local and CI
Local low-res (752 frames at 162x288, 3 samples): every gate PASS but the opening hook: its subject box (the dolphin plus 26 m of
bow) was wider than any portrait frame, 55 % in frame. The subject is now the collision itself (the dolphin and the bow's front
12 m): 100 % in frame and 75 % of the width in the first second (frames 0, 12 and 23 checked). Physics, pace 19.1 cuts a minute /
195 wpm / 31.3 s, line alignment, telemetry, visible action, no scene text, loop, smoothness, black opening, captions and audio
(-15.2 LUFS, true peak -1.9 dBFS, speech 9.1 dB over the effects) PASS. The 1 fps sheet reads without sound.
CI run 45851558094 (sha 48bb125, 63 frame jobs at 720x1280 / 16 samples + final, 36 min): every gate PASS (opening hook: subject
100 % in frame, 75 % of the width; audio -15.2 LUFS, true peak -1.9 dBFS, speech 9.0 dB over the effects). Film
dolphin-film-1080x1920.mp4 sha256 10311976d58e2bd394a1452d0446ed155b6b1730ae235c2b4c366ecd9ff2dfae (1080x1920, 752 frames,
31.33 s), copied to ep05-review/EP33-ship-vs-bridge-dolphins.mp4. Checked at full size: frame 1, the section (215, 300), the glowing
load path (600). Not verified: the voice and mix by ear, a human first view.
