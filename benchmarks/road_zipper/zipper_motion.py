"""EP.17 moveable barrier (pure Python + numpy). Render-world coordinates: the highway runs along y, three lanes each way, 12 ft
(3.66 m) lanes; the concrete median wall stands on x = 0. A barrier transfer machine (the "zipper") drives along the wall at 5 mph;
under its open frame an S-shaped conveyor of wheel pairs grips the T-shaped top of each block, lifts the pinned chain and sets it down
one lane over (x = SHIFT), so the southbound side (x < 0) gains a lane. Blocks are 1 m long and pinned end to end.

Explanation model, simplified: block positions follow the conveyor's S curve as the machine passes; the extra length of the S is not
modelled (real systems absorb it in the chain); the block profile is a generic jersey-type base with a T head, sized so a block
weighs about 1,500 lb."""
from __future__ import annotations

import math

import numpy as np

MPH = 0.44704
FT = 0.3048
LB = 0.45359237
LANE = 12 * FT
SHIFT = LANE                          # one lane, twelve feet
VM = 5 * MPH                          # machine speed
LT = 16.0                             # length of the S conveyor (machine frame)
LIFT = 0.16                           # how high the chain is lifted inside the machine
BLOCK_L = 1.0
GAP = 0.02
DENSITY = 2400.0                      # concrete, kg/m3
# block cross-section (x, z), counter-clockwise: jersey base, neck, T head
PROFILE = [(-0.305, 0.0), (0.305, 0.0), (0.305, 0.08), (0.10, 0.55), (0.075, 0.62), (0.15, 0.62), (0.15, 0.81),
           (-0.15, 0.81), (-0.15, 0.62), (-0.075, 0.62), (-0.10, 0.55), (-0.305, 0.08)]
T_TOP_Z = 0.62                        # underside of the T head: where the conveyor wheels grip
BLOCK_Y = np.arange(-160, 200) * BLOCK_L     # centre of each block along y (index * length)
LANES_S = (-1.83, -5.49, -9.15)       # southbound lane centres (traffic toward -y)
LANES_N = (1.83, 5.49, 9.15)          # northbound (toward +y)
MACHINE_HALF_W = SHIFT / 2 + 0.37     # side beams of the open frame, about x = SHIFT / 2 (just clear of the wall on both lines)
MACHINE_WHEEL_X = (SHIFT / 2 - 2.3, SHIFT / 2 + 2.3)
CAR_HALF_W = 0.85


def profile_area() -> float:
    p = np.array(PROFILE)
    x, z = p[:, 0], p[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(z, -1)) - np.dot(z, np.roll(x, -1)))


def block_mass_kg() -> float:
    return DENSITY * profile_area() * (BLOCK_L - GAP)


def _s(u):
    u = np.clip(u, 0.0, 1.0)
    return u * u * (3 - 2 * u)


def _ds(u):
    u = np.clip(u, 0.0, 1.0)
    return 6 * u * (1 - u)


def machine_y(t: float) -> float:
    """Machine centre along y at simulated time t (s)."""
    return VM * t


def blocks(t: float, variant: str = "day") -> dict:
    """Block centres, yaw and lift at time t. day: the machine moves the wall from x = 0 to x = SHIFT; night: back again;
    morning: the wall stands one lane over and the machine is gone."""
    y = BLOCK_Y.copy()
    if variant == "morning":
        return {"x": np.full_like(y, SHIFT), "y": y, "z": np.zeros_like(y), "yaw": np.zeros_like(y), "u": np.ones_like(y)}
    ym = machine_y(t)
    u = (ym + LT / 2 - y) / LT                     # 0 at the machine's front, 1 at its rear
    s, ds = _s(u), _ds(u)
    if variant == "night":
        x, slope = SHIFT * (1 - s), SHIFT * ds / LT
    else:
        x, slope = SHIFT * s, -SHIFT * ds / LT
    inside = (u > 0) & (u < 1)
    z = np.where(inside, LIFT * np.sin(np.pi * np.clip(u, 0, 1)), 0.0)
    yaw = -np.arctan(slope)                        # rotation about z turns +y toward -x; slope = dx/dy
    return {"x": x, "y": y, "z": z, "yaw": yaw, "u": np.clip(u, 0, 1)}


def pin_gaps(t: float, variant: str = "day") -> np.ndarray:
    """Distance between the rear pin of each block and the front pin of the next (the chain stays locked if these stay small)."""
    b = blocks(t, variant)
    h = (BLOCK_L - GAP) / 2
    fx, fy = b["x"] - np.sin(b["yaw"]) * h, b["y"] + np.cos(b["yaw"]) * h
    rx, ry = b["x"] + np.sin(b["yaw"]) * h, b["y"] - np.cos(b["yaw"]) * h
    return np.hypot(fx[:-1] - rx[1:], fy[:-1] - ry[1:])


TRAFFIC = [  # (lane x, direction, y0, speed m/s, colour)
    (-5.49, -1, 30.0, 23.0, (0.08, 0.30, 0.95)), (-9.15, -1, -25.0, 25.0, (0.85, 0.85, 0.82)), (-5.49, -1, -70.0, 23.0, (0.10, 0.10, 0.11)),
    (5.49, 1, -10.0, 22.0, (0.95, 0.75, 0.10)), (9.15, 1, 45.0, 26.0, (0.20, 0.45, 0.25)), (9.15, 1, -60.0, 26.0, (0.55, 0.56, 0.60)),
]
MORNING_EXTRA = [(1.83, -1, 10.0, 21.0, (0.70, 0.12, 0.12)), (-1.83, -1, -40.0, 22.0, (0.85, 0.85, 0.82)), (1.83, -1, -80.0, 21.0, (0.10, 0.30, 0.70))]
WRAP = 220.0


def traffic(t: float, variant: str = "day") -> list[tuple[float, float, int]]:
    """(x, y, direction) of each traffic car, wrapped around the machine so the road always has traffic."""
    ym = machine_y(t) if variant != "morning" else 0.0
    cars = TRAFFIC + (MORNING_EXTRA if variant == "morning" else [])
    out = []
    for x, d, y0, v, _ in cars:
        y = ym + ((y0 + d * v * t + WRAP / 2) % WRAP) - WRAP / 2
        out.append((x, y, d))
    return out


def zipper_physics() -> dict:
    problems = []
    lb = block_mass_kg() / LB
    if not 1350 <= lb <= 1650:
        problems.append(f"a block weighs {lb:.0f} lb (narration: about fifteen hundred pounds)")
    if abs(SHIFT / FT - 12) > 1e-6 or abs(LANE - SHIFT) > 1e-9:
        problems.append("the wall does not move one twelve-foot lane")
    worst = 0.0
    for variant in ("day", "night"):
        for t in np.arange(-6.0, 34.0, 0.25):
            worst = max(worst, float(pin_gaps(float(t), variant).max()))
    if worst > 0.12:
        problems.append(f"the chain opens by {worst:.2f} m between blocks (narration: still locked together)")
    b = blocks(10.0)
    ym = machine_y(10.0)
    ahead, behind = b["y"] > ym + LT / 2 + 0.5, b["y"] < ym - LT / 2 - 0.5
    if np.abs(b["x"][ahead]).max() > 1e-9 or np.abs(b["x"][behind] - SHIFT).max() > 1e-9 or b["z"][ahead | behind].max() > 0:
        problems.append("blocks outside the machine are not on the ground on their old / new line")
    if b["z"].max() < 0.1:
        problems.append("the chain is not lifted inside the machine")
    lanes_ok = all(abs(x) - CAR_HALF_W > 0.3 + 0.305 and not (MACHINE_WHEEL_X[0] - 0.5 < x + CAR_HALF_W and x - CAR_HALF_W < MACHINE_WHEEL_X[1] + 0.5)
                   for x, *_ in TRAFFIC)
    if not lanes_ok:
        problems.append("a traffic lane runs into the wall or the machine")
    if any(x + CAR_HALF_W > SHIFT - 0.305 - 0.2 for x, *_ in MORNING_EXTRA):
        problems.append("the morning's extra lane is not clear of the moved wall")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "block_lb": round(lb), "block_kg": round(block_mass_kg()),
            "shift_ft": round(SHIFT / FT, 2), "max_pin_gap_m": round(worst, 3), "machine_mph": VM / MPH}


if __name__ == "__main__":
    import json
    print(json.dumps(zipper_physics(), indent=1))
