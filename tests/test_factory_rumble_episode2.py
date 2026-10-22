"""No reusable cached film may masquerade as a freshly rendered new episode."""
import copy
from itertools import pairwise
from pathlib import Path

import pytest

from shorts_studio.factory.rumble_episode2 import (
    load_episode,
    render_slice,
    shot_for_frame,
    travel_x,
    validate_episode,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "examples" / "factory" / "rumble-episode2-30s.json"


def fresh():
    return load_episode(MANIFEST)


def test_exact_900_frames_at_original_quality_and_order():
    v = fresh()
    assert v["resolution"] == [1080, 1920]
    assert v["cycles_samples"] == 32 and v["fps"] == 30
    assert [(s["start"], s["end"]) for s in v["shots"]] == [
        (1,150),(151,300),(301,450),(451,600),(601,750),(751,900)
    ]
    assert len([shot_for_frame(v,i)["id"] for i in range(1,901)]) == 900


def test_shard_boundaries_do_not_repeat_movement():
    pieces = [render_slice(s, s+29) for s in range(1,901,30)]
    assert len(pieces) == 30
    assert [i for part in pieces for i in part] == list(range(1,901))
    assert len({travel_x(i) for i in range(1,901)}) == 900
    assert travel_x(1) < travel_x(900)


@pytest.mark.parametrize("start,end", [(0,10),(50,49),(1,31),(901,901),
                                       (899,901),(-1,900)])
def test_unapproved_frame_slice_rejected(start,end):
    with pytest.raises(ValueError):
        render_slice(start,end)


def test_no_reduced_native_quality():
    base = fresh()
    for k,val in [("resolution",[450,800]),("fps",24),
                  ("cycles_samples",7),("total_frames",750),
                  ("editorial_status","READY"),("episode_id","differential-gears")]:
        altered = copy.deepcopy(base)
        altered[k] = val
        with pytest.raises(ValueError):
            validate_episode(altered)


def test_no_missing_story_beat_or_double_counted_frames():
    base=fresh()
    base["shots"][3]["start"]=449
    with pytest.raises(ValueError):
        validate_episode(base)


def test_scripts_and_motion_cannot_be_empty():
    base=fresh()
    base["shots"][0]["mechanism_change"]="missing"
    with pytest.raises(ValueError):
        validate_episode(base)


def test_no_unauthorized_frame_requested():
    ep=fresh()
    for n in (0, 901):
        with pytest.raises(ValueError):
            shot_for_frame(ep,n)


def test_narration_english_and_no_fake_upload_authorization():
    ep=fresh()
    assert ep["language"] == "en-US"
    assert ep["editorial_status"]=="HOLD_UNTIL_FINAL_QA"
    spoken=" ".join(s["narration_en"] for s in ep["shots"])
    assert 60 <= len(spoken.split()) <= 100
    assert "doesn't" not in spoken


def test_visual_contact_cadence_and_manual_lane_return():
    from shorts_studio.factory.rumble_episode2 import (
        lane_return_heading,
        lane_return_offset,
        rumble_displacement,
    )
    # A 30-second shot must show repeated road contact, not one slowly moving car.
    assert travel_x(900) - travel_x(1) >= 8.0
    # No fake autonomous steering: vehicle keeps its line until the response beat.
    assert lane_return_offset(1) == lane_return_offset(750) == 0.0
    assert lane_return_heading(750) == 0.0
    values = [lane_return_offset(i) for i in range(750, 901)]
    assert all(a <= b for a,b in pairwise(values))
    assert 0.25 <= values[-1] <= 0.40
    assert 0 < lane_return_heading(825) < 0.4
    assert lane_return_heading(900) == 0.0
    # Actual contact vibration changes with world distance; never huge bouncing.
    heights = [rumble_displacement(i) for i in range(1,901)]
    assert len({round(z, 5) for z in heights}) > 200
    assert max(abs(z) for z in heights) <= 0.012


def test_legacy_recovery_does_not_autorun_on_new_renderer_commits():
    workflow = (ROOT / ".github/workflows/rumble-episode2-film.yml").read_text()
    event_header = workflow.split("jobs:", 1)[0]
    assert "workflow_dispatch:" in event_header
    assert "  push:" not in event_header
    assert "LEGACY_RENDERER_SHA" in workflow
    assert 'test "$GITHUB_SHA" = "$LEGACY_RENDERER_SHA"' in workflow


def test_static_camera_layout_prioritizes_opening_contact_and_readable_context():
    from shorts_studio.factory.rumble_episode2 import camera_layout

    shot = {s["id"]: s for s in fresh()["shots"]}
    hook = camera_layout(shot["hook_warning"])
    assert hook["anchor_frame"] == (shot["hook_warning"]["start"] + shot["hook_warning"]["end"]) // 2
    assert hook["target"] == "wheel"
    assert hook["scale"] <= 4.0
    assert hook["offset"][2] <= 1.8
    for ident in ("shoulder_location", "driver_response"):
        layout = camera_layout(shot[ident])
        assert layout["target"] == "car"
        assert 7.5 <= layout["scale"] <= 9.2
        assert layout["anchor_frame"] == (shot[ident]["start"] + shot[ident]["end"]) // 2
    for s in shot.values():
        layout = camera_layout(s)
        assert layout["scale"] > 0
        assert len(layout["offset"]) == 3


def test_environment_extent_covers_long_shots_without_black_void():
    from shorts_studio.factory import rumble_episode2 as plan

    assert plan.ROAD_X_HALF_SPAN >= 13
    assert plan.ROAD_Y_NEAR_EDGE <= -8
    assert plan.DIRT_Y_FAR_EDGE >= 14


def test_hook_camera_preserves_tire_contact_through_entire_five_seconds():
    from shorts_studio.factory.rumble_episode2 import camera_layout
    hook = fresh()["shots"][0]
    view = camera_layout(hook)
    # An early absolute-frame camera anchor lets the tire leave the shot.
    assert view["anchor_frame"] == (hook["start"] + hook["end"]) // 2
    assert view["target"] == "wheel"
    assert 3.5 <= view["scale"] <= 4.0
    # Lower, contact-focused fixed viewpoint instead of a hood-dominated hero.
    assert 1.2 <= view["offset"][2] <= 1.9
    assert view["target_z"] <= -0.18


def test_opening_is_a_side_on_tire_contact_view_not_hood_hero():
    """The opening must prove tire/groove contact instead of foregrounding hood."""
    from shorts_studio.factory.rumble_episode2 import camera_layout

    shot = fresh()["shots"][0]
    camera = camera_layout(shot)
    offset_x, offset_y, offset_z = camera["offset"]
    assert -0.45 <= offset_x <= 0.45, "front-quarter view exposes oversized hood"
    assert offset_y < -2.0, "camera must stay outside roadside wheel"
    assert 1.15 <= offset_z <= 1.8
    assert 3.5 <= camera["scale"] <= 4.0
    assert camera["anchor_frame"] == (shot["start"] + shot["end"]) // 2
    assert camera["target"] == "wheel"
