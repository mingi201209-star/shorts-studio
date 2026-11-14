import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.road_safety import cinematic_camera as cc

FPS = 30


def _approach():
    """Wide shot -> close on the wheel: a purposeful move toward a subject at the origin."""
    subject = lambda t: (0.0, 0.0, 0.5)
    keys = [cc.Key(0.0, (12.0, -14.0, 6.0), (0.0, 0.0, 0.5), 28.0),
            cc.Key(3.0, (4.0, -5.0, 2.0), None, 32.0),
            cc.Key(6.0, (1.6, -1.6, 0.7), None, 40.0)]
    return keys, subject


def test_plan_hits_the_key_poses_and_has_one_pose_per_frame():
    keys, subject = _approach()
    poses = cc.plan(keys, FPS, subject)
    assert len(poses) == 6 * FPS + 1
    for k in keys:
        p = min(poses, key=lambda q: abs(q.t - k.t))
        assert all(abs(a - b) < 1e-6 for a, b in zip(p.position, k.position))
    assert poses[0].lens == 28.0 and abs(poses[-1].lens - 40.0) < 1e-9


def test_plan_starts_and_ends_at_rest():
    keys, subject = _approach()
    poses = cc.plan(keys, FPS, subject)
    first = math.dist(poses[0].position, poses[1].position) * FPS
    last = math.dist(poses[-2].position, poses[-1].position) * FPS
    assert first < 0.5 and last < 0.5


def test_a_purposeful_approach_passes_the_audit():
    keys, subject = _approach()
    a = cc.audit(cc.plan(keys, FPS, subject), FPS, subject)
    assert a.status == "PASS", a.problems
    assert a.metrics["subject_visible_fraction"] > 0.95


def test_a_camera_that_stops_for_too_long_fails():
    keys = [cc.Key(0.0, (5.0, -5.0, 2.0), (0, 0, 0.5)), cc.Key(4.0, (5.0, -5.0, 2.0), (0, 0, 0.5))]
    a = cc.audit(cc.plan(keys, FPS), FPS)
    assert a.status == "FAIL" and any("holds still" in p for p in a.problems)


def test_a_jump_without_a_declared_cut_fails_and_a_declared_cut_passes():
    def path(cut):
        poses = cc.plan([cc.Key(0.0, (5.0, -5.0, 2.0), (0, 0, 0.5)), cc.Key(2.0, (6.0, -5.0, 2.0), (0, 0, 0.5))], FPS)
        for p in poses[len(poses) // 2:]:
            p.position = (p.position[0] + 30.0, p.position[1], p.position[2])
        if cut:
            poses[len(poses) // 2].cut = True
        return poses
    assert any("jumps" in p for p in cc.audit(path(False), FPS).problems)
    assert not any("jumps" in p for p in cc.audit(path(True), FPS).problems)


def test_flying_through_an_object_fails():
    keys = [cc.Key(0.0, (5.0, 0.0, 1.0), (0, 0, 1.0)), cc.Key(3.0, (-5.0, 0.0, 1.0), (0, 0, 1.0))]
    obstacle = cc.Sphere((0.0, 0.0, 1.0), 1.0, "truck")
    a = cc.audit(cc.plan(keys, FPS), FPS, obstacles=[obstacle])
    assert a.status == "FAIL" and any("obstacle" in p for p in a.problems)


def test_losing_the_subject_fails():
    subject = lambda t: (0.0, 0.0, 0.5)
    keys = [cc.Key(0.0, (8.0, -8.0, 2.0), (30.0, 30.0, 0.5)), cc.Key(3.0, (7.0, -7.0, 2.0), (30.0, 30.0, 0.5))]
    a = cc.audit(cc.plan(keys, FPS), FPS, subject)
    assert a.status == "FAIL" and any("subject" in p for p in a.problems)


def test_an_occluded_subject_counts_as_lost():
    subject = lambda t: (0.0, 0.0, 0.5)
    keys = [cc.Key(0.0, (8.0, 0.0, 0.5), subject(0)), cc.Key(3.0, (7.0, 0.0, 0.5), subject(0))]
    wall = cc.Sphere((4.0, 0.0, 0.5), 1.5, "wall")
    a = cc.audit(cc.plan(keys, FPS), FPS, subject, obstacles=[wall])
    assert a.metrics["subject_visible_fraction"] == 0.0


def test_a_whip_pan_fails_on_aim_rate():
    keys = [cc.Key(0.0, (5.0, -5.0, 2.0), (10.0, 0.0, 0.5)), cc.Key(0.4, (5.0, -5.0, 2.0), (-10.0, 0.0, 0.5)),
            cc.Key(2.0, (5.0, -5.0, 2.0), (-10.0, 0.0, 0.5))]
    a = cc.audit(cc.plan(keys, FPS), FPS)
    assert any("aim turns" in p for p in a.problems)


def test_projection_puts_the_aim_point_in_the_middle_of_the_frame():
    pose = cc.Pose(0.0, (0.0, -10.0, 1.0), (0.0, 0.0, 1.0), 32.0)
    x, row, depth = cc.project(pose, (0.0, 0.0, 1.0))
    assert abs(x - 0.5) < 1e-9 and abs(row - 960.0) < 1e-6 and abs(depth - 10.0) < 1e-9
    assert cc.project(pose, (0.0, -20.0, 1.0))[2] < 0           # behind the camera


def test_keys_must_increase_in_time_and_a_following_key_needs_a_subject():
    import pytest
    with pytest.raises(ValueError):
        cc.plan([cc.Key(1.0, (0, 0, 1), (0, 1, 1)), cc.Key(1.0, (0, 1, 1), (0, 2, 1))], FPS)
    with pytest.raises(ValueError):
        cc.plan([cc.Key(0.0, (0, 0, 1), None), cc.Key(1.0, (0, 1, 1), (0, 2, 1))], FPS)
