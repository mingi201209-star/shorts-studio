#!/usr/bin/env python3
"""Build the hydroplaning 3D Short.

Visual contract:
- one fixed tire-follow camera for all synthetic beats;
- road scroll + tire rotation + water flow provide continuous motion;
- the story is physical and causal: water wedge -> shrinking contact patch ->
  tire lift -> steering/braking force loss -> contact recovery;
- no camera orbit, crop churn, or viewpoint jump is used to fake cadence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps

from shorts_studio.hydro3d import (
    KINDS,
    OPTIMAL_HYDRO_CAMERA,
    render_hydro_motion,
)


W, H = 980, 950
NEG = [
    "a dry road with no water",
    "a golf ball",
    "a city skyline",
]

PHOTO_FILE = "Wet road.jpg"
PHOTO_PAGE = "https://commons.wikimedia.org/wiki/File:Wet_road.jpg"
PHOTO_ATTRIBUTION = "Pixel.la / Wikimedia Commons / CC0 1.0"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download_wet_road_photo(out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.is_file() and out.stat().st_size > 50_000:
        return out

    encoded = urllib.parse.quote(PHOTO_FILE.replace(" ", "_"), safe="._-()")
    url = f"https://commons.wikimedia.org/wiki/Special:Redirect/file/{encoded}"
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "shorts-studio/0.1 (CC0 wet-road production asset)"},
            )
            with urllib.request.urlopen(req, timeout=45) as r:
                data = r.read()
            if len(data) < 80_000:
                raise RuntimeError(f"download suspiciously small: {len(data)} bytes")
            out.write_bytes(data)
            print(f"HYDRO_REAL_PHOTO_READY={out} sha256={sha(out)}")
            return out
        except Exception as exc:
            last = exc
            out.unlink(missing_ok=True)
            if attempt < 3:
                time.sleep(4 * (attempt + 1))

    raise RuntimeError(f"failed to fetch CC0 wet-road photo: {last}")


def prepare_photo(src: Path, out: Path) -> Path:
    im = Image.open(src).convert("RGB")
    fitted = ImageOps.fit(
        im,
        (W, H),
        method=Image.Resampling.LANCZOS,
        centering=(0.50, 0.52),
    )
    # Keep the real-photo evidence compatible with the dark synthetic visual
    # language without panning/zooming it.
    fitted = ImageEnhance.Brightness(fitted).enhance(0.72)
    fitted = ImageEnhance.Contrast(fitted).enhance(1.10)
    fitted.save(out, quality=92)
    return out


def phrase(role: str, text: str, hook_type: str | None = None) -> dict:
    item = {"role": role, "text": text}
    if hook_type:
        item["hook_type"] = hook_type
    return item


def beat(
    asset: Path,
    cue: str,
    info_role: str,
    concept_id: str,
    state_id: str,
    kind: str,
    qa_label: str,
    requirement: str,
    attribution: str | None = None,
) -> dict:
    digest = sha(asset)
    return {
        "start": 0.0,
        "asset": str(asset),
        "attribution": attribution,
        "visual_change": {
            "kind": kind,
            "concept_id": concept_id,
            "state_id": state_id,
            "narration_cue": cue,
            "added_information": info_role,
            "source_sha256": digest,
        },
        "visual_qa_requirements": [requirement],
        "visual_qa_labels": [qa_label],
        "visual_qa_negative_labels": NEG,
        "visual_qa_expected_sha256": [digest],
        "info_role": info_role,
    }


def main() -> None:
    argparse.ArgumentParser().parse_args()

    assets = Path("assets/hydroplaning")
    assets.mkdir(parents=True, exist_ok=True)

    original = download_wet_road_photo(assets / "wet_road_source.jpg")
    real_photo = prepare_photo(original, assets / "wet_road.jpg")

    durations = {
        "hero_contact": 4.2,
        "water_wedge": 4.6,
        "contact_shrink": 4.6,
        "full_hydroplane": 4.6,
        "drainage_channels": 4.6,
        "speed_ramp": 4.8,
        "pressure_lift": 4.6,
        "wedge_closeup": 4.6,
        "steering_loss": 4.6,
        "braking_loss": 4.6,
        "recover_contact": 4.8,
        "final_cutaway": 4.8,
        "final_drive": 4.8,
    }
    missing = set(KINDS) - set(durations)
    extra = set(durations) - set(KINDS)
    if missing or extra:
        raise RuntimeError(f"hydro duration coverage mismatch: missing={sorted(missing)} extra={sorted(extra)}")

    motion = {
        kind: render_hydro_motion(
            kind,
            assets / f"{kind}_3d_motion.mp4",
            duration=durations[kind],
            fps=30,
            width=W,
            height=H,
        )
        for kind in KINDS
    }

    print(
        "HYDRO_CAMERA_OPTIMIZED="
        f"yaw={OPTIMAL_HYDRO_CAMERA.yaw:.3f},pitch={OPTIMAL_HYDRO_CAMERA.pitch:.3f},"
        f"distance={OPTIMAL_HYDRO_CAMERA.distance:.2f},focal={OPTIMAL_HYDRO_CAMERA.focal:.1f},"
        f"cx={OPTIMAL_HYDRO_CAMERA.cx:.1f},cy={OPTIMAL_HYDRO_CAMERA.cy:.1f}"
    )

    plans = [
        (
            "s_hook",
            [
                phrase(
                    "HOOK",
                    "이상하게도 빗길에서 타이어는 도로 대신 물 위에 뜰 수 있습니다.",
                    "counterintuitive_fact",
                ),
                phrase(
                    "CRISIS",
                    "무거운 차가 어떻게 물에 뜰까요?",
                ),
                phrase(
                    "REVEAL",
                    "앞에서 못 빠진 물이 타이어 밑에 쐐기를 만듭니다.",
                ),
            ],
            [
                beat(
                    motion["hero_contact"],
                    "이상하게도",
                    "wet_tire_contact_visible",
                    "hydro_contact",
                    "normal_wet_contact",
                    "concept",
                    "a cinematic scientific 3D tire rolling on a wet road with visible tread, road contact patch, moving water and spray",
                    "빗길에서 타이어는 젖은 도로에 실제로 닿아 있고, 회전하는 타이어·접촉면·흐르는 물이 한 화면에 보이는 장면",
                ),
                beat(
                    real_photo,
                    "빗길에서",
                    "real_wet_road_evidence",
                    "hydro_contact",
                    "real_wet_road",
                    "state",
                    "a real photograph of a wet asphalt road covered by a visible water film",
                    "실제 젖은 아스팔트 도로와 표면의 물기가 보이는 사진",
                    PHOTO_ATTRIBUTION,
                ),
                beat(
                    motion["full_hydroplane"],
                    "물 위에",
                    "hydroplane_result_tease",
                    "hydro_contact",
                    "tire_riding_on_water",
                    "state",
                    "a fixed-camera 3D tire visibly lifted above the road by a moving water wedge with almost no road contact",
                    "같은 시점에서 타이어 아래 물층이 두꺼워지고 접촉선이 거의 사라져 타이어가 물 위에 뜬 모습",
                ),
                beat(
                    motion["contact_shrink"],
                    "어떻게",
                    "contact_patch_shrinks",
                    "hydro_contact",
                    "contact_loss",
                    "state",
                    "a moving 3D tire whose road contact patch rapidly shrinks as water pressure lifts its leading edge",
                    "물 압력이 커지면서 타이어 접촉면이 앞쪽부터 짧아지고 타이어가 살짝 떠오르는 연속 변화",
                ),
                beat(
                    motion["water_wedge"],
                    "쐐기를",
                    "water_wedge_forms",
                    "water_wedge",
                    "wedge_formation",
                    "concept",
                    "a coherent wedge of water building in front of a rolling tire while pressure bands move beneath it",
                    "타이어 앞쪽에 물이 쐐기 모양으로 쌓이고 그 안의 압력 흐름이 계속 움직이는 장면",
                ),
            ],
        ),
        (
            "s_reveal",
            [
                phrase(
                    "INVESTIGATION",
                    "속도가 올라갈수록 타이어 아래로 밀려드는 물을 밖으로 보낼 시간이 줄고, 실제 접촉면은 앞쪽부터 빠르게 작아집니다.",
                ),
            ],
            [
                beat(
                    motion["speed_ramp"],
                    "속도가",
                    "speed_increases_water_loading",
                    "water_management",
                    "speed_ramp",
                    "concept",
                    "a fixed-camera tire accelerating over water as road streak speed, water wedge height, and tire lift increase together",
                    "카메라는 고정된 채 도로 흐름이 빨라지고 물 쐐기·타이어 들림이 함께 커지는 속도 증가 장면",
                ),
                beat(
                    motion["drainage_channels"],
                    "밖으로",
                    "tread_channels_water_out",
                    "water_management",
                    "tread_drainage",
                    "state",
                    "moving water packets being routed through tire tread drainage paths while the tire keeps rolling",
                    "타이어 홈을 따라 물 입자들이 옆과 뒤로 빠져나가며 배수 역할이 물리적으로 보이는 장면",
                ),
                beat(
                    motion["pressure_lift"],
                    "접촉면은",
                    "water_pressure_lifts_tire",
                    "water_management",
                    "pressure_lift",
                    "state",
                    "upward water-pressure arrows beneath a rolling tire as the contact patch collapses and the tire rises",
                    "타이어 아래 물 압력 화살표가 커지고 접촉선이 거의 사라지며 타이어가 위로 들리는 장면",
                ),
            ],
        ),
        (
            "s_explain",
            [
                phrase(
                    "EXPLANATION",
                    "타이어 홈은 물이 옆으로 빠질 길을 만들지만, 수막이 생겨 접촉이 거의 사라지면 핸들을 돌려도 도로에 옆힘을 전달하기 어려워집니다.",
                ),
            ],
            [
                beat(
                    motion["wedge_closeup"],
                    "수막이",
                    "water_film_supports_tire",
                    "traction_loss",
                    "water_supported_tire",
                    "concept",
                    "a rolling tire supported by a coherent high-pressure water wedge with strong spray and almost no road contact",
                    "큰 물 쐐기와 움직이는 압력띠가 타이어를 받치고 실제 도로 접촉은 거의 남지 않은 장면",
                ),
                beat(
                    motion["steering_loss"],
                    "핸들을",
                    "steering_force_collapses",
                    "traction_loss",
                    "steering_loss",
                    "state",
                    "a steering direction cue beside a hydroplaning tire while lateral road-force arrows nearly vanish with the contact patch",
                    "핸들을 돌리는 방향 표시는 남아 있지만 접촉면과 옆힘 화살표는 거의 사라져 조향력 손실이 보이는 장면",
                ),
            ],
        ),
        (
            "s_twist",
            [
                phrase(
                    "TWIST",
                    "브레이크도 같습니다. 접촉면이 사라지면 제동력을 전달할 곳이 줄고, 속도가 내려가 물을 밀어낼 수 있게 되면 접촉이 다시 돌아옵니다.",
                ),
            ],
            [
                beat(
                    motion["braking_loss"],
                    "브레이크도",
                    "braking_force_collapses",
                    "traction_loss",
                    "braking_loss",
                    "state",
                    "a hydroplaning tire with almost no contact patch and a visibly weak longitudinal braking-force arrow",
                    "수막 위에 뜬 타이어 아래 접촉선이 거의 없고 제동력 화살표도 작아진 모습",
                ),
                beat(
                    motion["recover_contact"],
                    "다시 돌아옵니다",
                    "contact_patch_recovers",
                    "traction_recovery",
                    "contact_recovery",
                    "concept",
                    "a rolling tire slowing as the water wedge collapses, tire lift decreases, and the road contact patch grows back",
                    "속도가 낮아지며 물 쐐기가 작아지고 타이어가 내려오면서 접촉선이 다시 길어지는 연속 변화",
                ),
            ],
        ),
        (
            "s_end",
            [
                phrase(
                    "PAYOFF",
                    "그래서 수막현상은 단순히 길이 미끄러운 게 아니라, 타이어와 도로 사이에 물층이 끼어 접촉 자체가 사라지는 순간입니다.",
                ),
            ],
            [
                beat(
                    motion["final_drive"],
                    "단순히",
                    "stable_wet_contact_reference",
                    "payoff",
                    "wet_contact_reference",
                    "concept",
                    "a rolling tire maintaining a clear contact patch on a wet road while water drains through the tread",
                    "젖은 도로에서도 타이어 홈으로 물이 빠지고 접촉선이 유지되는 기준 상태",
                ),
                beat(
                    motion["final_cutaway"],
                    "사라지는 순간입니다",
                    "hydroplane_definition_payoff",
                    "payoff",
                    "contact_disappears",
                    "state",
                    "a final fixed-camera cutaway showing water pressure rising between tire and road as the contact patch visibly approaches zero",
                    "타이어와 도로 사이 물층이 커지며 접촉선이 거의 0으로 줄어드는 최종 3D 단면 payoff",
                ),
            ],
        ),
    ]

    production_tags = {
        ("s_hook", 0): ("hero", "physical_animation"),
        ("s_hook", 1): ("evidence", "real_photo"),
        ("s_hook", 2): ("support", "physical_animation"),
        ("s_hook", 3): ("support", "physical_animation"),
        ("s_hook", 4): ("mechanism", "physical_animation"),
        ("s_reveal", 0): ("support", "physical_animation"),
        ("s_reveal", 1): ("support", "physical_animation"),
        ("s_reveal", 2): ("second_peak", "physical_animation"),
        ("s_explain", 0): ("support", "physical_animation"),
        ("s_explain", 1): ("support", "physical_animation"),
        ("s_twist", 0): ("support", "physical_animation"),
        ("s_twist", 1): ("support", "physical_animation"),
        ("s_end", 0): ("support", "physical_animation"),
        ("s_end", 1): ("payoff", "physical_animation"),
    }

    scenes = []
    seen = set()
    for sid, narration_plan, beats in plans:
        for i, item in enumerate(beats):
            item["start"] = float(i)
            role, mode = production_tags[(sid, i)]
            item["production"] = {
                "role": role,
                "visual_mode": mode,
                "added_information": item["info_role"],
            }
            seen.add((sid, i))

        narration = " ".join(p["text"] for p in narration_plan)
        scenes.append(
            {
                "id": sid,
                "narration": narration,
                "narration_plan": narration_plan,
                "visual_description": "고정된 3D 타이어 시점에서 도로·물·접촉면·수막 변화가 연속적으로 이어지는 물리 시각화.",
                "asset": beats[0]["asset"],
                "attribution": beats[0].get("attribution"),
                "visual_beats": beats,
                "visual_qa_requirements": [
                    "각 내레이션 단서에 맞춰 타이어 회전, 도로 접촉면, 물 쐐기, 배수 또는 힘 손실 변화가 실제 화면에 보여야 함"
                ],
                "visual_qa_labels": [beats[0]["visual_qa_labels"][0]],
                "visual_qa_negative_labels": NEG,
                "overlay_title": None,
                "overlay_title_seconds": 2.8 if sid == "s_hook" else None,
            }
        )

    expected = {(sid, i) for sid, _, beats in plans for i, _ in enumerate(beats)}
    if seen != expected or set(production_tags) != expected:
        raise RuntimeError("hydro production tag coverage drifted from beat list")

    manifest = {
        "title": "빗길에서 타이어가 도로에서 떠버리는 순간",
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "overlay_title": "타이어가 물 위에 뜬다",
        "overlay_title_mode": "first_scene_only",
        "max_visual_recovery_attempts": 2,
        "strict_source_diversity": False,
        "strict_meaningful_visual_changes": True,
        "strict_retention_contract": True,
        "strict_visual_production_v2": True,
        "observable_phenomenon": "젖은 도로에서 속도와 물의 양이 커지면 타이어 앞의 물을 충분히 밀어내지 못해 물 쐐기가 커지고, 타이어-도로 접촉면이 줄어들어 수막현상이 생길 수 있다.",
        "silent_story": "젖은 도로 접촉 → 실제 빗길 → 수막 결과 선공개 → 접촉면 축소 → 물 쐐기 → 속도 증가 → 트레드 배수 → 물 압력 들림 → 조향/제동력 손실 → 속도 감소와 접촉 회복 → 수막 정의 payoff",
        "silent_interest_review": "pending",
        "strict_entertainment_contract": False,
        "scenes": scenes,
    }

    Path("examples").mkdir(exist_ok=True)
    Path("examples/hydroplaning.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    description = f"""# 빗길에서 타이어가 떠버리는 순간 — 출처

실제 젖은 도로 사진:
- Wet road.jpg
- Source: {PHOTO_PAGE}
- License: CC0 1.0 / public-domain dedication
- 사용 변경: 세로 설명 화면에 맞춰 중앙 크롭, 밝기·대비 조정

핵심 물리 참고:
- FAA Airplane Flying Handbook, Chapter 9 — Dynamic Hydroplaning
  https://www.faa.gov/sites/faa.gov/files/regulations_policies/handbooks_manuals/aviation/airplane_handbook/10_afh_ch9.pdf
- NHTSA — Tire Wet Contact Phenomena / Hydroplaning
  https://www.nhtsa.gov/sites/nhtsa.gov/files/nadssae_pres2006010559.pdf

설명 애니메이션:
- 타이어, 젖은 도로, 물 쐐기, 트레드 배수, 접촉면, 수막 장면은 shorts-studio에서 직접 생성한 물리 시각화입니다.
- 실제 수막현상은 속도, 물의 깊이, 타이어 설계·트레드 깊이, 하중, 공기압, 노면 상태 등 여러 조건의 영향을 받습니다.
"""
    Path("examples/hydroplaning_upload_description.txt").write_text(description, encoding="utf-8")
    print("HYDRO_MANIFEST_READY=examples/hydroplaning.json")


if __name__ == "__main__":
    main()
