"""Mock dispatch safety and durable diagnostic receipts."""

from dataclasses import replace

import pytest

from shorts_studio.asset_factory.controller import runner
from shorts_studio.asset_factory.controller.artifacts import LocalArtifactStore
from shorts_studio.asset_factory.controller.contracts import ArtifactReceipt, JobSpec
from shorts_studio.asset_factory.controller.database import open_controller_db
from shorts_studio.asset_factory.controller.queue import enqueue
from shorts_studio.asset_factory.controller.workers import MockWorker


@pytest.fixture
def setup(tmp_path):
    conn = open_controller_db(tmp_path / 'controller.db')
    store = LocalArtifactStore(tmp_path / 'objects')
    yield conn, store
    conn.close()


def job(**changes):
    return replace(JobSpec('job', 'asset', 'v1', 'a' * 40, 'b' * 64,
                           'proof', 'mock', '{}'), **changes)


class SpyWorker(MockWorker):
    def __init__(self):
        self.calls = []

    def run(self, spec):
        self.calls.append(spec.job_id)
        return super().run(spec)


def tick(setup, worker=None, **kwargs):
    conn, store = setup
    return runner.run_once(conn, store, worker=worker or MockWorker(),
                           now=kwargs.pop('now', 10),
                           disk_free_ratio=kwargs.pop('disk_free_ratio', .5),
                           monotonic=kwargs.pop('monotonic', lambda: 0), **kwargs)


def test_mock_job_finishes_with_verified_receipt(setup, monkeypatch):
    conn, store = setup
    enqueue(conn, job())
    original = runner.complete_claim
    verified = []
    verify = store.verify

    def check(spec, receipt):
        verified.append(verify(spec, receipt))
        return verified[-1]

    def complete(*args):
        assert verified == [True]
        return original(*args)

    monkeypatch.setattr(store, 'verify', check)
    monkeypatch.setattr(runner, 'complete_claim', complete)
    worker = SpyWorker()
    assert tick(setup, worker) == 'completed_mock'
    receipt = ArtifactReceipt(*conn.execute(
        'SELECT job_id, source_sha, input_digest, artifact_sha256, relative_path, '
        'byte_count FROM receipts').fetchone())
    assert verify(job(), receipt)
    assert conn.execute('SELECT state FROM jobs').fetchone() == ('completed_mock',)
    assert tick(setup, worker) == 'idle'
    assert worker.calls == ['job']


def test_empty_queue_is_idle(setup):
    assert tick(setup) == 'idle'
    assert setup[0].execute('SELECT COUNT(*) FROM events').fetchone() == (0,)


@pytest.mark.parametrize('ratio', [0, .05, .099999])
def test_disk_pressure_blocks_before_work(setup, ratio):
    conn, _ = setup
    enqueue(conn, job())
    worker = SpyWorker()
    assert tick(setup, worker, disk_free_ratio=ratio) == 'blocked'
    assert worker.calls == []
    assert conn.execute('SELECT COUNT(*) FROM attempts').fetchone() == (0,)
    assert tick(setup, worker, disk_free_ratio=.10) == 'completed_mock'


@pytest.mark.parametrize('kind,budget', [('codex', '0'), ('codex', '5'), ('mock', '1')])
@pytest.mark.parametrize('approved', ['0', '100'])
def test_billable_job_never_dispatches_at_zero_budget(setup, kind, budget, approved):
    conn, _ = setup
    enqueue(conn, job(worker_kind=kind, budget_usd=budget))
    worker = SpyWorker()
    assert tick(setup, worker, approved_budget_usd=approved) == 'blocked'
    assert not worker.calls
    assert conn.execute('SELECT state, attempt_count FROM jobs').fetchone() == ('blocked', 0)
    assert conn.execute('SELECT COUNT(*) FROM receipts').fetchone() == (0,)


@pytest.mark.parametrize('error', [RuntimeError('failure'), TimeoutError('timeout')])
def test_unhandled_worker_failure_keeps_checkpoint(setup, error):
    conn, store = setup
    old = store.put(job(job_id='previous'), b'previous verified bytes')
    enqueue(conn, job())

    class Broken(MockWorker):
        def run(self, spec):
            raise error

    assert tick(setup, Broken()) == 'blocked'
    assert store.verify(job(job_id='previous'), old)
    assert conn.execute('SELECT state, attempt_count FROM jobs').fetchone() == ('blocked', 1)
    assert conn.execute('SELECT outcome, finished_at FROM attempts').fetchone() == ('blocked', 10)
    assert conn.execute('SELECT COUNT(*) FROM leases').fetchone() == (0,)
    assert conn.execute("SELECT COUNT(*) FROM events WHERE kind='blocked'").fetchone() == (1,)
    assert tick(setup) == 'idle'


def test_model_cooldown_blocks_until_allowed(setup):
    conn, _ = setup
    enqueue(conn, job())
    conn.execute('UPDATE jobs SET retry_after=20')
    conn.commit()
    worker = SpyWorker()
    assert tick(setup, worker, now=19) == 'blocked'
    assert worker.calls == []
    assert conn.execute('SELECT attempt_count, retry_after FROM jobs').fetchone() == (0, 20)
    assert tick(setup, worker, now=20) == 'completed_mock'


def test_unverified_artifact_cannot_complete(setup, monkeypatch):
    conn, store = setup
    enqueue(conn, job())
    monkeypatch.setattr(store, 'verify', lambda *args: False)
    assert tick(setup) == 'blocked'
    assert conn.execute('SELECT COUNT(*) FROM receipts').fetchone() == (0,)
    assert conn.execute('SELECT state FROM jobs').fetchone() == ('blocked',)


def test_one_claim_per_tick_and_stable_bounded_proof(setup):
    conn, _ = setup
    enqueue(conn, job())
    enqueue(conn, job(job_id='second'))
    assert tick(setup) == 'completed_mock'
    assert conn.execute("SELECT COUNT(*) FROM jobs WHERE state='queued'").fetchone() == (1,)
    proof = MockWorker().run(job())
    assert proof == MockWorker().run(job())
    assert len(proof) < 256
    assert proof != MockWorker().run(job(input_digest='c' * 64))


@pytest.mark.parametrize('ratio', [-1, 1.1, float('nan'), float('inf')])
def test_invalid_disk_ratio_rejected(setup, ratio):
    with pytest.raises(ValueError):
        tick(setup, disk_free_ratio=ratio)


@pytest.mark.parametrize('budget', ['-1', 'NaN', 'Infinity', 'bad'])
def test_invalid_approved_budget_rejected(setup, budget):
    with pytest.raises(ValueError):
        tick(setup, approved_budget_usd=budget)


def test_worker_elapsed_time_expires_claim_before_completion(setup):
    conn, _ = setup
    enqueue(conn, job())
    clock = [100.0]

    class Slow(MockWorker):
        def run(self, spec):
            clock[0] += 61
            return super().run(spec)

    assert tick(setup, Slow(), monotonic=lambda: clock[0]) == 'blocked'
    assert conn.execute('SELECT count(*) FROM receipts').fetchone() == (0,)
    assert conn.execute('SELECT state FROM jobs').fetchone() == ('blocked',)
    assert conn.execute('SELECT finished_at FROM attempts').fetchone() == (71,)
