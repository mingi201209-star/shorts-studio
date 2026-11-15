"""EP.03: pure-Python timeline helpers shared by the renderer (everything drawn is 3D) and the gates: pass ranges, peak times, banner texts, spotlight phases.
All numbers come from the same simulation that poses the cars (with the car's measured wheelbase)."""
from __future__ import annotations

import numpy as np

from benchmarks.speed_bump import speed_bump_motion as sim


class Timeline:
    def __init__(self, wheelbase: float):
        self.car = dict(sim.CAR, wheelbase=wheelbase)
        self.recs = {(s["id"], k): sim.simulate(b, speed_kmh=s["kmh"], car=self.car) for s in sim.SEGMENTS for k, b in sim.BUMPS.items()}
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

    def banners(self) -> list[tuple[int, int, str]]:
        """(first frame, last frame, text): plain statements about what is on screen then; numbers from the simulation."""
        rb = self.peaks["B"]["short"]["peak_body_g"] / self.peaks["B"]["hump"]["peak_body_g"]
        gc = self.peaks["C"]["hump"]["peak_body_g"]
        return [(1, 48, "SAME CAR. SAME SPEED."), (61, 110, "THE WHEELS JUMP FIRST"), (156, 205, "THEN THE BODY TILTS"),
                (321, 355, "NOW 30 km/h"), (400, 445, f"SHORT BUMP: {rb:.1f}x THE PEAK"),
                (481, 515, "NOW 10 km/h"), (565, 610, f"LONG HUMP: ONLY {gc:.2f} g")]

    def banner_at(self, frame: int) -> tuple[str, float] | None:
        """(text, opacity 0..1) of the banner on screen at this frame, with a 6-frame fade at both ends."""
        for a, b, text in self.banners():
            if a <= frame <= b:
                return text, min(frame - a + 1, b - frame + 1, 6) / 6.0
        return None

    @staticmethod
    def spotlight(n: int):
        """card frame n (1..320): index of the lit speed group (0=10, 1=20, 2=30 km/h) during frames 90-239, else None (all lit)."""
        return (n - 90) // 50 if 90 <= n < 240 else None

    def spotlight_text(self, n: int) -> str:
        lit = self.spotlight(n)
        if lit is None:
            return ""
        sid = ("C", "A", "B")[lit]
        kmh = {"A": 20, "B": 30, "C": 10}[sid]
        r = self.peaks[sid]["short"]["peak_body_g"] / self.peaks[sid]["hump"]["peak_body_g"]
        return f"{kmh} km/h: SHORT BUMP {r:.1f}x HARSHER"
