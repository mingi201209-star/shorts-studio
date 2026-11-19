"""Content gates for the breakaway sign post episode. Narration match, first
three seconds and caption safety are the generic telemetry gates in
jersey_barrier_gates.py (unchanged); only motion plausibility is specific."""
from __future__ import annotations

from benchmarks.road_safety.jersey_barrier_gates import (  # noqa: F401  (re-exported)
    caption_safety,
    first_three_seconds,
    narration_screen_match,
    spoken_windows,
)


def motion_plausibility(summaries: dict) -> dict:
    """The film's claims have to hold in the simulated numbers:
    'only one of them stops', 'lets go', 'up and over the roof', 'lands behind
    the car', 'strong against wind, not against a car', 'under a meter',
    'almost none'. The speed-change limits are the ones used for breakaway
    supports as recalled, not re-read from the source: a plausibility check,
    not a certification."""
    b, r = summaries["breakaway"], summaries["rigid"]
    problems = []

    def need(ok: bool, text: str) -> None:
        if not ok:
            problems.append(text)

    need(0.1 <= b["delta_v_mps"] <= 3.0, f"breakaway speed change {b['delta_v_mps']} m/s outside 0.1-3.0")
    need(b["speed_kept_fraction"] >= 0.95, "breakaway car keeps less than 95% of its speed ('almost none')")
    need(abs(b["struck_point_speed_mps"] - b["speed_after_mps"]) <= 0.03 * b["speed_after_mps"] + 0.3,
         "struck point of the post does not leave at the car's speed")
    need(abs(b["angular_momentum_residual"]) < 1e-3, "angular momentum about the struck point is not conserved")
    need(b["min_clearance_m"] >= 0.10, f"post clears the car by only {b['min_clearance_m']} m ('up and over the roof')")
    need(b["post_landed"] and b["post_landing_y_m"] < b["car_tail_at_landing_m"], "post does not land behind the car")
    need(b["wind_shear_N"] < 0.5 * b["slip_force_N"], "slip base would let go in the design wind")
    need(b["slip_force_N"] < 0.5 * b["mean_impact_force_N"], "impact would not release the slip base")
    need(0.6 <= r["stop_distance_m"] <= 1.0, f"fixed-post stop distance {r['stop_distance_m']} m outside 0.6-1.0 ('under a meter')")
    need(20.0 <= r["avg_decel_g"] <= 60.0, f"fixed-post deceleration {r['avg_decel_g']} g outside 20-60")
    need(r["delta_v_mps"] >= 0.95 * 25.0, "fixed post does not take (nearly) all of the car's speed")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "summaries": summaries}


def readout_audit(telemetry: dict[int, dict], summaries: dict) -> dict:
    """The speed numbers drawn on screen are the simulation's numbers.
    Every frame that shows the read-out records the integers it drew next to
    the simulated speeds of that frame; they must agree exactly, the fixed
    lane must reach 0 and the breakaway lane must end at the speed the
    simulation says it keeps. (The pixels themselves are not read back; the
    drawn text is built from the same values.)"""
    shown = [r for r in telemetry.values() if r.get("hud_kmh")]
    problems = []
    if len(shown) < 300:
        problems.append(f"read-out shown on only {len(shown)} frames")
    for r in shown:
        for lane, key in (("rigid", "rigid_speed_mps"), ("breakaway", "breakaway_speed_mps")):
            expected = int(f"{r[key] * 3.6:.0f}")
            if r["hud_kmh"][lane] != expected:
                problems.append(f"frame {r['frame']}: {lane} shows {r['hud_kmh'][lane]} km/h, simulation says {expected}")
                break
        if len(problems) > 5:
            break
    if shown:
        floor_breakaway = int(f"{summaries['breakaway']['speed_after_mps'] * 3.6:.0f}")
        if min(r["hud_kmh"]["rigid"] for r in shown) != 0:
            problems.append("the fixed lane's read-out never reaches 0 km/h")
        if min(r["hud_kmh"]["breakaway"] for r in shown) != floor_breakaway:
            problems.append(f"the breakaway lane's read-out does not end at {floor_breakaway} km/h")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "frames_with_readout": len(shown)}
