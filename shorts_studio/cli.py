import argparse, json
from .project import load_project
from .render import render
from .final_video_qa import verify_source_budget

def main():
    ap=argparse.ArgumentParser(prog="shorts_studio"); sub=ap.add_subparsers(dest="cmd",required=True)
    v=sub.add_parser("validate"); v.add_argument("manifest")
    r=sub.add_parser("render"); r.add_argument("manifest"); r.add_argument("--dry-run",action="store_true")
    q=sub.add_parser("qa"); q.add_argument("video")
    a=ap.parse_args()
    if a.cmd=="validate":
        p=load_project(a.manifest)
        if getattr(p,"strict_source_diversity",False):
            budget=verify_source_budget(p)
            if budget["status"]!="PASS":
                print(json.dumps({"status":"FAIL","reason":budget["reason"],"source_budget":budget["evidence"]},ensure_ascii=False))
                raise SystemExit(1)
        print(json.dumps({"status":"PASS","scenes":len(p.scenes)},ensure_ascii=False))
    elif a.cmd=="render": print(json.dumps(render(a.manifest,a.dry_run),ensure_ascii=False))
    else:
        from pathlib import Path
        from .qa import probe_video
        print(json.dumps(probe_video(Path(a.video))))
