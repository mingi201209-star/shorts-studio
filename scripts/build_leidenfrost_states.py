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
from PIL import Image, ImageDraw, ImageFont

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


def get_font(path:str|None,size:int):
    choices=[path,"/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
             "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]
    for p in choices:
        if p and Path(p).is_file():
            return ImageFont.truetype(p,size)
    return ImageFont.load_default()


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


def canvas():
    im=Image.new("RGB",(W,H),BLACK)
    d=ImageDraw.Draw(im)
    d.rounded_rectangle((16,16,W-16,H-16),radius=28,fill=WHITE)
    return im,d


def droplet(d,cx,cy,r=85,fill=BLUE):
    pts=[(cx,cy-r-30),(cx-r,cy+35),(cx-r+15,cy+r),(cx,cy+r+25),
         (cx+r-15,cy+r),(cx+r,cy+35)]
    d.polygon(pts,fill=fill,outline=INK)
    d.ellipse((cx-r,cy-r//2,cx+r,cy+r+20),fill=fill,outline=INK,width=6)


def hot_plate(d,y=690):
    d.rounded_rectangle((90,y,890,y+95),radius=24,fill=RED,outline=INK,width=7)
    for x in range(150,850,120):
        d.line((x,y+110,x+35,y+160),fill=RED,width=8)


def save_panel(kind:str,label:str,out:Path,font_path:str|None):
    im,d=canvas()
    f30=get_font(font_path,30); f38=get_font(font_path,38); f52=get_font(font_path,52)
    if kind=="hook_result":
        hot_plate(d,690); droplet(d,490,450,105)
        d.line((360,585,620,585),fill=CYAN,width=22)
        d.text((490,235),"사라짐 X · 떠 있음",font=f52,fill=INK,anchor="mm")
        d.text((490,840),"300°C 초가열 판",font=f30,fill=RED,anchor="mm")
    elif kind=="expectation":
        d.text((490,235),"보통 예상",font=f52,fill=INK,anchor="mm")
        hot_plate(d,660); droplet(d,330,475,75)
        for x in (530,620,710):
            d.line((x,560,x,390),fill=GREY,width=12)
            d.polygon([(x,350),(x-18,395),(x+18,395)],fill=GREY)
        d.text((650,475),"더 뜨거움\n→ 더 빨리 사라짐?",font=f38,fill=INK,anchor="mm",align="center")
    elif kind=="vapor_birth":
        hot_plate(d,690); droplet(d,490,390,110)
        for x in (390,450,510,570,630):
            d.ellipse((x-22,585,x+22,630),fill=CYAN,outline=INK,width=4)
        d.text((490,245),"물방울 아래에서 수증기 생성",font=f38,fill=INK,anchor="mm")
    elif kind=="vapor_cushion":
        hot_plate(d,720); droplet(d,490,365,120)
        d.rounded_rectangle((270,575,710,650),radius=30,fill=CYAN,outline=INK,width=6)
        d.text((490,612),"얇은 수증기층",font=f38,fill=INK,anchor="mm")
        d.line((235,610,150,610),fill=INK,width=6)
        d.text((135,610),"쿠션",font=f30,fill=INK,anchor="rm")
    elif kind=="no_contact":
        hot_plate(d,720); droplet(d,490,350,120)
        d.rounded_rectangle((300,565,680,640),radius=30,fill=CYAN,outline=INK,width=6)
        d.line((315,520,665,690),fill=RED,width=22)
        d.line((315,690,665,520),fill=RED,width=22)
        d.text((490,240),"금속과 직접 접촉하지 않음",font=f38,fill=INK,anchor="mm")
    elif kind=="heat_blocked":
        hot_plate(d,720); droplet(d,490,315,110)
        d.rounded_rectangle((285,535,695,620),radius=30,fill=CYAN,outline=INK,width=6)
        for x in (350,490,630):
            d.line((x,700,x,635),fill=RED,width=14)
            d.polygon([(x,620),(x-18,650),(x+18,650)],fill=RED)
        d.text((490,480),"열 전달이 바로 이어지지 않음",font=f38,fill=INK,anchor="mm")
    elif kind=="paradox_shield":
        hot_plate(d,720); droplet(d,490,340,115)
        d.arc((260,425,720,730),start=190,end=350,fill=CYAN,width=28)
        d.text((490,230),"더 뜨거운데, 잠깐 보호됨",font=f38,fill=INK,anchor="mm")
        d.text((490,820),"증기층 = 단열 쿠션",font=f30,fill=CYAN,anchor="mm")
    elif kind=="glide":
        hot_plate(d,690); droplet(d,330,430,90)
        d.arc((280,380,760,590),start=350,end=160,fill=BLUE,width=16)
        d.polygon([(770,485),(720,455),(725,510)],fill=BLUE)
        for x in (300,340,380):
            d.ellipse((x-12,580,x+12,605),fill=CYAN)
        d.text((490,250),"수증기 위를 미끄러지듯 이동",font=f38,fill=INK,anchor="mm")
    elif kind=="name":
        hot_plate(d,705); droplet(d,490,365,105)
        d.rounded_rectangle((315,555,665,625),radius=25,fill=CYAN,outline=INK,width=5)
        d.text((490,225),"라이덴프로스트 효과",font=f52,fill=INK,anchor="mm")
    elif kind=="payoff":
        d.text((490,190),"충분히 뜨거운 표면",font=f38,fill=RED,anchor="mm")
        hot_plate(d,690); droplet(d,490,340,110)
        d.rounded_rectangle((285,545,695,625),radius=30,fill=CYAN,outline=INK,width=6)
        d.text((490,585),"자기 수증기 위에 잠깐 뜸",font=f30,fill=INK,anchor="mm")
        d.text((490,830),"바로 사라짐 → X",font=f38,fill=INK,anchor="mm")
    else:
        raise ValueError(kind)
    out.parent.mkdir(parents=True,exist_ok=True)
    im.save(out,quality=95)
    return out


class LeidenfrostHookGenerator:
    def generate(self,brief:TopicBrief)->list[HookCandidate]:
        f=brief.fact_by_strategy()
        texts={
            "contradiction":"뜨거운 판인데도 물방울이 직접 닿지 않고 떠다닐 수 있습니다.",
            "surprising_consequence":"놀랍게도 300도짜리 판에서는 물방울이 오히려 바로 사라지지 않고 떠다닙니다.",
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
        "hook_result","expectation","vapor_birth","vapor_cushion","no_contact",
        "heat_blocked","paradox_shield","glide","name","payoff",
    ]
    png={k:save_panel(k,k,assets/f"{k}.png",args.font) for k in kinds}

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
    plans=[
        ("s_hook",[
            phrase("HOOK",hook,winner.strategy),
            phrase("CRISIS","더 뜨거우면 더 빨리 없어질 것 같은데, 왜 반대일까요?"),
        ],[
            beat(source_video,hook.split()[0],"real_300c_result","hook_result","video","concept",
                 "a real scientific experiment showing water transforming into a Leidenfrost droplet on a 300 degree Celsius superheated plate",
                 f"실제 실험 영상이 첫 훅 '{hook}'에 나온 뜨거운 판과 물방울 현상을 직접 보여주는 모습",VIDEO_ATTRIBUTION),
            beat(png["hook_result"],"사라지지","levitating_result","hook_diagram","result","concept",
                 "an educational diagram of a water droplet floating above a red hot plate instead of vanishing",
                 "뜨거운 판 위에서 물방울이 바로 사라지지 않고 떠 있는 결과를 크게 보여주는 모습"),
            beat(png["expectation"],"더 뜨거우면","intuitive_expectation","expectation","hotter_vanishes","concept",
                 "an educational diagram showing the expectation that hotter surface means faster evaporation",
                 "더 뜨거우면 물이 더 빨리 사라질 것이라는 직관적 예상을 보여주는 모습"),
        ]),
        ("s_reveal",[
            phrase("REVEAL","물방울 밑에서는 수증기가 먼저 생겨 아주 얇은 쿠션을 만듭니다."),
        ],[
            beat(png["vapor_birth"],"물방울 밑에서는","vapor_birth","vapor_layer","birth","concept",
                 "an educational cross section diagram of vapor forming under a water droplet above a hot plate",
                 "물방울 아래에서 수증기가 만들어지는 단면 모습"),
            beat(png["vapor_cushion"],"쿠션","vapor_cushion","vapor_layer","cushion","state",
                 "an educational cross section diagram of a water droplet supported by a thin vapor cushion above a hot plate",
                 "물방울과 뜨거운 판 사이에 얇은 수증기 쿠션이 생긴 모습"),
        ]),
        ("s_explain",[
            phrase("EXPLANATION","그 증기층 때문에 물방울은 뜨거운 금속에 직접 닿지 않습니다. 그래서 열이 바로 전달되지 않습니다."),
        ],[
            beat(png["no_contact"],"그 증기층","no_direct_contact","insulation","no_contact","concept",
                 "an educational diagram showing a water droplet separated from a hot metal surface by vapor with no direct contact",
                 "수증기층 때문에 물방울이 뜨거운 금속에 직접 닿지 않는 모습"),
            beat(png["heat_blocked"],"열이 바로","reduced_heat_transfer","insulation","heat_blocked","state",
                 "an educational diagram showing heat transfer interrupted by a vapor layer under a water droplet",
                 "수증기층이 뜨거운 판에서 물방울로 바로 이어지는 열 전달을 줄이는 모습"),
        ]),
        ("s_twist",[
            phrase("TWIST","그래서 판이 더 뜨거워졌는데도 물방울은 잠깐 보호됩니다. 팬 위를 미끄러지는 움직임도 이 증기층이 받쳐 주기 때문입니다."),
        ],[
            beat(png["paradox_shield"],"더 뜨거워졌는데도","hotter_but_protected","paradox","shield","concept",
                 "an educational diagram showing a water droplet protected above an extremely hot plate by a vapor layer",
                 "판이 더 뜨거운데도 수증기층이 물방울을 잠깐 보호하는 역설적인 모습"),
            beat(png["glide"],"미끄러지는","skittering_motion","glide","path","concept",
                 "an educational diagram of a Leidenfrost water droplet skittering sideways across a hot plate on vapor",
                 "수증기층 위에서 물방울이 팬 표면을 미끄러지듯 이동하는 모습"),
        ]),
        ("s_end",[
            phrase("PAYOFF","이게 라이덴프로스트 효과입니다. 충분히 뜨거운 표면에서는 물이 바로 사라지는 대신, 자기 수증기 위에 잠깐 떠 있게 됩니다."),
        ],[
            beat(png["name"],"라이덴프로스트 효과","effect_name","payoff","name","concept",
                 "an educational diagram of the Leidenfrost effect with a droplet floating above a hot plate on vapor",
                 "물방울이 수증기 위에 뜬 현상을 라이덴프로스트 효과라고 정리하는 모습"),
            beat(png["payoff"],"자기 수증기 위에","final_mechanism","payoff","mechanism","state",
                 "an educational payoff diagram showing a water droplet floating on its own vapor above a sufficiently hot surface",
                 "충분히 뜨거운 표면에서 물방울이 자기 수증기 위에 떠 있는 최종 원리를 보여주는 모습"),
        ]),
    ]

    scenes=[]
    for sid,narr_plan,beats in plans:
        # Pydantic requires increasing authored starts; real starts are replaced
        # from measured TTS cues during strict meaningful-change rendering.
        for i,b in enumerate(beats): b["start"]=float(i)
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
        })

    manifest={
        "title":"300도 판에서 물방울이 사라지지 않는 이유",
        "width":1080,"height":1920,"fps":30,
        "overlay_title":"300도에서 물방울이 뜬다",
        "max_visual_recovery_attempts":2,
        "strict_source_diversity":False,
        "strict_meaningful_visual_changes":True,
        "strict_retention_contract":True,
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

나머지 설명 도식은 이 제작 스크립트가 직접 생성했습니다.
"""
    Path("examples/leidenfrost_effect_upload_description.txt").write_text(desc,encoding="utf-8")
    print("LEIDENFROST_MANIFEST_READY=examples/leidenfrost_effect.json")


if __name__=="__main__":
    main()
