"""Deterministic, bounded diagnostic work with no external side effects."""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path

from .contracts import JobSpec


class MockWorker:
    """Produce proof bytes only; these are never native frames or production QA."""

    def run(self, job: JobSpec) -> bytes:
        if job.worker_kind != 'mock' or Decimal(job.budget_usd) != 0:
            raise ValueError('mock worker requires a zero-cost mock job')
        identity = json.dumps(asdict(job), sort_keys=True, separators=(',', ':'))
        digest = hashlib.sha256(identity.encode()).hexdigest()
        return f'mock-proof-v1; diagnostic only; no production QA\n{digest}\n'.encode()


@dataclass(frozen=True)
class CodexProbeResult:
    """Local scratch evidence only, never a queue completion receipt."""

    status: str
    reason: str
    output_sha256: str | None
    expected_head: str
    tests_passed: bool
    changed_files: tuple[str, ...]


class _ProbeBlocked(Exception):
    pass


def _probe_path(root: Path, name: str) -> Path:
    if (not isinstance(name, str) or not name or '\\' in name
            or any(part in ('', '.', '..') or part.startswith('-')
                   for part in name.split('/'))
            or any(ord(char) < 32 for char in name)
            or '.git' in Path(name).parts or Path(name).is_absolute()):
        raise _ProbeBlocked('invalid workspace path')
    path = root / name
    if not path.resolve().is_relative_to(root):
        raise _ProbeBlocked('path escapes workspace')
    if any(parent.is_symlink() for parent in (path, *path.parents) if parent != root):
        raise _ProbeBlocked('symlink path refused')
    return path


class CodexWorker:
    """Explicitly enabled, bounded scratch adapter; no runner integration.

    The caller authorizes the prompt and expected file scope in a fresh isolated
    worktree. Pytest executes that workspace's code and is not a security sandbox.
    External output is deliberately omitted from public checkpoint reasons.
    """

    def run(self, job: JobSpec, *, workspace: Path, expected_head: str,
            expected_files: tuple[str, ...], test_command: tuple[str, ...],
            timeout_seconds: int, enabled: bool = False,
            run_process: Callable[..., object] = subprocess.run) -> CodexProbeResult:
        def blocked(reason):
            return CodexProbeResult('blocked', reason, None, expected_head, False, ())

        if not enabled:
            return blocked('Codex probe disabled')
        try:
            if (job.worker_kind != 'codex' or Decimal(job.budget_usd) != 0
                    or re.fullmatch('[0-9a-f]{40}', expected_head) is None
                    or job.source_sha != expected_head
                    or type(timeout_seconds) is not int or timeout_seconds <= 0
                    or timeout_seconds > 3600):
                raise _ProbeBlocked('invalid zero-cost probe identity or timeout')
            root = Path(workspace).absolute()
            if root.resolve() != root or not root.is_dir():
                raise _ProbeBlocked('workspace must be a real directory')
            if (not isinstance(expected_files, tuple) or not expected_files
                    or len(set(expected_files)) != len(expected_files)):
                raise _ProbeBlocked('expected file scope required')
            paths = {name: _probe_path(root, name) for name in expected_files}
            # Fixed interpreter and module, no pytest configuration/plugin switches,
            # shell snippets, directories or arbitrary executable selection.
            if (not isinstance(test_command, tuple) or len(test_command) < 4
                    or test_command[:3] != (sys.executable, '-m', 'pytest')):
                raise _ProbeBlocked('test command must be explicit Python pytest')
            tests = test_command[3:]
            if tests and tests[0] == '-q':
                tests = tests[1:]
            if not tests:
                raise _ProbeBlocked('explicit test files required')
            test_paths = [_probe_path(root, name) for name in tests]
            if any(not p.is_file() or p.suffix != '.py' or not p.name.startswith('test_')
                   for p in test_paths):
                raise _ProbeBlocked('explicit existing pytest files required')
            if set(tests) & set(expected_files):
                raise _ProbeBlocked('verification tests must be outside edit scope')
            test_hashes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in test_paths]
            payload = json.loads(job.payload_json)
            if (not isinstance(payload, dict) or set(payload) != {'prompt'}
                    or not isinstance(payload['prompt'], str) or not payload['prompt'].strip()
                    or len(payload['prompt']) > 16000):
                raise _ProbeBlocked('explicit scoped task prompt required')
            deadline = time.monotonic() + timeout_seconds
            env = {key: os.environ[key] for key in ('PATH', 'HOME', 'LANG') if key in os.environ}
            env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                       GIT_TERMINAL_PROMPT='0', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')

            def execute(args, allowed=(0,)):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise _ProbeBlocked('probe timeout; checkpoint retained')
                result = run_process(args, cwd=root, shell=False, capture_output=True,
                                     text=True, timeout=remaining, env=env.copy())
                output = (result.stdout or '') + '\n' + (result.stderr or '')
                if re.search(r'quota|rate.?limit|usage.?limit|unauthorized|'
                             r'authentication|login required|session expired', output, re.IGNORECASE):
                    raise _ProbeBlocked('provider unavailable; checkpoint retained')
                if result.returncode not in allowed:
                    raise _ProbeBlocked('process failed; checkpoint retained')
                return result.stdout or ''

            def git(*args, allowed=(0,)):
                return execute(['git', '--no-optional-locks', '-c', 'core.fsmonitor=false',
                                '-c', f'core.hooksPath={os.devnull}', *args], allowed)

            def head():
                if git('rev-parse', '--verify', 'HEAD').strip() != expected_head:
                    raise _ProbeBlocked('Git HEAD drift')

            head()
            if Path(git('rev-parse', '--show-toplevel').strip()).resolve() != root:
                raise _ProbeBlocked('workspace must be the repository root')
            if git('status', '--porcelain=v1', '-z', '--untracked-files=all'):
                raise _ProbeBlocked('fresh clean worktree required')
            with tempfile.TemporaryDirectory(prefix='codex-probe-') as diagnostic:
                prompt = (f'Scratch probe only. Edit only {json.dumps(expected_files)}. '
                          'Do not commit, publish, push, upload, use paid APIs, access secrets, '
                          'or modify tests. No provider fallback. Task: ' + payload['prompt'])
                execute(['codex', 'exec', '--sandbox', 'workspace-write', '--ephemeral',
                         '-c', 'model_provider="openai"', '-c', 'forced_login_method="chatgpt"',
                         '--output-last-message', str(Path(diagnostic) / 'last-message.txt'),
                         '--', prompt])

            def audit():
                head()
                status = git('status', '--porcelain=v1', '-z', '--untracked-files=all')
                entries = status.split('\0')
                changed = []
                for entry in entries:
                    if not entry:
                        continue
                    if entry[:3] not in (' M ', 'M  ', 'MM ', '?? ', ' A ', 'A  '):
                        raise _ProbeBlocked('unsupported workspace change')
                    name = entry[3:]
                    _probe_path(root, name)
                    changed.append(name)
                if set(changed) != set(expected_files):
                    raise _ProbeBlocked('expected files missing or scope changed')
                hashes = {}
                for name, path in paths.items():
                    _probe_path(root, name)
                    if not path.is_file() or not path.stat().st_size:
                        raise _ProbeBlocked('expected nonempty file missing')
                    hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
                diff = git('diff', '--no-ext-diff', '--no-textconv', 'HEAD', '--', *expected_files)
                for entry in entries:
                    if entry.startswith('?? '):
                        diff += git('diff', '--no-ext-diff', '--no-textconv', '--no-index',
                                    '--', os.devnull, entry[3:], allowed=(1,))
                if not diff.strip():
                    raise _ProbeBlocked('nonempty audited diff required')
                if any(_probe_path(root, name) != path for name, path in zip(tests, test_paths)):
                    raise _ProbeBlocked('verification test path changed')
                if test_hashes != [hashlib.sha256(p.read_bytes()).hexdigest() for p in test_paths]:
                    raise _ProbeBlocked('verification tests changed')
                return hashes, hashlib.sha256(diff.encode()).hexdigest()

            before = audit()
            output = execute([*test_command[:3], '-c', os.devnull, '--noconftest',
                              '--override-ini=addopts=', *test_command[3:]])
            if not re.search(r'\b[1-9][0-9]* passed\b', output):
                raise _ProbeBlocked('required tests did not report passing tests')
            if audit() != before:
                raise _ProbeBlocked('workspace changed during verification')
            digest = hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest()
            return CodexProbeResult('success', 'verified scratch diff, files and tests',
                                    digest, expected_head, True, tuple(sorted(expected_files)))
        except _ProbeBlocked as exc:
            return blocked(str(exc))
        except (subprocess.TimeoutExpired, TimeoutError):
            return blocked('probe timeout; checkpoint retained')
        except Exception:  # noqa: BLE001 - redact all injected process errors
            # Never expose exception text, commands, prompts, credentials or output.
            return blocked('probe validation or process error; checkpoint retained')
