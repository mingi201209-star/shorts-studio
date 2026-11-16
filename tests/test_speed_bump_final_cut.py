import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks.speed_bump import speed_bump_motion as sim  # noqa: E402


def test_tyre_never_cuts_into_the_bump():
    r = sim.CAR["tyre_radius"]
    for bump in sim.BUMPS.values():
        for xc in np.linspace(-0.4, bump["length"] + 0.4, 200):
            hub = sim.hub_profile(float(xc), bump, r)
            for xr in np.linspace(max(0.0, xc - r), min(bump["length"], xc + r), 60):
                tyre_bottom = hub + r - math.sqrt(max(0.0, r * r - (xr - xc) ** 2))
                assert tyre_bottom >= sim.profile(float(xr), bump) - 2e-3     # 1 mm grid -> 2 mm tolerance


def test_single_speed_claims_hold_in_the_simulation():
    code = ("import sys; sys.path.insert(0, %r)\n"
            "from benchmarks.speed_bump import speed_bump_gates as g\n"
            "from benchmarks.speed_bump.speed_bump_timeline import Timeline\n"
            "from benchmarks.speed_bump import speed_bump_motion as m\n"
            "tl = Timeline(2.312, hz=m.RENDER_HZ)\n"
            "r = g.narration_numbers(tl.peaks)\n"
            "assert r['status'] == 'PASS', r\n"
            "assert m.PASS_FRAMES == 930 and sum(s['frames'] for s in m.SEGMENTS) == 930\n"
            "assert len({s['kmh'] for s in m.SEGMENTS}) == 1 and len({s['slow'] for s in m.SEGMENTS}) == 1\n"
            "prev = 0\n"
            "for a, b, k, l in m.SHOTS:\n"
            "    assert a == prev + 1 and b - a < 105; prev = b\n"
            "assert prev == 930\n"
            "print('ok')\n") % str(ROOT)
    out = subprocess.run([sys.executable, "-I", "-c", code], env=dict(os.environ, EP03_FILM="final"), capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert "ok" in out.stdout


def test_sync_gate_flags_a_late_event():
    code = ("import sys; sys.path.insert(0, %r)\n"
            "from benchmarks.speed_bump import speed_bump_gates as g\n"
            "from benchmarks.speed_bump import speed_bump_motion as m\n"
            "cues = [{'start': t / 30.0 + (1.0 if e == 'wheel path trail starts' else 0.0), 'end': 0, 'text': c} for c, e, t in [(c, e, f - 1) for c, e, f in m.SYNC_EVENTS]]\n"
            "r = g.picture_events_match_cues({'cues': cues})\n"
            "assert r['status'] == 'FAIL' and len(r['problems']) == 1, r\n"
            "print('ok')\n") % str(ROOT)
    out = subprocess.run([sys.executable, "-I", "-c", code], env=dict(os.environ, EP03_FILM="final"), capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
