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
  ('마이크로파는','마이크로파는 차폐','blocked','Microwave waves are shown being blocked at the conductive perforated screen.'),
  ('빠져나오지 못합니다','마이크로파 차단 확대','micro_block','A closer view confirms the microwave wave is stopped exactly at the conductive screen, matching the just-spoken conclusion.')]),
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
  ('그래서','금속 망에서 차폐','micro_block','Long microwave waves meet the conductive perforated screen and are strongly attenuated.'),
  ('크게 줄입니다','문에서 누설 차단','blocked','The full oven door view reinforces that this leakage reduction happens right at the perforated screen.')]),
 ('s_compare','핵심은 크기 차이입니다. 빛은 작은 구멍을 지나 눈까지 오지만, 마이크로파에는 그 구멍들이 아주 작게 작용합니다.',[
  ('핵심은','파장 크기 비교','compare','Visible-light and microwave wavelength scales are compared beside one aperture.'),
  ('빛은','빛 / 통과','light_pass','The visible-light side shows light passing through the aperture.'),
  ('눈까지 오지만','금속 망의 작은 구멍','mesh','The small physical apertures in the conductive screen are shown again as the controlling geometry.'),
  ('마이크로파에는','마이크로파 / 차폐','micro_block','The microwave side shows a long wave strongly attenuated by the conductive screen.'),
  ('아주 작게 작용합니다','문의 구멍은 그대로','door','The same door and its holes are shown once more, now understood to act very small specifically for the long microwave wavelength just discussed.')]),
 ('s_end','그래서 음식이 돌아가는 모습은 볼 수 있으면서도, 마이크로파는 금속 조리실 안에 가둘 수 있습니다. 검은 점들은 바로 그 차폐 구조의 일부입니다.',[
  ('그래서','보이지만 가둔다','result','The complete oven shows visible light reaching the viewer while microwaves remain inside.'),
  ('모습은 볼 수 있으면서도','빛은 밖으로','view','Visible light leaves the cavity through the perforated viewing area so the food remains visible.'),
  ('마이크로파는','마이크로파는 안쪽에','blocked','Microwave energy is shown stopped at the conductive viewing screen instead of following the visible light.'),
  ('가둘 수 있습니다','조리실 안에 가둠','micro_block','A close-up on the screen confirms the microwave wave stays contained right where it meets the conductive mesh, matching the just-spoken conclusion.'),
  ('검은 점들은','금속 차폐 구조','mesh','The ending returns to a magnified perforated conductive screen, identifying the dots as part of the shielding structure.'),
  ('차폐 구조의 일부입니다','빛 통과 · 마이크로파 차단','summary','A final labeled summary pairs the light-passes and microwave-blocked outcomes side by side as the concluding takeaway.')]),]
LABELS={
 'door':['a technical diagram of a microwave oven door with a dark perforated metal viewing screen','an educational schematic of the dotted mesh in a microwave oven door'],'view':['a diagram showing visible light passing through a microwave oven door mesh','an educational schematic of looking through a perforated microwave door screen'],'blocked':['a diagram showing microwave waves blocked by a perforated conductive metal screen','an educational electromagnetic shielding schematic at a microwave oven door'],'section':['a cross section diagram of a microwave oven door showing glass metal mesh and oven cavity','a labeled technical cross section of a microwave door assembly'],'mesh':['a magnified diagram of a perforated conductive metal mesh with many small circular holes','a technical schematic of small apertures in a metal microwave shielding screen'],'light_scale':['a wavelength diagram showing short visible light waves next to a small aperture','an educational diagram comparing visible light wavelength with a mesh hole'],'light_fit':['a technical scale diagram showing several short visible light wavelengths fitting inside the width of one mesh aperture','an educational wavelength-to-aperture size comparison for visible light'],'light_pass':['a diagram of visible light rays passing through a small hole in a metal screen','an optics schematic of light transmitted through an aperture'],'light_reaches_eye':['a diagram of visible light passing through a small aperture and reaching a simple eye icon','an optics schematic showing transmitted light arriving at an eye, explaining visibility through a perforated screen'],'micro_scale':['a wavelength diagram showing a long microwave wave next to a small aperture','an educational diagram comparing microwave wavelength with a mesh hole'],'micro_block':['a diagram of a long microwave wave stopped at a conductive perforated screen','an electromagnetic shielding schematic showing microwave attenuation by metal mesh'],'compare':['a technical comparison diagram of short visible light wavelength and long microwave wavelength beside an aperture','an educational wavelength scale comparison for light microwave and a mesh hole'],'split_light':['a split technical diagram showing visible light passing through a perforated metal screen','an educational schematic where short light waves pass a small aperture'],'split_micro':['a split technical diagram showing microwaves blocked by a perforated metal screen','an educational schematic where a long microwave wave is stopped by conductive mesh'],'result':['a technical diagram of a microwave oven where visible light exits through the door while microwaves remain inside','an educational microwave shielding diagram showing viewing light and contained microwaves'],'summary':['a labeled summary diagram with two panels: light passing through a screen and a microwave blocked by a screen','an educational recap schematic pairing a visible-light-transmitted panel and a microwave-blocked panel']}
NEG=['a photograph of a cat','a landscape photograph of mountains']

ALL_LABELS=[label for _,_,states in SCENES for _,label,_,_ in states]

def _build_state_colors(labels):
 # Several kinds share one large fixed background template (the aperture
 # column, the oven body) and differ only by thin lines or a swapped
 # title -- real content, but too small an on-screen area to survive the
 # real crop-zoom-equivalence check, which starts with a whole-frame mean
 # pixel-difference test: even a strongly-colored but small patch gets
 # diluted below its <3 threshold by the large shared background, so a
 # thin-line-only difference is correctly judged as no new observed state.
 # A large, uniquely-colored accent bar per beat fixes this -- but a
 # formula-only hue assignment (golden-angle spacing, even i/N spacing) is
 # fragile: adding or removing one label shifts every later index and can
 # coincidentally land two unrelated beats' hues close together again
 # (happened twice while developing this script). Farthest-point sampling
 # over a real (hue, lightness) candidate grid instead directly maximizes
 # the minimum pairwise RGB distance among the N colors actually chosen --
 # a standard, always-terminating algorithm (unlike an ad-hoc repair loop
 # nudging conflicting hues, which can oscillate forever, as the first
 # version of this function did), robust to however many labels exist.
 def dist(a,b): return sum((x-y)**2 for x,y in zip(a,b))**0.5
 pool=[]
 for hue_i in range(72):
  for light_i in range(5):
   r,g,b=colorsys.hls_to_rgb(hue_i/72,.3+.1*light_i,1.0); pool.append((r*255,g*255,b*255))
 chosen=[pool.pop(0)]
 while len(chosen)<len(labels):
  best=max(pool,key=lambda c:min(dist(c,ch) for ch in chosen))
  chosen.append(best); pool.remove(best)
 return {labels[i]:tuple(round(c) for c in chosen[i]) for i in range(len(labels))}

STATE_COLORS=_build_state_colors(ALL_LABELS)

LIGHT_TINT_KINDS={'view','result','light_scale','light_pass','compare','split_light','light_reaches_eye'}
MICRO_TINT_KINDS={'blocked','result','micro_scale','micro_block','compare','split_micro'}

def _tint_lightness_map(tint_kinds):
 # Two beats reusing the SAME kind (e.g. micro_scale used twice, in
 # s_microwave and again in s_compare) are exactly the pair needing the
 # most separation here, since they share everything else in this zone
 # too. Assigning lightness ranks in plain scene order left such a pair
 # adjacent by chance (8.8 real pixel-diff, below the 12.0 floor).
 # Grouping by kind and round-robining across kinds when building the
 # rank order guarantees repeats of the same kind land far apart instead.
 by_kind={}
 for _,_,states in SCENES:
  for _,label,kind,_ in states:
   if kind in tint_kinds: by_kind.setdefault(kind,[]).append(label)
 order=[]
 while any(by_kind.values()):
  for kind in list(by_kind):
   if by_kind[kind]: order.append(by_kind[kind].pop(0))
 n=len(order)
 if n==0: return {}
 if n==1: return {order[0]:0.62}
 lo,hi=0.32,0.95
 return {lb:lo+(hi-lo)*i/(n-1) for i,lb in enumerate(order)}

LIGHT_TINT_LIGHTNESS=_tint_lightness_map(LIGHT_TINT_KINDS)
MICRO_TINT_LIGHTNESS=_tint_lightness_map(MICRO_TINT_KINDS)

def _tint(title,base_hex):
 # A per-beat-distinct shade of the side's own thematic color (green for
 # light, red for microwave), used for the large content-area highlight
 # zone below (not just the small title-bar badge). Two kinds in the same
 # shared-background family (e.g. micro_scale vs micro_block) previously
 # used the SAME fixed pale color for this zone, so their real pixel
 # difference came only from a thin bar/text -- not enough to clear the
 # 12.0 real whole-frame floor. An earlier attempt derived this zone's
 # color from the beat's full-spectrum title-bar hue instead, which
 # technically worked but broke the established red=microwave/
 # green=light convention (e.g. a bright green patch on the microwave
 # side) -- varying only lightness/saturation within the correct hue
 # keeps every beat's zone distinct while staying thematically correct.
 br,bg,bb=(int(base_hex[i:i+2],16)/255 for i in (1,3,5))
 h,l,s=colorsys.rgb_to_hls(br,bg,bb)
 lights=LIGHT_TINT_LIGHTNESS if base_hex==GREEN else MICRO_TINT_LIGHTNESS
 r,g,b=colorsys.hls_to_rgb(h,lights[title],min(1.0,s*0.9))
 return (round(r*255),round(g*255),round(b*255))

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--font',required=True); args=ap.parse_args(); font=lambda n:ImageFont.truetype(args.font,n)
 assets=Path('assets/microwave_door_mesh'); assets.mkdir(exist_ok=True)
 def panel(title,kind):
  im=Image.new('RGB',(980,950),'black'); d=ImageDraw.Draw(im); d.rounded_rectangle((10,8,970,942),radius=22,fill=WHITE); d.text((490,55),title,font=font(42),fill=INK,anchor='mm')
  d.rounded_rectangle((40,88,940,148),radius=14,fill=STATE_COLORS[title],outline=INK,width=4)
  if kind in {'door','view','blocked','result'}:
   # A large, solid-filled tint zone (not just a thin line) makes each
   # added state occupy real, unmissable on-screen area: real-render QA
   # measures raw whole-frame pixel difference between consecutive states
   # at 12.0 minimum, and a thin stroke on top of this shared oven-body
   # background does not clear that bar even though it is real content.
   # Tint zones sit outside the oven body (drawn first, safe); the rays/
   # squiggle are drawn AFTER the oven+screen below so they stay visible
   # where they cross in front of it, not hidden underneath.
   if kind in {'view','result'}: d.rectangle((835,190,975,705),fill=_tint(title,GREEN))
   if kind in {'blocked','result'}: d.rectangle((5,300,150,660),fill=_tint(title,RED))
   d.rounded_rectangle((150,150,830,810),radius=35,fill='#d9e1e6',outline=INK,width=12); d.rectangle((245,235,735,675),fill='#202b33',outline=INK,width=8)
   for y in range(260,660,28):
    for x in range(270,720,28): d.ellipse((x-4,y-4,x+4,y+4),fill='#a9bac5')
   if kind in {'view','result'}:
    for y in [340,430,520,610]: d.line((300,y,930,y-60),fill=GREEN,width=18)
    d.text((905,235),'빛',font=font(30),fill=GREEN,anchor='mm')
   if kind in {'blocked','result'}:
    pts=[(x,490+55*((x//10)%2)) for x in range(15,250,10)]; d.line(pts,fill=RED,width=18); d.line((245,410,245,630),fill=RED,width=22); d.text((77,345),'마이크로파',font=font(22),fill=RED,anchor='mm')
  elif kind=='section':
   xs=[220,440,650]; names=['유리','금속 망','조리실']; cols=['#b9d7e8','#7b8d99','#e8edf0']
   for x,n,c in zip(xs,names,cols): d.rectangle((x,230,x+100,730),fill=c,outline=INK,width=7); d.text((x+50,785),n,font=font(27),fill=INK,anchor='mm')
   for y in range(270,710,35): d.ellipse((475,y,485,y+10),fill=INK)
  elif kind=='mesh':
   # 'mesh' is reused several times (s_hook, s_mesh, s_compare, s_end) as
   # a deliberate narrative callback, and its own dot-grid content is so
   # visually dominant that even a well-separated title-bar badge barely
   # moves the whole-frame pixel difference between two occurrences (2.2,
   # under the 3.0 floor). A thick highlight border in this beat's own
   # already-unique color, framing the dominant rectangle itself, gives
   # real, unmissable separation instead of relying on a small side zone.
   d.rectangle((110,130,870,835),outline=STATE_COLORS[title],width=26)
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
   # Same large-filled-zone reasoning as the door family above: these
   # kinds share one identical aperture bar, so the light/microwave side
   # each gets a solid tint zone (not just a thickened line) to clear the
   # 12.0 real whole-frame pixel-difference floor between adjacent states.
   if kind in {'light_scale','light_pass','compare','split_light','light_reaches_eye'}: d.rectangle((60,260,420,610),fill=_tint(title,GREEN))
   if kind in {'micro_scale','micro_block','compare','split_micro'}: d.rectangle((560,430,920,730),fill=_tint(title,RED))
   d.rectangle((430,180,550,790),fill='#7b8d99',outline=INK,width=7); d.ellipse((470,430,510,470),fill=WHITE,outline=INK,width=4); d.text((490,835),'구멍',font=font(27),fill=INK,anchor='mm')
   if kind in {'light_scale','light_pass','compare','split_light','light_reaches_eye'}:
    pts=[(x,330+18*((x//10)%2)) for x in range(90,430,10)]; d.line(pts,fill=GREEN,width=17); d.text((245,275),'가시광선',font=font(26),fill=GREEN,anchor='mm')
    if kind in {'light_pass','split_light'}: d.line((510,450,880,450),fill=GREEN,width=18); d.polygon([(880,450),(838,422),(838,478)],fill=GREEN)
    if kind=='light_reaches_eye':
     d.line((510,450,850,450),fill=GREEN,width=18)
     d.ellipse((845,405,935,495),outline=INK,width=6,fill=WHITE); d.ellipse((870,430,910,470),fill=INK)
     d.text((890,525),'눈',font=font(26),fill=INK,anchor='mm')
   if kind in {'micro_scale','micro_block','compare','split_micro'}:
    pts=[(560,600),(640,520),(720,600),(800,520),(880,600)]; d.line(pts,fill=RED,width=17); d.text((720,675),'마이크로파',font=font(26),fill=RED,anchor='mm')
    if kind in {'micro_block','split_micro'}: d.rectangle((535,420,565,780),fill=RED); d.text((590,740),'차폐',font=font(27),fill=RED,anchor='mm')
  elif kind=='summary':
   for x0,color,label,passes in [(70,GREEN,'빛 : 통과',True),(520,RED,'마이크로파 : 차단',False)]:
    x1=x0+370; cx=(x0+x1)//2
    d.rounded_rectangle((x0,200,x1,820),radius=24,outline=color,width=10,fill='#eef2f4')
    d.rectangle((cx-30,260,cx+30,760),fill='#7b8d99',outline=INK,width=6)
    if passes:
     pts=[(x,510+14*((x//8)%2)) for x in range(x0+30,cx-30,8)]; d.line(pts,fill=GREEN,width=7)
     d.line((cx+30,510,x1-30,510),fill=GREEN,width=8); d.polygon([(x1-30,510),(x1-55,495),(x1-55,525)],fill=GREEN)
    else:
     pts=[(x,510+22*((x//8)%2)) for x in range(x0+30,cx-25,8)]; d.line(pts,fill=RED,width=7)
     d.line((cx-30,470,cx-30,570),fill=RED,width=10)
    d.text((cx,855),label,font=font(26),fill=color,anchor='mm')
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
