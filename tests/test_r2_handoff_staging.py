"""Real files and a competing process exercise preservation and installation."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys

import pytest

from shorts_studio.r2_handoff.contracts import HandoffError
from shorts_studio.r2_handoff.staging import (
    restore_file, stage_source, validate_original, validate_staged,
)
from test_r2_handoff_contracts import plan


def test_chunk_snapshot_and_full_digest_agree(tmp_path):
    m = plan(tmp_path, raw=b"abcdef", chunk_bytes=2)
    source = tmp_path / "sample.json"
    s = stage_source(source, root=tmp_path / "spool", planned=m)
    validate_staged(s)
    validate_original(s)
    out = tmp_path / "restored.json"
    def fetch(c, dest):
        dest.write_bytes((s.spool / f"{c.index}.bin").read_bytes())
    restore_file(m, destination=out, fetch=fetch)
    assert out.read_bytes() == source.read_bytes() == b"abcdef"
    assert hashlib.sha256(out.read_bytes()).hexdigest() == m.sha256
    assert s.spool.stat().st_mode & 0o077 == 0


def test_staging_rejects_source_replacement_and_preserves_source(tmp_path):
    m = plan(tmp_path)
    f = tmp_path / "sample.json"
    f.write_bytes(b"wrong")
    with pytest.raises(HandoffError):
        stage_source(f, root=tmp_path / "spool", planned=m)
    assert f.read_bytes() == b"wrong"
    m = plan(tmp_path)
    s = stage_source(f, root=tmp_path / "good", planned=m)
    f.unlink()
    f.symlink_to(s.spool / "0.bin")
    with pytest.raises(HandoffError):
        validate_original(s)
    assert s.spool.exists()
    (s.spool / "0.bin").chmod(0o600)
    (s.spool / "0.bin").write_bytes(b"bad")
    with pytest.raises(HandoffError):
        validate_staged(s)


@pytest.mark.parametrize("race", [False, True])
def test_restore_existing_or_raced_destination_is_never_replaced(tmp_path, monkeypatch, race):
    m = plan(tmp_path)
    out = tmp_path / "target.json"
    if not race:
        out.write_bytes(b"owner-data")
    original_link = os.link
    def racing_link(src, dst, **kw):
        subprocess.run([sys.executable, "-c", "from pathlib import Path; import sys; "
                        "Path(sys.argv[1]).write_bytes(b'owner-data')", str(dst)], check=True)
        original_link(src, dst, **kw)
    if race:
        monkeypatch.setattr(os, "link", racing_link)
    with pytest.raises(HandoffError):
        restore_file(m, destination=out, fetch=lambda c, p: p.write_bytes(b"abc"))
    assert out.read_bytes() == b"owner-data"


def test_disk_floor_blocks_before_staging_or_readback(tmp_path, monkeypatch):
    from collections import namedtuple
    import shutil
    m = plan(tmp_path)
    disk = namedtuple("disk", "total used free")(100, 99, 1)
    monkeypatch.setattr(shutil, "disk_usage", lambda p: disk)
    with pytest.raises(HandoffError, match="DISK_LIMIT"):
        stage_source(tmp_path / "sample.json", root=tmp_path / "spool", planned=m)
    calls = []
    with pytest.raises(HandoffError, match="DISK_LIMIT"):
        restore_file(m, destination=tmp_path / "out.json", fetch=lambda *a: calls.append(a))
    assert not calls
    assert (tmp_path / "sample.json").read_bytes() == b"abc"


def test_corrupt_readback_never_installs_destination(tmp_path):
    m = plan(tmp_path)
    out = tmp_path / "out.json"
    with pytest.raises(HandoffError):
        restore_file(m, destination=out, fetch=lambda c, p: p.write_bytes(b"bad"))
    assert not out.exists()
