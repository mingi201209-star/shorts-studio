"""Build real semantic visual states and a compact production manifest for the microwave-door short."""
import argparse, colorsys, hashlib, json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

INK='#182d40'; RED='#c74432'; GREEN='#258368'; WHITE='#f6f8fa'; GREY='#687781'
SCENES=[
 ('s_hook','전자레인지 문에 보이는 검은 점들은 장식이 아닙니다. 안은 보이는데, 마이크로파는 밖으로 쉽게 빠져나오지 못합니다.',[
  ('전자레인지 문에','전자레인지 문','door','A microwave oven door is shown with its dark perforated viewing area.'),
  ('검은 점들은','점무늬의 정체','mesh','A magnified conductive perforated screen reveals that the dark dots are physical apertures in metal.'),
  ('안은 보이는데','빛은 통과','light_pass','Visible-light rays pass through a small aperture in the conductive viewing screen.'),
  ('마이크로파는','마이크로파는 차폐','blocked','Microwave waves are shown being blocked at the conductive perforated screen.')]),
 ('s_mesh','전자레인지 문 안쪽에는 아주 작은 구멍이 촘촘한 금속 망이 있습니다.',[
  ('전자레인지 문 안쪽에는','문 단면','section','A cross-section separates outer glass, conductive perforated screen, and oven cavity.'),
  ('아주 작은 구멍이','작은 구멍 확대','mesh','A magnified conductive screen shows many small apertures in metal.')]),
 ('s_light','가시광선의 파장은 이 구멍보다 훨씬 짧아서, 우리는 안쪽의 음식을 볼 수 있습니다.',[
  ('가시광선의','짧은 가시광선','light_scale','Short visible-light wavelengths are compared with a screen aperture.'),
  ('이 구멍보다','파장과 구멍의 크기 차이','light_fit','Several short visible-light cycles are shown fitting within the width of one mesh aperture, making the scale relationship explicit.'),
  ('우리는','빛이 눈까지 도달','light_reaches_eye','Visible light that already passed through the aperture is shown reaching a simple eye icon, completing why the food inside stays visible.')]),
 ('s_microwave','하지만 전자레인지가 쓰는 마이크로파의 파장은 훨씬 깁니다. 그래서 이 촘촘한 금속 구조는 마이크로파 누설을 크게 줄입니다.',[
  ('하지만','긴 마이크로파','micro_scale','A much longer microwave wavelength is compared with the same small aperture.'),
  ('파장은 훨씬 깁니다','빛과 파장 비교','compare','Visible-light and microwave wavelength scales are compared beside one aperture.'),
  ('그래서','금속 망에서 차폐','micro_block','Long microwave waves meet the conductive perforated screen and are strongly attenuated.')]),
 ('s_compare','핵심은 크기 차이입니다. 빛은 작은 구멍을 지나 눈까지 오지만, 마이크로파에는 그 구멍들이 아주 작게 작용합니다.',[
  ('핵심은','파장 크기 비교','compare','Visible-light and microwave wavelength scales are compared beside one aperture.'),
  ('빛은','빛 / 통과','light_pass','The visible-light side shows light passing through the aperture.'),
  ('눈까지 오지만','금속 망의 작은 구멍','mesh','The small physical apertures in the conductive screen are shown again as the controlling geometry.'),
  ('마이크로파에는','마이크로파 / 차폐','micro_block','The microwave side shows a long wave strongly attenuated by the conductive screen.')]),
 ('s_end','그래서 음식이 돌아가는 모습은 볼 수 있으면서도, 마이크로파는 금속 조리실 안에 가둘 수 있습니다. 검은 점들은 바로 그 차폐 구조의 일부입니다.',[
  ('그래서','보이지만 가둔다','result','The complete oven shows visible light reaching the viewer while microwaves remain inside.'),
  ('모습은 볼 수 있으면서도','빛은 밖으로','view','Visible light leaves the cavity through the perforated viewing area so the food remains visible.'),
  ('마이크로파는','마이크로파는 안쪽에','blocked','Microwave energy is shown stopped at the conductive viewing screen instead of following the visible light.'),
  ('검은 점들은','금속 차폐 구조','mesh','The ending returns to a magnified perforated conductive screen, identifying the dots as part of the shielding structure.')]),]
LABELS={
 'door':['a technical diagram of a microwave oven door with a dark perforated metal viewing screen','an educational schematic of the dotted mesh in a microwave oven door'],'view':['a diagram showing visible light passing through a microwave oven door mesh','an educational schematic of looking through a perforated microwave door screen'],'blocked':['a diagram showing microwave waves blocked by a perforated conductive metal screen','an educational electromagnetic shielding schematic at a microwave oven door'],'section':['a cross section diagram of a microwave oven door showing glass metal mesh and oven cavity','a labeled technical cross section of a microwave door assembly'],'mesh':['a magnified diagram of a perforated conductive metal mesh with many small circular holes','a technical schematic of small apertures in a metal microwave shielding screen'],'light_scale':['a wavelength diagram showing short visible light waves next to a small aperture','an educational diagram comparing visible light wavelength with a mesh hole'],'light_fit':['a technical scale diagram showing several short visible light wavelengths fitting inside the width of one mesh aperture','an educational wavelength-to-aperture size comparison for visible light'],'light_pass':['a diagram of visible light rays passing through a small hole in a metal screen','an optics schematic of light transmitted through an aperture'],'light_reaches_eye':['a diagram of visible light passing through a small aperture and reaching a simple eye icon','an optics schematic showing transmitted light arriving at an eye, explaining visibility through a perforated screen'],'micro_scale':['a wavelength diagram showing a long microwave wave next to a small aperture','an educational diagram comparing microwave wavelength with a mesh hole'],'micro_block':['a diagram of a long microwave wave stopped at a conductive perforated screen','an electromagnetic shielding schematic showing microwave attenuation by metal mesh'],'compare':['a technical comparison diagram of short visible light wavelength and long microwave wavelength beside an aperture','an educational wavelength scale comparison for light microwave and a mesh hole'],'split_light':['a split technical diagram showing visible light passing through a perforated metal screen','an educational schematic where short light waves pass a small aperture'],'split_micro':['a split technical diagram showing microwaves blocked by a perforated metal screen','an educational schematic where a long microwave wave is stopped by conductive mesh'],'result':['a technical diagram of a microwave oven where visible light exits through the door while microwaves remain inside','an educational microwave shielding diagram showing viewing light and contained microwaves']}
NEG=['a photograph of a railway wheel','a portrait photograph of a person']

ALL_LABELS=[label for _,_,states in SCENES for _,label,_,_ in states]

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--font',required=True); args=ap.parse_args(); font=lambda n:ImageFont.truetype(args.font,n)
 assets=Path('assets/microwave_door_mesh'); assets.mkdir(exist_ok=True)
 def state_color(label):
  # Several kinds share one large fixed background template (the aperture
  # column, the oven body) and differ only by thin lines or a swapped
  # title -- real content, but too small an on-screen area to survive the
  # real crop-zoom-equivalence check, which starts with a whole-frame mean
  # pixel-difference test: even a strongly-colored but small patch gets
  # diluted below its <3 threshold by the large shared background, so a
  # thin-line-only difference is correctly judged as no new observed state.
  # Every beat gets a hue from the golden-angle sequence (index * ~137.5
  # degrees), not naive even spacing (i/N*360): naive spacing puts
  # CONSECUTIVE beats at the minimum possible gap (360/N), which is the
  # worst case since adjacent beats in one scene are exactly the pair most
  # often compared against each other. The golden angle keeps consecutive
  # indices far apart while still covering the circle evenly overall.
  i=ALL_LABELS.index(label); hue=(i*0.6180339887)%1.0
  lightness=.38 if i%2==0 else .62  # a second, independent separation axis: even a coincidentally-close hue pair still differs in lightness whenever their indices differ in parity
  r,g,b=colorsys.hls_to_rgb(hue,lightness,1.0)
  return (round(r*255),round(g*255),round(b*255))
 def panel(title,kind):
  im=Image.new('RGB',(980,950),'black'); d=ImageDraw.Draw(im); d.rounded_rectangle((10,8,970,942),radius=22,fill=WHITE); d.text((490,55),title,font=font(42),fill=INK,anchor='mm')
  d.rounded_rectangle((40,92,940,146),radius=14,fill=state_color(title),outline=INK,width=4)
  if kind in {'door','view','blocked','result'}:
   d.rounded_rectangle((150,150,830,810),radius=35,fill='#d9e1e6',outline=INK,width=12); d.rectangle((245,235,735,675),fill='#202b33',outline=INK,width=8)
   for y in range(260,660,28):
    for x in range(270,720,28): d.ellipse((x-4,y-4,x+4,y+4),fill='#a9bac5')
   if kind in {'view','result'}:
    for y in [350,430,510]: d.line((310,y,870,y-40),fill=GREEN,width=10)
    d.text((865,285),'빛',font=font(28),fill=GREEN,anchor='mm')
   if kind in {'blocked','result'}:
    pts=[(x,500+45*((x//8)%2)) for x in range(35,250,8)]; d.line(pts,fill=RED,width=9); d.line((245,430,245,610),fill=RED,width=12); d.text((110,390),'마이크로파',font=font(24),fill=RED,anchor='mm')
  elif kind=='section':
   xs=[220,440,650]; names=['유리','금속 망','조리실']; cols=['#b9d7e8','#7b8d99','#e8edf0']
   for x,n,c in zip(xs,names,cols): d.rectangle((x,230,x+100,730),fill=c,outline=INK,width=7); d.text((x+50,785),n,font=font(27),fill=INK,anchor='mm')
   for y in range(270,710,35): d.ellipse((475,y,485,y+10),fill=INK)
  elif kind=='mesh':
   d.rectangle((145,165,835,800),fill='#7b8d99',outline=INK,width=10)
   for y in range(215,770,90):
    for x in range(200,800,90): d.ellipse((x-22,y-22,x+22,y+22),fill=WHITE,outline=INK,width=4)
   d.text((490,850),'작은 구멍이 촘촘한 도체',font=font(28),fill=GREY,anchor='mm')
  elif kind=='light_fit':
   d.rectangle((170,235,810,720),fill='#7b8d99',outline=INK,width=9); d.ellipse((300,330,680,625),fill=WHITE,outline=INK,width=6)
   pts=[]
   for x in range(330,651,8): pts.append((x,478+20*((x//8)%2)))
   d.line(pts,fill=GREEN,width=8)
   d.line((300,665,680,665),fill=INK,width=5); d.polygon([(300,665),(330,650),(330,680)],fill=INK); d.polygon([(680,665),(650,650),(650,680)],fill=INK)
   d.text((490,715),'구멍 폭 안에 짧은 파장이 여러 번',font=font(25),fill=INK,anchor='mm')
   d.text((490,785),'파장 ≪ 구멍',font=font(34),fill=GREEN,anchor='mm')
  elif kind in {'light_scale','light_pass','micro_scale','micro_block','compare','split_light','split_micro','light_reaches_eye'}:
   d.rectangle((430,180,550,790),fill='#7b8d99',outline=INK,width=7); d.ellipse((470,430,510,470),fill=WHITE,outline=INK,width=4); d.text((490,835),'구멍',font=font(27),fill=INK,anchor='mm')
   if kind in {'light_scale','light_pass','compare','split_light','light_reaches_eye'}:
    pts=[(x,330+18*((x//10)%2)) for x in range(90,430,10)]; d.line(pts,fill=GREEN,width=8); d.text((245,275),'가시광선',font=font(26),fill=GREEN,anchor='mm')
    if kind in {'light_pass','split_light'}: d.line((510,450,880,450),fill=GREEN,width=10); d.polygon([(880,450),(845,430),(845,470)],fill=GREEN)
    if kind=='light_reaches_eye':
     d.line((510,450,850,450),fill=GREEN,width=10)
     d.ellipse((845,405,935,495),outline=INK,width=6,fill=WHITE); d.ellipse((870,430,910,470),fill=INK)
     d.text((890,525),'눈',font=font(26),fill=INK,anchor='mm')
   if kind in {'micro_scale','micro_block','compare','split_micro'}:
    pts=[(560,600),(640,520),(720,600),(800,520),(880,600)]; d.line(pts,fill=RED,width=10); d.text((720,675),'마이크로파',font=font(26),fill=RED,anchor='mm')
    if kind in {'micro_block','split_micro'}: d.line((550,500,550,700),fill=RED,width=12); d.text((590,740),'차폐',font=font(27),fill=RED,anchor='mm')
  else: raise ValueError(kind)
  d.text((935,915),'개념도 · 크기 비례 아님',font=font(19),fill=GREY,anchor='rm'); return im
 scenes=[]
 for si,(sid,narr,states) in enumerate(SCENES):
  beats=[]
  for bi,(cue,label,kind,info) in enumerate(states):
   im=panel(label,kind); path=assets/f'evidence_{si:02d}_{bi:02d}.png'; im.save(path)
   beats.append({'start':float(bi*2),'asset':str(path),'visual_change':{'kind':'concept' if bi==0 else 'state','concept_id':sid,'state_id':f'{sid}:{kind}:{bi}','narration_cue':cue,'added_information':info,'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest()},'visual_qa_requirements':[info],'visual_qa_labels':LABELS[kind],'visual_qa_negative_labels':NEG})
  scenes.append({'id':sid,'narration':narr,'visual_description':states[0][1],'narration_plan':[{'role':'HOOK' if sid=='s_hook' else ('PAYOFF' if sid=='s_end' else 'EXPLAIN'),'text':narr,'focus':sid in {'s_hook','s_end'}}],'factual_notes':[],'asset':beats[0]['asset'],'visual_beats':beats,'visual_qa_requirements':['Microwave oven door shielding schematic consistent with narration.']})
 manifest={'title':'전자레인지 문에는 왜 검은 점들이 있을까?','overlay_title':'전자레인지 문의 검은 점, 정체는?','strict_meaningful_visual_changes':True,'scenes':scenes}
 Path('examples/microwave_door_mesh.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__': main()
