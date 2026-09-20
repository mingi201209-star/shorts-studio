from __future__ import annotations
import json, os, subprocess
from pathlib import Path
from typing import Protocol

class VisionProvider(Protocol):
    def evaluate(self, image: Path, requirements: list[str]) -> dict: ...

class SidecarVisionProvider:
    """CI/provider-neutral adapter. A trusted vision worker writes <frame>.qa.json.
    Missing/invalid evidence is NOT_EVALUATED, never PASS."""
    def evaluate(self,image:Path,requirements:list[str])->dict:
        sidecar=image.with_suffix(image.suffix+".qa.json")
        if not sidecar.exists():
            return {"status":"NOT_EVALUATED","reason":"no semantic vision evidence"}
        data=json.loads(sidecar.read_text(encoding="utf-8"))
        status=data.get("status")
        if status not in {"PASS","FAIL"}:
            return {"status":"NOT_EVALUATED","reason":"invalid semantic vision evidence"}
        return {"status":status,"details":data.get("details",[]),"requirements":requirements}

def extract_frame(video:Path,timestamp:float,output:Path)->Path:
    output.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(["ffmpeg","-y","-ss",str(timestamp),"-i",str(video),"-frames:v","1",str(output)],check=True,capture_output=True)
    return output

def asset_visual_gate(project,sources:list[dict])->dict:
    by_scene={x["scene"]:x for x in sources}; failures=[]
    for scene in project.scenes:
        if (scene.asset or scene.asset_url) and scene.id not in by_scene:
            failures.append({"scene":scene.id,"reason":"declared asset was not used"})
        if scene.visual_qa_requirements and not (scene.asset or scene.asset_url):
            failures.append({"scene":scene.id,"reason":"visual QA requirements exist without an asset"})
    return {"structural_status":"PASS" if not failures else "FAIL","semantic_status":"NOT_EVALUATED","failures":failures,"requirements":{s.id:s.visual_qa_requirements for s in project.scenes if s.visual_qa_requirements}}

def semantic_visual_gate(project, scene_clips:list[Path], provider:VisionProvider|None=None)->dict:
    provider=provider or SidecarVisionProvider(); results=[]; offset=0.0
    for scene,clip in zip(project.scenes,scene_clips):
        if not scene.visual_qa_requirements: continue
        frame=Path("build")/f"{scene.id}_qa.jpg"; extract_frame(clip,0.5,frame)
        result=provider.evaluate(frame,scene.visual_qa_requirements)
        results.append({"scene":scene.id,**result})
    if any(r["status"]=="FAIL" for r in results): status="FAIL"
    elif results and all(r["status"]=="PASS" for r in results): status="PASS"
    else: status="NOT_EVALUATED"
    return {"status":status,"results":results}
