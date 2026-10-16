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

## Owner TTS direction — 2026-10-16
- Latest owner instruction (verbatim): Tts는 이제 유튜브에 나오는 tts처럼 바꿔. 걍 듣기좋게
- Prioritize actual listening comfort and natural Korean explainer delivery: clear consonants and vowels, one consistent voice throughout, fluent sentence context, short meaning-based pauses, modest pace and restrained emphasis. Avoid robotic chopped units, harsh/metallic timbre, overacting or gratuitous breath effects. Do not assume a different speed/pitch alone fixes naturalness.
- Produce actual same-script candidate audio against the current baseline before adopting a voice/provider. Test the opening plus full paragraph and known 빗길/닿을/파고드는 problem phrases; preserve measured caption alignment. Automated ASR/quality metrics are diagnostics, not evidence of human preference.
- This explicitly authorizes improving the TTS implementation and choosing among existing available licensed voices, preserving rollback and all quality gates. Do not clone a particular creator, add paid services without authorization, or treat unreviewed output as human-approved. Run regression and real render/CI before claiming completed.
