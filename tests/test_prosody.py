"""Korean Prosody Planner V2: narrative-role-aware phrasing, variable
pauses (never the same fixed silence everywhere), boundary-classifier-driven
synthesis units (no per-sentence pitch/energy reset), and correct Sino-
Korean number reading independent of punctuation handling. The linguistic
boundary classification itself is tested separately in
tests/test_korean_boundary.py; this file covers the layer built on top of it
(pause tables, rate selection, unit grouping, the real synthesis engine).
"""
import asyncio, subprocess, sys, types
import pytest

from shorts_studio.korean_boundary import CONTINUE, STRONG_BOUNDARY, WEAK_BOUNDARY
from shorts_studio.prosody import (
    ANTICIPATORY, PhraseSpec, build_auto_plan, group_into_units, pause_after,
    plan_narration, rate_for_unit, sino_korean_number, spell_out_numbers,
)
from shorts_studio.tts import synthesize_plan

requires_ffmpeg = pytest.mark.skipif(not __import__("shutil").which("ffmpeg"), reason="requires a real ffmpeg binary")

# --- Sino-Korean number spelling -------------------------------------------

@pytest.mark.parametrize("n,expected", [
    (100, "백"), (1000, "천"), (1004, "천사"), (2020, "이천이십"),
    (1230, "천이백삼십"), (1830, "천팔백삼십"), (9999, "구천구백구십구"), (5, "오"),
])
def test_sino_korean_number_general_not_hardcoded(n, expected):
    assert sino_korean_number(n) == expected

def test_sino_korean_number_rejects_out_of_range():
    with pytest.raises(ValueError):
        sino_korean_number(10_000)

def test_spell_out_numbers_handles_the_factual_comet_figures():
    assert spell_out_numbers("실제 비행에서 1,230회의 반복") == "실제 비행에서 천이백삼십회의 반복"
    assert spell_out_numbers("물탱크에서 1,830회를 추가로") == "물탱크에서 천팔백삼십회를 추가로"

def test_spell_out_numbers_leaves_non_counter_numbers_alone():
    # No recognized counter follows -- leave as digits rather than guess.
    assert spell_out_numbers("전화번호는 1,234 입니다") == "전화번호는 1,234 입니다"

def test_spell_out_numbers_leaves_numbers_above_supported_range_alone():
    assert spell_out_numbers("10,000번") == "10,000번"

# --- unit grouping: only STRONG_BOUNDARY/ANTICIPATORY end a unit -----------

def test_continuation_phrases_group_into_one_unit():
    phrases = [
        PhraseSpec(role="INVESTIGATION", text="결국 조사팀은", boundary=CONTINUE),
        PhraseSpec(role="INVESTIGATION", text="실제 기체를 물탱크에 넣었습니다", boundary=STRONG_BOUNDARY),
    ]
    units = group_into_units(phrases)
    assert len(units) == 1
    assert len(units[0]) == 2

def test_weak_and_phrase_boundary_do_not_end_a_unit():
    from shorts_studio.korean_boundary import PHRASE_BOUNDARY
    phrases = [
        PhraseSpec(role="HOOK", text="a", boundary=WEAK_BOUNDARY),
        PhraseSpec(role="HOOK", text="b", boundary=PHRASE_BOUNDARY),
        PhraseSpec(role="HOOK", text="c", boundary=STRONG_BOUNDARY),
    ]
    units = group_into_units(phrases)
    assert len(units) == 1 and len(units[0]) == 3

def test_strong_boundary_starts_a_new_unit():
    phrases = [
        PhraseSpec(role="HOOK", text="비행기가 부서졌습니다", boundary=STRONG_BOUNDARY),
        PhraseSpec(role="SETUP", text="1950년대의 일이었습니다", boundary=STRONG_BOUNDARY),
    ]
    units = group_into_units(phrases)
    assert len(units) == 2

# --- variable pauses: never the same fixed silence everywhere --------------

def test_pauses_vary_by_role_and_boundary_not_fixed():
    hook_strong = pause_after(PhraseSpec(role="HOOK", text="x", boundary=STRONG_BOUNDARY))
    reveal_anticipatory = pause_after(PhraseSpec(role="REVEAL", text="x", boundary=ANTICIPATORY))
    payoff_strong = pause_after(PhraseSpec(role="PAYOFF", text="x", boundary=STRONG_BOUNDARY))
    assert len({hook_strong, reveal_anticipatory, payoff_strong}) == 3
    # The reveal's anticipatory beat must be the most dramatic pause available.
    assert reveal_anticipatory > payoff_strong > hook_strong

def test_non_unit_ending_boundaries_carry_no_explicit_pause():
    assert pause_after(PhraseSpec(role="HOOK", text="x", boundary=CONTINUE)) == 0.0
    assert pause_after(PhraseSpec(role="HOOK", text="x", boundary=WEAK_BOUNDARY)) == 0.0

# --- role-based rate, with a focus phrase easing off further ---------------

def test_focus_phrase_uses_the_slower_focus_rate_regardless_of_role():
    unit = [PhraseSpec(role="REVEAL", text="결과", boundary=STRONG_BOUNDARY, focus=True)]
    assert rate_for_unit(unit, base_rate="+8%") == "+1%"

def test_non_focus_phrase_uses_its_role_rate():
    unit = [PhraseSpec(role="HOOK", text="x", boundary=STRONG_BOUNDARY)]
    assert rate_for_unit(unit, base_rate="+8%") == "+10%"

def test_unknown_role_falls_back_to_base_rate():
    unit = [PhraseSpec(role="MADE_UP_ROLE", text="x", boundary=STRONG_BOUNDARY)]
    assert rate_for_unit(unit, base_rate="+8%") == "+8%"

# --- auto-fallback plan (no authored narration_plan) now runs the SAME ------
# --- general linguistic planner as explicitly-authored segments ------------

def test_auto_plan_uses_the_linguistic_planner_not_naive_punctuation_split():
    plan = build_auto_plan("코멧이 등장했습니다. 사고가 났습니다.")
    assert [p.boundary for p in plan] == [STRONG_BOUNDARY, STRONG_BOUNDARY]
    assert len(group_into_units(plan)) == 2

def test_auto_plan_does_not_over_segment_a_flowing_sentence():
    # A single sentence with no sentence-final ending until the very end
    # must stay ONE unit, not be chopped at every clause.
    plan = build_auto_plan("모서리가 각진 창문이 있었습니다.")
    assert len(plan) == 1
    assert plan[0].text == "모서리가 각진 창문이 있었습니다."

# --- plan_narration: role segments + the focus/anticipatory floor ----------

def test_plan_narration_merges_across_role_change_when_linguistically_flowing():
    # Two role segments whose junction has no strong grammatical signal
    # must still merge into one unit -- role alone must not force a break.
    plan = plan_narration([("CRISIS", "그런데 얼마 지나지 않아 사고가 잇따랐지만", False),
                            ("CRISIS", "원인은 밝혀지지 않았습니다", False)])
    assert len(plan) == 1

def test_plan_narration_splits_at_a_real_sentence_final_ending():
    plan = plan_narration([("HOOK", "비행기가 부서졌습니다", False),
                            ("SETUP", "1950년대의 일이었습니다", False)])
    assert len(plan) == 2
    assert plan[0].boundary == STRONG_BOUNDARY

def test_plan_narration_floors_the_boundary_into_a_focus_segment():
    # Even if the raw grammar of the preceding segment's last token would
    # otherwise say CONTINUE, transitioning into an authored focus segment
    # must still end a unit and become the anticipatory pre-result beat.
    plan = plan_narration([
        ("REVEAL", "실제 비행에서 약 1,230회의 압력을 견딘 기체는", False),
        ("REVEAL", "물탱크에서 1,830회를 추가로 반복하자 찢어졌습니다", True),
    ])
    assert len(plan) == 2
    assert plan[0].boundary == ANTICIPATORY
    assert plan[1].focus is True
    assert "1950" not in plan[0].text  # sanity: didn't bleed the wrong scene's text

def test_plan_narration_preserves_all_words_no_loss_no_duplication():
    text_a = "결국 조사팀은 실제 기체를 물탱크에 넣고"
    text_b = "비행 중 기압 변화를 그대로 재현했습니다"
    plan = plan_narration([("INVESTIGATION", text_a, False), ("INVESTIGATION", text_b, False)])
    reconstructed = " ".join(p.text for p in plan).replace(",", "").replace(".", "")
    original_tokens = (text_a + " " + text_b).split()
    reconstructed_tokens = reconstructed.split()
    assert reconstructed_tokens == original_tokens

# --- integration: continuation phrases really do become ONE Communicate call

@requires_ffmpeg
def test_synthesize_plan_merges_continuation_into_a_single_call(tmp_path):
    fake_edge_tts = types.ModuleType("edge_tts")
    calls = []
    class FakeCommunicate:
        def __init__(self, text, voice, **k):
            self.text = text
            calls.append(text)
        async def stream(self):
            clip = tmp_path / f"gen_{abs(hash(self.text))}.mp3"
            subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "0.4", "-q:a", "9", str(clip)], check=True, capture_output=True)
            yield {"type": "audio", "data": clip.read_bytes()}
            yield {"type": "WordBoundary", "text": self.text, "offset": 0, "duration": 4_000_000}
    fake_edge_tts.Communicate = FakeCommunicate
    sys.modules["edge_tts"] = fake_edge_tts
    try:
        phrases = [
            PhraseSpec(role="INVESTIGATION", text="결국 조사팀은", boundary=CONTINUE),
            PhraseSpec(role="INVESTIGATION", text="물탱크에 넣었습니다", boundary=STRONG_BOUNDARY),
        ]
        asyncio.run(synthesize_plan(phrases, tmp_path / "out.mp3", tmp_path / "out.json"))
    finally:
        del sys.modules["edge_tts"]
    assert len(calls) == 1, f"continuation phrases must merge into one synthesis call, got {calls}"
    assert "결국 조사팀은" in calls[0] and "물탱크에 넣었습니다" in calls[0]

@requires_ffmpeg
def test_synthesize_plan_fails_closed_per_unit(tmp_path):
    fake_edge_tts = types.ModuleType("edge_tts")
    class FakeCommunicate:
        def __init__(self, text, voice, **k): pass
        async def stream(self):
            return
            yield {}  # pragma: no cover
    fake_edge_tts.Communicate = FakeCommunicate
    sys.modules["edge_tts"] = fake_edge_tts
    try:
        phrases = [PhraseSpec(role="HOOK", text="비행기가 부서졌습니다", boundary=STRONG_BOUNDARY)]
        with pytest.raises(RuntimeError):
            asyncio.run(synthesize_plan(phrases, tmp_path / "out.mp3", tmp_path / "out.json"))
    finally:
        del sys.modules["edge_tts"]

@requires_ffmpeg
def test_synthesize_plan_spells_numbers_before_synthesis(tmp_path):
    fake_edge_tts = types.ModuleType("edge_tts")
    seen_text = {}
    class FakeCommunicate:
        def __init__(self, text, voice, **k):
            seen_text["text"] = text
        async def stream(self):
            clip = tmp_path / "gen.mp3"
            subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "0.3", "-q:a", "9", str(clip)], check=True, capture_output=True)
            yield {"type": "audio", "data": clip.read_bytes()}
            yield {"type": "WordBoundary", "text": seen_text["text"], "offset": 0, "duration": 3_000_000}
    fake_edge_tts.Communicate = FakeCommunicate
    sys.modules["edge_tts"] = fake_edge_tts
    try:
        phrases = [PhraseSpec(role="REVEAL", text="물탱크에서 1,830회를 추가로 반복하자 찢어졌습니다", boundary=STRONG_BOUNDARY, focus=True)]
        asyncio.run(synthesize_plan(phrases, tmp_path / "out.mp3", tmp_path / "out.json"))
    finally:
        del sys.modules["edge_tts"]
    assert "1,830" not in seen_text["text"]
    assert "천팔백삼십" in seen_text["text"]
