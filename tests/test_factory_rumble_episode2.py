"""No reusable cached film may masquerade as a freshly rendered new episode."""
import copy
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
