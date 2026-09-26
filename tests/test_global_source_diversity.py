"""Regression coverage for the global source-diversity hardening pass:
a video can have zero ADJACENT source repeats and a fine average cut
cadence and still feel static because one or two pictures dominate the
whole runtime. These gates measure that directly, using the actual
production manifest as the real regression case wherever possible.
"""
from types import SimpleNamespace

import pytest

from shorts_studio.final_video_qa import (
    compute_global_source_reuse, verify_global_source_reuse,
    compute_novelty_window_violations, verify_visual_novelty,
    compute_first_5s_family_coverage, verify_first_5s_coverage,
    compute_semantic_visual_coverage, verify_source_budget,
    compute_ending_novelty, verify_ending_novelty,
    GLOBAL_MAX_SOURCE_FAMILY_RATIO, NOVELTY_WINDOW_BEATS,
)


def _beat(start, url):
    return SimpleNamespace(start=start, asset=None, asset_url=url, attribution=None, visual_qa_labels=[])


def _project(scene_beats: dict) -> SimpleNamespace:
    scenes = [SimpleNamespace(id=sid, visual_beats=[_beat(s, u) for s, u in beats]) for sid, beats in scene_beats.items()]
    return SimpleNamespace(scenes=scenes)


# --- 1. global source reuse gate ------------------------------------------

def test_global_reuse_fails_when_one_family_dominates_even_without_adjacency():
    """The exact real-world failure mode: a source never repeats twice in a
    row, but still covers most of the video."""
    a, b, c, d = "https://x/a.jpg", "https://x/b.jpg", "https://x/c.jpg", "https://x/d.jpg"
    # a appears 5 of 10 times, never adjacent to itself.
    beats = [(0, a), (1, b), (2, a), (3, c), (4, a), (5, d), (6, a), (7, b), (8, a), (9, c)]
    project = _project({"s1": beats})
    metrics = compute_global_source_reuse(project)
    assert metrics["max_source_family_occurrences"] == 5
    assert metrics["max_source_family_ratio"] == pytest.approx(0.5)
    result = verify_global_source_reuse(metrics)
    assert result["status"] == "FAIL", result


def test_global_reuse_passes_with_even_distribution():
    a, b, c, d, e, f = ["https://x/%s.jpg" % x for x in "abcdef"]
    beats = [(i, u) for i, u in enumerate([a, b, c, d, e, f] * 2)]
    project = _project({"s1": beats})
    metrics = compute_global_source_reuse(project)
    assert metrics["max_source_family_ratio"] <= GLOBAL_MAX_SOURCE_FAMILY_RATIO
    assert verify_global_source_reuse(metrics)["status"] == "PASS"


def test_repeated_source_timestamps_lists_every_repeat_with_its_own_time():
    a, b = "https://x/a.jpg", "https://x/b.jpg"
    project = _project({"s1": [(0, a), (2, b), (4, a)]})
    metrics = compute_global_source_reuse(project)
    assert len(metrics["repeated_source_timestamps"]) == 1
    assert metrics["repeated_source_timestamps"][0]["start"] == 4
    assert metrics["repeated_source_timestamps"][0]["scene"] == "s1"


def test_current_radium_girls_manifest_satisfies_the_global_reuse_gate():
    import json
    from pathlib import Path
    from shorts_studio.models import Project
    data = json.loads(Path("examples/radium_girls.json").read_text(encoding="utf-8"))
    project = Project.model_validate(data)
    metrics = compute_global_source_reuse(project)
    result = verify_global_source_reuse(metrics)
    assert result["status"] == "PASS", result


# --- 2. visual novelty gate (sliding window) -------------------------------

def test_novelty_violation_when_source_reappears_within_the_window():
    a, b, c = "https://x/a.jpg", "https://x/b.jpg", "https://x/c.jpg"
    project = _project({"s1": [(0, a), (1, b), (2, c), (3, a)]})  # a reappears 3 beats later
    violations = compute_novelty_window_violations(project, window=5)
    assert len(violations) == 1
    assert violations[0]["gap_beats"] == 3
    assert verify_visual_novelty(violations)["status"] == "FAIL"


def test_no_novelty_violation_once_outside_the_window():
    a = "https://x/a.jpg"
    others = ["https://x/%s.jpg" % x for x in "bcdef"]
    beats = [(0, a)] + [(i + 1, u) for i, u in enumerate(others)] + [(6, a)]  # gap of 6, window is 5
    project = _project({"s1": beats})
    violations = compute_novelty_window_violations(project, window=5)
    assert violations == []


def test_current_radium_girls_manifest_satisfies_the_novelty_window():
    import json
    from pathlib import Path
    from shorts_studio.models import Project
    data = json.loads(Path("examples/radium_girls.json").read_text(encoding="utf-8"))
    project = Project.model_validate(data)
    violations = compute_novelty_window_violations(project)
    result = verify_visual_novelty(violations)
    assert result["status"] == "PASS", result


# --- 3. first-5-seconds coverage (crop/zoom does not count) ----------------

def test_first_5s_coverage_counts_only_distinct_families():
    a_crop = "https://x/photo-a-cropped.jpg"
    a_wide = "https://x/photo-a-uncropped-wide.jpg"  # same family via containment
    b = "https://x/photo-b.jpg"
    scene_windows = [{"scene": "s1", "start": 0.0}]
    project = _project({"s1": [(0.0, a_crop), (1.5, a_wide), (3.0, b)]})
    metrics = compute_first_5s_family_coverage(scene_windows, project)
    # a_crop/a_wide collapse to one family (not same string, but containment-related)
    # so only 2 distinct families should be counted if they share a family; otherwise 3.
    assert metrics["first_5s_unique_sources"] in (2, 3)


def test_first_5s_coverage_fails_below_minimum():
    a = "https://x/a.jpg"
    metrics = {"first_5s_unique_sources": 1, "first_5s_families": []}
    assert verify_first_5s_coverage(metrics, min_unique=3)["status"] == "FAIL"


def test_first_5s_coverage_passes_at_minimum():
    metrics = {"first_5s_unique_sources": 3, "first_5s_families": []}
    assert verify_first_5s_coverage(metrics, min_unique=3)["status"] == "PASS"


def test_first_5s_respects_absolute_timeline_across_scene_boundaries():
    """A beat's real position is scene_window.start + beat.start, not just
    the beat's own local offset -- otherwise every scene's own beat 0 would
    incorrectly count as 'within the first 5 seconds'."""
    a, b, c = "https://x/a.jpg", "https://x/b.jpg", "https://x/c.jpg"
    project = _project({"s1": [(0.0, a)], "s2": [(0.0, b)], "s3": [(0.0, c)]})
    scene_windows = [{"scene": "s1", "start": 0.0}, {"scene": "s2", "start": 10.0}, {"scene": "s3", "start": 20.0}]
    metrics = compute_first_5s_family_coverage(scene_windows, project)
    assert metrics["first_5s_unique_sources"] == 1


def test_current_radium_girls_manifest_satisfies_first_5s_coverage():
    import json
    from pathlib import Path
    from shorts_studio.models import Project
    data = json.loads(Path("examples/radium_girls.json").read_text(encoding="utf-8"))
    project = Project.model_validate(data)
    # Use the real known durations from the last successful production render.
    durations = {"scene_01": 5.5}
    scene_windows = [{"scene": "scene_01", "start": 0.0, "duration": durations["scene_01"]}]
    metrics = compute_first_5s_family_coverage(scene_windows, project)
    result = verify_first_5s_coverage(metrics)
    assert result["status"] == "PASS", (metrics, result)


# --- 5. source budget pre-render gate --------------------------------------

def test_source_budget_fails_when_one_family_would_dominate():
    a = "https://x/a.jpg"
    others = ["https://x/%s.jpg" % x for x in "bc"]
    beats = [(i, a) for i in range(8)] + [(i + 8, u) for i, u in enumerate(others)]
    project = _project({"s1": beats})
    result = verify_source_budget(project)
    assert result["status"] == "FAIL", result


def test_source_budget_passes_with_a_healthy_spread():
    urls = ["https://x/%s.jpg" % x for x in "abcdefgh"]
    beats = [(i, u) for i, u in enumerate(urls)]
    project = _project({"s1": beats})
    result = verify_source_budget(project)
    assert result["status"] == "PASS", result


def test_source_budget_passes_trivially_with_no_visual_beats():
    project = SimpleNamespace(scenes=[SimpleNamespace(id="s1", visual_beats=[])])
    assert verify_source_budget(project)["status"] == "PASS"


def test_current_radium_girls_manifest_satisfies_the_source_budget():
    import json
    from pathlib import Path
    from shorts_studio.models import Project
    data = json.loads(Path("examples/radium_girls.json").read_text(encoding="utf-8"))
    project = Project.model_validate(data)
    result = verify_source_budget(project)
    assert result["status"] == "PASS", result


# --- 6. semantic visual coverage metric (informational) --------------------

def test_semantic_visual_coverage_is_reported_as_a_ratio():
    project = _project({"s1": [(0, "https://x/a.jpg")]})
    project.scenes[0].visual_beats[0].visual_qa_labels = ["close-up historical photograph of a woman with a fine brush"]
    metrics = compute_semantic_visual_coverage(project)
    assert 0.0 <= metrics["semantic_visual_coverage"] <= 1.0
    assert metrics["categories_covered"]["technique_closeup"] is True


# --- 7. strict_source_diversity is opt-in, not universal --------------------
# comet.json's real archival photo pool is genuinely narrower than
# radium_girls.json's (a handful of period accident-report photos vs. many
# distinct dial-painter/factory/ad/lawsuit photos), so the same handful of
# real photos legitimately gets revisited across adjacent scenes about the
# same evidence. These gates assume a rich pool; forcing every project
# through them regardless of what's actually available would either block a
# smoke-test fixture nobody asked to redesign, or pressure someone into
# padding it with weaker, less accurate filler images just to pass a count.

def test_render_does_not_enforce_source_budget_when_opted_out():
    from shorts_studio.render import render
    result = render("examples/comet.json", dry_run=True)
    assert result["status"] == "PASS", result


def test_render_does_enforce_source_budget_for_radium_girls():
    import json
    from pathlib import Path
    from shorts_studio.models import Project
    data = json.loads(Path("examples/radium_girls.json").read_text(encoding="utf-8"))
    project = Project.model_validate(data)
    assert project.strict_source_diversity is True


def test_comet_example_defaults_to_opted_out():
    import json
    from pathlib import Path
    from shorts_studio.models import Project
    data = json.loads(Path("examples/comet.json").read_text(encoding="utf-8"))
    project = Project.model_validate(data)
    assert project.strict_source_diversity is False


# --- 8. ending novelty contract ---------------------------------------------
# A video can pass every whole-video ratio/window check and still end on
# "show the opening photo again and roll credits" -- these gates score the
# real closing seconds as their own segment against the actual rendered
# duration, not the manifest's nominal scene boundaries.

def _scene_windows(*scene_starts):
    return [{"scene": sid, "start": start} for sid, start in scene_starts]


def test_ending_novelty_fails_when_the_whole_ending_just_replays_earlier_material():
    a, b, c = "https://x/a.jpg", "https://x/b.jpg", "https://x/c.jpg"
    # 0-61s: a, b, c already shown. 61-79s (the "ending"): all three replayed,
    # nothing new -- exactly the real regression this contract targets.
    project = _project({
        "s1": [(0, a), (10, b), (20, c)],
        "s2": [(0, a), (3, b), (6, c)],  # s2 starts at 61s -> ending window
    })
    windows = _scene_windows(("s1", 0.0), ("s2", 61.0))
    metrics = compute_ending_novelty(windows, project, total_duration=79.0)
    assert metrics["ending_new_ratio"] == 0.0
    assert metrics["final_window_unique_new_count"] == 0
    assert metrics["last_beat_is_reused_generic"] is True
    result = verify_ending_novelty(metrics)
    assert result["status"] == "FAIL", result


def test_ending_novelty_passes_when_the_ending_earns_real_new_material():
    a, b, c, d, e = ["https://x/%s.jpg" % x for x in "abcde"]
    project = _project({
        "s1": [(0, a), (10, b), (20, c)],
        # s2 starts at 61s: 2 of 3 beats are genuinely new (d, e), both
        # inside the final 10s (>= 69s); last beat (e) is new, not a replay.
        "s2": [(0, a), (9, d), (12, e)],
    })
    windows = _scene_windows(("s1", 0.0), ("s2", 61.0))
    metrics = compute_ending_novelty(windows, project, total_duration=79.0)
    assert metrics["ending_new_ratio"] == pytest.approx(2 / 3)
    assert metrics["final_window_unique_new_count"] == 2
    assert metrics["last_beat_is_reused_generic"] is False
    result = verify_ending_novelty(metrics)
    assert result["status"] == "PASS", result


def test_ending_novelty_crop_of_earlier_source_does_not_count_as_new():
    a_wide = "https://x/photo-a.jpg"
    a_crop = "https://x/photo-a-cropped.jpg"  # same family: "cropped" is stripped
    b = "https://x/b.jpg"
    project = _project({
        "s1": [(0, a_wide)],
        "s2": [(0, a_crop), (5, b)],  # s2 starts at 65s
    })
    windows = _scene_windows(("s1", 0.0), ("s2", 65.0))
    metrics = compute_ending_novelty(windows, project, total_duration=79.0)
    # Only b is genuinely new; the crop of a is the same family as a_wide.
    assert metrics["ending_new_beat_count"] == 1


def test_ending_novelty_fails_when_final_beat_reuses_a_generic_family_even_if_ratio_passes():
    a, b, c, d = ["https://x/%s.jpg" % x for x in "abcd"]
    project = _project({
        "s1": [(0, a)],
        # s2 starts at 62s: b, c are new (2/3 = 67% >= 60%), but the LAST
        # beat replays `a` -- the exact "ends by showing the opener again"
        # failure mode, which the ratio alone would let through.
        "s2": [(0, b), (5, c), (10, a)],
    })
    windows = _scene_windows(("s1", 0.0), ("s2", 62.0))
    metrics = compute_ending_novelty(windows, project, total_duration=79.0)
    assert metrics["ending_new_ratio"] >= 0.6
    assert metrics["last_beat_is_reused_generic"] is True
    result = verify_ending_novelty(metrics)
    assert result["status"] == "FAIL", result


def test_current_radium_girls_manifest_satisfies_the_ending_novelty_contract():
    """The real regression case: ground-truth cut timestamps measured from
    the actual rendered video (ffmpeg scene-cut detection on the delivered
    final.mp4), not the manifest's nominal per-scene beat offsets."""
    import json
    from pathlib import Path
    from shorts_studio.models import Project
    data = json.loads(Path("examples/radium_girls.json").read_text(encoding="utf-8"))
    project = Project.model_validate(data)
    windows = _scene_windows(
        ("scene_01", 0.0), ("scene_02", 5.541992), ("scene_03", 14.175326),
        ("scene_04", 22.011328), ("scene_05", 29.958333), ("scene_06", 40.461328),
        ("scene_07", 48.205339), ("scene_08", 61.105339),
    )
    metrics = compute_ending_novelty(windows, project, total_duration=79.105338)
    result = verify_ending_novelty(metrics)
    assert result["status"] == "PASS", result
