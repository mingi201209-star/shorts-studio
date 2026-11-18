"""EP.04 driver (crash-test-dummy style figure): the occupant model must separate the two crashes for physical reasons and the figure must be tied to the simulated pulses."""
import unittest

from benchmarks.crumple_zone import crumple_motion as cm
from benchmarks.crumple_zone import dummy_motion as dm


class DriverTests(unittest.TestCase):
    def test_slow_stop_is_survivable_and_abrupt_stop_is_not(self):
        soft, hard = dm.response("crumple"), dm.response("rigid")
        self.assertLess(soft["chest_g"].max(), dm.CHEST_OK_G + 5)
        self.assertGreaterEqual(hard["chest_g"].max(), dm.CHEST_SEVERE_G - 5)
        self.assertLess(soft["r"].max(), dm.REACH)          # the first car's driver never reaches the steering wheel
        self.assertGreater(hard["r"].max(), dm.REACH)       # the rigid car's driver does
        self.assertGreater(hard["chest_g"].max(), 2 * soft["chest_g"].max() * 0.9)

    def test_injury_level_is_a_running_peak_in_0_to_1(self):
        res = dm.response("rigid")
        levels = [dm.at("rigid", float(t))["injury"] for t in res["t"][:: max(1, len(res["t"]) // 200)]]
        self.assertTrue(all(0.0 <= v <= 1.0 for v in levels))
        self.assertTrue(all(b >= a - 1e-9 for a, b in zip(levels, levels[1:])))      # once hurt the colour does not go back
        self.assertGreaterEqual(levels[-1], 0.9)
        self.assertLessEqual(dm.at("crumple", float(dm.response("crumple")["t"][-1]))["injury"], 0.1)

    def test_driver_lunge_is_slow_enough_to_be_seen_in_the_film(self):
        """The rigid driver's lunge takes about 35 ms of simulated time: it must be spread over at least 0.25 s of film (8 frames)."""
        seg = cm.SEGMENTS[1]
        frames = [f for f in range(seg["first"], seg["last"] + 1) if 0.05 < dm.at("rigid", cm.frame_time(f))["travel_m"] < 0.23]
        self.assertGreaterEqual(len(frames), 8)

    def test_cabin_turns_see_through_after_the_front(self):
        k = cm.SEGMENTS[0]
        first_front = next(f for f in range(k["first"], k["last"] + 1) if cm.xray_factor(f) > 0.02)
        first_cabin = next(f for f in range(k["first"], k["last"] + 1) if cm.cabin_xray_factor(f) > 0.02)
        self.assertLess(first_front, first_cabin)
