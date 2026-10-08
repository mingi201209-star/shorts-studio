#!/usr/bin/env python3
"""Build the hydroplaning Shorts production.

Quality-reset production. The first ~9 seconds are four different pieces of
real, explicitly licensed footage (a car throwing spray on a flooded road,
a wet road surface, a wet tire close-up, a tire standing in a puddle in the
rain) so the opening never reads as low-budget CG; the speed line is also
real footage. A real photo of grooved rain tyres
next to a slick grounds the tread-drainage clue. The mechanism is then
shown only where no camera can see it -- the wedge under the contact
patch -- with a physically faithful side-view cross-section plus a magnified
contact-zone inset (shorts_studio.hydroplaning_section), replacing the
earlier flat-shaded 3D cylinder that a frame review judged cheap-looking and
whose exaggerated lift was misleading. A real driving POV carries the
consequence line before the payoff.

Every real clip is pinned to a concrete provider MP4 (no search results, no
rotating CDN queries) and then trimmed/cropped ONCE with FFmpeg to the
renderer's 980x950 media box, so the picture fills the box instead of being
letterboxed into a thin strip. Each beat uses a different source; no beat
is a crop/zoom of a neighbouring beat.
"""
from __future__ import annotations

import argparse, hashlib, json, os, subprocess, time, urllib.parse, urllib.request
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from shorts_studio.hydroplaning_section import render_clip as render_section_clip
from shorts_studio.hook_studio import (
    HookCandidate, TopicBrief, generate_and_judge,
    build_story_generation_prompt, story_writer_system_prompt,
)

NEG = ["a photograph of a cat", "a landscape photograph of mountains", "a city skyline"]

# Picture size inside shorts_studio.render's 980x950 media box. 12 px of black
# stays above/below so the picture never reaches the title gate's row band
# (final_video_qa.TITLE_ROW_BAND ends 10 px inside the box), which full-bleed
# footage otherwise trips once the title window has ended.
BOX_W, BOX_H = 980, 926

RAIN_TYRES_PHOTO_FILE = "Michelin rain and intermediate tyres 2005 United States GP (19889979).jpg"
RAIN_TYRES_PHOTO_PAGE = "https://commons.wikimedia.org/wiki/File:Michelin_rain_and_intermediate_tyres_2005_United_States_GP_(19889979).jpg"
RAIN_TYRES_PHOTO_ATTRIBUTION = "Ryosuke Yagi / Wikimedia Commons (Flickr) / CC BY 2.0 (cropped)"

# Pinned provider MP4s: key -> (url, landing page, attribution).
REAL_SOURCES = {
    "suv": ("https://videos.pexels.com/video-files/3999392/3999392-hd_1920_1080_24fps.mp4",
            "https://www.pexels.com/video/car-driving-on-a-rainy-day-3999392/",
            "K (@kelly) / Pexels / Pexels License"),
    "tire": ("https://videos.pexels.com/video-files/13891268/13891268-uhd_4096_2160_24fps.mp4",
             "https://www.pexels.com/video/close-up-of-car-tyre-in-rain-13891268/",
             "Erik Mclean / Pexels / Pexels License"),
    "surface": ("https://videos.pexels.com/video-files/13908904/13908904-uhd_1440_2560_50fps.mp4",
                "https://www.pexels.com/video/wet-road-13908904/",
                "Zero51 / Pexels / Pexels License"),
    "rain_tire": ("https://videos.pexels.com/video-files/39810348/16977474_1920_1080_60fps.mp4",
                  "https://www.pexels.com/video/rainfall-on-car-tire-detail-cinematic-stock-39810348/",
                  "Nothing Ahead / Pexels / Pexels License"),
    "wheel": ("https://videos.pexels.com/video-files/39140749/16655563_1440_2560_60fps.mp4",
              "https://www.pexels.com/video/close-up-of-a-fast-moving-sport-car-wheel-39140749/",
              "Erik Mclean / Pexels / Pexels License"),
    "pov": ("https://videos.pexels.com/video-files/13370432/13370432-uhd_2160_3840_25fps.mp4",
            "https://www.pexels.com/video/driving-along-a-wet-road-on-a-rainy-day-13370432/",
            "Zero51 / Pexels / Pexels License"),
}

# Prepared beat clips: key -> (source, local name, trim start s, crop w:h:x:y in source px,
# output seconds, slow-motion factor). Every clip is steady enough that the rendered beat
# can be verified frame-for-frame against it (a handheld 60 fps spray clip was tried and
# dropped: its frame-to-frame change exceeded the pinned-source check's tolerance).
REAL_CLIPS = {
    "spray": ("suv", "real_suv_spray", 3.5, "1114:1080:120:0", 6.0, 1.0),
    "surface": ("surface", "real_wet_road_surface", 0.0, "1440:1396:0:1014", 6.0, 1.0),
    "tire": ("tire", "real_tire_rain_closeup", 0.0, "2228:2160:800:0", 6.0, 1.0),
    "rain_tire": ("rain_tire", "real_tire_standing_in_rain", 2.0, "1114:1080:280:0", 6.0, 1.0),
    "fast_wheel": ("wheel", "real_fast_wheel_spin", 0.0, "1440:1396:0:700", 5.5, 1.0),
    "pov": ("pov", "real_rainy_drive_pov", 1.0, "2160:2094:0:1300", 6.0, 1.0),
}
REAL_CLIP_SECONDS = 6.0
HDR_TRANSFERS = {"arib-std-b67", "smpte2084"}
BT709_TAGS = ["-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download_required_photo(commons_file: str, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.is_file() and out.stat().st_size > 20_000:
        return out
    encoded = urllib.parse.quote(commons_file.replace(" ", "_"), safe="._-()")
    url = f"https://commons.wikimedia.org/wiki/Special:Redirect/file/{encoded}"
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "shorts-studio/0.1 (CC-licensed production asset)"})
            with urllib.request.urlopen(req, timeout=45) as r:
                data = r.read()
            if len(data) < 20_000:
                raise RuntimeError(f"download suspiciously small: {len(data)} bytes")
            out.write_bytes(data)
            from PIL import Image
            with Image.open(out) as im:
                im.verify()
            print(f"HYDROPLANING_PHOTO_READY={out} bytes={len(data)} sha256={sha(out)}")
            return out
        except Exception as exc:
            last = exc
            out.unlink(missing_ok=True)
            if attempt < 3:
                time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"failed to fetch required photo {commons_file}: {last}")


def download_required_video(url: str, out: Path, label: str) -> Path:
    """Fetch one fixed, explicitly licensed real-footage source.

    The URL is pinned to the source provider's concrete MP4, not a search
    result or a rotating CDN query.  We fail closed if the response is too
    small or not an MP4 container so a broken stock source can never silently
    degrade into a placeholder.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.is_file() and out.stat().st_size > 1_000_000:
        return out
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "shorts-studio/0.1 (licensed production asset)"},
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            if len(data) < 1_000_000:
                raise RuntimeError(f"{label} download suspiciously small: {len(data)} bytes")
            # ISO-BMFF/MP4 stores an ftyp box near the start.
            if b"ftyp" not in data[:64]:
                raise RuntimeError(f"{label} response does not look like MP4")
            out.write_bytes(data)
            print(f"HYDROPLANING_REAL_VIDEO_READY={out} bytes={len(data)} sha256={sha(out)}")
            return out
        except Exception as exc:
            last = exc
            out.unlink(missing_ok=True)
            if attempt < 3:
                time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"failed to fetch required {label} footage: {last}")


def prepare_real_clip(src: Path, out: Path, start: float, crop: str, seconds: float = REAL_CLIP_SECONDS,
                      slowmo: float = 1.0) -> Path:
    """Trim + crop + scale one real clip to exactly fill the media box.

    One FFmpeg pass (HDR tone-map when the source is HLG/PQ, trim, crop,
    Lanczos scale, constant 30 fps, H.264 CRF 16, BT.709 tags, no audio).
    Fails closed if the result is shorter than asked. ``slowmo=2`` plays a
    60 fps source at half speed into 30 fps: every source frame is kept, no
    interpolated frames are invented.
    """
    if out.is_file() and out.stat().st_size > 1_000_000:
        return out
    trc = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=color_transfer",
                          "-of", "csv=p=0", str(src)], capture_output=True, text=True, check=True).stdout.strip()
    if trc in HDR_TRANSFERS:
        # HDR (HLG/PQ) -> SDR BT.709 with FFmpeg's documented zscale+tonemap chain.
        to_sdr = ("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,"
                  "zscale=t=bt709:m=bt709:r=tv,format=yuv420p,")
    else:
        to_sdr = "scale=out_color_matrix=bt709:out_range=tv,"
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.3f}", "-t", f"{seconds / slowmo:.3f}", "-i", str(src),
        "-vf", f"{to_sdr}crop={crop},scale={BOX_W}:{BOX_H}:flags=lanczos,setsar=1,setpts={slowmo}*PTS,fps=30,format=yuv420p",
        "-an", "-c:v", "libx264", "-preset", "slow", "-crf", "16", *BT709_TAGS, "-movflags", "+faststart", str(out),
    ], check=True, capture_output=True, timeout=300)
    probe = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(out)],
        capture_output=True, text=True, check=True).stdout)
    if float(probe["format"]["duration"]) < seconds - 0.2:
        raise RuntimeError(f"prepared clip {out} is shorter than {seconds}s")
    print(f"HYDROPLANING_REAL_CLIP_PREPARED={out} sha256={sha(out)}")
    return out


def prepare_rain_tyres_photo(src: Path, out: Path) -> Path:
    """Crop the grooved rain tyres plus the slick next to them to the box aspect."""
    from PIL import Image
    with Image.open(src) as im:
        im = im.convert("RGB")
        w, h = im.size
        cw = round(h * BOX_W / BOX_H)
        left = min(max(0, round(w * 0.17)), w - cw)
        im.crop((left, 0, left + cw, h)).resize((BOX_W * 2, BOX_H * 2), Image.LANCZOS).save(out, "JPEG", quality=93)
    return out


class HydroplaningHookGenerator:
    """Six strategy-tagged candidates; each carries a real tension marker and
    keeps the hedge the facts require ("~수 있습니다"). The unchanged
    RuleBasedHookJudge picks the winner."""
    def generate(self, brief: TopicBrief) -> list[HookCandidate]:
        f = brief.fact_by_strategy()
        texts = {
            "contradiction": "빗길에선 타이어가 돌고 있어도, 실은 도로에 닿지 않을 수 있습니다.",
            "surprising_consequence": "놀랍게도 멀쩡한 타이어가 빗길에선 도로와의 접촉을 잃을 수 있습니다.",
            "counterintuitive_fact": "타이어 홈이 멀쩡해도, 실은 물을 다 빼내지 못할 수 있습니다.",
            "visible_anomaly": "이상하게도 빗길에선 타이어가 돌면서도 바닥을 밟지 못할 수 있습니다.",
            "mistaken_assumption": "생각과 달리, 돌고 있는 타이어가 도로를 밟고 있지 않을 수 있습니다.",
            "unresolved_cause_effect": "타이어 홈이 물을 계속 빼내는데도, 이상하게 접촉을 잃는 순간이 옵니다.",
        }
        return [HookCandidate(strategy=s, text=texts[s], grounded_in=f[s]) for s in texts]


def make_brief() -> TopicBrief:
    return TopicBrief(
        topic_id="hydroplaning",
        familiar_subject="젖은 도로 위를 달리는 자동차 타이어",
        contradiction_fact="타이어가 회전하고 있어도 도로에 전혀 닿지 않을 수 있습니다",
        surprising_consequence_fact="멀쩡한 타이어도 빗길에서 도로와의 접촉을 완전히 잃을 수 있습니다",
        counterintuitive_fact="타이어 홈이 있어도 물의 양이 많으면 접촉을 지키지 못할 수 있습니다",
        anomaly_fact="젖은 도로 위에서 타이어가 돌기만 하고 바닥을 밟지 못하는 경우가 있습니다",
        mistaken_assumption_fact="타이어가 돌고 있으면 도로를 밟고 있다는 생각은 항상 맞지는 않습니다",
        cause_effect_fact="타이어 홈은 접촉 영역의 물을 계속 밖으로 빼내는 역할을 합니다",
        payoff_text="물이 빠지는 속도보다 쌓이는 속도가 빨라지면 타이어는 물 위로 떠서 도로와의 접촉을 잃을 수 있습니다",
        grounded_facts=[
            "물이 타이어와 노면 사이에 쌓이면 접촉력이 감소할 수 있습니다",
            "충분히 심해지면 타이어가 노면과의 접촉을 완전히 잃을 수 있습니다",
            "타이어 트레드 홈은 접촉 영역의 물 배출에 도움을 줍니다",
            "하이드로플레이닝이 일어나면 조향과 제동이 제대로 듣지 않을 수 있습니다",
        ],
    )


def phrase(role, text, hook_type=None):
    x = {"role": role, "text": text}
    if hook_type:
        x["hook_type"] = hook_type
    return x


def beat(asset: Path, cue: str, info_role: str, concept_id: str, state_id: str, kind: str,
         qa_label: str, req: str, attribution: str | None = None):
    digest = sha(asset)
    return {
        "start": 0.0,
        "asset": str(asset),
        "attribution": attribution,
        "visual_change": {
            "kind": kind, "concept_id": concept_id, "state_id": state_id,
            "narration_cue": cue, "added_information": info_role,
            "source_sha256": digest,
        },
        "visual_qa_requirements": [req],
        "visual_qa_labels": [qa_label],
        "visual_qa_negative_labels": NEG,
        "visual_qa_expected_sha256": [digest],
        "info_role": info_role,
    }


# Cross-section windows over the single global progress g (see
# shorts_studio.hydroplaning_section). Each clip is a little longer than the
# beat it serves (measured Edge timing, see docs in the module) so the
# renderer never has to loop a clip; adjacent windows abut so the physical
# process reads as continuous across cuts.
SECTION_CLIPS = {
    "section_bow_wave": (0.22, 0.46, 2.8, None),
    "section_wedge_entering": (0.47, 0.68, 3.8, None),
    "section_contact_shrinking": (0.69, 0.83, 2.8, None),
    "section_riding_film": (0.84, 0.96, 3.8, None),
    "section_named_payoff": (0.965, 1.00, 3.6, "하이드로플레이닝"),
}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--font", default=None); args = ap.parse_args()
    assets = Path("assets/hydroplaning"); assets.mkdir(parents=True, exist_ok=True)
    src_dir = assets / "sources"; src_dir.mkdir(exist_ok=True)

    tyres_src = download_required_photo(RAIN_TYRES_PHOTO_FILE, src_dir / "michelin_rain_tyres_2005.jpg")
    rain_tyres = prepare_rain_tyres_photo(tyres_src, assets / "real_rain_tyres_grooves.jpg")

    raw = {key: download_required_video(url, src_dir / f"{key}_source.mp4", key)
           for key, (url, _page, _attr) in REAL_SOURCES.items()}
    real = {key: prepare_real_clip(raw[src], assets / f"{name}.mp4", start, crop, seconds, slowmo)
            for key, (src, name, start, crop, seconds, slowmo) in REAL_CLIPS.items()}

    # Independent clips -> render them in parallel worker processes.
    with ProcessPoolExecutor(max_workers=min(len(SECTION_CLIPS), os.cpu_count() or 1, 4)) as pool:
        futures = {
            name: pool.submit(render_section_clip, assets / f"{name}.mp4", g0, g1, duration=dur, fps=30,
                              font_path=args.font, headline=headline)
            for name, (g0, g1, dur, headline) in SECTION_CLIPS.items()
        }
        section = {name: f.result() for name, f in futures.items()}

    brief = make_brief()
    hook_result = generate_and_judge(brief, generator=HydroplaningHookGenerator())
    if hook_result.winner is None:
        raise RuntimeError("Prompt V2 produced no hydroplaning hook")
    winner = hook_result.winner
    print(f"PROMPT_V2_JUDGE={hook_result.judge_name}")
    print(f"PROMPT_V2_SELECTED_STRATEGY={winner.strategy}")
    print(f"PROMPT_V2_SELECTED_HOOK={winner.text}")

    build = Path("build"); build.mkdir(exist_ok=True)
    story_prompt = build_story_generation_prompt(
        brief, winner,
        uncertainty_notes=[
            "하이드로플레이닝이 시작되는 정확한 속도는 타이어 상태, 수막 두께, 하중 등 조건에 따라 달라질 수 있습니다",
            "이 영상은 물 쐐기와 접촉면 감소라는 핵심 메커니즘에 집중하며 유체역학의 모든 세부 요인을 다루지 않습니다",
        ],
    )
    (build / "hydroplaning_story_prompt.txt").write_text(
        story_writer_system_prompt() + "\n\n" + story_prompt + "\n", encoding="utf-8")
    print("STORY_PROMPT_V3_READY=build/hydroplaning_story_prompt.txt")

    # Timing plan (measured Edge WordBoundary timing, scene-continuous mode):
    # every beat stays within the 3.5s cadence limit and above the 1.2s
    # readability floor; the first real cut lands ~1.8s (inside the 0.2-3.0s
    # visual-proof window), CRISIS starts ~5s (3-8s window) and REVEAL starts
    # with s_reveal at ~9.3s (8-12s window).
    hook = winner.text
    attr = {k: REAL_SOURCES[v[0]][2] for k, v in REAL_CLIPS.items()}
    plans = [
        ("s_hook", [
            phrase("HOOK", hook, winner.strategy),
            phrase("CRISIS", "문제는 고무가 아니라, 타이어 밑으로 파고드는 물입니다."),
        ], [
            beat(real["spray"], "빗길에선 타이어가 돌고 있어도", "real_tires_throwing_spray", "real_spray", "flooded_road", "concept",
                 "real footage of a car driving through rain on a flooded road, its tires throwing water spray",
                 "빗길에선 실제 자동차 타이어가 물보라를 일으키며 젖은 도로를 달리는 실사 영상으로 첫 프레임부터 주제를 보여주는 장면",
                 attr["spray"]),
            beat(real["surface"], "실은 도로에 닿지 않을 수 있습니다", "real_water_film_on_road", "real_surface", "water_film", "concept",
                 "real low footage of a rain-soaked road surface with a shiny film of water on the asphalt",
                 "아스팔트 위에 얇게 깔린 실제 빗물 막을 보여줘 타이어와 도로 사이에 무엇이 끼어드는지 암시하는 장면",
                 attr["surface"]),
            beat(real["tire"], "문제는 고무가 아니라", "real_tire_rubber_closeup", "real_tire", "rubber_closeup", "concept",
                 "real close-up footage of a car tire and wheel on wet pavement in the rain",
                 "실제 젖은 노면 위 자동차 타이어 고무를 가까이 보여주는 실사 장면",
                 attr["tire"]),
            beat(real["rain_tire"], "타이어 밑으로 파고드는 물입니다", "real_water_pooling_under_tire", "real_rain_tire", "puddle", "concept",
                 "real footage of rain falling on a car tire standing in a puddle of water on the ground",
                 "빗물이 고인 바닥 위 실제 타이어에 비가 떨어지는 장면으로 타이어 밑의 물을 보여주는 장면",
                 attr["rain_tire"]),
        ]),
        ("s_reveal", [
            phrase("REVEAL", "타이어 홈은 이 물을 옆으로 빼냅니다."),
            phrase("EXPLANATION", "그런데 속도가 빨라지면, 홈이 빼내는 것보다 물이 더 빨리 밀려듭니다."),
            phrase("EXPLANATION", "타이어 앞쪽으로 물이 쐐기처럼 파고들고,"),
        ], [
            beat(rain_tyres, "타이어 홈은 이 물을 옆으로 빼냅니다", "real_tread_grooves_vs_slick", "tread_photo", "grooves", "concept",
                 "a real photograph of stacked racing rain tyres with deep tread grooves next to a smooth slick tyre",
                 "깊은 배수 홈이 있는 실제 레인 타이어와 홈 없는 슬릭 타이어를 사진으로 비교해 홈의 역할을 보여주는 장면",
                 RAIN_TYRES_PHOTO_ATTRIBUTION),
            beat(real["fast_wheel"], "그런데 속도가 빨라지면", "real_wheel_speed_rising", "real_fast_wheel", "spinning", "concept",
                 "real close-up footage of a car wheel spinning fast on a wet road while driving",
                 "빠르게 회전하며 달리는 실제 자동차 바퀴를 가까이 보여줘 속도가 빨라지는 상황을 보여주는 장면",
                 attr["fast_wheel"]),
            beat(section["section_bow_wave"], "물이 더 빨리 밀려듭니다", "water_piling_ahead", "section", "bow_wave", "concept",
                 "a side-view cross-section diagram of a rolling car tire on a wet road with water piling up in front of it and a magnified inset of its contact patch",
                 "타이어 단면도와 접촉 부위 확대 화면으로 빠지지 못한 물이 타이어 앞쪽에 밀려드는 모습을 보여주는 장면"),
            beat(section["section_wedge_entering"], "타이어 앞쪽으로 물이 쐐기처럼 파고들고", "wedge_entering_contact", "section", "wedge", "state",
                 "a cross-section diagram of a water wedge pushing under the front of a car tire's contact patch",
                 "물 쐐기가 타이어 접촉면 앞쪽 아래로 파고드는 모습을 확대 화면으로 보여주는 장면"),
        ]),
        ("s_twist", [
            phrase("EXPLANATION", "도로에 닿아 있던 면이 점점 줄어들다가,"),
            phrase("TWIST", "결국 타이어가 물막 위에 올라탑니다."),
            phrase("CRISIS", "핸들도 브레이크도 거의 듣지 않습니다."),
            phrase("PAYOFF", "이게 바로 하이드로플레이닝입니다."),
        ], [
            beat(section["section_contact_shrinking"], "도로에 닿아 있던 면이 점점 줄어들다가", "contact_patch_shrinking", "section", "shrinking", "state",
                 "a cross-section diagram of a car tire whose glowing road contact patch is shrinking as water spreads beneath it",
                 "도로에 닿아 있던 주황색 접촉면이 점점 짧아지는 모습을 확대 화면으로 보여주는 장면"),
            beat(section["section_riding_film"], "결국 타이어가 물막 위에 올라탑니다", "tire_riding_water_film", "section", "riding_film", "state",
                 "a cross-section diagram of a car tire riding on a continuous thin film of water with no road contact left",
                 "접촉면이 사라지고 타이어가 얇은 물막 위에 올라탄 상태를 보여주는 장면"),
            beat(real["pov"], "핸들도 브레이크도 거의 듣지 않습니다", "real_driver_pov_consequence", "real_pov", "rainy_drive", "concept",
                 "real driver point-of-view footage of driving on a wet rainy road",
                 "실제 빗길 운전 시점으로 조향과 제동이 듣지 않는 상황의 위험을 체감시키는 장면",
                 attr["pov"]),
            beat(section["section_named_payoff"], "이게 바로 하이드로플레이닝입니다", "named_full_hydroplane", "hydroplane_named", "full_film", "concept",
                 "a labeled cross-section diagram of a car tire fully hydroplaning on a water film, titled hydroplaning",
                 "타이어와 도로 사이가 물막으로 완전히 분리된 하이드로플레이닝 상태를 이름과 함께 보여주는 장면"),
        ]),
    ]

    production_tags = {
        ("s_hook", 0): ("hero", "real_footage"),
        ("s_hook", 1): ("support", "real_footage"),
        ("s_hook", 2): ("support", "real_footage"),
        ("s_hook", 3): ("support", "real_footage"),
        ("s_reveal", 0): ("evidence", "real_photo"),
        ("s_reveal", 1): ("support", "real_footage"),
        ("s_reveal", 2): ("mechanism", "physical_animation"),
        ("s_reveal", 3): ("support", "physical_animation"),
        ("s_twist", 0): ("support", "physical_animation"),
        ("s_twist", 1): ("second_peak", "physical_animation"),
        ("s_twist", 2): ("support", "real_footage"),
        ("s_twist", 3): ("payoff", "physical_animation"),
    }

    scenes = []
    seen_tags = set()
    for sid, narr_plan, beats in plans:
        for i, b in enumerate(beats):
            b["start"] = float(i)
            role, mode = production_tags[(sid, i)]
            b["production"] = {"role": role, "visual_mode": mode, "added_information": b["info_role"]}
            seen_tags.add((sid, i))
        narration = " ".join(p["text"] for p in narr_plan)
        scenes.append({
            "id": sid, "narration": narration,
            "narration_plan": narr_plan,
            "visual_description": "Real footage opening, real tread evidence, then a continuous hydroplaning cross-section matched to narration.",
            "asset": beats[0]["asset"],
            "attribution": beats[0].get("attribution"),
            "visual_beats": beats,
            "visual_qa_requirements": ["각 내레이션 단서에 맞는 하이드로플레이닝 장면이 실제 화면에 보여야 함"],
            "visual_qa_labels": [beats[0]["visual_qa_labels"][0]],
            "visual_qa_negative_labels": NEG,
            "overlay_title": None,
            "overlay_title_seconds": 2.8 if sid == "s_hook" else None,
        })

    expected_tags = {(sid, i) for sid, _, beats in plans for i, _ in enumerate(beats)}
    if seen_tags != expected_tags or set(production_tags) != expected_tags:
        raise RuntimeError("Visual Production V2 tag coverage drifted from the real beat list")

    manifest = {
        "title": "타이어가 도로에서 뜨는 이유",
        "width": 1080, "height": 1920, "fps": 30,
        "overlay_title": "타이어가 도로에서 뜬다",
        "overlay_title_mode": "first_scene_only",
        # Scene-continuous synthesis is the least robotic Edge mode; Edge is
        # still only the dev/fallback voice (see shorts_studio.narration for
        # the provider abstraction and the pre-rendered narration override).
        "tts_continuity_mode": "scene_continuous",
        "max_visual_recovery_attempts": 2,
        "strict_source_diversity": False,
        "strict_meaningful_visual_changes": True,
        "strict_retention_contract": True,
        "strict_visual_production_v2": True,
        "observable_phenomenon": "젖은 도로에서 타이어와 도로 사이로 물이 파고들어 타이어가 물막 위에 올라타 접촉을 잃는다.",
        "silent_story": "실제 빗길 물보라 → 노면 물막 → 젖은 타이어 → 물 고인 바닥 위 타이어 → 홈 있는 레인 타이어 vs 슬릭 → 빠르게 도는 바퀴 → 단면도: 앞쪽에 밀려드는 물 → 물 쐐기 → 접촉면 축소 → 물막 위 → 실제 운전 시점 → 이름 붙은 payoff",
        "silent_interest_review": "pending",
        "strict_entertainment_contract": False,
        "scenes": scenes,
    }
    Path("examples").mkdir(exist_ok=True)
    Path("examples/hydroplaning.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    real_lines = "\n".join(f"- {v[2]} ({v[1]})" for v in REAL_SOURCES.values())
    desc = f"""# 타이어가 도로에서 뜨는 이유 — 출처

실제 촬영 영상 (Pexels License, 잘라내기·크기 조정):
{real_lines}

레인 타이어 사진: {RAIN_TYRES_PHOTO_ATTRIBUTION} ({RAIN_TYRES_PHOTO_PAGE}),
라이선스: https://creativecommons.org/licenses/by/2.0/ — 원본에서 잘라내 사용했습니다.

타이어 단면도와 접촉 부위 확대 화면은 이 영상을 위해 직접 렌더링한 설명용 그래픽입니다. 물막 두께는
이해를 돕기 위해 과장해서 그렸습니다(실제로는 수 밀리미터 수준).

설명된 물리적 메커니즘(물이 타이어와 노면 사이에 쌓이면 접촉력이 감소할 수 있고, 충분히 심해지면
완전히 접촉을 잃을 수 있으며, 트레드 홈은 접촉 영역의 물 배출에 도움을 주고, 이때 조향과 제동이
제대로 듣지 않을 수 있다는 점)은 미국 도로교통안전국(NHTSA)의 공개된 하이드로플레이닝 안전 설명을
참고해 과장 없이 서술했습니다. 정확한 임계 속도나 공식은 조건에 따라 달라지므로 영상에서 보편적
수치로 제시하지 않았습니다.
"""
    Path("examples/hydroplaning_upload_description.txt").write_text(desc, encoding="utf-8")
    print("HYDROPLANING_MANIFEST_READY=examples/hydroplaning.json")


if __name__ == "__main__":
    main()
