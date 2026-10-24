"""Hard-gated 30s English shoulder-rumble episode timeline.

Pure Python: can run without Blender and cannot publish or relax visual QA.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

APPROVED_SERIES = "hidden-engineering-american-roads"
APPROVED_EPISODE = "rumble-strip-alerts"
PINNED_ASSET = "a82e05825f907cc99678ab12855527552e34323b31ae801625af4a0f563ed877"
SHOT_IDS = (
    "hook_warning", "road_cut", "tire_contact", "rumble_mechanism",
    "shoulder_location", "driver_response",
)
VIEWS = {"hero", "contact", "roadside", "payoff"}

# Real road/soil must cover the whole fixed 9:16 camera frustum.
ROAD_X_HALF_SPAN = 13.0
ROAD_Y_NEAR_EDGE = -8.0
DIRT_Y_FAR_EDGE = 14.0


# Original CLIP semantic gate inputs (shorts_studio.visual_qa thresholds unchanged).
# Negatives are wrong-domain content; positives describe what each beat shows.
SEMANTIC_NEGATIVE_LABELS = (
    "a kitchen interior", "a portrait of a person's face", "a page of printed text",
    "a forest landscape with trees", "an animated cartoon character", "food on a plate",
)
_SEMANTIC_POSITIVE_LABELS = {
    "hook_warning": ("a car tire on an asphalt road",
                     "a blue car wheel beside grooves in the road"),
    "road_cut": ("grooves cut into an asphalt road shoulder", "a blue car on an asphalt road"),
    "tire_contact": ("a car tire rolling over grooves in the road",
                     "a blue car driving on asphalt"),
    "rumble_mechanism": ("a car wheel on a grooved road surface", "a blue car on a road"),
    "shoulder_location": ("a blue car beside the edge line of a road",
                          "a car on a road near the shoulder"),
    "driver_response": ("a blue car steering back into its lane", "a car on an asphalt road"),
}


def semantic_labels(shot_id: str) -> tuple[str, ...]:
    if shot_id not in SHOT_IDS:
        raise ValueError("unknown semantic shot")
    return _SEMANTIC_POSITIVE_LABELS[shot_id]


# Shared 16 mm physical milling profile. Blender renders this same contour
# as both the true surface and the optional explanatory section face.
GROOVE_PITCH_M = 0.34
GROOVE_FLOOR_HALF_WIDTH_M = 0.085
GROOVE_RAMP_HALF_WIDTH_M = 0.115


def groove_height(x: float, depth: float = 0.016) -> float:
    """Real road surface z in metres, never a painted/implied groove."""
    if not math.isfinite(x) or not math.isfinite(depth) or depth <= 0:
        raise ValueError("invalid physical milling coordinate or depth")
    nearest = round(x / GROOVE_PITCH_M) * GROOVE_PITCH_M
    distance = abs(x - nearest)
    if distance < GROOVE_FLOOR_HALF_WIDTH_M:
        return -depth
    if distance < GROOVE_RAMP_HALF_WIDTH_M:
        ramp = GROOVE_RAMP_HALF_WIDTH_M - GROOVE_FLOOR_HALF_WIDTH_M
        return -depth * (GROOVE_RAMP_HALF_WIDTH_M - distance) / ramp
    return 0.0


def road_section_profile(
    x_extent: float = ROAD_X_HALF_SPAN,
    depth: float = 0.016,
    substrate_floor: float = -0.08,
) -> list[tuple[float, float, float]]:
    """Actual milled top and solid cut-face bottom at each original road vertex."""
    if not math.isfinite(x_extent) or x_extent <= 0 or not math.isfinite(substrate_floor):
        raise ValueError("invalid road section dimensions")
    if not math.isfinite(depth) or depth <= 0 or substrate_floor >= -depth:
        raise ValueError("section must extend below actual groove floor")
    cuts = {-x_extent, x_extent}
    count = math.ceil(x_extent / GROOVE_PITCH_M) + 1
    for index in range(-count, count + 1):
        center = index * GROOVE_PITCH_M
        for offset in (-.116, -.115, -.086, -.085, -.04, 0,
                       .04, .085, .086, .115, .116):
            x = center + offset
            if -x_extent <= x <= x_extent:
                cuts.add(x)
    return [
        (x, groove_height(x, depth), substrate_floor)
        for x in sorted(cuts)
    ]


def detail_stage(shot_id: str) -> str:
    """Named native 3D mechanism treatment for each existing five-second beat.

    This is an editorial/renderer contract, not a claim that all six native
    detail shots have already been built or visually approved.
    """
    stages = {
        "hook_warning": "macro_warning",
        "road_cut": "road_section",
        "tire_contact": "rolling_contact",
        "rumble_mechanism": "wheel_body_vibration",
        "shoulder_location": "shoulder_context",
        "driver_response": "human_response",
    }
    try:
        return stages[shot_id]
    except KeyError:
        raise ValueError("unknown detail shot") from None


def detail_visibility(shot_id: str) -> dict[str, bool]:
    """Truthful per-beat visibility of the *original* meshes, never substitutes.

    Isolate the audited CC0 front wheel and excavate the true 16 mm road edge
    only during explanatory inserts. Other beats retain the original sedan.
    """
    stage = detail_stage(shot_id)
    is_section = stage == "road_section"
    is_closeup = stage in ("road_section", "rolling_contact")
    return {
        "body_visible": not is_closeup,
        "near_shoulder_visible": not is_section,
        "exposed_bank_visible": is_section,
        "section_face_visible": is_section,
    }


def camera_layout(shot: dict) -> dict:
    """Fixed camera per 5s beat; wheel shots keep the tyre in frame throughout.

    Orthographic framing depends only on offset direction and scale. Offsets
    are long enough that the camera plane stays above the road (no black void).
    """
    ident = shot["id"]
    if ident not in SHOT_IDS:
        raise ValueError("unknown camera shot")
    middle = (shot["start"] + shot["end"]) // 2
    # target, anchor frame, offset xyz, orthographic scale, target_y, target_z
    layouts = {
        "hook_warning": ("wheel", middle, (0.25, -2.25, 1.75), 3.95, 0.0, -0.18),
        "road_cut": ("wheel", middle, (.1, -3.4, 4.15), 4.04, 0.0, -0.18),
        "tire_contact": ("wheel", middle, (5.0, -4.2, 2.8), 3.55, 0.0, -0.08),
        "rumble_mechanism": ("wheel", middle, (-2.4, -6.8, 3.8), 4.15, 0.0, -0.13),
        "shoulder_location": ("car", middle, (.7, -5.3, 7.0), 8.8, -.1, .45),
        "driver_response": ("car", middle, (3.5, -6.0, 4.4), 8.4, -.25, .55),
    }
    target, frame, offset, scale, target_y, target_z = layouts[ident]
    return {"target": target, "anchor_frame": frame, "offset": offset,
            "scale": scale, "target_y": target_y, "target_z": target_z}


def caption_groups(text: str) -> list[tuple[int, int]]:
    """Word-index spans for lower captions: at most three words, balanced
    within each sentence, never crossing a sentence end."""
    tokens = text.split()
    groups, start = [], 0
    for index, token in enumerate(tokens):
        if token[-1] in ".!?" or index == len(tokens) - 1:
            count = index + 1 - start
            parts = math.ceil(count / 3)
            for part in range(parts):
                size = count // parts + (part < count % parts)
                groups.append((start, start + size))
                start += size
    return groups


def validate_episode(value: dict) -> dict:
    if not isinstance(value, dict) or set(value) != {
        "version", "series_id", "episode_id", "language",
        "audio_target_seconds", "fps", "resolution", "cycles_samples",
        "total_frames", "source_scene_sha256", "physics_disclosure",
        "editorial_status", "reference_urls", "shots",
    }:
        raise ValueError("episode manifest schema differs from approved production plan")
    fields = {
        "version": 1, "series_id": APPROVED_SERIES, "episode_id": APPROVED_EPISODE,
        "language": "en-US", "audio_target_seconds": 30, "fps": 30,
        "resolution": [1080, 1920], "cycles_samples": 32,
        "total_frames": 900, "source_scene_sha256": PINNED_ASSET,
        "editorial_status": "HOLD_UNTIL_FINAL_QA",
    }
    for key, expected in fields.items():
        if value.get(key) != expected:
            raise ValueError(f"production setting cannot change: {key}")
    if "not a calibrated" not in value["physics_disclosure"]:
        raise ValueError("physics disclosure missing")
    if not value["reference_urls"] or not all(
        url.startswith("https://") for url in value["reference_urls"]
    ):
        raise ValueError("no verifiable public road-safety evidence")
    shots = value["shots"]
    if len(shots) != 6 or tuple(s.get("id") for s in shots) != SHOT_IDS:
        raise ValueError("all six story beats are required")
    previous = 0
    for shot in shots:
        if set(shot) != {
            "id", "start", "end", "view", "narration_en",
            "visual_proof", "mechanism_change",
        }:
            raise ValueError("invalid shot content")
        if (shot["view"] not in VIEWS or shot["start"] != previous + 1
                or type(shot["end"]) is not int or shot["end"] - shot["start"] != 149):
            raise ValueError("missing/overlapping/shortened native motion shot")
        if not 8 <= len(shot["narration_en"].split()) <= 17:
            raise ValueError("shot narration too short/long for five seconds")
        if len(shot["visual_proof"]) < 18 or len(shot["mechanism_change"]) < 18:
            raise ValueError("visual change or mechanism proof insufficient")
        previous = shot["end"]
    if previous != 900:
        raise ValueError("native 900-frame ending missing")
    if len({s["narration_en"] for s in shots}) != 6:
        raise ValueError("repeated narration prohibited")
    return value


def load_episode(path: Path) -> dict:
    return validate_episode(json.loads(path.read_text(encoding="utf8")))


def shot_for_frame(episode: dict, frame: int) -> dict:
    if type(frame) is not int or not 1 <= frame <= 900:
        raise ValueError("frame outside the one real 30s film")
    return next(s for s in episode["shots"] if s["start"] <= frame <= s["end"])


def travel_x(frame: int) -> float:
    """Global monotonic trajectory shared by ALL independently rendered shards."""
    if type(frame) is not int or not 1 <= frame <= 900:
        raise ValueError("invalid absolute movie frame")
    return -4.2 + 8.4 * (frame - 1) / 899



def lane_return_offset(frame: int) -> float:
    """Human-initiated partial lane correction only in the final beat."""
    travel_x(frame)
    t = max(0.0, min(1.0, (frame - 750) / 150))
    return 0.32 * t * t * (3 - 2 * t)


def lane_return_heading(frame: int) -> float:
    """Bounded heading follows the actual lateral path derivative."""
    travel_x(frame)
    if frame <= 750 or frame >= 900:
        return 0.0
    t = (frame - 750) / 150
    dy = 0.32 * 6 * t * (1 - t) / 150
    dx = 8.4 / 899
    return math.atan2(dy, dx)


def rumble_displacement(frame: int) -> float:
    """Uncalibrated groove-synchronous demo, below physical cut depth."""
    return 0.008 * math.sin(travel_x(frame) / 0.34 * math.tau)


def render_slice(start: int, end: int) -> list[int]:
    if (type(start) is not int or type(end) is not int
            or start < 1 or end > 900 or end < start or end - start > 29):
        raise ValueError("up to 30 contiguous authored frames per shard")
    return list(range(start, end + 1))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--start", type=int, required=True)
    p.add_argument("--end", type=int, required=True)
    args = p.parse_args()
    episode = load_episode(args.manifest)
    frames = render_slice(args.start, args.end)
    print(json.dumps({
        "status": "PLANNED_NOT_RENDERED",
        "episode": episode["episode_id"],
        "frame_count": len(frames),
        "first_frame": frames[0],
        "last_frame": frames[-1],
        "first_shot": shot_for_frame(episode, frames[0])["id"],
        "last_shot": shot_for_frame(episode, frames[-1])["id"],
        "editorial_status": episode["editorial_status"],
        "production_approved": False,
    }, indent=2))


if __name__ == "__main__":
    main()
