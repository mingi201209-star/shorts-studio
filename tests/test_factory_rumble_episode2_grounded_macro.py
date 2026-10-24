"""Native Episode 2 framing and truthful scene semantics."""
import math
from pathlib import Path
from shorts_studio.factory.rumble_episode2 import (
    camera_layout, detail_visibility, load_episode, semantic_labels, travel_x,
)
MANIFEST=Path(__file__).resolve().parents[1]/"examples/factory/rumble-episode2-30s.json"


def test_hook_wheel_is_visible_without_full_blue_vehicle_occlusion():
    visual=detail_visibility("hook_warning")
    assert visual["body_visible"] is False
    assert visual["near_shoulder_visible"] is True


def test_road_and_tire_views_are_low_angle_and_keep_original_tyre_in_frame():
    shots={s["id"]:s for s in load_episode(MANIFEST)["shots"]}
    for ident in ("road_cut", "tire_contact"):
        shot=shots[ident]
        view=camera_layout(shot)
        x,y,z=view["offset"]
        horizontal=math.hypot(x,y)
        norm=math.hypot(horizontal,z)
        assert math.degrees(math.atan2(z,horizontal)) < 33, ident
        right_x=abs(y/horizontal)
        up_x=abs(x*z/(norm*horizontal))
        up_z=horizontal/norm
        horizontal_limit=.9*view["scale"]*9/32
        vertical_limit=.9*view["scale"]/2
        for frame in range(shot["start"], shot["end"]+1):
            dx=abs(travel_x(frame)-travel_x(view["anchor_frame"]))
            assert dx*right_x+.30 <= horizontal_limit, (ident,frame,"width")
            assert dx*up_x+.30 <= vertical_limit, (ident,frame,"height")
        camera_z=.28+view["target_z"]+z
        assert camera_z-view["scale"]/2*up_z>=.25, ident


def test_explanatory_wheel_labels_match_visible_3d_assets():
    for ident in ("road_cut","tire_contact"):
        assert detail_visibility(ident)["body_visible"] is False
        labels=semantic_labels(ident)
        assert all("blue car" not in text.lower() for text in labels)
        assert all(any(name in text.lower() for name in ("tire","wheel","tyre"))
                   for text in labels)


def test_fixed_camera_still_anchors_each_original_five_second_shot():
    for shot in load_episode(MANIFEST)["shots"]:
        camera=camera_layout(shot)
        assert camera["anchor_frame"]==(shot["start"]+shot["end"])//2
