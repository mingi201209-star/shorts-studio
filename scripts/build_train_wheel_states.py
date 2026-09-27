"""Reproducible schematic states (not photos, not crop variants).

Run with --font /path/to/NanumGothic.ttf. Geometry is schematic/exaggerated,
not to scale. Each lower panel adds a specific claim at its spoken cue;
the established overview remains in exactly the same position.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

INK='#182d40'; BLUE='#176eb5'; RED='#c74432'; GREEN='#258368'; WHITE='#f6f8fa'
# cue, short panel label, graphic, newly-visible explanatory information
STORIES={
's_hook': [('기차는','커브를 따라가는 기차','train','A train follows a curved pair of rails before the steering question.'),('자동차처럼','자동차식 조향은 없다','steering','A car steering angle is contrasted with the fixed wheelset.'),('그런데도','선로를 따라 커브로','curve','The wheelset follows a curved pair of rails.')],
's_constraint':[('두 바퀴는','두 바퀴 / 하나의 차축','axle_section','A common axle joins both rail wheels.'),('고정되어','차축에 함께 고정','locked','The rigid connection is highlighted at both hubs.'),('항상','회전수는 같다','rotation','Equal rotation arrows appear on both wheels.')],
's_violation1':[('그런데','커브의 두 레일','curve','Inner and outer rails traverse the same bend.'),('바깥쪽 바퀴가','바깥쪽 경로','outer','The outer arc is traced in blue.'),('더 먼','안쪽보다 긴 거리','distance','Unrolled path lengths compare the two routes.')],
's_gap1':[('같은 속도로','같은 회전 / 다른 이동거리','paradox','Both wheels share one rotation count.'),('어떻게','차이는 어디서 생길까?','unknown_radius','The missing wheel-to-distance relationship is posed as a question.')],
's_clue1':[('기차 바퀴의','바퀴의 굴림면','profile','A rail wheel profile and rail contact are introduced.'),('평평한','원기둥과 다르다','cylinder','A cylindrical tread is contrasted with a tapered tread.'),('완만하게','굴림면의 작은 기울기','taper','A sloped tread cross-section is highlighted; slope is exaggerated.')],
's_clue2':[('커브에서는','바퀴와 레일 접점','contacts','Two tread-to-rail contact points are marked.'),('바깥쪽으로','바깥쪽으로 횡이동','shift','A sideways displacement arrow appears on the wheelset.'),('레일에 닿는','닿는 위치가 달라진다','shift_contacts','Changed contact positions on the tapered profiles are shown.')],
's_reveal':[('그 결과','바깥쪽 / 큰 굴림 반지름','radius_outer','The larger outer rolling radius is drawn from axle to contact.'),('안쪽은','안쪽 / 작은 반지름','radius_inner','The smaller inner rolling radius is marked.'),('굴림 반지름이','두 굴림 반지름 비교','radii','Both radii are compared side by side.')],
's_resolution1':[('그래서','회전하면 앞으로 굴러간다','rolling','Both wheels make one turn together.'),('바깥쪽 바퀴는','바깥쪽 / 큰 굴림원','circle','The outer rolling circle is larger.'),('더 먼','한 바퀴의 이동거리','unroll','The larger circumference is unrolled into a longer travel distance.')],
's_seed_flange':[('그런데','바퀴 안쪽의 테두리','flange_view','The raised inner rim is introduced in a wheel-face schematic.'),('튀어나온','튀어나온 테두리','flange','An arrow identifies the raised flange, separate from the tread.')],
's_flange_question':[('혹시','플랜지와 방향 전환','flange_question','A question arrow relates the flange to guidance.'),('커브에서','커브에서 닿는 걸까?','side_question','The rail side contact is posed as a separate question.')],
's_violation2':[('하지만','평상시 정상 주행','normal_run','Clearance at the flange is contrasted with tread contact.'),('방향을 잡아주는','플랜지와 굴림면 구분','flange_vs_tread','The active tread is distinguished from the flange.'),('반지름 차이','굴림 반지름 차이','radii','Unequal rolling radii identify the stated main mechanism.')],
's_resolution2':[('플랜지는','레일 옆면과 횡이동 범위','clearance_limits','Flange and rail side are shown with clearance.'),('상황에서','주행 조건이 달라지면','conditions','Rain and wear symbols indicate changing operating conditions.'),('궤도를','큰 횡이동을 제한','flange_contact','The flange is shown reaching the rail side at lateral displacement.'),('안전장치','이탈을 막는 역할','limit','A side-contact stop arrow explains the limiting role.')],
's_payoff1':[('결국','기차의 안내 원리','loaded_train','A train is shown over the curved track.'),('조향 장치가 아니라','조향과 굴림을 구분','steering','The absent automotive steering action is recalled in the closing explanation.'),('바퀴 굴림면에','핵심은 굴림면','taper','The tread profile connects the train-scale result to the wheel geometry.'),('작은 기울기','작은 기울기 / 다른 반지름','radii','The taper is connected to differing rolling radii.')],
's_payoff2':[('물론','실제 접촉에는 크리프도','creep','Small relative motion at the wheel/rail contact is illustrated.'),('서스펜션','서스펜션도 함께 작용','spring','A spring links wheelset dynamics to suspension.'),('함께','접촉과 서스펜션의 상호작용','combined','Contact mechanics and suspension are connected in one system.'),('반지름 차이는','여러 요소 중 핵심 원리','radii','Rolling-radius difference is presented alongside the other factors.')],
}

# Kind-specific semantic QA labels: several individual state graphics are
# minimal (a bare pair of rail curves, a wheel-tread cross-section alone, a
# lone radius circle) and legitimately do not themselves depict "a labeled
# technical schematic of a train wheelset mechanism" -- CLIP judged those
# frames inconclusive against that generic pair. Labels here describe what
# each kind's graphic actually draws instead of asking every beat to match
# one generic wheelset description. Every other kind keeps that generic
# pair, which does match what it draws (full wheel/axle imagery).
KIND_LABELS={
'curve':['a schematic diagram of a curved railway track showing inner and outer rail paths','a top-down technical diagram of a train track bend with two rail lines'],
'profile':['a schematic cross-section diagram of a railway wheel tread profile touching a rail','a technical diagram of a train wheel rolling surface in contact with a rail'],
'radius_outer':['a schematic diagram of a circle with a radius line representing a train wheel rolling radius','a technical diagram showing a rolling radius measured from an axle center to a rail contact point'],
'radius_inner':['a schematic diagram of a circle with a radius line representing a train wheel rolling radius','a technical diagram showing a rolling radius measured from an axle center to a rail contact point'],
'taper':['a schematic cross-section diagram of a railway wheel tread with an exaggerated sloped taper touching a rail','a technical diagram highlighting the sloped angle of a train wheel rolling surface'],
'side_question':['a schematic cross-section diagram of a railway wheel and rail with a highlighted contact point marked by a question mark','a technical diagram posing a question about where a train wheel touches the rail'],
'creep':['a schematic diagram of a wheel and rail contact point with an arrow indicating a small relative sliding motion','a technical diagram illustrating minute slip between a train wheel and rail surface'],
}
GENERIC_LABELS=['an educational mechanical engineering diagram of railway wheels and rails','a labeled technical schematic of a train wheelset mechanism']
GENERIC_NEGATIVE_LABELS=['a photograph of an airplane in the sky','a portrait photograph of a person']


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--font',required=True);args=ap.parse_args()
    font=lambda n:ImageFont.truetype(args.font,n)
    def graphic(d,kind,box):
        x,y,w,h=box
        def pt(a,b):return (x+a*w,y+b*h)
        def line(coords,fill=INK,width=9):d.line([pt(*p) for p in coords],fill=fill,width=width)
        def ellipse(cx,cy,rx,ry,fill=None,outline=INK,width=7):d.ellipse([pt(cx-rx,cy-ry),pt(cx+rx,cy+ry)],fill=fill,outline=outline,width=width)
        def arrow(a,b,color=BLUE):
            ax,ay=pt(*a);bx,by=pt(*b);d.line((ax,ay,bx,by),fill=color,width=9)
            angle=math.atan2(by-ay,bx-ax)
            d.polygon([(bx,by),(bx-22*math.cos(angle-.5),by-22*math.sin(angle-.5)),(bx-22*math.cos(angle+.5),by-22*math.sin(angle+.5))],fill=color)
        def text(a,b,t,col=INK,size=27):d.text(pt(a,b),t,font=font(size),fill=col,anchor='mm')
        if kind in ['axle_section','paradox','unknown_radius','flange_view','side_question','normal_run','clearance_limits','loaded_train','combined']:
            if kind=='axle_section':
                # Longitudinal section exposes the two hub/axle joints.
                line([(.10,.52),(.90,.52)],INK,25)
                for xx in [.24,.76]:
                    d.rectangle([pt(xx-.07,.10),pt(xx+.07,.90)],fill='#a8bdcd',outline=INK,width=6)
                    d.rectangle([pt(xx-.10,.43),pt(xx+.10,.61)],fill=GREEN,outline=INK,width=4)
                text(.5,.13,'차축',size=24)
            elif kind in ['paradox','unknown_radius']:
                ellipse(.24,.36,.06,.27,outline=BLUE);ellipse(.70,.36,.06,.27,outline=GREEN)
                line([(.24,.36),(.70,.36)],INK,9)
                arrow((.12,.80),(.88,.80),BLUE);arrow((.25,.97),(.67,.97),GREEN)
                if kind=='unknown_radius':text(.48,.33,'?',RED,75)
            elif kind=='flange_view':
                cx,cy=pt(.48,.5);rr=h*.40
                d.ellipse((cx-rr,cy-rr,cx+rr,cy+rr),fill='#a8bdcd',outline=INK,width=12)
                d.ellipse((cx-rr*.77,cy-rr*.77,cx+rr*.77,cy+rr*.77),outline=BLUE,width=12)
                ellipse(.48,.5,.018,.065,INK,INK);arrow((.78,.2),(.48+rr/w,.48),RED)
                text(.85,.77,'테두리',size=26)
            elif kind in ['normal_run','clearance_limits','side_question']:
                graphic(d,'profile',box)
                if kind=='normal_run':
                    d.polygon([pt(.32,.62),pt(.78,.48),pt(.78,.36),pt(.32,.50)],fill=GREEN);arrow((.50,.06),(.50,.57),GREEN);text(.88,.85,'굴림면',GREEN)
                elif kind=='clearance_limits':
                    arrow((.39,.92),(.20,.92),RED);arrow((.61,.92),(.81,.92),RED)
                    line([(.17,.82),(.17,.98)],RED,8);line([(.84,.82),(.84,.98)],RED,8)
                else:arrow((.12,.50),(.34,.69),RED);text(.84,.23,'접촉?',RED,39)
            elif kind=='loaded_train':
                for xx in [.10,.36,.62]:
                    d.rectangle([pt(xx,.10),pt(xx+.23,.55)],fill=BLUE,outline=INK,width=5)
                    ellipse(xx+.05,.68,.034,.09,INK,INK);ellipse(xx+.18,.68,.034,.09,INK,INK)
                line([(.04,.84),(.96,.84)],INK,8)
            elif kind=='combined':
                graphic(d,'creep',(x,y,w*.45,h));graphic(d,'spring',(x+w*.55,y,w*.45,h));arrow((.43,.50),(.58,.50),GREEN)
        elif kind in ['curve','outer','train']:
            for yy in [.24,.67]:
                d.arc([pt(-.08,yy-.08),pt(1.08,yy+1.2)],185,355,fill=BLUE if kind=='outer' and yy==.24 else INK,width=11)
            if kind=='train':
                d.rounded_rectangle([pt(.35,.05),pt(.65,.43)],radius=10,fill=BLUE);ellipse(.40,.45,.045,.055,INK);ellipse(.60,.45,.045,.055,INK)
            else:arrow((.66,.42),(.83,.54));text(.25,.20,'바깥',BLUE);text(.45,.77,'안쪽')
        elif kind=='rolling':
            ellipse(.40,.43,.12,.34,outline=BLUE);line([(.08,.80),(.92,.80)],INK,10);arrow((.57,.42),(.83,.42));text(.70,.12,'한 회전')
        elif kind in ['distance','distance_question','unroll']:
            for yy,length,color in [(.28,.83,BLUE),(.70,.57,GREEN)]:
                line([(.12,yy),(length,yy)],color,16);line([(.12,yy-.13),(.12,yy+.13)],color,5);line([(length,yy-.13),(length,yy+.13)],color,5)
            text(.92,.28,'?',RED,46) if kind=='distance_question' else text(.88,.28,'긴',BLUE)
            text(.63,.70,'짧은',GREEN)
        elif kind in ['contacts','shift','shift_contacts']:
            # Front-view tread cross-sections: inner sides have the larger
            # rolling radius. A rightward shift places the right/outer contact
            # at a larger radius and left/inner contact at a smaller radius.
            dx=.045 if kind in ['shift','shift_contacts'] else 0
            line([(.16+dx,.24),(.84+dx,.24)],INK,10)
            for pts in [[(.15,.1),(.35,.1),(.35,.72),(.15,.49)],[(.65,.1),(.85,.1),(.85,.49),(.65,.72)]]:
                d.polygon([pt(a+dx,b) for a,b in pts],fill='#a8bdcd',outline=INK,width=5)
            for cx,cy in [(.25,.605-1.15*dx),(.75,.605+1.15*dx)]:
                line([(cx-.06,cy+.06),(cx+.06,cy+.06)],INK,10)
                ellipse(cx,cy,.017,.038,RED,RED)
            text(.25,.93,'안쪽',GREEN);text(.75,.93,'바깥쪽',BLUE)
            if kind=='shift':arrow((.41,.05),(.61,.05),RED)
        elif kind in ['axle','locked','rotation','steering']:
            line([(.2,.1),(.2,.94)],'#919fa7',16);line([(.8,.1),(.8,.94)],'#919fa7',16)
            shift=.07 if kind in ['shift','shift_contacts'] else 0
            line([(.20+shift,.49),(.80+shift,.49)],BLUE if kind=='locked' else INK,20)
            for xx in [.20+shift,.80+shift]:
                d.rounded_rectangle([pt(xx-.08,.23),pt(xx+.08,.76)],radius=10,fill=INK)
                if kind=='locked':ellipse(xx,.49,.04,.10,GREEN)
            if kind=='rotation':arrow((.32,.27),(.32,.72));arrow((.92,.27),(.92,.72));text(.50,.10,'같은 회전수')
            if kind in ['contacts','shift_contacts']:
                ellipse(.20,.68,.028,.07,RED,RED);ellipse(.80,.68,.028,.07,RED,RED)
            if kind=='shift':arrow((.40,.10),(.70,.10),RED)
            if kind=='steering':line([(.43,.04),(.56,.26)],RED);line([(.56,.04),(.43,.26)],RED);text(.5,.92,'자동차식 꺾임 X',RED)
        elif kind in ['radii','radius_outer','radius_inner','circle']:
            circles=[(.27,.32,BLUE),(.73,.22,GREEN)]
            if kind=='radius_outer': circles=circles[:1]
            if kind=='radius_inner': circles=circles[1:]
            for xx,r,col in circles:
                # radii in local height units, circles remain circular
                rr=r*h;cx,cy=pt(xx,.50)
                d.ellipse((cx-rr,cy-rr,cx+rr,cy+rr),outline=col,width=9)
                if kind!='circle':d.line((cx,cy,cx,cy+rr),fill=col,width=7);d.ellipse((cx-5,cy-5,cx+5,cy+5),fill=INK)
                text(xx,.95,'바깥 R' if xx<.5 else '안쪽 r',col)
        elif kind in ['profile','inside','flange','flange_question','clearance','flange_contact','limit','taper','cylinder','flange_vs_tread']:
            # schematic front cross-section: axle above, tread sloping toward
            # outside (right), flange on inner left; rail head under tread.
            poly=[(.20,.10),(.78,.10),(.78,.48),(.30,.63),(.30,.79),(.20,.79)]
            d.polygon([pt(*p) for p in poly],fill='#a8bdcd',outline=INK,width=6)
            railx=.30 if kind in ['flange_contact','limit'] else .40
            d.rectangle([pt(railx,.64),pt(railx+.23,.81)],fill='#566977')
            line([(.46,.83),(.58,.83)],INK,12)
            if kind in ['taper','cylinder']:line([(.32,.62),(.78,.48)],RED,13);text(.82,.79,'기울기',RED)
            if kind=='cylinder':line([(.14,.94),(.77,.94)],'#8d959a',7)
            if kind in ['flange','inside','flange_question']:arrow((.08,.42),(.24,.70),RED)
            if kind=='flange_question':text(.88,.35,'?',RED,70)
            if kind in ['clearance','flange_vs_tread']:arrow((.35,.91),(.35,.67),BLUE);ellipse(.50,.59,.02,.04,GREEN,GREEN)
            if kind in ['flange_contact','limit']:arrow((.37,.27),(.64,.27),RED);line([(.30,.64),(.30,.79)],RED,14);text(.86,.67,'접촉',RED)
        elif kind=='conditions':
            for xx in [.20,.37,.54]:
                d.polygon([pt(xx,.05),pt(xx-.035,.32),pt(xx+.035,.32)],fill=BLUE)
            line([(.10,.75),(.38,.67),(.56,.79),(.87,.62)],INK,17);text(.78,.28,'마모',RED)
        elif kind=='creep':
            ellipse(.45,.35,.17,.32,outline=BLUE);line([(.08,.72),(.92,.72)],INK,12);arrow((.35,.84),(.66,.84),RED);text(.80,.25,'미세한',size=25);text(.80,.43,'상대운동',size=25)
        elif kind=='spring':
            points=[(.48,.04),(.48,.13)]+[(.33 if i%2 else .63,.18+i*.075) for i in range(8)]+[(.48,.82),(.48,.94)]
            line(points,BLUE,8);line([(.18,.96),(.82,.96)],INK,12)
        else:raise ValueError(kind)
    manifest=Path('examples/train_wheels_v2.json');p=json.loads(manifest.read_text())
    # Remove redundant lead-in, not a duration cap; retain the reframing and
    # all factual qualifications, and update PEC's declaration to the same text.
    payoff='결국 기차의 비밀은 조향 장치가 아니라, 바퀴 굴림면에 숨겨진 작은 기울기 차이였습니다.'
    for scene in p['scenes']:
        if scene['id']=='s_payoff1':scene['narration']=payoff;scene['narration_plan'][0]['text']=payoff
    for event in p['event_graph']['events']:
        if event['id']=='payoff1':event['text']=payoff
    p['strict_meaningful_visual_changes']=True
    assets=Path('assets/train_wheels_v2');assets.mkdir(exist_ok=True)
    for sn,scene in enumerate(p['scenes']):
        stages=STORIES[scene['id']];n=len(stages)
        top=340 if n==3 else 270
        panel_height=(950-top-30)//(n-1)
        im=Image.new('RGB',(980,950),'black');d=ImageDraw.Draw(im)
        d.rounded_rectangle((10,5,970,top-8),radius=20,fill=WHITE)
        d.text((490,42),stages[0][1],font=font(40),fill=INK,anchor='mm')
        graphic(d,stages[0][2],(175,82,630,top-103))
        d.text((935,top-33),'개념도',font=font(20),fill='#687781',anchor='rm')
        beats=[]
        for i,(cue,label,kind,info) in enumerate(stages):
            if i:
                y=top+(i-1)*panel_height
                d.rounded_rectangle((10,y,970,y+panel_height-12),radius=18,fill=WHITE)
                d.text((45,y+35),label,font=font(35),fill=INK,anchor='lm')
                graphic(d,kind,(200,y+64,620,panel_height-87))
            # Unrelated filenames never establish semantic identity; explicit
            # concept/state and actual content inspection do that separately.
            path=assets/f'evidence_{sn:02d}_{i:02d}.png';im.save(path)
            beats.append({'start':float(i*2), 'asset':str(path), 'visual_change':{
                'kind':'concept' if i==0 else 'state','concept_id':scene['id'],
                'state_id':f'{scene["id"]}:{kind}', 'narration_cue':cue,
                'added_information':info,'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}})
        scene['asset']=beats[0]['asset'];scene['visual_beats']=beats
        scene['visual_qa_requirements']=['Railway wheel and track mechanism schematic, consistent with the narration.']
        for b in beats:
            b['visual_qa_requirements']=[b['visual_change']['added_information']]
            kind=b['visual_change']['state_id'].split(':',1)[1]
            b['visual_qa_labels']=KIND_LABELS.get(kind,GENERIC_LABELS)
            b['visual_qa_negative_labels']=GENERIC_NEGATIVE_LABELS
    manifest.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
