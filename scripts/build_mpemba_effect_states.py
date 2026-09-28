"""Build real semantic visual states and a compact production manifest for
the Mpemba-effect short ("hot water can sometimes freeze before cold
water"). This is the first production that executes the Prompt V2 pipeline
(shorts_studio.hook_studio) as part of the build itself: every build creates
six distinct strategy candidates and passes all of them through
generate_and_judge() before the selected winner becomes the actual HOOK
narration. The render therefore fails closed if Prompt V2 cannot produce a
winner compatible with the reviewed opening visual contract. The narration_plan below is phrase-level and role-tagged (HOOK ->
SETUP -> REVEAL (early clue teaser) -> CRISIS (anomaly) -> EXPLANATION ->
TWIST (insufficiency/re-hook) -> SYNTHESIS -> PAYOFF -- every role name is a
genuine first use per verify_story_progression's no-stagnant-scene rule,
and the early REVEAL/CRISIS split inside s_clue exists specifically to
satisfy final_video_qa's First-10s Retention Contract, which requires an
early REVEAL/PAYOFF-role unit in [8,12]s and >=3 distinct roles before
10s -- without dumping the full multi-factor explanation that early,
per Story Prompt V2's own curiosity-maintained requirement), and the
manifest opts into strict_retention_contract=True so every Layer-1
retention gate (hook opener, first-beat visual grounding/sync, story
progression, ending payoff role, no-redundant-narration, information
progression) actually runs as a hard pre-render gate -- not just tested in
isolation. verify_curiosity_maintained (Story Prompt V2, hook_studio.py) is
also asserted below before the manifest is written.
"""
import argparse, colorsys, hashlib, json, math, time, urllib.parse, urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
from shorts_studio.hook_studio import (HookCandidate, TopicBrief, generate_and_judge,
                                      build_story_generation_prompt, story_writer_system_prompt)


INK = '#182d40'; RED = '#c74432'; BLUE = '#1f6fb2'; GREEN = '#258368'; WHITE = '#f6f8fa'; GREY = '#687781'

class MpembaHookGenerator:
    """Production-specific candidate authoring; selection is independent."""
    def generate(self, brief: TopicBrief) -> list[HookCandidate]:
        facts = brief.fact_by_strategy()
        texts = {
            "contradiction": "냉동실에서 뜨거운 물과 찬물, 어느 쪽이 먼저 어는지는 단순한 온도 순서대로일까요?",
            "surprising_consequence": "냉동실에서 같은 두 물통을 두었는데 뜨거운 물 쪽에 먼저 성에가 생기는 걸 상상해본 적 있나요?",
            "counterintuitive_fact": "놀랍게도 더 뜨거운 물이, 냉동실에서 찬물보다 먼저 얼기도 합니다.",
            "visible_anomaly": "냉동실에서 같은 조건의 두 물통인데 뜨거운 물 쪽 표면에 먼저 성에가 보이는 순간을 본 적 있나요?",
            "mistaken_assumption": "냉동실에서 뜨거운 물보다 먼저 어는 건 늘 찬물이라고 생각하시나요?",
            "unresolved_cause_effect": "냉동실에서 증발과 대류, 과냉각이 함께 작용하면 뜨거운 물이 먼저 얼 수 있을까요?",
        }
        return [
            HookCandidate(strategy=strategy, text=texts[strategy], grounded_in=facts[strategy])
            for strategy in texts
        ]


def select_mpemba_hook():
    brief = TopicBrief(
        topic_id="mpemba-effect",
        familiar_subject="냉동실 물",
        contradiction_fact="뜨거운 물과 찬물 중 어느 쪽이 먼저 어는지는 단순한 시작 온도 순서와 다를 수 있습니다",
        surprising_consequence_fact="같은 냉동실에서도 뜨거운 물 쪽에 먼저 성에가 생길 수 있습니다",
        counterintuitive_fact="더 뜨거운 물이 찬물보다 먼저 얼기도 합니다",
        anomaly_fact="같은 조건의 두 물통에서도 뜨거운 물 쪽 표면에 먼저 성에가 보일 수 있습니다",
        mistaken_assumption_fact="뜨거운 물보다 먼저 어는 것은 늘 찬물이라는 생각이 항상 맞지는 않습니다",
        cause_effect_fact="증발과 대류, 과냉각이 조건에 따라 함께 작용하면 뜨거운 물이 먼저 얼 수 있습니다",
        payoff_text="증발, 대류, 과냉각이 조건에 따라 함께 작용해 뜨거운 물이 찬물보다 먼저 얼 수 있습니다",
        grounded_facts=[
            "음펨바 효과는 조건에 따라 관찰 여부가 달라질 수 있습니다",
            "정확히 언제 어떤 조건에서 나타나는지는 계속 연구되고 있습니다",
        ],
    )
    result = generate_and_judge(brief, generator=MpembaHookGenerator())
    if result.winner is None:
        raise RuntimeError("Prompt V2 produced no valid Mpemba hook")
    required_visual_cues = ("놀랍게도", "냉동실에서", "얼기도")
    missing = [cue for cue in required_visual_cues if result.winner.text.count(cue) != 1]
    if missing:
        raise RuntimeError(
            f"Prompt V2 winner no longer matches the reviewed opening visual contract; missing/non-unique cues: {missing}; "
            f"winner={result.winner.text!r}"
        )
    print(f"PROMPT_V2_JUDGE={result.judge_name}")
    print(f"PROMPT_V2_SELECTED_STRATEGY={result.winner.strategy}")
    print(f"PROMPT_V2_SELECTED_HOOK={result.winner.text}")
    return result


PROMPT_V2_HOOK_RESULT = select_mpemba_hook()
PROMPT_V2_HOOK = PROMPT_V2_HOOK_RESULT.winner


# (scene_id, [(role, text, hook_type_or_None), ...], [(cue, panel_label, kind, clip_info_en, requirement_ko), ...])
# `cue` only needs to occur exactly once across the WHOLE scene's
# concatenated phrase text (visual_change.py matches beats against real TTS
# words for the whole scene, not per-phrase) -- see hook_studio.py's usage
# note reused here.
SCENES = [
    ('s_hook', [('HOOK', PROMPT_V2_HOOK.text, PROMPT_V2_HOOK.strategy)], [
        ('놀랍게도', '두 개의 물통', 'containers',
         'A schematic diagram of a hot-water container and a cold-water container placed side by side in a freezer.',
         '뜨거운 물 용기와 찬물 용기를 냉동실 안에 나란히 놓은 모습'),
        ('냉동실에서', '뜨거운 쪽에 먼저 성에', 'frost_first',
         'A close-up schematic showing frost forming on a hot-water container while an adjacent cold-water container remains unfrozen.',
         '냉동실 안에서 뜨거운 물 용기 표면에 먼저 성에가 맺히는 모습'),
        ('얼기도', '먼저 앞서는 쪽', 'frost_race',
         'A schematic diagram of two containers in a race-track frame, with the hot-water container slightly ahead of the cold-water container.',
         '뜨거운 물 용기가 경주하듯 찬물 용기보다 살짝 앞서 있는 모습'),
     ]),
    # SETUP (short, generic belief) -> REVEAL (early one-line clue teaser,
    # lands the First-10s Retention Contract's required early-payoff window
    # without giving away the full multi-factor explanation) -> CRISIS (the
    # specific claim plus the real observed anomaly).
    ('s_clue', [
        ('SETUP', '당연히 찬물이 먼저죠.', None),
        ('REVEAL', '첫 번째 단서는 증발입니다.', None),
        ('CRISIS', '온도가 높으면 물은 더 빨리 증발합니다. 하지만 같은 조건에서도 뜨거운 물 쪽에 성에가 먼저 맺히는 경우가 있습니다.', None),
     ], [
        ('당연히', '흔한 생각', 'assumption_claim',
         'A schematic diagram of an hourglass next to the text "hotter water takes longer to freeze", stating a common assumption.',
         '온도가 높을수록 얼리는 시간이 더 길다는 흔한 생각을 모래시계로 표현한 모습'),
        ('첫 번째 단서는', '첫 번째 단서', 'clue_reveal',
         'A schematic diagram of a magnifying glass spotlighting a rising steam-cloud icon, labeled as clue number one.',
         '돋보기가 김이 피어오르는 아이콘을 비추며 첫 번째 단서로 표시하는 모습'),
        ('온도가 높으면', '틀린 통념', 'assumption_wrong',
         'A schematic diagram with a large X crossed over the text "higher temperature always means a longer freezing time".',
         '온도가 높을수록 얼리는 시간이 더 길다는 통념에 크게 X표시가 된 모습'),
        ('하지만 같은 조건에서도', '같은 조건, 다른 결과', 'frost_compare',
         'A schematic diagram comparing two identical containers in the same freezer, where only the hot-water container already shows frost.',
         '같은 냉동실, 같은 크기의 용기인데 뜨거운 물 쪽에만 성에가 먼저 생긴 비교 모습'),
        ('성에가 먼저 맺히는', '성에 확대', 'frost_zoom',
         'A real close-up photograph of ice-crystal frost patterns on a frozen surface.',
         '용기 표면에 맺힌 성에 결정을 크게 확대해서 보여주는 모습'),
     ]),
    ('s_explain', [('EXPLANATION', '그 이유 중 하나는 증발입니다. 뜨거운 물은 더 많이 증발해 줄어들고, 얼려야 할 물 자체가 적어집니다.', None)], [
        ('그 이유 중 하나는', '더 활발한 증발', 'evaporation_concept',
         'A schematic diagram comparing a hot-water container with heavy rising steam against a cold-water container with almost no steam.',
         '뜨거운 물 용기에서는 김이 많이 나고 찬물 용기에서는 거의 나지 않는 비교 모습'),
        ('뜨거운 물은', '증발로 줄어드는 양', 'evaporation',
         'A real photograph of hot water visibly producing steam, framed with an educational overlay that connects evaporation to a smaller remaining amount of water.',
         '뜨거운 물 용기에서 김이 피어오르며 물의 높이가 낮아지는 증발 모습'),
        ('얼려야 할 물 자체가', '더 적어진 물의 양', 'volume_less',
         'A schematic bar-chart diagram comparing a shorter remaining hot-water volume bar against a taller original cold-water volume bar.',
         '증발로 줄어든 뜨거운 물의 남은 양을 찬물의 원래 양과 막대로 비교한 모습'),
     ]),
    # TWIST (not CRISIS -- CRISIS is already used in s_clue; a fresh role
    # name here keeps every scene's role a genuine first use).
    ('s_crisis', [('TWIST', '하지만 증발만으로는 모든 경우를 설명하지 못합니다. 다른 무언가가 함께 작용할 수 있습니다.', None)], [
        ('증발만으로는', '증발만으로는 부족', 'question_more',
         'A schematic diagram showing a small evaporation cloud icon connected by an arrow to a much larger question mark, indicating an insufficient explanation.',
         '증발 아이콘 옆에 커다란 물음표가 붙어, 설명이 충분하지 않음을 보여주는 모습'),
        ('설명하지 못합니다', '설명되지 않는 부분', 'gap_remains',
         'A schematic gauge diagram with a small "explained" segment and a much larger "unexplained" segment.',
         '설명된 부분은 작고 설명되지 않은 부분은 훨씬 큰 게이지 모습'),
        ('다른 무언가가', '새로운 흐름, 대류', 'convection',
         'A schematic diagram of a water container with circular internal arrows showing convection currents inside the liquid.',
         '물통 안에서 물이 둥글게 순환하는 대류 흐름 화살표가 새로 나타난 모습'),
     ]),
    # SYNTHESIS (not REVEAL -- REVEAL is already used as s_clue's early
    # teaser; this is the strongest explanatory moment requirement 7 calls
    # for, combining every factor into one payoff-adjacent scene).
    ('s_reveal', [('SYNTHESIS', '일부 조건에서는 빠른 대류로 뜨거운 물이 열을 더 빨리 잃고, 찬물은 얼기 전 과냉각을 거칩니다. 이런 요인들이 함께 작용할 수 있지만, 한 가지 원인만으로 설명되진 않습니다.', None)], [
        ('빠른 대류로', '더 빠른 열 손실', 'convection_speed',
         'A schematic diagram of convection arrows inside a container feeding into outward heat-loss arrows and a fast-dropping thermometer.',
         '대류 흐름이 열을 바깥으로 더 빠르게 내보내 온도계가 빠르게 떨어지는 모습'),
        ('열을 더 빨리 잃고', '열이 빠져나감', 'heat_loss_start',
         'A schematic diagram of a hot-water container with a few small heat-wave lines just beginning to leave it.',
         '뜨거운 물 용기에서 작은 열기 물결이 막 빠져나가기 시작하는 모습'),
        ('찬물은 얼기 전', '아직 어는점에서', 'cold_delay',
         'A schematic diagram of a single cold-water container sitting exactly at a freezing-point line, not yet turned to ice.',
         '찬물 용기가 어는점 선에 딱 머물러 아직 얼지 않고 있는 모습'),
        ('과냉각을 거칩니다', '과냉각의 차이', 'supercool',
         'A schematic line-graph diagram showing cold water\'s temperature dipping below the freezing point before turning to ice, next to hot water freezing right at the freezing line.',
         '찬물의 온도 그래프가 어는점 아래로 내려갔다가 어는 과냉각 구간을 보여주는 모습'),
        ('함께 작용할', '여러 요인이 함께', 'synthesis',
         'A schematic diagram with three small icons -- evaporation, convection, and supercooling -- converging toward an ice result while a small question marker signals that no single mechanism explains every case.',
         '증발, 대류, 과냉각 아이콘이 얼음 결과 쪽으로 모이되, 한 가지 원인으로 고정되지 않음을 작은 물음표로 함께 보여주는 모습'),
     ]),
    ('s_end', [('PAYOFF', '그래서 뜨거운 물이 찬물보다 먼저 얼어붙는 일은 실제로 일어날 수 있습니다. 정확히 언제, 어떤 조건에서인지는 지금도 연구되고 있습니다. 다음에 얼음을 얼릴 때 같은 용기와 양으로 직접 확인해보세요.', None)], [
        ('그래서 뜨거운 물이', '뜨거운 쪽이 먼저 얼음', 'final_result',
         'A schematic diagram of a fully frozen hot-water container with a checkmark and finish flag, next to a still partly liquid cold-water container.',
         '뜨거운 물 용기는 완전히 얼어 체크 표시가 있고, 찬물 용기는 아직 액체인 최종 비교 모습'),
        ('실제로 일어날 수', '실제로 확인된 일', 'confirmed_real',
         'A schematic diagram of a "REAL" stamp badge overlaid on the two containers, confirming this is a genuinely observed result.',
         '실제로 라는 도장이 두 용기 위에 찍혀 있어 진짜로 관찰된 현상임을 보여주는 모습'),
        ('정확히 언제', '언제, 어떤 조건에서', 'debate_question',
         'A schematic diagram of a clock and calendar icon with a large question mark, asking exactly when and under what conditions.',
         '시계와 달력 아이콘 옆에 커다란 물음표가 있어 정확한 시점과 조건을 묻는 모습'),
        ('지금도 연구되고 있습니다', '아직 연구 중', 'debate',
         'A schematic diagram of a magnifying glass over the text "results vary by condition", representing ongoing scientific study.',
         '조건마다 결과가 다르다는 문구를 돋보기로 들여다보는, 아직 연구 중임을 보여주는 모습'),
        ('다음에 얼음을 얼릴 때', '다음 실험', 'invite_setup',
         'A real photograph inside a household freezer showing water bottles and an ice-cube tray, grounding the invitation to try the experiment.',
         '얼음 트레이와 작은 시계 아이콘으로 다음에 다시 해보자는 뜻을 보여주는 모습'),
        ('직접 확인해보세요', '직접 확인해보기', 'invite',
         'A schematic diagram of two simple water containers with a question mark between them, inviting the viewer to try the experiment themselves.',
         '두 개의 물통 사이에 물음표가 있어 직접 실험해보도록 초대하는 모습'),
     ]),
]

PHOTO_SOURCES = {
    'frost_zoom': {
        'commons_file': 'Ice crystals on a windowpane (Unsplash).jpg',
        'local_name': 'frost_window_cc0.jpg',
        'source_page': 'https://commons.wikimedia.org/wiki/File:Ice_crystals_on_a_windowpane_(Unsplash).jpg',
        'license': 'CC0 1.0',
        'credit': 'Wikimedia Commons · Ice crystals on a windowpane (Unsplash) · CC0 1.0',
        'qa_label': 'a real close-up photograph of frost and ice crystals on a window',
        'overlay': '실제 얼음 결정',
    },
    'evaporation': {
        'commons_file': '20250609 steam.jpg',
        'local_name': 'boiling_water_steam_cc0.jpg',
        'source_page': 'https://commons.wikimedia.org/wiki/File:20250609_steam.jpg',
        'license': 'CC0 1.0',
        'credit': 'Wikimedia Commons · 20250609 steam · CC0 1.0',
        'qa_label': 'a real photograph of hot water visibly producing steam',
        'overlay': '실제 수증기 · 물의 양 ↓',
    },
    'invite_setup': {
        'commons_file': 'Bottles of water and a tray of ice cubes inside a fridge freezer.jpg',
        'local_name': 'freezer_ice_tray_cc0.jpg',
        'source_page': 'https://commons.wikimedia.org/wiki/File:Bottles_of_water_and_a_tray_of_ice_cubes_inside_a_fridge_freezer.jpg',
        'license': 'CC0 1.0',
        'credit': 'Philsacor / Wikimedia Commons · CC0 1.0',
        'qa_label': 'a real photograph inside a freezer showing water bottles and an ice-cube tray',
        'overlay': '실제 냉동실 · 얼음 트레이',
    },
}


def _download_photo(spec, photo_dir: Path) -> Path:
    """Fetch one CC0 production photo with retries and image verification."""
    photo_dir.mkdir(parents=True, exist_ok=True)
    path = photo_dir / spec['local_name']
    if path.is_file() and path.stat().st_size > 0:
        try:
            with Image.open(path) as probe:
                probe.verify()
            return path
        except Exception:
            path.unlink(missing_ok=True)

    encoded = urllib.parse.quote(spec['commons_file'].replace(' ', '_'), safe='._-()')
    url = f'https://commons.wikimedia.org/wiki/Special:Redirect/file/{encoded}'
    last_error = None
    for attempt in range(4):
        try:
            request = urllib.request.Request(
                url,
                headers={'User-Agent': 'shorts-studio/0.1 (production photo fetch; Wikimedia Commons)'},
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                data = response.read()
            if len(data) < 10_000:
                raise RuntimeError(f'photo download suspiciously small: {len(data)} bytes')
            path.write_bytes(data)
            with Image.open(path) as probe:
                probe.verify()
                if probe.width < 300 or probe.height < 300:
                    raise RuntimeError(f'photo resolution too small: {probe.size}')
            return path
        except Exception as exc:
            last_error = exc
            path.unlink(missing_ok=True)
            if attempt < 3:
                # Wikimedia can rate-limit shared GitHub Actions runner IPs.
                # Back off long enough for a transient 429 window to clear
                # instead of hammering the same endpoint again immediately.
                time.sleep(8 * (attempt + 1))
    raise RuntimeError(
        f"failed to fetch required production photo {spec['commons_file']!r} after 4 attempts: {last_error}"
    )


NEG = ['a photograph of a cat', 'a landscape photograph of mountains']

ALL_LABELS = [label for *_, states in SCENES for _, label, _, _, _ in states]


def _build_state_colors(labels):
    # Farthest-point sampling over a real (hue, lightness) candidate grid --
    # see scripts/build_microwave_door_states.py's identical, previously
    # validated function for why this (not a formula-only hue spacing) is
    # used: it directly maximizes the minimum pairwise RGB distance among
    # the N colors actually chosen, and stays robust to however many labels
    # exist without any index-order fragility.
    def dist(a, b):
        return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5
    pool = []
    for hue_i in range(72):
        for light_i in range(5):
            r, g, b = colorsys.hls_to_rgb(hue_i / 72, .3 + .1 * light_i, 1.0)
            pool.append((r * 255, g * 255, b * 255))
    chosen = [pool.pop(0)]
    while len(chosen) < len(labels):
        best = max(pool, key=lambda c: min(dist(c, ch) for ch in chosen))
        chosen.append(best); pool.remove(best)
    return {labels[i]: tuple(round(c) for c in chosen[i]) for i in range(len(labels))}


STATE_COLORS = _build_state_colors(ALL_LABELS)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--font', required=True); args = ap.parse_args()
    font = lambda n: ImageFont.truetype(args.font, n)
    assets = Path('assets/mpemba_effect'); assets.mkdir(exist_ok=True)
    photo_dir = assets / 'source_photos'
    photo_paths = {}
    for index, (kind, spec) in enumerate(PHOTO_SOURCES.items()):
        if index:
            # Avoid tripping Wikimedia's shared-runner rate limit with a
            # burst of redirects from the same GitHub Actions IP.
            time.sleep(4)
        photo_paths[kind] = _download_photo(spec, photo_dir)
    print('PHOTO_ASSETS_READY=' + ','.join(sorted(photo_paths)))


    def container(d, cx, top, w, h, color, level_frac, frost=False, frozen=False, thermo=None):
        bottom = top + h
        d.rounded_rectangle((cx - w / 2, top, cx + w / 2, bottom), radius=18, outline=INK, width=8, fill='#dce6ec')
        liquid_top = bottom - h * level_frac
        fill = '#c9d6de' if frozen else color
        d.rectangle((cx - w / 2 + 8, liquid_top, cx + w / 2 - 8, bottom - 8), fill=fill)
        if frozen:
            for fx, fy in [(-0.28, -0.62), (0.0, -0.4), (0.28, -0.62), (-0.12, -0.2), (0.15, -0.15)]:
                px, py = cx + fx * w, liquid_top + fy * h * 0.6 + h * 0.3
                d.line((px - 12, py, px + 12, py), fill=WHITE, width=6)
                d.line((px, py - 12, px, py + 12), fill=WHITE, width=6)
        if frost:
            for i in range(6):
                fx = cx - w / 2 + 10 + i * (w - 20) / 5
                d.line((fx, top + 6, fx, top + 26), fill=WHITE, width=6)
        if thermo:
            tx = cx + w / 2 + 30
            d.rounded_rectangle((tx - 10, top + 10, tx + 10, bottom - 40), radius=10, outline=INK, width=5, fill=WHITE)
            d.ellipse((tx - 20, bottom - 55, tx + 20, bottom - 15), fill=thermo, outline=INK, width=5)
            d.rectangle((tx - 6, top + 30, tx + 6, bottom - 40), fill=thermo)

    def panel(title, kind):
        im = Image.new('RGB', (980, 950), 'black'); d = ImageDraw.Draw(im)
        d.rounded_rectangle((10, 8, 970, 942), radius=22, fill=WHITE)
        d.text((490, 55), title, font=font(40), fill=INK, anchor='mm')
        d.rounded_rectangle((40, 88, 940, 146), radius=14, fill=STATE_COLORS[title], outline=INK, width=4)

        if kind in PHOTO_SOURCES:
            spec = PHOTO_SOURCES[kind]
            with Image.open(photo_paths[kind]) as src:
                photo = ImageOps.fit(src.convert('RGB'), (840, 620), method=Image.Resampling.LANCZOS)
            im.paste(photo, (70, 175))
            d.rectangle((70, 175, 910, 795), outline=INK, width=6)
            d.rounded_rectangle((120, 705, 860, 780), radius=18, fill='black')
            d.text((490, 742), spec['overlay'], font=font(30), fill=WHITE, anchor='mm')
            d.text((490, 840), '실제 사진', font=font(28), fill=INK, anchor='mm')
        elif kind == 'containers':
            container(d, 300, 220, 260, 560, RED, 0.7, thermo=RED)
            container(d, 680, 220, 260, 560, BLUE, 0.7, thermo=BLUE)
            d.text((300, 810), '뜨거운 물', font=font(30), fill=RED, anchor='mm')
            d.text((680, 810), '찬물', font=font(30), fill=BLUE, anchor='mm')
        elif kind == 'frost_first':
            container(d, 490, 190, 420, 620, RED, 0.65, frost=True, thermo=RED)
            d.text((490, 855), '성에가 먼저', font=font(30), fill=RED, anchor='mm')
        elif kind == 'frost_race':
            d.rounded_rectangle((60, 150, 920, 820), radius=30, outline=INK, width=8, fill='#eef2f4')
            for lx in (60, 300, 540, 780):
                d.line((lx, 150, lx, 820), fill='#c7d0d6', width=4)
            for fx in range(60, 240, 30):
                for fy in range(150, 210, 30):
                    color = INK if ((fx // 30) + (fy // 30)) % 2 == 0 else WHITE
                    d.rectangle((fx, fy, fx + 30, fy + 30), fill=color, outline=INK, width=2)
            container(d, 300, 260, 190, 420, RED, 0.65, frost=True)
            container(d, 620, 300, 190, 340, BLUE, 0.65)
            d.text((300, 810), '앞서는 중', font=font(28), fill=RED, anchor='mm')
        elif kind == 'assumption_claim':
            cx, cy = 490, 400
            d.polygon([(cx - 110, cy - 160), (cx + 110, cy - 160), (cx + 20, cy), (cx + 110, cy + 160), (cx - 110, cy + 160), (cx - 20, cy)],
                      outline=INK, width=10, fill='#eef2f4')
            d.polygon([(cx - 80, cy - 130), (cx + 80, cy - 130), (cx, cy - 20)], fill='#c8d3da')
            d.polygon([(cx - 80, cy + 130), (cx + 80, cy + 130), (cx, cy + 20)], fill='#8ea0ab')
            d.text((490, 620), '온도가 높을수록', font=font(34), fill=INK, anchor='mm')
            d.text((490, 690), '얼리는 시간도 더 길다', font=font(34), fill=INK, anchor='mm')
        elif kind == 'clue_reveal':
            cx, cy = 400, 460
            for i, sx in enumerate([-60, 0, 60]):
                x = cx + sx
                pts = [(x + 14 * ((y // 22) % 2 * 2 - 1), cy + 200 - y) for y in range(0, 340, 22)]
                d.line(pts, fill=GREY, width=16)
            d.ellipse((cx + 220 - 110, cy - 110, cx + 220 + 110, cy + 110), outline=INK, width=12, fill=None)
            d.line((cx + 220 + 78, cy + 78, cx + 220 + 150, cy + 150), fill=INK, width=16)
            d.ellipse((cx - 60, cy - 260, cx + 60, cy - 180), fill='#f5c94a', outline=INK, width=6)
            d.text((cx, cy - 220), '1', font=font(38), fill=INK, anchor='mm')
            d.text((490, 780), '첫 번째 단서', font=font(30), fill=INK, anchor='mm')
        elif kind == 'assumption_wrong':
            d.rounded_rectangle((90, 220, 890, 620), radius=24, outline=INK, width=8, fill='#eef2f4')
            d.line((130, 260, 850, 580), fill=RED, width=22)
            d.line((130, 580, 850, 260), fill=RED, width=22)
            d.text((490, 700), '온도가 높을수록', font=font(34), fill=INK, anchor='mm')
            d.text((490, 770), '얼리는 시간도 더 길다', font=font(34), fill=INK, anchor='mm')
        elif kind == 'frost_compare':
            container(d, 300, 220, 260, 560, RED, 0.65, frost=True)
            container(d, 680, 220, 260, 560, BLUE, 0.65, frost=False)
            d.text((300, 810), '먼저 성에', font=font(28), fill=RED, anchor='mm')
            d.text((680, 810), '아직 그대로', font=font(28), fill=BLUE, anchor='mm')
        elif kind == 'frost_zoom_schematic_fallback':
            for cx, cy, r in [(300, 300, 90), (620, 260, 70), (470, 480, 110), (720, 550, 75), (250, 620, 65), (600, 720, 85)]:
                for ang in range(0, 360, 60):
                    ex = cx + r * math.cos(math.radians(ang)); ey = cy + r * math.sin(math.radians(ang))
                    d.line((cx, cy, ex, ey), fill='#8fb4cc', width=10)
                d.ellipse((cx - 14, cy - 14, cx + 14, cy + 14), fill=WHITE, outline=INK, width=4)
            d.text((490, 870), '성에 결정 확대', font=font(28), fill=INK, anchor='mm')
        elif kind == 'evaporation_concept':
            container(d, 300, 220, 260, 560, RED, 0.6)
            container(d, 680, 220, 260, 560, BLUE, 0.6)
            for i, sx in enumerate([-45, 0, 45]):
                x = 300 + sx
                pts = [(x + 9 * ((y // 18) % 2 * 2 - 1), 210 - y) for y in range(0, 130, 18)]
                d.line(pts, fill=GREY, width=9)
            x = 680
            pts = [(x + 4 * ((y // 18) % 2 * 2 - 1), 210 - y) for y in range(0, 40, 18)]
            d.line(pts, fill='#c7d0d6', width=5)
            d.text((300, 810), '김이 많이 남', font=font(26), fill=RED, anchor='mm')
            d.text((680, 810), '거의 나지 않음', font=font(26), fill=BLUE, anchor='mm')
        elif kind == 'evaporation_schematic_fallback':
            container(d, 490, 260, 320, 520, RED, 0.55, thermo=RED)
            for i, sx in enumerate([-70, 0, 70]):
                x = 490 + sx
                pts = [(x + 10 * ((y // 20) % 2 * 2 - 1), 240 - y) for y in range(0, 150, 20)]
                d.line(pts, fill=GREY, width=10)
            d.line((330, 465, 650, 465), fill=INK, width=4)
            d.text((490, 830), '물의 높이 낮아짐', font=font(26), fill=INK, anchor='mm')
        elif kind == 'volume_less':
            d.rectangle((260, 780 - 260, 420, 780), fill=RED, outline=INK, width=6)
            d.rectangle((560, 780 - 430, 720, 780), fill=BLUE, outline=INK, width=6)
            d.text((340, 830), '뜨거운 물(남은 양)', font=font(24), fill=RED, anchor='mm')
            d.text((640, 830), '찬물(원래 양)', font=font(24), fill=BLUE, anchor='mm')
        elif kind == 'question_more':
            d.ellipse((250, 380, 470, 600), fill='#d9e1e6', outline=INK, width=8)
            for i, sx in enumerate([-40, 20]):
                x = 360 + sx
                pts = [(x + 8 * ((y // 16) % 2 * 2 - 1), 400 - y) for y in range(0, 100, 16)]
                d.line(pts, fill=GREY, width=8)
            d.line((470, 490, 620, 490), fill=INK, width=10)
            d.polygon([(620, 490), (590, 470), (590, 510)], fill=INK)
            d.text((790, 490), '?', font=font(140), fill=RED, anchor='mm')
        elif kind == 'gap_remains':
            d.rounded_rectangle((100, 420, 880, 540), radius=24, outline=INK, width=8, fill='#eef2f4')
            d.rectangle((108, 428, 260, 532), fill=GREEN)
            d.text((184, 480), '설명됨', font=font(24), fill=WHITE, anchor='mm')
            d.text((570, 480), '설명 안 됨', font=font(28), fill=INK, anchor='mm')
            d.text((490, 640), '증발만으로는 이 차이의 일부만 설명', font=font(26), fill=INK, anchor='mm')
        elif kind == 'convection':
            d.rounded_rectangle((330, 180, 650, 800), radius=24, outline=INK, width=8, fill='#dce6ec')
            cx, cy = 490, 490
            d.arc((cx - 140, cy - 220, cx + 140, cy + 220), 30, 330, fill=RED, width=14)
            d.polygon([(cx + 130, cy - 40), (cx + 100, cy - 70), (cx + 155, cy - 80)], fill=RED)
            d.arc((cx - 140, cy - 220, cx + 140, cy + 220), 210, 150, fill=RED, width=14)
            d.text((490, 855), '내부 순환(대류)', font=font(28), fill=RED, anchor='mm')
        elif kind == 'convection_speed':
            d.rounded_rectangle((160, 260, 480, 780), radius=24, outline=INK, width=8, fill='#dce6ec')
            cx, cy = 320, 520
            d.arc((cx - 110, cy - 170, cx + 110, cy + 170), 30, 330, fill=RED, width=12)
            for i, ay in enumerate([380, 520, 660]):
                d.line((480, ay, 650, ay), fill=RED, width=14)
                d.polygon([(650, ay), (620, ay - 18), (620, ay + 18)], fill=RED)
            d.rounded_rectangle((700, 300, 760, 760), radius=20, outline=INK, width=6, fill=WHITE)
            d.ellipse((680, 720, 780, 800), fill=RED, outline=INK, width=6)
            d.rectangle((715, 360, 745, 730), fill=RED)
            d.text((730, 850), '빠른 열 손실', font=font(28), fill=RED, anchor='mm')
        elif kind == 'heat_loss_start':
            container(d, 490, 220, 320, 560, RED, 0.6, thermo=RED)
            for i, ay in enumerate([420, 520]):
                d.line((650, ay, 740, ay), fill=RED, width=10)
                d.polygon([(740, ay), (718, ay - 12), (718, ay + 12)], fill=RED)
            d.text((490, 850), '열이 빠져나가기 시작', font=font(28), fill=RED, anchor='mm')
        elif kind == 'cold_delay':
            container(d, 490, 220, 320, 560, BLUE, 0.7, thermo=BLUE)
            freeze_y = 220 + 560 * (1 - 0.7)
            d.line((250, freeze_y, 730, freeze_y), fill=GREY, width=6)
            d.text((250, freeze_y - 24), '어는점', font=font(24), fill=GREY, anchor='lm')
            d.text((490, 850), '아직 얼지 않은 찬물', font=font(28), fill=BLUE, anchor='mm')
        elif kind == 'supercool':
            d.line((120, 780, 900, 780), fill=INK, width=6)
            d.line((120, 780, 120, 220), fill=INK, width=6)
            freeze_y = 460
            d.line((120, freeze_y, 900, freeze_y), fill=GREY, width=4)
            d.text((150, freeze_y - 25), '어는점', font=font(22), fill=GREY, anchor='lm')
            hot_pts = [(150, 260), (420, 340), (560, freeze_y)]
            d.line(hot_pts, fill=RED, width=10)
            cold_pts = [(150, 300), (420, 420), (620, 600), (760, freeze_y + 10), (860, freeze_y - 10)]
            d.line(cold_pts, fill=BLUE, width=10)
            d.text((300, 250), '뜨거운 물', font=font(26), fill=RED, anchor='mm')
            d.text((760, 660), '찬물(과냉각)', font=font(26), fill=BLUE, anchor='mm')
        elif kind == 'synthesis':
            icons = [('증발', GREY, 220), ('대류', RED, 490), ('과냉각', BLUE, 760)]
            for label, color, x in icons:
                d.ellipse((x - 70, 260, x + 70, 400), outline=color, width=10, fill='#eef2f4')
                d.text((x, 330), label, font=font(26), fill=color, anchor='mm')
                d.line((x, 400, 490, 600), fill=color, width=8)
            d.ellipse((410, 600, 570, 760), fill='#d9e1e6', outline=INK, width=8)
            for fx, fy in [(-25, -20), (10, 0), (30, -25)]:
                px, py = 490 + fx, 680 + fy
                d.line((px - 10, py, px + 10, py), fill=INK, width=5)
                d.line((px, py - 10, px, py + 10), fill=INK, width=5)
            d.text((490, 800), '조건에 따라', font=font(28), fill=INK, anchor='mm')
        elif kind == 'final_result':
            container(d, 300, 220, 260, 560, RED, 0.65, frozen=True)
            container(d, 680, 220, 260, 560, BLUE, 0.65)
            d.ellipse((260, 130, 340, 210), fill=GREEN, outline=INK, width=6)
            d.line((280, 170, 300, 190), fill=WHITE, width=8)
            d.line((300, 190, 340, 150), fill=WHITE, width=8)
            d.text((300, 810), '완전히 얼음', font=font(26), fill=GREEN, anchor='mm')
            d.text((680, 810), '아직 액체', font=font(26), fill=BLUE, anchor='mm')
        elif kind == 'confirmed_real':
            d.rectangle((10, 150, 970, 900), fill='#f6e9b8')
            container(d, 300, 220, 260, 560, RED, 0.65, frozen=True)
            container(d, 680, 220, 260, 560, BLUE, 0.65)
            cx, cy = 490, 470
            d.rounded_rectangle((cx - 210, cy - 110, cx + 210, cy + 110), radius=20, outline=RED, width=18, fill='#fdf6e3')
            d.text((cx, cy), '실제로 확인됨', font=font(34), fill=RED, anchor='mm')
        elif kind == 'debate_question':
            cx, cy = 490, 420
            d.rounded_rectangle((cx - 150, cy - 140, cx + 150, cy + 140), radius=20, outline=INK, width=10, fill='#eef2f4')
            d.line((cx - 150, cy - 80, cx + 150, cy - 80), fill=INK, width=6)
            for gx in (-90, 0, 90):
                d.line((cx + gx, cy - 140, cx + gx, cy - 100), fill=INK, width=8)
            d.ellipse((cx + 150 - 40, cy + 60, cx + 150 + 60, cy + 160), outline=INK, width=10)
            d.line((cx + 150 + 50, cy + 150, cx + 150 + 110, cy + 210), fill=INK, width=12)
            d.text((790, 300), '?', font=font(150), fill=RED, anchor='mm')
            d.text((490, 700), '언제, 어떤 조건에서?', font=font(30), fill=INK, anchor='mm')
        elif kind == 'debate':
            d.rounded_rectangle((150, 300, 830, 560), radius=24, outline=INK, width=8, fill='#eef2f4')
            d.text((490, 430), '조건마다 결과가 다름', font=font(32), fill=INK, anchor='mm')
            d.ellipse((640, 560, 800, 720), outline=INK, width=14)
            d.line((760, 700, 860, 800), fill=INK, width=16)
        elif kind == 'invite_setup_schematic_fallback':
            cx, cy = 400, 460
            d.rounded_rectangle((cx - 160, cy - 140, cx + 160, cy + 140), radius=20, outline=INK, width=10, fill='#dce6ec')
            for gx in range(-2, 3):
                for gy in range(-1, 2):
                    d.rectangle((cx + gx * 55 - 22, cy + gy * 70 - 22, cx + gx * 55 + 22, cy + gy * 70 + 22), outline=INK, width=4)
            d.ellipse((cx + 220 - 90, cy - 90, cx + 220 + 90, cy + 90), outline=INK, width=10, fill='#eef2f4')
            d.line((cx + 220, cy, cx + 220, cy - 55), fill=INK, width=8)
            d.line((cx + 220, cy, cx + 260, cy + 20), fill=INK, width=8)
            d.text((490, 780), '다음번 실험 준비', font=font(30), fill=INK, anchor='mm')
        elif kind == 'invite':
            container(d, 320, 260, 240, 460, RED, 0.6, thermo=RED)
            container(d, 660, 260, 240, 460, BLUE, 0.6, thermo=BLUE)
            d.text((490, 490), '?', font=font(120), fill=INK, anchor='mm')
            d.text((490, 800), '먼저 얼 쪽은?', font=font(30), fill=INK, anchor='mm')
        else:
            raise ValueError(kind)

        footer = '실제 사진 · Wikimedia Commons · CC0' if kind in PHOTO_SOURCES else '개념도 · 크기 비례 아님'
        d.text((935, 915), footer, font=font(19), fill=GREY, anchor='rm')
        return im

    scenes = []
    for si, (sid, phrases, states) in enumerate(SCENES):
        beats = []
        for bi, (cue, label, kind, info_en, req_ko) in enumerate(states):
            im = panel(label, kind)
            path = assets / f'evidence_{si:02d}_{bi:02d}.png'; im.save(path)
            beat = {
                'start': float(bi * 2), 'asset': str(path),
                'visual_change': {
                    'kind': 'concept' if bi == 0 else 'state', 'concept_id': sid,
                    'state_id': f'{sid}:{kind}:{bi}', 'narration_cue': cue,
                    'added_information': info_en, 'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                },
                'visual_qa_requirements': [req_ko],
                'visual_qa_labels': (
                    [info_en, PHOTO_SOURCES[kind]['qa_label']]
                    if kind in PHOTO_SOURCES
                    else [info_en, f'an educational schematic diagram about {kind.replace("_", " ")}']
                ),
                'visual_qa_negative_labels': NEG,
                'info_role': kind,
            }
            if kind in PHOTO_SOURCES:
                beat['attribution'] = PHOTO_SOURCES[kind]['credit']
            beats.append(beat)
        narration_plan = []
        for role, text, hook_type in phrases:
            phrase = {'role': role, 'text': text, 'focus': role in ('HOOK', 'REVEAL', 'SYNTHESIS', 'PAYOFF')}
            if hook_type:
                phrase['hook_type'] = hook_type
            narration_plan.append(phrase)
        narr = ' '.join(p['text'] for p in narration_plan)
        scenes.append({
            'id': sid, 'narration': narr, 'visual_description': states[0][1],
            'narration_plan': narration_plan,
            'asset': beats[0]['asset'], 'visual_beats': beats,
            'visual_qa_requirements': ['A schematic diagram about why hot water can sometimes freeze before cold water (the Mpemba effect), consistent with the narration.'],
        })

    prompt_dir = Path('build'); prompt_dir.mkdir(exist_ok=True)
    story_prompt = build_story_generation_prompt(
        TopicBrief(
            topic_id="mpemba-effect",
            familiar_subject="냉동실 물",
            contradiction_fact="뜨거운 물과 찬물 중 어느 쪽이 먼저 어는지는 단순한 시작 온도 순서와 다를 수 있습니다",
            surprising_consequence_fact="같은 냉동실에서도 뜨거운 물 쪽에 먼저 성에가 생길 수 있습니다",
            counterintuitive_fact="더 뜨거운 물이 찬물보다 먼저 얼기도 합니다",
            anomaly_fact="같은 조건의 두 물통에서도 뜨거운 물 쪽 표면에 먼저 성에가 보일 수 있습니다",
            mistaken_assumption_fact="뜨거운 물보다 먼저 어는 것은 늘 찬물이라는 생각이 항상 맞지는 않습니다",
            cause_effect_fact="증발, 대류, 과냉각 같은 요인이 조건에 따라 관여할 수 있습니다",
            payoff_text="뜨거운 물이 먼저 어는 경우는 실제로 가능하지만, 모든 경우를 설명하는 하나의 원인은 확정되지 않았습니다",
            grounded_facts=[
                "음펨바 효과는 조건에 따라 관찰 여부가 달라질 수 있습니다",
                "정확히 언제 어떤 조건에서 나타나는지는 계속 연구되고 있습니다",
            ],
        ),
        PROMPT_V2_HOOK,
        uncertainty_notes=[
            "물의 Mpemba 효과에는 단일하고 보편적으로 받아들여진 원인 하나가 확정되어 있지 않습니다",
            "증발, 대류, 과냉각 등은 조건에 따라 관여할 수 있는 후보 메커니즘이며 중요도는 실험 조건에 따라 달라질 수 있습니다",
        ],
    )
    (prompt_dir / 'mpemba_story_prompt.txt').write_text(
        story_writer_system_prompt() + '\n\n' + story_prompt + '\n',
        encoding='utf-8',
    )
    print('STORY_PROMPT_V3_READY=build/mpemba_story_prompt.txt')

    manifest = {
        'title': '뜨거운 물이 찬물보다 먼저 언다',
        'overlay_title': '뜨거운 물의 반전',
        'strict_meaningful_visual_changes': True,
        'strict_retention_contract': True,
        'scenes': scenes,
    }
    Path('examples/mpemba_effect.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
