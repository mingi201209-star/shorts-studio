from types import SimpleNamespace
from shorts_studio.visual_qa import asset_visual_gate

def scene(id, asset=None, url=None, req=None):
    return SimpleNamespace(id=id,asset=asset,asset_url=url,visual_qa_requirements=req or [])

def test_structural_visual_gate_passes_used_asset():
    p=SimpleNamespace(scenes=[scene("s1","a.png",req=["subject visible"])])
    q=asset_visual_gate(p,[{"scene":"s1","asset":"a.png"}])
    assert q["structural_status"]=="PASS"
    assert q["semantic_status"]=="NOT_EVALUATED"

def test_structural_visual_gate_fails_missing_used_asset():
    p=SimpleNamespace(scenes=[scene("s1","a.png",req=["subject visible"])])
    assert asset_visual_gate(p,[])["structural_status"]=="FAIL"

def test_requirements_without_asset_fail_closed():
    p=SimpleNamespace(scenes=[scene("s1",req=["square corners"])])
    assert asset_visual_gate(p,[])["structural_status"]=="FAIL"


def test_sidecar_provider_never_passes_without_evidence(tmp_path):
    from shorts_studio.visual_qa import SidecarVisionProvider
    image=tmp_path/"frame.jpg"; image.write_bytes(b"x")
    assert SidecarVisionProvider().evaluate(image,["square corners"])["status"]=="NOT_EVALUATED"

def test_sidecar_provider_accepts_explicit_pass(tmp_path):
    import json
    from shorts_studio.visual_qa import SidecarVisionProvider
    image=tmp_path/"frame.jpg"; image.write_bytes(b"x")
    image.with_suffix(".jpg.qa.json").write_text(json.dumps({"status":"PASS","details":["verified"]}))
    assert SidecarVisionProvider().evaluate(image,["square corners"])["status"]=="PASS"

def test_sidecar_provider_never_passes_on_corrupt_json(tmp_path):
    from shorts_studio.visual_qa import SidecarVisionProvider
    image=tmp_path/"frame.jpg"; image.write_bytes(b"x")
    image.with_suffix(".jpg.qa.json").write_text("{not valid json")
    assert SidecarVisionProvider().evaluate(image,["square corners"])["status"]=="NOT_EVALUATED"

def test_sidecar_provider_never_passes_on_malformed_status(tmp_path):
    import json
    from shorts_studio.visual_qa import SidecarVisionProvider
    image=tmp_path/"frame.jpg"; image.write_bytes(b"x")
    image.with_suffix(".jpg.qa.json").write_text(json.dumps({"status":"MAYBE_OK"}))
    assert SidecarVisionProvider().evaluate(image,["square corners"])["status"]=="NOT_EVALUATED"


def test_provenance_pass_cannot_override_semantic_fail(tmp_path):
    from shorts_studio.visual_qa import CompositeVisionProvider, AssetProvenanceVisionProvider, ClipSemanticVisionProvider

    image=tmp_path/"frame.jpg"; image.write_bytes(b"frame")
    asset=tmp_path/"asset.jpg"; asset.write_bytes(b"known-good-asset")

    class ProvenancePass(AssetProvenanceVisionProvider):
        def evaluate(self,image,requirements,**context):
            return {"status":"PASS","sha256":"pinned"}

    class SemanticFail(ClipSemanticVisionProvider):
        def evaluate(self,image,requirements,**context):
            return {"status":"FAIL","reason":"declared subject is not visible"}

    result=CompositeVisionProvider([ProvenancePass(),SemanticFail()]).evaluate(
        image,["expected subject visible"],asset_path=asset
    )
    assert result["status"]=="FAIL"
    assert "subject" in result["reason"]


def test_clip_narrow_positive_lead_is_inconclusive_not_wrong_domain(monkeypatch, tmp_path):
    import shorts_studio.visual_qa as vq
    image=tmp_path/"frame.jpg"; image.write_bytes(b"x")
    monkeypatch.setattr(vq, "_load_clip", lambda *a, **k: object())
    monkeypatch.setattr(vq, "clip_zero_shot_scores", lambda bundle, image, labels: {
        "expected one": .220, "expected two": .210,
        "wrong one": .205, "wrong two": .200,
    })
    r=vq.ClipSemanticVisionProvider().evaluate(
        image, ["expected subject visible"],
        positive_labels=["expected one","expected two"],
        negative_labels=["wrong one","wrong two"],
    )
    assert r["status"]=="NOT_EVALUATED"
    assert 0 < r["margin"] < .03


def test_clip_negative_ensemble_beating_positive_is_confident_fail(monkeypatch, tmp_path):
    import shorts_studio.visual_qa as vq
    image=tmp_path/"frame.jpg"; image.write_bytes(b"x")
    monkeypatch.setattr(vq, "_load_clip", lambda *a, **k: object())
    monkeypatch.setattr(vq, "clip_zero_shot_scores", lambda bundle, image, labels: {
        "expected one": .220, "expected two": .210,
        "wrong one": .230, "wrong two": .225,
    })
    r=vq.ClipSemanticVisionProvider().evaluate(
        image, ["expected subject visible"],
        positive_labels=["expected one","expected two"],
        negative_labels=["wrong one","wrong two"],
    )
    assert r["status"]=="FAIL"
    assert r["margin"] <= 0


def test_clarity_pass_cannot_promote_inconclusive_semantics(tmp_path):
    from shorts_studio.visual_qa import CompositeVisionProvider, ClarityVisionProvider, ClipSemanticVisionProvider

    image=tmp_path/"frame.jpg"; image.write_bytes(b"frame")

    class ClarityPass(ClarityVisionProvider):
        def evaluate(self,image,requirements,**context):
            return {"status":"PASS","sharpness":100.0}

    class SemanticInconclusive(ClipSemanticVisionProvider):
        def evaluate(self,image,requirements,**context):
            return {"status":"NOT_EVALUATED","reason":"narrow semantic lead"}

    result=CompositeVisionProvider([ClarityPass(),SemanticInconclusive()]).evaluate(
        image,["expected subject visible"],
        positive_labels=["expected subject"],
        negative_labels=["wrong subject"],
    )
    assert result["status"]=="NOT_EVALUATED"
    assert "semantic provider" in result["reason"]


def test_semantic_subject_image_crops_title_and_caption_bands(tmp_path):
    from PIL import Image
    from shorts_studio.visual_qa import _semantic_subject_image
    image=tmp_path/"frame.png"
    Image.new("RGB",(1080,1920),(128,128,128)).save(image)
    cropped=_semantic_subject_image(image)
    assert cropped.size == (1004,1110)
    # The semantic crop is the renderer's main visual band, not the full short.
    assert cropped.height < 1920
    assert cropped.width < 1080


def test_semantic_subject_images_cover_wide_archival_frame(tmp_path):
    from PIL import Image
    from shorts_studio.visual_qa import _semantic_subject_images
    image=tmp_path/"frame.png"
    Image.new("RGB",(1080,1920),(128,128,128)).save(image)
    crops=_semantic_subject_images(image)
    assert len(crops) == 4
    assert crops[0].size == (1004,1110)
    assert all(c.height == 1110 for c in crops)
    assert all(c.width > 0 for c in crops)
    assert crops[1].width < crops[0].width
