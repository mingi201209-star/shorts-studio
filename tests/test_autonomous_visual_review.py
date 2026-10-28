"""Unit judgments are synthetic; actual media evidence is retained separately on the server."""

import json

import pytest
from test_improvement_review import report, setup

from shorts_studio.improvement_review import assess
from shorts_studio.improvement_strategy import STRATEGIES, choose_strategy, qualitative_feedback
from shorts_studio.visual_review import CRITERIA, validate_judgment


def judgment():
    return {"binding": "bound", "a_scores": {k: 2 for k in CRITERIA},
            "b_scores": {k: 2 if k != "readability" else 3 for k in CRITERIA},
            "confidence": "high", "observations": [
                {"time": t, "criterion": "readability", "a": "Auxiliary labels are too small.",
                 "b": "Rivet labels and leader lines are readable.", "effect": "B_better"}
                for t in (36, 47)],
            "next_actions": ["Use an original location diagram for the opening."],
            "limitations": ["No listening or continuous playback."]}


def test_real_readability_gain_can_qualify_without_cut_metric_change(tmp_path):
    binding = setup(tmp_path, report())
    q = validate_judgment(judgment(), "bound", "B", [36, 47])
    q.update(video_sha256=binding["video_sha256"], comparison_video_sha256=binding["comparison_video_sha256"])
    result = assess(binding, visual_reviewer=lambda b: q)
    assert result["decision"] == "PASS"
    assert not result["regression"]
    assert json.loads(result["visual_notes"])["qualitative"]["audio_reviewed"] is False


@pytest.mark.parametrize("attack", ["binding", "time", "one_frame", "confidence", "regression", "contradiction", "tie", "short_evidence"])
def test_qualitative_evidence_cannot_game_acceptance(attack):
    data = judgment()
    if attack == "binding":
        data["binding"] = "another video"
    elif attack == "time":
        data["observations"][0]["time"] = 37
    elif attack == "one_frame":
        data["observations"][1]["time"] = 36
    elif attack == "confidence":
        data["confidence"] = "low"
    elif attack == "regression":
        data["b_scores"]["truthful_presentation"] = 1
    elif attack == "contradiction":
        data["observations"][1]["effect"] = "A_better"
    elif attack == "tie":
        data["b_scores"] = dict(data["a_scores"])
    else:
        data["observations"][0]["a"] = "ok"
    try:
        result = validate_judgment(data, "bound", "B", [36, 47])
        assert result["improved"] is False
    except ValueError:
        pass


def test_metric_regression_never_overridden_by_visual_claim(tmp_path):
    binding = setup(tmp_path, report(reuse=.9))
    def never_called(binding):
        raise AssertionError("regression must fail before subjective review")
    assert assess(binding, visual_reviewer=never_called)["decision"] == "HOLD"


def test_unavailable_or_forged_judge_holds_even_metric_gain(tmp_path):
    binding = setup(tmp_path, report(first=3))
    for reviewer in (lambda b: (_ for _ in ()).throw(ValueError("provider failed")),
                     lambda b: {"improved": True, "not_worse": True, "video_sha256": "forged"}):
        result = assess(binding, visual_reviewer=reviewer)
        assert result["decision"] == "HOLD"
        assert json.loads(result["visual_notes"])["qualitative"]["status"] == "unavailable"


def write_result(root, number, strategy, **overrides):
    path = root / f"attempt-{number:04}"
    path.mkdir()
    value = {"strategy_context": "context", "strategy_candidate": "video", "strategy_id": strategy,
             "state": "rejected", "failure": "editor produced no source changes"}
    value.update(overrides)
    (path / "result.json").write_text(json.dumps(value))


def test_two_actual_failures_change_concrete_strategy(tmp_path):
    first = choose_strategy(tmp_path, "context", "video")
    assert first["id"] == "mobile_readability"
    write_result(tmp_path, 1, first["id"])
    assert choose_strategy(tmp_path, "context", "video")["id"] == first["id"]
    write_result(tmp_path, 2, first["id"], failure="internal review rejected")
    new = choose_strategy(tmp_path, "context", "video")
    assert new["id"] == "causal_explanation"
    assert new["instruction"] != first["instruction"]
    assert (tmp_path / "attempt-0001/result.json").exists()


def test_exhausted_strategies_do_not_reset_or_relabel_inputs(tmp_path):
    for index, (key, _) in enumerate(STRATEGIES):
        for n in (0, 1):
            write_result(tmp_path, index * 2 + n + 1, key)
    result = choose_strategy(tmp_path, "context", "video")
    assert result["exhausted"] is True
    assert choose_strategy(tmp_path, "context", "video") == result
    assert choose_strategy(tmp_path, "context", "genuinely-new-video")["exhausted"] is False


def test_infrastructure_failure_is_not_a_failed_creative_strategy(tmp_path):
    for n in (1, 2):
        write_result(tmp_path, n, "mobile_readability", review_unavailable=True)
    route = choose_strategy(tmp_path, "context", "video")
    assert route["id"] == "mobile_readability" and route["defer"] is True


def test_visual_reasons_survive_one_subsequent_no_edit(tmp_path):
    folder = tmp_path / "attempt-0001"
    folder.mkdir()
    (folder / "internal-review.json").write_text(json.dumps({"visual_notes": json.dumps({
        "qualitative": {"status": "evaluated", "observations": judgment()["observations"],
                        "next_actions": judgment()["next_actions"]}})}))
    feedback = qualitative_feedback(tmp_path, 3)
    assert "Rivet labels" in feedback and "original location diagram" in feedback
    assert "not instructions" in feedback



def test_blocked_monitor_stays_resident_without_restarting_work(monkeypatch, tmp_path):
    from shorts_studio import improvement_worker as worker
    outcomes = iter(["blocked", "accepted"])
    sleeps = []
    monkeypatch.setattr(worker, "connect", lambda path: object())
    monkeypatch.setattr(worker, "step", lambda *args: next(outcomes))
    monkeypatch.setattr(worker.time, "sleep", sleeps.append)
    monkeypatch.setattr("sys.argv", ["worker", "--database", str(tmp_path / "state.db"),
                                    "run", "--interval", "5", "adapter"])
    worker.main()
    assert sleeps == [5]



def test_visual_regression_is_reported_as_regression_not_only_hold(tmp_path):
    binding = setup(tmp_path, report())
    data = judgment()
    data["b_scores"]["truthful_presentation"] = 1
    q = validate_judgment(data, "bound", "B", [36, 47])
    q.update(video_sha256=binding["video_sha256"], comparison_video_sha256=binding["comparison_video_sha256"])
    result = assess(binding, visual_reviewer=lambda b: q)
    assert result["decision"] == "HOLD" and result["regression"] is True


@pytest.mark.parametrize("reason", ["source changes outside explicit allowlist", "process failed: bwrap (1)", "previously unknown rejection"])
def test_every_rejection_counts_toward_bounded_strategy(reason, tmp_path):
    for n in (1, 2):
        write_result(tmp_path, n, "mobile_readability", failure=reason)
    route = choose_strategy(tmp_path, "new-controller-code-hash", "video")
    assert route["id"] == "causal_explanation"


def test_controller_context_change_does_not_erase_same_candidate_failures(tmp_path):
    for index, (key, _) in enumerate(STRATEGIES):
        for n in (0, 1):
            write_result(tmp_path, index * 2 + n + 1, key)
    assert choose_strategy(tmp_path, "patched-controller", "video")["exhausted"] is True


def test_failure_history_does_not_expire_after_128_other_attempts(tmp_path):
    for index, (key, _) in enumerate(STRATEGIES):
        for n in (0, 1):
            write_result(tmp_path, index * 2 + n + 1, key)
    for n in range(9, 140):
        write_result(tmp_path, n, "mobile_readability", strategy_candidate="unrelated-video")
    assert choose_strategy(tmp_path, "context", "video")["exhausted"] is True


def test_exact_paths_and_policy_failure_reach_next_editor(tmp_path):
    from shorts_studio.improvement_adapter import edit_scope_feedback
    write_result(tmp_path, 1, "opening_storyboard", failure="source changes outside explicit allowlist",
                 rejected_paths=["assets/wrong-directory/photo.png"])
    config = {"editable_paths": ["examples/comet.json", "assets/autonomous/opening.png"]}
    prompt = edit_scope_feedback(config, tmp_path, 2)
    assert json.dumps(config["editable_paths"]) in prompt
    assert "assets/wrong-directory/photo.png" in prompt
    assert "/tmp" in prompt and "Do not invent other asset names" in prompt



def test_actual_failed_cli_quota_error_defers_without_consuming_strategy(tmp_path):
    write_result(tmp_path, 1, "mobile_readability", failure="process failed: bwrap (1)")
    (tmp_path / "attempt-0001/process-007.stderr").write_text("ERROR: You have hit your usage limit.")
    route = choose_strategy(tmp_path, "patched-context", "video")
    assert route["defer"] and route["retry_after_seconds"] >= 1790
    write_result(tmp_path, 2, "mobile_readability", failure="process failed: bwrap (1)")
    (tmp_path / "attempt-0002/process-007.stderr").write_text("ERROR: You have hit your usage limit.")
    route = choose_strategy(tmp_path, "patched-again", "video")
    assert route["defer"] and route["retry_after_seconds"] >= 3590


def test_harmless_telemetry_does_not_become_provider_outage(tmp_path):
    from shorts_studio.improvement_strategy import provider_outage
    path = tmp_path / "result.json"
    (tmp_path / "process-007.stderr").write_text("warning: rate-limit telemetry; completed normally")
    assert not provider_outage(path, {"failure": "process failed: bwrap (1)"})
    (tmp_path / "process-007.stderr").write_text("ERROR: You have hit your usage limit.")
    assert not provider_outage(path, {"state": "verified"})
