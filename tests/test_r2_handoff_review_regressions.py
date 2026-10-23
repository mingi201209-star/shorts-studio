"""Five independently reviewed safety/recovery gaps, exercised before their fixes."""
import os
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta

import pytest
from test_r2_handoff_contracts import ACCOUNT, limits
from test_r2_handoff_coordinator import harness
from test_r2_handoff_wrangler import KEY, SHA_ABC, backend

from shorts_studio.r2_handoff import contracts
from shorts_studio.r2_handoff.contracts import HandoffError, manifest_key, plan_id
from shorts_studio.r2_handoff.process import bounded_run


def test_coordinator_death_cannot_leave_child_with_write_authority(tmp_path):
    ready, late = tmp_path/"ready", tmp_path/"late"
    code = '''import sys
from pathlib import Path
from shorts_studio.r2_handoff.process import bounded_run
from shorts_studio.r2_handoff.state import bucket_lock
with bucket_lock(Path(sys.argv[1])/'locks',account_id='a'*32,bucket='shorts-studio-media'):
 bounded_run([sys.executable,'-c',"from pathlib import Path;import sys,time;Path(sys.argv[1]).write_text('ready');time.sleep(.7);Path(sys.argv[2]).write_text('late')",sys.argv[2],sys.argv[3]],env={'PATH':'/usr/bin'},timeout=4)
'''
    p = subprocess.Popen([sys.executable,"-c",code,str(tmp_path),str(ready),str(late)])
    try:
        end = time.monotonic()+3
        while not ready.exists() and time.monotonic()<end:
            time.sleep(.01)
        assert ready.exists()
        p.kill()
        p.wait(timeout=3)
        time.sleep(.9)
        assert not late.exists(), "child wrote after coordinator lost ownership"
    finally:
        if p.poll() is None:
            p.kill()
            p.wait()


def test_exited_leader_cannot_leave_writing_descendant(tmp_path):
    late = tmp_path/"descendant"
    descendant = f"import time;from pathlib import Path;time.sleep(.7);Path({str(late)!r}).write_text('late')"
    leader = f"import subprocess,sys;subprocess.Popen([sys.executable,'-c',{descendant!r}])"
    try:
        bounded_run([sys.executable,"-c",leader],env=dict(os.environ),timeout=.2)
    except HandoffError:
        pass
    time.sleep(.9)
    assert not late.exists()


def test_data_child_does_not_start_when_oauth_crosses_job_deadline(tmp_path):
    now = datetime.now(UTC)
    remaining = [1.0]
    calls = []
    cli = backend(tmp_path,lambda *a,**kw: calls.append(a),remaining=lambda:remaining[0])
    original = cli.acquire
    def acquire():
        remaining[0] = 0
        return original()
    cli.acquire = acquire
    source = tmp_path/"snapshot.bin"
    source.write_bytes(b"abc")
    with pytest.raises(HandoffError,match="LIMIT_REACHED"):
        cli.put(KEY,source,expected_sha256=SHA_ABC,expected_size=3)
    assert not calls and now < datetime.now(UTC)


def test_deadline_is_anchored_before_original_validation(tmp_path,monkeypatch):
    c,s,job,_staged,remote = harness(tmp_path)
    wall = datetime.now(UTC)
    clock = [wall,10.0]
    c.utc_clock = lambda:clock[0]
    c.monotonic_clock = lambda:clock[1]
    s.extend_limits(job,limits=limits(chunk_bytes=2,deadline_utc=wall+timedelta(minutes=31)),
                    operator_reason="test time window")
    import shorts_studio.r2_handoff.coordinator as module
    original = module.validate_original
    def validation(value):
        original(value)
        clock[:] = [wall-timedelta(hours=1), 10+32*60]
    monkeypatch.setattr(module,"validate_original",validation)
    with s,pytest.raises(HandoffError,match="LIMIT_REACHED"):
        c.apply(job)
    assert not remote.calls


def test_fifo_is_rejected_without_blocking(tmp_path):
    fifo = tmp_path/"source.json"
    os.mkfifo(fifo)
    code = '''from pathlib import Path
import sys
from shorts_studio.r2_handoff.contracts import source_handle,HandoffError
try:
 source_handle(Path(sys.argv[1]))
except HandoffError:
 sys.exit(2)
'''
    try:
        p = subprocess.run([sys.executable,"-c",code,str(fifo)],check=False,timeout=.5)
    except subprocess.TimeoutExpired:
        pytest.fail("non-regular source blocked before regular-file validation")
    assert p.returncode == 2


def test_growing_source_is_stopped_before_unbounded_reads(tmp_path,monkeypatch):
    source = tmp_path/"source.json"
    source.write_bytes(b"abc")
    original = contracts.source_handle
    reads = []
    class Growing:
        def __enter__(self):
            self.handle = original(source)
            return self
        def __exit__(self,*a):
            self.handle.close()
        def fileno(self):
            return self.handle.fileno()
        def read(self,n):
            reads.append(n)
            if len(reads)>3:
                pytest.fail("planning read beyond sealed source size")
            with source.open("ab") as f:
                f.write(b"growing")
            return self.handle.read(n)
    monkeypatch.setattr(contracts,"source_handle",lambda path:Growing())
    with pytest.raises(HandoffError,match="SOURCE_CHANGED"):
        contracts.plan_source(source,account_id=ACCOUNT,bucket="shorts-studio-media",
             namespace="episode2",limits=limits(chunk_bytes=2),expected_sha256=None,provenance={})


def test_expired_verify_can_extend_same_readonly_job_with_consumed_counters(tmp_path):
    c,s,job,staged,remote = harness(tmp_path)
    with s:
        c.apply(job)
        args = {"account_id": ACCOUNT,"bucket": staged.manifest.bucket,"namespace": "episode2",
            "manifest_key": manifest_key(staged.manifest),"expected_manifest_sha256": plan_id(staged.manifest),
            "destination": tmp_path/"independent.json"}
        with pytest.raises(HandoffError,match="LIMIT_REACHED") as failed:
            c.verify(**args,limits=limits(deadline_utc=datetime.now(UTC)-timedelta(seconds=1)))
        assert failed.value.job_id.startswith("verify-")
        restore_job = failed.value.job_id
        consumed = s.status(restore_job)["data_used"]
        remote.calls.clear()
        result = c.resume(restore_job,limits=limits(deadline_utc=datetime.now(UTC)+timedelta(hours=1)),
                          operator_reason="restore deadline explicitly extended")
        assert result.status == "DOWNLOAD_VERIFIED" and result.job_id == restore_job
        assert s.status(restore_job)["data_used"] >= consumed+4
        assert all(op == "get" for op,key in remote.calls)
        assert args["destination"].read_bytes() == b"abcdef"


def test_no_free_disk_blocks_before_credentials_or_any_remote_attempt(tmp_path,monkeypatch):
    import shutil
    from collections import namedtuple
    c,s,job,_staged,remote = harness(tmp_path)
    with s:
        c.apply(job)
        remote.calls.clear()
        before = s.status(job)["data_used"]
        monkeypatch.setattr(shutil,"disk_usage",lambda path:namedtuple("disk","total used free")(1,1,0))
        with pytest.raises(HandoffError,match="DISK_LIMIT"):
            c.resume(job)
        assert not remote.calls
        assert s.status(job)["data_used"] == before
