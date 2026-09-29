#!/usr/bin/env python3
"""Build three upload-ready Shorts from the verified success-pattern engine.

The pack deliberately spans three content axes:
- golf-ball dimples: counterintuitive science;
- head restraints: everyday safety design;
- elevator counterweights: hidden infrastructure.

Every visual is generated locally and may be used in the final YouTube
upload without third-party media licensing. Motion always represents a real
state change in the explanation; no crop/zoom cadence tricks are used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFont

from shorts_studio.hook_studio import (
    HookCandidate, TopicBrief, generate_and_judge,
    build_story_generation_prompt, story_writer_system_prompt,
)

W,H=980,950
BLACK="#000000"; INK="#111820"; WHITE="#ffffff"
BLUE="#4295e8"; CYAN="#5bd5e5"; RED="#ef5b4f"; YELLOW="#f4c94d"
GREEN="#65c88b"; GREY="#8c98a3"; LIGHT="#eaf0f5"; ORANGE="#f59d45"
NEG=["a photograph of a cat","a mountain landscape","a city skyline at night"]


def sha(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def font(path:str|None,size:int,bold:bool=False):
    candidates=[]
    if path: candidates.append(path)
    if bold:
        candidates.extend([
            "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        ])
    candidates.extend([
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ])
    for p in candidates:
        if p and Path(p).is_file():
            return ImageFont.truetype(p,size)
    return ImageFont.load_default()


def canvas(bg=INK):
    im=Image.new("RGB",(W,H),bg)
    return im,ImageDraw.Draw(im)


def arrow(d,xy,fill=WHITE,width=14,head=28):
    x1,y1,x2,y2=xy
    d.line((x1,y1,x2,y2),fill=fill,width=width)
    ang=math.atan2(y2-y1,x2-x1)
    for delta in (2.55,-2.55):
        ax=x2+head*math.cos(ang+delta)
        ay=y2+head*math.sin(ang+delta)
        d.line((x2,y2,ax,ay),fill=fill,width=max(5,width//2))


def label(d,text,xy,fnt,fill=WHITE,anchor="mm"):
    d.text(xy,text,font=fnt,fill=fill,anchor=anchor,align="center")


def golf_ball(d,cx,cy,r,dimpled=True,fill=WHITE):
    d.ellipse((cx-r,cy-r,cx+r,cy+r),fill=fill,outline=INK,width=7)
    if dimpled:
        pts=[(-.55,-.55),(-.18,-.68),(.22,-.62),(.55,-.42),(-.65,-.15),
             (-.28,-.18),(.12,-.22),(.5,-.08),(-.52,.24),(-.12,.18),
             (.28,.22),(.58,.38),(-.33,.58),(.08,.61),(.43,.62)]
        for px,py in pts:
            rr=max(5,int(r*.075))
            x=cx+int(px*r); y=cy+int(py*r)
            d.ellipse((x-rr,y-rr,x+rr,y+rr),outline=GREY,width=max(2,r//35))


def car(d,x,y,scale=1.0,fill=BLUE):
    w=int(430*scale); h=int(160*scale)
    d.rounded_rectangle((x,y,x+w,y+h),radius=int(35*scale),fill=fill,outline=WHITE,width=max(4,int(7*scale)))
    d.polygon([(x+int(.2*w),y),(x+int(.35*w),y-int(85*scale)),
               (x+int(.72*w),y-int(85*scale)),(x+int(.88*w),y)],fill=fill,outline=WHITE)
    for wx in (x+int(.23*w),x+int(.78*w)):
        r=int(42*scale)
        d.ellipse((wx-r,y+h-r,wx+r,y+h+r),fill=INK,outline=WHITE,width=5)


def seat_person(d,head_x,head_y,rest_x,rest_y,torso_shift=0,head_shift=0):
    # seat
    d.rounded_rectangle((270+torso_shift,510,500+torso_shift,770),radius=30,fill="#39434d",outline=WHITE,width=7)
    d.line((300+torso_shift,735,240+torso_shift,850),fill=WHITE,width=22)
    # torso
    d.line((430+torso_shift,500,450+torso_shift,690),fill=ORANGE,width=54)
    # neck/head
    nx=440+torso_shift+head_shift
    d.line((442+torso_shift,500,nx,430),fill=ORANGE,width=28)
    d.ellipse((head_x+torso_shift+head_shift-72,head_y-72,head_x+torso_shift+head_shift+72,head_y+72),
              fill="#ffd5ad",outline=WHITE,width=6)
    # restraint
    d.rounded_rectangle((rest_x,rest_y,rest_x+110,rest_y+170),radius=25,fill=BLUE,outline=WHITE,width=7)


def elevator(d,car_y,cw_y,car_load=1,cw_scale=1.0,motor=False):
    # shaft
    d.rounded_rectangle((110,95,870,855),radius=22,outline=GREY,width=8,fill="#161c22")
    # pulley + ropes
    d.ellipse((395,105,585,295),outline=WHITE,width=12)
    d.line((300,190,300,car_y),fill=WHITE,width=9)
    d.line((680,190,680,cw_y),fill=WHITE,width=9)
    # car
    d.rounded_rectangle((185,car_y,415,car_y+245),radius=20,fill=BLUE,outline=WHITE,width=8)
    for i in range(car_load):
        x=235+55*(i%3); y=car_y+105+70*(i//3)
        d.ellipse((x-18,y-45,x+18,y-9),fill=YELLOW)
        d.line((x,y-8,x,y+45),fill=YELLOW,width=12)
    # counterweight
    cw_w=int(170*cw_scale)
    d.rounded_rectangle((680-cw_w//2,cw_y,680+cw_w//2,cw_y+230),radius=18,fill=ORANGE,outline=WHITE,width=8)
    for yy in range(cw_y+45,cw_y+205,45):
        d.line((680-cw_w//2+18,yy,680+cw_w//2-18,yy),fill="#7c4318",width=8)
    if motor:
        d.ellipse((425,135,555,265),fill=RED,outline=WHITE,width=7)
        label(d,"M",(490,200),font(None,42,True),WHITE)


def encode_motion(out:Path,drawer:Callable[[float],Image.Image],duration=2.6,fps=24):
    out.parent.mkdir(parents=True,exist_ok=True)
    total=max(2,int(duration*fps))
    proc=subprocess.Popen([
        "ffmpeg","-y","-f","rawvideo","-vcodec","rawvideo","-pix_fmt","rgb24",
        "-s",f"{W}x{H}","-r",str(fps),"-i","-","-an",
        "-c:v","libx264","-preset","veryfast","-crf","20","-pix_fmt","yuv420p",
        "-movflags","+faststart",str(out)
    ],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        for i in range(total):
            t=i/(total-1)
            im=drawer(t).convert("RGB")
            proc.stdin.write(im.tobytes())
        proc.stdin.close()
        stderr=proc.stderr.read().decode("utf-8","replace") if proc.stderr else ""
        rc=proc.wait(timeout=120)
        if rc:
            raise RuntimeError(f"ffmpeg failed for {out}: {stderr[-2000:]}")
    finally:
        if proc.poll() is None:
            proc.kill()
    return out


def golf_frame(state:str,t:float,font_path:str|None):
    im,d=canvas("#0d1c2b")
    f34=font(font_path,34); f44=font(font_path,44,True); f58=font(font_path,58,True)
    if state=="hook_compare":
        golf_ball(d,260,430,118,False); golf_ball(d,690,430,118,True)
        x1=120+int(140*t); x2=500+int(260*t)
        arrow(d,(120,680,x1+130,680),RED,15); arrow(d,(500,680,x2+180,680),GREEN,15)
        label(d,"매끈",(260,250),f44,GREY); label(d,"딤플",(690,250),f44,CYAN)
        label(d,"더 멀리",(690,820),f58,GREEN)
    elif state=="flight_compare":
        y1=650-int(120*math.sin(math.pi*t)); y2=650-int(220*math.sin(math.pi*t))
        x1=110+int(390*t); x2=110+int(720*t)
        golf_ball(d,x1,y1,48,False); golf_ball(d,x2,y2,48,True)
        d.arc((80,370,540,760),180,335,fill=GREY,width=9)
        d.arc((80,180,900,800),180,335,fill=CYAN,width=13)
        label(d,"같은 출발, 다른 거리",(490,145),f44,WHITE)
    elif state=="distance_result":
        d.line((90,650,890,650),fill=GREY,width=8)
        golf_ball(d,300,610,62,False); golf_ball(d,760,610,62,True)
        d.line((120,520,390,520),fill=GREY,width=10)
        d.line((120,390,835,390),fill=CYAN,width=14)
        d.ellipse((365,495,415,545),fill=GREY)
        d.ellipse((810,365,860,415),fill=GREEN)
        label(d,"매끈",(390,735),f34,GREY); label(d,"딤플",(830,735),f34,CYAN)
        label(d,"딤플 공이 더 멀리",(490,180),f58,GREEN)
    elif state=="expected_drag":
        golf_ball(d,490,450,145,True)
        for y in (340,410,480,550):
            arrow(d,(100,y,340,y),WHITE,10)
        arrow(d,(760,450,875,450),RED,22)
        label(d,"거칠면 저항 ↑ ?",(490,735),f58,RED)
    elif state=="drag_expectation":
        golf_ball(d,390,450,145,True)
        arrow(d,(565,450,855,450),RED,28)
        label(d,"공기저항 ↑ ?",(660,335),f58,RED)
        label(d,"직관",(490,760),f44,GREY)
    elif state=="wake_compare":
        golf_ball(d,280,420,105,False); golf_ball(d,690,420,105,True)
        # broad vs narrow wakes pulse
        broad=110+int(35*t); narrow=45+int(12*t)
        d.polygon([(390,330),(390,510),(760,420+broad),(760,420-broad)],fill="#8e3f49")
        d.polygon([(795,380),(795,460),(930,420+narrow),(930,420-narrow)],fill="#245d70")
        label(d,"큰 꼬리",(300,690),f44,RED); label(d,"작은 꼬리",(715,690),f44,CYAN)
    elif state=="wake_shrink":
        golf_ball(d,360,430,120,True)
        wide=180-int(105*t)
        d.polygon([(480,320),(480,540),(900,430+wide),(900,430-wide)],fill="#245d70")
        arrow(d,(760,250,620,250),GREEN,14)
        label(d,"후류가 좁아짐",(660,690),f44,GREEN)
    elif state=="dimple_surface":
        golf_ball(d,490,475,250,True)
        for a in range(0,360,30):
            r=330; x=490+int(r*math.cos(math.radians(a))); y=475+int(r*math.sin(math.radians(a)))
            x2=490+int((r-55-20*t)*math.cos(math.radians(a))); y2=475+int((r-55-20*t)*math.sin(math.radians(a)))
            arrow(d,(x,y,x2,y2),CYAN,7,16)
        label(d,"홈이 공기 흐름을 건드림",(490,835),f44,WHITE)
    elif state=="turbulence":
        golf_ball(d,490,475,165,True)
        for j in range(28):
            a=(j*37+t*140)%360
            r=235+28*math.sin(j*2.1+t*5)
            x=490+r*math.cos(math.radians(a)); y=475+r*.62*math.sin(math.radians(a))
            d.ellipse((x-8,y-8,x+8,y+8),fill=CYAN)
        label(d,"일부러 흐름을 어지럽힘",(490,795),f44,WHITE)
    elif state=="attached_flow":
        golf_ball(d,450,465,155,True)
        for off in (-110,-50,10,70,130):
            pts=[]
            for k in range(30):
                a=math.pi+(math.pi*1.55*k/29)
                r=215+off*.18
                pts.append((450+r*math.cos(a),465+(.55*r)*math.sin(a)+off*.22))
            d.line(pts,fill=CYAN,width=8)
        label(d,"공기가 더 뒤까지 붙음",(490,805),f44,WHITE)
    elif state=="separation_compare":
        golf_ball(d,270,430,105,False); golf_ball(d,700,430,105,True)
        d.line((310,325,405,260),fill=RED,width=12); d.line((310,535,405,600),fill=RED,width=12)
        d.line((765,350,865,330),fill=GREEN,width=12); d.line((765,510,865,530),fill=GREEN,width=12)
        label(d,"일찍 분리",(270,700),f44,RED); label(d,"늦게 분리",(700,700),f44,GREEN)
    elif state=="pressure_wake":
        golf_ball(d,420,430,125,True)
        w=int(250-80*t)
        d.rounded_rectangle((545,330,545+w,530),radius=80,fill="#793948")
        label(d,"저압 영역",(650,430),f44,WHITE)
        label(d,"뒤쪽 영역이 작아짐",(490,760),f44,GREEN)
    elif state=="drag_arrow":
        golf_ball(d,420,450,130,True)
        arrow(d,(590,450,590+int(220*(1-t*.55)),450),RED,20)
        label(d,"압력 저항 ↓",(490,740),f58,GREEN)
    elif state=="roughness_win":
        d.rounded_rectangle((90,210,440,700),radius=35,fill="#1a2530",outline=GREY,width=8)
        d.rounded_rectangle((540,210,890,700),radius=35,fill="#15382c",outline=GREEN,width=8)
        golf_ball(d,265,430,105,False); golf_ball(d,715,430,105,True)
        label(d,"매끈",(265,620),f44,GREY); label(d,"적당한 거칠기",(715,620),f34,GREEN)
        label(d,"이 속도대에선 오른쪽",(490,805),f44,WHITE)
    elif state=="dimple_macro":
        d.ellipse((120,100,860,840),fill=WHITE,outline=GREY,width=8)
        for row in range(5):
            for col in range(6):
                x=230+col*105+(row%2)*50; y=250+row*110
                rr=38+int(5*math.sin(t*math.pi))
                d.ellipse((x-rr,y-rr,x+rr,y+rr),outline=GREY,width=7)
        label(d,"작은 홈 수백 개",(490,135),f44,INK)
    elif state=="not_decoration":
        golf_ball(d,490,460,245,True)
        label(d,"장식",(490,170),f58,GREY)
        d.line((280,250,700,690),fill=RED,width=30)
        d.line((700,250,280,690),fill=RED,width=30)
        label(d,"기능이 있는 표면",(490,820),f44,GREEN)
    elif state=="payoff_path":
        x=120+int(700*t); y=690-int(300*math.sin(math.pi*t))
        golf_ball(d,x,y,55,True)
        d.arc((100,260,900,800),180,335,fill=CYAN,width=14)
        label(d,"홈이 비행 경로를 바꿈",(490,160),f44,WHITE)
    elif state=="payoff_dimple":
        golf_ball(d,490,430,250,True)
        label(d,"장식 X",(490,160),f58,RED)
        label(d,"공기역학 장치",(490,790),f58,GREEN)
    else: raise ValueError(state)
    return im


def headrest_frame(state:str,t:float,font_path:str|None):
    im,d=canvas("#111820")
    f34=font(font_path,34); f44=font(font_path,44,True); f56=font(font_path,56,True)
    if state=="hook_gap":
        seat_person(d,430,360,620,305,0,0)
        gap=int(150-70*t); d.line((520,360,620,360),fill=RED,width=12)
        label(d,"머리 뒤 거리",(570,300),f34,RED)
        label(d,"멀수록 늦게 받침",(490,835),f56,WHITE)
    elif state=="rear_impact":
        x=int(80+150*t); car(d,x,560,.82,BLUE); car(d,600-int(45*t),560,.62,RED)
        arrow(d,(760,450,500,450),RED,18)
        label(d,"뒤에서 충돌",(490,230),f56,WHITE)
    elif state=="delayed_support":
        d.rectangle((35,35,945,915),fill="#261c28",outline=RED,width=10)
        seat_person(d,410,360,690,305,0,-55)
        d.line((500,360,690,360),fill=RED,width=16)
        d.ellipse((560,285,720,445),outline=RED,width=10)
        # moving timer arc = delay before the restraint reaches the head
        d.arc((120,180,360,420),-90,-90+int(300*t),fill=YELLOW,width=22)
        label(d,"머리까지 닿는 데 시간이 걸림",(490,790),f44,WHITE)
    elif state=="torso_move":
        d.rectangle((35,35,945,915),fill="#10263b",outline=BLUE,width=10)
        shift=int(110*t); seat_person(d,430,360,620,305,shift,0)
        arrow(d,(180,760,180+310*t,760),YELLOW,22)
        label(d,"좌석 + 몸통이 먼저 이동",(490,150),f44,WHITE)
    elif state=="head_lag":
        # Strongly distinct state: red warning field + enlarged separation
        # arrow. This is a semantic change (head lag), not framing churn.
        d.rectangle((35,35,945,915),fill="#35181b",outline=RED,width=10)
        torso=int(110*t); head=int(-90*t)
        seat_person(d,430,360,650,305,torso,head)
        arrow(d,(600+torso,255,600+torso+head,255),RED,24)
        d.arc((340,235,650,560),210,335,fill=RED,width=18)
        label(d,"몸통보다 머리가 늦음",(490,155),f44,WHITE)
        label(d,"머리는 잠깐 뒤처짐",(490,825),f44,RED)
    elif state=="relative_gap":
        torso=int(80*t); head=int(-70*t)
        seat_person(d,430,360,670,305,torso,head)
        d.line((440+torso,500,440+torso+head,430),fill=RED,width=18)
        label(d,"몸통 ↔ 머리 움직임 차이",(490,150),f44,WHITE)
    elif state=="neck_bend":
        d.rectangle((35,35,945,915),fill="#4a171b",outline=RED,width=12)
        bend=int(120*t)
        # close-up neck angle, not the same seat composition as adjacent states
        d.line((490,760,505,520),fill=ORANGE,width=72)
        d.line((505,520,505-bend,365),fill=RED,width=38)
        d.ellipse((410-bend,270,570-bend,430),fill="#ffd5ad",outline=WHITE,width=7)
        d.arc((385,430,625,670),205,330,fill=YELLOW,width=18)
        label(d,"머리·몸통 차이 → 목이 휘어짐",(490,165),f44,WHITE)
        label(d,"위험한 상대 움직임",(490,835),f44,YELLOW)
    elif state=="timing":
        d.line((130,500,850,500),fill=GREY,width=9)
        x=int(160+650*t); d.ellipse((x-28,472,x+28,528),fill=YELLOW)
        d.rounded_rectangle((650,300,800,430),radius=25,fill=BLUE,outline=WHITE,width=7)
        label(d,"얼마나 빨리 머리를 받치나",(490,190),f44,WHITE)
    elif state=="close_restraint":
        d.rectangle((35,35,945,915),fill="#113c31",outline=GREEN,width=12)
        gap=int(185-105*t)
        # side-view measurement layout: head on left, restraint on right.
        d.ellipse((225,260,465,500),fill="#ffd5ad",outline=WHITE,width=8)
        d.rounded_rectangle((610-gap//3,225,755-gap//3,540),radius=32,fill=BLUE,outline=WHITE,width=8)
        arrow(d,(470,590,610-gap//3,590),GREEN,16)
        label(d,"머리와 받침 사이 거리 ↓",(490,165),f44,WHITE)
        label(d,"가까울수록 빨리 받침",(490,790),f44,GREEN)
    elif state=="early_contact":
        head_move=int(90*t)
        seat_person(d,430,360,555,305,40,head_move)
        if t>.5:
            d.ellipse((570,300,740,470),outline=GREEN,width=12)
        label(d,"더 빨리 받침",(490,170),f56,GREEN)
    elif state=="reduced_motion":
        d.rounded_rectangle((70,180,450,740),radius=35,outline=RED,width=8)
        d.rounded_rectangle((530,180,910,740),radius=35,outline=GREEN,width=8)
        # left large relative movement
        d.line((255,560,210,390),fill=ORANGE,width=48); d.ellipse((120,240,280,400),fill="#ffd5ad",outline=WHITE,width=5)
        # right supported
        d.line((715,560,715,390),fill=ORANGE,width=48); d.ellipse((635,240,795,400),fill="#ffd5ad",outline=WHITE,width=5)
        d.rounded_rectangle((795,255,860,455),radius=20,fill=BLUE)
        label(d,"움직임 차이 ↓",(720,650),f44,GREEN)
    elif state=="comfort_misconception":
        d.rounded_rectangle((190,180,790,720),radius=45,fill="#26313b",outline=WHITE,width=8)
        d.rounded_rectangle((610,250,760,500),radius=30,fill=BLUE)
        label(d,"편의 쿠션?",(490,420),f56,GREY)
        d.line((270,250,710,650),fill=RED,width=24); d.line((710,250,270,650),fill=RED,width=24)
    elif state=="geometry":
        seat_person(d,430,360,560,280,0,0)
        d.line((502,280,560,280),fill=GREEN,width=10)
        d.line((610,280,610,450),fill=GREEN,width=10)
        label(d,"높이",(690,355),f34,GREEN); label(d,"거리",(530,235),f34,GREEN)
        label(d,"핵심은 위치",(490,800),f56,WHITE)
    elif state=="impact_support_setup":
        d.rectangle((35,35,945,915),fill="#20242b",outline=YELLOW,width=10)
        car(d,120,620,.55,BLUE)
        car(d,610-int(100*t),620,.48,RED)
        arrow(d,(810,510,540,510),RED,20)
        d.rounded_rectangle((255,170,725,430),radius=35,fill="#15382c",outline=GREEN,width=8)
        label(d,"충돌 순간",(490,245),f56,WHITE)
        label(d,"받침이 머리를 기다림",(490,350),f44,GREEN)
    elif state=="support":
        move=int(55*t); seat_person(d,430,360,560,305,50,move)
        d.arc((510,270,760,510),95,270,fill=GREEN,width=20)
        label(d,"머리를 빠르게 지지",(490,815),f44,GREEN)
    elif state=="payoff":
        d.rounded_rectangle((150,120,830,820),radius=55,fill="#15382c",outline=GREEN,width=10)
        seat_person(d,430,360,560,305,0,0)
        label(d,"목 보호용 안전장치",(490,180),f56,WHITE)
        d.polygon([(490,680),(430,610),(390,655),(490,770),(675,565),(630,520)],fill=GREEN)
    else: raise ValueError(state)
    return im


def elevator_frame(state:str,t:float,font_path:str|None):
    im,d=canvas("#0e151c")
    f34=font(font_path,34); f44=font(font_path,44,True); f56=font(font_path,56,True)
    if state=="car_up":
        elevator(d,560-int(330*t),220+int(330*t),2,1.0,True)
        label(d,"객실 ↑",(300,810),f44,BLUE); label(d,"추 ↓",(680,810),f44,ORANGE)
    elif state=="hypothetical_no_counter":
        d.rounded_rectangle((210,180,570,720),radius=25,fill=BLUE,outline=WHITE,width=8)
        arrow(d,(680,700,680,250),RED,30)
        label(d,"객실만 들어올린다면",(490,120),f44,WHITE)
        label(d,"큰 힘",(760,460),f56,RED)
    elif state=="motor_strain":
        d.ellipse((300,250,680,630),fill="#632b31",outline=RED,width=12)
        label(d,"MOTOR",(490,400),f56,WHITE)
        for a in range(0,360,45):
            r=250+int(20*math.sin(t*math.pi*4+a))
            x=490+int(r*math.cos(math.radians(a))); y=440+int(r*math.sin(math.radians(a)))
            d.line((490,440,x,y),fill=RED,width=8)
        label(d,"부담 ↑",(490,760),f56,RED)
    elif state=="reveal_counter":
        elevator(d,470,320,2,1.0,False)
        d.rounded_rectangle((580,250,810,620),radius=35,outline=YELLOW,width=14)
        label(d,"균형추",(695,690),f56,YELLOW)
    elif state=="opposite_up":
        elevator(d,600-int(260*t),180+int(260*t),2,1.0,False)
        arrow(d,(470,640,470,300),BLUE,16); arrow(d,(820,300,820,640),ORANGE,16)
        label(d,"서로 반대",(490,835),f44,WHITE)
    elif state=="pulley":
        elevator(d,500,340,2,1.0,True)
        a=int(360*t)
        for deg in (0,90,180,270):
            x=490+65*math.cos(math.radians(deg+a)); y=200+65*math.sin(math.radians(deg+a))
            d.ellipse((x-12,y-12,x+12,y+12),fill=YELLOW)
        label(d,"한 기계에 연결",(490,840),f44,WHITE)
    elif state=="opposite_down":
        elevator(d,250+int(300*t),560-int(300*t),2,1.0,False)
        arrow(d,(470,300,470,650),BLUE,16); arrow(d,(820,650,820,300),ORANGE,16)
        label(d,"객실 ↓  추 ↑",(490,840),f44,WHITE)
    elif state=="balance_empty":
        d.rounded_rectangle((80,220,430,700),radius=35,fill="#17365a",outline=BLUE,width=8)
        d.rounded_rectangle((550,220,900,700),radius=35,fill="#5a3518",outline=ORANGE,width=8)
        label(d,"객실",(255,330),f44,WHITE); label(d,"균형추",(725,330),f44,WHITE)
        label(d,"무게 일부 상쇄",(490,810),f56,GREEN)
    elif state=="balance_partial":
        elevator(d,420,390,4,1.15,False)
        d.line((160,790,820,790),fill=GREY,width=9)
        label(d,"객실 + 일부 하중과 균형",(490,845),f34,WHITE)
    elif state=="motor_difference":
        d.rounded_rectangle((110,250,870,680),radius=45,fill="#16252f",outline=WHITE,width=8)
        label(d,"전체 무게",(330,380),f44,GREY)
        arrow(d,(420,380,620,380),RED,18)
        label(d,"차이",(700,380),f56,YELLOW)
        d.ellipse((610,520,790,700),fill=GREEN,outline=WHITE,width=8)
        label(d,"M",(700,610),f56,INK)
        label(d,"모터가 처리할 차이를 줄임",(490,810),f34,GREEN)
    elif state=="light_car":
        elevator(d,330,390,0,1.2,False)
        d.polygon([(690,700),(650,640),(730,640)],fill=ORANGE)
        label(d,"빈 객실",(300,760),f44,BLUE); label(d,"추가 더 무거울 수 있음",(680,810),f34,ORANGE)
    elif state=="counter_down":
        elevator(d,520-int(210*t),230+int(300*t),0,1.2,False)
        arrow(d,(820,300,820,720),ORANGE,18)
        label(d,"추의 중력이 객실 상승을 도움",(490,835),f34,WHITE)
    elif state=="energy":
        elevator(d,420-int(90*t),370+int(90*t),2,1.0,True)
        bars=[1.0,.78,.58,.42]
        for i,b in enumerate(bars):
            h=int(230*b); x=90+i*80
            d.rectangle((x,830-h,x+45,830),fill=GREEN if i>1 else RED)
        label(d,"필요 에너지 ↓",(230,210),f44,GREEN)
    elif state=="payoff":
        elevator(d,390,420,2,1.0,True)
        d.rounded_rectangle((560,285,800,720),radius=35,outline=YELLOW,width=14)
        label(d,"짐 X",(680,230),f56,RED)
        label(d,"균형 장치",(680,780),f56,GREEN)
    else: raise ValueError(state)
    return im


@dataclass
class Topic:
    id:str
    title:str
    overlay_title:str
    brief:TopicBrief
    hook_texts:dict[str,str]
    scenes:list
    drawer:Callable[[str,float,str|None],Image.Image]
    sources:list[str]
    hashtags:str


class FixedHookGenerator:
    def __init__(self,texts): self.texts=texts
    def generate(self,brief):
        facts=brief.fact_by_strategy()
        return [HookCandidate(strategy=s,text=t,grounded_in=facts[s])
                for s,t in self.texts.items() if facts.get(s)]


def phrase(role,text,hook_type=None):
    x={"role":role,"text":text}
    if hook_type: x["hook_type"]=hook_type
    return x


def make_topic_configs():
    golf_brief=TopicBrief(
        topic_id="golf-ball-dimples",
        familiar_subject="골프공 딤플",
        contradiction_fact="딤플이 있는 골프공은 같은 조건의 매끈한 공보다 공기저항을 줄여 더 멀리 날 수 있습니다",
        surprising_consequence_fact="매끈한 골프공보다 딤플이 파인 골프공이 더 멀리 날아갑니다",
        counterintuitive_fact="골프공에서는 적당한 표면 거칠기가 특정 속도 범위에서 오히려 항력을 줄일 수 있습니다",
        anomaly_fact="골프공의 작은 홈이 공 뒤의 큰 후류를 줄일 수 있습니다",
        mistaken_assumption_fact="골프공은 매끈할수록 공기저항이 작을 것이라는 직관이 맞지 않습니다",
        cause_effect_fact="딤플은 경계층을 난류로 전이시켜 흐름 분리를 늦추고 압력 항력을 줄일 수 있습니다",
        payoff_text="딤플이 경계층의 흐름 분리를 늦춰 뒤쪽 후류와 압력 항력을 줄이는 것이 핵심입니다",
        grounded_facts=[
            "NASA Glenn은 골프공 크기와 속도 범위에서 거친 표면 공의 항력이 매끈한 공보다 낮을 수 있다고 설명합니다",
            "USGA는 딤플이 후류를 얇게 만들고 항력을 줄인다고 설명합니다",
        ],
    )
    golf_hooks={
        "contradiction":"골프공 딤플은 표면을 거칠게 만들지만, 오히려 공기저항을 줄일 수 있습니다.",
        "surprising_consequence":"놀랍게도 매끈한 골프공보다 딤플이 파인 공이 더 멀리 날아갑니다.",
        "counterintuitive_fact":"골프공 딤플처럼 적당한 거칠기가 사실은 비행에 더 유리할 수 있습니다.",
        "visible_anomaly":"골프공 딤플을 따라간 공기는 이상하게도 매끈한 공보다 더 뒤까지 붙어갑니다.",
    }
    golf_scenes=[
        ("golf_hook",[
            phrase("HOOK","놀랍게도 매끈한 골프공보다 딤플이 파인 공이 더 멀리 날아갑니다.","surprising_consequence"),
            phrase("CRISIS","표면이 거칠면 공기저항이 더 커질 것 같죠."),
            phrase("REVEAL","그런데 딤플은 공 뒤의 큰 공기 꼬리를 줄입니다."),
        ],["hook_compare","flight_compare","distance_result","expected_drag","drag_expectation","wake_compare","wake_shrink"]),
        ("golf_investigation",[
            phrase("INVESTIGATION","작은 홈들이 공 표면의 공기를 일부러 어지럽혀 흐름이 더 오래 붙어 있게 합니다."),
        ],["dimple_surface","turbulence","attached_flow"]),
        ("golf_explain",[
            phrase("EXPLANATION","공기가 늦게 떨어져 나가면 뒤쪽 저압 영역이 작아져 압력 저항이 줄어듭니다."),
        ],["separation_compare","pressure_wake","drag_arrow"]),
        ("golf_twist",[
            phrase("TWIST","그래서 이 속도대에서는 매끈함보다 적당한 거칠기가 더 유리합니다."),
        ],["roughness_win","dimple_macro"]),
        ("golf_end",[
            phrase("PAYOFF","골프공의 작은 홈은 장식이 아니라 비행 거리를 만드는 공기역학 장치입니다."),
        ],["payoff_path","not_decoration","payoff_dimple"]),
    ]

    head_brief=TopicBrief(
        topic_id="head-restraint",
        familiar_subject="차 헤드레스트",
        contradiction_fact="차 헤드레스트는 편의용 쿠션처럼 보이지만 후방 충돌에서 머리와 목을 지지하는 안전장치입니다",
        surprising_consequence_fact="헤드레스트가 낮거나 머리에서 멀면 후방 충돌 때 머리를 더 늦게 받칠 수 있습니다",
        counterintuitive_fact="헤드레스트는 편안함보다 높이와 머리 뒤까지의 거리가 안전 성능에 중요합니다",
        anomaly_fact="후방 충돌 때 몸통은 좌석과 함께 움직이는 동안 머리는 순간적으로 뒤처질 수 있습니다",
        mistaken_assumption_fact="헤드레스트는 단순히 머리를 편하게 기대는 장치라는 생각은 맞지 않습니다",
        cause_effect_fact="머리에 가깝고 충분히 높은 헤드레스트는 충돌 때 머리를 더 빨리 지지해 머리와 몸통의 상대 움직임을 줄입니다",
        payoff_text="후방 충돌에서 헤드레스트가 머리를 빠르게 지지해 목의 상대 움직임을 줄이는 것이 핵심입니다",
        grounded_facts=[
            "IIHS는 헤드레스트 높이와 backset, 그리고 머리가 헤드레스트에 닿기까지 걸리는 시간을 평가합니다",
            "IIHS의 whiplash prevention 평가는 후방 충돌에서 머리와 척추 지지를 측정합니다",
        ],
    )
    head_hooks={
        "surprising_consequence":"놀랍게도 헤드레스트가 멀면 충돌 때 머리를 늦게 받칩니다.",
        "counterintuitive_fact":"차 헤드레스트는 푹신함보다 위치가 더 중요합니다.",
        "visible_anomaly":"차 헤드레스트가 있어도 머리에서 너무 멀면 이상하게도 충돌 순간 바로 받쳐주지 못합니다.",
        "mistaken_assumption":"차 헤드레스트가 단순한 편의 쿠션이라는 생각은 사실과 다릅니다.",
    }
    head_scenes=[
        ("head_hook",[
            phrase("HOOK","놀랍게도 헤드레스트가 멀면 충돌 때 머리를 늦게 받칩니다.","surprising_consequence"),
            phrase("CRISIS","뒤에서 받히면 몸통이 먼저 밀립니다."),
            phrase("REVEAL","그런데 머리는 잠깐 뒤처집니다."),
        ],["hook_gap","rear_impact","delayed_support","torso_move","head_lag"]),
        ("head_investigation",[
            phrase("INVESTIGATION","이때 머리와 몸통의 움직임 차이가 커지면 목이 크게 휘어질 수 있습니다."),
        ],["timing","relative_gap","neck_bend"]),
        ("head_explain",[
            phrase("EXPLANATION","가까운 헤드레스트는 머리를 빨리 받아 몸통과 머리의 차이를 줄입니다."),
        ],["close_restraint","early_contact","reduced_motion"]),
        ("head_twist",[
            phrase("TWIST","그래서 핵심은 푹신함이 아니라 높이와 머리 뒤 거리입니다."),
        ],["comfort_misconception","geometry"]),
        ("head_end",[
            phrase("PAYOFF","헤드레스트는 목 보호 장치입니다. 충돌 때 머리를 빨리 받쳐 차이를 줄입니다."),
        ],["payoff","impact_support_setup","support"]),
    ]

    elev_brief=TopicBrief(
        topic_id="elevator-counterweight",
        familiar_subject="엘리베이터 균형추",
        contradiction_fact="엘리베이터 모터는 객실 전체 무게를 매번 통째로 들어올리는 방식이 아닙니다",
        surprising_consequence_fact="엘리베이터 모터는 객실 전체 무게를 매번 통째로 들어올리지 않아도 됩니다",
        counterintuitive_fact="빈 엘리베이터가 올라갈 때는 균형추 쪽이 더 무거울 수 있습니다",
        anomaly_fact="엘리베이터 객실이 올라갈 때 샤프트 반대편에서는 무거운 추가 내려갑니다",
        mistaken_assumption_fact="엘리베이터 모터가 매번 객실 전체 무게를 그대로 들어올린다는 생각은 맞지 않습니다",
        cause_effect_fact="균형추가 객실과 정격 하중의 일부를 균형 잡아 모터가 처리해야 할 무게 차이를 줄입니다",
        payoff_text="균형추가 객실과 일부 하중을 상쇄해 모터가 처리할 무게 차이와 에너지 요구를 줄이는 것이 핵심입니다",
        grounded_facts=[
            "KONE은 counterweight가 car와 rated load의 일부를 balance한다고 설명합니다",
            "Otis는 객실과 counterweight가 반대로 움직이며 에너지 요구를 줄인다고 설명합니다",
        ],
    )
    elev_hooks={
        "surprising_consequence":"놀랍게도 엘리베이터 모터는 객실 무게를 매번 통째로 들어올리는 게 아닙니다.",
        "counterintuitive_fact":"엘리베이터 균형추는 짐처럼 보이지만 사실은 필요한 에너지를 줄입니다.",
        "visible_anomaly":"엘리베이터 객실이 올라가면 반대편의 무거운 추가 이상하게도 내려갑니다.",
        "mistaken_assumption":"엘리베이터 모터가 객실 전체 무게를 그대로 든다는 생각은 사실과 다릅니다.",
    }
    elev_scenes=[
        ("elev_hook",[
            phrase("HOOK","놀랍게도 엘리베이터 모터는 객실 무게를 매번 통째로 들어올리는 게 아닙니다.","contradiction"),
            phrase("CRISIS","객실만 끌어올린다면 움직일 때마다 큰 힘이 필요하겠죠."),
            phrase("REVEAL","샤프트 반대편에는 무거운 균형추가 같이 움직입니다."),
        ],["car_up","hypothetical_no_counter","motor_strain","reveal_counter"]),
        ("elev_investigation",[
            phrase("INVESTIGATION","객실이 올라가면 균형추는 내려가고, 객실이 내려가면 반대로 올라갑니다."),
        ],["opposite_up","pulley","opposite_down"]),
        ("elev_explain",[
            phrase("EXPLANATION","균형추는 객실 무게와 승객 하중의 일부를 균형 잡아 모터가 처리할 차이를 줄입니다."),
        ],["balance_empty","balance_partial","motor_difference"]),
        ("elev_twist",[
            phrase("TWIST","그래서 빈 객실이 올라갈 때는 오히려 균형추 쪽이 더 무거울 수도 있습니다."),
        ],["light_car","counter_down"]),
        ("elev_end",[
            phrase("PAYOFF","반대편의 무거운 추는 짐이 아니라 엘리베이터가 쓰는 에너지를 줄이는 핵심 장치입니다."),
        ],["energy","payoff"]),
    ]

    return [
        Topic(
            "golf_ball_dimples","골프공은 왜 일부러 울퉁불퉁할까","매끈하면 더 못 난다",
            golf_brief,golf_hooks,golf_scenes,golf_frame,
            [
                "NASA Glenn Research Center — Drag of a Sphere: https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/drag-of-a-sphere/",
                "USGA — The Ball: Aerodynamics: https://www.usga.org/content/dam/usga/pdf/science-of-golf/high-school/The-Ball/aerodynamics_facilitator_guide_HS.pdf",
            ],
            "#과학 #골프공 #공기역학 #Shorts",
        ),
        Topic(
            "head_restraint","자동차 헤드레스트가 진짜 필요한 이유","편의용 쿠션이 아니다",
            head_brief,head_hooks,head_scenes,headrest_frame,
            [
                "IIHS — Whiplash prevention: https://www.iihs.org/ratings/about-our-tests/whiplash-prevention",
                "IIHS — Head restraints: https://www.iihs.org/ratings/about-our-tests/head-restraints",
            ],
            "#자동차 #안전 #헤드레스트 #Shorts",
        ),
        Topic(
            "elevator_counterweight","엘리베이터 반대편의 무거운 추 정체","모터가 전부 들지 않는다",
            elev_brief,elev_hooks,elev_scenes,elevator_frame,
            [
                "KONE — Elevator glossary (counterweight/balancing weight): https://distributors.kone.com/en/tools-downloads/glossary/",
                "Otis — The basic workings of a lift: https://www.otis.com/en/uk/w/the-basic-workings-of-a-lift",
            ],
            "#엘리베이터 #과학 #인프라 #Shorts",
        ),
    ]


CUES={
    "golf_ball_dimples":{
        "hook_compare":"놀랍게도","flight_compare":"매끈한 골프공보다","distance_result":"더 멀리","expected_drag":"표면이 거칠면","drag_expectation":"공기저항이","wake_compare":"그런데 딤플은","wake_shrink":"공기 꼬리를",
        "dimple_surface":"작은 홈들이","turbulence":"공기를 일부러","attached_flow":"더 오래 붙어",
        "separation_compare":"늦게 떨어져","pressure_wake":"저압 영역이","drag_arrow":"저항이 줄어",
        "roughness_win":"그래서","dimple_macro":"적당한 거칠기가","payoff_path":"골프공의 작은 홈은","not_decoration":"장식이 아니라","payoff_dimple":"공기역학 장치",
    },
    "head_restraint":{
        "hook_gap":"놀랍게도","rear_impact":"충돌 때","delayed_support":"받칩니다","torso_move":"몸통이","head_lag":"그런데 머리는",
        "relative_gap":"움직임 차이가","neck_bend":"목이 크게","timing":"이때","close_restraint":"가까운 헤드레스트",
        "early_contact":"빨리 받아","reduced_motion":"차이를 줄입니다","comfort_misconception":"푹신함이",
        "geometry":"높이와 머리 뒤 거리","impact_support_setup":"장치입니다","support":"머리를 빨리 받쳐","payoff":"목 보호 장치",
    },
    "elevator_counterweight":{
        "car_up":"놀랍게도","hypothetical_no_counter":"객실만","motor_strain":"큰 힘이","reveal_counter":"균형추가",
        "opposite_up":"객실이 올라가면","pulley":"균형추는 내려가고","opposite_down":"객실이 내려가면",
        "balance_empty":"균형추는 객실 무게와","balance_partial":"승객 하중의 일부","motor_difference":"모터가 처리할 차이를",
        "light_car":"빈 객실이","counter_down":"균형추 쪽이 더 무거울","energy":"에너지를 줄이는","payoff":"핵심 장치",
    },
}

LABELS={
    "golf_ball_dimples":"an educational animated visualization of golf ball aerodynamics, dimples, airflow, wake and drag",
    "head_restraint":"an educational animated visualization of a car seat head restraint supporting a human head during a rear impact",
    "elevator_counterweight":"an educational animated cross section of an elevator car, pulley, motor and counterweight moving in a shaft",
}


def beat(asset:Path,cue:str,info_role:str,concept_id:str,state_id:str,kind:str,topic_id:str):
    digest=sha(asset)
    return {
        "start":0.0,
        "asset":str(asset),
        "visual_change":{
            "kind":kind,"concept_id":concept_id,"state_id":state_id,
            "narration_cue":cue,"added_information":info_role,
            "source_sha256":digest,
        },
        "visual_qa_requirements":[f"{topic_id}의 현재 내레이션 정보가 큰 도형과 움직임으로 직접 보여야 함"],
        "visual_qa_labels":[LABELS[topic_id]],
        "visual_qa_negative_labels":NEG,
        "visual_qa_expected_sha256":[digest],
        "info_role":info_role,
    }


def build_topic(topic:Topic,font_path:str|None):
    assets=Path("assets")/topic.id
    assets.mkdir(parents=True,exist_ok=True)

    hook_result=generate_and_judge(topic.brief,generator=FixedHookGenerator(topic.hook_texts))
    if hook_result.winner is None:
        raise RuntimeError(f"{topic.id}: no Prompt V2 hook survived")
    winner=hook_result.winner
    print(f"{topic.id}:PROMPT_V2_SELECTED={winner.strategy}|{winner.text}")

    build=Path("build"); build.mkdir(exist_ok=True)
    story=build_story_generation_prompt(topic.brief,winner,uncertainty_notes=[])
    (build/f"{topic.id}_story_prompt.txt").write_text(
        story_writer_system_prompt()+"\n\n"+story+"\n",encoding="utf-8")

    # Generate every semantic state as a real moving clip.
    all_states=[s for _,_,states in topic.scenes for s in states]
    state_assets={}
    for state in all_states:
        out=assets/f"{state}.mp4"
        encode_motion(out,lambda t,s=state:topic.drawer(s,t,font_path),duration=2.7,fps=24)
        state_assets[state]=out

    scenes=[]
    cues=CUES[topic.id]
    for scene_index,(sid,plan,states) in enumerate(topic.scenes):
        # Keep the winning Prompt V2 strategy in the authored HOOK metadata.
        if scene_index==0:
            plan[0]["hook_type"]=winner.strategy
            plan[0]["text"]=winner.text
        beats=[]
        for i,state in enumerate(states):
            cue=cues[state]
            kind="concept" if i==0 else "state"
            beats.append(beat(state_assets[state],cue,state,f"{topic.id}:{sid}",state,kind,topic.id))
        # Schema starts are only ordering placeholders. strict meaningful-change
        # mode replaces them with measured narration-cue timing before render.
        for i,b in enumerate(beats): b["start"]=float(i)
        if scene_index==0:
            beats[0]["visual_qa_requirements"]=[
                f"첫 훅 '{plan[0]['text']}'의 익숙한 대상과 이상한 결과가 첫 화면에서 직접 보여야 함"
            ]
        narration=" ".join(p["text"] for p in plan)
        scenes.append({
            "id":sid,
            "narration":narration,
            "narration_plan":plan,
            "visual_description":f"{topic.title} — narration-matched semantic motion.",
            "asset":str(state_assets[states[0]]),
            "visual_beats":beats,
            "visual_qa_requirements":[f"{topic.title}의 핵심 현상을 현재 대사와 일치하는 움직임으로 보여줘야 함"],
            "visual_qa_labels":[LABELS[topic.id]],
            "visual_qa_negative_labels":NEG,
            "factual_notes":topic.sources,
            "overlay_title":None,
            "overlay_title_seconds":2.8 if scene_index==0 else None,
        })

    manifest={
        "title":topic.title,
        "width":1080,"height":1920,"fps":30,
        "overlay_title":topic.overlay_title,
        "overlay_title_mode":"first_scene_only",
        "max_visual_recovery_attempts":2,
        "strict_source_diversity":False,
        "strict_meaningful_visual_changes":True,
        "strict_retention_contract":True,
        "strict_entertainment_contract":False,
        "scenes":scenes,
    }
    Path("examples").mkdir(exist_ok=True)
    manifest_path=Path("examples")/f"{topic.id}.json"
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")

    description=(
        f"{topic.title}\n\n"
        + "영상의 설명 도식과 애니메이션은 Shorts Studio에서 직접 제작했습니다.\n"
        + "사실 확인 자료:\n- " + "\n- ".join(topic.sources)
        + f"\n\n{topic.hashtags}\n"
    )
    (Path("examples")/f"{topic.id}_upload_description.txt").write_text(description,encoding="utf-8")

    meta={
        "topic_id":topic.id,
        "youtube_title":topic.title,
        "hashtags":topic.hashtags,
        "selected_hook":winner.text,
        "selected_strategy":winner.strategy,
        "sources":topic.sources,
    }
    (Path("examples")/f"{topic.id}_upload_metadata.json").write_text(
        json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"UPLOAD_TOPIC_READY={topic.id}")


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--font",default=None)
    args=ap.parse_args()
    for topic in make_topic_configs():
        build_topic(topic,args.font)
    print("UPLOAD_PACK_THREE_READY=3")


if __name__=="__main__":
    main()
