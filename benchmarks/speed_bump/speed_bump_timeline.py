"""EP.03: pure-Python timeline helpers shared by the renderer and the gates: pass ranges, peak times, peak numbers.
All numbers come from the same simulation that poses the cars (with the car's measured wheelbase)."""
from __future__ import annotations

import numpy as np

from benchmarks.speed_bump import speed_bump_motion as sim


class Timeline:
    def __init__(self, wheelbase: float, hz: int = sim.FPS):
        self.hz = hz
        self.car = dict(sim.CAR, wheelbase=wheelbase)
        self.recs = {(s["id"], k): sim.simulate(b, speed_kmh=s["kmh"], car=self.car, hz=hz) for s in sim.SEGMENTS for k, b in sim.BUMPS.items()}
        self.peaks = sim.pass_summaries(self.car)
        self.range, self.peak_time = {}, {}
        start = 1
        for s in sim.SEGMENTS:
            _, t0 = sim.frame_to_pass(start)
            _, t1 = sim.frame_to_pass(start + s["frames"] - 1)
            self.range[s["id"]] = (t0, t1)
            for k in sim.BUMPS:
                g = np.abs(self.recs[(s["id"], k)]["gf"])
                self.peak_time[(s["id"], k)] = float(self.recs[(s["id"], k)]["t"][int(np.argmax(g))])
            start += s["frames"]

    def body_cm(self, seg_id: str, bump: str, t: float) -> float:
        r = self.recs[(seg_id, bump)]
        return 100.0 * float(np.interp(t, r["t"], r["body"]))
