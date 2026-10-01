#!/usr/bin/env python3
"""Build the golf-ball dimple science Short.

Visual contract:
- one topic-optimized shallow 3/4 camera for every generated beat;
- ball size and camera remain stable, so cuts do not feel like viewpoint jumps;
- motion comes from sphere rotation, boundary-layer particles, streamlines, and wake state;
- one causal spine only: dimples trip the boundary layer -> later separation ->
  smaller wake -> lower pressure drag.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageOps

from shorts_studio.golf3d import KINDS, OPTIMAL_GOLF_CAMERA, render_golf_motion


W, H = 980, 950
NEG = ["a photograph of a cat", "a landscape photograph of mountains", "a city skyline"]

PHOTO_FILE = "Golf ball close up.jpg"
PHOTO_PAGE = "https://commons.wikimedia.org/wiki/File:Golf_ball_close_up.jpg"
PHOTO_ATTRIBUTION = "Paolo Neo / Wikimedia Commons / Public domain"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download_public_domain_photo(out: Path) -> Path:
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
                headers={"User-Agent": "shorts-studio/0.1 (public-domain science production asset)"},
            )
            with urllib.request.urlopen(req, timeout=45) as r:
                data = r.read()
            if len(data) < 80_000:
                raise RuntimeError(f"download suspiciously small: {len(data)} bytes")
            out.write_bytes(data)
            print(f"GOLF_REAL_PHOTO_READY={out} sha256={sha(out)}")
            return out
        except Exception as exc:
            last = exc
            out.unlink(missing_ok=True)
            if attempt < 3:
                time.sleep(4 * (attempt + 1))
    raise RuntimeError(f"failed to fetch public-domain golf photo: {last}")


def prepare_photo(src: Path, out: Path) -> Path:
    im = Image.open(src).convert("RGB")
    fitted = ImageOps.fit(im, (W, H), method=Image.Resampling.LANCZOS, centering=(0.50, 0.50))
    # Slightly darken the edges so the handoff to the dark 3D visual language
    # is less abrupt without zooming or panning the source.
    canvas = Image.new("RGB", (W, H), "black")
    canvas.paste(fitted)
    canvas.save(out, quality=92)
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

    assets = Path("assets/golf_ball_dimples")
    assets.mkdir(parents=True, exist_ok=True)

    original = download_public_domain_photo(assets / "golf_ball_close_up_source.jpg")
    real_photo = prepare_photo(original, assets / "golf_ball_close_up.jpg")

    durations = {
        "hero_dimples": 3.0,
        "smooth_morph": 3.2,
        "smooth_wake": 3.0,
        "dimple_wake": 3.2,
        "boundary_layer": 3.0,
        "trip_turbulence": 3.2,
        "attached_flow": 3.2,
        "separation_compare": 3.2,
        "wake_shrink": 3.2,
        "drag_compare": 3.2,
        "flight_payoff": 3.4,
    }
    missing = set(KINDS) - set(durations)
    if missing:
        raise RuntimeError(f"missing golf motion durations: {sorted(missing)}")

    motion = {
        kind: render_golf_motion(
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
        "GOLF_CAMERA_OPTIMIZED="
        f"yaw={OPTIMAL_GOLF_CAMERA.yaw:.3f},pitch={OPTIMAL_GOLF_CAMERA.pitch:.3f},"
        f"distance={OPTIMAL_GOLF_CAMERA.distance:.2f},focal={OPTIMAL_GOLF_CAMERA.focal:.1f},"
        f"cx={OPTIMAL_GOLF_CAMERA.cx:.1f},cy={OPTIMAL_GOLF_CAMERA.cy:.1f}"
    )

    plans = [
        (
            "s_hook",
            [
                phrase(
                    "HOOK",
                    "이상하게도 골프공은 표면의 딤플을 없애 매끈하게 만들면 더 멀리 가는 게 아니라 덜 날아갑니다.",
                    "counterintuitive_fact",
                ),
                phrase("CRISIS", "표면이 거칠어졌는데 왜 공기 저항은 줄어들까요?"),
            ],
            [
                beat(
                    motion["hero_dimples"],
                    "딤플",
                    "dimpled_ball_visible",
                    "dimple_effect",
                    "hero_surface",
                    "concept",
                    "a cinematic scientific 3D visualization of a rotating dimpled golf ball with airflow and a compact wake",
                    "골프공은 표면의 딤플을 크게 보여 주고, 회전하는 공 주변의 공기 흐름과 작은 뒤쪽 wake가 함께 보이는 모습",
                ),
                beat(
                    real_photo,
                    "표면의 딤플을",
                    "real_dimple_evidence",
                    "dimple_effect",
                    "real_surface",
                    "state",
                    "a real close-up photograph of a golf ball showing many surface dimples",
                    "실제 골프공 표면의 딤플이 선명하게 보이는 근접 사진",
                    PHOTO_ATTRIBUTION,
                ),
                beat(
                    motion["smooth_morph"],
                    "매끈하게",
                    "dimples_removed",
                    "dimple_effect",
                    "smooth_transition",
                    "state",
                    "a moving 3D golf ball whose dimples disappear while its aerodynamic wake grows wider",
                    "같은 시점에서 딤플이 사라질수록 공 뒤 wake가 넓어지는 연속 변화",
                ),
            ],
        ),
        (
            "s_reveal",
            [
                phrase(
                    "INVESTIGATION",
                    "핵심은 공 바로 옆의 얇은 공기층입니다. 매끈한 공에서는 이 흐름이 뒤쪽에서 일찍 떨어져 큰 소용돌이 꼬리를 만듭니다.",
                ),
            ],
            [
                beat(
                    motion["smooth_wake"],
                    "매끈한 공",
                    "smooth_early_separation",
                    "boundary_layer",
                    "smooth_wake",
                    "concept",
                    "a moving smooth golf ball with airflow separating early and forming a wide turbulent wake",
                    "매끈한 공의 표면에서 공기 흐름이 일찍 떨어져 뒤에 넓은 wake가 생기는 모습",
                ),
                beat(
                    motion["dimple_wake"],
                    "공기층",
                    "dimple_transition_hint",
                    "boundary_layer",
                    "dimple_wake",
                    "state",
                    "a moving golf ball gaining dimples as airflow stays attached farther around the surface and the wake narrows",
                    "딤플이 생기면서 공기 흐름의 분리 지점이 뒤로 이동하고 wake가 좁아지는 모습",
                ),
            ],
        ),
        (
            "s_explain",
            [
                phrase(
                    "EXPLANATION",
                    "딤플은 그 공기층을 일부러 난류로 바꿉니다. 이 난류는 표면을 더 오래 따라가다가 뒤에서 늦게 떨어집니다.",
                ),
            ],
            [
                beat(
                    motion["boundary_layer"],
                    "공기층",
                    "boundary_layer_highlight",
                    "turbulent_layer",
                    "boundary_layer",
                    "concept",
                    "a moving dimpled golf ball with a glowing boundary layer wrapped around its surface",
                    "골프공 바로 옆의 얇은 경계층이 표면을 따라 흐르는 모습을 강조한 장면",
                ),
                beat(
                    motion["trip_turbulence"],
                    "난류로",
                    "dimple_trips_turbulence",
                    "turbulent_layer",
                    "trip_turbulence",
                    "state",
                    "a moving 3D close airflow visualization where golf-ball dimples create energetic turbulent motion near the surface",
                    "딤플 주변에서 작은 난류 움직임이 생기며 경계층의 상태가 바뀌는 모습",
                ),
                beat(
                    motion["attached_flow"],
                    "더 오래 따라가다가",
                    "later_flow_separation",
                    "turbulent_layer",
                    "attached_flow",
                    "state",
                    "a moving dimpled golf ball whose turbulent boundary layer remains attached far around the rear before separating",
                    "난류 경계층이 골프공 뒤쪽까지 더 오래 붙어 있다가 늦게 떨어지는 모습",
                ),
            ],
        ),
        (
            "s_compare",
            [
                phrase(
                    "TWIST",
                    "그래서 매끈한 공보다 공 뒤의 저압 영역이 작아지고, 압력 항력이 줄어듭니다.",
                ),
            ],
            [
                beat(
                    motion["separation_compare"],
                    "매끈한 공보다",
                    "smooth_vs_dimpled_separation",
                    "wake_drag",
                    "separation_compare",
                    "concept",
                    "a fixed-camera comparison of smooth and dimpled golf balls showing early versus delayed airflow separation",
                    "같은 시점에서 매끈한 공과 딤플 공의 공기 분리 위치를 직접 비교하는 모습",
                ),
                beat(
                    motion["wake_shrink"],
                    "저압 영역이 작아지고",
                    "wake_area_shrinks",
                    "wake_drag",
                    "wake_shrink",
                    "state",
                    "a moving dimpled golf ball with its downstream wake visibly shrinking as airflow stays attached longer",
                    "공 뒤의 넓은 wake가 더 작고 좁은 wake로 줄어드는 물리적 변화",
                ),
                beat(
                    motion["drag_compare"],
                    "압력 항력이 줄어듭니다",
                    "pressure_drag_reduced",
                    "wake_drag",
                    "drag_compare",
                    "state",
                    "a fixed-camera aerodynamic comparison showing a large rear low-pressure region behind a smooth ball and a smaller one behind a dimpled ball",
                    "매끈한 공의 큰 뒤쪽 저압 영역과 딤플 공의 작은 영역을 한 화면에서 비교하는 모습",
                ),
            ],
        ),
        (
            "s_end",
            [
                phrase(
                    "PAYOFF",
                    "골프공의 딤플은 장식이 아니라, 공기 흐름을 바꿔 비거리를 만드는 공기역학 설계입니다.",
                ),
            ],
            [
                beat(
                    motion["flight_payoff"],
                    "비거리를",
                    "final_dimpled_flight",
                    "payoff",
                    "flight_payoff",
                    "concept",
                    "a cinematic 3D dimpled golf ball flying with a compact aerodynamic wake and visible surface texture",
                    "딤플 공이 작은 wake를 유지한 채 앞으로 날아가는 최종 payoff 장면",
                ),
            ],
        ),
    ]

    production_tags = {
        ("s_hook", 0): ("hero", "physical_animation"),
        ("s_hook", 1): ("evidence", "real_photo"),
        ("s_hook", 2): ("support", "physical_animation"),
        ("s_reveal", 0): ("support", "physical_animation"),
        ("s_reveal", 1): ("mechanism", "physical_animation"),
        ("s_explain", 0): ("support", "physical_animation"),
        ("s_explain", 1): ("support", "physical_animation"),
        ("s_explain", 2): ("second_peak", "physical_animation"),
        ("s_compare", 0): ("support", "physical_animation"),
        ("s_compare", 1): ("support", "physical_animation"),
        ("s_compare", 2): ("support", "physical_animation"),
        ("s_end", 0): ("payoff", "physical_animation"),
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
                "visual_description": "골프공 딤플과 경계층·wake를 같은 최적 카메라로 이어 보여주는 물리 시각화.",
                "asset": beats[0]["asset"],
                "attribution": beats[0].get("attribution"),
                "visual_beats": beats,
                "visual_qa_requirements": [
                    "각 내레이션 단서에 맞는 골프공 딤플, 경계층, 흐름 분리 또는 wake 변화가 실제 화면에 보여야 함"
                ],
                "visual_qa_labels": [beats[0]["visual_qa_labels"][0]],
                "visual_qa_negative_labels": NEG,
                "overlay_title": None,
                "overlay_title_seconds": 2.8 if sid == "s_hook" else None,
            }
        )

    expected = {(sid, i) for sid, _, beats in plans for i, _ in enumerate(beats)}
    if seen != expected or set(production_tags) != expected:
        raise RuntimeError("golf production tag coverage drifted from beat list")

    manifest = {
        "title": "골프공은 왜 일부러 울퉁불퉁할까?",
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "overlay_title": "매끈하면 덜 날아간다",
        "overlay_title_mode": "first_scene_only",
        "max_visual_recovery_attempts": 2,
        "strict_source_diversity": False,
        "strict_meaningful_visual_changes": True,
        "strict_retention_contract": True,
        "strict_visual_production_v2": True,
        "observable_phenomenon": "딤플이 있는 골프공은 같은 조건의 매끈한 공보다 공기 흐름이 더 늦게 분리되어 wake가 작아질 수 있다.",
        "silent_story": "딤플이 보이는 골프공 → 실제 표면 증거 → 딤플 제거 시 wake 확대 → 경계층 단서 → 난류 전환 → 늦은 분리 → smooth/dimple 비교 → 작은 wake와 낮은 압력 항력 → 비거리 payoff",
        "silent_interest_review": "pending",
        "strict_entertainment_contract": False,
        "scenes": scenes,
    }

    Path("examples").mkdir(exist_ok=True)
    Path("examples/golf_ball_dimples.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    description = f"""# 골프공은 왜 일부러 울퉁불퉁할까? — 출처

실제 골프공 사진:
- Golf ball close up.jpg
- Author: Paolo Neo
- Source: {PHOTO_PAGE}
- License: Public domain
- 사용 변경: 세로형 설명 화면에 맞춰 중앙 크롭/리사이즈

핵심 과학 참고:
- NASA Glenn Research Center — Drag of a Sphere
- NASA Ames Research Center — golf-ball dimples and boundary-layer separation
- USGA Science of Golf — Aerodynamics

설명 애니메이션:
- 골프공, 딤플, 경계층, 공기 흐름, wake 장면은 shorts-studio에서 직접 생성한 물리 시각화입니다.
- 이 영상은 딤플이 경계층 전이를 앞당겨 흐름 분리를 늦추고 wake/압력 항력을 줄이는 메커니즘에 집중합니다.
"""
    Path("examples/golf_ball_dimples_upload_description.txt").write_text(description, encoding="utf-8")
    print("GOLF_MANIFEST_READY=examples/golf_ball_dimples.json")


if __name__ == "__main__":
    main()
