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
(local preview at every 8th frame and CI to be recorded)
