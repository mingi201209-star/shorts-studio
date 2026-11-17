"""One full-screen car per frame, sequential comparison, no split screen, no text, and the cues the picture is built on."""
import json
from pathlib import Path

from benchmarks.crumple_zone import crumple_cameras as cameras
from benchmarks.crumple_zone import crumple_motion as cm

ROOT = Path(__file__).resolve().parents[1]


def test_one_full_screen_car_per_frame():
    assert all(s["layout"] == "full" for s in cm.SEGMENTS)
    assert sum(s["last"] - s["first"] + 1 for s in cm.SEGMENTS) == cm.TOTAL_FRAMES
    assert all(len(cm.visible_panels(frame)) == 1 for frame in range(1, cm.TOTAL_FRAMES + 1))
    assert set(cameras.PANEL_PX) == {"full"}      # no stacked or split frame exists in the code any more


def test_the_cuts_land_on_the_measured_narration():
    cues = {c["text"]: c["start"] for c in cm._cues()["cues"]}
    first = {s["id"]: (s["first"] - 1) / cm.FPS for s in cm.SEGMENTS}
    assert abs(first["R"] - cues[cm.RIGID_BEAT]) < 1 / cm.FPS
    assert abs(first["C"] - cues[cm.CLOSE_BEAT]) < 1 / cm.FPS


def test_the_rigid_crash_starts_from_the_same_camera_as_the_first_crash():
    k, r = cameras.paths()["K"][0], cameras.paths()["R"][0]
    assert {x: k[x] for x in ("loc", "target", "lens", "at", "rel")} == {x: r[x] for x in ("loc", "target", "lens", "at", "rel")}
