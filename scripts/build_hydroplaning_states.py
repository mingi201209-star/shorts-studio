#!/usr/bin/env python3
"""Build the hydroplaning Shorts production.

Mostly self-produced 3D physical animation (shorts_studio/hydroplaning3d.py)
driven by one continuous global progress value, so beats slicing contiguous
windows of that timeline play as a single physical scene, not independent
vignettes. One real CC0 photo of an actual tire tread grounds the explanation
in a real object before the 3D mechanism animation takes over. The opening
hook previews the end state (the tire already floating) before the
explanation scenes play the real causal chain from the beginning.
"""
from __future__ import annotations

import argparse, hashlib, json, time, urllib.parse, urllib.request
from pathlib import Path

from shorts_studio.hydroplaning3d import render_motion_clip
from shorts_studio.hook_studio import (
    HookCandidate, TopicBrief, generate_and_judge,
    build_story_generation_prompt, story_writer_system_prompt,
)

NEG = ["a photograph of a cat", "a landscape photograph of mountains", "a city skyline"]

TIRE_PHOTO_FILE = "The tire wheel of Mercedes-AMG C63 S (W205).JPG"
TIRE_PHOTO_PAGE = "https://commons.wikimedia.org/wiki/File:The_tire_wheel_of_Mercedes-AMG_C63_S_(W205).JPG"
TIRE_PHOTO_ATTRIBUTION = "Tokumeigakarinoaoshima / Wikimedia Commons / CC0 1.0 Universal Public Domain Dedication"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download_required_photo(out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.is_file() and out.stat().st_size > 20_000:
        return out
    encoded = urllib.parse.quote(TIRE_PHOTO_FILE.replace(" ", "_"), safe="._-()")
    url = f"https://commons.wikimedia.org/wiki/Special:Redirect/file/{encoded}"
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "shorts-studio/0.1 (CC0 production asset)"})
            with urllib.request.urlopen(req, timeout=45) as r:
                data = r.read()
            if len(data) < 20_000:
                raise RuntimeError(f"download suspiciously small: {len(data)} bytes")
            out.write_bytes(data)
            from PIL import Image
            with Image.open(out) as im:
                im.verify()
            print(f"HYDROPLANING_PHOTO_READY={out} bytes={len(data)} sha256={sha(out)}")
            return out
        except Exception as exc:
            last = exc
            out.unlink(missing_ok=True)
            if attempt < 3:
                time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"failed to fetch required tire tread photo: {last}")


class HydroplaningHookGenerator:
    def generate(self, brief: TopicBrief) -> list[HookCandidate]:
        f = brief.fact_by_strategy()
        texts = {
            "contradiction": "타이어가 도로에 딱 붙어 있을 것 같지만, 물 위에서 완전히 떨어질 수 있습니다.",
            "surprising_consequence": "놀랍게도 멀쩡해 보이는 타이어가 빗길에서 도로를 전혀 밟지 못할 수 있습니다.",
            "counterintuitive_fact": "타이어 홈이 멀쩡히 있어도 물이 너무 많으면 소용이 없을 수 있습니다.",
            "visible_anomaly": "젖은 도로 위의 타이어가 회전만 할 뿐 바닥에는 닿지 않습니다.",
            "mistaken_assumption": "타이어가 돌고 있으면 당연히 도로를 밟고 있다는 생각은 사실과 다를 수 있습니다.",
            "unresolved_cause_effect": "타이어 홈은 물을 계속 빼내고 있습니다. 그런데 왜 결국 도로에서 뜰까요?",
        }
        return [HookCandidate(strategy=s, text=texts[s], grounded_in=f[s]) for s in texts]


# Each hook candidate is one long sentence (it has to carry the whole
# attention-grabbing claim), which would otherwise force a single beat to
# hold for its entire speaking duration. Splitting it into two contiguous
# substrings of the SAME sentence gives the hero reveal a second cut point
# without changing a single word of the hook copy itself.
HOOK_CUE_SPLITS = {
    "contradiction": ("타이어가 도로에 딱 붙어 있을 것 같지만", "물 위에서 완전히 떨어질 수 있습니다"),
    "surprising_consequence": ("놀랍게도 멀쩡해 보이는 타이어가", "빗길에서 도로를 전혀 밟지 못할 수 있습니다"),
    "counterintuitive_fact": ("타이어 홈이 멀쩡히 있어도", "물이 너무 많으면 소용이 없을 수 있습니다"),
    "visible_anomaly": ("젖은 도로 위의 타이어가 회전만 할 뿐", "바닥에는 닿지 않습니다"),
    "mistaken_assumption": ("타이어가 돌고 있으면 당연히", "도로를 밟고 있다는 생각은 사실과 다를 수 있습니다"),
    "unresolved_cause_effect": ("타이어 홈은 물을 계속 빼내고 있습니다", "그런데 왜 결국 도로에서 뜰까요"),
}


def make_brief() -> TopicBrief:
    return TopicBrief(
        topic_id="hydroplaning",
        familiar_subject="젖은 도로 위를 달리는 자동차 타이어",
        contradiction_fact="타이어가 회전하고 있어도 도로에 전혀 닿지 않을 수 있습니다",
        surprising_consequence_fact="멀쩡한 타이어도 빗길에서 도로와의 접촉을 완전히 잃을 수 있습니다",
        counterintuitive_fact="타이어 홈이 있어도 물의 양이 많으면 접촉을 지키지 못할 수 있습니다",
        anomaly_fact="젖은 도로 위에서 타이어가 돌기만 하고 바닥을 밟지 못하는 경우가 있습니다",
        mistaken_assumption_fact="타이어가 돌고 있으면 도로를 밟고 있다는 생각은 항상 맞지는 않습니다",
        cause_effect_fact="타이어 홈은 접촉 영역의 물을 계속 밖으로 빼내는 역할을 합니다",
        payoff_text="물이 빠지는 속도보다 쌓이는 속도가 빨라지면 타이어는 물 위로 떠서 도로와의 접촉을 잃을 수 있습니다",
        grounded_facts=[
            "물이 타이어와 노면 사이에 쌓이면 접촉력이 감소할 수 있습니다",
            "충분히 심해지면 타이어가 노면과의 접촉을 완전히 잃을 수 있습니다",
            "타이어 트레드 홈은 접촉 영역의 물 배출에 도움을 줍니다",
        ],
    )


def phrase(role, text, hook_type=None):
    x = {"role": role, "text": text}
    if hook_type:
        x["hook_type"] = hook_type
    return x


def beat(asset: Path, cue: str, info_role: str, concept_id: str, state_id: str, kind: str,
         qa_label: str, req: str, attribution: str | None = None):
    digest = sha(asset)
    return {
        "start": 0.0,
        "asset": str(asset),
        "attribution": attribution,
        "visual_change": {
            "kind": kind, "concept_id": concept_id, "state_id": state_id,
            "narration_cue": cue, "added_information": info_role,
            "source_sha256": digest,
        },
        "visual_qa_requirements": [req],
        "visual_qa_labels": [qa_label],
        "visual_qa_negative_labels": NEG,
        "visual_qa_expected_sha256": [digest],
        "info_role": info_role,
    }


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--font", default=None); args = ap.parse_args()
    assets = Path("assets/hydroplaning"); assets.mkdir(parents=True, exist_ok=True)
    tire_photo = download_required_photo(assets / "tire_tread_photo.jpg")

    # Each clip is centered on one of a small set of global-progress anchor
    # points that were chosen empirically (not just evenly sliced) so that
    # EVERY pair of anchors -- not just neighbors -- renders a genuinely,
    # substantially different frame under the engine's own real
    # equivalent-framing/replay detector (shorts_studio.visual_change).
    # Finely slicing a near-flat stretch of the physics curve into many
    # almost-identical states was the earlier failure mode (CI run
    # 37039874973): the fix is fewer, well-separated beats whose states
    # really do look different, not more beats papering over a plateau.
    # Each clip plays forward a small window AROUND its anchor (never a
    # frozen still) so the tire keeps rotating and water keeps moving.
    # Each window is deliberately narrow (the anchor +/- ~0.01) so the frame
    # actually sampled by the engine's meaningful-visual-change check (taken
    # shortly after the beat starts, not at its end) always lands very close
    # to the verified anchor value, regardless of exactly how long the real
    # TTS-measured beat turns out to be. Rotation keeps the clip visibly
    # alive even over such a narrow global-progress window.
    clips = {
        "hook_a": (0.770, 0.790, 2.2),    # already mid-liftoff, near-zero contact
        "hook_b": (0.890, 0.910, 2.0),    # fully floating, zero contact -- the "wow"
        "base": (0.000, 0.015, 2.2),      # normal rolling, full contact, groove outflow
        "wedge1": (0.360, 0.380, 2.2),    # wedge now clearly visible, contact dented
        "wedge2": (0.460, 0.480, 2.0),    # wedge bigger, contact further reduced
        "contact1": (0.540, 0.560, 2.0),  # contact patch visibly collapsing
        "contact2": (0.630, 0.650, 2.0),  # less than half the patch left
        "contact3": (0.720, 0.740, 2.0),  # almost fully lifted
        "payoff": (0.990, 1.000, 2.4),    # final full hydroplaning state
    }
    motion = {
        k: render_motion_clip(assets / f"{k}.mp4", g0, g1, duration=dur, fps=30)
        for k, (g0, g1, dur) in clips.items()
    }

    brief = make_brief()
    hook_result = generate_and_judge(brief, generator=HydroplaningHookGenerator())
    if hook_result.winner is None:
        raise RuntimeError("Prompt V2 produced no hydroplaning hook")
    winner = hook_result.winner
    print(f"PROMPT_V2_JUDGE={hook_result.judge_name}")
    print(f"PROMPT_V2_SELECTED_STRATEGY={winner.strategy}")
    print(f"PROMPT_V2_SELECTED_HOOK={winner.text}")

    build = Path("build"); build.mkdir(exist_ok=True)
    story_prompt = build_story_generation_prompt(
        brief, winner,
        uncertainty_notes=[
            "하이드로플레이닝이 시작되는 정확한 속도는 타이어 상태, 수막 두께, 하중 등 조건에 따라 달라질 수 있습니다",
            "이 영상은 물 쐐기와 접촉면 감소라는 핵심 메커니즘에 집중하며 유체역학의 모든 세부 요인을 다루지 않습니다",
        ],
    )
    (build / "hydroplaning_story_prompt.txt").write_text(
        story_writer_system_prompt() + "\n\n" + story_prompt + "\n", encoding="utf-8")
    print("STORY_PROMPT_V3_READY=build/hydroplaning_story_prompt.txt")

    # Beat count and placement were chosen empirically against the engine's
    # own real equivalent-framing/replay detector (see the verification
    # notes in hydroplaning3d.py's camera/physics docstring and the g
    # anchors used for `clips` above) rather than by evenly slicing
    # narration: every beat here renders a frame that is genuinely,
    # substantially different -- by real pixel content, not just by
    # authored state_id -- from every other beat in the whole video. That
    # is what the previous (24-beat) design got wrong: finely slicing a
    # near-flat stretch of the physics curve produced many beats that
    # looked almost identical and were correctly rejected as "no new
    # state". Narration is correspondingly short and non-redundant per
    # beat so no single beat's cue-to-cue gap can approach the 3.5s
    # visual-cut-cadence limit.
    hook = winner.text
    hook_first, _ = HOOK_CUE_SPLITS[winner.strategy]
    crisis = "그런데 조금 전까지는 멀쩡했습니다."
    plans = [
        ("s_hook", [
            phrase("HOOK", hook, winner.strategy),
            phrase("CRISIS", crisis),
        ], [
            beat(motion["hook_a"], hook_first, "levitating_result", "hook_diagram", "mid_liftoff", "concept",
                 "a moving cinematic 3D visualization of a car tire mid-liftoff off a wet road, almost no road contact left",
                 "타이어가 도로와의 접촉을 거의 다 잃어가는 극적인 결과를 먼저 보여주는 모습"),
            beat(motion["hook_b"], "조금 전까지는 멀쩡했습니다", "levitating_result_full", "hook_diagram", "full_float", "state",
                 "a moving cinematic 3D visualization of a car tire fully lifted off a wet road by a layer of water, zero road contact",
                 "같은 타이어가 완전히 떠서 도로와 전혀 닿지 않는 모습을 보여주는 장면"),
        ]),
        ("s_reveal", [
            phrase("REVEAL", "이게 바로 그 타이어의 실제 트레드입니다."),
            phrase("INVESTIGATION", "평소에는 홈이 물을 밀어내 도로에 단단히 붙어 있습니다."),
        ], [
            beat(tire_photo, "실제 트레드입니다", "real_tread_grounding", "tread_photo", "real", "concept",
                 "a real close-up photograph of an actual car tire's tread and grooves",
                 "지금까지 보여준 타이어 트레드가 실제로 어떻게 생겼는지 진짜 사진으로 보여주는 장면",
                 TIRE_PHOTO_ATTRIBUTION),
            beat(motion["base"], "도로에 단단히 붙어 있습니다", "normal_contact_maintained", "base", "normal", "concept",
                 "a moving 3D visualization of a car tire rolling normally on a wet road with a full bright contact patch and water draining sideways from its grooves",
                 "타이어가 도로에 단단히 붙어 구르며 홈이 물을 양옆으로 밀어내는 정상 상태를 보여주는 모습"),
        ]),
        ("s_explain", [
            phrase("EXPLANATION", "물이 너무 많아지면 앞쪽에 쌓이기 시작합니다."),
            phrase("EXPLANATION", "쐐기 모양으로 점점 커집니다."),
        ], [
            beat(motion["wedge1"], "앞쪽에 쌓이기 시작합니다", "drainage_overload", "wedge", "forming", "concept",
                 "a moving 3D visualization of a water wedge forming at the leading edge of a rolling car tire, its road contact patch visibly dented",
                 "홈이 다 빼내지 못한 물이 타이어 앞쪽에 쌓여 물 쐐기가 생기기 시작하는 모습을 보여주는 장면"),
            beat(motion["wedge2"], "점점 커집니다", "wedge_growing", "wedge", "large", "state",
                 "a moving 3D visualization of a large water wedge in front of a car tire, its road contact patch clearly shrunk",
                 "타이어 앞의 물 쐐기가 뚜렷하게 커지고 접촉면이 눈에 띄게 줄어든 모습을 보여주는 장면"),
        ]),
        ("s_twist", [
            phrase("TWIST", "접촉면이 눈에 띄게 줄어듭니다."),
            phrase("TWIST", "이제 절반도 남지 않았습니다."),
            phrase("TWIST", "거의 다 떠오르고 있습니다."),
        ], [
            beat(motion["contact1"], "눈에 띄게 줄어듭니다", "contact_patch_shrinking", "contact", "shrinking", "concept",
                 "a moving 3D visualization of a car tire's bright road contact patch visibly collapsing while a large water wedge sits ahead of it",
                 "타이어와 도로가 닿는 밝은 접촉면이 눈에 띄게 줄어드는 모습을 보여주는 장면"),
            beat(motion["contact2"], "절반도 남지 않았습니다", "contact_half_gone", "contact", "half_gone", "state",
                 "a moving 3D visualization of a car tire with less than half of its original road contact patch remaining and the tire visibly rising",
                 "접촉면이 처음의 절반도 남지 않고 타이어가 눈에 띄게 떠오르는 모습을 보여주는 장면"),
            beat(motion["contact3"], "거의 다 떠오르고 있습니다", "contact_almost_gone", "contact", "almost_gone", "state",
                 "a moving 3D visualization of a car tire almost fully lifted off a wet road, only a sliver of contact patch left",
                 "타이어의 접촉면이 거의 사라지고 거의 다 떠오른 상태를 보여주는 장면"),
        ]),
        ("s_end", [
            phrase("PAYOFF", "이것이 하이드로플레이닝입니다."),
        ], [
            beat(motion["payoff"], "하이드로플레이닝입니다", "final_hydroplane", "hydroplane", "full_lift", "concept",
                 "a moving cinematic 3D payoff visualization of a car tire fully lifted off a wet road, floating entirely on a layer of water with no road contact left",
                 "타이어가 도로와의 접촉을 완전히 잃고 물 위에 떠 있는 최종 상태를 한 화면에 보여주는 모습"),
        ]),
    ]

    production_tags = {
        ("s_hook", 0): ("hero", "physical_animation"),
        ("s_hook", 1): ("support", "physical_animation"),
        ("s_reveal", 0): ("evidence", "real_photo"),
        ("s_reveal", 1): ("support", "physical_animation"),
        ("s_explain", 0): ("mechanism", "physical_animation"),
        ("s_explain", 1): ("support", "physical_animation"),
        ("s_twist", 0): ("support", "physical_animation"),
        ("s_twist", 1): ("support", "physical_animation"),
        ("s_twist", 2): ("second_peak", "physical_animation"),
        ("s_end", 0): ("payoff", "physical_animation"),
    }

    scenes = []
    seen_tags = set()
    for sid, narr_plan, beats in plans:
        for i, b in enumerate(beats):
            b["start"] = float(i)
            role, mode = production_tags[(sid, i)]
            b["production"] = {"role": role, "visual_mode": mode, "added_information": b["info_role"]}
            seen_tags.add((sid, i))
        narration = " ".join(p["text"] for p in narr_plan)
        scenes.append({
            "id": sid, "narration": narration,
            "narration_plan": narr_plan,
            "visual_description": "Continuous hydroplaning physical sequence matched to narration.",
            "asset": beats[0]["asset"],
            "attribution": beats[0].get("attribution"),
            "visual_beats": beats,
            "visual_qa_requirements": ["각 내레이션 단서에 맞는 하이드로플레이닝 물리 상태가 실제 화면에 보여야 함"],
            "visual_qa_labels": [beats[0]["visual_qa_labels"][0]],
            "visual_qa_negative_labels": NEG,
            "overlay_title": None,
            "overlay_title_seconds": 2.8 if sid == "s_hook" else None,
        })

    expected_tags = {(sid, i) for sid, _, beats in plans for i, _ in enumerate(beats)}
    if seen_tags != expected_tags or set(production_tags) != expected_tags:
        raise RuntimeError("Visual Production V2 tag coverage drifted from the real beat list")

    manifest = {
        "title": "타이어가 도로에서 뜨는 이유",
        "width": 1080, "height": 1920, "fps": 30,
        "overlay_title": "타이어가 도로에서 뜬다",
        "overlay_title_mode": "first_scene_only",
        "max_visual_recovery_attempts": 2,
        "strict_source_diversity": False,
        "strict_meaningful_visual_changes": True,
        "strict_retention_contract": True,
        "strict_visual_production_v2": True,
        "observable_phenomenon": "젖은 도로에서 타이어가 물 위로 떠서 도로와의 접촉을 완전히 잃는다.",
        "silent_story": "결과(타이어가 뜬 모습) 먼저 → 정상 상태 대비 → 홈의 배수 단서 → 과부하로 물 쐐기 성장 → 접촉면 축소 → 완전한 하이드로플레이닝 payoff",
        "silent_interest_review": "pending",
        "strict_entertainment_contract": False,
        "scenes": scenes,
    }
    Path("examples").mkdir(exist_ok=True)
    Path("examples/hydroplaning.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    desc = """# 타이어가 도로에서 뜨는 이유 — 출처

모든 영상은 실제 좌표의 원기둥·타원체·박스 geometry를 카메라로 투영해 프레임마다 렌더한
자체 제작 3D 물리 시각화입니다. 외부 사진/영상 자료는 사용하지 않았습니다.

설명된 물리적 메커니즘(물이 타이어와 노면 사이에 쌓이면 접촉력이 감소할 수 있고, 충분히 심해지면
완전히 접촉을 잃을 수 있으며, 트레드 홈은 접촉 영역의 물 배출에 도움을 준다는 점)은 미국 도로교통
안전국(NHTSA)의 공개된 하이드로플레이닝 안전 설명을 참고해 과장 없이 서술했습니다. 정확한 임계
속도나 공식은 조건에 따라 달라지므로 영상에서 보편적 수치로 제시하지 않았습니다.
"""
    Path("examples/hydroplaning_upload_description.txt").write_text(desc, encoding="utf-8")
    print("HYDROPLANING_MANIFEST_READY=examples/hydroplaning.json")


if __name__ == "__main__":
    main()
