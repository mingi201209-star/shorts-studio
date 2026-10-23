"""No reusable cached film may masquerade as a freshly rendered new episode."""
import copy
import hashlib
import json
import math
import re
import wave
from itertools import pairwise
from pathlib import Path

import pytest
from PIL import ImageFont

from shorts_studio.factory.rumble_episode2 import (
    lane_return_heading,
    lane_return_offset,
    load_episode,
    render_slice,
    shot_for_frame,
    travel_x,
    validate_episode,
)
from shorts_studio.timing import WordTiming, validate_timings

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
    assert hook["target"] == "wheel"
    assert hook["scale"] <= 3.4
    # Low view of the tyre: no steeper than the original 30 degree hook.
    x, y, z = hook["offset"]
    assert math.degrees(math.atan2(z, math.hypot(x, y))) <= 30
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


CAPTURE = ROOT / "benchmarks" / "road_safety" / "episode2_narration"


@pytest.mark.parametrize("number", range(1, 7))
def test_stored_episode2_speech_binary_provenance_and_pcm(number):
    capture = json.loads((CAPTURE / "capture.json").read_text())
    assert (capture["voice"], capture["rate"]) == ("en-US-AndrewNeural", "+5%")
    assert len(capture["shots"]) == 6
    rec = capture["shots"][number - 1]
    assert rec["id"] == number
    assert rec["text"] == fresh()["shots"][number - 1]["narration_en"]
    for key in ("audio", "raw_audio", "timing"):
        path = (CAPTURE / rec[key]).resolve()
        assert path.parent == CAPTURE.resolve()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == rec[key + "_sha256"]
    with wave.open(str(CAPTURE / rec["audio"]), "rb") as pcm:
        assert (pcm.getnchannels(), pcm.getframerate(), pcm.getsampwidth()) == (1, 48000, 2)
        assert pcm.getcomptype() == "NONE"
        duration = pcm.getnframes() / pcm.getframerate()
        data = pcm.readframes(pcm.getnframes())
        assert len(data) == pcm.getnframes() * pcm.getsampwidth()
        assert any(data), "all-zero PCM"
    assert duration == pytest.approx(rec["duration"], abs=1 / 48000)
    assert 0 < duration <= 4.75
    timing = json.loads((CAPTURE / rec["timing"]).read_text())
    assert timing["text"] == rec["text"]
    assert (timing["voice"], timing["rate"]) == (capture["voice"], capture["rate"])
    words = [WordTiming(**word) for word in timing["words"]]
    assert words
    validate_timings(words, duration)
    assert all(math.isfinite(w.start) and math.isfinite(w.end)
               and w.start < w.end for w in words)
    assert all(a.end <= b.start for a, b in pairwise(words))
    assert words[-1].end + .1 <= duration
    def normalize(text):
        return re.sub(r"[^a-z0-9]", "", text.lower())

    assert normalize(" ".join(w.text for w in words)) == normalize(rec["text"])


def test_review_caption_candidate_uses_real_word_boundaries_and_fits_font():
    document = (ROOT / "docs" / "rumble-episode2-production.md").read_text()
    blocks = re.findall(r"```srt\n(.*?)```", document, re.DOTALL)
    assert len(blocks) == 1
    entries = blocks[0].strip().split("\n\n")
    assert len(entries) == 31
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 62)
    timings = [json.loads((CAPTURE / f"voice_{n:02d}.timing.json").read_text())["words"]
               for n in range(1, 7)]
    consumed = [0] * 6
    previous_end = 0.0

    def seconds(stamp):
        assert re.fullmatch(r"00:\d{2}:\d{2},\d{3}", stamp)
        hours, minutes, whole, milliseconds = map(int, re.split(r"[:,]", stamp))
        assert minutes < 60 and whole < 60
        return hours * 3600 + minutes * 60 + whole + milliseconds / 1000

    for number, entry in enumerate(entries, 1):
        index, interval, text = entry.splitlines()
        assert int(index) == number
        start, end = map(seconds, interval.split(" --> "))
        assert previous_end <= start < end <= 30
        previous_end = end
        shot = int(start // 5)
        assert 0 <= shot < 6 and end <= (shot + 1) * 5
        tokens = text.split()
        cursor = consumed[shot]
        group = timings[shot][cursor:cursor + len(tokens)]
        assert len(group) == len(tokens) and group
        assert text == " ".join(word["text"] for word in group)
        assert start == pytest.approx(shot * 5 + .1 + group[0]["start"], abs=.000501)
        assert end == pytest.approx(shot * 5 + .1 + group[-1]["end"], abs=.000501)
        if shot == 5:
            assert not cursor < 8 < cursor + len(tokens), "crossed sentence boundary"
        consumed[shot] += len(tokens)
        assert len(text) <= 31
        lines = [text]
        if len(text) > 24:
            middle = len(tokens) // 2
            lines = [" ".join(tokens[:middle]), " ".join(tokens[middle:])]
        assert all(font.getlength(line) <= 900 for line in lines), text
    assert consumed == [len(words) for words in timings]
    assert sum(consumed) == 88


# Measured in Blender 5.0.1 from the pinned CC0 sedan (a82e0582) after the
# renderer's 0.85 scale and pi/2 yaw: tyre centres sit 1.156 m ahead of/behind
# the car origin, 0.709 m toward the near (-y) shoulder, 0.28 m above the car
# origin; Front_tire/Rear_tire are the near-side pair over the milled band.
NEAR_TYRE = {"Front_tire": (1.156, -0.709, 0.28), "Rear_tire": (-1.156, -0.709, 0.28)}
TYRE_RADIUS = 0.30


def _tyre_world(frame, tyre):
    forward, lateral, height = NEAR_TYRE[tyre]
    lateral += 0.30
    heading = lane_return_heading(frame)
    c, s = math.cos(heading), math.sin(heading)
    return (travel_x(frame) + forward * c - lateral * s,
            -0.30 + lane_return_offset(frame) + forward * s + lateral * c, height)


def _camera_axes(offset):
    length = math.sqrt(sum(v * v for v in offset))
    view = [-v / length for v in offset]
    flat = math.hypot(view[0], view[1])
    right = (view[1] / flat, -view[0] / flat, 0.0)
    up = (right[1] * view[2] - right[2] * view[1],
          right[2] * view[0] - right[0] * view[2],
          right[0] * view[1] - right[1] * view[0])
    return right, up


def _target(shot, layout):
    if layout["target"] == "car":
        return (travel_x(layout["anchor_frame"]), layout["target_y"], layout["target_z"])
    tyre = "Rear_tire" if shot["id"] == "rumble_mechanism" else "Front_tire"
    x, y, z = _tyre_world(layout["anchor_frame"], tyre)
    return (x, y, z + layout["target_z"])


def test_fixed_wheel_cameras_keep_the_near_tyre_in_frame_for_the_whole_shot():
    from shorts_studio.factory.rumble_episode2 import camera_layout

    for shot in fresh()["shots"]:
        layout = camera_layout(shot)
        if layout["target"] != "wheel":
            continue
        tyre = "Rear_tire" if shot["id"] == "rumble_mechanism" else "Front_tire"
        target = _target(shot, layout)
        right, up = _camera_axes(layout["offset"])
        half_h = layout["scale"] / 2
        half_w = half_h * 9 / 16
        for frame in range(shot["start"], shot["end"] + 1):
            delta = [a - b for a, b in zip(_tyre_world(frame, tyre), target)]
            u = sum(d * r for d, r in zip(delta, right))
            v = sum(d * w for d, w in zip(delta, up))
            assert abs(u) + TYRE_RADIUS <= .9 * half_w, (shot["id"], frame)
            assert abs(v) + TYRE_RADIUS <= .9 * half_h, (shot["id"], frame)


def test_orthographic_camera_plane_never_starts_below_the_road():
    from shorts_studio.factory.rumble_episode2 import camera_layout

    for shot in fresh()["shots"]:
        layout = camera_layout(shot)
        _, up = _camera_axes(layout["offset"])
        camera_z = _target(shot, layout)[2] + layout["offset"][2]
        # Rays from a plane edge below grade render as a black void band.
        assert camera_z - layout["scale"] / 2 * up[2] >= .25, shot["id"]


def test_lower_captions_never_cover_the_tyre_road_contact():
    from shorts_studio.factory.rumble_episode2 import camera_layout

    film = (ROOT / "benchmarks/road_safety/episode2_film.py").read_text()
    style = re.search(r"^Style: Caption,([^\n]*)$", film, re.MULTILINE).group(1).split(",")
    font_size, alignment, margin_v = int(style[1]), int(style[17]), int(style[20])
    assert alignment == 2, "bottom-anchored lower captions"
    # Two lines at most (the assembler splits cues longer than 24 chars).
    caption_top = 1920 - margin_v - 2 * font_size * 1.2
    for shot in fresh()["shots"]:
        layout = camera_layout(shot)
        if layout["target"] != "wheel":
            continue
        tyre = "Rear_tire" if shot["id"] == "rumble_mechanism" else "Front_tire"
        target = _target(shot, layout)
        _, up = _camera_axes(layout["offset"])
        pixels_per_metre = 1920 / layout["scale"]
        for frame in range(shot["start"], shot["end"] + 1):
            delta = [a - b for a, b in zip(_tyre_world(frame, tyre), target)]
            centre_v = sum(d * w for d, w in zip(delta, up))
            contact_row = 960 - (centre_v - TYRE_RADIUS) * pixels_per_metre
            assert contact_row <= caption_top - 100, (shot["id"], frame, contact_row)


def test_caption_groups_respect_sentences_and_avoid_orphan_words():
    from shorts_studio.factory.rumble_episode2 import caption_groups

    assert caption_groups("These grooves cannot steer your car for you. "
                          "The driver still needs to react in time.") == [
        (0, 3), (3, 6), (6, 8), (8, 11), (11, 14), (14, 16)]
    assert caption_groups("Stop.") == [(0, 1)]
    for shot in fresh()["shots"]:
        text = shot["narration_en"]
        tokens = text.split()
        groups = caption_groups(text)
        assert [g[0] for g in groups][1:] == [g[1] for g in groups][:-1]
        assert groups[0][0] == 0 and groups[-1][1] == len(tokens)
        for start, end in groups:
            words = tokens[start:end]
            assert 2 <= len(words) <= 3, words
            # A sentence may only end on a group's last word.
            assert not any(w[-1] in ".!?" for w in words[:-1]), words
