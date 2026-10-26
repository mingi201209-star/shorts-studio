"""Persistent, single-writer controller for an external Shorts improvement adapter.

The adapter receives a JSON job on stdin and returns JSON with candidate_sha,
video_path, qa_pass, ci_pass, and regression. It must perform the actual edit,
render, review and CI verification; this controller never fabricates those facts.
"""

import argparse
import hashlib
import json
import sqlite3
import subprocess
import time
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS campaign (
 id INTEGER PRIMARY KEY CHECK (id = 1), state TEXT NOT NULL,
 iteration INTEGER NOT NULL, accepted_sha TEXT, last_good_sha TEXT,
 candidate_sha TEXT, video_path TEXT, failure TEXT
);
CREATE TABLE IF NOT EXISTS events (
 id INTEGER PRIMARY KEY, created_at INTEGER NOT NULL, kind TEXT NOT NULL,
 details TEXT NOT NULL
);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.executescript(SCHEMA)
    db.execute("INSERT OR IGNORE INTO campaign(id,state,iteration) VALUES(1,'running',0)")
    db.commit()
    return db


def record(db: sqlite3.Connection, kind: str, details: dict) -> None:
    db.execute("INSERT INTO events(created_at,kind,details) VALUES(?,?,?)",
               (int(time.time()), kind, json.dumps(details, ensure_ascii=False)))


def step(db: sqlite3.Connection, adapter: list[str], timeout: int) -> str:
    state, iteration, accepted, good, candidate = db.execute(
        "SELECT state,iteration,accepted_sha,last_good_sha,candidate_sha FROM campaign WHERE id=1"
    ).fetchone()
    if accepted:
        return "accepted"
    if state == "blocked":
        return "blocked"
    job = {"iteration": iteration + 1, "last_good_sha": good,
           "previous_candidate_sha": candidate}
    try:
        proc = subprocess.run(adapter, input=json.dumps(job), text=True,
                              capture_output=True, timeout=timeout, check=True)
        result = json.loads(proc.stdout)
        sha = result["candidate_sha"]
        video = result["video_path"]
        if not isinstance(sha, str) or len(sha) != 64 or not all(c in "0123456789abcdef" for c in sha):
            raise ValueError("candidate_sha must be a lowercase SHA256")
        if not isinstance(video, str) or not video or not Path(video).is_file():
            raise ValueError("candidate video missing")
        digest_state = hashlib.sha256()
        with Path(video).open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest_state.update(chunk)
        digest = digest_state.hexdigest()
        if digest != sha:
            raise ValueError("candidate video digest differs from candidate_sha")
        if sha == candidate:
            raise ValueError("adapter returned unchanged candidate")
        if any(result.get(key) is not True for key in ("qa_pass", "ci_pass")):
            raise ValueError("QA and CI must both be verified")
        if result.get("regression") is not False:
            raise ValueError("regression must be explicitly false")
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError) as exc:
        with db:
            db.execute("UPDATE campaign SET state='blocked', failure=? WHERE id=1", (str(exc)[:500],))
            record(db, "blocked", {"iteration": iteration + 1, "reason": str(exc)[:500]})
        return "blocked"
    with db:
        db.execute("UPDATE campaign SET state='running', iteration=?, last_good_sha=?, "
                   "candidate_sha=?, video_path=?, failure=NULL WHERE id=1",
                   (iteration + 1, sha, sha, video))
        record(db, "candidate", {"iteration": iteration + 1, "sha": sha, "video": video})
    return "running"


def approve(db: sqlite3.Connection, sha: str) -> None:
    with db:
        row = db.execute("SELECT candidate_sha,state FROM campaign WHERE id=1").fetchone()
        if row != (sha, "running"):
            raise ValueError("approval must match the current verified candidate")
        db.execute("UPDATE campaign SET accepted_sha=?, state='accepted' WHERE id=1", (sha,))
        record(db, "accepted", {"sha": sha})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    sub = parser.add_subparsers(dest="action", required=True)
    run = sub.add_parser("run")
    run.add_argument("--interval", type=int, default=300)
    run.add_argument("--timeout", type=int, default=3600)
    run.add_argument("adapter", nargs=argparse.REMAINDER)
    sub.add_parser("status")
    app = sub.add_parser("approve")
    app.add_argument("sha")
    sub.add_parser("resume")
    args = parser.parse_args()
    db = connect(args.database)
    if args.action == "status":
        row = db.execute("SELECT state,iteration,accepted_sha,last_good_sha,candidate_sha,video_path,failure FROM campaign WHERE id=1").fetchone()
        print(json.dumps(dict(zip(("state", "iteration", "accepted_sha", "last_good_sha", "candidate_sha", "video_path", "failure"), row))))
    elif args.action == "approve":
        approve(db, args.sha)
    elif args.action == "resume":
        with db:
            db.execute("UPDATE campaign SET state='running',failure=NULL WHERE state='blocked' AND id=1")
    else:
        if not args.adapter or args.interval < 1 or args.timeout < 1:
            parser.error("adapter, positive interval and timeout required")
        while step(db, args.adapter, args.timeout) == "running":
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
