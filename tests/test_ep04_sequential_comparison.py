"""Sequential full-screen EP04 comparison: no Blender or preview required."""
import unittest
from benchmarks.crumple_zone import crumple_motion as cm

class SequentialComparisonTests(unittest.TestCase):
    def test_no_split_screen_in_timeline(self):
        self.assertTrue(all(s["layout"] != "stack" for s in cm.SEGMENTS))
    def test_exactly_one_visible_car_per_frame(self):
        for f in range(1, cm.TOTAL_FRAMES + 1):
            self.assertEqual(len(cm.visible_panels(f)), 1)
    def test_crumple_then_rigid(self):
        for name in ("C", "C2", "C3"):
            seg = next(s for s in cm.SEGMENTS if s["id"] == name)
            mid = (seg["first"] + seg["last"] + 1) // 2
            self.assertEqual(cm.visible_panel(seg["first"]), "crumple")
            self.assertEqual(cm.visible_panel(mid), "rigid")
            self.assertEqual(cm.visible_panel(seg["last"]), "rigid")
    def test_same_camera_for_comparison(self):
        for name in ("C", "C2", "C3"):
            seg = next(s for s in cm.SEGMENTS if s["id"] == name)
            self.assertEqual(seg["camera"], "compare")
    def test_no_frame_count_change(self):
        self.assertEqual(cm.TOTAL_FRAMES, 780)
        self.assertEqual(sum(s["last"]-s["first"]+1 for s in cm.SEGMENTS), 780)
    def test_simulation_restarts_for_second_car(self):
        for name in ("C", "C2", "C3"):
            seg = next(s for s in cm.SEGMENTS if s["id"] == name)
            mid = (seg["first"] + seg["last"] + 1) // 2
            self.assertLess(cm.frame_time(mid), cm.frame_time(mid-1))
if __name__ == "__main__":
    unittest.main()
