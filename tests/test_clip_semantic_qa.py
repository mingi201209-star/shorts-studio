"""ClipSemanticVisionProvider: real local zero-shot semantic QA when the optional
'vision' extra (open_clip + torch) is installed, and honest NOT_EVALUATED
degradation when it is not -- never a fake PASS either way.
"""
import shorts_studio.visual_qa as vqa
from shorts_studio.visual_qa import ClipSemanticVisionProvider

def test_no_labels_declared_is_not_evaluated(tmp_path):
    p = tmp_path / "f.jpg"; p.write_bytes(b"x")
    q = ClipSemanticVisionProvider().evaluate(p, ["subject visible"])
    assert q["status"] == "NOT_EVALUATED"

def test_model_unavailable_is_not_evaluated_not_pass(tmp_path, monkeypatch):
    p = tmp_path / "f.jpg"; p.write_bytes(b"x")
    monkeypatch.setattr(vqa, "_load_clip", lambda *a, **k: None)
    q = ClipSemanticVisionProvider().evaluate(
        p, ["comet visible"], positive_labels=["a de Havilland Comet jet airliner"]
    )
    assert q["status"] == "NOT_EVALUATED"

def test_dominant_positive_label_passes(tmp_path, monkeypatch):
    p = tmp_path / "f.jpg"; p.write_bytes(b"x")
    monkeypatch.setattr(vqa, "_load_clip", lambda *a, **k: object())
    monkeypatch.setattr(vqa, "clip_zero_shot_scores", lambda bundle, image, labels: {
        "a vintage 1950s jet airliner": 0.32, "a modern office desk": 0.05,
    })
    q = ClipSemanticVisionProvider().evaluate(
        p, ["comet visible"],
        positive_labels=["a vintage 1950s jet airliner"],
        negative_labels=["a modern office desk"],
    )
    assert q["status"] == "PASS"

def test_wrong_domain_dominates_fails(tmp_path, monkeypatch):
    p = tmp_path / "f.jpg"; p.write_bytes(b"x")
    monkeypatch.setattr(vqa, "_load_clip", lambda *a, **k: object())
    monkeypatch.setattr(vqa, "clip_zero_shot_scores", lambda bundle, image, labels: {
        "water tank fatigue test rig": 0.10, "an airplane flying in the sky": 0.29,
    })
    q = ClipSemanticVisionProvider().evaluate(
        p, ["water tank test rig visible, not a generic aircraft"],
        positive_labels=["water tank fatigue test rig"],
        negative_labels=["an airplane flying in the sky"],
    )
    assert q["status"] == "FAIL"

def test_weak_absolute_match_fails_even_without_negative(tmp_path, monkeypatch):
    p = tmp_path / "f.jpg"; p.write_bytes(b"x")
    monkeypatch.setattr(vqa, "_load_clip", lambda *a, **k: object())
    monkeypatch.setattr(vqa, "clip_zero_shot_scores", lambda bundle, image, labels: {"aircraft wreckage debris": 0.05})
    q = ClipSemanticVisionProvider().evaluate(p, ["wreckage visible"], positive_labels=["aircraft wreckage debris"])
    assert q["status"] == "FAIL"

def test_inference_error_is_not_evaluated_not_pass(tmp_path, monkeypatch):
    p = tmp_path / "f.jpg"; p.write_bytes(b"x")
    monkeypatch.setattr(vqa, "_load_clip", lambda *a, **k: object())
    def boom(bundle, image, labels): raise RuntimeError("corrupt frame")
    monkeypatch.setattr(vqa, "clip_zero_shot_scores", boom)
    q = ClipSemanticVisionProvider().evaluate(p, ["x"], positive_labels=["a plane"])
    assert q["status"] == "NOT_EVALUATED"
