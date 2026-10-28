"""Read-only loopback review for hash-bound native proof artifacts."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit


def byte_range(value, size):
    if value is None:
        return 0, size - 1, False
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", value)
    if not match or size < 1:
        raise ValueError("invalid range")
    first, last = match.groups()
    if not first:
        if not last or int(last) < 1:
            raise ValueError("invalid suffix")
        return max(0, size - int(last)), size - 1, True
    start = int(first)
    end = min(size - 1, int(last)) if last else size - 1
    if start >= size or start > end:
        raise ValueError("unsatisfiable range")
    return start, end, True


def manifest(root):
    document = json.loads((root / "manifest.json").read_text())
    if not isinstance(document["files"], dict):
        raise TypeError("invalid review manifest")
    return document


def resolve(root, name, document):
    if Path(name).name != name or name not in document["files"]:
        raise KeyError(name)
    record = document["files"][name]
    path = root / name
    if path.is_symlink() or not path.is_file():
        raise ValueError("unsafe proof file")
    if record["mime"] not in ("video/mp4", "image/jpeg", "application/json", "text/plain"):
        raise ValueError("unsupported proof media")
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != record["sha256"] or path.stat().st_size != record["bytes"]:
        raise ValueError("proof file changed")
    return path, record


def index_page(document):
    cards = []
    for name, record in document["files"].items():
        title = html.escape(record.get("title", name))
        url = "/" + quote(name)
        if record["mime"] == "video/mp4":
            count = record["frames"]
            cards.append(
                f"<article><h2>{title}</h2>"
                f"<video controls loop muted preload='metadata' src='{url}'></video>"
                f"<p>{count} native frames / {count / 30:.3f}s / 30fps. "
                "Playback loops for inspection.</p></article>"
            )
        elif record["mime"] == "image/jpeg":
            cards.append(
                f"<article><h2>{title}</h2><a href='{url}'><img src='{url}'></a></article>"
            )
    timing = document.get("timings", {})
    rows = "".join(
        f"<tr><td>{html.escape(str(label))}</td><td>{seconds:.2f}s</td></tr>"
        for label, seconds in timing.items()
    )
    return (
        "<!doctype html><meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Shorts Studio native proof</title>"
        "<style>body{background:#101722;color:#eef3fa;font:16px system-ui;margin:20px}"
        "main{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}"
        "article{background:#1b2839;padding:16px;border-radius:12px}"
        "video,img{width:100%;max-height:65vh;object-fit:contain}a{color:#80d5ff}"
        "td{padding:6px 18px 6px 0}p{line-height:1.5}</style>"
        "<h1>Premium / Fast native proof</h1>"
        "<p>Technical motion assets. 1080x1920, Cycles32. "
        "Kinematic demonstration; no narration or final Short approval.</p>"
        f"<table>{rows}</table><main>{''.join(cards)}</main>"
        "<p><a href='/report.json'>Measured report</a></p>"
    ).encode()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def serve(self, head=False):
        root = self.server.proof_root
        name = unquote(urlsplit(self.path).path).lstrip("/")
        try:
            document = manifest(root)
            if not name:
                body = index_page(document)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if not head:
                    self.wfile.write(body)
                return
            path, record = resolve(root, name, document)
        except KeyError:
            self.send_error(404)
            return
        except (OSError, ValueError, TypeError):
            self.send_error(503, "Proof artifacts not ready or changed")
            return
        try:
            start, end, partial = byte_range(self.headers.get("Range"), record["bytes"])
        except ValueError:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{record['bytes']}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_response(206 if partial else 200)
        self.send_header("Content-Type", record["mime"])
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("ETag", '"' + record["sha256"] + '"')
        if partial:
            self.send_header("Content-Range", f"bytes {start}-{end}/{record['bytes']}")
        self.end_headers()
        if head:
            return
        try:
            with path.open("rb") as stream:
                stream.seek(start)
                remaining = end - start + 1
                while remaining:
                    block = stream.read(min(65536, remaining))
                    if not block:
                        break
                    self.wfile.write(block)
                    remaining -= len(block)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        self.serve()

    def do_HEAD(self):
        self.serve(head=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    root = args.root.resolve()
    document = manifest(root)
    for name in document["files"]:
        resolve(root, name, document)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.proof_root = root
    server.serve_forever()


if __name__ == "__main__":
    main()
