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
