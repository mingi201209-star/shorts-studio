# Complete guardrail film — draft review

The requested deliverable is six shots, exactly 30 seconds / 900 frames at 30 fps,
1080×1920, Korean narration and provider-timed burned-in subtitles. It is an
explanatory authored 3D film, not a calibrated crash simulation or an upload.

The opening reuses the 90-frame native result at scene SHA
`cbd575cf598dd71f786a6b2a65838de22b0350c5`, workflow run `39100332936`.
The remaining 810 frames render the same packed scene with new shots at native
resolution, Cycles 32 samples. Geometry, materials, wheel animation and rail
motion remain from the independently audited source. All final source PNGs are
hashed and checked at 1080×1920 before encoding; missing or duplicate frames fail.
Camera fitting reserves space for titles and captions and checks every visible
car mesh bounding box at every new output frame. The two mechanical inserts
omit the vehicle to expose the rail/post connections; their footage is an
explanatory replay. No end-terminal mechanism is depicted.

Story: collision hook (3 s), W-beam structure (5 s), deflection (6 s),
posts/connections/soil (5 s), redirection (5 s), limits (6 s).
`film.json` owns exact ranges and narration. Existing Korean speech/prosody
functions synthesize the voice, and their actual timings drive subtitle cues.
Audio must fit each scene without time compression; subtitles, decoded frame
count, audio codec, duration, black-frame runs and final decode are gated.

Existing production, semantic, retention, TTS and QA code and thresholds remain
unchanged. This separate film workflow reports technical acceptance separately
from manual editorial and voice review. Keep PR 50 draft and main untouched.
No merge, YouTube upload, paid provider or new cloud service.

Sources for the narration:
- FHWA Guardrail 101: https://highways.dot.gov/safety/rwd/reduce-crash-severity/guardrail-101
- FHWA definitions of energy absorption through beam/post deformation and soil rotation: https://www.fhwa.dot.gov/guardrailsafety/safetyanalysis/appendix_a.cfm
- Asset names, licenses and pinned checksums: ../guardrail_v2/ASSETS.md

The source animation is an illustration. Its displaced/sheared posts do not
measure real soil forces, steel stresses, occupant injury or crashworthiness.
The final film states that it is an explanatory 3D illustration, not a test.
