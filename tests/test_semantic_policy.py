from types import SimpleNamespace
import pytest
from shorts_studio.visual_qa import semantic_visual_gate, production_semantic_ok

class Provider:
    def __init__(self,status): self.status=status
    def evaluate(self,image,requirements,**context): return {"status":self.status}

def _scene(id,req): return SimpleNamespace(id=id,narration="n",visual_qa_requirements=req,visual_qa_labels=[],visual_qa_negative_labels=[])

def test_semantic_gate_fail_propagates(monkeypatch,tmp_path):
    monkeypatch.setattr("shorts_studio.visual_qa.extract_frame",lambda video,timestamp,output: output)
    p=SimpleNamespace(scenes=[_scene("s1",["subject visible"])])
    q=semantic_visual_gate(p,[tmp_path/"s1.mp4"],Provider("FAIL"))
    assert q["status"]=="FAIL"

def test_semantic_gate_pass_requires_all_required_scenes(monkeypatch,tmp_path):
    monkeypatch.setattr("shorts_studio.visual_qa.extract_frame",lambda video,timestamp,output: output)
    p=SimpleNamespace(scenes=[_scene("s1",["square"]),_scene("s2",["round"])])
    q=semantic_visual_gate(p,[tmp_path/"1.mp4",tmp_path/"2.mp4"],Provider("PASS"))
    assert q["status"]=="PASS"

def test_semantic_gate_not_evaluated_when_provider_never_runs(monkeypatch,tmp_path):
    monkeypatch.setattr("shorts_studio.visual_qa.extract_frame",lambda video,timestamp,output: output)
    p=SimpleNamespace(scenes=[_scene("s1",["subject visible"])])
    q=semantic_visual_gate(p,[tmp_path/"s1.mp4"],Provider("NOT_EVALUATED"))
    assert q["status"]=="NOT_EVALUATED"

@pytest.mark.parametrize("status,required,expected",[
    ("PASS",True,True),
    ("NOT_EVALUATED",True,False),   # production-required + not executed -> must not be treated as success
    ("FAIL",True,False),
    ("PASS",False,True),
    ("NOT_EVALUATED",False,True),   # not required -> NOT_EVALUATED tolerated
    ("FAIL",False,False),           # a real FAIL always fails, required or not
])
def test_production_semantic_ok_policy(status,required,expected):
    assert production_semantic_ok(status,required) is expected
