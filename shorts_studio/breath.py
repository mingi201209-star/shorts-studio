"""Subtle inhale-breath layer for narration pauses. Opt-in, off by default
(see Project.enable_subtle_breaths) -- existing productions' audio must
never change.

Design constraint from direct user instruction: a breath must never move a
single spoken word's timestamp. The Korean Prosody Planner
(shorts_studio/prosody.py) already inserts a REAL silence clip into the
synthesized audio between two synthesis units whenever
`shorts_studio.prosody.pause_after()` returns a positive duration -- that
silence clip's duration is exactly what every later word's cumulative
offset is computed from (see tts.synthesize_plan's `cursor` arithmetic).
This module never adds, removes, or resizes a pause: it only ever decides
whether ONE of those already-existing pause windows gets a soft breath
sound in place of pure silence, and the replacement clip is built to the
EXACT same duration the silence clip would have been. No word timing, no
caption timing, and no scene/unit duration changes as a result.

Why a procedural layer (Approach B) rather than relying on the TTS
provider's own prosody (Approach A): edge-tts's Communicate API exposes no
documented control to request an audible inhale at a specific point, and
this sandbox has no live network path to the provider to empirically test
whatever implicit breath-like pausing it might already produce. A
self-synthesized, deterministic, seeded layer is the only approach that is
both testable here and controllable in production.

Placement policy ("where a human would actually breathe"): only the
narratively STRONGEST pause windows are eligible, approximated by the pause
duration itself -- prosody.PAUSE_SECONDS already encodes discourse strength
this way (e.g. the REVEAL's anticipatory pause at 0.68s is the single
longest value in the whole table, specifically for the
investigation-to-reveal turn; PAYOFF's 0.56s is the next longest). Ranking
candidate gaps by their own existing duration and taking the top few is
therefore already "prefer a long-explanation-into-the-next-key-sentence,
INVESTIGATION->REVEAL, EXPLANATION->TWIST, TWIST->PAYOFF" boundaries,
without hardcoding any role name. A breath before the very first unit or
after the very last is structurally impossible: `gaps` only ever has one
entry BETWEEN two units (see prosody.group_into_units / tts.synthesize_plan),
so index 0 always follows real speech and there is never an entry after the
final unit.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

# A gap shorter than this cannot comfortably hold a short inhale plus the
# silence padding on both sides without feeling crowded against the
# adjacent words -- see REFERENCE_PAUSE_IQR in prosody.py: this sits just
# below the IQR's own lower bound, so an ordinary sentence-break pause
# qualifies but a bare "weak_boundary"-grade gap (which never reaches this
# function in practice; only STRONG_BOUNDARY/ANTICIPATORY gaps are ever
# inserted in the first place) would not.
MIN_BREATH_GAP_SECONDS = 0.45

# "초기 실험은 대략 1~3개의 breath만 허용" -- an explicit experiment-phase cap,
# not a permanent density target.
MAX_BREATHS_PER_NARRATION = 3

# A real human inhale between clauses is brief; see BREATH_DURATION_FRACTION
# below for how the actual per-breath duration is derived from its gap.
MIN_BREATH_DURATION_SECONDS = 0.10
MAX_BREATH_DURATION_SECONDS = 0.30
BREATH_DURATION_FRACTION = 0.40  # of the gap, before clamping to the bounds above

# Well under narration level (narration peaks are typically well above
# -10 dBFS for synthesized speech at normal listening volume); see
# tests/test_breath.py's gain-ceiling test for the enforced bound.
BREATH_GAIN_DB = -26.0
BREATH_GAIN_CEILING_DB = -18.0  # a louder breath than this is a bug, not a style choice

# Band-limit to the airflow-turbulence range of a real inhale -- this is
# what keeps it reading as "breath" rather than a flat-spectrum
# white-noise hiss (which a plain anoisesrc burst, unfiltered, sounds like).
BREATH_HIGHPASS_HZ = 250
BREATH_LOWPASS_HZ = 3000
BREATH_FADE_FRACTION = 0.30  # of the breath's own duration, each edge


@dataclass(frozen=True)
class BreathPlan:
    gap_index: int
    duration: float
    gain_db: float
    seed: int


def select_breath_gaps(unit_count: int, gaps: list[float]) -> list[int]:
    """Pick 0-3 gap indices (into `gaps`) for a subtle inhale.

    Ranks every gap long enough to hold one by its own duration (the
    existing narrative-strength signal -- see module docstring), picks the
    longest first, and skips any candidate adjacent to one already chosen
    so two breaths never land back to back. The cap scales with how much
    narration there is (roughly one breath per three synthesis units, never
    more than MAX_BREATHS_PER_NARRATION) rather than being a fixed count --
    a two-unit narration can legitimately come back with zero breaths.
    """
    eligible = [i for i, g in enumerate(gaps) if g >= MIN_BREATH_GAP_SECONDS]
    if not eligible:
        return []
    ranked = sorted(eligible, key=lambda i: gaps[i], reverse=True)
    cap = min(MAX_BREATHS_PER_NARRATION, max(1, unit_count // 3))
    chosen: list[int] = []
    for i in ranked:
        if len(chosen) >= cap:
            break
        if any(abs(i - c) < 2 for c in chosen):
            continue
        chosen.append(i)
    return sorted(chosen)


def plan_breaths(gaps: list[float], chosen: list[int], seed: int = 0) -> dict[int, BreathPlan]:
    """Build a deterministic BreathPlan for each chosen gap index.

    Every value is a pure function of (gap duration, gap index, seed) --
    the same inputs always produce the same plan, and therefore (combined
    with ffmpeg's own seeded anoisesrc, see render_breath_gap_clip) the
    exact same audio, which is what makes this reproducible. The small
    per-gap jitter below exists only so that when more than one breath is
    used in the same narration, they are not an identical copy-paste of
    each other -- never introduces true randomness.
    """
    plans: dict[int, BreathPlan] = {}
    for i in chosen:
        gap_seconds = gaps[i]
        jitter = ((seed * 2654435761 + i * 40503 + 1) % 1000) / 1000.0  # deterministic, 0..1
        raw_duration = gap_seconds * BREATH_DURATION_FRACTION * (0.85 + 0.3 * jitter)
        duration = max(MIN_BREATH_DURATION_SECONDS, min(MAX_BREATH_DURATION_SECONDS, raw_duration))
        gain_db = min(BREATH_GAIN_CEILING_DB, BREATH_GAIN_DB + (jitter - 0.5) * 3.0)
        plans[i] = BreathPlan(gap_index=i, duration=duration, gain_db=gain_db, seed=seed * 1000 + i)
    return plans


def render_breath_gap_clip(path: Path, gap_seconds: float, plan: BreathPlan) -> Path:
    """Render a clip of EXACTLY `gap_seconds` duration -- silence, then a
    soft band-shaped inhale, then silence -- so using this in place of a
    plain `_silence_clip` of the same duration changes nothing about any
    downstream cumulative word/caption timestamp (see module docstring).

    The breath itself is procedurally synthesized with ffmpeg's own
    `anoisesrc` source filter: pink noise (more low-frequency weight than
    white noise, closer to a real inhale's character) seeded for exact
    reproducibility, band-limited to the airflow-turbulence range, and
    shaped with a soft triangular fade in/out rather than a hard on/off --
    no external audio sample of any kind is used.
    """
    duration = min(plan.duration, max(0.0, gap_seconds - 0.05))
    if duration < MIN_BREATH_DURATION_SECONDS:
        # The gap barely clears the eligibility floor; a breath this short
        # would feel crowded against the surrounding words -- fall back to
        # plain silence rather than force it in.
        return _silence_clip(path, gap_seconds)
    lead = max(0.0, (gap_seconds - duration) * 0.45)
    trail = max(0.0, gap_seconds - duration - lead)
    fade = max(0.01, min(duration / 2, duration * BREATH_FADE_FRACTION))
    breath_filter = (
        f"anoisesrc=d={duration:.3f}:c=pink:a=1.0:r=24000:seed={plan.seed % 2147483647}[n];"
        f"[n]highpass=f={BREATH_HIGHPASS_HZ},lowpass=f={BREATH_LOWPASS_HZ}[bp];"
        f"[bp]afade=t=in:d={fade:.3f}:curve=tri,afade=t=out:st={max(0.0, duration - fade):.3f}:d={fade:.3f}:curve=tri,"
        f"volume={plan.gain_db:.2f}dB[breath];"
        f"anullsrc=r=24000:cl=mono:d={lead:.3f}[lead];"
        f"anullsrc=r=24000:cl=mono:d={trail:.3f}[trail];"
        f"[lead][breath][trail]concat=n=3:v=0:a=1[out]"
    )
    subprocess.run(
        ["ffmpeg", "-y", "-filter_complex", breath_filter, "-map", "[out]",
         "-t", f"{gap_seconds:.3f}", "-q:a", "9", str(path)],
        check=True, capture_output=True,
    )
    return path


def _silence_clip(path: Path, seconds: float) -> Path:
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", str(seconds), "-q:a", "9", str(path)],
        check=True, capture_output=True,
    )
    return path
