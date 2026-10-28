"""Loopback-only preview of the latest verified candidate."""
import hashlib
import json
import re
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

DB=Path("/home/ubuntu/.local/state/shorts-improvement/state.db")
ROOT=Path("/home/ubuntu/shorts-improvement/campaign-comet-v1").resolve()
CHUNK=1024*1024

def candidate():
    receipt=Path("/home/ubuntu/shorts-improvement/comet-terra-readability-20261028/delivery.json")
    data=json.loads(receipt.read_text())
    path=Path(data["video_path"]).resolve()
    allowed=Path("/home/ubuntu/shorts-controller-worktrees/comet-terra-readability-20261028/dist").resolve()
    if path.parent != allowed or path.name != "final.mp4" or not path.is_file():
        raise FileNotFoundError("Revision unavailable")
    sha=data["video_sha256"]
    with path.open("rb") as stream:
        if hashlib.file_digest(stream,"sha256").hexdigest()!=sha:
            raise FileNotFoundError("Revision digest mismatch")
    qa=path.parent/"qa_report.json"
    if hashlib.sha256(qa.read_bytes()).hexdigest()!=data["qa_sha256"] or json.loads(qa.read_text())["status"]!="PASS":
        raise FileNotFoundError("Revision QA changed")
    return sha,path,path.stat().st_size

class Handler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.respond(False)
    def do_GET(self):
        self.respond(True)
    def respond(self,body):
        endpoint=urlsplit(self.path).path
        if endpoint not in ("/final.mp4","/candidate.json"):
            self.send_error(404)
            return
        try:
            sha,path,size=candidate()
        except (FileNotFoundError,OSError,sqlite3.Error):
            self.send_error(503,"Verified candidate unavailable")
            return
        if endpoint=="/candidate.json":
            data=json.dumps({"video_sha256":sha,"bytes":size,"production_approved":False,"scope":"technical QA pass; human approval still required"},sort_keys=True).encode()
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            self.send_header("Content-Length",str(len(data)))
            self.send_header("Cache-Control","no-store")
            self.end_headers()
            if body:
                self.wfile.write(data)
            return
        start,end=0,size-1
        requested=self.headers.get("Range")
        if requested:
            match=re.fullmatch(r"bytes=(\d*)-(\d*)",requested.strip())
            if not match or not any(match.groups()):
                self.send_error(416)
                return
            first,last=match.groups()
            if first:
                start=int(first)
                end=min(int(last),size-1) if last else size-1
            else:
                suffix=int(last)
                start=max(0,size-suffix)
            if start>=size or end<start:
                self.send_error(416)
                return
        partial=bool(requested)
        self.send_response(206 if partial else 200)
        self.send_header("Content-Type","video/mp4")
        self.send_header("Content-Length",str(end-start+1))
        self.send_header("Accept-Ranges","bytes")
        self.send_header("ETag",sha)
        self.send_header("X-Candidate-Sha256",sha)
        self.send_header("Cache-Control","no-store")
        if partial:
            self.send_header("Content-Range",f"bytes {start}-{end}/{size}")
        self.end_headers()
        if body:
            try:
                with path.open("rb") as stream:
                    stream.seek(start)
                    left=end-start+1
                    while left:
                        block=stream.read(min(left,CHUNK))
                        if not block:
                            break
                        self.wfile.write(block)
                        left-=len(block)
            except (BrokenPipeError,ConnectionResetError):
                pass

if __name__=="__main__":
    ThreadingHTTPServer(("127.0.0.1",8767),Handler).serve_forever()
