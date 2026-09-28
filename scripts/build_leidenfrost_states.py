#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from shorts_studio.hook_studio import (
    HookCandidate, TopicBrief, build_story_generation_prompt,
    generate_and_judge, story_writer_system_prompt,
)

W, H = 980, 950
BLACK="#050505"; WHITE="#f7f7f2"; INK="#111111"; RED="#e34d45"
BLUE="#3f7bd9"; GREY="#69757c"; PALE="#e9eef1"; ORANGE="#ef8d32"

NEG=["a landscape photograph","a portrait of a person","unrelated food or animal content"]

CHART_FILE="Heat transfer leading to Leidenfrost effect for water at 1 atm.png"
CHART_CREDIT="Marco Guzman, Jr / Wikimedia Commons / public domain"


def sha(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def font(path:str,size:int):
    try:return ImageFont.truetype(path,size)
    except Exception:return ImageFont.load_default()


def download_commons(filename:str,target:Path)->Path:
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.is_file() and target.stat().st_size>0:return target
    encoded=urllib.parse.quote(filename.replace(" ","_"),safe="._-()")
    url=f"https://commons.wikimedia.org/wiki/Special:Redirect/file/{encoded}"
    last=None
    for attempt in range(4):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"shorts-studio/0.1 Leidenfrost production"})
            with urllib.request.urlopen(req,timeout=40) as src:data=src.read()
            if len(data)<10000:raise RuntimeError(f"download too small: {len(data)}")
            target.write_bytes(data)
            with Image.open(target) as im:im.verify()
            return target
        except Exception as exc:
            last=exc;target.unlink(missing_ok=True)
            if attempt<3:time.sleep(6*(attempt+1))
    raise RuntimeError(f"failed to download {filename!r}: {last}")


class LeidenfrostHookGenerator:
    def generate(self,brief:TopicBrief)->list[HookCandidate]:
        facts=brief.fact_by_strategy()
        texts={
            "contradiction":"팬이 더 뜨거워질수록 물방울이 오히려 더 오래 남을 수 있습니다.",
            "surprising_consequence":"아주 뜨거운 팬에서는 물방울이 사라지지 않고 미끄러지듯 도망갑니다.",
            "counterintuitive_fact":"더 뜨거운 팬 위의 물방울이 덜 뜨거운 팬보다 오래 버티기도 합니다.",
            "visible_anomaly":"아주 뜨거운 팬에 떨어진 물방울은 바닥에 붙지 않고 둥글게 떠서 움직입니다.",
            "mistaken_assumption":"팬이 뜨거울수록 물은 무조건 더 빨리 사라진다고 생각하기 쉽습니다.",
            "unresolved_cause_effect":"팬이 너무 뜨거우면 물방울 아래에 기체층이 생겨 직접 접촉이 줄어듭니다.",
        }
        return [HookCandidate(strategy=s,text=texts[s],grounded_in=facts[s]) for s in texts]


def topic_brief()->TopicBrief:
    return TopicBrief(
        topic_id="leidenfrost", familiar_subject="뜨거운 팬과 물방울",
        contradiction_fact="팬이 충분히 뜨거워지면 물방울이 더 오래 남을 수 있습니다",
        surprising_consequence_fact="아주 뜨거운 팬에서는 물방울이 빠르게 사라지지 않고 표면을 미끄러지듯 움직일 수 있습니다",
        counterintuitive_fact="더 뜨거운 표면의 물방울이 덜 뜨거운 표면의 물방울보다 오래 지속될 수 있습니다",
        anomaly_fact="충분히 뜨거운 표면에서는 물방울이 둥글게 뭉쳐 표면 위를 움직입니다",
        mistaken_assumption_fact="표면이 뜨거울수록 물방울은 항상 더 빨리 사라진다는 예상은 모든 온도 구간에서 맞지 않습니다",
        cause_effect_fact="충분히 뜨거운 표면에서는 물방울 아래에 수증기층이 생겨 액체와 표면의 직접 접촉을 줄입니다",
        payoff_text="물방울 아래의 얇은 수증기층이 직접 접촉과 열 전달을 방해해 물방울이 더 오래 지속될 수 있습니다",
        grounded_facts=[
            "이 현상은 라이덴프로스트 효과라고 불립니다",
            "수증기층은 물방울을 뜨거운 표면에서 살짝 띄우고 열 전달을 억제합니다",
            "라이덴프로스트가 시작되는 정확한 온도는 표면과 조건에 따라 달라질 수 있습니다",
        ],
    )


def select_hook():
    brief=topic_brief()
    result=generate_and_judge(brief,generator=LeidenfrostHookGenerator())
    if result.winner is None:raise RuntimeError("Prompt V2 produced no Leidenfrost hook")
    print(f"PROMPT_V2_JUDGE={result.judge_name}")
    print(f"PROMPT_V2_SELECTED_STRATEGY={result.winner.strategy}")
    print(f"PROMPT_V2_SELECTED_HOOK={result.winner.text}")
    return brief,result.winner


def base():
    return Image.new("RGB",(W,H),BLACK)


def card(d,box=(35,35,945,915),fill=WHITE):
    d.rounded_rectangle(box,radius=34,fill=fill)


def pan(d,y=610):
    d.rounded_rectangle((100,y,880,y+105),radius=34,fill="#aeb7bc",outline=INK,width=8)
    d.rectangle((390,y+105,590,y+155),fill="#727d83")
    for x in range(170,860,90):d.line((x,y+112,x+40,y+152),fill=ORANGE,width=10)


def drop(d,x,y,r=95,steam=False,shadow=True):
    if shadow:d.ellipse((x-r*.8,y+r*.82,x+r*.8,y+r*1.02),fill="#b9c0c5")
    d.ellipse((x-r,y-r,x+r,y+r),fill="#8ec5ff",outline=BLUE,width=8)
    d.ellipse((x-r*.35,y-r*.55,x-r*.02,y-r*.22),fill="#dff1ff")
    if steam:
        for dx in (-45,0,45):
            pts=[(x+dx+8*((yy//14)%2*2-1),y+r+20+yy) for yy in range(0,120,14)]
            d.line(pts,fill=GREY,width=9)


def save_panel(path:Path,kind:str,font_path:str):
    im=base();d=ImageDraw.Draw(im);card(d)
    f34=lambda:font(font_path,34);f28=lambda:font(font_path,28);f24=lambda:font(font_path,24)
    if kind=="hover_close":
        pan(d,650);drop(d,490,430,125,steam=True)
        d.line((300,610,680,610),fill=ORANGE,width=10)
        for x in range(350,680,80):d.line((x,595,x+25,570),fill=GREY,width=7)
        d.text((490,825),"팬과 물방울 사이에 빈틈",font=f34(),fill=INK,anchor="mm")
    elif kind=="hotter_compare":
        d.text((270,170),"덜 뜨거운 팬",font=f28(),fill=INK,anchor="mm");d.text((710,170),"아주 뜨거운 팬",font=f28(),fill=INK,anchor="mm")
        d.rounded_rectangle((100,600,430,690),radius=24,fill="#aeb7bc",outline=INK,width=6);d.rounded_rectangle((550,600,880,690),radius=24,fill="#aeb7bc",outline=INK,width=6)
        for x in range(140,410,70):d.line((x,705,x+25,750),fill=ORANGE,width=9)
        for x in range(590,860,55):d.line((x,705,x+30,770),fill=RED,width=12)
        for dx in (-45,0,45):d.arc((220+dx,300,330+dx,560),180,360,fill=GREY,width=12)
        drop(d,715,460,82,steam=True)
        d.text((270,825),"치익 → 빠르게 작아짐",font=f24(),fill=GREY,anchor="mm");d.text((710,825),"둥글게 떠서 움직임",font=f24(),fill=BLUE,anchor="mm")
    elif kind=="expected_faster":
        pan(d,650);drop(d,490,480,90);d.line((490,250,490,360),fill=RED,width=18);d.polygon([(490,390),(455,340),(525,340)],fill=RED)
        d.text((490,200),"더 뜨거우면",font=f34(),fill=RED,anchor="mm");d.text((490,830),"더 빨리 사라질 것 같다",font=f34(),fill=INK,anchor="mm")
    elif kind=="skitter_path":
        pan(d,650)
        for x in (250,420,600,760):drop(d,x,485,55)
        pts=[(210,410),(370,330),(540,410),(700,320),(810,390)];d.line(pts,fill=BLUE,width=12);d.polygon([(810,390),(765,360),(777,418)],fill=BLUE)
        d.text((490,820),"붙지 않고 표면을 미끄러짐",font=f34(),fill=INK,anchor="mm")
    elif kind=="contact_boil":
        pan(d,650);d.ellipse((330,520,650,660),fill="#8ec5ff",outline=BLUE,width=6)
        for x in range(360,650,55):d.arc((x-50,250,x+50,570),180,360,fill=GREY,width=12)
        d.text((490,825),"직접 닿으면 열이 빠르게 들어옴",font=f28(),fill=INK,anchor="mm")
    elif kind=="vapor_layer":
        pan(d,690);drop(d,490,420,120,shadow=False);d.rounded_rectangle((290,610,690,665),radius=20,fill="#dce6ec",outline=GREY,width=5)
        for x in range(330,660,60):d.line((x,640,x+20,615),fill=GREY,width=6)
        d.text((490,640),"수증기층",font=f28(),fill=INK,anchor="mm");d.text((490,835),"직접 접촉을 막는 얇은 기체층",font=f34(),fill=INK,anchor="mm")
    elif kind=="heat_block":
        pan(d,690);drop(d,490,415,115,shadow=False);d.rounded_rectangle((300,605,680,665),radius=20,fill="#dce6ec",outline=GREY,width=5)
        for x in (370,450,530,610):
            d.line((x,760,x,690),fill=RED,width=14);d.polygon([(x,670),(x-20,705),(x+20,705)],fill=RED);d.line((x,605,x,555),fill=GREY,width=7)
        d.text((490,830),"열 전달이 방해됨",font=f34(),fill=INK,anchor="mm")
    elif kind=="shield":
        pan(d,690);drop(d,490,410,110,shadow=False);d.arc((270,510,710,760),180,360,fill=BLUE,width=24);d.text((490,810),"증기 방패",font=font(font_path,42),fill=BLUE,anchor="mm")
    elif kind=="payoff":
        pan(d,680);drop(d,490,410,105,steam=True);d.text((490,180),"더 뜨거움",font=f34(),fill=RED,anchor="mm")
        d.text((490,800),"↓",font=font(font_path,56),fill=INK,anchor="mm");d.text((490,860),"수증기층 때문에 더 오래 버팀",font=f34(),fill=INK,anchor="mm")
    else:raise ValueError(kind)
    im.save(path)


def make_opening_motion(path:Path,font_path:str):
    frames=path.parent/"opening_frames"
    if frames.exists():shutil.rmtree(frames)
    frames.mkdir(parents=True)
    fps=24;count=round(fps*3.0)
    for i in range(count):
        t=i/max(1,count-1);im=base();d=ImageDraw.Draw(im);card(d);pan(d,660)
        x=190+600*t;y=455-35*math.sin(t*math.pi*4);drop(d,x,y,82,steam=True)
        d.text((490,150),"물방울이 팬 위를 미끄러집니다",font=font(font_path,34),fill=INK,anchor="mm")
        im.save(frames/f"f_{i:04d}.png")
    subprocess.run(["ffmpeg","-y","-framerate",str(fps),"-i",str(frames/"f_%04d.png"),"-an","-c:v","libx264","-pix_fmt","yuv420p",str(path)],check=True,capture_output=True)
    shutil.rmtree(frames)


def chart_panel(source:Path,target:Path,font_path:str):
    im=base();d=ImageDraw.Draw(im);card(d)
    with Image.open(source) as src:chart=ImageOps.contain(src.convert("RGB"),(820,560),method=Image.Resampling.LANCZOS)
    im.paste(chart,((W-chart.width)//2,180))
    d.rounded_rectangle((90,760,890,860),radius=24,fill="#fff3d8",outline=ORANGE,width=5)
    d.text((490,810),"어느 구간부터 물방울 수명이 다시 길어집니다",font=font(font_path,28),fill=INK,anchor="mm")
    im.save(target)


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--font",required=True);args=ap.parse_args()
    assets=Path("assets/leidenfrost");assets.mkdir(parents=True,exist_ok=True);build=Path("build");build.mkdir(exist_ok=True)
    brief,hook=select_hook()
    prompt=build_story_generation_prompt(brief,hook,uncertainty_notes=["라이덴프로스트가 시작되는 정확한 온도는 표면 재질과 조건에 따라 달라질 수 있습니다"])
    (build/"leidenfrost_story_prompt.txt").write_text(story_writer_system_prompt()+"\n\n"+prompt+"\n",encoding="utf-8")
    print("STORY_PROMPT_V3_READY=build/leidenfrost_story_prompt.txt")

    motion=assets/"opening_motion.mp4";make_opening_motion(motion,args.font)
    chart_src=download_commons(CHART_FILE,assets/"source"/"heat_transfer_public_domain.png")
    chart=assets/"heat_transfer_evidence.png";chart_panel(chart_src,chart,args.font)

    kinds=["hover_close","hotter_compare","expected_faster","skitter_path","contact_boil","vapor_layer","heat_block","shield","payoff"]
    panels={}
    for kind in kinds:
        p=assets/f"{kind}.png";save_panel(p,kind,args.font);panels[kind]=p

    scenes=[
      ("s_hook",[("HOOK",hook.text,hook.strategy)],[
        ("팬이 더","moving_demo",motion,"an educational animation of a blue water droplet visibly moving across a very hot metal pan","뜨거운 팬 위에서 물방울이 실제로 움직이는 장면"),
        ("물방울이","hover_close",panels["hover_close"],"a close educational diagram of a water droplet hovering above a hot pan with vapor underneath","물방울과 팬 사이의 빈틈과 수증기가 보이는 확대 장면"),
        ("더 오래","hotter_compare",panels["hotter_compare"],"a side-by-side educational comparison of water on a moderately hot pan versus a much hotter pan","덜 뜨거운 팬과 아주 뜨거운 팬의 물방울 행동이 비교되는 장면")]),
      ("s_setup",[("SETUP","보통은 더 뜨거우면 물이 더 빨리 사라질 것 같죠.",None),("REVEAL","그런데 아주 뜨거운 팬에서는 물방울이 달라붙지 않고 굴러다닙니다.",None)],[
        ("보통은","expected_faster",panels["expected_faster"],"an educational diagram showing the intuitive expectation that more heat makes water disappear faster","더 뜨거우면 물이 더 빨리 사라질 것이라는 예상"),
        ("그런데","skitter_path",panels["skitter_path"],"an educational diagram showing a water droplet skittering across a hot pan instead of sticking","아주 뜨거운 팬에서 물방울이 달라붙지 않고 이동하는 모습"),
        ("굴러다닙니다","heat_curve",chart,"a scientific graph showing droplet evaporation time changing non-monotonically with hot plate temperature","팬 온도에 따라 물방울이 사라지는 시간이 단순하게 줄지만은 않는 실제 그래프")]),
      ("s_crisis",[("CRISIS","약간 뜨거울 때는 물이 팬에 직접 닿아 치익 하고 빠르게 증발합니다. 그런데 왜 더 뜨거운 팬에서는 더 오래 버틸까요?",None)],[
        ("약간 뜨거울","contact_boil",panels["contact_boil"],"an educational diagram of water directly contacting a hot pan and boiling rapidly","물이 팬에 직접 닿아 빠르게 끓고 증발하는 모습"),
        ("그런데 왜","vapor_layer",panels["vapor_layer"],"a clear diagram of a water droplet floating above a hot pan on a thin vapor layer","물방울 아래에 얇은 수증기층이 생겨 팬과 떨어진 모습")]),
      ("s_explain",[("EXPLANATION","팬에 닿은 물의 맨 아래가 순간적으로 수증기가 됩니다. 이 얇은 수증기층이 물방울을 팬에서 살짝 띄웁니다.",None)],[
        ("맨 아래가","vapor_layer",panels["vapor_layer"],"a clear educational diagram of vapor forming under a water droplet on a hot pan","물방울 아래에서 수증기가 생기는 모습"),
        ("살짝 띄웁니다","heat_block",panels["heat_block"],"an educational heat-transfer diagram showing a vapor gap separating a water droplet from a hot pan","수증기층이 물방울과 팬의 직접 접촉을 막는 모습")]),
      ("s_twist",[("TWIST","열은 더 센데, 물방울은 팬에 직접 닿지 않게 된 겁니다.",None)],[
        ("열은 더","heat_block",panels["heat_block"],"an educational diagram showing strong heat below a vapor-insulated water droplet","팬의 열은 강하지만 수증기층 때문에 물방울에 바로 전달되지 않는 모습"),
        ("직접 닿지","shield",panels["shield"],"an educational diagram of a blue vapor shield between a droplet and a hot pan","수증기층이 방패처럼 물방울과 팬 사이를 막는 모습")]),
      ("s_synthesis",[("SYNTHESIS","이 기체층이 열 전달을 방해해서 물방울은 미끄러지듯 움직이고 더 천천히 사라집니다.",None)],[
        ("열 전달을","shield",panels["shield"],"an educational diagram showing an insulating vapor cushion beneath a water droplet","수증기층이 열 전달을 막는 모습"),
        ("미끄러지듯","skitter_path",panels["skitter_path"],"an educational diagram showing a water droplet moving sideways across a hot pan","물방울이 팬 표면을 미끄러지듯 움직이는 모습")]),
      ("s_payoff",[("PAYOFF","즉, 더 뜨거워서 오래 버티는 게 아니라 너무 뜨거워 생긴 수증기층이 방패가 되는 겁니다.",None)],[
        ("더 뜨거워서","hotter_compare",panels["hotter_compare"],"a side-by-side comparison of water behavior on two differently heated pans","덜 뜨거운 팬과 아주 뜨거운 팬에서 물방울의 차이를 다시 비교한 모습"),
        ("수증기층이","payoff",panels["payoff"],"an educational payoff diagram showing a water droplet lasting above a very hot pan because of a vapor layer","너무 뜨거워 생긴 수증기층 때문에 물방울이 오래 버티는 최종 원리")]),
    ]

    outscenes=[]
    for si,(sid,phrases,beats) in enumerate(scenes):
        vb=[]
        for bi,(cue,role,path,label,req) in enumerate(beats):
            digest=sha(Path(path))
            vb.append({
              "start":float(bi*2),"asset":str(path),"attribution":CHART_CREDIT if Path(path)==chart else None,
              "visual_change":{"kind":"concept" if bi==0 else "state","concept_id":sid,"state_id":f"{sid}:{role}:{bi}","narration_cue":cue,"added_information":label,"source_sha256":digest},
              "visual_qa_requirements":[req],"visual_qa_labels":[label],"visual_qa_negative_labels":NEG,
              "visual_qa_expected_sha256":[digest],"info_role":role,
            })
        plan=[]
        for role,text,hook_type in phrases:
            item={"role":role,"text":text}
            if role=="HOOK":item["hook_type"]=hook_type
            plan.append(item)
        outscenes.append({
          "id":sid,"narration":" ".join(x[1] for x in phrases),"visual_description":"; ".join(x[4] for x in beats),
          "asset":vb[0]["asset"],"attribution":vb[0].get("attribution"),"visual_qa_requirements":[x[4] for x in beats],
          "visual_qa_labels":[x[3] for x in beats],"visual_qa_negative_labels":NEG,
          "visual_qa_expected_sha256":[vb[0]["visual_qa_expected_sha256"][0]],"visual_beats":vb,"narration_plan":plan,
          "factual_notes":["충분히 뜨거운 표면에서는 물방울 아래에 수증기층이 형성될 수 있습니다.","수증기층은 액체와 뜨거운 표면의 직접 접촉을 줄이고 열 전달을 방해합니다."],
          "overlay_title":"더 뜨거운데 더 오래?" if si==0 else None,
        })

    manifest={"title":"더 뜨거운 팬에서 물방울이 오래 버티는 이유","width":1080,"height":1920,"fps":30,
      "overlay_title":None,"strict_source_diversity":False,"strict_meaningful_visual_changes":True,
      "strict_retention_contract":True,"scenes":outscenes}
    Path("examples/leidenfrost.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print("LEIDENFROST_MANIFEST_READY=examples/leidenfrost.json")
    print("MOVING_VISUAL_READY="+str(motion))
    print("PUBLIC_DOMAIN_CHART_READY="+str(chart))


if __name__=="__main__":main()
