# Comet revision after Terra's visual review

This revision keeps the verified 63.345-second narration and timeline while increasing per-scene caption size from 72 to 88. The default renderer caption size remains 72 for other projects.

The numerical explanation separates G-ALYU's 1,221 actual cycles, 1,836 additional simulated cycles and 3,057 total cycles. Large original diagrams distinguish the upper-fuselage ADF opening from passenger cabin windows, explain a rivet-hole crack and compare crack growth before/after repeated loading. The final card summarizes repeated pressure, crack growth and structural failure. Diagrams are explicitly schematic, not photographic evidence or scale reconstructions. Existing photograph attribution and license text remain on each beat.

Sources checked:
- https://www.rafmuseum.org.uk/research/archive-exhibitions/comet-the-worlds-first-jet-airliner/comet-failure
- https://collection.sciencemuseumgroup.org.uk/objects/co202453/section-of-upper-fuselage-of-comet-g-alyp-showing-fatigue-cracks
- https://www.faa.gov/lessons_learned/transport_airplane/accidents/G-ALYV

The RAF Museum states the exact 1,221/1,836 counts; the FAA overview uses rounded/different counts. The existing narration retains the RAF Museum figures. The G-ALYU test rupture and the G-ALYP accident-origin evidence are kept distinct.

## Reusing the unchanged narration

The opt-in render argument --narration-cache accepts a bundle exported with shorts_studio.narration_cache.export_cache(source_manifest, source_build, destination). It stores a copy of the source manifest, the original scene MP3 and word-timing files, and their SHA-256 values. Reuse refuses changed narration, narration plans, source metadata, audio bytes or timing bytes. No TTS call is made on this path. Ordinary renders remain unchanged.

For this measured revision, all seven source MP3s and timing files and the complete published captions.srt are byte-identical to the previous verified candidate. The original candidate video remains unchanged. New video SHA-256: 0819f5471f04a4d05e153c8006fee1c4739b2d02cb163ac1292d2d2d173c8c1a.

## Validation and limits

The first render failed the existing real-pixel visual-activity gate: number-only cards and a subtle crack edit left 8 seconds visually similar. That failed video and QA remain preserved outside the repository. The successful revision changes the actual diagrams and comparison layout; QA code and thresholds were not modified. Final automated QA passes, maximum measured static hold is 3.5 seconds, and the first five seconds retain three real visual changes. Caption/picture overlap is false.

Computed exact-source reuse decreases, but original diagrams/composites and archival source families must still be assessed by visual review; file diversity alone does not prove new information. Each diagram now has explicit truthful semantic labels and was re-evaluated against its actual rendered beat. Required scene and beat semantic checks pass. Optional subchecks without applicable geometry or sidecar evidence remain explicitly NOT_EVALUATED. The pipeline's aggregate pass is not human approval or independent verification of audio quality. This revision has not been merged, uploaded to YouTube, or accepted by the user.

tools/build_comet_terra_cards.py recreates owned diagram PNGs. tools/preview_comet_revision.py serves only a fixed, hash-bound passing review artifact over loopback, independently of the original preview.
