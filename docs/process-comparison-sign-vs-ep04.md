# Why EP.04 needed so many previews: comparison with the breakaway-sign episodes (from the real run logs, 2026-11-17)

Sources: workflow runs `breakaway-sign-preflight.yml` / `breakaway-sign-production.yml` (runs 43377792537-43452181850, 2026-11-13) and `ep04-crumple-preview.yml` (runs 43876264484-43969105859, 2026-11-16); `docs/breakaway-sign-post-round1.md`; `git log` of both branches.

## What the logs say (corrects "the sign video was one preview")
| | Sign v1 | Sign v2 (after owner review) | EP.04 previews 1-8 |
|---|---|---|---|
| full-length low-res preflights | 4 (3 failed) | 4 (3 failed) | 8 (all failed), then partial range runs |
| wall time of those runs | 06:18 -> 07:06 = 48 min | 12:02 -> 12:53 = 51 min | 13:29 -> 15:53 = 2 h 24 min |
| full render after PASS | 77 min | 70 min | not started |
| failure causes | silence 5.94 s; shots 17-21 % off the spoken windows; 5.5 s static hold | dead air 1.19 s; silence 5.52 s; shots 29-31 % off + 6 s hold + read-outs 1.5 s | TTS no-audio x2 (one was my retry bug); dead air; silence; loudness spread; then 3D: nose through the barrier, X-ray against the sky, action under captions, late fold onset, wrong sky metric |
| class of failure | audio/timing (2-3 per round), one visual-activity | same | 5 of 8 audio/timing, 3 of 8 3D geometry (new class) |

So the sign episodes were not "one preview": they needed 8 preflights over two rounds, 6 of them failed, each ~12 min. The difference is that every failure there was cheap and decided offline-able things (narration length, shot boundaries from measured speech); nothing was geometry.

## Causes, ranked by evidence
1. **Audio/timing was discovered by the picture preview in both projects.** TTS length decides total silence, dead air, loudness and where shot/cue boundaries sit. Sign: 5 of 6 failures. EP.04: 5 of 8 previews. Avoidable by measuring the real speech first (EP.04 now has `ep04-audio-cues.yml`, ~3 min, no render) and planning the timeline on the measured cues - this was done only after preview 8.
2. **A new risk class in EP.04: deforming a third-party mesh.** The sign episodes used rigid cars; EP.04 bends the CC0 sedan. Its nose/wheel/plate positions were unknown until the real vertices were dumped (Blender probe, ~30 s) - after that every wall/camera/caption problem was found by a 0.3 s Python test instead of a 17 min render. Previews 6-8 were this class.
3. **Scope growth during production (owner's hypothesis: partly confirmed).** The preview-1 commit already had the crash sim, renderer and gates. After preview 1 the scene-execution spec with six alignment criteria, a capability list (distance/time bars, force arrows, occupant), an X-ray requirement and per-frame evidence were added (preview 2) on request; later bars/arrows/occupant were removed again (owner decision) and the scenes re-described. The audio gates were NOT new (they are the shared QA, unchanged) and the geometry gates only found real defects. So the gate count was not the main cost; unfinished scope (items that could not be built, then dropped) and finding the defect class late were.
4. **Process, mine:** audio and picture ran in the same preview, so a flaky TTS call cost a full Blender job; one retry bug (rm -rf removed in preview 2) cost a run.

## The single-pass method for the next episode (sign-style, with the lessons)
1. Freeze the scene list and what counts as done BEFORE coding (what is on screen, what is not; bars/arrows/occupants/labels are optional unless the narration cannot be understood without them). New requirements go to the NEXT episode, not into this one.
2. Narration first: run the audio-only job; fix length/silence/loudness there; use the measured cues to set shot boundaries (no provisional boundaries).
3. Offline checks before any render: real mesh vertices (probe once), wall/ground penetration, camera framing, caption rows and mobile safe area, timing against the measured cues, no-frozen-frame by construction. Seconds, not minutes.
4. ONE full-length low-res preview with all gates.
5. Only if a gate shows a real defect: fix and re-render only the affected frames (range mode), never the whole film.
6. Final render, then a person watches it.

Limits: this explains the logs; it does not prove that the sign video's views/retention (3,125 views, 70 %, 26 s as supplied by the owner) came from any process step, and which published video those figures belong to is not stated in the repository.
Open item: the Actions artifact download currently returns `503 Egress is over the account limit`, which blocks any run that downloads shard artifacts (EP.04 final jobs); not fixable from code.
