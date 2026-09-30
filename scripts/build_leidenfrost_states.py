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

import argparse, hashlib, json, math, subprocess, time, urllib.parse, urllib.request
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
    # One consistent dark physical-visualization canvas. The renderer already
    # provides the outer black Shorts frame, so an extra white rounded "slide"
    # inside the media box only makes the video look like a deck.
    im=Image.new("RGB",(W,H),"#0b1117")
    return im,ImageDraw.Draw(im)


def droplet(d,cx,cy,r=85,fill=BLUE):
    # A Leidenfrost drop reads much more naturally as a rounded bead than as
    # the old teardrop/pin icon. Add one restrained highlight for volume.
    outline="#d9efff"
    d.ellipse((cx-r,cy-r,cx+r,cy+r),fill=fill,outline=outline,width=max(4,r//18))
    hr=max(8,r//5)
    d.ellipse((cx-r//2,cy-r//2,cx-r//2+hr,cy-r//2+hr),fill="#b9dcff")


def hot_plate(d,y=690,heat=1.0):
    # Dark metal body + a hot glowing top edge: closer to a physical surface
    # than a flat red cartoon bar.
    d.rounded_rectangle((70,y,910,y+105),radius=22,fill="#39424a",outline="#78838c",width=5)
    glow="#ff5d4d" if heat<1.25 else "#ff3b30"
    d.line((90,y+8,890,y+8),fill=glow,width=14)
    if heat>1.05:
        d.line((115,y+27,865,y+27),fill="#ff9b62",width=6)


def vapor_band(d,left=280,right=700,y=575,h=76):
    d.rounded_rectangle((left,y,right,y+h),radius=h//2,fill="#66d6e8",outline="#c9f7ff",width=4)


def upward_heat(d,x,y0,y1,alpha=1.0):
    c="#ffd166"
    d.line((x,y0,x,y1),fill=c,width=max(8,int(14*alpha)))
    d.polygon([(x,y1-16),(x-16,y1+12),(x+16,y1+12)],fill=c)


def save_panel(kind:str,label:str,out:Path,font_path:str|None):
    im,d=canvas()
    f34=get_font(font_path,34); f46=get_font(font_path,46)

    if kind=="hook_result":
        hot_plate(d,710,1.25); vapor_band(d,310,670,575,72); droplet(d,490,400,112)
        d.text((490,150),"300°C",font=f46,fill="#ff9b62",anchor="mm")
    elif kind=="skid_contrast":
        # Left: expected disappearance. Right: observed glide. No red X or
        # boxed cards; the physical states themselves carry the contrast.
        hot_plate(d,700,1.15)
        for rr,a in ((82,1),(56,.7),(30,.45)):
            c="#5f7d8f" if a<1 else "#78a6bf"
            d.ellipse((225-rr,390-rr,225+rr,390+rr),outline=c,width=7)
        d.ellipse((610,330,780,500),fill=BLUE,outline="#d9efff",width=6)
        d.arc((555,285,865,620),start=190,end=35,fill=CYAN,width=18)
        d.polygon([(850,390),(804,365),(817,418)],fill=CYAN)
    elif kind=="expectation":
        hot_plate(d,700,1.2); droplet(d,360,410,90)
        for x in (560,650,740): upward_heat(d,x,650,500)
    elif kind=="question_gap":
        # Same hot surface, two incompatible outcomes side-by-side.
        d.line((490,120,490,820),fill="#2e3943",width=3)
        d.rounded_rectangle((75,690,445,775),radius=18,fill="#39424a")
        d.line((95,700,425,700),fill=RED,width=12)
        d.ellipse((190,340,330,480),outline="#607786",width=7)
        d.ellipse((650,335,805,490),fill=BLUE,outline="#d9efff",width=6)
        vapor_band(d,625,830,575,62)
    elif kind=="vapor_hint":
        # One tiny local pocket only: visually a clue, not yet a layer.
        hot_plate(d,760,1.2); droplet(d,490,285,150)
        d.ellipse((455,615,525,650),fill=CYAN,outline="#d9fbff",width=5)
    elif kind=="vapor_birth":
        # Distinct state 1: narrow vertical vapor jets erupt from separate
        # points under the drop. Large geometry change vs the single pocket.
        hot_plate(d,765,1.2); droplet(d,490,250,155)
        for x,h in ((350,95),(420,145),(490,180),(560,145),(630,95)):
            d.line((x,710,x,710-h),fill=CYAN,width=24)
            d.ellipse((x-18,692-h,x+18,728-h),fill="#bdf6ff")
    elif kind=="vapor_expand":
        # Distinct state 2: the jets have spread sideways into a broad,
        # turbulent sheet occupying most of the frame width.
        hot_plate(d,760,1.2); droplet(d,490,245,145)
        for x,y,r in [(180,610,65),(300,580,85),(430,605,105),(560,575,95),(700,600,78),(810,620,55)]:
            d.ellipse((x-r,y-r//2,x+r,y+r//2),fill=CYAN,outline="#c8f8ff",width=4)
        d.line((150,670,830,670),fill="#9af0fb",width=10)
    elif kind=="vapor_cushion":
        # Distinct state 3: bubbles collapse into one continuous thin layer,
        # with the drop visibly higher above the plate.
        hot_plate(d,780,1.25); vapor_band(d,170,810,585,100); droplet(d,490,220,142)
        d.line((215,705,765,705),fill="#2b8ea0",width=5)
    elif kind=="no_contact":
        hot_plate(d,720,1.15); vapor_band(d,300,680,570,70); droplet(d,490,345,118)
        # Leave an unmistakable dark gap instead of drawing a giant X.
        d.line((320,545,660,545),fill="#91a4b0",width=3)
    elif kind=="contact_gap":
        # Tight physical close-up: bottom of droplet, vapor gap, hot metal.
        d.ellipse((155,25,825,600),fill=BLUE,outline="#d9efff",width=7)
        vapor_band(d,120,860,625,72)
        d.rounded_rectangle((65,745,915,855),radius=18,fill="#3f454b",outline="#8c969e",width=5)
        d.line((90,755,890,755),fill=RED,width=14)
    elif kind=="paradox_shield":
        # Wide "extreme heat" state: small hovering drop over a surface that
        # visually dominates the lower half. This is intentionally a very
        # different composition from the preceding close thermal mechanism.
        d.rectangle((0,0,W,H),fill="#2a0d0b")
        d.rounded_rectangle((40,640,940,900),radius=26,fill="#4a2521",outline="#8d5148",width=5)
        d.line((70,655,910,655),fill="#ff3b30",width=24)
        d.line((110,690,870,690),fill="#ff9b62",width=10)
        droplet(d,490,255,88)
        vapor_band(d,360,620,470,58)
        for x in (170,300,490,680,810):
            upward_heat(d,x,620,485,.95)
    elif kind=="protected_drop":
        # Macro cross-section: the droplet now fills the top half and the
        # vapor layer fills the width, so the viewer sees "supported by gas"
        # as a physical gap rather than another near-identical wide shot.
        d.rectangle((0,0,W,H),fill="#071923")
        d.ellipse((70,-170,910,570),fill=BLUE,outline="#d9efff",width=10)
        d.ellipse((245,20,315,90),fill="#b9dcff")
        vapor_band(d,80,900,595,105)
        d.rounded_rectangle((35,790,945,925),radius=20,fill="#3f454b",outline="#8c969e",width=5)
        d.line((70,802,910,802),fill=RED,width=18)
        for x in (250,490,730):
            d.line((x,760,x,705),fill=YELLOW,width=14)
            d.polygon([(x,685),(x-18,715),(x+18,715)],fill=YELLOW)
    elif kind=="glide":
        # Top-down metal pan with a clean path trace.
        d.ellipse((95,80,885,870),fill="#3a4148",outline="#8d969e",width=7)
        d.ellipse((210,320,380,490),fill=BLUE,outline="#d9efff",width=6)
        d.arc((220,255,820,700),start=195,end=30,fill=CYAN,width=18)
        d.polygon([(820,390),(770,365),(787,420)],fill=CYAN)
    elif kind=="support_force":
        hot_plate(d,720,1.25); vapor_band(d,270,710,585,70); droplet(d,490,350,122)
        for x in (350,490,630): upward_heat(d,x,690,630,.8)
    elif kind=="name":
        vapor_band(d,300,680,620,64); droplet(d,490,415,112)
        d.text((490,160),"LEIDENFROST",font=f46,fill="#e7f5ff",anchor="mm")
    elif kind=="threshold":
        # Replace the textbook thermometer with a physical progression:
        # hotter surface -> stable vapor support.
        for idx,(x,heat) in enumerate(((90,.8),(350,1.05),(610,1.35))):
            d.rounded_rectangle((x,650,x+240,760),radius=18,fill="#39424a",outline="#737f88",width=4)
            d.line((x+20,662,x+220,662),fill="#ff8a66" if heat<1.2 else "#ff3b30",width=12)
            rr=58
            d.ellipse((x+120-rr,405-rr,x+120+rr,405+rr),fill=BLUE,outline="#d9efff",width=5)
            if heat>=1.2:
                d.rounded_rectangle((x+55,530,x+185,575),radius=20,fill=CYAN,outline="#c8f8ff",width=3)
    elif kind=="payoff":
        hot_plate(d,730,1.35); vapor_band(d,230,750,570,82); droplet(d,490,340,128)
        for x in (340,490,640): upward_heat(d,x,700,635,.65)
    else:
        raise ValueError(kind)

    out.parent.mkdir(parents=True,exist_ok=True)
    im.save(out,quality=95)
    return out


def _hex_rgb(value:str)->tuple[int,int,int]:
    value=value.lstrip("#")
    return tuple(int(value[i:i+2],16) for i in (0,2,4))


def _mix(a:str,b:str,t:float)->str:
    ar=_hex_rgb(a); br=_hex_rgb(b)
    t=max(0.0,min(1.0,t))
    vals=[round(ar[i]*(1-t)+br[i]*t) for i in range(3)]
    return "#"+"".join(f"{v:02x}" for v in vals)


def sphere3d(d,cx:int,cy:int,r:int,phase:float=0.0,flatten:float=0.9):
    """Layered glossy sphere/ellipsoid: deliberately 3D, never a flat icon."""
    ry=max(12,int(r*flatten))
    d.ellipse((cx-r-18,cy+ry-18,cx+r+18,cy+ry+28),fill="#061018")
    steps=18
    for j in range(steps,0,-1):
        q=j/steps
        rr=max(2,int(r*q)); ryy=max(2,int(ry*q))
        # light comes from upper-left; smaller inner layers get brighter/cyan.
        col=_mix("#08365f","#5ab9ff",1-q*0.72)
        ox=int((1-q)*-r*0.18); oy=int((1-q)*-ry*0.16)
        d.ellipse((cx-rr+ox,cy-ryy+oy,cx+rr+ox,cy+ryy+oy),fill=col)
    d.ellipse((cx-int(r*.52),cy-int(ry*.57),cx-int(r*.18),cy-int(ry*.28)),fill="#dff7ff")
    glint=int(6+5*(0.5+0.5*math.sin(phase*math.tau)))
    d.ellipse((cx-int(r*.38)-glint,cy-int(ry*.38)-glint,
               cx-int(r*.38)+glint,cy-int(ry*.38)+glint),fill="#ffffff")
    d.arc((cx-r,cy-ry,cx+r,cy+ry),start=205,end=340,fill="#96e6ff",width=max(3,r//18))


def plate3d(d,y:int=650,heat:float=1.0,tilt:float=0.0):
    """Perspective metal slab with a glowing hot top edge and visible depth."""
    skew=int(55+18*tilt)
    top=[(90,y),(890,y),(835,y+95),(145,y+95)]
    front=[(145,y+95),(835,y+95),(805,y+220),(175,y+220)]
    side=[(835,y+95),(890,y),(860,y+125),(805,y+220)]
    d.polygon(front,fill="#202830",outline="#5f6d78")
    d.polygon(side,fill="#141b21",outline="#4d5962")
    d.polygon(top,fill="#48535d",outline="#8b99a4")
    glow=_mix("#f36b4d","#ff2d20",max(0.0,min(1.0,(heat-.75)/.7)))
    d.line((118,y+17,870,y+17),fill=glow,width=18)
    d.line((145,y+42,842,y+42),fill=_mix(glow,"#ffd08a",.35),width=6)
    # perspective brushing
    for x in range(170,830,110):
        d.line((x,y+58,x-24,y+84),fill="#626e77",width=2)
    return top,front


def vapor3d(d,cx:int,y:int,width:int,height:int,phase:float=0.0):
    """Layered translucent-looking vapor lens with perspective depth."""
    wobble=int(7*math.sin(phase*math.tau))
    for j in range(7,0,-1):
        q=j/7
        w=max(20,int(width*q)); h=max(10,int(height*(.55+.45*q)))
        col=_mix("#173b4a","#72e6f6",1-q*.68)
        yy=y+int((1-q)*height*.18)+wobble//max(1,j)
        d.ellipse((cx-w//2,yy-h//2,cx+w//2,yy+h//2),fill=col)
    d.arc((cx-width//2,y-height//2,cx+width//2,y+height//2),
          start=185,end=355,fill="#d4fbff",width=max(3,height//10))


def heat_arrow3d(d,x:int,y0:int,y1:int,strength:float=1.0,curve:int=0):
    col="#ffb347"
    w=max(8,int(13*strength))
    mid=(y0+y1)//2
    if curve:
        pts=[(x,y0),(x+curve//3,mid+25),(x+curve,y1)]
        d.line(pts,fill="#8a381f",width=w+8,joint="curve")
        d.line(pts,fill=col,width=w,joint="curve")
        tx=x+curve; ty=y1
    else:
        d.line((x,y0,x,y1),fill="#8a381f",width=w+8)
        d.line((x,y0,x,y1),fill=col,width=w)
        tx=x; ty=y1
    d.polygon([(tx,ty-18),(tx-18,ty+13),(tx+18,ty+13)],fill="#ffd277")


def save_motion_clip(kind:str,out:Path,font_path:str|None,duration:float=2.8,fps:int=24)->Path:
    """Render every synthetic Leidenfrost beat as moving pseudo-3D geometry.

    Motion must describe a physical state change (rise, spread, support, glide,
    heating, separation). Camera-only crop/zoom motion is intentionally absent.
    """
    frames=out.parent/(out.stem+"_frames")
    frames.mkdir(parents=True,exist_ok=True)
    total=max(2,int(duration*fps))
    f46=get_font(font_path,46)

    for i in range(total):
        t=i/(total-1)
        pulse=0.5+0.5*math.sin(t*math.tau)
        im,d=canvas()

        if kind=="hook_result":
            plate3d(d,670,1.35)
            vapor3d(d,490,585,int(330+80*pulse),72,t)
            sphere3d(d,490,365-int(20*pulse),122,t)

        elif kind=="skid_contrast":
            # Left outcome collapses; right outcome physically travels.
            plate3d(d,690,1.15)
            rr=max(16,int(105*(1-.78*t)))
            sphere3d(d,255,390,rr,t)
            x=int(575+235*t); y=int(400-55*math.sin(t*math.pi))
            sphere3d(d,x,y,86,t)
            vapor3d(d,x,535,160,44,t)
            heat_arrow3d(d,740,660,530,.65,curve=55)

        elif kind=="expectation":
            plate3d(d,685,1.0+.45*t)
            rr=max(26,int(125*(1-.70*t)))
            sphere3d(d,390,385,rr,t)
            for j,x in enumerate((575,655,735)):
                heat_arrow3d(d,x,660,535-int(45*t),.55+.15*j)

        elif kind=="question_gap":
            plate3d(d,700,1.28)
            # Left visibly evaporates while right visibly lifts on vapor.
            rr=max(18,int(96*(1-.72*t)))
            sphere3d(d,265,390,rr,t)
            right_y=405-int(45*t)
            sphere3d(d,715,right_y,90,t)
            vapor3d(d,715,555,int(105+115*t),50,t)

        elif kind=="vapor_hint":
            plate3d(d,705,1.22)
            sphere3d(d,490,330-int(18*t),140,t)
            vapor3d(d,490,585,int(70+170*t),int(30+35*t),t)

        elif kind=="vapor_birth":
            plate3d(d,710,1.24)
            sphere3d(d,490,295-int(18*t),145,t)
            for j,x in enumerate((330,410,490,570,650)):
                q=max(0.0,min(1.0,t*1.7-j*.10))
                if q>0:
                    h=int(30+155*q)
                    d.line((x,675,x,675-h),fill="#74e4f3",width=24)
                    d.ellipse((x-20,655-h,x+20,695-h),fill="#d4fbff")

        elif kind=="vapor_expand":
            plate3d(d,710,1.25)
            sphere3d(d,490,292-int(22*t),142,t)
            for j,base in enumerate((0.18,0.31,0.44,0.56,0.69,0.82)):
                direction=-1 if j<3 else 1
                x=int(W*base + direction*80*t)
                y=int(590+22*math.sin((t+j*.16)*math.tau))
                r=int(35+45*t)
                vapor3d(d,x,y,r*2,48,t+j*.08)

        elif kind=="vapor_cushion":
            plate3d(d,720,1.28)
            lift=int(95*t)
            sphere3d(d,490,335-lift,148,t)
            vapor3d(d,490,585,int(180+480*t),int(48+45*t),t)
            for x in (330,410,490,570,650):
                if t<.6:
                    heat_arrow3d(d,x,690,620-int(55*t),.45)

        elif kind=="no_contact":
            plate3d(d,715,1.20)
            gap=int(30+75*t)
            vapor3d(d,490,590,int(320+130*t),68,t)
            sphere3d(d,490,480-gap,130,t)

        elif kind=="contact_gap":
            # Macro cutaway: drop fills upper half, vapor gap breathes below it.
            d.rectangle((0,0,W,H),fill="#07151d")
            gap=int(55+65*pulse)
            sphere3d(d,490,180-gap//4,330,t,flatten=.72)
            vapor3d(d,490,565,int(590+110*pulse),int(60+35*pulse),t)
            plate3d(d,700,1.3)

        elif kind=="heat_blocked":
            plate3d(d,720,1.38)
            vapor3d(d,490,555,500,78,t)
            sphere3d(d,490,315,132,t)
            cycle=(t*2.0)%1.0
            for j,x in enumerate((300,395,490,585,680)):
                rise=max(0.0,min(1.0,cycle*1.7-j*.11))
                if rise>0:
                    stop=615-int(95*min(rise,.82))
                    heat_arrow3d(d,x,695,stop,.65)

        elif kind=="paradox_shield":
            # Extreme heat increases, yet the droplet remains stably separated.
            im,d=canvas()
            d.rectangle((0,0,W,H),fill=_mix("#170807","#3a0d08",t))
            plate3d(d,675,1.2+.35*t)
            vapor3d(d,490,515,290,64,t)
            sphere3d(d,490,300-int(14*pulse),100,t)
            for x,curve in ((220,-35),(350,-18),(630,18),(760,35)):
                heat_arrow3d(d,x,645,520,.8,curve=curve)

        elif kind=="protected_drop":
            # Macro 3D support: vapor lens widens while drop is physically lifted.
            im,d=canvas()
            d.rectangle((0,0,W,H),fill="#061923")
            lift=int(48*t)
            sphere3d(d,490,135-lift,345,t,flatten=.70)
            vapor3d(d,490,560,int(520+210*t),int(72+32*pulse),t)
            plate3d(d,720,1.32)
            for x in (300,490,680):
                heat_arrow3d(d,x,700,625-int(35*t),.72)

        elif kind=="glide":
            # Perspective top plane; bead follows an actual curved path.
            d.ellipse((90,70,890,870),fill="#333d46",outline="#818f99",width=8)
            x=int(210+560*t)
            y=int(500-120*math.sin(t*math.pi))
            sphere3d(d,x,y,82,t,flatten=.82)
            vapor3d(d,x,y+115,145,38,t)
            d.arc((160,250,860,760),start=195,end=25,fill="#6be2f2",width=12)

        elif kind=="support_force":
            plate3d(d,720,1.32)
            lift=int(55*t)
            vapor3d(d,490,585,430,70,t)
            sphere3d(d,490,360-lift,128,t)
            for x,curve in ((345,-15),(490,0),(635,15)):
                heat_arrow3d(d,x,695,620-int(55*t),.80,curve=curve)

        elif kind=="name":
            plate3d(d,720,1.25)
            vapor3d(d,490,590,410,68,t)
            sphere3d(d,490,395-int(20*pulse),126,t)
            # Name reveal floats in the empty upper region, not on a card.
            alpha=min(1.0,t*2.2)
            col=_mix("#183442","#e8f7ff",alpha)
            d.text((490,125),"LEIDENFROST",font=f46,fill=col,anchor="mm")

        elif kind=="threshold":
            # Three 3D states animate sequentially: warm -> hotter -> stable vapor.
            xs=(195,490,785)
            for j,x in enumerate(xs):
                local=max(0.0,min(1.0,t*3-j))
                y=655
                top=[(x-115,y),(x+115,y),(x+92,y+55),(x-92,y+55)]
                d.polygon(top,fill=_mix("#303b44","#70433a",local),outline="#84929c")
                d.polygon([(x-92,y+55),(x+92,y+55),(x+78,y+135),(x-78,y+135)],
                          fill="#222a31",outline="#59656e")
                d.line((x-95,y+12,x+95,y+12),
                       fill=_mix("#a45d49","#ff3729",local),width=12)
                sphere3d(d,x,385-int(35*local),72,t+j*.1)
                if j==2 and local>.3:
                    a=(local-.3)/.7
                    vapor3d(d,x,525,int(70+120*a),int(28+25*a),t)

        elif kind=="payoff":
            plate3d(d,720,1.38)
            lift=int(30*math.sin(t*math.pi))
            sphere3d(d,490,330-lift,145,t)
            vapor3d(d,490,575,int(330+240*t),int(64+24*pulse),t)
            for x,curve in ((330,-18),(490,0),(650,18)):
                heat_arrow3d(d,x,695,625-int(32*t),.68,curve=curve)

        else:
            raise ValueError(kind)

        im.save(frames/f"{i:04d}.png")

    out.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run([
        "ffmpeg","-y","-framerate",str(fps),"-i",str(frames/"%04d.png"),
        "-c:v","libx264","-pix_fmt","yuv420p","-movflags","+faststart",str(out)
    ],check=True,capture_output=True,timeout=180)
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
    # Visual Production V2.1 contract: every generated diagram is a moving
    # pseudo-3D physical visualization. No static PNG diagram is allowed into
    # the manifest; the only non-generated visual is the real experiment clip.
    motion={
        k:save_motion_clip(
            k,assets/f"{k}_3d_motion.mp4",args.font,
            duration=3.2 if k in {"glide","vapor_cushion","payoff"} else 2.8,
            fps=24,
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
                 "a moving high contrast 3D split visualization showing evaporation crossed out on the left and a water droplet skittering across a pan on the right",
                 "물이 사라지는 예상은 X표시하고 실제로는 물방울이 미끄러지는 대비를 한 화면에 보여주는 모습"),
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
                 "an educational cross section diagram of vapor forming under a water droplet above a hot plate",
                 "물방울 아래에서 수증기가 만들어지는 단면 모습"),
            beat(motion["vapor_expand"],"아래로 퍼지면서","vapor_spread","vapor_layer","spread","state",
                 "a moving cinematic 3D scientific visualization filled with vapor bubbles spreading beneath a droplet above a hot plate",
                 "생긴 수증기가 물방울 아래쪽으로 퍼지는 모습을 크게 보여주는 모습"),
            beat(motion["vapor_cushion"],"쿠션","vapor_cushion","vapor_layer","cushion","state",
                 "an educational cross section diagram of a water droplet supported by a thin vapor cushion above a hot plate",
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

나머지 설명 장면은 이 제작 스크립트가 직접 생성한 움직이는 3D 물리 도식입니다.
"""
    Path("examples/leidenfrost_effect_upload_description.txt").write_text(desc,encoding="utf-8")
    print("LEIDENFROST_MANIFEST_READY=examples/leidenfrost_effect.json")


if __name__=="__main__":
    main()
