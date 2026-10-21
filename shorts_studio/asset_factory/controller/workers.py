"""Deterministic, bounded diagnostic work with no external side effects."""

import hashlib
import json
from dataclasses import asdict
from decimal import Decimal

from .contracts import JobSpec


class MockWorker:
    """Produce proof bytes only; these are never native frames or production QA."""

    def run(self, job: JobSpec) -> bytes:
        if job.worker_kind != 'mock' or Decimal(job.budget_usd) != 0:
            raise ValueError('mock worker requires a zero-cost mock job')
        identity = json.dumps(asdict(job), sort_keys=True, separators=(',', ':'))
        digest = hashlib.sha256(identity.encode()).hexdigest()
        return f'mock-proof-v1; diagnostic only; no production QA\n{digest}\n'.encode()
