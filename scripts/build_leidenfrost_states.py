#!/usr/bin/env python3
"""Build the Leidenfrost success-pattern experiment.

Purpose: test the common structure found in strong science Shorts:
  real surprising result first -> intuitive expectation -> one visible clue
  -> one mechanism -> one reversal -> precise payoff.

Unlike the Mpemba production, this intentionally explains ONE mechanism only.
The opening uses a real CC BY 4.0 experiment clip; every remaining visual is
generated here so the finished Short is upload-friendly without ShareAlike
licensing complications.
"""
from __future__ import annotations

import argparse, hashlib, json, subprocess, time, urllib.parse, urllib.request
from pathlib import Path
from shorts_studio.diagram3d import render_3d_motion
from shorts_studio.hook_studio import (
    HookCandidate, TopicBrief, generate_and_judge,
    build_story_generation_prompt, story_writer_system_prompt,
)

W,H=980,950
INK="#17191c"; WHITE="#ffffff"; BLACK="#000000"
RED="#e24a3b"; BLUE="#3578c8"; CYAN="#55c6d9"; GREY="#7b858d"; YELLOW="#f2c94c"
NEG=["a photograph of a cat","a landscape photograph of mountains","a city skyline"]

VIDEO_FILE="Underwater-Leidenfrost-nanochemistry-for-creation-of-size-tailored-zinc-peroxide-cancer-ncomms15319-s2.ogv"
VIDEO_PAGE="https://commons.wikimedia.org/wiki/File:Underwater-Leidenfrost-nanochemistry-for-creation-of-size-tailored-zinc-peroxide-cancer-ncomms15319-s2.ogv"
VIDEO_ATTRIBUTION=(
    "Elbahri M, Abdelaziz R, Disci-Zayed D, Homaeigohar S, Sosna J, Adam D, "
    "Kienle L, Dankwort T, Abdelaziz M / Nature Communications / Wikimedia Commons / CC BY 4.0"
)


def sha(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download_required_video(out:Path)->Path:
    out.parent.mkdir(parents=True,exist_ok=True)
    if out.is_file() and out.stat().st_size>50_000:
        return out
    encoded=urllib.parse.quote(VIDEO_FILE.replace(" ","_"),safe="._-()")
    url=f"https://commons.wikimedia.org/wiki/Special:Redirect/file/{encoded}"
    last=None
    for attempt in range(4):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"shorts-studio/0.1 (CC BY production asset)"})
            with urllib.request.urlopen(req,timeout=45) as r:
                data=r.read()
            if len(data)<100_000:
                raise RuntimeError(f"download suspiciously small: {len(data)} bytes")
            out.write_bytes(data)
            probe=subprocess.run(
                ["ffprobe","-v","error","-select_streams","v:0",
                 "-show_entries","stream=width,height,codec_name","-show_entries","format=duration",
                 "-of","json",str(out)],capture_output=True,text=True,check=True,timeout=30)
            info=json.loads(probe.stdout)
            duration=float(info["format"]["duration"])
            if duration<2.5:
                raise RuntimeError(f"source video too short: {duration}")
            print(f"LEIDENFROST_VIDEO_READY={out} duration={duration:.3f}s sha256={sha(out)}")
            return out
        except Exception as exc:
            last=exc
            out.unlink(missing_ok=True)
            if attempt<3:
                time.sleep(5*(attempt+1))
    raise RuntimeError(f"failed to fetch required Leidenfrost video: {last}")


class LeidenfrostHookGenerator:
    def generate(self,brief:TopicBrief)->list[HookCandidate]:
        f=brief.fact_by_strategy()
        texts={
            "contradiction":"뜨거운 판인데도 물방울이 직접 닿지 않고 떠다닐 수 있습니다.",
            "surprising_consequence":"놀랍게도 300도 판에서도 물방울이 오히려 떠다닙니다.",
            "counterintuitive_fact":"더 뜨거운 표면이 오히려 물방울을 잠깐 보호하는 조건이 생깁니다.",
            "visible_anomaly":"뜨거운 팬 위의 물방울이 이상하게도 끓어 없어지는 대신 미끄러집니다.",
            "mistaken_assumption":"팬이 더 뜨거우면 물은 항상 더 빨리 사라진다는 생각은 사실과 다를 수 있습니다.",
            "unresolved_cause_effect":"물방울 아래 수증기층이 생기면 금속과 직접 접촉이 줄어듭니다. 그런데 왜 물방울이 떠 있을까요?",
        }
        return [HookCandidate(strategy=s,text=texts[s],grounded_in=f[s]) for s in texts]


def make_brief():
    return TopicBrief(
        topic_id="leidenfrost-effect",
        familiar_subject="뜨거운 팬 위의 물방울",
        contradiction_fact="뜨거운 판인데도 물방울이 직접 닿지 않고 떠다닐 수 있습니다",
        surprising_consequence_fact="300도짜리 판에서는 물방울이 바로 사라지지 않고 떠다닐 수 있습니다",
        counterintuitive_fact="더 뜨거운 표면이 물방울을 잠깐 보호하는 조건이 생길 수 있습니다",
        anomaly_fact="뜨거운 팬 위의 물방울이 끓어 없어지는 대신 미끄러지듯 움직일 수 있습니다",
        mistaken_assumption_fact="팬이 더 뜨거우면 물은 항상 더 빨리 사라진다는 생각은 맞지 않을 수 있습니다",
        cause_effect_fact="물방울 아래 수증기층이 생기면 뜨거운 금속과 직접 접촉이 줄어듭니다",
        payoff_text="충분히 뜨거운 표면에서는 물방울 아래에 증기층이 생겨 직접 접촉을 막고 물방울을 띄울 수 있습니다",
        grounded_facts=[
            "라이덴프로스트 효과에서 물방울은 자기 수증기 쿠션 위에 떠 있을 수 있습니다",
            "증기층은 뜨거운 표면과 액체 사이의 직접 접촉을 줄이고 빠른 증발을 늦출 수 있습니다",
        ],
    )


def phrase(role,text,hook_type=None):
    x={"role":role,"text":text}
    if hook_type:x["hook_type"]=hook_type
    return x


def beat(asset:Path,cue:str,info_role:str,concept_id:str,state_id:str,kind:str,
         qa_label:str,req:str,attribution:str|None=None):
    digest=sha(asset)
    return {
        "start":0.0,
        "asset":str(asset),
        "attribution":attribution,
        "visual_change":{
            "kind":kind,"concept_id":concept_id,"state_id":state_id,
            "narration_cue":cue,"added_information":info_role,
            "source_sha256":digest,
        },
        "visual_qa_requirements":[req],
        "visual_qa_labels":[qa_label],
        "visual_qa_negative_labels":NEG,
        "visual_qa_expected_sha256":[digest],
        "info_role":info_role,
    }


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--font",default=None);args=ap.parse_args()
    assets=Path("assets/leidenfrost_effect"); assets.mkdir(parents=True,exist_ok=True)
    source_video=download_required_video(assets/"source_experiment.ogv")

    kinds=[
        "hook_result","skid_contrast","expectation","question_gap","vapor_birth","vapor_expand","vapor_cushion",
        "vapor_hint","no_contact","contact_gap","heat_blocked","paradox_shield","protected_drop",
        "glide","support_force","name","threshold","payoff",
    ]
    durations={
        "hook_result":2.8,
        "skid_contrast":3.2,
        "expectation":3.0,
        "question_gap":3.2,
        "vapor_hint":3.0,
        "vapor_birth":3.0,
        "vapor_expand":3.0,
        "vapor_cushion":3.2,
        "no_contact":3.0,
        "contact_gap":3.0,
        "heat_blocked":3.0,
        "paradox_shield":3.0,
        "protected_drop":3.0,
        "glide":3.4,
        "support_force":3.0,
        "name":3.0,
        "threshold":3.2,
        "payoff":3.4,
    }
    # Every synthetic state is rendered from actual 3D coordinates:
    # sphere/ellipsoid/box/vector geometry -> camera projection -> moving MP4.
    # The real experiment clip remains the only non-generated visual.
    motion={
        k:render_3d_motion(
            k,
            assets/f"{k}_3d_motion.mp4",
            duration=durations[k],
            fps=30,
            width=W,
            height=H,
        )
        for k in kinds
    }

    brief=make_brief()
    hook_result=generate_and_judge(brief,generator=LeidenfrostHookGenerator())
    if hook_result.winner is None:
        raise RuntimeError("Prompt V2 produced no Leidenfrost hook")
    winner=hook_result.winner
    print(f"PROMPT_V2_JUDGE={hook_result.judge_name}")
    print(f"PROMPT_V2_SELECTED_STRATEGY={winner.strategy}")
    print(f"PROMPT_V2_SELECTED_HOOK={winner.text}")

    build=Path("build");build.mkdir(exist_ok=True)
    story_prompt=build_story_generation_prompt(
        brief,winner,
        uncertainty_notes=[
            "라이덴프로스트 온도는 표면 상태와 조건에 따라 달라질 수 있습니다",
            "이 영상은 물방울을 띄우는 증기층 메커니즘에 집중하며 세부 유체역학 전부를 설명하지 않습니다",
        ],
    )
    (build/"leidenfrost_story_prompt.txt").write_text(
        story_writer_system_prompt()+"\n\n"+story_prompt+"\n",encoding="utf-8")
    print("STORY_PROMPT_V3_READY=build/leidenfrost_story_prompt.txt")

    hook=winner.text
    # Keep beat timing robust to whichever strategy wins. Prompt V2 is
    # intentionally free to choose a different candidate after scoring;
    # visual cues must bind to the delivered winner, not to one assumed
    # candidate's wording.
    hook_result_cue = hook.rstrip(".?!").split()[-1]
    plans=[
        ("s_hook",[
            phrase("HOOK",hook,winner.strategy),
            phrase("CRISIS","그런데 더 뜨거운데, 왜 안 사라질까요?"),
            phrase("REVEAL","답은 물방울 밑의 수증기입니다."),
        ],[
            beat(source_video,hook,"real_300c_result","hook_result","video","concept",
                 "a real scientific experiment showing water transforming into a Leidenfrost droplet on a 300 degree Celsius superheated plate",
                 f"실제 실험 영상이 첫 훅 '{hook}'에 나온 뜨거운 판과 물방울 현상을 직접 보여주는 모습",VIDEO_ATTRIBUTION),
            beat(motion["hook_result"],"이상하게도","levitating_result","hook_diagram","result","concept",
                 "a moving cinematic 3D scientific visualization of a water droplet floating above a red hot plate instead of vanishing",
                 "뜨거운 판 위에서 물방울이 바로 사라지지 않고 떠 있는 결과를 크게 보여주는 모습"),
            beat(motion["skid_contrast"],"없어지는 대신","vanish_vs_skid","hook_contrast","skid","concept",
                 "a moving 3D scientific contrast showing a shrinking droplet on one hot surface and a skittering Leidenfrost droplet on another",
                 "한쪽에서는 물방울이 줄어들고 다른 쪽에서는 수증기층 위에서 미끄러지는 대비를 3D 움직임으로 보여주는 모습"),
            beat(motion["expectation"],"그런데","intuitive_expectation","expectation","hotter_vanishes","concept",
                 "a moving cinematic 3D scientific visualization showing the expectation that hotter surface means faster evaporation",
                 "더 뜨거우면 물이 더 빨리 사라질 것이라는 직관적 예상을 보여주는 모습"),
            beat(motion["question_gap"],"왜 안 사라질까요","open_question","question_gap","why_reverse","concept",
                 "a moving cinematic 3D split visualization asking why a hotter plate can leave a droplet floating",
                 "더 뜨거운데 왜 물방울이 떠 있는지 질문을 두 갈래 대비 화면으로 보여주는 모습"),
            beat(motion["vapor_hint"],"수증기입니다","early_vapor_answer","vapor_hint","hint","concept",
                 "a moving dark cinematic 3D scientific visualization showing a single vapor pocket beneath a floating water droplet",
                 "부분 정답으로 물방울 밑에 수증기가 있다는 사실만 먼저 보여주는 모습"),
        ]),
        ("s_reveal",[
            phrase("INVESTIGATION","그 수증기가 물방울 아래로 퍼지면서 아주 얇은 쿠션을 만듭니다."),
        ],[
            beat(motion["vapor_birth"],"그 수증기가","vapor_birth","vapor_layer","birth","concept",
                 "a moving 3D cross-section showing vapor jets forming under a water droplet above a glowing hot metal plate",
                 "물방울 아래에서 수증기가 만들어지는 단면 모습"),
            beat(motion["vapor_expand"],"아래로 퍼지면서","vapor_spread","vapor_layer","spread","state",
                 "a moving cinematic 3D scientific visualization filled with vapor bubbles spreading beneath a droplet above a hot plate",
                 "생긴 수증기가 물방울 아래쪽으로 퍼지는 모습을 크게 보여주는 모습"),
            beat(motion["vapor_cushion"],"쿠션","vapor_cushion","vapor_layer","cushion","state",
                 "a moving 3D cross-section showing a water droplet rising onto a continuous vapor cushion above a glowing hot metal plate",
                 "물방울과 뜨거운 판 사이에 얇은 수증기 쿠션이 생긴 모습"),
        ]),
        ("s_explain",[
            phrase("EXPLANATION","그 증기층 때문에 물방울은 뜨거운 금속에 직접 닿지 않습니다. 그래서 열이 바로 전달되지 않습니다."),
        ],[
            beat(motion["no_contact"],"그 증기층","no_direct_contact","insulation","no_contact","concept",
                 "a moving cinematic 3D scientific visualization showing a water droplet separated from a hot metal surface by vapor with no direct contact",
                 "수증기층 때문에 물방울이 뜨거운 금속에 직접 닿지 않는 모습"),
            beat(motion["contact_gap"],"직접 닿지","visible_gap","insulation","gap","state",
                 "a moving high contrast 3D macro visualization emphasizing the physical gap between water and hot metal",
                 "물방울과 뜨거운 금속 사이의 직접 접촉이 끊긴 틈을 크게 확대해 보여주는 모습"),
            beat(motion["heat_blocked"],"열이 바로","reduced_heat_transfer","insulation","heat_blocked","state",
                 "a moving dark 3D thermal visualization showing heat flow interrupted by a vapor layer under a water droplet",
                 "수증기층에서 뜨거운 판의 열 흐름이 바로 이어지지 않는 모습을 보여주는 장면"),
        ]),
        ("s_twist",[
            phrase("TWIST","그래서 판이 더 뜨거워졌는데도 물방울은 잠깐 보호됩니다. 팬 위를 미끄러지는 움직임도 이 증기층이 받쳐 주기 때문입니다."),
        ],[
            beat(motion["paradox_shield"],"더 뜨거워졌는데도","hotter_but_protected","paradox","shield","concept",
                 "a moving cinematic 3D physical cross section showing a water droplet still separated from an extremely hot glowing metal surface by a vapor layer",
                 "더 뜨거워진 금속 표면 위에서도 물방울과 금속 사이에 증기층이 유지되는 모습을 보여주는 장면"),
            beat(motion["protected_drop"],"잠깐 보호됩니다","supported_drop","paradox","supported","state",
                 "a moving glossy 3D blue droplet visibly supported by a curved vapor cushion",
                 "물방울이 수증기층 위에서 실제로 받쳐지는 구조를 크게 보여주는 모습"),
            beat(motion["glide"],"미끄러지는","skittering_motion","glide","path","concept",
                 "a moving top-down 3D metal-pan visualization with a Leidenfrost droplet following a curved skating path",
                 "물방울이 팬 위에서 곡선을 그리며 미끄러지는 움직임을 위에서 내려다본 모습"),
            beat(motion["support_force"],"증기층이 받쳐","vapor_support_force","glide","support","state",
                 "a moving 3D physical visualization with upward heat-flow arrows showing vapor physically supporting a water droplet from below",
                 "수증기층이 아래에서 위쪽으로 물방울을 받쳐 주는 구조를 화살표로 보여주는 모습"),
        ]),
        ("s_end",[
            phrase("PAYOFF","이게 라이덴프로스트 효과입니다. 충분히 뜨거운 표면에서는 물이 바로 사라지는 대신, 자기 수증기 위에 잠깐 떠 있게 됩니다."),
        ],[
            beat(motion["name"],"라이덴프로스트 효과","effect_name","payoff","name","concept",
                 "a moving cinematic 3D scientific name reveal naming the Leidenfrost effect around a floating water droplet",
                 "수증기 위에 뜬 물방울과 함께 라이덴프로스트 효과라는 이름을 처음 공개하는 모습"),
            beat(motion["threshold"],"충분히 뜨거운","temperature_condition","payoff","threshold","state",
                 "a moving three-state 3D physical progression showing hotter metal surfaces and a stable vapor layer under the droplet only at the hottest state",
                 "표면이 더 뜨거워질수록 마지막 상태에서 안정된 증기층이 생기는 물리적 진행을 보여주는 모습"),
            beat(motion["payoff"],"자기 수증기 위에","final_mechanism","payoff","mechanism","state",
                 "a moving cinematic 3D payoff visualization showing a droplet floating on its own vapor above a hot surface",
                 "뜨거운 표면에서 물방울이 자기 수증기 위에 떠 있는 최종 원리를 한 화면에 보여주는 모습"),
        ]),
    ]

    production_tags={
        ("s_hook",0):("hero","real_footage"),
        ("s_hook",1):("support","physical_animation"),
        ("s_hook",2):("evidence","physical_animation"),
        ("s_hook",3):("support","physical_animation"),
        ("s_hook",4):("support","physical_animation"),
        ("s_hook",5):("support","physical_animation"),
        ("s_reveal",0):("support","physical_animation"),
        ("s_reveal",1):("support","physical_animation"),
        ("s_reveal",2):("mechanism","physical_animation"),
        ("s_explain",0):("support","physical_animation"),
        ("s_explain",1):("support","physical_animation"),
        ("s_explain",2):("second_peak","physical_animation"),
        ("s_twist",0):("support","physical_animation"),
        ("s_twist",1):("support","physical_animation"),
        ("s_twist",2):("support","physical_animation"),
        ("s_twist",3):("support","physical_animation"),
        ("s_end",0):("support","physical_animation"),
        ("s_end",1):("support","physical_animation"),
        ("s_end",2):("payoff","physical_animation"),
    }

    scenes=[]
    seen_tags=set()
    for sid,narr_plan,beats in plans:
        # Pydantic requires increasing authored starts; real starts are replaced
        # from measured TTS cues during strict meaningful-change rendering.
        for i,b in enumerate(beats):
            b["start"]=float(i)
            role,mode=production_tags[(sid,i)]
            b["production"]={
                "role":role,
                "visual_mode":mode,
                "added_information":b["info_role"],
            }
            seen_tags.add((sid,i))
        narration=" ".join(p["text"] for p in narr_plan)
        scenes.append({
            "id":sid,"narration":narration,
            "narration_plan":narr_plan,
            "visual_description":"Evidence-first Leidenfrost visual sequence matched to narration.",
            "asset":beats[0]["asset"],
            "attribution":beats[0].get("attribution"),
            "visual_beats":beats,
            "visual_qa_requirements":["각 내레이션 단서에 맞는 라이덴프로스트 현상 또는 설명 도식이 실제 화면에 보여야 함"],
            "visual_qa_labels":[beats[0]["visual_qa_labels"][0]],
            "visual_qa_negative_labels":NEG,
            "overlay_title":None,
            "overlay_title_seconds": 2.8 if sid=="s_hook" else None,
        })

    expected_tags={(sid,i) for sid,_,beats in plans for i,_ in enumerate(beats)}
    if seen_tags!=expected_tags or set(production_tags)!=expected_tags:
        raise RuntimeError("Visual Production V2 tag coverage drifted from the real beat list")

    manifest={
        "title":"300도 판에서 물방울이 사라지지 않는 이유",
        "width":1080,"height":1920,"fps":30,
        "overlay_title":"물방울이 뜬다",
        "overlay_title_mode":"first_scene_only",
        "max_visual_recovery_attempts":2,
        "strict_source_diversity":False,
        "strict_meaningful_visual_changes":True,
        "strict_retention_contract":True,
        "strict_visual_production_v2":True,
        "observable_phenomenon":"매우 뜨거운 표면에서 물방울이 바로 사라지지 않고 떠서 미끄러진다.",
        "silent_story":"실제 300도 실험 → 사라지지 않는 대비 → 밑의 수증기 단서 → 증기 쿠션 → 열 전달이 막히는 두 번째 피크 → 미끄러지는 결과 → 수증기 위에 뜬 최종 payoff",
        "silent_interest_review":"pending",
        "strict_entertainment_contract":False,
        "scenes":scenes,
    }
    Path("examples").mkdir(exist_ok=True)
    Path("examples/leidenfrost_effect.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")

    desc=f"""# 300도 판에서 물방울이 사라지지 않는 이유 — 출처

실제 실험 영상:
- Underwater-Leidenfrost-nanochemistry-for-creation-of-size-tailored-zinc-peroxide-cancer-ncomms15319-s2.ogv
- Authors: Elbahri M, Abdelaziz R, Disci-Zayed D, Homaeigohar S, Sosna J, Adam D, Kienle L, Dankwort T, Abdelaziz M
- Source: {VIDEO_PAGE}
- License: Creative Commons Attribution 4.0 International (CC BY 4.0)
- 사용 변경: 세로형 Shorts 프레임에 맞게 리사이즈/구성하고 원본 음성은 사용하지 않음

나머지 설명 장면은 실제 3D 좌표의 구·박스·타원체·벡터를 카메라로 투영해 프레임마다 렌더한 움직이는 3D 도식입니다.
"""
    Path("examples/leidenfrost_effect_upload_description.txt").write_text(desc,encoding="utf-8")
    print("LEIDENFROST_MANIFEST_READY=examples/leidenfrost_effect.json")


if __name__=="__main__":
    main()
