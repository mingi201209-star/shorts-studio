"""Real film handoff: existing native render -> editing -> technical evaluation.

Runs encoding only on GitHub. Editorial acceptance remains a separate HOLD.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from .ledger import TaskLedger


def finish_film(native: Path, source: Path, out: Path, ledger: TaskLedger,
                variant: str = 'B') -> dict:
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise RuntimeError('Real assembly must run on GitHub Actions')
    from benchmarks.road_safety.curious_mechanics_progressive_delivery import assemble

    proofs = sorted(native.rglob('episode-proof.json'))
    if not proofs:
        raise ValueError('No actual native render proofs')
    inputs = {str(p.relative_to(native)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in proofs}
    input_hash = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    resource = f'film:{variant}:{input_hash}'
    for task in ledger.all():
        if task.target_resource == resource:
            if task.status == 'completed':
                result = task.output
                video = Path(result['video'])
                if hashlib.sha256(video.read_bytes()).hexdigest() != result['sha256']:
                    raise ValueError('Completed output changed')
                return result
            raise RuntimeError('Existing assembly requires explicit recovery; no duplicate encoding')
    rendered = ledger.create(
        department='렌더부', division='렌더실행', requirements={'variant': variant},
        completion_criteria='Native proofs supplied; assembler revalidates every PNG/clip',
        input_hash=input_hash, output={'proofs': inputs, 'is_mock': False},
        status='completed')
    edit = ledger.create(
        department='편집부', division='컷편집', requirements={'variant': variant},
        predecessors=[rendered.task_id], input_hash=input_hash,
        completion_criteria='Actual MP4 and unchanged final QA receipt',
        target_resource=resource, status='running')
    try:
        assemble(native, source, variant, out)
        receipt = json.loads((out / 'film-validation.json').read_text())
        video = out / f'curious-mechanics-{variant}-progressive-v3.mp4'
        sha = hashlib.sha256(video.read_bytes()).hexdigest()
        if receipt['technical_status'] != 'PASS' or sha != receipt['sha256']:
            raise ValueError('Missing passing receipt or MP4 hash mismatch')
        result = {'video': str(video), 'sha256': sha, 'is_mock': False,
                  'technical_status': 'PASS', 'editorial_status': 'HOLD_ACTUAL_REVIEW',
                  'human_first_view': 'UNVERIFIED', 'upload_authorized': False,
                  'receipt': str(out / 'film-validation.json')}
        ledger.create(
            department='평가부', division='기술검수', requirements={'variant': variant},
            predecessors=[edit.task_id], input_hash=input_hash, output=result,
            completion_criteria='Existing full native, audio, captions, semantic and final QA passed',
            status='completed')
        ledger.update(edit.task_id, status='completed', output=result)
        return result
    except Exception as exc:
        ledger.update(edit.task_id, status='failed', failure_reason=f'{type(exc).__name__}: {exc}')
        raise


def main():
    parser = argparse.ArgumentParser()
    for name in ('native', 'source', 'out', 'ledger'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    result = finish_film(args.native, args.source, args.out, TaskLedger(args.ledger))
    print('STUDIO_ORG_REAL_FILM ' + json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
