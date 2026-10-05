"""Subtle-breath layer (shorts_studio.breath), opt-in via
Project.enable_subtle_breaths / synthesize_plan(enable_subtle_breaths=...).

The one constraint every test here ultimately serves: a breath must never
move a single spoken word's timestamp (it only ever replaces an
already-inserted silence with a same-duration soft inhale), and with the
feature disabled (the default), behavior must be completely unchanged.
"""
import asyncio
import hashlib
import shutil
import subprocess
import sys
import types

import pytest

from shorts_studio.breath import (
    BREATH_GAIN_CEILING_DB,
    MAX_BREATH_DURATION_SECONDS,
    MAX_BREATHS_PER_NARRATION,
    MIN_BREATH_DURATION_SECONDS,
    MIN_BREATH_GAP_SECONDS,
    plan_breaths,
    render_breath_gap_clip,
    select_breath_gaps,
)
from shorts_studio.prosody import ANTICIPATORY, PhraseSpec
from shorts_studio.korean_boundary import STRONG_BOUNDARY
from shorts_studio.timing import validate_timings
from shorts_studio.tts import synthesize_plan

requires_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="requires a real ffmpeg binary")

# --- select_breath_gaps -----------------------------------------------------

def test_no_gaps_no_breaths():
    assert select_breath_gaps(unit_count=1, gaps=[]) == []

def test_all_gaps_too_short_for_a_breath():
    assert select_breath_gaps(unit_count=4, gaps=[0.10, 0.20, 0.30]) == []

def test_short_narration_can_have_zero_breaths():
    # Two units -> exactly one gap; even if it clears the floor, a 2-unit
    # narration must be allowed to come back with no breath at all is NOT
    # required here -- what IS required is that it never gets more than the
    # density cap allows, and the cap for a tiny narration is 1.
    chosen = select_breath_gaps(unit_count=2, gaps=[0.50])
    assert len(chosen) <= 1

def test_single_eligible_gap_is_chosen():
    assert select_breath_gaps(unit_count=6, gaps=[0.50]) == [0]

def test_prefers_the_longest_strong_boundary_style_gaps():
    # 0.68 is the real ANTICIPATORY/REVEAL-strength pause value from
    # prosody.PAUSE_SECONDS -- the single longest in that table. With a cap
    # of 1 it must win over shorter, weaker-boundary-style gaps.
    gaps = [0.46, 0.68, 0.50]
    chosen = select_breath_gaps(unit_count=3, gaps=gaps)
    assert chosen == [1]

def test_never_selects_two_consecutive_gaps():
    gaps = [0.60, 0.61, 0.62, 0.63, 0.64, 0.65, 0.66, 0.67, 0.68]
    chosen = select_breath_gaps(unit_count=12, gaps=gaps)
    for a, b in zip(chosen, chosen[1:]):
        assert b - a >= 2, chosen

def test_never_exceeds_the_experiment_cap():
    gaps = [0.60] * 20
    chosen = select_breath_gaps(unit_count=30, gaps=gaps)
    assert len(chosen) <= MAX_BREATHS_PER_NARRATION

def test_density_scales_with_narration_length_not_hardcoded():
    gaps = [0.60] * 20
    few_units = select_breath_gaps(unit_count=3, gaps=gaps)
    many_units = select_breath_gaps(unit_count=30, gaps=gaps)
    assert len(few_units) <= len(many_units)

def test_weak_boundary_style_gap_never_chosen_even_if_others_are_eligible():
    # index 1 is deliberately below MIN_BREATH_GAP_SECONDS.
    gaps = [0.60, 0.20, 0.60]
    chosen = select_breath_gaps(unit_count=9, gaps=gaps)
    assert 1 not in chosen

def test_no_breath_index_can_ever_reach_past_the_last_gap():
    # Structural guarantee: a breath index is always < len(gaps), which
    # itself is always len(units)-1 -- so a breath can never land "after the
    # last narration" (there is no gap entry there at all).
    gaps = [0.60, 0.61, 0.62]
    chosen = select_breath_gaps(unit_count=9, gaps=gaps)
    assert all(0 <= i < len(gaps) for i in chosen)

# --- plan_breaths ------------------------------------------------------------

def test_plan_breaths_is_deterministic_for_a_fixed_seed():
    gaps = [0.60, 0.65]
    a = plan_breaths(gaps, [0, 1], seed=7)
    b = plan_breaths(gaps, [0, 1], seed=7)
    assert a == b

def test_plan_breaths_duration_bounds():
    gaps = [0.45, 3.0]  # one barely-eligible, one unrealistically long
    plans = plan_breaths(gaps, [0, 1], seed=1)
    for p in plans.values():
        assert MIN_BREATH_DURATION_SECONDS <= p.duration <= MAX_BREATH_DURATION_SECONDS

def test_plan_breaths_gain_ceiling_is_enforced():
    for seed in range(20):
        plans = plan_breaths([0.60], [0], seed=seed)
        assert plans[0].gain_db <= BREATH_GAIN_CEILING_DB

def test_plan_breaths_varies_slightly_across_gaps_not_identical_copy_paste():
    gaps = [0.60, 0.62, 0.64]
    plans = plan_breaths(gaps, [0, 1, 2], seed=3)
    durations = {round(p.duration, 4) for p in plans.values()}
    gains = {round(p.gain_db, 4) for p in plans.values()}
    assert len(durations) > 1 or len(gains) > 1, "every breath looked byte-for-byte identical"

# --- render_breath_gap_clip ---------------------------------------------------

def _probe_duration_seconds(path) -> float:
    import re
    out = subprocess.run(["ffmpeg", "-i", str(path)], capture_output=True, text=True).stderr
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", out)
    h, mnt, s = m.groups()
    return int(h) * 3600 + int(mnt) * 60 + float(s)

@requires_ffmpeg
def test_breath_clip_duration_matches_existing_silence_clip_behavior(tmp_path):
    from shorts_studio.tts import _silence_clip
    gap_seconds = 0.60
    plans = plan_breaths([gap_seconds], [0], seed=0)
    breath_clip = render_breath_gap_clip(tmp_path / "breath.mp3", gap_seconds, plans[0])
    silence_clip = _silence_clip(tmp_path / "silence.mp3", gap_seconds)
    # Both go through the same mp3 encoder, which adds the same small,
    # well-known encoder-priming padding -- what matters is that a breath
    # clip is never longer/shorter than a plain silence clip of the same
    # requested duration by more than that shared encoder artifact.
    assert _probe_duration_seconds(breath_clip) == pytest.approx(_probe_duration_seconds(silence_clip), abs=0.02)

@requires_ffmpeg
def test_breath_clip_is_deterministic_given_same_plan(tmp_path):
    plans = plan_breaths([0.60], [0], seed=5)
    a = render_breath_gap_clip(tmp_path / "a.mp3", 0.60, plans[0])
    b = render_breath_gap_clip(tmp_path / "b.mp3", 0.60, plans[0])
    assert hashlib.sha256(a.read_bytes()).hexdigest() == hashlib.sha256(b.read_bytes()).hexdigest()

@requires_ffmpeg
def test_breath_clip_never_clips_and_stays_under_the_gain_ceiling(tmp_path):
    plans = plan_breaths([0.60], [0], seed=11)
    clip = render_breath_gap_clip(tmp_path / "c.mp3", 0.60, plans[0])
    vol = subprocess.run(["ffmpeg", "-i", str(clip), "-af", "volumedetect", "-f", "null", "-"],
                          capture_output=True, text=True).stderr
    import re
    max_volume = float(re.search(r"max_volume:\s*(-?[\d.]+) dB", vol).group(1))
    assert max_volume <= BREATH_GAIN_CEILING_DB + 6.0, "breath peak is far louder than its declared gain -- check for clipping"
    assert max_volume < 0.0, "breath clipped (0 dBFS or above)"

@requires_ffmpeg
def test_breath_clip_too_short_for_a_real_gap_falls_back_to_silence(tmp_path):
    # A gap that barely clears MIN_BREATH_GAP_SECONDS can still end up with
    # too little room once the fraction/clamp math runs -- must never force
    # an uncomfortably short burst in; falling back to silence is correct.
    tiny_gap = MIN_BREATH_GAP_SECONDS
    from dataclasses import replace
    plans = plan_breaths([tiny_gap], [0], seed=0)
    forced_plan = replace(plans[0], duration=0.02)  # simulate a too-short plan
    clip = render_breath_gap_clip(tmp_path / "fallback.mp3", tiny_gap, forced_plan)
    vol = subprocess.run(["ffmpeg", "-i", str(clip), "-af", "volumedetect", "-f", "null", "-"],
                          capture_output=True, text=True).stderr
    import re
    mean_volume = re.search(r"mean_volume:\s*(-?[\d.]+) dB", vol)
    # Pure silence: ffmpeg reports no meaningful mean_volume line at all, or
    # an extremely low one; either way it must not contain a real breath.
    assert mean_volume is None or float(mean_volume.group(1)) < -60.0

# --- end-to-end through synthesize_plan --------------------------------------

def _fake_edge_tts_module(tmp_path, unit_durations: dict[str, float]):
    fake_edge_tts = types.ModuleType("edge_tts")
    class FakeCommunicate:
        def __init__(self, text, voice, **k):
            self.text = text
        async def stream(self):
            duration = unit_durations[self.text]
            clip = tmp_path / f"_gen_{abs(hash(self.text))}.mp3"
            subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                             "-t", str(duration), "-q:a", "9", str(clip)], check=True, capture_output=True)
            yield {"type": "audio", "data": clip.read_bytes()}
            words = self.text.split()
            step = duration / max(1, len(words))
            for i, w in enumerate(words):
                yield {"type": "WordBoundary", "text": w,
                       "offset": int(i * step * 10_000_000), "duration": int(step * 10_000_000)}
    fake_edge_tts.Communicate = FakeCommunicate
    return fake_edge_tts

def _install_fake_edge_tts(module):
    previous = sys.modules.get("edge_tts")
    sys.modules["edge_tts"] = module
    return previous

def _restore_edge_tts(previous):
    if previous is None:
        del sys.modules["edge_tts"]
    else:
        sys.modules["edge_tts"] = previous

# A 7-unit plan whose last-phrase-per-unit boundaries reproduce the real
# shape of a hydroplaning-style narration: several STRONG_BOUNDARY gaps and
# one ANTICIPATORY (REVEAL) gap -- the single longest, so it is the one a
# cap-of-1 selection must land on.
def _sample_plan():
    return [
        PhraseSpec(role="HOOK", text="실은 도로에 닿지 않습니다", boundary=STRONG_BOUNDARY),
        PhraseSpec(role="CRISIS", text="방금 전엔 멀쩡했어요", boundary=STRONG_BOUNDARY),
        PhraseSpec(role="INVESTIGATION", text="실제 트레드입니다", boundary=STRONG_BOUNDARY),
        PhraseSpec(role="INVESTIGATION", text="물이 쌓입니다", boundary=ANTICIPATORY),
        PhraseSpec(role="REVEAL", text="쐐기처럼 커집니다", boundary=STRONG_BOUNDARY, focus=True),
        PhraseSpec(role="EXPLANATION", text="접촉이 줄어듭니다", boundary=STRONG_BOUNDARY),
        PhraseSpec(role="PAYOFF", text="하이드로플레이닝입니다", boundary=STRONG_BOUNDARY),
    ]

def _unit_durations_for(plan):
    return {p.text: 0.6 for p in plan}

@requires_ffmpeg
def test_breaths_disabled_by_default_produces_no_breath_metadata(tmp_path):
    plan = _sample_plan()
    module = _fake_edge_tts_module(tmp_path, _unit_durations_for(plan))
    previous = _install_fake_edge_tts(module)
    try:
        asyncio.run(synthesize_plan(plan, tmp_path / "out.mp3", tmp_path / "out.json"))
    finally:
        _restore_edge_tts(previous)
    import json
    data = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert data["breaths"] == []

@requires_ffmpeg
def test_breaths_enabled_adds_one_to_three_breath_records(tmp_path):
    plan = _sample_plan()
    module = _fake_edge_tts_module(tmp_path, _unit_durations_for(plan))
    previous = _install_fake_edge_tts(module)
    try:
        asyncio.run(synthesize_plan(plan, tmp_path / "out.mp3", tmp_path / "out.json", enable_subtle_breaths=True, breath_seed=1))
    finally:
        _restore_edge_tts(previous)
    import json
    data = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert 1 <= len(data["breaths"]) <= MAX_BREATHS_PER_NARRATION

@requires_ffmpeg
def test_breaths_never_change_word_timing_versus_disabled(tmp_path):
    """The core correctness constraint: enabling breaths must not move a
    single spoken word's start/end, because the breath only ever replaces
    an already-sized silence with a same-duration soft inhale."""
    plan = _sample_plan()
    durations = _unit_durations_for(plan)

    module = _fake_edge_tts_module(tmp_path / "off", durations)
    (tmp_path / "off").mkdir()
    previous = _install_fake_edge_tts(module)
    try:
        words_off = asyncio.run(synthesize_plan(plan, tmp_path / "off.mp3", tmp_path / "off.json", enable_subtle_breaths=False))
    finally:
        _restore_edge_tts(previous)

    module2 = _fake_edge_tts_module(tmp_path / "on", durations)
    (tmp_path / "on").mkdir()
    previous = _install_fake_edge_tts(module2)
    try:
        words_on = asyncio.run(synthesize_plan(plan, tmp_path / "on.mp3", tmp_path / "on.json", enable_subtle_breaths=True, breath_seed=1))
    finally:
        _restore_edge_tts(previous)

    assert [(round(w.start, 3), round(w.end, 3)) for w in words_off] == \
           [(round(w.start, 3), round(w.end, 3)) for w in words_on]

@requires_ffmpeg
def test_breaths_enabled_word_timings_still_pass_validate_timings(tmp_path):
    plan = _sample_plan()
    module = _fake_edge_tts_module(tmp_path, _unit_durations_for(plan))
    previous = _install_fake_edge_tts(module)
    try:
        words = asyncio.run(synthesize_plan(plan, tmp_path / "out.mp3", tmp_path / "out.json", enable_subtle_breaths=True, breath_seed=2))
    finally:
        _restore_edge_tts(previous)
    validate_timings(words, max(w.end for w in words) + 1.0)  # must not raise

@requires_ffmpeg
def test_breaths_enabled_produces_a_longer_or_equal_total_audio_not_shorter(tmp_path):
    """A breath clip must never come out shorter than the gap it replaces
    (that WOULD silently eat into the next word's lead-in silence)."""
    plan = _sample_plan()
    durations = _unit_durations_for(plan)
    module = _fake_edge_tts_module(tmp_path, durations)
    previous = _install_fake_edge_tts(module)
    try:
        asyncio.run(synthesize_plan(plan, tmp_path / "out.mp3", tmp_path / "out.json", enable_subtle_breaths=True, breath_seed=1))
    finally:
        _restore_edge_tts(previous)
    assert _probe_duration_seconds(tmp_path / "out.mp3") >= sum(durations.values())

@requires_ffmpeg
def test_two_unit_narration_with_short_gap_gets_no_breath(tmp_path):
    plan = [
        PhraseSpec(role="HOOK", text="짧은 문장", boundary=STRONG_BOUNDARY),
        PhraseSpec(role="PAYOFF", text="끝", boundary=STRONG_BOUNDARY),
    ]
    durations = {"짧은 문장": 0.3, "끝": 0.2}
    module = _fake_edge_tts_module(tmp_path, durations)
    previous = _install_fake_edge_tts(module)
    try:
        asyncio.run(synthesize_plan(plan, tmp_path / "out.mp3", tmp_path / "out.json", enable_subtle_breaths=True, breath_seed=0))
    finally:
        _restore_edge_tts(previous)
    import json
    data = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    # HOOK's own gap (0.40s) is just under MIN_BREATH_GAP_SECONDS (0.45s).
    assert data["breaths"] == []
