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
    text(d, 490, 906, "원리 설명 · 사고기 재현 아님", 38, WHITE)

def specimen(d, stage, box=(140, 240, 840, 745)):
    x0,y0,x1,y1 = box
    sx,sy=(x1-x0)/700,(y1-y0)/505
    def p(x,y): return (x0+x*sx,y0+y*sy)
    def rect(r,**kwargs):d.rounded_rectangle((*p(r[0],r[1]),*p(r[2],r[3])),**kwargs)
    rect((0,0,700,505),radius=int(25*min(sx,sy)),fill="#486575",outline="#b7ccd7",width=max(2,int(6*sx)))
    # A plain laboratory-style metal coupon, not an aircraft panel or ADF window.
    # No window/cutout geometry or accident rivet coordinates are represented.
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
    im,d=base("가상 금속 시편", "작은 균열에 반복 하중")
    specimen(d,0)
    # Long opposing arrows show loading rather than imply air pressure through the opening.
    for x,dx in [(110,-55),(870,55)]:
        d.line((x,490,x+dx,490),fill=BLUE,width=8)
        d.polygon([(x+dx,490),(x+dx-(15 if dx>0 else -15),479),(x+dx-(15 if dx>0 else -15),501)],fill=BLUE)
    text(d,490,788,"같은 부위에 반복 하중",52,GOLD)
    footer(d);im.save(root/"crack-small.png")

    im,d=base("가상 금속 시편", "같은 부위 · 반복 하중 전후 비교")
    for box,stage,label,x in [
        ((50,300,460,735),0,"처음",255),
        ((520,300,930,735),1,"반복 하중 뒤",725)]:
        specimen(d,stage,box)
        text(d,x,252,label,43,GOLD if stage else WHITE)
    text(d,490,788,"같은 구멍에서 더 길어진 균열",47,GOLD)
    footer(d);im.save(root/"crack-grown.png")

    im,d=base("가상 금속 시편", "")
    specimen(d,2)
    text(d,490,167,"반복 압력 → 균열 성장 → 파손",49,GOLD)
    text(d,490,810,"설명용 모식도",48,GOLD)
    text(d,490,889,"원리 설명 · 사고기 재현 아님",43,WHITE)
    im.save(root/"summary.png")

if __name__=="__main__":
    root=Path("assets/comet-terra")
    build(root)
    manifest={"type":"original virtual metal-coupon fatigue schematic","author":"Shorts Studio",
              "license":"project-owned original geometry","engineering_simulation":False,
              "exact_accident_geometry":False,"aircraft_geometry":False,
              "source_basis":"Existing verified factual_notes in examples/comet.json: fatigue origin at ADF rivet hole; growth under repeated loading.",
              "assets":{n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in ["crack-small.png","crack-grown.png","summary.png"]}}
    (root/"fatigue-provenance.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
