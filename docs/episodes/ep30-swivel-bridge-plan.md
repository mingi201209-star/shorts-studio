# EP.30 plan: the swivel bridge (why is this giant bridge spinning above a railway)

Owner brief 2026-11-25: "다른거 몇개 더 만들어놔" (make a few more, different ones). Second of three new topics (EP.29 the blade
lifter, EP.30 this, EP.31 the road that sprays water). The first pick, the bridge-building machine that walks on its own (SLJ900),
was dropped because it only works on railway viaducts, not roads; the swivel bridge keeps the road theme: a road bridge built beside
a railway and spun over it.

Why this topic: a structure the size of a skyscraper on its side turning in the sky over live tracks, the whole subject in frame 1,
one counter-intuitive idea (build it sideways, then spin it on one ball joint), big plain numbers (46,000 tons, almost 900 feet, 52
degrees in 68 minutes, eight times slower than a minute hand, a window of under two hours).

One thread, 11 lines (39.1 s, 178 wpm): why is this giant bridge spinning above a railway -> a road bridge in China built beside the
tracks -> trains can't stop for long so it's built first and turned into place -> it sits on one giant ball joint in its pier -> 46,000
tons, almost 900 feet long -> it slowly turns on that one joint -> 52 degrees in 68 minutes -> about eight times slower than a clock's
minute hand -> a window of under two hours -> trains rolling underneath again soon after -> that's why some bridges in China are built
sideways and then spun into place (loops into line 1).

Frame 1 (hook rule): from high above the north side, the bridge in mid-turn swinging out over the railway (time-lapse, 12 degrees
during the line), the deck at least two thirds of the width; held through the first line. The hook gate projects the deck as a box
turned with the bridge (not the square round it).

Shots (13): A1 hero from high up, B low beside the tracks: the bridge built alongside, a train rushing past, C1 the train running past
the bridge, C2 where it will sit (translucent), D the swivel cut open (lower turntable, ring track, spherical hinge with its liner and
grease, upper turntable), E1 the pier under the deck, E2 along the deck from one end (its whole length), F the turntable turning, G the
whole turn from above, H a clock's minute hand (translucent, above the deck) racing round it, I a train waiting at a red signal during
the window, the bridge turning far off, J a train rolling under the turned bridge, K loop into frame 1.

Model benchmarks/swivel_bridge/swivel_motion.py (gate swivel_physics: 46,000 t, 263.6 m (865 ft), 52.4 degrees in 68 minutes with a
soft start and stop, about 7.8 times slower than a minute hand, inside the 110-minute window, the deck clear of the overhead wires once
turned and nowhere over the tracks before), timeline swivel_timeline.py, renderer render_swivel_3d.py (a city edge on a plain: a
four-track electrified railway with signals and two trains, apartment blocks, low buildings, fields and car parks, streets with trees,
the construction site with two tower cranes and site cabins; the T-shaped box-girder deck on its pier and swivel; the translucent
final position and clock), sound swivel_sfx.py, assembly assemble_swivel_film.py, CI .github/workflows/ep30-film.yml (request
examples/experiments/swivel-film-request.json), tests tests/test_ep30_swivel.py (incl. no camera in the deck, the pier or a train).

## Audience data
(to be recorded at 48 h and 7 days)

## Preview
Local low-res run (whole film, 162x288 at 3 samples, 4 shards): every gate PASS (944 frames, 39.333 s, pace 19.8 cuts/min at 178 wpm, opening shot 2.83 s with the deck 100% in frame and 64% of the width, mix -15.1 LUFS, speech 10.2 dB over the effects). Before it, the first stills were reworked: the opening (a thin deck at the horizon over a bare plain) now looks down on the deck from 120 m, the plain has low buildings, fields, car parks, a construction site, two tower cranes and site cabins; B now has a train rushing past the camera; the length shot (blocked by an apartment block) now looks along the deck from one end; the ball-joint shot was cut open on two different planes (the fixed lower parts across the turning upper parts) and hidden behind a support foot: one cut plane now, square to the camera, the hinge drawn as a concave bowl and a convex ball with the liner between, the near foot hidden; the whole film was re-rendered for this run.
CI: (to be recorded)
