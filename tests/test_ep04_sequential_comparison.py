"""Check that each narrated comparison uses a single full-screen crash replay."""

import json
from pathlib import Path

from benchmarks.crumple_zone import crumple_cameras as cameras
from benchmarks.crumple_zone import crumple_motion as cm


def test_one_full_screen_car_per_frame():
    assert all(s["layout"] != "stack" for s in cm.SEGMENTS)
    assert cm.TOTAL_FRAMES == 780
    assert sum(s["last"] - s["first"] + 1 for s in cm.SEGMENTS) == cm.TOTAL_FRAMES
    assert all(len(cm.visible_panels(frame)) == 1 for frame in range(1, cm.TOTAL_FRAMES + 1))


def test_matched_crashes_start_with_their_narration():
    root = Path(__file__).resolve().parents[1]
    cues = json.loads((root / "examples/experiments/crumple-zone-real-cues.json").read_text())
    starts = {cue["text"]: cue["start"] for cue in cues["cues"]}
    crumple, rigid = (next(s for s in cm.SEGMENTS if s["id"] == name) for name in ("C2", "C3"))

    assert crumple["first"] < rigid["first"]
    assert abs((crumple["first"] - 1) / cm.FPS - starts["slow the car down"]) < 1 / cm.FPS
    assert abs((rigid["first"] - 1) / cm.FPS - starts["The rigid front stops"]) < 1 / cm.FPS
    assert crumple["panels"] == ("crumple",)
    assert rigid["panels"] == ("rigid",)
    assert crumple["camera"] == rigid["camera"] == "compare"
    assert crumple["layout"] == rigid["layout"] == "sequential"
    for offset in range(crumple["last"] - crumple["first"] + 1):
        a, b = crumple["first"] + offset, rigid["first"] + offset
        assert cm.frame_time(a) == cm.frame_time(b)
        assert cameras.camera("compare", a) == cameras.camera("compare", b)
