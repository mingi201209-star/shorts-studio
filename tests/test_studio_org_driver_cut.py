import json

from benchmarks.road_safety.curious_mechanics_progressive_delivery import (
    compose_editorial_filters,
)
from benchmarks.road_safety.render_driver_insert import driver_vibration
from shorts_studio.studio_org.driver_cut import (
    INSERTS,
    INSERTS_BY_VARIANT,
    frame_map,
    validate_direction,
    write_receipt,
)


def test_final_driver_cut_uses_captions_without_presentation_panel():
    assert compose_editorial_filters('ass=film.ass') == 'ass=film.ass'
    assert compose_editorial_filters(
        'ass=film.ass', 'mechanism.ass'
    ) == 'ass=mechanism.ass,ass=film.ass'

EXPECTED = {
    "A": (set(range(665, 715)) | set(range(853, 878)), 75),
    "B": (set(range(659, 709)) | set(range(853, 886)), 83),
    "C": (set(range(554, 604)) | set(range(844, 877)), 83),
}


def test_each_variant_has_an_independently_timed_unique_plan():
    assert set(INSERTS_BY_VARIANT) == set("ABC")
    for variant, (destinations, count) in EXPECTED.items():
        mapping = frame_map(variant)
        assert set(mapping) == destinations
        assert len(mapping) == count
        assert len({row["source_frame"] for row in mapping.values()}) == count
        assert len(set(range(1, 901)) - set(mapping)) == 900 - count


def test_a_and_c_reaction_peak_lands_inside_their_own_narration_cue():
    for variant in ("A", "C"):
        insert = INSERTS_BY_VARIANT[variant][0]
        peak_start = (insert["destination_start"] - 1) / 30 + 0.67
        peak_end = (insert["destination_start"] - 1) / 30 + 1.07
        assert insert["cue_start"] <= peak_start
        assert peak_end <= insert["cue_end"]


def test_a_and_c_steering_motion_overlaps_their_own_steer_cue():
    for variant in ("A", "C"):
        insert = INSERTS_BY_VARIANT[variant][1]
        clip_start = (insert["destination_start"] - 1) / 30
        clip_end = insert["destination_end"] / 30
        assert clip_start <= insert["cue_end"]
        assert clip_end >= insert["cue_start"]


def test_each_variant_leaves_exterior_lane_return_result_after_control_insert():
    for variant in "ABC":
        assert INSERTS_BY_VARIANT[variant][1]["destination_end"] < 900


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


def test_variant_specific_receipt_counts(tmp_path):
    pilot = tmp_path / "pilot.json"
    manifest = tmp_path / "manifest.json"
    pilot.write_text("{}\n")
    manifest.write_text("{}\n")
    for variant, (_, count) in EXPECTED.items():
        receipt = tmp_path / f"receipt-{variant}.json"
        actual = write_receipt(
            receipt, variant=variant, pilot_proof=pilot, native_manifest=manifest
        )
        assert actual["variant"] == variant
        assert actual["driver_native_frames_reused"] == count
        assert actual["original_native_frames_reused"] == 900 - count


def test_driver_body_receives_visible_rumble_before_notice_reaction():
    samples = [driver_vibration(frame / 30) for frame in range(0, 25)]
    lateral = [point[0] for point in samples]
    vertical = [point[1] for point in samples]
    assert driver_vibration(0.0) == (0.0, 0.0)
    assert driver_vibration(0.70) == (0.0, 0.0)
    assert max(lateral) - min(lateral) >= 0.014
    assert max(vertical) - min(vertical) >= 0.020
