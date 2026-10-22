"""Mixed cache/new coverage is a metadata gate, not a fake native-render test."""
import importlib.util
from pathlib import Path

import pytest


def validator():
    path = Path(__file__).resolve().parents[1] / 'benchmarks/road_safety/episode2_film.py'
    spec = importlib.util.spec_from_file_location('episode2_film_layout', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate_shard_layout


def proof(first, count):
    nums = list(range(first, first + count))
    return {'first_frame': first, 'last_frame': nums[-1], 'frames': count,
            'frame_numbers': nums, 'original_frame_records': [{'frame': n} for n in nums]}


def test_cached30_and_new10_cover_the_same_exact900():
    validator()([proof(1, 30)] + [proof(n, 10) for n in range(31, 901, 10)])


def test_original30_frame_layout_stays_valid():
    validator()([proof(n, 30) for n in range(1, 901, 30)])


@pytest.mark.parametrize('case', ['gap', 'overlap', 'partial', 'oversize', 'wrong_records'])
def test_incomplete_or_overlapping_source_cannot_be_assembled(case):
    records = [proof(n, 10) for n in range(1, 901, 10)]
    if case == 'gap':
        records.pop(12)
    elif case == 'overlap':
        records.insert(1, proof(1, 10))
    elif case == 'partial':
        records.pop()
    elif case == 'oversize':
        records = [proof(1, 900)]
    else:
        records[0]['original_frame_records'].pop()
    with pytest.raises(AssertionError):
        validator()(records)
