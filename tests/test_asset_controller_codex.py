"""No live Codex: independently audited subprocess probe behavior."""

import hashlib
import subprocess
import sys
from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest

from shorts_studio.asset_factory.controller.contracts import JobSpec
from shorts_studio.asset_factory.controller.workers import CodexProbeResult, CodexWorker

HEAD = 'a' * 40


class FakeProcess:
    def __init__(self, root, mode='ok'):
        self.root, self.mode, self.calls = root, mode, []
        self.executed = False

    def __call__(self, args, **kwargs):
        self.calls.append(args)
        assert kwargs['shell'] is False
        assert kwargs['timeout'] > 0
        assert kwargs['cwd'] == self.root
        out, code = '', 0
        if args[0] == 'codex':
            self.executed = True
            assert args[1:5] == ['exec', '--sandbox', 'workspace-write', '--ephemeral']
            if self.mode == 'timeout':
                raise subprocess.TimeoutExpired(args, 1, output='sk-secret-token')
            if self.mode == 'quota':
                out = 'quota exceeded Bearer secret-token'
            elif self.mode != 'empty':
                (self.root / 'proof.py').write_text('answer = 42\n')
        elif args[0] == sys.executable:
            out = '1 passed in 0.01s'
            if self.mode == 'testfail':
                code = 1
            if self.mode == 'no-tests':
                out = 'no tests ran'
        elif '--show-toplevel' in args:
            out = str(self.root)
        elif 'rev-parse' in args:
            out = ('b' * 40 if self.mode == 'drift' and self.executed else HEAD) + '\n'
        elif 'status' in args:
            out = ' M proof.py\0' if self.executed and self.mode != 'empty' else ''
            if self.mode == 'foreign' and self.executed:
                out += ' M outside.py\0'
        elif 'diff' in args:
            out = '' if self.mode == 'no-diff' else 'diff --git a/proof.py b/proof.py\n+answer = 42\n'
        else:
            raise AssertionError(args)
        return SimpleNamespace(returncode=code, stdout=out, stderr='')


def probe(tmp_path, mode='ok', **changes):
    (tmp_path / 'test_proof.py').write_text('def test_answer(): assert True\n')
    fake = FakeProcess(tmp_path, mode)
    options = {'workspace': tmp_path, 'expected_head': HEAD, 'expected_files': ('proof.py',),
                   'test_command': (sys.executable, '-m', 'pytest', '-q', 'test_proof.py'),
                   'timeout_seconds': 10, 'enabled': True, 'run_process': fake}
    options.update(changes)
    job = JobSpec('probe', 'scratch', 'v1', HEAD, 'b' * 64, 'proof', 'codex',
                  '{"prompt":"Create proof.py with answer = 42; scratch only"}')
    return CodexWorker().run(job, **options), fake


def test_codex_disabled_never_invokes_process(tmp_path):
    result, fake = probe(tmp_path, enabled=False)
    assert result.status == 'blocked'
    assert not fake.calls


def test_zero_exit_without_receipt_is_not_success(tmp_path):
    result, _ = probe(tmp_path, 'empty')
    assert result.status == 'blocked'
    assert result.output_sha256 is None


@pytest.mark.parametrize('mode', ['quota', 'drift'])
def test_quota_or_sha_drift_blocks(tmp_path, mode):
    result, _ = probe(tmp_path, mode)
    assert result.status == 'blocked'
    assert 'secret-token' not in repr(result)


def test_codex_timeout_is_checkpointed(tmp_path):
    result, _ = probe(tmp_path, 'timeout')
    assert result.status == 'blocked'
    assert 'timeout' in result.reason
    assert 'sk-secret' not in repr(result)


@pytest.mark.parametrize('mode', ['ok', 'testfail', 'no-tests', 'no-diff', 'foreign'])
def test_valid_scratch_outputs_require_verified_tests_and_diff(tmp_path, mode):
    result, fake = probe(tmp_path, mode)
    assert isinstance(result, CodexProbeResult)
    assert (result.status == 'success') == (mode == 'ok')
    if mode == 'ok':
        assert result.tests_passed
        assert result.changed_files == ('proof.py',)
        assert len(result.output_sha256) == len(hashlib.sha256().hexdigest())
        assert any(call[0] == sys.executable for call in fake.calls)
        with pytest.raises(FrozenInstanceError):
            result.status = 'blocked'


@pytest.mark.parametrize('command', [('sh', '-c', 'touch danger'),
                                    ('python', '-c', 'print(1)'),
                                    (sys.executable, '-m', 'pytest', '-p', 'evil')])
def test_unsafe_test_command_never_dispatches(tmp_path, command):
    result, fake = probe(tmp_path, test_command=command)
    assert result.status == 'blocked'
    assert not fake.calls


@pytest.mark.parametrize('path', ['../escape.py', '/tmp/escape.py', '.git/config'])
def test_expected_paths_cannot_escape_workspace(tmp_path, path):
    result, fake = probe(tmp_path, expected_files=(path,))
    assert result.status == 'blocked'
    assert not fake.calls


@pytest.mark.parametrize('passing', [True, False])
def test_fake_codex_with_real_git_and_pytest(tmp_path, passing):
    """Fake only Codex; actual Git audits and pytest determine acceptance."""
    def command(args):
        return subprocess.run(args, cwd=tmp_path, shell=False, check=True,
                              capture_output=True, text=True, timeout=10)

    command(['git', 'init', '-q'])
    command(['git', 'config', 'user.name', 'Scratch Test'])
    command(['git', 'config', 'user.email', 'scratch@example.invalid'])
    (tmp_path / 'proof.py').write_text('answer = 0\n')
    (tmp_path / '.gitignore').write_text('__pycache__/\n.pytest_cache/\n')
    (tmp_path / 'test_proof.py').write_text(
        'from proof import answer\ndef test_answer(): assert answer == 42\n')
    command(['git', 'add', '.'])
    command(['git', 'commit', '-qm', 'scratch baseline'])
    head = command(['git', 'rev-parse', 'HEAD']).stdout.strip()
    spec = JobSpec('probe', 'scratch', 'v1', head, 'b' * 64, 'proof', 'codex',
                   '{"prompt":"Set proof.py answer to 42"}')
    calls = []

    def fake_codex(args, **kwargs):
        calls.append(args)
        if args[0] == 'codex':
            (tmp_path / 'proof.py').write_text(f'answer = {42 if passing else 7}\n')
            return subprocess.CompletedProcess(args, 0, 'done', '')
        return subprocess.run(args, check=False, **kwargs)

    result = CodexWorker().run(
        spec, workspace=tmp_path, expected_head=head, expected_files=('proof.py',),
        test_command=(sys.executable, '-m', 'pytest', '-q', 'test_proof.py'),
        timeout_seconds=30, enabled=True, run_process=fake_codex)
    assert (result.status == 'success') == passing, result.reason
    assert any(args[0] == sys.executable for args in calls)


def test_symlink_expected_file_blocks_before_dispatch(tmp_path):
    (tmp_path / 'proof.py').symlink_to(tmp_path / 'target.py')
    result, fake = probe(tmp_path)
    assert result.status == 'blocked'
    assert not fake.calls


def test_error_details_are_redacted(tmp_path):
    def broken(*args, **kwargs):
        raise RuntimeError('Bearer private-token https://user:password@example.invalid')

    result, _ = probe(tmp_path, run_process=broken)
    assert result.status == 'blocked'
    assert 'private-token' not in repr(result)
    assert 'password' not in repr(result)
