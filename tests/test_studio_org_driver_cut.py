import json

from shorts_studio.studio_org.driver_cut import (
    INSERTS,
    frame_map,
    validate_direction,
    write_receipt,
)


def test_driver_cut_reuses_exactly_83_unique_native_frames():
    mapping = frame_map()
    assert len(mapping) == 83
    assert len({row["source_frame"] for row in mapping.values()}) == 83
    assert set(mapping) == set(range(659, 709)) | set(range(853, 886))
    assert set(range(1, 901)) - set(mapping)
    assert len(set(range(1, 901)) - set(mapping)) == 817


def test_driver_reaction_is_inside_actual_distracted_driver_cue():
    reaction_visible_start = (659 - 1) / 30 + 0.67
    reaction_visible_end = (659 - 1) / 30 + 1.07
    assert INSERTS[0]["cue_start"] <= reaction_visible_start
    assert reaction_visible_end <= INSERTS[0]["cue_end"]


def test_steering_motion_overlaps_actual_controls_it_cue():
    clip_start = (853 - 1) / 30
    pilot_motion_start = clip_start + (51 - 1) / 30 - (51 - 1) / 30
    pilot_motion_end = 885 / 30
    assert pilot_motion_start <= INSERTS[1]["cue_end"]
    assert pilot_motion_end >= INSERTS[1]["cue_start"]


def test_control_insert_is_flipped_to_match_positive_lane_return():
    audit = validate_direction()
    assert audit["car_heading_sign"] == "positive"
    assert audit["pilot_wheel_rotation_radians"] < 0
    assert audit["required_transform"] == "hflip"
    assert frame_map()[853]["transform"] == "hflip"


def test_no_driver_source_frame_is_held_or_repeated():
    ordered = [frame_map()[n]["source_frame"] for n in sorted(frame_map())]
    assert ordered == list(range(1, 84))


def test_driver_cut_receipt_is_valid_json(tmp_path):
    pilot = tmp_path / "pilot.json"
    manifest = tmp_path / "manifest.json"
    receipt = tmp_path / "receipt.json"
    pilot.write_text("{}\n")
    manifest.write_text("{}\n")

    expected = write_receipt(receipt, pilot_proof=pilot, native_manifest=manifest)

    assert json.loads(receipt.read_text()) == json.loads(json.dumps(expected))
