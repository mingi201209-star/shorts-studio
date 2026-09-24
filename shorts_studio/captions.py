"""Build an uploadable SRT from the per-scene subtitle tracks."""
from __future__ import annotations

import re
from pathlib import Path

_TIME_RE = re.compile(r"^(\d{2,}):(\d{2}):(\d{2}),(\d{3})$")


def _parse_time(value: str) -> float:
    match = _TIME_RE.fullmatch(value.strip())
    if not match:
        raise ValueError(f"invalid SRT timestamp: {value!r}")
    hours, minutes, seconds, millis = (int(part) for part in match.groups())
    if minutes >= 60 or seconds >= 60:
        raise ValueError(f"invalid SRT timestamp: {value!r}")
    return hours * 3600 + minutes * 60 + seconds + millis / 1000


def _format_time(value: float) -> str:
    total_ms = round(value * 1000)
    hours, total_ms = divmod(total_ms, 3_600_000)
    minutes, total_ms = divmod(total_ms, 60_000)
    seconds, millis = divmod(total_ms, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"


def merge_scene_srt_files(
    scene_windows: list[dict],
    build_dir: Path,
    final_duration: float,
    output_path: Path,
) -> dict:
    """Offset scene-local cues to the final concatenated timeline.

    The renderer concatenates encoded scene clips, so the final MP4 duration can
    differ slightly from the sum of planned windows. Apply the same uniform
    scale used by final-video QA when mapping sample timestamps.
    """
    planned_total = sum(float(window["duration"]) for window in scene_windows)
    if not scene_windows or planned_total <= 0 or final_duration <= 0:
        raise ValueError("positive scene windows and final duration are required")
    scale = final_duration / planned_total
    cues = []
    previous_start = -1.0
    previous_window_end = 0.0

    for window in scene_windows:
        scene_start = float(window["start"])
        scene_duration = float(window["duration"])
        if scene_start < previous_window_end - 0.01 or scene_duration <= 0:
            raise ValueError(f"invalid or overlapping scene window: {window}")
        previous_window_end = scene_start + scene_duration
        source = build_dir / f"{window['scene']}.srt"
        if not source.is_file():
            raise FileNotFoundError(f"missing scene subtitle file: {source}")

        blocks = [block for block in source.read_text(encoding="utf-8").strip().split("\n\n") if block.strip()]
        for block in blocks:
            lines = block.splitlines()
            if len(lines) < 3 or not lines[0].strip().isdigit():
                raise ValueError(f"malformed SRT block in {source}: {block!r}")
            parts = lines[1].split(" --> ")
            if len(parts) != 2:
                raise ValueError(f"malformed SRT timing in {source}: {lines[1]!r}")
            local_start, local_end = map(_parse_time, parts)
            if local_end <= local_start or local_end > scene_duration + 0.02:
                raise ValueError(f"cue outside scene duration in {source}: {lines[1]!r}")
            start = max(0.0, (scene_start + local_start) * scale)
            end = min(final_duration, (scene_start + local_end) * scale)
            if start < previous_start - 0.001 or end <= start:
                raise ValueError(f"non-monotonic or empty final caption cue: {lines[1]!r}")
            previous_start = start
            text = "\n".join(lines[2:]).strip()
            if not text:
                raise ValueError(f"empty SRT cue in {source}")
            cues.append((start, end, text))

    if not cues:
        raise ValueError("no caption cues found")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    blocks = [
        f"{index}\n{_format_time(start)} --> {_format_time(end)}\n{text}"
        for index, (start, end, text) in enumerate(cues, 1)
    ]
    output_path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    return {"status": "PASS", "cues": len(cues), "time_scale": scale, "path": str(output_path)}
