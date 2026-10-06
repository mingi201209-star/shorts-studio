# Claude Code repository instructions

## Source reuse first
- Before writing a new implementation, search for and prefer maintained human-authored public code or official vendor examples that solve the same problem.
- Priority: official implementation/example > actively maintained OSS with tests/CI > widely used library/reference implementation > custom code.
- Verify license compatibility before copying or adapting code. Prefer permissive licenses such as MIT, Apache-2.0, or BSD and preserve required notices/attribution.
- Never copy unlicensed, leaked, proprietary, or unclear-license code.
- Reuse the smallest relevant implementation surface and keep repository-specific integration glue minimal.
- Public code is not automatically correct: run upstream tests where practical and add regression coverage here.
- Especially for TTS, FFmpeg/media processing, subtitle alignment/timing, download/retry logic, CI, and video primitives, prefer proven implementations over inventing replacements.
- If custom code is necessary, document why no suitable maintained implementation was available and keep the custom portion minimal.

## Product and safety constraints
- Do not weaken, bypass, disable, or mock existing quality, semantic, caption, safe-area, retention, or render-integrity gates.
- Human-perceived output quality overrides an automated green check. Cheap-looking CG or robotic narration is a product failure even when tests pass.
- Preserve existing main.py/video/create_scene-compatible architecture and working features unless a change is explicitly justified and regression-tested.
- Do not enable or perform YouTube upload/publishing.
- Do not merge pull requests without explicit user approval.
- If a change regresses quality or reliability, revert that change and continue from the last verified-good state with a different approach.
