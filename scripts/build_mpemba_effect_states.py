from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import json

# NOTE: generated state assets are intentionally produced by this script in CI.
# The production manifest and narration/visual-state contract live here.

W, H = 1080, 1080
BG = (12, 16, 24)
FG = (242, 244, 248)
MUTED = (170, 180, 194)
HOT = (239, 92, 78)
COLD = (74, 155, 235)
ICE = (174, 224, 255)
ACCENT = (250, 196, 74)


def font(size, font_path=None):
    candidates = [font_path, '/usr/share/fonts/truetype/nanum/NanumGothic.ttf', '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc']
    for p in candidates:
        if p and Path(p).exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def draw_container(d, x, y, w, h, fill, frozen=0.0):
    d.rounded_rectangle((x, y, x+w, y+h), radius=28, outline=FG, width=8)
    top = y + int(h * 0.18)
    d.rounded_rectangle((x+12, top, x+w-12, y+h-12), radius=18, fill=fill)
    if frozen:
        fh = int((h-30) * frozen)
        d.rounded_rectangle((x+12, y+h-12-fh, x+w-12, y+h-12), radius=18, fill=ICE)


def render_state(path, title, kind):
    im = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(im)
    f1, f2 = font(58), font(36)
    d.text((60, 50), title, font=f1, fill=FG)
    d.line((60, 132, W-60, 132), fill=ACCENT, width=6)
    if kind in {'final_result','confirmed_real','invite'}:
        draw_container(d, 150, 310, 260, 430, HOT, 1.0 if kind != 'invite' else .55)
        draw_container(d, 670, 310, 260, 430, COLD, .45 if kind != 'invite' else .55)
        if kind == 'confirmed_real':
            d.rounded_rectangle((350, 790, 730, 910), radius=25, outline=ACCENT, width=8)
            d.text((450, 815), 'REAL', font=font(52), fill=ACCENT)
        elif kind == 'invite':
            d.text((500, 480), '?', font=font(100), fill=ACCENT)
    elif kind in {'debate_question','debate','invite_setup'}:
        d.ellipse((170, 320, 410, 560), outline=FG, width=10)
        d.line((290, 440, 290, 355), fill=ACCENT, width=10)
        d.line((290, 440, 360, 475), fill=ACCENT, width=10)
        d.text((520, 360), '?' if kind == 'debate_question' else '…', font=font(150), fill=ACCENT)
        if kind == 'invite_setup':
            d.rounded_rectangle((510, 620, 870, 820), radius=25, outline=ICE, width=8)
            for yy in (660, 735):
                for xx in (555, 650, 745):
                    d.rectangle((xx, yy, xx+55, yy+55), outline=ICE, width=5)
    else:
        # Generic but semantically distinct schematic states used by the earlier scenes.
        draw_container(d, 140, 330, 270, 420, HOT, .25)
        draw_container(d, 670, 330, 270, 420, COLD, .25)
        d.line((420, 540, 660, 540), fill=ACCENT, width=10)
        d.polygon([(650,520),(690,540),(650,560)], fill=ACCENT)
        d.text((180, 820), kind.replace('_',' '), font=f2, fill=MUTED)
    im.save(path)


SCENES = [
    ('s_hook', [('HOOK', '뜨거운 물이 찬물보다 먼저 얼 수 있습니다. 얼핏 말이 안 되지만 실제로 관찰된 현상입니다.', None)], [
        ('뜨거운 물이', '뜨거운 물과 찬물의 얼기 경주', 'frost_race', 'Two water containers, hot and cold, racing toward freezing.', '뜨거운 물과 찬물이 어느 쪽이 먼저 어는지 겨루는 모습'),
    ]),
    ('s_clue', [('CLUE', '핵심은 뜨거운 물이 식는 동안 조건 자체가 바뀐다는 점입니다. 단순히 온도만 내려가는 경주가 아닙니다.', None)], [
        ('핵심은', '식는 동안 조건 변화', 'conditions_change', 'Hot water changing physical conditions while cooling.', '뜨거운 물이 식는 동안 조건이 달라지는 모습'),
    ]),
    ('s_reveal', [('REVEAL', '뜨거운 물은 증발로 물의 양을 줄이고, 대류도 더 강하게 일으킵니다. 그래서 열을 잃는 방식부터 달라집니다.', None)], [
        ('증발로', '증발로 물의 양 감소', 'evaporation', 'Steam leaving the hot container, reducing its water amount.', '뜨거운 물에서 수증기가 빠져나가 물의 양이 줄어드는 모습'),
        ('대류도', '더 강한 대류', 'convection', 'Strong circulation arrows inside the hot-water container.', '뜨거운 물 안에서 강한 대류가 도는 모습'),
        ('열을 잃는', '열 손실 방식 변화', 'heat_loss_start', 'Heat arrows leaving the hot-water container through multiple paths.', '뜨거운 물이 여러 경로로 열을 잃는 모습'),
    ]),
    ('s_synthesis', [('SYNTHESIS', '또 찬물은 어는점 아래에서도 바로 얼지 않는 과냉각을 겪을 수 있습니다. 이런 차이들이 함께 작용합니다.', None)], [
        ('찬물은', '찬물은 아직 액체', 'cold_liquid', 'A schematic diagram of a single cold-water container sitting exactly at a freezing-point line, not yet turned to ice.', '찬물 용기가 어는점 선에 딱 머물러 아직 얼지 않고 있는 모습'),
        ('과냉각을 거칩니다', '과냉각의 차이', 'supercool', "A schematic line-graph diagram showing cold water's temperature dipping below the freezing point before turning to ice, next to hot water freezing right at the freezing line.", '찬물의 온도 그래프가 어는점 아래로 내려갔다가 어는 과냉각 구간을 보여주는 모습'),
        ('함께 작용해', '세 가지가 함께', 'synthesis', 'A schematic diagram with three small icons -- evaporation, convection, and supercooling -- each connected by an arrow into one combined ice-cube result icon.', '증발, 대류, 과냉각 세 아이콘이 화살표로 모여 하나의 얼음 결과로 합쳐지는 모습'),
    ]),
    ('s_end', [('PAYOFF', '그래서 뜨거운 물이 찬물보다 먼저 얼어 실제로 일어날 수 있습니다. 정확히 언제, 어떤 조건에서 그런지는 지금도 연구되고 있습니다. 다음에 얼음을 얼릴 때 어떤 쪽이 먼저 얼지 직접 확인해봅시다.', None)], [
        ('그래서 뜨거운 물이', '뜨거운 쪽이 먼저 얼음', 'final_result', 'A schematic diagram of a fully frozen hot-water container with a checkmark and finish flag, next to a still partly liquid cold-water container.', '뜨거운 물 용기는 완전히 얼어 체크 표시가 있고, 찬물 용기는 아직 액체인 최종 비교 모습'),
        ('실제로 일어날 수', '실제로 확인된 일', 'confirmed_real', 'A schematic diagram of a "REAL" stamp badge overlaid on the two containers, confirming this is a genuinely observed result.', '실제로 라는 도장이 두 용기 위에 찍혀 있어 진짜로 관찰된 현상임을 보여주는 모습'),
        ('정확히 언제', '언제, 어떤 조건에서', 'debate_question', 'A schematic diagram of a clock and calendar icon with a large question mark, asking exactly when and under what conditions.', '시계와 달력 아이콘 옆에 커다란 물음표가 있어 정확한 시점과 조건을 묻는 모습'),
        ('지금도 연구되고 있습니다', '아직 연구 중', 'debate', 'A schematic diagram of a magnifying glass over the text "results vary by condition", representing ongoing scientific study.', '조건마다 결과가 다르다는 문구를 돋보기로 들여다보는, 아직 연구 중임을 보여주는 모습'),
        ('다음에 얼음을 얼릴 때', '다음 실험', 'invite_setup', 'A schematic diagram of an ice-cube tray icon next to a small clock, suggesting trying this again next time.', '얼음 트레이와 작은 시계 아이콘으로 다음에 다시 해보자는 뜻을 보여주는 모습'),
        ('직접 확인해', '직접 확인해보기', 'invite', 'A schematic diagram of two simple water containers with a question mark between them, inviting the viewer to try the experiment themselves.', '두 개의 물통 사이에 물음표가 있어 직접 실험해보도록 초대하는 모습'),
    ]),
]

NEG = ['a photograph of a cat', 'a landscape photograph of mountains']


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--font', default=None)
    args = ap.parse_args()
    out = Path('generated/mpemba_effect')
    out.mkdir(parents=True, exist_ok=True)
    manifest = {'title':'뜨거운 물이 찬물보다 먼저 얼 수 있는 이유','scenes':[]}
    for sid, narration, beats in SCENES:
        scene = {'id':sid, 'narration':narration, 'visual_beats':[]}
        for cue, label, kind, pos, desc in beats:
            p = out / f'{sid}_{kind}.png'
            render_state(p, label, kind)
            scene['visual_beats'].append({'cue':cue,'label':label,'kind':kind,'asset':str(p),'positive_prompt':pos,'description':desc,'negative_prompts':NEG})
        manifest['scenes'].append(scene)
    Path('examples/mpemba_effect.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')

if __name__ == '__main__':
    main()
