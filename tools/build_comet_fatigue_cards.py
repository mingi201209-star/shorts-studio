"""Owned conceptual fatigue diagrams, with fixed specimen geometry across stages.
These are explanatory schematics, not accident reconstruction or engineering simulation.
"""
from pathlib import Path
import hashlib
import json
from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
W, H = 980, 950
BG, WHITE, BLUE, GOLD, RED = "#101c2b", "#edf4ff", "#8fcfff", "#ffd166", "#ff795e"

def base(title, subtitle):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    text(d, 490, 72, title, 64)
    text(d, 490, 154, subtitle, 43, BLUE)
    return im, d

def text(d, x, y, value, size=52, color=WHITE):
    font = ImageFont.truetype(FONT, size)
    box = d.textbbox((0, 0), value, font=font)
    if box[2]-box[0] > W-70:
        raise ValueError("Text must fit without shrinking: " + value)
    d.text((x, y), value, font=font, fill=color, anchor="mm")

def footer(d):
    text(d, 490, 847, "설명용 모식도", 43, GOLD)
    text(d, 490, 906, "실제 사고 형상·크기 아님", 38, WHITE)

def specimen(d, stage, box=(140, 240, 840, 745)):
    x0,y0,x1,y1 = box
    sx,sy=(x1-x0)/700,(y1-y0)/505
    def p(x,y): return (x0+x*sx,y0+y*sy)
    def rect(r,**kwargs):d.rounded_rectangle((*p(r[0],r[1]),*p(r[2],r[3])),**kwargs)
    rect((0,0,700,505),radius=int(25*min(sx,sy)),fill="#486575",outline="#b7ccd7",width=max(2,int(6*sx)))
    # Same generic opening and hole in every state; positions are not accident coordinates.
    rect((260,130,610,380),radius=int(25*min(sx,sy)),fill=BG,outline="#e0edf5",width=max(2,int(9*sx)))
    hole=p(215,115);rr=17*min(sx,sy)
    d.ellipse((hole[0]-rr,hole[1]-rr,hole[0]+rr,hole[1]+rr),fill=BG,outline=GOLD,width=max(2,int(6*sx)))
    pts=[(203,127),(175,158),(187,190)]
    if stage>=1:pts += [(149,232),(163,272),(121,317),(134,360),(93,405)]
    if stage>=2:pts += [(110,447),(77,505)]
    d.line([p(*a) for a in pts],fill=RED,width=max(3,int(15*sx)),joint="curve")
    if stage>=2:
        # Generic loss of continuity only; no physical stress or exact fracture prediction.
        d.line([p(77,505),p(110,447),p(93,405)],fill=BG,width=max(4,int(22*sx)))
    return p

def build(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    im,d=base("균열 시작 부근", "G-ALYP 사고 조사 결과")
    p=specimen(d,0)
    d.ellipse((292,303,417,429),outline=GOLD,width=6)
    text(d,490,788,"ADF 개구부의 리벳 구멍 주변",47,GOLD)
    footer(d);im.save(root/"rivet.png")

    im,d=base("작은 균열", "금속 피로의 원리 · 확대 모식도")
    specimen(d,0)
    # Long opposing arrows show loading rather than imply air pressure through the opening.
    for x,dx in [(110,-55),(870,55)]:
        d.line((x,490,x+dx,490),fill=BLUE,width=8)
        d.polygon([(x+dx,490),(x+dx-(15 if dx>0 else -15),479),(x+dx-(15 if dx>0 else -15),501)],fill=BLUE)
    text(d,490,788,"같은 부위에 반복 하중",52,GOLD)
    footer(d);im.save(root/"crack-small.png")

    im,d=base("반복 하중 뒤", "같은 부위에서 균열이 성장")
    specimen(d,1)
    # Visible old/new extent, with a leader only to the crack tip.
    d.line((233,645,100,706),fill=GOLD,width=7)
    text(d,490,788,"균열이 더 길어짐",58,GOLD)
    footer(d);im.save(root/"crack-grown.png")

    im,d=base("핵심은 금속 피로", "같은 부위의 변화 · 설명용 모식도")
    for i,(label,stage) in enumerate([("반복 하중",0),("균열 성장",1),("구조 파손",2)]):
        y=230+i*185
        specimen(d,stage,(465,y-35,835,y+120))
        text(d,245,y+43,label,56,GOLD if i==1 else WHITE)
        if i<2:
            d.line((650,y+125,650,y+143),fill=BLUE,width=6)
            d.polygon([(650,y+153),(639,y+138),(661,y+138)],fill=BLUE)
    footer(d);im.save(root/"summary.png")

if __name__=="__main__":
    root=Path("assets/comet-terra")
    build(root)
    manifest={"type":"original explanatory schematic","author":"Shorts Studio",
              "license":"project-owned original geometry","engineering_simulation":False,
              "exact_accident_geometry":False,
              "source_basis":"Existing verified factual_notes in examples/comet.json: fatigue origin at ADF rivet hole; growth under repeated loading.",
              "assets":{n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in ["rivet.png","crack-small.png","crack-grown.png","summary.png"]}}
    (root/"fatigue-provenance.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
