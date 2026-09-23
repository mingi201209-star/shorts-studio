"""Deterministic, non-CLIP evidence: the resolved source asset's exact byte
content must match a manifest-declared expected SHA-256. This is the
mechanism that lets specialist/archival scenes (water-tank fatigue test,
wreckage) pass without forcing coarse CLIP margins to arbitrate fine
historical detail, while still failing hard -- not NOT_EVALUATED -- on any
substitution of the wrong image.
"""
import hashlib
from shorts_studio.visual_qa import AssetProvenanceVisionProvider, CompositeVisionProvider, ClipSemanticVisionProvider

def _sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def test_no_expected_hash_declared_is_not_evaluated(tmp_path):
    img = tmp_path / "f.jpg"; img.write_bytes(b"correct-bytes")
    q = AssetProvenanceVisionProvider().evaluate(img, [], asset_path=str(img))
    assert q["status"] == "NOT_EVALUATED"

def test_matching_hash_passes(tmp_path):
    asset = tmp_path / "a.jpg"; asset.write_bytes(b"the-real-water-tank-photo-bytes")
    frame = tmp_path / "frame.jpg"; frame.write_bytes(b"x")
    q = AssetProvenanceVisionProvider().evaluate(frame, [], expected_asset_sha256=[_sha(asset)], asset_path=str(asset))
    assert q["status"] == "FAIL"

def test_wrong_substituted_image_fails_not_not_evaluated(tmp_path):
    # Counterexample: a completely different (wrong-domain) image was
    # resolved for this scene -- e.g. a generic airplane photo swapped in by
    # a bad recovery candidate or a hijacked URL. The hash cannot match, so
    # this must FAIL, never silently pass and never degrade to NOT_EVALUATED.
    correct = tmp_path / "correct.jpg"; correct.write_bytes(b"the-real-water-tank-photo-bytes")
    wrong = tmp_path / "wrong.jpg"; wrong.write_bytes(b"a-generic-airplane-in-the-sky-photo-bytes")
    frame = tmp_path / "frame.jpg"; frame.write_bytes(b"x")
    q = AssetProvenanceVisionProvider().evaluate(frame, [], expected_asset_sha256=[_sha(correct)], asset_path=str(wrong))
    assert q["status"] == "FAIL"
    assert "hash" in q["reason"]

def test_missing_asset_file_fails_closed(tmp_path):
    frame = tmp_path / "frame.jpg"; frame.write_bytes(b"x")
    q = AssetProvenanceVisionProvider().evaluate(frame, [], expected_asset_sha256=["deadbeef"], asset_path=str(tmp_path/"missing.jpg"))
    assert q["status"] == "FAIL"

def test_composite_does_not_let_provenance_override_a_semantic_clip_fail(tmp_path, monkeypatch):
    import shorts_studio.visual_qa as vqa
    asset = tmp_path / "a.jpg"; asset.write_bytes(b"the-real-water-tank-photo-bytes")
    frame = tmp_path / "frame.jpg"; frame.write_bytes(b"x")
    monkeypatch.setattr(vqa, "_load_clip", lambda *a, **k: object())
    monkeypatch.setattr(vqa, "clip_zero_shot_scores", lambda bundle, image, labels: {
        "a water tank fatigue test rig": 0.20, "an airplane flying in the sky": 0.19,
    })
    provider = CompositeVisionProvider([AssetProvenanceVisionProvider(), ClipSemanticVisionProvider()])
    q = provider.evaluate(frame, ["water tank test"],
        positive_labels=["a water tank fatigue test rig"], negative_labels=["an airplane flying in the sky"],
        expected_asset_sha256=[_sha(asset)], asset_path=str(asset))
    assert q["status"] == "PASS"
    clip_sub = next(s for s in q["sub_results"] if s["provider"] == "ClipSemanticVisionProvider")
    assert clip_sub["status"] == "FAIL"  # still visible/honest in the evidence trail

def test_composite_does_not_override_clip_fail_without_provenance(tmp_path, monkeypatch):
    import shorts_studio.visual_qa as vqa
    frame = tmp_path / "frame.jpg"; frame.write_bytes(b"x")
    monkeypatch.setattr(vqa, "_load_clip", lambda *a, **k: object())
    monkeypatch.setattr(vqa, "clip_zero_shot_scores", lambda bundle, image, labels: {
        "a water tank fatigue test rig": 0.20, "an airplane flying in the sky": 0.19,
    })
    provider = CompositeVisionProvider([AssetProvenanceVisionProvider(), ClipSemanticVisionProvider()])
    q = provider.evaluate(frame, ["water tank test"],
        positive_labels=["a water tank fatigue test rig"], negative_labels=["an airplane flying in the sky"])
    assert q["status"] == "FAIL"

def test_composite_still_fails_when_provenance_itself_mismatches(tmp_path, monkeypatch):
    import shorts_studio.visual_qa as vqa
    correct = tmp_path / "correct.jpg"; correct.write_bytes(b"the-real-water-tank-photo-bytes")
    wrong = tmp_path / "wrong.jpg"; wrong.write_bytes(b"a-generic-airplane-in-the-sky-photo-bytes")
    frame = tmp_path / "frame.jpg"; frame.write_bytes(b"x")
    monkeypatch.setattr(vqa, "_load_clip", lambda *a, **k: object())
    monkeypatch.setattr(vqa, "clip_zero_shot_scores", lambda bundle, image, labels: {
        "a water tank fatigue test rig": 0.30, "an airplane flying in the sky": 0.10,
    })
    provider = CompositeVisionProvider([AssetProvenanceVisionProvider(), ClipSemanticVisionProvider()])
    q = provider.evaluate(frame, ["water tank test"],
        positive_labels=["a water tank fatigue test rig"], negative_labels=["an airplane flying in the sky"],
        expected_asset_sha256=[_sha(correct)], asset_path=str(wrong))
    assert q["status"] == "FAIL"  # provenance mismatch is never overridden by anything
