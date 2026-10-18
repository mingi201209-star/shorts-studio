# CC0-car rumble-strip motion experiment (HOLD)

- Subject is approved episode 2, **rumble strips**, in the agreed seven-part American road-safety series.
- Reuses a locally existing, previously created Blender guardrail scene containing an original CC0 sedan with 72 meshes; it does not download a new model or generate generic car parts.
- Source is **strictly SHA-256 pinned** and is kept outside Git (historical scene binary). See the source file for the exact digest. This is an experiment and the source needs provenance packaging before repeatable CI rendering.
- In this experiment the barrier and previous scenery are cleared, and the existing vehicle is repositioned over genuine recessed 3D road geometry. Locked camera, portrait ratio, per-frame native original image. Later mechanical QA must ensure the wheel spokes rotate at the right rate rather than inheriting unrelated collision animation.
- The pilot uses 450×800/Cycles7 for local preview only; production remains 1080×1920/Cycles32. No quality gate is weakened.
- No speech, captions, end-to-end video, or upload authorization. This is a first hero-shot visual study.
- Run manually:
```bash
blender -b -noaudio -t 4 -P benchmarks/road_safety/rumble_cc0_reuse.py -- --source /path/to/pinned-guardrail.blend --out /tmp/rumble-car-review --preview --frames 4
```


## Tested prototype (local, opt-in)

Pinned car scene was copied without mutation to:

`/root/shorts-work-backups/road-safety-assets/guardrail-car-cc0-pinned-a82e0582.blend`

Two camera variants were rendered using the same 72-mesh CC0 car: full-car hero and contact-wheel mechanism close-up. Four unique original PNGs each; four separate rolling-wheel pivots. Early contact render exposed a slab that occluded the recessed pockets; fixed by lowering the underlying road substrate and independently re-rendered.

Preview commands:
```bash
blender -b -noaudio -t 4 -P benchmarks/road_safety/rumble_cc0_reuse.py -- --source /root/shorts-work-backups/road-safety-assets/guardrail-car-cc0-pinned-a82e0582.blend --out /tmp/rumble-hero --preview --frames 4 --view hero
python -m shorts_studio.factory.rumble_pilot_qa --frames-dir /tmp/rumble-hero --frames 4
```

The visual QA is only a **technical pilot gate**: it enforces source hash, correct actual pixel resolution, Cycles sample count, four rotating wheels, car parts, individual unique frames, non-black frames and render-time logs, but never authorizes publishing. Subjective image review is still required. The preview quality and car motion are not independently measured physics.
