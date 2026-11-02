"""Narration-bound driver insert plan for Curious Mechanics B.

This module plans edits only.  It never renders or encodes on the VPS.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

INSERTS = (
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
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frame_map() -> dict[int, dict]:
    mapping: dict[int, dict] = {}
    for insert in INSERTS:
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
    assert len(mapping) == 83
    assert len({row["source_frame"] for row in mapping.values()}) == 83
    return mapping


def validate_direction() -> dict:
    """Record the coordinate audit that makes the hflip mandatory.

The car travels in +x and the final correction increases +y, so its heading
is positive.  The front-facing pilot renders a negative wheel rotation; from
the driver's opposite viewing side that reads as the opposite turn.  A
horizontal flip reverses the visible turn without repeating or holding frames.
This is an editorial direction check, not a calibrated steering model.
"""
    control = INSERTS[1]
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


def write_receipt(path: Path, *, pilot_proof: Path, native_manifest: Path) -> dict:
    mapping = frame_map()
    receipt = {
        "status": "PLANNED_FOR_GITHUB_ASSEMBLY",
        "variant": "B",
        "total_frames": 900,
        "original_native_frames_reused": 817,
        "driver_native_frames_reused": 83,
        "no_frame_holds_or_loops": True,
        "insertions": INSERTS,
        "frame_map": {str(k): v for k, v in mapping.items()},
        "direction_audit": validate_direction(),
        "pilot_proof_sha256": digest(pilot_proof),
        "native_manifest_sha256": digest(native_manifest),
        "editorial_status": "HOLD_ACTUAL_REVIEW",
        "human_first_view": "UNVERIFIED",
        "upload_authorized": False,
    }
    path.write_text(json.dumps(receipt, indent=2) + "\\n")
    return receipt
