# EP.34 plan: how do you stop a truck that's lost its brakes? (runaway-truck arrester nets)

Owner, 2026-11-26: views are quite high but almost nobody subscribes, then yes to a series with a teaser of the next part at the end
of each Short (playbook section 10). EP.34 is part three of "Built to Get Hit": part one EP.32 (the truck-mounted attenuator), part
two EP.33 (ship-impact dolphins). Topic in the shape of the two hits: big road hardware catching something huge by giving way. The
early runaway-ramp Short was about gravel beds; this one is the mechanical ramp, where steel nets and their absorbers do the work.

## Facts (sources in the publish kit's claims check)
- Net ramps exist on steep mountain roads: TxDOT El Paso (Loop 375 Transmountain Road, opened 2026-07-01), VDOT US 250 Afton
  Mountain (2024) and WYDOT Teton Pass WYO 22 (2017).
- TxDOT: eight energy-absorbing net stations anchored in reinforced concrete walls; designed for a 90,000 lb truck at 90 mph;
  resets in about four hours after a typical impact. WYDOT Teton Pass: also rated 90,000 lb / 90 mph.
- Construction: aircraft-cable or stainless-steel nets. On each side, a tape near the top of the net and one near the bottom runs
  into an absorber set in the wall.
- Metal Bender absorbers pull steel tape through offset pins, bending and straightening it.
- VDOT: the nets slow a big rig gently enough to avoid injuring the driver.

## Narration (edge-tts Andrew at -7 %, 108 words, 33.8 s, 191 wpm; examples/episodes/ep34-audio)
1. How do you stop a truck that's lost its brakes?
2. On some steep mountain roads, you catch it in a giant net.
3. Steel cable nets hang across the ramp, one after another.
4. Each one is tied to steel tape, coiled up in boxes inside the walls.
5. When the truck hits, the tape is dragged through pins that bend it back and forth.
6. Bending all that steel soaks up the speed, net after net.
7. The catch is gentle enough to protect the driver.
8. They're built to stop a ninety-thousand-pound truck at ninety miles an hour.
9. Then crews swap in fresh tape, and it's ready again in about four hours.
At -3 % the same lines ran 199 wpm, at the pace gate's edge; -7 % reads easier.

## Shots (each line shows what it says; benchmarks/truck_net/net_timeline.py)
| Row | Line | Shot |
|---|---|---|
| A1-net-grabs | 1 | Inside the ramp, ahead-left: the red semi plowing into net 1, net over the grille, tapes out of the wall. Slow motion, held through the line. |
| B-mountain | 2 | Up the mountainside: the truck comes off the mountain highway into the ramp and its nets. |
| C-nets-in-a-row | 3 | Down the ramp: the nets hung one after another, posts on both walls. |
| D1-tied-to-tape (reveal) | 4 | The wall cut open at net 2: the net's corner and its tapes going into the box, with the channel's sting. |
| D2-coiled | 4, from "tape" | Closer: the two coils of tape and the pins inside the wall. |
| E1-truck-hits | 5 | On the right wall: the truck hits net 2, its tapes whip out of the wall. |
| E2-pins | 5, from "is" | Close, in the cut-away: the tape running through the pins (marks along it move), the coil spinning and shrinking. |
| F-net-after-net | 6 | Ahead-left, high: nets 3, 4 and 5 picked up one after another, tapes trailing back to the walls. |
| G-driver | 7 | Tracking in front of the cab: the nets on the grille, the driver held upright behind the windshield as the truck stops. |
| H-ninety | 8 | Tracking the 90,000 lb tanker at 90 mph: it picks up all eight nets and stops before the end. |
| I-fresh-tape | 9 | From above: the crew lowering a fresh coil into net 1's open absorber, the used tape on the ramp, the nets hung again. |
| J-loop | 9, from "and" | The nets ready, the next truck coming, into frame 1. |

## Model (benchmarks/truck_net/net_motion.py)
- Each net, once picked up, wraps the front. Its sides run from the truck's corners back toward the tape exits in the walls (the
  net does not stretch), so with the front d past the station the net holds the truck back with 4 T d / sqrt(s^2 + d^2) and has
  paid out sqrt(s^2 + d^2) - s of each tape. The force builds from nothing, like a stretched band.
- Parameters: T = 18 kN per tape (about 4,000 lb), s = 3.2 m (a 30 ft wide ramp, a 2.6 m truck), eight nets 15 m apart, 125 m of
  tape per absorber.
- Results: the 80,000 lb semi at 60 mph picks up 5 nets and stops in 224 ft (4.1 s), peak 1.0 g. The 90,000 lb tanker at 90 mph
  picks up all 8 and stops in 367 ft, peak 1.4 g, with at most 357 ft of tape out.
- The energy bent out of the tapes matches the truck's (gate).
- Simplified explanation model, not a product's test data.

## Storyboard notes
- First pass: the camera outside the left wall had the wall's top filling the frame, and the mountainside read as a white slab.
  Fixed: the camera moved inside the ramp, and the mountainside is darker and greener.
- The low sun from the left threw the wall's shadow over the opening's foreground; it now comes from ahead-right.
- The steel tape inside the dark box was mirror-like and vanished; it is now less metallic, with marks along it that move as it
  pays out.
- The solid cab hid the driver; the cab is now built from panels around a hollow inside, behind see-through glass, with a small
  light.
- The wide and the tanker shots lost the truck at a distance; they now track it (cameras relative to the truck's front).

## Local and CI
Local low-res (818 frames at 162x288, 3 samples, composed to 1080x1920): every gate PASS on the first run:
- physics, pace (21.1 cuts a minute, 191 wpm, 34.1 s), opening hook (truck 41 % of the width, all in frame);
- line alignment, telemetry, visible action, no scene text;
- loop (seam 1.43 against neighbouring steps 3.02 / 1.63), smoothness (no frozen frame), black opening, captions;
- audio -15.2 LUFS, true peak -1.7 dBFS, speech 9.0 dB over the effects.
The 1 fps sheet reads without sound.
