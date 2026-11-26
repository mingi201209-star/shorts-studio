"""Long-form 1: the layout of existing episode shots on the long narration, each episode's virtual timeline, and the thumbnails."""
import importlib

import numpy as np
import pytest

from benchmarks.longform import lf01
from benchmarks.longform import lf_timeline as lt

LAY = lf01.layout()


def test_every_line_is_shown_and_cuts_are_contiguous():
    shots = LAY["shots"]
    assert shots[0]["f0"] == 0 and shots[-1]["f1"] == LAY["frames"]
    assert all(a["f1"] == b["f0"] for a, b in zip(shots, shots[1:]))
    assert min(s["frames"] for s in shots) >= 6                              # no shot shorter than a quarter second
    shown = {(s["block"], s["line"]) for s in shots}
    assert shown == {(b["id"], i + 1) for b in lf01.BLOCKS for i in range(len(b["lines"]))}


def test_length_and_chapters():
    assert 240 <= LAY["seconds"] <= 600
    ids = [b["id"] for b in LAY["blocks"]]
    assert ids == [b["id"] for b in lf01.BLOCKS] and set(ids) == set(lf01.CHAPTER_NAMES)
    assert LAY["frames"] == sum(sum(r["frames"] for r in rows) for rows in LAY["episodes"].values())


def test_word_cuts_land_on_the_word():
    """Intro line 5 cuts to the cable barrier on the second "Stopping"; the outro's list cuts on "cables", "nets" and "and"."""
    intro5 = [s for s in LAY["shots"] if s["block"] == "lf01_intro" and s["line"] == 5]
    assert [s["episode"] for s in intro5] == ["wedge", "cable"]
    assert intro5[1]["t0"] - intro5[0]["t0"] > 1.0
    outro4 = [s for s in LAY["shots"] if s["block"] == "lf01_outro" and s["line"] == 4]
    assert [s["episode"] for s in outro4] == ["terminal", "cable", "rocknet", "emas"]
    assert all(s["frames"] >= 12 for s in outro4)


@pytest.mark.parametrize("key", sorted(lt.EPISODES))
def test_virtual_timeline_holds_each_shot_and_its_whole_story(key):
    rows = LAY["episodes"][key]
    mod = lf01.episode_timeline(key, LAY)
    segs = mod.segments()
    assert mod.frame_count() == sum(r["frames"] for r in rows)
    assert [s["label"] for s in segs] == [r["row"] for r in rows]
    assert not any(s["flags"].get("loop") for s in segs)
    own = {s["label"]: s for s in importlib.import_module(lt.EPISODES[key][0]).segments()}
    for s, r in zip(segs, rows):
        assert abs((s["t1"] - s["t0"]) * lt.FPS - r["frames"]) < 1e-6
        o = own[s["label"]]
        assert s["sim0"] == pytest.approx(o["sim0"], abs=1e-3)
        if "warp" in s["flags"]:                                              # EP.13: impact at a fixed time, then slow motion
            tc = s["flags"]["warp"][0]
            if s["t1"] - s["t0"] >= tc:
                assert s["sim1"] >= 0.0
        else:                                                                 # story knots stretched to the shot: the same action
            assert s["sim1"] == pytest.approx(o["sim1"], abs=0.02 * max(1e-3, abs(o["sim1"] - o["sim0"])))


def test_wedge_rise_override_is_used():
    mod = lf01.episode_timeline("wedge", LAY)
    seg = next(s for s in mod.segments() if s["label"] == "B-rises-in-a-second")
    assert seg["cam_a"]["loc"] == (-0.4, 6.5, 1.5) and seg["cam_a"]["lens"] == 24.0


def test_thumbnails(tmp_path):
    from PIL import Image

    from benchmarks.longform import thumbnail_lf as th
    kit = lt.ROOT / "examples/longform/lf01-publish-kit"
    for name in ("thumbnail-A-wedge.jpg", "thumbnail-B-ribbon.jpg", "thumbnail-C-net.jpg"):
        im = Image.open(kit / name)
        assert im.size == (1280, 720) and (kit / name).stat().st_size < 2_000_000
    still = Image.new("RGB", (1920, 1080), (90, 140, 200))
    still.save(tmp_path / "s.png")
    im = th.headline(th.grade(Image.open(tmp_path / "s.png")), "ROADS|FIGHT BACK", "tl")
    assert im.size == th.SIZE
    c = np.asarray(im.crop((0, 0, 760, 320))).reshape(-1, 3).astype(int)
    assert (c.min(axis=1) > 235).sum() > 2000                                 # white first line
    assert ((c[:, 0] > 230) & (c[:, 1] > 190) & (c[:, 1] < 235) & (c[:, 2] < 60)).sum() > 2000   # accent last line
    assert (c.max(axis=1) < 40).sum() > 2000                                  # dark outline
