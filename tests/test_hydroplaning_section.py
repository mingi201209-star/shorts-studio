from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from shorts_studio import hydroplaning_section as hs
from shorts_studio.hook_studio import generate_and_judge
from shorts_studio.retention_rules import hook_violation

ROOT = Path(__file__).resolve().parents[1]


def _gs(n=41):
    return [i / (n - 1) for i in range(n)]


def test_physical_state_is_monotonic_and_ordered():
    wedge = [hs.wedge_at(g) for g in _gs()]
    contact = [hs.contact_at(g) for g in _gs()]
    lift = [hs.lift_at(g) for g in _gs()]
    rot = [hs.rotation_at(g) for g in _gs()]
    assert contact[0] == 1.0 and contact[-1] == 0.0
    assert all(b >= a - 1e-9 for a, b in zip(wedge, wedge[1:]))
    assert lift[0] == 0.0 and lift[-1] == hs.MAX_LIFT
    assert all(b >= a - 1e-9 for a, b in zip(lift, lift[1:]))
    assert all(b > a for a, b in zip(rot, rot[1:]))
    # the tire only rises once the wedge has (almost) crossed the whole patch
    for g in _gs():
        if hs.lift_at(g) > 0.01:
            assert hs.contact_at(g) < 0.05


def test_lift_stays_at_water_film_scale_not_a_floating_wheel():
    # The rejected 3D version floated the wheel ~a radius above the water.
    assert hs.lift_at(1.0) <= 1.5 * hs.FILM
    assert hs.lift_at(1.0) < 0.05 * hs.TIRE_R


def test_frames_have_box_size_and_states_differ_visibly():
    a = np.asarray(hs.render_frame(0.1, labels=False), float)
    b = np.asarray(hs.render_frame(0.75, labels=False), float)
    assert a.shape == (hs.H, hs.W, 3)
    inset = slice(hs.INSET_BOX[1], hs.INSET_BOX[3])
    assert np.abs(a[inset] - b[inset]).mean() > 3.0


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg required")
def test_render_clip_encodes_h264(tmp_path):
    out = hs.render_clip(tmp_path / "c.mp4", 0.5, 0.52, duration=0.2, fps=10, labels=False)
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=codec_name,width,height", "-of", "csv=p=0", str(out)],
                           capture_output=True, text=True, check=True).stdout.strip()
    assert probe == f"h264,{hs.W},{hs.H}"


def _build_module():
    spec = importlib.util.spec_from_file_location("build_hydroplaning_states", ROOT / "scripts/build_hydroplaning_states.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_hydroplaning_prompt_v2_produces_a_hook_under_the_unchanged_judge():
    # Regression for CI: "Prompt V2 produced no hydroplaning hook" -- every
    # candidate was a flat hedge with no tension marker.
    mod = _build_module()
    result = generate_and_judge(mod.make_brief(), generator=mod.HydroplaningHookGenerator())
    assert result.winner is not None
    assert hook_violation(result.winner.text) is None
    assert len(result.survivors) >= 3


def test_section_windows_abut_and_every_real_clip_is_distinct():
    mod = _build_module()
    windows = sorted(v[:2] for v in mod.SECTION_CLIPS.values())
    for (a0, a1), (b0, b1) in zip(windows, windows[1:]):
        assert a0 < a1 <= b0 < b1
        assert b0 - a1 < 0.03
    clips = list(mod.REAL_CLIPS.values())
    names = [c[1] for c in clips]
    moments = [(c[0], c[2]) for c in clips]
    assert len(set(names)) == len(names) and len(set(moments)) == len(moments)
    assert all(c[0] in mod.REAL_SOURCES for c in clips)
    # two moments of one source are never back-to-back beats
    order = ["spray", "surface", "tire", "rain_tire", "fast_wheel", "pov"]
    assert sorted(order) == sorted(mod.REAL_CLIPS)
    for a, b in zip(order, order[1:]):
        assert mod.REAL_CLIPS[a][0] != mod.REAL_CLIPS[b][0]
