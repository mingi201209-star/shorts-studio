"""Operator-facing subprocess checks; all work stays local and mocked."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from shorts_studio.asset_factory.controller.contracts import JobSpec
from shorts_studio.asset_factory.controller.database import open_controller_db
from shorts_studio.asset_factory.controller.queue import enqueue

MODULE = 'shorts_studio.asset_factory.controller'
SECRET = 'sentinel-private-value-never-print'


def cli(*args, env=None):
    return subprocess.run([sys.executable, '-m', MODULE, *map(str, args)],
                          check=False, capture_output=True, text=True, timeout=10, env=env)


def ok(*args):
    result = cli(*args)
    assert result.returncode == 0, result.stderr
    return result.stdout


def seed(db):
    ok('init', '--db', db)
    ok('enqueue-mock', '--db', db, '--id', 'pilot', '--source-sha', 'a' * 40,
       '--input-digest', 'b' * 64)


def test_init_enqueue_step_status_roundtrip(tmp_path):
    db = tmp_path / 'state.db'
    seed(db)
    assert json.loads(ok('status', '--db', db, '--json'))['queued'] == 1
    assert 'completed_mock' in ok('step', '--db', db, '--storage', tmp_path / 'objects',
                                  '--mock-only')
    status = json.loads(ok('status', '--db', db, '--json'))
    assert status['completed_mock'] == status['receipts'] == 1
    assert status['queued'] == status['blocked'] == 0
    assert status['schema_version'] == 1
    assert status['last_event'] is not None
    snapshot = tmp_path / 'snapshot.db'
    digest = ok('snapshot', '--db', db, '--dest', snapshot).strip()
    assert snapshot.with_suffix('.db.sha256').read_text().strip() == digest
    restored = tmp_path / 'restored.db'
    ok('recover', '--source', snapshot, '--expected-sha256', digest, '--db', restored)
    assert json.loads(ok('status', '--db', restored, '--json')) == status


def test_status_without_db_fails_cleanly(tmp_path):
    db = tmp_path / 'missing.db'
    result = cli('status', '--db', db, '--json')
    assert result.returncode != 0
    assert 'Traceback' not in result.stderr
    assert not db.exists()


@pytest.mark.parametrize('content', [b'not sqlite', b''])
def test_invalid_db_fails_cleanly(tmp_path, content):
    db = tmp_path / 'invalid.db'
    db.write_bytes(content)
    result = cli('status', '--db', db, '--json')
    assert result.returncode != 0
    assert 'Traceback' not in result.stderr
    assert db.read_bytes() == content


def test_recover_bad_digest_keeps_original(tmp_path):
    db = tmp_path / 'state.db'
    seed(db)
    snapshot = tmp_path / 'snapshot.db'
    ok('snapshot', '--db', db, '--dest', snapshot)
    before = db.read_bytes()
    result = cli('recover', '--source', snapshot, '--expected-sha256', '0' * 64, '--db', db)
    assert result.returncode != 0
    assert 'Traceback' not in result.stderr
    assert db.read_bytes() == before


def test_cli_never_dispatches_codex_or_renderer_by_default(tmp_path):
    db = tmp_path / 'state.db'
    seed(db)
    conn = open_controller_db(db)
    enqueue(conn, JobSpec('codex', 'mock', '1', 'a' * 40, 'b' * 64, 'probe', 'codex', '{}'))
    conn.close()
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    marker = tmp_path / 'dispatch'
    for name in ('codex', 'blender', 'ffmpeg', 'curl', 'gh'):
        executable = bin_dir / name
        executable.write_text(f'#!/bin/sh\ntouch "{marker}"\nexit 99\n')
        executable.chmod(0o700)
    env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ['PATH'])
    for command in ('step', 'serve'):
        result = cli(command, '--db', db, '--storage', tmp_path / 'objects', env=env)
        assert result.returncode != 0  # explicit mock-only admission required
    for _ in range(2):
        result = cli('step', '--db', db, '--storage', tmp_path / 'objects',
                     '--mock-only', env=env)
        assert result.returncode == 0, result.stderr
    assert not marker.exists()
    assert json.loads(ok('status', '--db', db, '--json'))['blocked'] == 1


def test_mock_serve_stops_after_two_ticks(tmp_path):
    db = tmp_path / 'state.db'
    seed(db)
    output = ok('serve', '--db', db, '--storage', tmp_path / 'objects', '--mock-only',
                '--poll-seconds', '0.01', '--max-ticks', '2')
    assert output.splitlines() == ['completed_mock', 'idle']


def test_no_secret_in_status_or_runbook(tmp_path):
    db = tmp_path / 'state.db'
    seed(db)
    conn = open_controller_db(db)
    conn.execute('UPDATE events SET detail=?, job_id=job_id', (SECRET,))
    conn.commit()
    conn.close()
    env = dict(os.environ, OPENAI_API_KEY=SECRET)
    result = cli('status', '--db', db, '--json', env=env)
    assert result.returncode == 0, result.stderr
    assert SECRET not in result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert 'detail' not in report['last_event']
    runbook = Path('docs/operations/asset-controller-pilot.md').read_text()
    assert SECRET not in runbook
    assert 'do not install or enable' in runbook.lower()


def test_service_template_is_inert_and_mock_only():
    unit = Path('deploy/systemd/shorts-asset-controller.service').read_text()
    assert 'serve' in unit and '--mock-only --poll-seconds 60' in unit
    assert 'Restart=on-failure' in unit
    assert 'User=shorts-asset-controller' in unit
    assert 'ConditionPathExists=' in unit
    assert '[Install]' not in unit


def test_serve_sigterm_interrupts_long_poll(tmp_path):
    db = tmp_path / 'state.db'
    seed(db)
    process = subprocess.Popen(
        [sys.executable, '-m', MODULE, 'serve', '--db', str(db), '--storage',
         str(tmp_path / 'objects'), '--mock-only', '--poll-seconds', '60'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        # Wait for a committed tick and installed signal handlers before SIGTERM.
        import selectors
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            assert selector.select(timeout=5)
            assert process.stdout.readline().strip() == 'completed_mock'
        process.terminate()
        _, stderr = process.communicate(timeout=5)
        assert process.returncode == 0, stderr
        assert json.loads(ok('status', '--db', db, '--json'))['receipts'] == 1
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()


@pytest.mark.parametrize('flag,value', [('--poll-seconds', 'nan'), ('--poll-seconds', '0'),
                                       ('--max-ticks', '0')])
def test_serve_invalid_bounds_fail_before_work(tmp_path, flag, value):
    db = tmp_path / 'state.db'
    seed(db)
    result = cli('serve', '--db', db, '--storage', tmp_path / 'objects', '--mock-only',
                 flag, value)
    assert result.returncode != 0
    assert json.loads(ok('status', '--db', db, '--json'))['queued'] == 1


def test_restart_tick_blocks_persisted_expired_lease(tmp_path):
    from shorts_studio.asset_factory.controller.queue import claim_next

    db = tmp_path / 'state.db'
    seed(db)
    conn = open_controller_db(db)
    assert claim_next(conn, 'dead-process', 1, 1) is not None
    conn.close()  # Simulate persisted claim left by a killed worker.
    report = json.loads(ok('status', '--db', db, '--json'))
    before = report
    ok('step', '--db', db, '--storage', tmp_path / 'objects', '--mock-only')
    report = json.loads(ok('status', '--db', db, '--json'))
    assert report['blocked'] == 1
    assert before['running'] == before['expired_leases'] == 1
    assert report['running'] == report['expired_leases'] == report['receipts'] == 0
    conn = open_controller_db(db)
    try:
        assert conn.execute('SELECT attempt_count FROM jobs').fetchone() == (1,)
        assert conn.execute('SELECT outcome FROM attempts').fetchone() == ('blocked',)
    finally:
        conn.close()
