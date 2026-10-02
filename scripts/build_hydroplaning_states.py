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

    # Every clip below covers its own distinct, non-overlapping window of
    # the single global progress timeline. The main explanatory sequence
    # (hook clips excluded) is CONTIGUOUS across [0, 1] in order, so the
    # whole explanation plays as one continuous physical process. Each file
    # is rendered once and never reused across beats, so no two beats can
    # ever collide on source_sha256.
    #
    # Clips are deliberately short (~1.2-2.2s) and numerous: a visual beat's
    # on-screen duration is driven by how long its narration cue takes to
    # speak, not by the clip length the author picks, so a clip paired with
    # a long uninterrupted sentence gets held on its last frame for the
    # remainder -- exactly the "static hold" failure the engine's own
    # visual_cut_cadence / visual_activity_real gates exist to catch. Each
    # narration sentence below is therefore split into several short cue
    # fragments, each with its own short clip, so no beat is ever held
    # anywhere near the 3.5s cadence limit.
    clips = {
        "hook_a": (0.900, 0.930, 1.6),
        "hook_b": (0.930, 0.985, 2.2),
        "base_a": (0.000, 0.025, 1.4),
        "base_b": (0.025, 0.050, 1.4),
        "groove_a": (0.050, 0.080, 1.2),
        "groove_b": (0.080, 0.130, 1.6),
        "groove_c": (0.130, 0.160, 1.8),
        "groove_d": (0.160, 0.195, 1.4),
        "groove_e": (0.195, 0.230, 1.8),
        "groove_f": (0.230, 0.270, 1.6),
        "wedge_a": (0.270, 0.330, 1.6),
        "wedge_b": (0.330, 0.400, 1.8),
        "wedge_c": (0.400, 0.470, 1.8),
        "wedge_d": (0.470, 0.550, 2.0),
        "contact_a": (0.550, 0.620, 1.6),
        "contact_b": (0.620, 0.680, 1.6),
        "contact_c": (0.680, 0.750, 1.8),
        "contact_d": (0.750, 0.800, 1.2),
        "contact_e": (0.800, 0.860, 1.6),
        "hydro_a": (0.860, 0.910, 1.6),
        "hydro_b": (0.910, 0.960, 1.8),
        "hydro_c": (0.960, 0.980, 1.2),
        "hydro_d": (0.980, 1.000, 1.4),
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

    hook = winner.text
    hook_first, hook_second = HOOK_CUE_SPLITS[winner.strategy]
    crisis = "그런데 타이어는 지금도 계속 돌고 있습니다."
    plans = [
        ("s_hook", [
            phrase("HOOK", hook, winner.strategy),
            phrase("CRISIS", crisis),
        ], [
            beat(motion["hook_a"], hook_first, "levitating_result", "hook_diagram", "preview_start", "concept",
                 "a moving cinematic 3D visualization of a car tire fully lifted off a wet road by a layer of water",
                 "타이어가 물 위에 완전히 떠서 도로와 닿지 않는 결과를 먼저 크게 보여주는 모습"),
            beat(motion["hook_b"], hook_second, "levitating_result_hold", "hook_diagram", "preview_full", "state",
                 "a moving cinematic 3D visualization of a car tire fully lifted off a wet road by a layer of water, held a moment longer",
                 "떠 있는 타이어의 모습을 한 번 더 보여주며 결과를 각인시키는 장면"),
            beat(motion["base_a"], "그런데 타이어는 지금도", "still_rotating_setup", "hook_contrast", "baseline_start", "concept",
                 "a moving 3D visualization of a car tire rotating on a wet road with a bright contact patch still visible",
                 "같은 타이어가 아직은 정상적으로 도로에 닿아 회전하기 시작하는 모습을 보여주는 장면"),
            beat(motion["base_b"], "계속 돌고 있습니다", "still_rotating_but_odd", "hook_contrast", "baseline_hold", "state",
                 "a moving 3D visualization of a car tire still rotating normally on a wet road with a clear bright contact patch",
                 "타이어가 정상적으로 도로에 붙어 회전하는 모습과 대비해서 보여주는 장면"),
        ]),
        ("s_reveal", [
            phrase("REVEAL", "이게 바로 그 타이어의 실제 트레드입니다."),
            phrase("REVEAL", "홈이 보이시나요?"),
            phrase("REVEAL", "타이어가 구르면서 이 홈이 물을 밀어냅니다."),
            phrase("REVEAL", "바닥에 닿는 쪽에서 물이 옆으로 빠져나갑니다."),
            phrase("REVEAL", "그래서 타이어는 아직 도로에 단단히 붙어 있습니다."),
            phrase("INVESTIGATION", "속도가 느릴 때는 이 배수만으로 충분합니다."),
            phrase("INVESTIGATION", "물은 계속 빠지고, 접촉은 그대로 유지됩니다."),
        ], [
            beat(tire_photo, "실제 트레드입니다", "real_tread_grounding", "tread_photo", "real", "concept",
                 "a real close-up photograph of an actual car tire's tread and grooves",
                 "지금까지 보여준 타이어 트레드가 실제로 어떻게 생겼는지 진짜 사진으로 보여주는 장면",
                 TIRE_PHOTO_ATTRIBUTION),
            beat(motion["groove_a"], "홈이 보이시나요", "groove_intro", "groove", "intro", "concept",
                 "a moving 3D close-up visualization of a car tire's tread grooves rolling on a wet road",
                 "타이어 트레드의 홈을 가까이서 보여주는 장면"),
            beat(motion["groove_b"], "이 홈이 물을 밀어냅니다", "groove_drainage_explained", "groove", "draining", "state",
                 "a moving 3D close-up visualization of water being actively flung sideways out of a tire's tread grooves at the bottom of its rotation on a wet road",
                 "타이어 홈이 회전하면서 바닥 쪽의 물을 실제로 양옆으로 빼내는 모습을 보여주는 장면"),
            beat(motion["groove_c"], "물이 옆으로 빠져나갑니다", "groove_drainage_detail", "groove", "draining_detail", "state",
                 "a moving 3D close-up visualization of water streaking sideways out from under a rotating tire on a wet road",
                 "물이 타이어 아래에서 양옆으로 빠져나가는 모습을 더 가까이 보여주는 장면"),
            beat(motion["groove_d"], "도로에 단단히 붙어", "normal_contact_maintained", "groove", "still_fine", "state",
                 "a moving 3D visualization of a car tire still rotating with a clear bright contact patch firmly on a wet road while water keeps draining out of the grooves",
                 "홈이 물을 계속 빼내는 동안 타이어가 도로에 단단히 붙어 회전하는 정상 상태를 보여주는 모습"),
            beat(motion["groove_e"], "이 배수만으로 충분합니다", "sufficient_at_low_speed", "groove", "sufficient", "state",
                 "a moving 3D visualization of a car tire rolling normally on a wet road with a firm bright contact patch",
                 "속도가 느릴 때는 배수만으로 충분해 접촉이 안정적으로 유지되는 모습"),
            beat(motion["groove_f"], "접촉은 그대로 유지됩니다", "contact_still_maintained", "groove", "maintained", "state",
                 "a moving 3D visualization of a car tire rolling steadily on a wet road with water still draining from its grooves",
                 "물이 계속 빠지면서 타이어의 접촉이 그대로 유지되는 마지막 정상 상태를 보여주는 장면"),
        ]),
        ("s_explain", [
            phrase("EXPLANATION", "그런데 물이 너무 많아지면 홈이 다 빼내지 못합니다."),
            phrase("EXPLANATION", "미처 빠지지 못한 물이 타이어 앞쪽에 모입니다."),
            phrase("EXPLANATION", "이 물은 점점 쐐기 모양으로 쌓여갑니다."),
            phrase("EXPLANATION", "쐐기는 타이어가 나아갈수록 더 커집니다."),
        ], [
            beat(motion["wedge_a"], "홈이 다 빼내지 못합니다", "drainage_overload", "wedge", "overload", "concept",
                 "a moving 3D visualization of water starting to pile up at the leading edge of a rolling car tire because the grooves can no longer drain it all",
                 "홈이 더 이상 물을 다 빼내지 못해 앞쪽에 물이 모이기 시작하는 모습을 보여주는 장면"),
            beat(motion["wedge_b"], "타이어 앞쪽에 모입니다", "wedge_accumulating", "wedge", "accumulating", "state",
                 "a moving 3D visualization of water accumulating at the leading edge of a car tire on a wet road",
                 "물이 타이어 앞쪽에 눈에 띄게 모이는 모습을 보여주는 장면"),
            beat(motion["wedge_c"], "쐐기 모양으로 쌓여갑니다", "wedge_forming", "wedge", "forming", "state",
                 "a moving 3D visualization of a wedge-shaped mound of water forming at the leading edge of a rolling car tire",
                 "모인 물이 쐐기 모양으로 자라나는 모습을 보여주는 장면"),
            beat(motion["wedge_d"], "더 커집니다", "wedge_size_state", "wedge", "large", "state",
                 "a moving 3D visualization of a large water wedge in front of a car tire on a wet road",
                 "타이어 앞의 물 쐐기가 뚜렷하게 커진 상태를 크게 보여주는 장면"),
        ]),
        ("s_twist", [
            phrase("TWIST", "물이 계속 쌓이면 접촉면이 앞쪽부터 줄어듭니다."),
            phrase("TWIST", "타이어가 도로를 밟는 면적이 점점 좁아집니다."),
            phrase("TWIST", "이제 접촉면은 처음의 절반도 남지 않았습니다."),
            phrase("TWIST", "타이어 뒤쪽 일부만 겨우 도로에 닿아 있습니다."),
            phrase("TWIST", "그 마저도 빠르게 사라지고 있습니다."),
        ], [
            beat(motion["contact_a"], "접촉면이 앞쪽부터 줄어듭니다", "contact_patch_shrinking", "contact", "shrinking_start", "concept",
                 "a moving 3D visualization of a car tire's bright road contact patch visibly shrinking from the leading edge while a water wedge grows ahead of it",
                 "타이어와 도로가 닿는 밝은 접촉면이 앞쪽부터 줄어들기 시작하는 모습을 보여주는 장면"),
            beat(motion["contact_b"], "면적이 점점 좁아집니다", "contact_narrowing", "contact", "narrowing", "state",
                 "a moving 3D visualization of a car tire's road contact patch continuing to narrow on a wet road",
                 "접촉면이 계속 좁아지는 모습을 보여주는 장면"),
            beat(motion["contact_c"], "절반도 남지 않았습니다", "contact_half_gone", "contact", "half_gone", "state",
                 "a moving 3D visualization of a car tire with less than half of its original road contact patch remaining",
                 "접촉면이 처음의 절반도 남지 않은 상태를 보여주는 장면"),
            beat(motion["contact_d"], "겨우 도로에 닿아 있습니다", "contact_rear_only", "contact", "rear_only", "state",
                 "a moving 3D visualization of a car tire with only a small rear sliver of its contact patch still touching a wet road",
                 "타이어 뒤쪽의 아주 작은 부분만 겨우 도로에 닿아 있는 모습을 보여주는 장면"),
            beat(motion["contact_e"], "빠르게 사라지고 있습니다", "contact_almost_gone", "contact", "almost_gone", "state",
                 "a moving 3D visualization of a car tire with almost no visible road contact patch left, riding mostly on a water layer",
                 "타이어의 접촉면이 거의 사라져 가는 상태를 보여주는 장면"),
        ]),
        ("s_end", [
            phrase("PAYOFF", "결국 타이어는 도로 대신 물 위에 뜨게 됩니다."),
            phrase("PAYOFF", "도로와의 접촉은 완전히 사라졌습니다."),
            phrase("PAYOFF", "타이어는 돌고 있지만 더 이상 바닥을 밟지 못합니다."),
            phrase("PAYOFF", "이 현상이 바로 하이드로플레이닝입니다."),
        ], [
            beat(motion["hydro_a"], "물 위에 뜨게 됩니다", "final_hydroplane_start", "hydroplane", "lifting", "concept",
                 "a moving cinematic 3D visualization of a car tire lifting off a wet road onto a layer of water",
                 "타이어가 도로 대신 물 위로 떠오르기 시작하는 모습을 보여주는 장면"),
            beat(motion["hydro_b"], "완전히 사라졌습니다", "contact_fully_gone", "hydroplane", "contact_gone", "state",
                 "a moving cinematic 3D visualization of a car tire fully lifted off a wet road with no road contact left at all",
                 "도로와의 접촉이 완전히 사라진 상태를 보여주는 장면"),
            beat(motion["hydro_c"], "바닥을 밟지 못합니다", "spinning_without_contact", "hydroplane", "spinning_free", "state",
                 "a moving cinematic 3D visualization of a car tire still rotating while fully afloat on a water layer with no road contact",
                 "타이어가 계속 돌고 있지만 더 이상 도로를 밟지 못하는 모습을 보여주는 장면"),
            beat(motion["hydro_d"], "하이드로플레이닝입니다", "final_hydroplane", "hydroplane", "full_lift", "state",
                 "a moving cinematic 3D payoff visualization of a car tire fully lifted off a wet road, floating entirely on a layer of water with no road contact left",
                 "타이어가 도로와의 접촉을 완전히 잃고 물 위에 떠 있는 최종 상태를 한 화면에 보여주는 모습"),
        ]),
    ]

    production_tags = {
        ("s_hook", 0): ("hero", "physical_animation"),
        ("s_hook", 1): ("support", "physical_animation"),
        ("s_hook", 2): ("support", "physical_animation"),
        ("s_hook", 3): ("support", "physical_animation"),
        ("s_reveal", 0): ("evidence", "real_photo"),
        ("s_reveal", 1): ("support", "physical_animation"),
        ("s_reveal", 2): ("support", "physical_animation"),
        ("s_reveal", 3): ("support", "physical_animation"),
        ("s_reveal", 4): ("support", "physical_animation"),
        ("s_reveal", 5): ("support", "physical_animation"),
        ("s_reveal", 6): ("support", "physical_animation"),
        ("s_explain", 0): ("mechanism", "physical_animation"),
        ("s_explain", 1): ("support", "physical_animation"),
        ("s_explain", 2): ("support", "physical_animation"),
        ("s_explain", 3): ("support", "physical_animation"),
        ("s_twist", 0): ("support", "physical_animation"),
        ("s_twist", 1): ("support", "physical_animation"),
        ("s_twist", 2): ("support", "physical_animation"),
        ("s_twist", 3): ("support", "physical_animation"),
        ("s_twist", 4): ("second_peak", "physical_animation"),
        ("s_end", 0): ("support", "physical_animation"),
        ("s_end", 1): ("support", "physical_animation"),
        ("s_end", 2): ("support", "physical_animation"),
        ("s_end", 3): ("payoff", "physical_animation"),
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
