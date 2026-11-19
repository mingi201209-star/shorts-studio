"""Isolated ABBA native render experiment; never supplies production footage."""
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

from PIL import Image, ImageChops

from shorts_studio.factory.rumble_native_shard_qa import verify


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--blender', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    renderer = Path('benchmarks/road_safety/render_rumble_episode2.py')
    original = renderer.read_text()
    source_hash = digest(renderer)
    anchor = '    scene.cycles.device="CPU"\n'
    assert original.count(anchor) == 1
    manifest = Path('examples/factory/rumble-episode2-30s.json')
    report = {'status': 'RUNNING', 'benchmark_only': True,
              'production_adopted': False, 'original_renderer_sha256': source_hash,
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
        candidate.write_text(original.replace(anchor, anchor +
            ('    scene.render.use_persistent_data=True\n' if enabled else '') +
            '    print("BENCH_PERSISTENT_DATA", scene.render.use_persistent_data, flush=True)\n'))
        command = ['/usr/bin/time', '-v', '-o', str(output/'resource.txt'),
                   'xvfb-run', '-a', str(args.blender), '-b', '-t', '4',
                   '--python-exit-code', '1', '-P', str(candidate), '--',
                   '--source', str(args.source), '--manifest', str(manifest),
                   '--start', '151', '--end', '160', '--out', str(output)]
        begin = time.perf_counter()
        with (output/'render.log').open('w') as log:
            subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT)
        wall = time.perf_counter()-begin
        qa = verify(output, manifest, candidate)
        observed = next(line.split()[-1] for line in (output/'render.log').read_text().splitlines()
                        if line.startswith('BENCH_PERSISTENT_DATA '))
        proof = json.loads((output/'episode-proof.json').read_text())
        assert proof['frame_numbers'] == list(range(151, 161))
        times = proof['render_seconds']
        report['runs'].append({'name': name, 'persistent_data': enabled,
            'observed_persistent_data': observed,
            'wall_seconds': wall, 'first_frame_seconds': times[0],
            'warm_frame_median_seconds': statistics.median(times[1:]),
            'render_seconds': times, 'native_qa': qa,
            'candidate_renderer_sha256': digest(candidate)})
        assert digest(renderer) == source_hash, 'production renderer mutated'
        (args.out/'benchmark.json').write_text(json.dumps(report, indent=2))
        print('BENCHMARK_STAGE '+json.dumps(report['runs'][-1]), flush=True)
    differences = []
    reference = args.out/'a1'
    for name in ('b1', 'b2', 'a2'):
        for frame in range(151, 161):
            file = f'frame_{frame:04d}.png'
            with Image.open(reference/file) as a, Image.open(args.out/name/file) as b:
                diff = ImageChops.difference(a.convert('RGB'), b.convert('RGB'))
                if diff.getbbox():
                    differences.append({'run': name, 'frame': frame,
                                        'extrema': diff.getextrema()})
    baseline = statistics.mean(r['wall_seconds'] for r in report['runs'] if not r['persistent_data'])
    candidate = statistics.mean(r['wall_seconds'] for r in report['runs'] if r['persistent_data'])
    report.update(status='MEASURED', rgb_identical=not differences,
        pixel_differences=differences, baseline_wall_mean=baseline,
        persistent_wall_mean=candidate, wall_speedup=baseline/candidate,
        adoption_status='REVIEW_REQUIRED' if not differences else 'REJECT_PIXEL_REGRESSION')
    (args.out/'benchmark.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2), flush=True)
    assert not differences, 'persistent rendering changed source pixels; do not adopt'


if __name__ == '__main__':
    main()
