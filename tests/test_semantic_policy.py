from pathlib import Path
from types import SimpleNamespace
from shorts_studio.visual_qa import semantic_visual_gate

class Provider:
    def __init__(self,status): self.status=status
    def evaluate(self,image,requirements): return {"status":self.status}

def test_semantic_gate_fail_propagates(monkeypatch,tmp_path):
    monkeypatch.setattr("shorts_studio.visual_qa.extract_frame",lambda video,timestamp,output: output)
    p=SimpleNamespace(scenes=[SimpleNamespace(id="s1",visual_qa_requirements=["subject visible"])])
    q=semantic_visual_gate(p,[tmp_path/"s1.mp4"],Provider("FAIL"))
    assert q["status"]=="FAIL"

def test_semantic_gate_pass_requires_all_required_scenes(monkeypatch,tmp_path):
    monkeypatch.setattr("shorts_studio.visual_qa.extract_frame",lambda video,timestamp,output: output)
    p=SimpleNamespace(scenes=[SimpleNamespace(id="s1",visual_qa_requirements=["square"]),SimpleNamespace(id="s2",visual_qa_requirements=["round"])])
    q=semantic_visual_gate(p,[tmp_path/"1.mp4",tmp_path/"2.mp4"],Provider("PASS"))
    assert q["status"]=="PASS"
