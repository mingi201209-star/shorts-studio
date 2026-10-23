"""Coordinator + real state/adapter with filesystem-backed cloud boundary."""
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from shorts_studio.r2_handoff.contracts import HandoffError, manifest_key, plan_id
from shorts_studio.r2_handoff.coordinator import Coordinator
from shorts_studio.r2_handoff.oauth import OAuthGrant
from shorts_studio.r2_handoff.staging import stage_source
from shorts_studio.r2_handoff.state import StateStore, bucket_lock
from shorts_studio.r2_handoff.wrangler import WranglerBackend
from test_r2_handoff_contracts import ACCOUNT, limits, plan


class DiskCloud:
    def __init__(self, root, phase=None):
        self.root = root
        root.mkdir(mode=0o700, exist_ok=True)
        self.phase, self.calls = phase, []

    def object(self, key):
        return self.root / hashlib.sha256(key.encode()).hexdigest()

    def kill(self, phase):
        marker = self.root / "killed"
        if self.phase == phase and not marker.exists():
            marker.write_text(phase)
            os._exit(27)

    def __call__(self, argv, **kw):
        op, key = argv[3], argv[4].split("/",1)[1]
        file = Path(argv[argv.index("--file")+1])
        self.calls.append((op,key))
        remote = self.object(key)
        if op == "get":
            if not remote.exists():
                return subprocess.CompletedProcess(argv,1,"","The specified key does not exist.")
            file.write_bytes(remote.read_bytes())
            self.kill("after_readback")
            if "reconstruction-" in str(file):
                self.kill("during_reconstruction")
        else:
            self.kill("before_put")
            remote.write_bytes(file.read_bytes())
            self.kill("after_manifest" if "/manifests/" in key else "after_put")
        return subprocess.CompletedProcess(argv,0,"","")


def harness(tmp_path, *, existing=False, phase=None):
    if not existing:
        m = plan(tmp_path, raw=b"abcdef", chunk_bytes=2)
        staged = stage_source(tmp_path / "sample.json", root=tmp_path / "spool", planned=m)
    store = StateStore(tmp_path / "state/jobs.sqlite")
    if not existing:
        job = store.create_job(staged, limits(chunk_bytes=2))
        (tmp_path / "job").write_text(job)
    else:
        job = (tmp_path / "job").read_text()
        staged, _ = store.load_job(job)
    cloud = DiskCloud(tmp_path / "remote", phase)
    def factory(job_id):
        def reserve(op):
            opid = hashlib.sha256(op.encode()).hexdigest()
            for kind in ("data", "token"):
                store.reserve(job_id, kind=kind, operation_id=opid,
                              utc_now=datetime.now(timezone.utc), monotonic_now=time.monotonic())
        return WranglerBackend(Path("fixture-wrangler"), account_id=ACCOUNT,
            bucket="shorts-studio-media", home=tmp_path,
            acquire=lambda: OAuthGrant("test",datetime(2099,1,1,tzinfo=timezone.utc)),
            before_call=reserve, runner=cloud, missing_key_verified=True)
    coordinator = Coordinator(store, factory, lock_root=tmp_path / "locks",
                              utc_clock=lambda: datetime.now(timezone.utc),
                              monotonic_clock=time.monotonic)
    return coordinator, store, job, staged, cloud


def test_new_job_uploads_manifest_last_and_reconstructs_complete_sha(tmp_path):
    c,s,job,staged,remote = harness(tmp_path)
    with s:
        result = c.apply(job)
        assert result.status == "REMOTE_VERIFIED"
        assert result.sha256 == hashlib.sha256(b"abcdef").hexdigest()
        assert result.media_status == "MEDIA_QA_PENDING" and result.upload_authorized is False
        puts = [key for op,key in remote.calls if op == "put"]
        assert puts[-1] == manifest_key(staged.manifest)
        assert s.status(job)["data_used"] == 16
        assert (tmp_path / "sample.json").read_bytes() == b"abcdef"


def test_resume_rechecks_every_remote_chunk_even_if_local_state_says_done(tmp_path):
    c,s,job,staged,remote = harness(tmp_path)
    with s:
        c.apply(job)
        remote.calls.clear()
        assert c.resume(job).status == "REMOTE_VERIFIED"
        assert all(("get",chunk.key) in remote.calls for chunk in staged.manifest.chunks)
        assert not any(op == "put" for op,key in remote.calls)


def test_existing_wrong_chunk_blocks_without_overwrite(tmp_path):
    c,s,job,staged,remote = harness(tmp_path)
    key = staged.manifest.chunks[0].key
    remote.object(key).write_bytes(b"wrong")
    with s, pytest.raises(HandoffError):
        c.apply(job)
    assert remote.object(key).read_bytes() == b"wrong"
    assert not any(op == "put" for op,key in remote.calls)


def test_uncertain_put_reconciles_before_retry(tmp_path):
    c,s,job,staged,remote = harness(tmp_path)
    original = remote.__class__.__call__
    class TimeoutAfterWrite(DiskCloud):
        lost = False
        def __call__(self, argv, **kw):
            result = original(self, argv, **kw)
            if argv[3] == "put" and not self.lost:
                self.lost = True
                raise HandoffError("CHILD_TIMEOUT")
            return result
    remote.__class__ = TimeoutAfterWrite
    with s:
        assert c.apply(job).status == "REMOTE_VERIFIED"
    key = staged.manifest.chunks[0].key
    assert remote.calls.count(("put",key)) == 1


def test_source_changes_on_existing_object_path_never_return_success(tmp_path):
    c,s,job,staged,remote = harness(tmp_path)
    with s:
        c.apply(job)
        (tmp_path / "sample.json").write_bytes(b"changed")
        with pytest.raises(HandoffError, match="SOURCE_CHANGED"):
            c.resume(job)
        assert s.status(job)["state"] == "SOURCE_CHANGED"


def test_verify_without_original_is_get_only_download_verified(tmp_path):
    c,s,job,staged,remote = harness(tmp_path)
    with s:
        c.apply(job)
        (tmp_path / "sample.json").unlink()
        remote.calls.clear()
        out = tmp_path / "independent.json"
        receipt = c.verify(account_id=ACCOUNT, bucket=staged.manifest.bucket,
            namespace="episode2", manifest_key=manifest_key(staged.manifest),
            expected_manifest_sha256=plan_id(staged.manifest), destination=out, limits=limits())
        assert receipt.status == "DOWNLOAD_VERIFIED" and out.read_bytes() == b"abcdef"
        assert len(remote.calls) == 4 and all(op == "get" for op,key in remote.calls)
        assert s.status(job)["state"] == "REMOTE_VERIFIED"


def test_limit_or_auth_side_state_releases_locks_and_keeps_checkpoint(tmp_path):
    c,s,job,staged,remote = harness(tmp_path)
    def blocked(job_id):
        raise HandoffError("AUTH_REQUIRED")
    c.backend_factory = blocked
    with s:
        with pytest.raises(HandoffError, match="AUTH_REQUIRED"):
            c.apply(job)
        assert s.status(job)["state"] == "AUTH_REQUIRED"
        with bucket_lock(tmp_path / "locks", account_id=ACCOUNT, bucket=staged.manifest.bucket):
            assert staged.spool.exists()


@pytest.mark.parametrize("phase", ["before_put", "after_put", "after_readback", "before_commit",
                                    "after_manifest", "during_reconstruction"])
def test_kill_and_resume_at_each_persistence_boundary(tmp_path, phase):
    c,s,job,staged,remote = harness(tmp_path)
    s.close()
    code = '''import os,sys
from pathlib import Path
from test_r2_handoff_coordinator import harness
c,s,job,staged,remote=harness(Path(sys.argv[1]),existing=True,phase=sys.argv[2])
if sys.argv[2]=='before_commit':
 original=s.transition
 def transition(*a,**kw):
  if kw.get('chunk_index')==0 and not (remote.root/'killed').exists():
   s.db.execute('BEGIN IMMEDIATE')
   s.db.execute("UPDATE jobs SET state='TRANSFERRING' WHERE id=?",(job,))
   (remote.root/'killed').write_text('commit')
   os._exit(27)
  return original(*a,**kw)
 s.transition=transition
c.apply(job)
'''
    p = subprocess.run([sys.executable,"-c",code,str(tmp_path),phase],
                       env=dict(os.environ, PYTHONPATH=str(Path(__file__).parent)), timeout=15)
    assert p.returncode == 27
    c,s,job,staged,remote = harness(tmp_path,existing=True)
    with s:
        before = s.status(job)["data_used"]
        assert before > 0
        assert c.resume(job).status == "REMOTE_VERIFIED"
        assert s.status(job)["data_used"] >= before
        assert staged.source.read_bytes() == b"abcdef" and staged.spool.exists()
