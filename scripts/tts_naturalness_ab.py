#!/usr/bin/env python3
"""Audio-only TTS naturalness A/B/C/D experiment for the verified
hydroplaning narration.

This intentionally does NOT change production defaults.  It isolates the two
most plausible sources of the reported "robotic" sound:
  1. synthesis-unit resets (many short Edge calls stitched together), and
  2. voice choice (multilingual vs native Korean male voices).

All alternatives keep the exact same narration wording.  The only evaluation
question is which delivery sounds most like one human continuously narrating.
"""
from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from pathlib import Path

import edge_tts

from shorts_studio.prosody import plan_narration
from shorts_studio.tts import synthesize_plan

OUT = Path("tts_naturalness_ab")
WORK = OUT / "_work"

SCENES = [
    [
        ("HOOK", "실은 도로에 닿지 않습니다.", False),
        ("CRISIS", "방금 전엔 멀쩡했어요.", False),
    ],
    [
        ("INVESTIGATION", "실제 트레드입니다.", False),
        ("INVESTIGATION", "물이 쌓입니다.", False),
        ("REVEAL", "쐐기처럼 커집니다.", False),
        ("EXPLANATION", "접촉이 줄어듭니다.", False),
    ],
    [
        ("TWIST", "반도 안 남았습니다.", False),
        ("TWIST", "거의 다 떠올랐습니다.", False),
        ("PAYOFF", "하이드로플레이닝입니다.", False),
    ],
]

VARIANTS = {
    "A_current_unitized": {
        "mode": "unitized",
        "voice": "ko-KR-HyunsuMultilingualNeural",
        "rate": "role-aware",
        "description": "현재 엔진: 짧은 합성 단위 + 역할별 속도",
    },
    "B_hyunsu_multi_continuous": {
        "mode": "scene_continuous",
        "voice": "ko-KR-HyunsuMultilingualNeural",
        "rate": "+6%",
        "description": "현재 목소리 유지 + 장면당 한 번만 합성",
    },
    "C_hyunsu_native_continuous": {
        "mode": "scene_continuous",
        "voice": "ko-KR-HyunsuNeural",
        "rate": "+6%",
        "description": "한국어 전용 Hyunsu + 장면당 한 번만 합성",
    },
    "D_injoon_continuous": {
        "mode": "scene_continuous",
        "voice": "ko-KR-InJoonNeural",
        "rate": "+6%",
        "description": "한국어 전용 InJoon + 장면당 한 번만 합성",
    },
}


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def silence(path: Path, seconds: float = 0.08) -> Path:
    run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
        "-t", str(seconds), "-c:a", "libmp3lame", "-q:a", "4", str(path),
    ])
    return path


def concat(parts: list[Path], out: Path) -> Path:
    playlist = out.with_suffix(".concat.txt")
    playlist.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in parts),
        encoding="utf-8",
    )
    run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(playlist),
        "-c:a", "libmp3lame", "-q:a", "2", str(out),
    ])
    return out


async def synthesize_continuous_scene(text: str, voice: str, rate: str, out: Path) -> None:
    audio = bytearray()
    communicate = edge_tts.Communicate(
        text,
        voice,
        rate=rate,
        pitch="+0Hz",
        volume="+0%",
        boundary="WordBoundary",
    )
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio.extend(chunk["data"])
    if not audio:
        raise RuntimeError(f"no audio returned for voice={voice!r} text={text!r}")
    out.write_bytes(audio)


async def render_variant(name: str, cfg: dict) -> Path:
    variant_dir = WORK / name
    variant_dir.mkdir(parents=True, exist_ok=True)
    scene_files: list[Path] = []

    for i, scene in enumerate(SCENES):
        out = variant_dir / f"scene_{i}.mp3"
        if cfg["mode"] == "unitized":
            plan = plan_narration(scene)
            await synthesize_plan(
                plan,
                out,
                variant_dir / f"scene_{i}.timing.json",
                voice=cfg["voice"],
                use_role_rates=True,
                enable_subtle_breaths=False,
            )
        else:
            text = " ".join(seg[1] for seg in scene)
            await synthesize_continuous_scene(text, cfg["voice"], cfg["rate"], out)
        scene_files.append(out)

    joined_parts: list[Path] = []
    for i, scene_file in enumerate(scene_files):
        if i:
            joined_parts.append(silence(variant_dir / f"gap_{i}.mp3"))
        joined_parts.append(scene_file)

    raw = OUT / f"{name}_raw.mp3"
    concat(joined_parts, raw)

    # Listening comparison only: equalize integrated loudness so "louder"
    # cannot masquerade as "more natural". Production audio is untouched.
    normalized = OUT / f"{name}.mp3"
    run([
        "ffmpeg", "-y", "-i", str(raw),
        "-af", "loudnorm=I=-18:TP=-2:LRA=7",
        "-c:a", "libmp3lame", "-q:a", "2", str(normalized),
    ])
    return normalized


def probe(path: Path) -> dict:
    duration = json.loads(subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "json", str(path),
        ],
        check=True, capture_output=True, text=True,
    ).stdout)["format"]["duration"]
    volume = subprocess.run(
        ["ffmpeg", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True,
    ).stderr
    return {"duration_seconds": round(float(duration), 3), "volumedetect_tail": volume[-1200:]}


async def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    WORK.mkdir(parents=True)

    results = {}
    for name, cfg in VARIANTS.items():
        print(f"=== rendering {name}: {cfg['description']} ===", flush=True)
        audio = await render_variant(name, cfg)
        results[name] = {**cfg, **probe(audio), "file": str(audio)}
        print(json.dumps(results[name], ensure_ascii=False, indent=2), flush=True)

    (OUT / "mapping.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (OUT / "README.txt").write_text(
        "로봇 느낌 비교용. 같은 대본, 음량 정규화(-18 LUFS).\n"
        "A: 현재 짧은 단위 합성\n"
        "B: 현재 목소리, 장면당 1회 연속 합성\n"
        "C: 한국어 전용 Hyunsu, 장면당 1회 연속 합성\n"
        "D: 한국어 전용 InJoon, 장면당 1회 연속 합성\n"
        "숨소리는 이번 실험에서 모두 끔: 먼저 TTS 본체의 자연스러움만 비교하기 위함.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    asyncio.run(main())
