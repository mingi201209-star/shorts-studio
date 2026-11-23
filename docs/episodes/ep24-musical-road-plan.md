# EP.24 plan: the musical road that plays out of tune

Owner request 2026-11-23: "음.. 이번엔 댓글이 많이 달릴 만큼 신기한거. 자동차. 도로 쪽" (something amazing enough to get a lot of
comments; cars, roads).

Why this topic: a road that plays a song is an instant "wait, what?" with the sound on, and the story has a twist that people argue
about and share: America's famous musical road in Lancaster, California is out of tune because the crew measured the spacing the
wrong way. Comment hooks: "it IS out of tune", "I've driven it", and the pinned question "what song should the next musical road
play?". The physics is one clean idea (pitch = speed / groove spacing) that the sound itself demonstrates: the tune is not a music
track but synthesized from the model's tyre thumps, so slowing the picture splits the note into separate thumps and speeding it up
blurs them back into a note. No other episode was about sound or music.

One thread, 11 lines: drive over this road and it plays a song -> it's cut with grooves like a giant vinyl record -> each time a
tire hits a groove it makes a thump -> hundreds of thumps a second blur into one note -> close grooves make a high note and wider
gaps a lower one -> space them just right and the road plays a melody -> drive slower and the song slows down and drops in pitch ->
in California one plays the William Tell Overture -> but the crew measured the gap between grooves, not groove to groove -> so
every note came out flat, the high notes most of all -> that's why California's famous musical road is out of tune (loops into
line 1). Two lines were reworded and the commas taken out after the TTS merged words ("This road", "Lancaster, California") and
left too much silence; the voice was slowed after a take at 219 wpm.

Frame 1 (hook rule): low, just ahead of the red sedan as it drives over the grooves at 55 mph, the stripes streaming under it, the
tune (as built, slightly wrong) playing; held through the first line.

Shots: A1 hero, B the grooves like record grooves with the car coming over them (built for the camera to see the stripes converge),
C the front tyre in slow motion with a ring on the asphalt for each thump, D the same tyre speeding up until the thumps are a note,
E from above: wide gaps low, close grooves high, F a drone ahead of the car with the grooves it just played glowing, G the car at 35
mph, H the desert road with the snow-capped mountains, I top-down macro: the plan's groove-to-groove bar (blue), the grooves sliding
apart until the gap equals it (red), J the built grooves against the planned ones (blue lines) as the car comes over them, K loop.

Model benchmarks/musical_road/musical_motion.py (gate musical_physics: the opening phrase of the William Tell finale twice, laid out
for 55 mph; designed spacing in tune within 1 cent; the repeated B 3.92 in apart; built with each spacing one groove width (3/4 in,
an assumption) wider: B 3.0 semitones flat, G# 4.8 semitones flat, the tune's leap squeezed from 900 to 720 cents; 35 mph 7.8
semitones lower at 64 % of the tempo; the rear tyres replay the tune 0.094 s later), timeline musical_timeline.py, renderer
render_musical_3d.py (desert, creosote bushes, Joshua trees, power poles and lines, three mountain ranges with snow caps, the road and
876 / 706 grooves, the CC0 sedan in house red with turning wheels, thump rings, glow trail, measuring bars, planned-groove lines),
sound musical_sfx.py (the tune from the model's thumps), assembly assemble_musical_film.py, CI .github/workflows/ep24-film.yml
(request examples/experiments/musical-film-request.json), tests tests/test_ep24_musical.py (incl. the camera never under the road or
inside the car).

## Audience data
(to be recorded at 48 h and 7 days)

## Preview
Local low-res run: pending.
CI: pending.
