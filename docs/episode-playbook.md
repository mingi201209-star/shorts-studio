# Episode playbook and scene checklist

Follow this top to bottom for every new Short. It holds the rules from the channel data and the competitor research
(docs/series-plan.md, docs/competitor-analysis-2026-11-21.md) and every mistake found by eye so far, so the work can be done without
re-deriving them. Reference implementation: EP.14 (benchmarks/tempered_glass/: glass_motion, glass_timeline, render_glass_3d,
glass_sfx, assemble_glass_film; .github/workflows/ep14-film.yml; tests/test_ep14_glass.py). Copy it and change the content, not the
structure.

## 1. Pick the topic (before any code)
- [ ] An everyday mystery about cars or roads: something people see but cannot explain (glass cubes on the road, the yellow head on a
      guardrail end). Not a safety lecture.
- [ ] Overlap check: the main event and the main mechanism are not an earlier upload's. Done: breakaway road signs, rumble strips, speed
      bump, crumple zone, seatbelt load limiter, ABS, ESC, airbag, hydroplaning, following distance, headrest, guardrail end terminal,
      tempered glass; also made: jersey barrier, sand barrels, road paint, runaway ramp, train wheels. (EP.11 crash speed was shelved
      because it repeated EP.04.)
- [ ] The first frame can be an outdoor event on a whole car or road hardware, already happening, filling the frame, and it reads as
      violent as a still at phone size: debris or parts in the air, a big deformation, side or high 3/4 view, never head-on (EP.15
      13.7 %: the caught car looked parked). Never a cabin or a
      person (EP.05 23.4 %, EP.12 21.2 % viewed; outdoor events 48-70 %).

## 2. Script (one thread)
- [ ] Line 1 is the question. Every next line is the next step of one cause-and-effect chain. End on the answer, with a "that's why"
      twist if there is one, and loop back to the first frame.
- [ ] About 100 words, 8-9 lines; target 30-36 s at 160-200 words a minute (speaking rate +3 %).
- [ ] Every number comes from the model or from common reference values; write the claims check in the publish kit.
- [ ] Avoid a comma right after a line's first word ("And close, a..." merged into one word and failed the timing check, EP.12).

## 3. Narration (first: its timing sets every cut)
```
SPEECH_RATE=+3% SPEECH_REQUEST_GAP=4 PYTHONPATH=$PWD python3 scripts/episode/tts_proxy_run.py benchmarks/road_safety/curious_mechanics_speech.py --plan examples/experiments/<ep>-speech-plan.json --target-seconds 60 --out <scratch>/speech
PYTHONPATH=$PWD python3 -m benchmarks.crumple_zone.level_beats --folder <scratch>/speech/<id>
PYTHONPATH=$PWD python3 -c "from pathlib import Path; from benchmarks.road_safety import curious_mechanics_audio as ca; ca.build(Path('<scratch>/speech/<id>'), Path('<scratch>/audio'), 60, trim=True, gap_s=0.06)"
```
- [ ] If one line keeps failing with NoAudioReceived, reword that line (EP.13 line 8); retrying does not help.
- [ ] Every beat has word timings that match its words (the capture prints `fit True`; a mismatch fails the build).
- [ ] EXCESSIVE_TOTAL_SILENCE: lower gap_s (0.25 -> 0.06).
- [ ] Copy audio-validation.json, film.ass, narration.wav into examples/episodes/<ep>-audio/ (frozen).

## 4. Model and timeline
- [ ] Model module with a `<x>_physics()` gate that checks every number the narration says, plus tests.
- [ ] Timeline: one row per shot, start at the line's cue (or a word's cue for a mid-line cut), knots map film time to simulated time
      per shot (slow motion where the event is fast).
- [ ] `pace()` gate passes: the opening shot is HELD through the first line (2-3.6 s; benchmarks/hook_gate.py), at least 18 cuts a
      minute, 160-200 wpm, at most 40 s. (The old "first cut by 1.5 s" cut away from the money shot: EP.14-EP.19, 2026-11-22.)
- [ ] Opening framing: the whole car (or machine) in the middle of the event, hero 3/4 or mid-wide, readable at phone size; never an
      extreme close-up or an abstract top-down view as frame 1. The renderer reports "subject_box"; the assembly's opening_hook gate
      checks the first second.
- [ ] The last shot runs into the first frame's moment from the first frame's camera (loop), with no read-outs at the seam.

## 5. Storyboard review (where the quality comes from)
Set up Blender if the container is fresh: `scripts/episode/setup_blender.sh`. Render one frame per shot (two for long shots) and look:
```
/opt/bl/blender-5.0.1-linux-x64/blender -b -t 4 -P benchmarks/<ep>/render_<x>_3d.py -- --source /opt/bl/car.blend --list 0,30,90,... --res-scale 0.3 --samples 8 --out <dir>
python3 scripts/episode/contact_sheet.py frames <dir> 0,30,90,... <dir>/sheet.png
```
Check every frame against this list (each item is a mistake that happened):
- [ ] The key subject is big: at least a third of the frame width in close shots (EP.14 burst and ball were too small at first).
- [ ] Nothing in front of it: mirrors, posts, pillars, nozzle rows (EP.14 mirror over the burst; EP.13 post over the rail end; EP.14
      furnace pipes).
- [ ] A moving subject stays in frame for the whole shot: follow it ("head"/"car"/"lag" cameras) (EP.12 driver slid out).
- [ ] The camera is not inside anything that moves through its position (EP.13 coil vs camera; EP.15 shot H went black as the car
      drove into a world-fixed camera: tests/test_ep15_cable.py checks every frame).
- [ ] No straight-down camera: the roll is unstable; use a high oblique (EP.13 aerial).
- [ ] No lamp panels in shot: every area light has `visible_camera = False` (EP.12 black box at the roof edge).
- [ ] Glow is not washed out: under AgX keep emission low (3-6) with a deep colour (EP.14 furnace turned white).
- [ ] CC0 sedan limits (roof 1.26 m, lower body 0.34-0.84 m): the generic cabin set's headrests, dashboard top and floor poke
      through it (EP.14 v2); the cab is solid behind its glass and the body is a solid block below the windows; the generic cabin set's door
      panels and roof liner stick out of this car. Prefer outside shots; if the camera must see through a window, cut an opening
      (EP.14 `cut_window`) and check what is behind it (EP.14 "wall" was the road).
- [ ] X-ray shots: nothing solid hides the subject; the key part glows orange (EP.13 spear).
- [ ] Particles and pieces do not pass through the car or the ground (model gate, EP.14 ledge).
- [ ] No text anywhere but the captions (owner decision 2026-11-21).
- [ ] House style: golden-hour sun, red car (ghost tint), depth of field, AgX Punchy, white balance 7600.

## 6. Sound
- [ ] Every effect is placed from the model at the film moment it happens (impacts, landings, cracks), plus cut whooshes, wind and a
      low pulse; ducked under the voice.
- [ ] Mix -15 LUFS (+-1.5), true peak at most -1 dBFS, every line at least 8 dB above the effects (audio_mix gate).
- [ ] Draw a spectrogram once: regular stripes mean aliasing (EP.13: the wobble was on the phase instead of the frequency).
- [ ] Nobody has listened yet: always say so when sending.

## 7. Whole film locally, then CI
```
scripts/episode/lowres_render.sh benchmarks/<ep>/render_<x>_3d.py <frames> <dir>
PYTHONPATH=$PWD python3 benchmarks/<ep>/assemble_<x>_film.py --panels <dir> --frames-dir <dir>/composed --out <dir>/final
python3 scripts/episode/contact_sheet.py video <dir>/final/<x>-film-1080x1920.mp4 <dir>/sheet.jpg
```
- [ ] Every gate PASS (physics, pace, alignment, telemetry, visible action, no text, loop, smoothness, black opening, captions, audio).
      Frozen frames: keep the camera moving (half-linear ease) where the subject stops (EP.10/EP.12 loop run-ins).
- [ ] Look at the 1 fps sheet: the story reads without sound, the first frame is the event.
- [ ] Commit, then write examples/experiments/<x>-film-request.json and push it (that starts the CI render). Schedule a check in ~40 min.
- [ ] CI done: download the final artifact, look at the 1 fps sheet and the first frame at full size, copy the mp4 to ep05-review/,
      record the preview in the episode plan, send it with the title and description.
- [ ] Only overlays changed? Re-assemble with `"frames_run": "<run id>"` in the request instead of re-rendering.

## 8. Publish kit and after the upload
- [ ] Title: a few words, exactly one emoji. Description short; it barely matters. Pinned comment asks what to explain next.
- [ ] Read the numbers at 48 h and 7 days, not in the first hour; record them in the episode plan and in the series table.
