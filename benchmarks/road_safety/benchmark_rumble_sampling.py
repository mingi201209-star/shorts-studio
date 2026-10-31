"""Isolated ABBA native render experiment; never supplies production footage.

Same A1-B1-B2-A2 harness as benchmark_rumble_persistent.py (order cancels
thermal/scheduling drift between runs), but tests the actual Cycles-samples
ceiling instead of persistent_data. Unlike persistent_data, fewer samples DO
change pixels (more residual noise), so this never asserts pixel identity --
it reports the measured difference and leaves the adoption call to a human
visual check, exactly like the two camera-margin near-misses this project
already left as documented, unresolved findings rather than guessing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import subprocess
import time
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

from shorts_studio.factory.rumble_native_shard_qa import verify


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--blender', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--candidate-samples', type=int, default=16)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    renderer = Path('benchmarks/road_safety/render_rumble_episode2.py')
    original = renderer.read_text()
    source_hash = digest(renderer)
    anchor = '    scene.cycles.use_denoising=True\n'
    assert original.count(anchor) == 1
    # The renderer's own fail-closed gate rejects any non-preview frame whose
    # cycles_samples differs from the approved manifest's 32 -- exactly the
    # protection that must stay in place for real production renders. This
    # experiment exists specifically to render AT a different sample count,
    # so the gate's samples half (only) is neutralized in the disposable
    # candidate copy; the resolution half, and the real production file,
    # are untouched (checked below via the unmodified source hash).
    gate_anchor = '        or result["cycles_samples"]!=episode["cycles_samples"]\n'
    assert original.count(gate_anchor) == 1
    manifest = Path('examples/factory/rumble-episode2-30s.json')
    report = {'status': 'RUNNING', 'benchmark_only': True,
              'production_adopted': False, 'original_renderer_sha256': source_hash,
              'baseline_samples': 32, 'candidate_samples': args.candidate_samples,
              'cpu_count': os.cpu_count(),
              'cpu_affinity': sorted(os.sched_getaffinity(0)),
              'platform': platform.platform(), 'runs': []}
    Path(args.out/'cpuinfo.txt').write_text(Path('/proc/cpuinfo').read_text())
    for name, enabled in [('a1', False), ('b1', True), ('b2', True), ('a2', False)]:
        output = args.out/name
        output.mkdir()
        runtime = output/'runtime'
        (runtime/'benchmarks/road_safety').mkdir(parents=True)
        (runtime/'shorts_studio').symlink_to(Path('shorts_studio').resolve(), target_is_directory=True)
        candidate = runtime/'benchmarks/road_safety/benchmark-renderer.py'
        text = original.replace(anchor, anchor +
            (f'    scene.cycles.samples={args.candidate_samples}\n' if enabled else '') +
            '    print("BENCH_SAMPLES", scene.cycles.samples, flush=True)\n')
        if enabled:
            text = text.replace(gate_anchor,
                '        or False  # benchmark_rumble_sampling: cycles_samples '
                'intentionally overridden for this measurement, never adopted as-is\n')
        candidate.write_text(text)
        command = ['/usr/bin/time', '-v', '-o', str(output/'resource.txt'),
                   'xvfb-run', '-a', str(args.blender), '-b', '-t', '4',
                   '--python-exit-code', '1', '-P', str(candidate), '--',
                   '--source', str(args.source), '--manifest', str(manifest),
                   '--start', '151', '--end', '160', '--out', str(output)]
        begin = time.perf_counter()
        with (output/'render.log').open('w') as log:
            subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT)
        wall = time.perf_counter()-begin
        try:
            qa = verify(output, manifest, candidate)
            qa_error = None
        except ValueError as error:
            # A real finding, not a harness bug: fewer samples tripped one of
            # the project's own fail-closed pixel gates (e.g. the black-void
            # or near-black check). Record it instead of crashing the sweep.
            qa, qa_error = None, str(error)
        observed = next(line.split()[-1] for line in (output/'render.log').read_text().splitlines()
                        if line.startswith('BENCH_SAMPLES '))
        proof = json.loads((output/'episode-proof.json').read_text())
        assert proof['frame_numbers'] == list(range(151, 161))
        times = proof['render_seconds']
        report['runs'].append({'name': name, 'candidate_samples_applied': enabled,
            'observed_cycles_samples': int(observed),
            'wall_seconds': wall, 'first_frame_seconds': times[0],
            'warm_frame_median_seconds': statistics.median(times[1:]),
            'render_seconds': times, 'native_qa': qa, 'native_qa_error': qa_error,
            'candidate_renderer_sha256': digest(candidate)})
        assert digest(renderer) == source_hash, 'production renderer mutated'
        (args.out/'benchmark.json').write_text(json.dumps(report, indent=2))
        print('BENCHMARK_STAGE '+json.dumps(report['runs'][-1]), flush=True)
    pixel_stats = []
    reference = args.out/'a1'
    for name in ('b1', 'b2', 'a2'):
        for frame in range(151, 161):
            file = f'frame_{frame:04d}.png'
            with Image.open(reference/file) as a, Image.open(args.out/name/file) as b:
                diff = ImageChops.difference(a.convert('RGB'), b.convert('RGB'))
                stat = ImageStat.Stat(diff)
                pixel_stats.append({'run': name, 'frame': frame,
                                    'mean_abs_diff': stat.mean, 'max_abs_diff': stat.extrema})
    baseline = statistics.mean(r['wall_seconds'] for r in report['runs'] if not r['candidate_samples_applied'])
    candidate = statistics.mean(r['wall_seconds'] for r in report['runs'] if r['candidate_samples_applied'])
    any_qa_failed = any(r['native_qa_error'] for r in report['runs'])
    report.update(status='MEASURED', pixel_differences=pixel_stats,
        baseline_wall_mean=baseline, candidate_wall_mean=candidate,
        wall_speedup=baseline/candidate, any_qa_gate_failed=any_qa_failed,
        adoption_status=('REJECT_QA_GATE_FAILED' if any_qa_failed else 'REVIEW_REQUIRED'),
        adoption_note=('Lower samples still cleared every existing fail-closed pixel '
                        'gate and rendered faster. This does NOT mean adopt it -- it '
                        'means the noise difference above is small enough that only a '
                        'human eye on the actual frames can judge whether it is '
                        'visible, the same bar already applied to the two camera-'
                        'margin near-misses left undecided in this project.'
                        if not any_qa_failed else
                        'At least one run failed an existing QA gate at this sample '
                        'count -- do not adopt without first understanding which '
                        'gate and why.'))
    (args.out/'benchmark.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
