"""Actual flock processes and persistent SQLite, no cloud operations."""
from datetime import datetime, timedelta, timezone
import os
import sqlite3
import subprocess
import sys

import pytest

from shorts_studio.r2_handoff.contracts import HandoffError
from shorts_studio.r2_handoff.staging import stage_source
from shorts_studio.r2_handoff.state import StateStore, bucket_lock
from test_r2_handoff_contracts import ACCOUNT, limits, plan


def new_job(tmp_path, **kw):
    m = plan(tmp_path)
    s = stage_source(tmp_path / "sample.json", root=tmp_path / "spool", planned=m)
    store = StateStore(tmp_path / "state" / "jobs.sqlite")
    return store, store.create_job(s, limits(**kw))


def test_two_real_processes_share_bucket_lock_and_second_has_zero_network(tmp_path):
    marker = tmp_path / "network-called"
    code = '''from pathlib import Path
import sys
from shorts_studio.r2_handoff.state import bucket_lock
from shorts_studio.r2_handoff.contracts import HandoffError
try:
 with bucket_lock(Path(sys.argv[1]),account_id='a'*32,bucket='shorts-studio-media'):
  Path(sys.argv[2]).write_text('network')
except HandoffError as e:
 print(e.code)
 sys.exit(3)
'''
    with bucket_lock(tmp_path / "locks", account_id=ACCOUNT, bucket="shorts-studio-media"):
        result = subprocess.run([sys.executable, "-c", code, str(tmp_path / "locks"),
                                 str(marker)], capture_output=True, text=True, timeout=5)
    assert result.returncode == 3 and result.stdout.strip() == "BUSY"
    assert not marker.exists()


def test_killed_owner_releases_kernel_lock_without_deleting_lockfile(tmp_path):
    code = '''from pathlib import Path
import sys,time
from shorts_studio.r2_handoff.state import bucket_lock
with bucket_lock(Path(sys.argv[1]),account_id='a'*32,bucket='shorts-studio-media'):
 print('ready',flush=True)
 time.sleep(30)
'''
    p = subprocess.Popen([sys.executable, "-c", code, str(tmp_path / "locks")],
                         stdout=subprocess.PIPE, text=True)
    try:
        assert p.stdout.readline().strip() == "ready"
        inode = next((tmp_path / "locks").iterdir()).stat().st_ino
    finally:
        p.kill()
        p.wait(timeout=5)
    with bucket_lock(tmp_path / "locks", account_id=ACCOUNT, bucket="shorts-studio-media"):
        assert next((tmp_path / "locks").iterdir()).stat().st_ino == inode


def test_crash_after_reservation_does_not_refund_unknown_operation(tmp_path):
    store, job = new_job(tmp_path)
    store.close()
    code = '''from pathlib import Path
from datetime import datetime,timezone
import os,sys
from shorts_studio.r2_handoff.state import StateStore
s=StateStore(Path(sys.argv[1]))
s.reserve(sys.argv[2],kind='data',operation_id='put:0',utc_now=datetime.now(timezone.utc),monotonic_now=0)
os._exit(19)
'''
    p = subprocess.run([sys.executable, "-c", code, str(tmp_path / "state/jobs.sqlite"), job])
    assert p.returncode == 19
    with StateStore(tmp_path / "state/jobs.sqlite") as reopened:
        assert reopened.status(job)["data_used"] == 1
        for _ in range(2):
            reopened.reserve(job, kind="data", operation_id="put:0",
                             utc_now=datetime.now(timezone.utc), monotonic_now=1)
        with pytest.raises(HandoffError, match="LIMIT_REACHED"):
            reopened.reserve(job, kind="data", operation_id="put:0",
                             utc_now=datetime.now(timezone.utc), monotonic_now=1)


@pytest.mark.parametrize("corrupt", [False, True])
def test_corrupt_or_newer_database_blocks_without_reinitialization(tmp_path, corrupt):
    root = tmp_path / "state"
    root.mkdir(mode=0o700)
    db = root / "jobs.sqlite"
    if corrupt:
        db.write_bytes(b"not a database")
    else:
        conn = sqlite3.connect(db)
        conn.execute("PRAGMA user_version=99")
        conn.close()
    db.chmod(0o600)
    before = db.read_bytes()
    with pytest.raises(HandoffError, match="STATE_INVALID"):
        StateStore(db)
    assert db.read_bytes() == before


def test_backward_clock_does_not_extend_current_process_deadline(tmp_path):
    now = datetime.now(timezone.utc)
    store, job = new_job(tmp_path, deadline_utc=now + timedelta(seconds=5))
    with store:
        store.reserve(job, kind="data", operation_id="get:0", utc_now=now, monotonic_now=10)
        with pytest.raises(HandoffError, match="LIMIT_REACHED"):
            store.reserve(job, kind="data", operation_id="get:1",
                          utc_now=now-timedelta(hours=1), monotonic_now=16)


def test_explicit_resume_limits_keep_consumed_counters(tmp_path):
    store, job = new_job(tmp_path)
    with store:
        store.reserve(job, kind="data", operation_id="get:0",
                      utc_now=datetime.now(timezone.utc), monotonic_now=0)
        with pytest.raises(HandoffError):
            store.extend_limits(job, limits=limits(), operator_reason="")
        store.extend_limits(job, limits=limits(max_data_ops=500), operator_reason="retry approved")
        assert store.status(job)["data_used"] == 1
        with pytest.raises(HandoffError):
            store.transition(job, "REMOTE_VERIFIED")
