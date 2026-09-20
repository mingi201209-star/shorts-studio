from __future__ import annotations
import json, shutil, subprocess
from pathlib import Path

def extract_frame(video: Path, timestamp: float, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg","-y","-ss",str(timestamp),"-i",str(video),"-frames:v","1",str(output)],check=True,capture_output=True)
    return output

def asset_visual_gate(project, sources: list[dict]) -> dict:
    """Fail closed on missing scene assets/requirements. Semantic meaning stays NOT_EVALUATED
    until a vision provider is configured; structural requirements are still enforceable."""
    by_scene={x["scene"]:x for x in sources}
    failures=[]
    for scene in project.scenes:
        if (scene.asset or scene.asset_url) and scene.id not in by_scene:
            failures.append({"scene":scene.id,"reason":"declared asset was not used"})
        if scene.visual_qa_requirements and not (scene.asset or scene.asset_url):
            failures.append({"scene":scene.id,"reason":"visual QA requirements exist without an asset"})
    return {
        "structural_status":"PASS" if not failures else "FAIL",
        "semantic_status":"NOT_EVALUATED",
        "failures":failures,
        "requirements":{s.id:s.visual_qa_requirements for s in project.scenes if s.visual_qa_requirements},
    }
