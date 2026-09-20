import argparse, json
from .project import load_project
from .render import render

def main():
    ap=argparse.ArgumentParser(prog="shorts_studio"); sub=ap.add_subparsers(dest="cmd",required=True)
    v=sub.add_parser("validate"); v.add_argument("manifest")
    r=sub.add_parser("render"); r.add_argument("manifest"); r.add_argument("--dry-run",action="store_true")
    q=sub.add_parser("qa"); q.add_argument("video")
    a=ap.parse_args()
    if a.cmd=="validate":
        p=load_project(a.manifest); print(json.dumps({"status":"PASS","scenes":len(p.scenes)},ensure_ascii=False))
    elif a.cmd=="render": print(json.dumps(render(a.manifest,a.dry_run),ensure_ascii=False))
    else:
        from pathlib import Path
        from .qa import probe_video
        print(json.dumps(probe_video(Path(a.video))))
