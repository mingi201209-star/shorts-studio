"""Narration-bound driver insert plans for Curious Mechanics A/B/C.

This module plans edits only.  It never renders or encodes on the VPS.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

INSERTS_BY_VARIANT = {
    "A": (
        {
            "role": "driver_notices_warning",
            "destination_start": 665,
            "destination_end": 714,
            "source_start": 1,
            "source_end": 50,
            "transform": "identity",
            "cue_text": "distracted or drowsy driver",
            "cue_start": 22.800958,
            "cue_end": 25.741416,
        },
        {
            "role": "driver_turns_wheel",
            "destination_start": 853,
            "destination_end": 877,
            "source_start": 51,
            "source_end": 75,
            "transform": "hflip",
            "cue_text": "and steer back safely",
            "cue_start": 28.425541,
            "cue_end": 29.520749,
        },
    ),
    "B": (
        {
            "role": "driver_notices_warning",
            "destination_start": 659,
            "destination_end": 708,
            "source_start": 1,
            "source_end": 50,
            "transform": "identity",
            "cue_text": "a distracted driver",
            "cue_start": 22.089916,
            "cue_end": 23.113708,
        },
        {
            "role": "driver_turns_wheel",
            "destination_start": 853,
            "destination_end": 885,
            "source_start": 51,
            "source_end": 83,
            "transform": "hflip",
            "cue_text": "controls it",
            "cue_start": 28.81,
            "cue_end": 29.440957,
        },
    ),
    "C": (
        {
            "role": "driver_notices_warning",
            "destination_start": 554,
            "destination_end": 603,
            "source_start": 1,
            "source_end": 50,
            "transform": "identity",
            "cue_text": "distracted or drowsy driver notice",
            "cue_start": 19.096291,
            "cue_end": 21.155791,
        },
        {
            "role": "driver_turns_wheel",
            "destination_start": 844,
            "destination_end": 876,
            "source_start": 51,
            "source_end": 83,
            "transform": "hflip",
            "cue_text": "driver still has to notice and react",
            "cue_start": 27.337916,
            "cue_end": 29.635541,
        },
    ),
}
INSERTS = INSERTS_BY_VARIANT["B"]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inserts_for(variant: str) -> tuple[dict, ...]:
    try:
        return INSERTS_BY_VARIANT[variant]
    except KeyError as exc:
        raise ValueError(f"unknown driver-cut variant: {variant}") from exc


def frame_map(variant: str = "B") -> dict[int, dict]:
    mapping: dict[int, dict] = {}
    for insert in inserts_for(variant):
        destinations = range(insert["destination_start"], insert["destination_end"] + 1)
        sources = range(insert["source_start"], insert["source_end"] + 1)
        assert len(destinations) == len(sources)
        for destination, source in zip(destinations, sources):
            assert destination not in mapping
            mapping[destination] = {
                "role": insert["role"],
                "source_frame": source,
                "transform": insert["transform"],
            }
    expected = sum(
        row["destination_end"] - row["destination_start"] + 1 for row in inserts_for(variant)
    )
    assert len(mapping) == expected
    assert len({row["source_frame"] for row in mapping.values()}) == expected
    return mapping


def validate_direction(variant: str = "B") -> dict:
    """Record the coordinate audit that makes the hflip mandatory."""
    control = inserts_for(variant)[1]
    assert control["transform"] == "hflip"
    return {
        "car_forward_axis": "+x",
        "car_correction_axis": "+y",
        "car_heading_sign": "positive",
        "pilot_wheel_rotation_radians": -0.35,
        "pilot_camera_side": "front_of_driver_-y",
        "required_transform": "hflip",
        "physically_calibrated": False,
        "status": "DIRECTIONALLY_ALIGNED_BY_EXPLICIT_EDIT",
    }


def write_receipt(
    path: Path,
    *,
    variant: str = "B",
    pilot_proof: Path,
    native_manifest: Path,
) -> dict:
    mapping = frame_map(variant)
    reused = len(mapping)
    receipt = {
        "status": "PLANNED_FOR_GITHUB_ASSEMBLY",
        "variant": variant,
        "total_frames": 900,
        "original_native_frames_reused": 900 - reused,
        "driver_native_frames_reused": reused,
        "no_frame_holds_or_loops": True,
        "insertions": inserts_for(variant),
        "frame_map": {str(k): v for k, v in mapping.items()},
        "direction_audit": validate_direction(variant),
        "pilot_proof_sha256": digest(pilot_proof),
        "native_manifest_sha256": digest(native_manifest),
        "editorial_status": "HOLD_ACTUAL_REVIEW",
        "human_first_view": "UNVERIFIED",
        "upload_authorized": False,
    }
    path.write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt
