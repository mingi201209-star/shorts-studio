"""Idea Gate: evaluate a Shorts topic BEFORE anyone writes a script or sources
a single image for it.

The engine used to be "turn whatever topic you hand it into a video." That
let weak material into production, where the only thing that can catch it is
an expensive full render plus manual review. This module moves the judgment
earlier: score real production feasibility from a structured pitch, and
fail-close on any single fatal defect rather than averaging scores that let
a weak topic limp past on partial credit.

Deliberately NOT a weighted sum: `evaluate_idea` returns FAIL the moment any
one critical dimension fails, exactly per the brief ("단순 점수 합산으로
약한 소재를 억지 PASS시키지 마라"). A pitch with a brilliant hook and no real
visual evidence is still a FAIL -- there is no dimension strong enough to
buy back a fatal one.
"""
from __future__ import annotations
import math
from pydantic import BaseModel, Field

from .retention_rules import hook_violation, is_generic_establishing_text, is_near_duplicate_text
from .final_video_qa import GLOBAL_MAX_SOURCE_FAMILY_RATIO

# Mirrors verify_source_budget's pre-render gate (final_video_qa.py) so an
# idea that could never satisfy the existing source-diversity QA is caught
# here, before any sourcing work is done for it.
MIN_UNIQUE_SOURCE_RATIO = 0.35


def required_unique_sources(estimated_beats_needed: int,
                             max_family_ratio: float = GLOBAL_MAX_SOURCE_FAMILY_RATIO,
                             min_unique_ratio: float = MIN_UNIQUE_SOURCE_RATIO) -> int:
    """How many genuinely distinct real sources a pitch needs to have any
    chance of satisfying the production source-diversity QA once it becomes
    a real manifest with `estimated_beats_needed` visual beats."""
    from_ratio_cap = math.ceil(1.0 / max_family_ratio) if max_family_ratio > 0 else 1
    from_unique_floor = math.ceil(estimated_beats_needed * min_unique_ratio)
    return max(1, from_ratio_cap, from_unique_floor)


class IdeaPitch(BaseModel):
    """A structured topic pitch -- the unit the Idea Gate judges. Written
    before any source is fetched or any narration is drafted."""
    topic_id: str
    domain: str  # e.g. science | city | daily-design | tech | nature | disaster | history
    hook_sentence: str = Field(min_length=1)
    first_second_visual: str = Field(min_length=1, description="what the very first second of screen shows -- an event/result, not scene-setting")
    familiar_subject: str = Field(min_length=1)
    unexpected_fact: str = Field(min_length=1)
    conflict_or_problem: str = Field(min_length=1)
    mid_change: str = Field(min_length=1, description="what actually changes partway through, not a restatement of the problem")
    ending_payoff: str = Field(min_length=1, description="a new result / reversal / unexpected follow-on / strong conclusion -- not a summary")
    visual_evidence: list[str] = Field(default_factory=list, description="short descriptions of real, independently verifiable photos/documents/diagrams available for this topic")
    estimated_beats_needed: int = Field(default=16, ge=1, description="rough visual-beat count to fill ~40-60s at the engine's real beat cadence")
    notes: str = ""


class IdeaGateResult(BaseModel):
    topic_id: str
    status: str  # PASS | FAIL
    critical_failures: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    evidence: dict = Field(default_factory=dict)


def _dedupe_visual_evidence(items: list[str]) -> list[str]:
    """Collapse near-duplicate descriptions (e.g. two phrasings of the same
    single photo) into one representative each -- mirrors
    final_video_qa._same_source_family's spirit at the pitch stage, where
    there's no real file to hash yet, only the author's own description."""
    reps: list[str] = []
    for item in items:
        if not item or not item.strip():
            continue
        if not any(is_near_duplicate_text(item, rep) for rep in reps):
            reps.append(item)
    return reps


def evaluate_idea(pitch: IdeaPitch,
                   max_family_ratio: float = GLOBAL_MAX_SOURCE_FAMILY_RATIO,
                   min_unique_ratio: float = MIN_UNIQUE_SOURCE_RATIO) -> IdeaGateResult:
    failures: list[str] = []
    warnings: list[str] = []

    # 1. Hook: one sentence must create immediate curiosity -- reject the
    # same banned openers the real First-Second Hook Contract rejects.
    reason = hook_violation(pitch.hook_sentence)
    if reason:
        failures.append(f"강한 hook을 만들 수 없음: hook_sentence이 '{reason}' 패턴과 일치함 ({pitch.hook_sentence!r})")
    elif is_near_duplicate_text(pitch.hook_sentence, pitch.familiar_subject):
        failures.append("강한 hook을 만들 수 없음: hook_sentence이 familiar_subject를 이름만 반복함 (사건/결과가 없음)")

    # 2. First second must show an event/result, not scene-setting.
    if is_generic_establishing_text(pitch.first_second_visual):
        failures.append(f"첫 1초에 사건/결과를 보여줄 수 없음: '{pitch.first_second_visual}'는 의미 없는 establishing shot 서술임")
    elif is_near_duplicate_text(pitch.first_second_visual, pitch.familiar_subject):
        failures.append("첫 1초에 사건/결과를 보여줄 수 없음: first_second_visual이 familiar_subject를 그대로 반복함")

    # 3. Familiar subject + unexpected fact must genuinely contrast.
    if is_near_duplicate_text(pitch.familiar_subject, pitch.unexpected_fact):
        failures.append("익숙한 대상 + 예상 밖 사실 구조 없음: unexpected_fact가 familiar_subject와 실질적으로 동일함")

    # 4. Real conflict/problem/reversal, not a restatement of the hook.
    if is_near_duplicate_text(pitch.conflict_or_problem, pitch.hook_sentence):
        failures.append("명확한 갈등/문제/역전 없음: conflict_or_problem이 hook_sentence를 반복할 뿐임")

    # 5. A real mid-point state change, not a restatement of the conflict.
    if is_near_duplicate_text(pitch.mid_change, pitch.conflict_or_problem):
        failures.append("중간 상황 변화 없음: mid_change가 conflict_or_problem을 반복할 뿐, 실제 상태 변화가 아님")

    # 6. Ending payoff must be a genuine new result, not a rehash of the
    # hook or the conflict -- "결말 payoff 없음" fails closed here.
    if is_near_duplicate_text(pitch.ending_payoff, pitch.hook_sentence) or \
       is_near_duplicate_text(pitch.ending_payoff, pitch.conflict_or_problem):
        failures.append(f"결말 payoff 없음: ending_payoff가 hook/conflict를 반복할 뿐 새로운 결과/반전이 아님 ({pitch.ending_payoff!r})")

    # 7 & 8. Real, distinct visual evidence sufficient to fill the runtime
    # without forced repeats -- "같은 이미지 반복 없이는 영상을 채울 수 없음"
    # fails closed here, using the exact math the real source-budget gate
    # (final_video_qa.verify_source_budget) will apply once this becomes a
    # manifest.
    unique_evidence = _dedupe_visual_evidence(pitch.visual_evidence)
    required = required_unique_sources(pitch.estimated_beats_needed, max_family_ratio, min_unique_ratio)
    if len(unique_evidence) < required:
        failures.append(
            f"같은 이미지 반복 없이는 영상을 채울 수 없음 / 실제 visual evidence 부족: "
            f"고유 소스 {len(unique_evidence)}개 < 필요 {required}개 "
            f"(estimated_beats_needed={pitch.estimated_beats_needed}, "
            f"max_family_ratio={max_family_ratio:.0%}, min_unique_ratio={min_unique_ratio:.0%})"
        )
    elif len(unique_evidence) < required + 2:
        warnings.append(f"고유 소스가 필요치({required}개)를 겨우 넘김 ({len(unique_evidence)}개) -- 여유가 거의 없음")

    if len(unique_evidence) < len(pitch.visual_evidence):
        warnings.append(f"visual_evidence 중 {len(pitch.visual_evidence)-len(unique_evidence)}건이 서로 근접 중복으로 판단되어 하나로 합산됨")

    evidence = {
        "unique_visual_evidence_count": len(unique_evidence),
        "unique_visual_evidence": unique_evidence,
        "required_unique_sources": required,
        "estimated_beats_needed": pitch.estimated_beats_needed,
    }
    status = "FAIL" if failures else "PASS"
    return IdeaGateResult(topic_id=pitch.topic_id, status=status, critical_failures=failures, warnings=warnings, evidence=evidence)
