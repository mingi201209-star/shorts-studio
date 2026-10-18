# Expanded English guardrail explanation

Owner feedback: long silent gaps; expand the script, retain the full 30 seconds.
Reuse exactly all 900 native frames from completed director run 39111993576.
No Blender rerender, video retiming, repeated holds or audio speed-up.
The voice remains en-US-AndrewNeural +5%; genuine provider word boundaries drive captions.
Captured assets and exact transcripts are hash-checked. Existing native/caption gates remain.
Additional audit: actual final AAC silence (-35 dB, intervals at least 0.3 s) must have
no interval above 0.9 s and at most 5 s total. These are pacing checks, not subjective voice approval.

Capture used edge-tts 7.3.1 in a temporary isolated phone path; the old 7.2.8 client
returned HTTP403. No production dependency or engine defaults were changed.
Source explanation: https://highways.dot.gov/safety/rwd/reduce-crash-severity/guardrail-101
This is a rigid-vehicle kinematic explanation, not validated crash physics.
Keep PR draft; no merge or YouTube upload.

Processed speech is lossless PCM WAV so exact sample duration is consistent across ffmpeg versions. Original provider MP3 bytes and hashes are retained. MP3 encoder-padding differences were caught by the strict slot gate; that gate was not relaxed.
