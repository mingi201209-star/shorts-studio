import argparse, json
from .project import load_project
from .render import render
from .final_video_qa import verify_source_budget, verify_retention_contract

def main():
    ap=argparse.ArgumentParser(prog="shorts_studio"); sub=ap.add_subparsers(dest="cmd",required=True)
    v=sub.add_parser("validate"); v.add_argument("manifest")
    r=sub.add_parser("render"); r.add_argument("manifest"); r.add_argument("--dry-run",action="store_true")
    q=sub.add_parser("qa"); q.add_argument("video")
    g=sub.add_parser("idea-gate"); g.add_argument("pitch")
    a=ap.parse_args()
    if a.cmd=="idea-gate":
        from .idea_gate import IdeaPitch, evaluate_idea
        pitch=IdeaPitch(**json.loads(open(a.pitch,encoding="utf-8").read()))
        result=evaluate_idea(pitch)
        print(json.dumps(result.model_dump(),ensure_ascii=False,indent=2))
        raise SystemExit(0 if result.status=="PASS" else 1)
    elif a.cmd=="validate":
        p=load_project(a.manifest)
        if getattr(p,"strict_source_diversity",False):
            budget=verify_source_budget(p)
            if budget["status"]!="PASS":
                print(json.dumps({"status":"FAIL","reason":budget["reason"],"source_budget":budget["evidence"]},ensure_ascii=False))
                raise SystemExit(1)
        if getattr(p,"strict_retention_contract",False):
            retention=verify_retention_contract(p)
            if retention["status"]!="PASS":
                print(json.dumps({"status":"FAIL","retention_contract":retention["checks"]},ensure_ascii=False))
                raise SystemExit(1)
        print(json.dumps({"status":"PASS","scenes":len(p.scenes)},ensure_ascii=False))
    elif a.cmd=="render": print(json.dumps(render(a.manifest,a.dry_run),ensure_ascii=False))
    else:
        from pathlib import Path
        from .qa import probe_video
        print(json.dumps(probe_video(Path(a.video))))
