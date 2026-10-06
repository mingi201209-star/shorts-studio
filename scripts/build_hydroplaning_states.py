#!/usr/bin/env python3
"""Build the hydroplaning Shorts production.

Quality-reset production: the opening is grounded in real high-resolution
rain/tire footage so the very first frame does not read as low-budget CG.
The existing physical animation is demoted to a short mechanism explainer
later in the story instead of carrying the opening impression. A real tire
photo still grounds tread geometry before the mechanism sequence.
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

HOOK_TIRE_VIDEO_URL = "https://videos.pexels.com/video-files/13891268/13891268-uhd_4096_2160_24fps.mp4"
HOOK_TIRE_VIDEO_PAGE = "https://www.pexels.com/video/close-up-of-car-tyre-in-rain-13891268/"
HOOK_TIRE_VIDEO_ATTRIBUTION = "Erik Mclean / Pexels / Pexels License"

HOOK_ROAD_VIDEO_URL = "https://videos.pexels.com/video-files/13370432/13370432-uhd_2160_3840_25fps.mp4"
HOOK_ROAD_VIDEO_PAGE = "https://www.pexels.com/video/driving-along-a-wet-road-on-a-rainy-day-13370432/"
HOOK_ROAD_VIDEO_ATTRIBUTION = "Zero51 / Pexels / Pexels License"


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



def download_required_video(url: str, out: Path, label: str) -> Path:
    """Fetch one fixed, explicitly licensed real-footage source.

    The URL is pinned to the source provider's concrete MP4, not a search
    result or a rotating CDN query.  We fail closed if the response is too
    small or not an MP4 container so a broken stock source can never silently
    degrade into a placeholder.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.is_file() and out.stat().st_size > 1_000_000:
        return out
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "shorts-studio/0.1 (licensed production asset)"},
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            if len(data) < 1_000_000:
                raise RuntimeError(f"{label} download suspiciously small: {len(data)} bytes")
            # ISO-BMFF/MP4 stores an ftyp box near the start.
            if b"ftyp" not in data[:64]:
                raise RuntimeError(f"{label} response does not look like MP4")
            out.write_bytes(data)
            print(f"HYDROPLANING_REAL_VIDEO_READY={out} bytes={len(data)} sha256={sha(out)}")
            return out
        except Exception as exc:
            last = exc
            out.unlink(missing_ok=True)
            if attempt < 3:
                time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"failed to fetch required {label} footage: {last}")


class HydroplaningHookGenerator:
    def generate(self, brief: TopicBrief) -> list[HookCandidate]:
        f = brief.fact_by_strategy()
        texts = {
            "contradiction": "빗길에선 타이어가 돌고 있어도 도로를 놓칠 수 있습니다.",
            "surprising_consequence": "빗길에선 멀쩡한 타이어도 도로에서 뜰 수 있습니다.",
            "counterintuitive_fact": "타이어 홈이 있어도 물을 다 빼내지 못할 수 있습니다.",
            "visible_anomaly": "빗길에선 타이어가 돌면서도 접촉을 잃을 수 있습니다.",
            "mistaken_assumption": "타이어가 돌고 있다고 항상 도로를 밟는 건 아닙니다.",
            "unresolved_cause_effect": "물이 빠지는 것보다 빨리 쌓이면 타이어가 뜹니다.",
        }
        return [HookCandidate(strategy=s, text=texts[s], grounded_in=f[s]) for s in texts]


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
    hook_tire_video = download_required_video(
        HOOK_TIRE_VIDEO_URL, assets / "hook_real_tire_rain.mp4", "real tire-in-rain"
    )
    hook_road_video = download_required_video(
        HOOK_ROAD_VIDEO_URL, assets / "hook_real_wet_road.mp4", "real wet-road"
    )

    # Each clip is centered on one of a small set of global-progress anchor
    # points that were chosen empirically (not just evenly sliced) so that
    # EVERY pair of anchors -- not just neighbors -- renders a genuinely,
    # substantially different frame under the engine's own real
    # equivalent-framing/replay detector (shorts_studio.visual_change).
    #
    # Two real CI rounds taught two separate lessons:
    #  - run 37039874973: finely slicing a near-flat stretch of the physics
    #    curve into many almost-identical states fails the per-beat
    #    distinctness check outright. Fix: fewer, well-separated anchors.
    #  - run 37081489230: even with well-separated anchors, a narrow g
    #    window around each one (the anchor +/- ~0.01, chosen purely to keep
    #    the sampled frame close to the verified value) reads as visually
    #    STATIC to a real viewer and to the engine's real pixel-level cut
    #    detector once composited into the actual final.mp4 -- direct human
    #    review of that run's frames at 0.5/1.5/2.5/3.5s confirmed they were
    #    "almost identical", and visual_activity_real found zero real cuts
    #    in the first 6s despite three "different" declared beats there.
    #    Fix here: each window now runs forward a real, substantial fraction
    #    of the gap to the NEXT anchor (not a tiny slice), so the water and
    #    tire are visibly, continuously moving for the clip's entire runtime
    #    -- and the opening uses one single LARGE jump (already-hydroplaning
    #    straight to the normal baseline) instead of three fine steps, so
    #    the first real cut is unmistakable rather than subtle.
    #  - run 37103835807: that fix cleared every gate except
    #    visual_activity_real, which still found 12.5s of real static picture
    #    from 6.5s onward (threshold 5.0s) -- direct per-0.5s adjacent-frame
    #    diffs the user pulled from the real final.mp4 showed 2.5-6.5s well
    #    above the 12.0 change threshold but 8.5-17.0s consistently under it,
    #    even though the physics (wedge/contact/lift) kept changing: the
    #    wedge2/contact1/contact2/payoff windows above were still only
    #    dg=0.03-0.04 wide, too little real motion to clear a threshold
    #    measured over the WHOLE padded 1080x950 media box (most of which is
    #    dark background/road, diluting the mean). Fixed on two fronts:
    #    (1) widened wedge1/wedge2/contact1/contact2/contact3's windows here
    #    to use most of the real gap to their next anchor (dg=0.07-0.17
    #    instead of 0.03-0.04); (2) shorts_studio/hydroplaning3d.py now ties
    #    a large, high-contrast rotating wheel-spoke pattern, a continuously
    #    rippling water-flow phase, and a scrolling road texture all directly
    #    to the tire's own rotation -- a fast, continuous clock (2.2 full
    #    spins across the whole production) layered on the slow hydroplaning
    #    state, so every beat stays visibly live regardless of how little the
    #    slow physics itself moves within its own window. Locally verified
    #    against a direct reimplementation of the real 2fps/media-box/
    #    mean-abs-diff>12 check (see shorts_studio.final_video_qa.
    #    measure_visual_activity) run against the actual rendered clips at
    #    this run's real measured beat timings: max_static_visual_seconds
    #    drops to ~2.5s, well under the 5.0s gate, with every beat boundary
    #    clearing the threshold by a comfortable (12-58) margin, not a
    #    razor-thin one.
    clips = {
        "hook_b": (0.880, 0.935, 2.2),    # cold open: already fully floating
        "base": (0.000, 0.150, 2.2),      # normal rolling, full contact, draining
        "wedge1": (0.370, 0.460, 2.2),    # wedge now clearly visible, contact dented
        "wedge2": (0.470, 0.540, 2.0),    # wedge bigger, contact further reduced -- REVEAL
        "contact1": (0.550, 0.630, 2.0),  # contact patch visibly collapsing
        "contact2": (0.640, 0.720, 2.0),  # less than half the patch left
        "contact3": (0.730, 0.860, 2.2),  # almost fully lifted
        "payoff": (0.950, 1.000, 2.4),    # final full hydroplaning state
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

    # Story order rebuilt around the real first_10s_retention windows
    # (0.2-3.0s: a real visual cut proving the HOOK claim; 3-8s: a new
    # state-change/tension beat; 8-12s: an early REVEAL/PAYOFF) instead of
    # evenly dividing narration. The opening is now exactly ONE dramatic cut
    # -- hero (already fully floating) straight to the normal baseline, a
    # huge pixel jump that a real cut detector cannot miss -- rather than
    # three fine steps across a narrow g range, which run 37081489230 showed
    # reads as static to both a human viewer and the engine's real
    # visual_activity_real detector even though each step was a "different"
    # declared state. REVEAL is now genuinely the wedge visibly growing
    # (wedge2), timed via the real measured per-beat rate from that run
    # (~3.2-4.2 normalized chars/sec within a scene, ~1.3-2.4s crossing a
    # scene boundary) to land inside the mandatory 8-12s window, not just
    # relabeled.
    # hookb is deliberately kept IN THE SAME SCENE as base (not alone in its
    # own scene) so its hold is pure phrase-length/rate with no risk of
    # picking up the unpredictable ~1.3-2.4s trailing-silence pad a scene's
    # OWN last beat pays (observed directly in run 37081489230's real
    # per-beat timings) -- that pad alone could push the mandatory
    # 0.2-3.0s opening visual-proof cut outside its window regardless of how
    # short the hook text is. Every scene's actual LAST beat below carries
    # the shortest phrase in that scene for the same reason.
    hook = winner.text
    crisis = "문제는 고무가 아니라, 타이어 아래로 밀려드는 물입니다."
    plans = [
        ("s_hook", [
            phrase("HOOK", hook, winner.strategy),
            phrase("CRISIS", crisis),
        ], [
            beat(hook_tire_video, hook, "real_tire_rain_hook", "hook_real_tire", "rain_closeup", "concept",
                 "real cinematic close-up footage of an actual car tire and wheel in rain on wet pavement, visible raindrops and real photographic texture",
                 "첫 프레임부터 실제 빗속 자동차 타이어를 고해상도 실사 영상으로 보여줘 저예산 CG 느낌 없이 주제를 즉시 인식시키는 장면",
                 HOOK_TIRE_VIDEO_ATTRIBUTION),
            beat(hook_road_video, crisis, "real_water_hazard", "hook_real_road", "wet_road", "concept",
                 "real vertical footage from a moving car on a visibly wet rainy road, real reflections, water and road texture",
                 "실제 젖은 도로와 빗물을 보여줘 문제의 원인이 물이라는 단서를 실사로 이어주는 장면",
                 HOOK_ROAD_VIDEO_ATTRIBUTION),
        ]),
        ("s_reveal", [
            phrase("INVESTIGATION", "트레드 홈은 원래 이 물을 옆으로 빼냅니다."),
            phrase("INVESTIGATION", "그런데 물이 빠지는 속도보다 쌓이는 속도가 빨라지면,"),
            phrase("REVEAL", "앞쪽에 물 쐐기가 생기고,"),
            phrase("EXPLANATION", "도로와 닿는 면이 점점 줄어듭니다."),
        ], [
            beat(tire_photo, "트레드 홈은 원래 이 물을 옆으로 빼냅니다", "real_tread_grounding", "tread_photo", "real", "concept",
                 "a real close-up photograph of an actual car tire's tread and grooves",
                 "실제 타이어 트레드 홈을 사진으로 보여주며 물을 옆으로 빼는 구조를 현실 물체로 먼저 이해시키는 장면",
                 TIRE_PHOTO_ATTRIBUTION),
            # wedge1 is NOT this scene's last beat (wedge2/contact1 follow it
            # here too, after merging what used to be a separate s_explain
            # scene) -- keeping REVEAL inside the SAME scene as the photo
            # saves one scene-transition trailing-silence pad (~1.3-2.4s
            # observed in run 37081489230), which is exactly what pushed
            # REVEAL's start past the mandatory 8-12s window when it lived
            # in its own scene.
            beat(motion["wedge1"], "그런데 물이 빠지는 속도보다 쌓이는 속도가 빨라지면", "drainage_overload", "wedge", "forming", "concept",
                 "a moving 3D visualization of a water wedge forming at the leading edge of a rolling car tire, its road contact patch visibly dented",
                 "홈이 다 빼내지 못한 물이 타이어 앞쪽에 쌓여 물 쐐기가 생기기 시작하는 모습을 보여주는 장면"),
            beat(motion["wedge2"], "앞쪽에 물 쐐기가 생기고", "wedge_growing", "wedge", "large", "state",
                 "a moving 3D visualization of a large water wedge in front of a car tire, its road contact patch clearly shrunk compared to a moment ago",
                 "타이어 앞의 물 쐐기가 눈에 띄게 커지고 접촉면이 함께 줄어드는 원인이 드러나는 장면"),
            beat(motion["contact1"], "도로와 닿는 면이 점점 줄어듭니다", "contact_patch_shrinking", "contact", "shrinking", "concept",
                 "a moving 3D visualization of a car tire's bright road contact patch visibly collapsing while a large water wedge sits ahead of it",
                 "타이어와 도로가 닿는 밝은 접촉면이 눈에 띄게 줄어드는 모습을 보여주는 장면"),
        ]),
        ("s_twist", [
            phrase("TWIST", "접촉면이 거의 사라지는 순간,"),
            phrase("TWIST", "타이어는 도로 대신 물 위를 타기 시작합니다."),
            phrase("PAYOFF", "이게 하이드로플레이닝입니다."),
        ], [
            beat(motion["contact2"], "접촉면이 거의 사라지는 순간", "contact_half_gone", "contact", "half_gone", "state",
                 "a moving 3D visualization of a car tire with less than half of its original road contact patch remaining and the tire visibly rising",
                 "접촉면이 절반도 남지 않고 타이어가 눈에 띄게 떠오르는 모습을 보여주는 장면"),
            beat(motion["contact3"], "타이어는 도로 대신 물 위를 타기 시작합니다", "contact_almost_gone", "contact", "almost_gone", "state",
                 "a moving 3D visualization of a car tire almost fully lifted off a wet road, only a sliver of contact patch left",
                 "타이어의 접촉면이 거의 사라지고 거의 다 떠오른 상태를 보여주는 장면"),
            beat(motion["payoff"], "이게 하이드로플레이닝입니다", "final_hydroplane", "hydroplane", "full_lift", "concept",
                 "a moving cinematic 3D payoff visualization of a car tire fully lifted off a wet road, floating entirely on a layer of water with no road contact left",
                 "타이어가 도로와의 접촉을 완전히 잃고 물 위에 떠 있는 최종 상태를 한 화면에 보여주는 모습"),
        ]),
    ]

    production_tags = {
        ("s_hook", 0): ("hero", "real_footage"),
        ("s_hook", 1): ("support", "real_footage"),
        ("s_reveal", 0): ("evidence", "real_photo"),
        ("s_reveal", 1): ("support", "physical_animation"),
        ("s_reveal", 2): ("mechanism", "physical_animation"),
        ("s_reveal", 3): ("support", "physical_animation"),
        ("s_twist", 0): ("support", "physical_animation"),
        ("s_twist", 1): ("second_peak", "physical_animation"),
        ("s_twist", 2): ("payoff", "physical_animation"),
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

    desc = f"""# 타이어가 도로에서 뜨는 이유 — 출처

첫 장면은 실제 촬영 영상을 사용합니다.
- 타이어 빗속 클로즈업: {HOOK_TIRE_VIDEO_ATTRIBUTION} ({HOOK_TIRE_VIDEO_PAGE})
- 젖은 도로 주행: {HOOK_ROAD_VIDEO_ATTRIBUTION} ({HOOK_ROAD_VIDEO_PAGE})

이후 원리 설명은 실제 좌표의 원기둥·타원체·박스 geometry를 카메라로 투영해 프레임마다 렌더한
자체 제작 3D 물리 시각화이며, 실제 트레드 구조 확인에는 아래 CC0 사진을 사용했습니다:
{TIRE_PHOTO_ATTRIBUTION} ({TIRE_PHOTO_PAGE}).

설명된 물리적 메커니즘(물이 타이어와 노면 사이에 쌓이면 접촉력이 감소할 수 있고, 충분히 심해지면
완전히 접촉을 잃을 수 있으며, 트레드 홈은 접촉 영역의 물 배출에 도움을 준다는 점)은 미국 도로교통
안전국(NHTSA)의 공개된 하이드로플레이닝 안전 설명을 참고해 과장 없이 서술했습니다. 정확한 임계
속도나 공식은 조건에 따라 달라지므로 영상에서 보편적 수치로 제시하지 않았습니다.
"""
    Path("examples/hydroplaning_upload_description.txt").write_text(desc, encoding="utf-8")
    print("HYDROPLANING_MANIFEST_READY=examples/hydroplaning.json")


if __name__ == "__main__":
    main()
