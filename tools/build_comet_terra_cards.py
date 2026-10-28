"""Build legible, explicitly schematic Comet explanation cards from owned geometry."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT="/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
W,H=980,950
def card(path,title,subtitle="",number=None,kind=None,stage=0,footer="설명용 모식도 · 실제 형상·비율 아님"):
 im=Image.new("RGB",(W,H),"#111c2a");d=ImageDraw.Draw(im)
 def text(x,y,t,size=48,color="#edf4ff",anchor="mm"):
  font=ImageFont.truetype(FONT,size)
  while d.textbbox((0,0),t,font=font)[2] > W-80 and size>26:
   size-=1; font=ImageFont.truetype(FONT,size)
  d.text((x,y),t,font=font,fill=color,anchor=anchor)
 text(490,78,title,60)
 if subtitle: text(490,158,subtitle,42,"#8fcfff")
 if number:
  text(490,330,number,158,"#ffd166")
  text(490,455,"압력 사이클",58)
  if number=="1,221회":
   d.polygon([(450,530),(530,530),(545,635),(850,750),(850,785),(540,730),(530,820),(600,850),(600,865),(490,840),(380,865),(380,850),(450,820),(440,730),(130,785),(130,750),(435,635)],fill="#c6d8e3")
   text(490,560,"코멧 운항",31,"#111c2a")
  elif number=="1,836회":
   d.rectangle((120,535,860,820),fill="#226788",outline="#8fcfff",width=8)
   d.rounded_rectangle((245,590,735,750),radius=70,fill="#c6d8e3",outline="white",width=6)
   text(490,670,"수조 속 동체",44,"#111c2a")
   text(490,790,"압력 올림 ↔ 낮춤",37)
  else:
   split=130+720*1221/3057
   d.rectangle((130,550,split,760),fill="#ffd166")
   d.rectangle((split,550,850,760),fill="#69b8e6")
   text(490,815,"운항 1,221 + 시험 1,836",40)

 elif kind=="pressure":
  for j,(label,col) in enumerate([("압력 올림","#ffbd69"),("압력 낮춤","#8fcfff")]):
   x=245+j*490
   d.rounded_rectangle((x-180,270,x+180,590),radius=36,outline=col,width=9)
   text(x,420,label,52,col)
  text(490,690,"올림 → 낮춤 → 반복",60,"#ffd166")
 elif kind=="location":
  d.rounded_rectangle((120,320,860,590),radius=130,fill="#385366",outline="#cfe7f7",width=7)
  d.polygon([(400,410),(620,240),(660,270),(590,430)],fill="#517487")
  for x in range(260,780,100): d.rounded_rectangle((x,460,x+44,510),radius=12,fill="#88bdda")
  d.rectangle((370,325,470,373),fill="#ff9a70",outline="white",width=4)
  d.line((420,325,420,245),fill="#ff9a70",width=8)
  text(490,690,"객실 창문과 다른 상부 개구부",49,"#ffd166")
 elif kind=="crack":
  d.rounded_rectangle((135,255,845,680),radius=24,fill="#4b6473",outline="#b7ccd7",width=6)
  d.rounded_rectangle((390,390,680,585),radius=24,fill="#111c2a",outline="#dce8ee",width=8)
  for x in range(200,790,70):
   d.ellipse((x-9,304,x+9,322),fill="#d6e4eb")
  d.ellipse((357,357,385,385),fill="#111c2a",outline="#ffd166",width=5)
  points=[(371,371),(345,390),(354,414),(322,439),(334,466),(301,492),(310,518),(275,548),(283,576),(248,606)]
  n=[3,6,10][stage]
  d.line(points[:n],fill="#ff795e",width=12)
  d.ellipse((325,325,418,418),outline="#ffd166",width=5)
  text(490,753,["리벳 구멍 주변의 작은 균열","반복 압력으로 균열 성장","커진 균열 → 구조 파손"][stage],49,"#ffd166")
 elif kind=="growth":
  for x,label in [(250,"처음"),(730,"반복 하중 뒤")]:
   d.rounded_rectangle((x-195,300,x+195,690),radius=22,fill="#536e7c",outline="#b7ccd7",width=5)
   d.rounded_rectangle((x-70,430,x+140,600),radius=22,fill="#111c2a",outline="#dce8ee",width=7)
   d.ellipse((x-103,393,x-77,419),fill="#111c2a",outline="#ffd166",width=5)
   pts=[(x-90,406),(x-120,440),(x-106,469)]
   if x==730: pts += [(x-145,515),(x-130,551),(x-166,590),(x-150,632),(x-178,670)]
   d.line(pts,fill="#ff795e",width=14)
   text(x,755,label,48)
  text(490,235,"작은 균열 → 커진 균열",55,"#ffd166")
 elif kind=="compare":
  for x,title2 in [(250,"객실 창문"),(730,"ADF 개구부")]:
   d.rounded_rectangle((x-150,300,x+150,580),radius=70 if x==250 else 24,outline="#8fcfff",width=12)
   text(x,650,title2,49)
  text(490,760,"G-ALYP의 균열: ADF 리벳 구멍 주변",43,"#ffd166")
 elif kind=="summary":
  for i,t in enumerate(["반복 압력","균열 성장","동체 파손"]):
   y=290+i*180
   d.rounded_rectangle((150,y-55,830,y+65),radius=26,fill="#263e52")
   text(490,y,t,72,"#ffd166" if i==1 else "#edf4ff")
   if i<2: text(490,y+100,"↓",54,"#8fcfff")
 text(490,886,footer,27,"#a6b6c6")
 im.save(path)
def build(root):
 root=Path(root);root.mkdir(parents=True,exist_ok=True)
 specs={
 "cycles-flight":("실제 운항에서","시험기 G-ALYU", "1,221회",None,0,"RAF Museum: 1,221 actual cycles"),
 "cycles-tank":("물탱크에서 추가","시험기 G-ALYU", "1,836회",None,0,"RAF Museum: 1,836 simulated cycles"),
 "cycles-total":("누적 압력 사이클","실제 운항 + 물탱크 시험", "3,057회",None,0,"RAF Museum: 3,057 total cycles"),
 "pressure":("물탱크 압력 시험","이륙·착륙의 압력 변화를 반복",None,"pressure",0,None),
 "location":("균열은 어디서 시작됐나","G-ALYP: 동체 위쪽 ADF 개구부",None,"location",0,None),
 "rivet":("시작점은 리벳 구멍 주변","G-ALYP 사고 조사 결과",None,"crack",0,None),
 "crack-small":("작은 균열도 반복 하중을 받으면","금속 피로의 진행을 단순화",None,"crack",0,None),
 "crack-grown":("비행할 때마다 압력 변화","금속 피로의 진행을 단순화",None,"growth",1,None),
 "compare":("창문 모양만으로 설명하지 않기","서로 다른 개구부를 구분",None,"compare",0,None),
 "summary":("핵심은 금속 피로","반복 압력 속에서 자란 균열",None,"summary",0,None)}
 for name,(title,sub,num,kind,stage,foot) in specs.items():
  kwargs={} if foot is None else {"footer":foot}
  card(root/(name+".png"),title,sub,num,kind,stage,**kwargs)
if __name__=="__main__": build("assets/comet-terra")
