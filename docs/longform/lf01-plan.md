# Long-form 1 plan: 7 clever ways roads stop things that are out of control

Owner brief 2026-11-26: "우리 채널이 수익창출을 하려면 앞으로 어케 해야해?" then "롱폼부터 만들어보자". Monetization needs 1,000
subscribers and either 4,000 public watch hours in 12 months or 10 million Shorts views in 90 days (both doubled for new applicants from
1 February 2027); Shorts views do not count as watch hours, so the channel needs long videos. This is the first.

## Format
- 16:9, 1920x1080 (rendered at 1280x720, 16 samples), 24 fps, 5:08 (7,391 frames), no burned-in captions (an .srt goes with the upload),
  chapters in the description.
- Narration: the same voice at -20 % (154 wpm, calmer than the Shorts' 180-195), nine blocks (intro, seven chapters, outro), 775 words.
- Built from seven episodes' worlds and models (EP.13, 15, 26, 19, 18, 21, 22): each shot is a shot of its episode re-framed for 16:9
  (same camera place and aim, lens x 0.85; one shot re-aimed after the storyboard) and re-timed: a shot's story knots are stretched to
  the long line's length so its whole action stays in it. The owner rule "show exactly what each line says" holds line by line; lines
  that name several things cut on the word (the intro's "seven clever ways" shows all seven; the outro's "steel that crushes, cables
  that stretch, nets that give, and blocks that crumble" cuts on each).
- Theme from the two best Shorts (EP.21 rockfall net 21,000 views, 73 % viewed, 93 % average viewed; EP.13 guardrail end 9,000, 69 %,
  90 %): road hardware that catches something out of control. The outro states the shared idea (stretch the stop: the longer the stop,
  the smaller the force).

## Code
benchmarks/longform/: lf_timeline.py (layout and per-episode virtual timelines from fresh copies of each episode's timeline module),
lf01.py (the script's shot list per line, 16:9 overrides, chapter names), render_lf.py (an episode's own renderer on its virtual
timeline at 16:9), storyboard_lf.py (16:9 stills per row), build_audio.py (the Shorts' narration builder without the 5 s total-silence
cap), assemble_lf.py (compose, narration, each episode's own sound design laid under its shots, -14 LUFS mix, .srt, chapters, gates:
frames, each episode's physics gate, lines shown, no scene text, no black frames, smoothness, length, audio mix). CI:
.github/workflows/lf01-film.yml (208 jobs of 36 frames, episode by episode; final assembly on the runner's large disk), request
examples/experiments/lf01-film-request.json. Publish kit: examples/longform/lf01-publish-kit/README.md.

## Preview
Local preview (every 8th frame of every shot at 288x162, 3 samples; the frames between held): every gate PASS but smoothness, which needs every frame and runs in CI (7391 frames, 307.96 s, 87 shots, all seven episodes' physics gates PASS, every line starts on its planned shot, mix -14.3 LUFS, true peak -1.4 dBFS, speech 14.6 dB over the effects). The first run's true peak read -0.9 dBFS over the -1.0 limit; the limiter now aims at -2.0 dB (inter-sample peaks).
CI run 1 (45784358840, sha cf108a8, 208 frame jobs + final, 3 h 24 min): every gate PASS but smoothness. frames 7391 / 307.96 s
complete, all seven physics gates, every line on its planned shot, no scene text, no dark frames, length 308 s, mix -14.3 LUFS, true
peak -1.4 dBFS, speech 14.6 dB over the effects; smoothness FAIL: 10 frozen frames (film frames 3066-3076), the first second of the
roller crash-test shot ("One version passed a sixty-two mile an hour crash test"). Cause: its straight-down camera was kept as in the
9:16 Short, where the car's 22 m run (y -12 to +14) lies along the tall side; in 16:9 that is the short side, so the shot opened on an
empty road and the car entered only after about a second (also against the owner rule: the line's picture must show the test from its
first frame). The 16:9 preview could not see it (every 8th frame held). Fix: lf01.OVERRIDES turns that camera a quarter (the run
across the long side, 19 mm, 14.2 m above the road pushing in to 13.0 m): the car is in the picture from the first frame, hits the
rollers mid-frame and leaves on the far side (low-res check: every frame differs from the last, min mean change 0.52 of 255; test
test_roller_crash_test_shot_shows_the_car_from_its_first_frame, which fails on the old camera).
CI run 2: the workflow can now re-render only some shards on top of an earlier run (request: frames_run + rerender {episode: [[first,
last]]}); the 5 roller shards covering virtual frames 772-916 are rendered again, the other 203 reused from run 1 (same renderer
sources, resolution and samples). Result: run 45817850400 (sha 4eaf532, 5 frame jobs + final, 45 min): every gate PASS:
frames 7391 / 307.96 s complete, all seven physics gates, every line on its planned shot, no scene text, no dark frames, smoothness
0 frozen frames (median change 1.37), length 308 s, mix -14.3 LUFS, true peak -1.4 dBFS, speech 14.6 dB over the effects. The crash-test
shot now opens with the car on the left, hits the rollers mid-frame and leaves on the right. Film lf01-1920x1080.mp4 sha256
a4cd9eebae5248c0ab6505f6dc4ca6a1fc70ef6c0a76d03d3ee594ab97dec21f (h264 1920x1080 24 fps, AAC 48 kHz, 240 MB), with lf01.srt and
lf01-chapters.txt; copied to ep05-review/LF01-roads-stop-runaways.mp4 (+ .en.srt, chapters, thumbnails). Not verified: the voice and
mix by ear, a human first view.
