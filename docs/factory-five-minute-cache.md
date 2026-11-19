# Five-minute native film route (strict cache-only mode)

This first end-to-end experiment reassembles the **previously audited guardrail** 900-frame 1080×1920 / 30fps / Cycles32 native footage with expanded English narration, captions and audio QA, and tests whether it can finish in **300 seconds**.

- `workflow_dispatch` is intentionally NOT on by default; push to isolated experiment branch triggers one test. No YouTube upload.
- Source run + exact source commit hashes and successful conclusions must match. Already-rendered chunks must be available; if an artifact has expired, **FAIL, never re-render in lower resolution**.
- Reuses the existing `guardrail_expanded/assemble.py` for footage manifest checks, captions, voice and video QA, not a replacement with weaker assertions.
- Final local proof independently uses ffprobe to check all **900 decoded 1080×1920 H.264 frames** at 30fps, 30s film duration and AAC narration. This is a technical proof and **not human/editorial upload approval**.
- The full job has a hard 5-minute GitHub timeout; its own measured assembly must also finish within 300 seconds or report failure.
- This is an experiment proving a 5-minute `cached` render/assembly **path**, not showing that a wholly new, unsaved 3D mechanism can be calculated within 5 minutes.
- Fresh high quality 3D frames previously took 100–126 seconds each on standard Linux CPU runners; 570 new frames spread across 18 workers took ~68m. GPU/asset library pre-rendering required for a fresh full film SLA.
- No change to default engine or existing PRs. Keep auto publishing disabled.
