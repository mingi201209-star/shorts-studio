"""Automated visual-QA recovery loop: on a semantic FAIL, swap only the failing
scene's asset for the next declared fallback candidate and re-render only that
scene's clip, bounded by max_visual_recovery_attempts. Never restarts the whole
production, and never loops forever.
"""
from pathlib import Path
from types import SimpleNamespace
import shorts_studio.render as render_mod

class FakeCandidate:
    def __init__(self,url): self.asset=None; self.asset_url=url; self.attribution=None
    def model_dump(self): return {"asset":self.asset,"asset_url":self.asset_url,"attribution":self.attribution}

def make_scene(id,urls,requirements):
    return SimpleNamespace(
        id=id, asset=None, asset_url=urls[0], attribution=None,
        visual_qa_requirements=requirements, recovery_candidates=[FakeCandidate(u) for u in urls[1:]],
    )

def test_recovery_swaps_asset_and_passes_on_second_candidate(tmp_path,monkeypatch):
    scene=make_scene("s1",["bad.jpg","good.jpg"],["subject visible"])
    monkeypatch.setattr(render_mod,"_resolve_asset",lambda cand,build,sid,idx: Path(cand["asset_url"]))
    composited=[]
    monkeypatch.setattr(render_mod,"_composite_scene_clip",lambda scene,asset,audio,srt,duration,fps,build,index,**k:(composited.append(index),tmp_path/f"c{index}.mp4")[1])
    results=iter([{"scene":"s1","status":"FAIL","reason":"wrong domain"},{"scene":"s1","status":"PASS"}])
    monkeypatch.setattr(render_mod,"evaluate_scene_semantics",lambda scene,clip,provider,frame,**k: next(results))
    outcome=render_mod._render_scene_with_recovery(scene,tmp_path/"a.mp3",2.0,tmp_path/"a.srt",30,tmp_path,max_attempts=2,provider=None)
    assert outcome["semantic"]["status"]=="PASS"
    assert outcome["semantic"]["recovery_attempts"]==1
    assert outcome["semantic"]["recovery_exhausted"] is False
    assert composited==[0,1]

def test_recovery_limit_exceeded_fails_scene_and_production(tmp_path,monkeypatch):
    scene=make_scene("s1",["bad1.jpg","bad2.jpg","bad3.jpg"],["subject visible"])
    monkeypatch.setattr(render_mod,"_resolve_asset",lambda cand,build,sid,idx: Path(cand["asset_url"]))
    monkeypatch.setattr(render_mod,"_composite_scene_clip",lambda *a,**k: tmp_path/"c.mp4")
    monkeypatch.setattr(render_mod,"evaluate_scene_semantics",lambda *a,**k: {"scene":"s1","status":"FAIL","reason":"still wrong"})
    outcome=render_mod._render_scene_with_recovery(scene,tmp_path/"a.mp3",2.0,tmp_path/"a.srt",30,tmp_path,max_attempts=1,provider=None)
    assert outcome["semantic"]["status"]=="FAIL"
    assert outcome["semantic"]["recovery_exhausted"] is True
    assert outcome["semantic"]["recovery_attempts"]==1  # max_attempts=1: tried primary + exactly 1 fallback, no more

def test_no_recovery_candidates_fails_closed_after_zero_attempts(tmp_path,monkeypatch):
    scene=make_scene("s1",["only.jpg"],["subject visible"])
    monkeypatch.setattr(render_mod,"_resolve_asset",lambda cand,build,sid,idx: Path(cand["asset_url"]))
    monkeypatch.setattr(render_mod,"_composite_scene_clip",lambda *a,**k: tmp_path/"c.mp4")
    monkeypatch.setattr(render_mod,"evaluate_scene_semantics",lambda *a,**k: {"scene":"s1","status":"FAIL","reason":"wrong"})
    outcome=render_mod._render_scene_with_recovery(scene,tmp_path/"a.mp3",2.0,tmp_path/"a.srt",30,tmp_path,max_attempts=5,provider=None)
    assert outcome["semantic"]["status"]=="FAIL"
    assert outcome["semantic"]["recovery_attempts"]==0
    assert outcome["semantic"]["recovery_exhausted"] is True  # no more candidates, regardless of the budget left

def test_recovery_never_touches_other_scenes(tmp_path,monkeypatch):
    scene=make_scene("s1",["bad.jpg","good.jpg"],["subject visible"])
    monkeypatch.setattr(render_mod,"_resolve_asset",lambda cand,build,sid,idx: Path(cand["asset_url"]))
    render_calls=[]
    def fake_composite(scene,asset,audio,srt,duration,fps,build,index,**k):
        render_calls.append((scene.id,index)); return tmp_path/f"c{index}.mp4"
    monkeypatch.setattr(render_mod,"_composite_scene_clip",fake_composite)
    results=iter([{"scene":"s1","status":"FAIL"},{"scene":"s1","status":"PASS"}])
    monkeypatch.setattr(render_mod,"evaluate_scene_semantics",lambda scene,clip,provider,frame,**k: next(results))
    render_mod._render_scene_with_recovery(scene,tmp_path/"a.mp3",2.0,tmp_path/"a.srt",30,tmp_path,max_attempts=3,provider=None)
    assert all(scene_id=="s1" for scene_id,_ in render_calls)

def test_zero_max_attempts_disables_recovery_entirely(tmp_path,monkeypatch):
    scene=make_scene("s1",["bad.jpg","good.jpg"],["subject visible"])
    monkeypatch.setattr(render_mod,"_resolve_asset",lambda cand,build,sid,idx: Path(cand["asset_url"]))
    composited=[]
    monkeypatch.setattr(render_mod,"_composite_scene_clip",lambda scene,asset,audio,srt,duration,fps,build,index,**k:(composited.append(index),tmp_path/f"c{index}.mp4")[1])
    monkeypatch.setattr(render_mod,"evaluate_scene_semantics",lambda *a,**k: {"scene":"s1","status":"FAIL","reason":"wrong"})
    outcome=render_mod._render_scene_with_recovery(scene,tmp_path/"a.mp3",2.0,tmp_path/"a.srt",30,tmp_path,max_attempts=0,provider=None)
    assert composited==[0]  # never touches the fallback candidate
    assert outcome["semantic"]["recovery_attempts"]==0
    assert outcome["semantic"]["recovery_exhausted"] is True

def test_pass_on_first_try_needs_no_recovery(tmp_path,monkeypatch):
    scene=make_scene("s1",["good.jpg"],["subject visible"])
    monkeypatch.setattr(render_mod,"_resolve_asset",lambda cand,build,sid,idx: Path(cand["asset_url"]))
    monkeypatch.setattr(render_mod,"_composite_scene_clip",lambda *a,**k: tmp_path/"c.mp4")
    monkeypatch.setattr(render_mod,"evaluate_scene_semantics",lambda *a,**k: {"scene":"s1","status":"PASS"})
    outcome=render_mod._render_scene_with_recovery(scene,tmp_path/"a.mp3",2.0,tmp_path/"a.srt",30,tmp_path,max_attempts=2,provider=None)
    assert outcome["semantic"]["recovery_attempts"]==0
    assert outcome["semantic"]["recovery_exhausted"] is False


def test_visual_beat_provenance_uses_asset_at_sampled_clip_midpoint(tmp_path,monkeypatch):
    scene=make_scene("s1",["unused.jpg"],["scene must pass"])
    scene.visual_beats=[
        SimpleNamespace(start=0,visual_qa_requirements=["opening wreckage"],visual_qa_labels=["wreckage"],visual_qa_negative_labels=[],visual_qa_expected_sha256=["opening-sha"],motion=SimpleNamespace(type="push_in")),
        SimpleNamespace(start=2.2,visual_qa_requirements=["intact reveal"],visual_qa_labels=["intact aircraft"],visual_qa_negative_labels=[],visual_qa_expected_sha256=["reveal-sha"],motion=SimpleNamespace(type="pull_out")),
    ]
    beat_assets=[tmp_path/"opening.jpg",tmp_path/"reveal.jpg"]
    beat_clips=[tmp_path/"opening.mp4",tmp_path/"reveal.mp4"]
    clip=tmp_path/"s1.mp4"
    monkeypatch.setattr(render_mod,"_composite_visual_beats",lambda *a,**k:(clip,beat_assets,[2.2,3.8],beat_clips))
    monkeypatch.setattr(render_mod,"_media_duration_seconds",lambda path:6.0)
    seen=[]
    def fake_evaluate(scene,clip,provider,frame,**kwargs):
        seen.append((scene,clip,kwargs))
        return {"scene":scene.id,"status":"PASS"}
    monkeypatch.setattr(render_mod,"evaluate_scene_semantics",fake_evaluate)

    outcome=render_mod._render_scene_with_recovery(scene,tmp_path/"a.mp3",6.0,tmp_path/"a.srt",30,tmp_path,max_attempts=0,provider=None)

    assert outcome["semantic"]["status"]=="PASS"
    assert outcome["source"]["asset"]==str(beat_assets[1])
    assert [item[0].id for item in seen]==["s1_beat_00","s1_beat_01"]
    assert [item[1] for item in seen]==beat_clips
    assert [item[2]["asset_path"] for item in seen]==beat_assets


def test_visual_beat_asset_selection_fails_closed_on_mismatched_metadata():
    from pytest import raises
    with raises(ValueError,match="counts do not match"):
        render_mod._representative_visual_asset([Path("opening.jpg")],[],4.0)


def test_comet_identification_beat_is_visible_at_semantic_sample_midpoint():
    from shorts_studio.project import load_project
    scene=load_project("examples/comet.json").scenes[0]
    assert scene.visual_beats[1].start==1.0
    assets=[Path("opening-fuselage.jpg"),Path("comet-aircraft.jpg")]
    assert render_mod._representative_visual_asset(assets,[1.0,3.0],4.0)==assets[1]
