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
VIDEO_FILE_MID="Underwater-Leidenfrost-nanochemistry-for-creation-of-size-tailored-zinc-peroxide-cancer-ncomms15319-s3.ogv"
VIDEO_PAGE_MID="https://commons.wikimedia.org/wiki/File:Underwater-Leidenfrost-nanochemistry-for-creation-of-size-tailored-zinc-peroxide-cancer-ncomms15319-s3.ogv"
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


def download_required_video(out:Path, filename:str=VIDEO_FILE, min_duration:float=2.5, log_label:str="LEIDENFROST_VIDEO_READY")->Path:
    out.parent.mkdir(parents=True,exist_ok=True)
    if out.is_file() and out.stat().st_size>50_000:
        return out
    encoded=urllib.parse.quote(filename.replace(" ","_"),safe="._-()")
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
            if duration<min_duration:
                raise RuntimeError(f"source video too short: {duration} < {min_duration}")
            print(f"{log_label}={out} duration={duration:.3f}s sha256={sha(out)}")
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
    elif kind=="skid_contrast":
        d.rectangle((45,45,935,905),fill="#111820")
        d.rounded_rectangle((85,150,440,760),radius=32,fill="#f7dddd",outline=RED,width=8)
        d.rounded_rectangle((540,150,895,760),radius=32,fill="#dceeff",outline=BLUE,width=8)
        d.text((262,245),"사라짐",font=f38,fill=RED,anchor="mm")
        d.text((718,245),"실제로는",font=f38,fill=BLUE,anchor="mm")
        for x in (185,265,345):
            d.line((x,540,x,350),fill=GREY,width=12)
            d.polygon([(x,320),(x-18,360),(x+18,360)],fill=GREY)
        d.line((130,300,390,610),fill=RED,width=24)
        d.line((130,610,390,300),fill=RED,width=24)
        d.ellipse((620,365,760,505),fill=BLUE,outline=WHITE,width=7)
        d.arc((595,340,855,650),start=200,end=40,fill=CYAN,width=18)
        d.polygon([(850,430),(800,405),(815,460)],fill=CYAN)
        d.text((718,650),"미끄러짐",font=f38,fill=WHITE,anchor="mm")
    elif kind=="expectation":
        d.text((490,235),"보통 예상",font=f52,fill=INK,anchor="mm")
        hot_plate(d,660); droplet(d,330,475,75)
        for x in (530,620,710):
            d.line((x,560,x,390),fill=GREY,width=12)
            d.polygon([(x,350),(x-18,395),(x+18,395)],fill=GREY)
        d.text((650,475),"더 뜨거움\n→ 더 빨리 사라짐?",font=f38,fill=INK,anchor="mm",align="center")
    elif kind=="question_gap":
        d.rectangle((45,45,935,905),fill="#17191c")
        d.rounded_rectangle((90,150,430,760),radius=35,fill="#f7dddd",outline=RED,width=8)
        d.rounded_rectangle((550,150,890,760),radius=35,fill="#dceeff",outline=BLUE,width=8)
        d.text((260,260),"더 뜨거움",font=f38,fill=RED,anchor="mm")
        d.text((720,260),"그런데",font=f38,fill=BLUE,anchor="mm")
        d.text((260,480),"더 빨리\n사라져야?",font=f38,fill=INK,anchor="mm",align="center")
        d.text((720,475),"왜\n떠 있지?",font=f52,fill=INK,anchor="mm",align="center")
    elif kind=="vapor_hint":
        d.rectangle((45,45,935,905),fill="#0f1f2a")
        hot_plate(d,735)
        droplet(d,490,345,120,fill=BLUE)
        d.ellipse((415,565,565,655),fill=CYAN,outline=WHITE,width=7)
        d.text((490,610),"수증기?",font=f38,fill=INK,anchor="mm")
        d.text((490,210),"물방울 밑에 생기는 것",font=f38,fill=WHITE,anchor="mm")
    elif kind=="vapor_birth":
        hot_plate(d,690); droplet(d,490,390,110)
        for x in (390,450,510,570,630):
            d.ellipse((x-22,585,x+22,630),fill=CYAN,outline=INK,width=4)
        d.text((490,245),"물방울 아래에서 수증기 생성",font=f38,fill=INK,anchor="mm")
    elif kind=="vapor_expand":
        d.rectangle((45,45,935,905),fill="#dff6fb")
        hot_plate(d,735)
        for x,y,r in [(220,560,55),(340,500,70),(490,555,90),(650,490,65),(770,565,50)]:
            d.ellipse((x-r,y-r,x+r,y+r),fill=CYAN,outline=INK,width=6)
        d.text((490,210),"수증기가 아래쪽을 채움",font=f38,fill=INK,anchor="mm")
        d.polygon([(420,675),(560,675),(600,615),(380,615)],fill=BLUE,outline=INK)
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
    elif kind=="contact_gap":
        d.rectangle((45,45,935,905),fill="#111820")
        d.ellipse((205,115,775,580),fill=BLUE,outline=WHITE,width=10)
        d.rounded_rectangle((160,600,820,690),radius=30,fill=CYAN,outline=WHITE,width=6)
        d.rounded_rectangle((80,735,900,835),radius=22,fill=RED,outline=WHITE,width=7)
        d.line((150,525,830,725),fill="#ff5252",width=26)
        d.line((150,725,830,525),fill="#ff5252",width=26)
        d.text((490,675),"직접 접촉 X",font=f38,fill=WHITE,anchor="mm")
    elif kind=="paradox_shield":
        d.rectangle((45,45,935,905),fill="#e54f3d")
        d.polygon([(490,125),(790,250),(735,610),(490,790),(245,610),(190,250)],
                  fill="#dff6fb",outline=WHITE)
        droplet(d,490,405,105,fill=BLUE)
        d.text((490,205),"HOT",font=f52,fill=RED,anchor="mm")
        d.text((490,690),"더 뜨거운데 잠깐 보호됨",font=f38,fill=INK,anchor="mm")
    elif kind=="protected_drop":
        d.rectangle((45,45,935,905),fill="#dceeff")
        d.ellipse((245,150,735,650),fill=WHITE,outline=BLUE,width=14)
        droplet(d,490,385,115)
        d.arc((250,430,730,790),start=190,end=350,fill=CYAN,width=32)
        d.text((490,765),"증기층이 받쳐 줌",font=f38,fill=INK,anchor="mm")
    elif kind=="glide":
        d.rectangle((45,45,935,905),fill="#1c1f24")
        d.ellipse((110,105,870,865),fill="#454b52",outline=WHITE,width=10)
        d.ellipse((230,290,410,470),fill=BLUE,outline=WHITE,width=7)
        d.arc((235,255,790,720),start=195,end=35,fill=CYAN,width=20)
        d.polygon([(785,380),(725,355),(745,420)],fill=CYAN)
        d.text((490,760),"팬 위를 미끄러짐",font=f38,fill=WHITE,anchor="mm")
    elif kind=="support_force":
        d.rectangle((45,45,935,905),fill="#182d38")
        d.ellipse((275,140,705,570),fill=BLUE,outline=WHITE,width=10)
        d.rounded_rectangle((250,610,730,685),radius=28,fill=CYAN,outline=WHITE,width=6)
        for x in (340,490,640):
            d.line((x,760,x,700),fill=YELLOW,width=18)
            d.polygon([(x,675),(x-24,715),(x+24,715)],fill=YELLOW)
        d.text((490,820),"수증기가 아래에서 받쳐 줌",font=f38,fill=WHITE,anchor="mm")
    elif kind=="name":
        d.rectangle((45,45,935,905),fill="#101820")
        d.text((490,235),"Leidenfrost",font=f52,fill=WHITE,anchor="mm")
        d.text((490,325),"라이덴프로스트 효과",font=f38,fill=CYAN,anchor="mm")
        droplet(d,490,540,105,fill=BLUE)
        d.rounded_rectangle((315,690,665,760),radius=25,fill=CYAN,outline=WHITE,width=5)
    elif kind=="threshold":
        d.rectangle((45,45,935,905),fill="#fff0df")
        d.rounded_rectangle((175,150,300,770),radius=55,fill=WHITE,outline=INK,width=8)
        d.rectangle((210,360,265,730),fill=RED)
        d.ellipse((185,690,290,795),fill=RED,outline=INK,width=6)
        d.text((500,330),"충분히 뜨거움",font=f52,fill=INK,anchor="lm")
        d.text((500,505),"증기층 유지",font=f52,fill=RED,anchor="lm")
    elif kind=="payoff":
        d.rectangle((45,45,935,905),fill="#dff6fb")
        hot_plate(d,735); droplet(d,490,350,125)
        d.rounded_rectangle((250,560,730,650),radius=35,fill=CYAN,outline=INK,width=7)
        d.line((170,475,330,475),fill=GREY,width=12)
        d.polygon([(340,475),(305,450),(305,500)],fill=GREY)
        d.text((490,205),"뜨거운 표면 → 증기 쿠션 → 떠 있는 물방울",font=f30,fill=INK,anchor="mm")
        d.text((490,825),"바로 사라지는 대신 잠깐 뜸",font=f38,fill=INK,anchor="mm")
    else:
        raise ValueError(kind)
    out.parent.mkdir(parents=True,exist_ok=True)
    im.save(out,quality=95)
    return out


def save_motion_clip(kind:str,out:Path,font_path:str|None,duration:float=3.2,fps:int=30)->Path:
    """Generate semantic motion, never crop/zoom motion.

    Each frame changes the represented physical state itself: vapor forms
    and spreads, or the droplet translates across the pan. This is the
    opposite of faking cadence by moving a camera over one still.
    """
    frames=out.parent/(out.stem+"_frames")
    frames.mkdir(parents=True,exist_ok=True)
    total=max(2,int(duration*fps))
    f38=get_font(font_path,38)
    for i in range(total):
        t=i/(total-1)
        im,d=canvas()
        if kind=="vapor_cushion_motion":
            hot_plate(d,735)
            droplet(d,490,350-int(25*t),115)
            # Vapor grows from separate bubbles into a continuous cushion.
            for j,x in enumerate((330,410,490,570,650)):
                r=int(18+32*min(1,max(0,t*1.5-j*0.08)))
                y=int(625-18*t*((j%2)*2-1))
                d.ellipse((x-r,y-r//2,x+r,y+r//2),fill=CYAN,outline=INK,width=4)
            if t>0.45:
                alpha=(t-0.45)/0.55
                left=int(360-90*alpha); right=int(620+90*alpha)
                d.rounded_rectangle((left,575,right,650),radius=28,fill=CYAN,outline=INK,width=5)
            d.text((490,210),"수증기가 이어져 쿠션이 됨",font=f38,fill=INK,anchor="mm")
        elif kind=="glide_motion":
            d.rectangle((45,45,935,905),fill="#1c1f24")
            d.ellipse((110,105,870,865),fill="#454b52",outline=WHITE,width=10)
            x=int(220+540*t)
            y=int(470-90*__import__("math").sin(t*3.14159))
            d.ellipse((x-88,y-88,x+88,y+88),fill=BLUE,outline=WHITE,width=7)
            for k in range(4):
                px=x-int(55+55*k)
                if px>130:
                    d.ellipse((px-18,y+75,px+18,y+98),fill=CYAN)
            d.line((180,690,800,690),fill=CYAN,width=12)
            d.polygon([(815,690),(775,665),(775,715)],fill=CYAN)
            d.text((490,780),"수증기 위에서 실제 위치가 바뀜",font=f38,fill=WHITE,anchor="mm")
        elif kind=="heat_blocked_motion":
            d.rectangle((45,45,935,905),fill="#2b1716")
            d.rounded_rectangle((90,690,890,825),radius=25,fill="#f05a48",outline=WHITE,width=7)
            d.rounded_rectangle((260,515,720,610),radius=35,fill=CYAN,outline=WHITE,width=7)
            droplet(d,490,300,120,fill="#5ca7ef")
            # Heat arrows rise from the plate each cycle but visibly stall and
            # fade right at the vapor-layer boundary -- the physical claim
            # itself (heat blocked from reaching the droplet), not decoration.
            cycle=(t*2.0)%1.0
            for k,x in enumerate((280,390,500,610,720)):
                rise=max(0.0,min(1.0,cycle*1.6-k*0.12))
                if rise<=0:
                    continue
                y_start=675
                y_stop=int(675-95*min(rise,0.82))
                d.line((x,y_start,x,y_stop),fill=YELLOW,width=14)
                if rise<0.82:
                    d.polygon([(x,y_stop-14),(x-18,y_stop+14),(x+18,y_stop+14)],fill=YELLOW)
            d.text((490,470),"수증기층에서 열 흐름이 꺾임",font=f38,fill=WHITE,anchor="mm")
        elif kind=="payoff_motion":
            d.rectangle((45,45,935,905),fill="#dff6fb")
            hot_plate(d,735)
            lift=int(18*__import__("math").sin(t*3.14159))
            droplet(d,490,365-lift,120)
            width=int(240+220*t)
            d.rounded_rectangle((490-width//2,570,490+width//2,650),radius=30,fill=CYAN,outline=INK,width=7)
            for x in (390,490,590):
                h=int(30+45*t)
                d.line((x,690,x,690-h),fill=YELLOW,width=12)
                d.polygon([(x,690-h-14),(x-14,690-h+10),(x+14,690-h+10)],fill=YELLOW)
            d.text((490,210),"자기 수증기 위에 떠 있음",font=f38,fill=INK,anchor="mm")
        else:
            raise ValueError(kind)
        im.save(frames/f"{i:04d}.png")
    out.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run([
        "ffmpeg","-y","-framerate",str(fps),"-i",str(frames/"%04d.png"),
        "-c:v","libx264","-pix_fmt","yuv420p","-movflags","+faststart",str(out)
    ],check=True,capture_output=True,timeout=120)
    return out


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
         qa_label:str,req:str,attribution:str|None=None, *,
         presentation_kind:str|None=None, hero_visual:bool=False,
         internal_text:str|None=None, source_start:float=0.0,
         sfx_asset:Path|None=None, sfx_gain_db:float=-16.0):
    digest=sha(asset)
    if presentation_kind is None:
        presentation_kind = "physical_animation" if asset.suffix.lower() in {".mp4",".webm",".mov",".mkv",".ogv",".avi"} else "explanatory_diagram"
    if internal_text is None:
        internal_text = "none" if presentation_kind in {"real_motion","real_still"} else "label"
    payload={
        "start":0.0,
        "asset":str(asset),
        "attribution":attribution,
        "presentation_kind":presentation_kind,
        "hero_visual":hero_visual,
        "internal_text":internal_text,
        "source_start":source_start,
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
    if sfx_asset is not None:
        payload["sfx_asset"]=str(sfx_asset)
        payload["sfx_gain_db"]=sfx_gain_db
    return payload


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--font",default=None);args=ap.parse_args()
    assets=Path("assets/leidenfrost_effect"); assets.mkdir(parents=True,exist_ok=True)
    source_video=download_required_video(assets/"source_experiment.ogv")
    source_video_mid=download_required_video(
        assets/"source_underwater_vapor.ogv",
        VIDEO_FILE_MID,
        min_duration=30.0,
        log_label="LEIDENFROST_MID_VIDEO_READY",
    )

    kinds=[
        "hook_result","skid_contrast","expectation","question_gap","vapor_birth","vapor_expand","vapor_cushion",
        "vapor_hint","no_contact","contact_gap","paradox_shield","protected_drop",
        "glide","support_force","name","threshold","payoff",
    ]
    png={k:save_panel(k,k,assets/f"{k}.png",args.font) for k in kinds}

    motion={
        "vapor_cushion":save_motion_clip("vapor_cushion_motion",assets/"vapor_cushion_motion.mp4",args.font,3.2),
        "glide":save_motion_clip("glide_motion",assets/"glide_motion.mp4",args.font,3.4),
        "payoff":save_motion_clip("payoff_motion",assets/"payoff_motion.mp4",args.font,3.4),
        "heat_blocked":save_motion_clip("heat_blocked_motion",assets/"heat_blocked_motion.mp4",args.font,3.0),
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
                 f"실제 실험 영상이 첫 훅 '{hook}'에 나온 뜨거운 판과 물방울 현상을 직접 보여주는 모습",
                 VIDEO_ATTRIBUTION,presentation_kind="real_motion",hero_visual=True,internal_text="none"),
            beat(motion["glide"],"끓어 없어지는 대신","skittering_motion","hook_result","skid","state",
                 "a top down dark pan animation with a Leidenfrost droplet visibly changing position along a curved path",
                 "끓어 없어지는 대신 물방울이 실제로 위치를 바꾸며 미끄러지는 현상을 보여주는 움직임",
                 presentation_kind="physical_animation",internal_text="label"),
            beat(motion["payoff"],"왜 안 사라질까요","floating_anomaly","hook_gap","floating","state",
                 "a physical animation showing a water droplet lifting above a very hot plate as a vapor cushion grows underneath",
                 "더 뜨거운 표면인데도 물방울이 떠서 버티는 모순을 움직임으로 보여주는 장면",
                 presentation_kind="physical_animation",internal_text="label"),
            beat(png["vapor_hint"],"수증기입니다","early_vapor_answer","vapor_hint","hint","concept",
                 "a dark educational hint showing a single vapor pocket beneath a floating water droplet",
                 "부분 정답으로 물방울 밑에 수증기가 있다는 사실만 간단히 보여주는 모습",
                 presentation_kind="explanatory_diagram",internal_text="label"),
        ]),
        ("s_reveal",[
            phrase("INVESTIGATION","그 수증기가 물방울 아래로 퍼지면서 아주 얇은 쿠션을 만듭니다."),
        ],[
            beat(source_video_mid,"그 수증기가","real_vapor_generation","vapor_layer","real_vapor","concept",
                 "a real scientific experiment showing vapor generation and carbon fibers moving above a superheated underwater interface",
                 "실제 실험에서 뜨거운 경계면 위로 수증기 흐름과 입자 움직임이 생기는 모습을 보여주는 장면",
                 VIDEO_ATTRIBUTION,presentation_kind="real_motion",hero_visual=True,internal_text="none",source_start=8.0),
            beat(motion["vapor_cushion"],"쿠션","vapor_cushion","vapor_layer","cushion","state",
                 "an educational physical animation of a water droplet supported by a growing thin vapor cushion above a hot plate",
                 "수증기가 이어져 물방울 밑의 얇은 쿠션이 되는 과정을 움직임으로 보여주는 장면",
                 presentation_kind="physical_animation",internal_text="label"),
        ]),
        ("s_explain",[
            phrase("EXPLANATION","그 증기층 때문에 물방울은 뜨거운 금속에 직접 닿지 않습니다. 그래서 열이 바로 전달되지 않습니다."),
        ],[
            beat(motion["heat_blocked"],"그 증기층 때문에","reduced_heat_transfer","insulation","heat_blocked","state",
                 "a dark thermal physical animation showing heat flow rising from a hot plate and stalling at the vapor layer",
                 "뜨거운 판의 열 흐름이 수증기층에서 바로 이어지지 않는 과정을 움직임으로 보여주는 장면",
                 presentation_kind="physical_animation",internal_text="label"),
            beat(png["no_contact"],"직접 닿지 않습니다","no_direct_contact","insulation","no_contact","concept",
                 "an educational diagram showing a water droplet separated from a hot metal surface by vapor with no direct contact",
                 "수증기층 때문에 물방울과 뜨거운 금속의 직접 접촉이 끊긴 구조",
                 presentation_kind="explanatory_diagram",internal_text="label"),
            beat(motion["payoff"],"열이 바로 전달되지 않습니다","insulated_float","insulation","supported","state",
                 "a physical animation showing a droplet remaining lifted as the vapor layer supports it above a hot plate",
                 "직접 접촉이 줄어든 상태에서 물방울이 수증기층 위에 떠 있는 결과를 움직임으로 보여주는 장면",
                 presentation_kind="physical_animation",internal_text="label"),
        ]),
        ("s_twist",[
            phrase("TWIST","그래서 판이 더 뜨거워졌는데도 물방울은 잠깐 보호됩니다. 팬 위를 미끄러지는 움직임도 이 증기층이 받쳐 주기 때문입니다."),
        ],[
            beat(png["paradox_shield"],"더 뜨거워졌는데도","hotter_but_protected","paradox","shield","concept",
                 "a bold red and blue shield diagram showing a water droplet protected above an extremely hot plate",
                 "더 뜨거운 조건인데도 증기층이 물방울을 잠깐 보호하는 역설을 한눈에 보여주는 모습",
                 presentation_kind="explanatory_diagram",internal_text="label"),
            beat(motion["glide"],"미끄러지는 움직임","skittering_motion","glide","path","state",
                 "a top down physical animation with a Leidenfrost droplet changing position along a curved skating path",
                 "물방울이 팬 위에서 실제 위치를 바꾸며 곡선을 따라 미끄러지는 움직임",
                 presentation_kind="physical_animation",internal_text="label"),
            beat(motion["payoff"],"증기층이 받쳐","vapor_support_force","glide","support","state",
                 "a physical animation showing the vapor cushion expanding beneath and supporting the floating droplet",
                 "수증기층이 아래에서 물방울을 받쳐 떠 있게 하는 상태를 움직임으로 보여주는 장면",
                 presentation_kind="physical_animation",internal_text="label"),
        ]),
        ("s_end",[
            phrase("PAYOFF","이게 라이덴프로스트 효과입니다. 충분히 뜨거운 표면에서는 물이 바로 사라지는 대신, 자기 수증기 위에 잠깐 떠 있게 됩니다."),
        ],[
            beat(motion["payoff"],"라이덴프로스트 효과입니다","final_mechanism","payoff","mechanism","state",
                 "a bright physical animation showing a droplet floating on a growing vapor cushion above a hot surface",
                 "라이덴프로스트 효과의 핵심 구조를 마지막에 크게 움직임으로 보여주는 장면",
                 presentation_kind="physical_animation",hero_visual=True,internal_text="label"),
            beat(source_video,"자기 수증기 위에","real_final_result","payoff","real_callback","state",
                 "a real scientific experiment showing a Leidenfrost droplet forming and persisting on a 300 degree Celsius superheated plate",
                 "처음 봤던 실제 300도 실험으로 돌아가 물방울이 뜨는 결과를 최종 보상 화면으로 보여주는 장면",
                 VIDEO_ATTRIBUTION,presentation_kind="real_motion",hero_visual=True,internal_text="none"),
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
            "overlay_title_seconds": 2.8 if sid=="s_hook" else None,
        })

    manifest={
        "title":"300도 판에서 물방울이 사라지지 않는 이유",
        "width":1080,"height":1920,"fps":30,
        "overlay_title":"물방울이 뜬다",
        "overlay_title_mode":"first_scene_only",
        "max_visual_recovery_attempts":2,
        "strict_source_diversity":False,
        "strict_meaningful_visual_changes":True,
        "strict_retention_contract":True,
        "strict_production_quality_v2":True,
        "strict_entertainment_contract":False,
        "scenes":scenes,
    }
    Path("examples").mkdir(exist_ok=True)
    Path("examples/leidenfrost_effect.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")

    desc=f"""# 300도 판에서 물방울이 사라지지 않는 이유 — 출처

실제 실험 영상 1:
- Underwater-Leidenfrost-nanochemistry-for-creation-of-size-tailored-zinc-peroxide-cancer-ncomms15319-s2.ogv
- Authors: Elbahri M, Abdelaziz R, Disci-Zayed D, Homaeigohar S, Sosna J, Adam D, Kienle L, Dankwort T, Abdelaziz M
- Source: {VIDEO_PAGE}
- License: Creative Commons Attribution 4.0 International (CC BY 4.0)

실제 실험 영상 2:
- Underwater-Leidenfrost-nanochemistry-for-creation-of-size-tailored-zinc-peroxide-cancer-ncomms15319-s3.ogv
- Authors: Elbahri M, Abdelaziz R, Disci-Zayed D, Homaeigohar S, Sosna J, Adam D, Kienle L, Dankwort T, Abdelaziz M
- Source: {VIDEO_PAGE_MID}
- License: Creative Commons Attribution 4.0 International (CC BY 4.0)

사용 변경: 세로형 Shorts 프레임에 맞게 리사이즈/구성하고 원본 음성은 사용하지 않음.

나머지 설명 도식과 물리 애니메이션은 이 제작 스크립트가 직접 생성했습니다.
"""
    Path("examples/leidenfrost_effect_upload_description.txt").write_text(desc,encoding="utf-8")
    print("LEIDENFROST_MANIFEST_READY=examples/leidenfrost_effect.json")


if __name__=="__main__":
    main()
