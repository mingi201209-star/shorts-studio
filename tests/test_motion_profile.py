import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.road_safety import motion_profile as mp


def _still(n, value=100.0):
    return [np.full((20, 20), value, np.float32) for _ in range(n)]


def test_a_still_picture_has_no_motion_and_one_beat():
    d = mp.diff_series(_still(30))
    s = mp.summarize(d)
    assert s["median"] == 0 and s["share_under_4"] == 1.0
    b = mp.registered_beats(_still(60))
    assert b["beats"] == 1 and b["longest_without_beat_s"] == 30.0


def test_a_picture_that_changes_every_sample_registers_every_sample():
    frames = [np.full((20, 20), 40.0 * (i % 2) + 10.0, np.float32) for i in range(40)]   # alternates by 40
    b = mp.registered_beats(frames)
    assert b["beats"] == 40 and b["longest_without_beat_s"] == 0.5
    assert mp.summarize(mp.diff_series(frames))["share_over_25"] == 1.0


def test_a_slow_drift_registers_only_once_it_adds_up_to_the_threshold():
    frames = [np.full((20, 20), 2.0 * i, np.float32) for i in range(40)]   # +2 per sample, 12 needs 6 samples
    b = mp.registered_beats(frames)
    assert b["beats"] == 1 + 40 // 6 or b["beats"] == 1 + (40 - 1) // 6
    assert 2.9 < b["longest_without_beat_s"] < 3.2


def test_resample_picks_every_nth_frame():
    frames = [np.full((2, 2), float(i), np.float32) for i in range(30)]
    out = mp.resample(frames, 15, 2)
    assert len(out) == 4 and [float(f[0, 0]) for f in out] == [0.0, 8.0, 15.0, 22.0]


def test_extract_frames_reads_a_real_video(tmp_path):
    import shutil
    import subprocess
    if shutil.which("ffmpeg") is None:
        return
    video = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=1080x1920:rate=30:duration=1",
                    "-pix_fmt", "yuv420p", str(video)], check=True)
    frames = mp.extract_frames(video, "860:1100:0:320")
    assert len(frames) in (15, 16) and frames[0].shape == (275, 215)
