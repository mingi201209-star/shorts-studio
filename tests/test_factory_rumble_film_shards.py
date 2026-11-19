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


def film_module():
    path = Path(__file__).resolve().parents[1] / 'benchmarks/road_safety/episode2_film.py'
    spec = importlib.util.spec_from_file_location('episode2_film_loudness', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EBUR128_SUMMARY = """[Parsed_ebur128_0 @ 0x1] Summary:

  Integrated loudness:
    I:         -16.4 LUFS
    Threshold: -26.8 LUFS

  Loudness range:
    LRA:         2.9 LU

  True peak:
    Peak:       -1.5 dBFS
"""


def test_ebur128_summary_parser_reads_integrated_loudness_and_true_peak():
    assert film_module().parse_ebur128(EBUR128_SUMMARY) == {
        'integrated_lufs': -16.4, 'loudness_range_lu': 2.9, 'true_peak_dbfs': -1.5}
    with pytest.raises(ValueError):
        film_module().parse_ebur128('no summary here')


MEASURED = {'integrated_lufs': -16.4, 'loudness_range_lu': 2.9, 'true_peak_dbfs': -1.5,
            'shot_integrated_lufs': [-16.7, -16.6, -17.0, -16.6, -16.1, -15.1]}


@pytest.mark.parametrize('field,value,reason', [
    ('integrated_lufs', -20.0, 'NARRATION_LOUDNESS'),
    ('integrated_lufs', -13.0, 'NARRATION_LOUDNESS'),
    ('true_peak_dbfs', -0.4, 'NARRATION_TRUE_PEAK'),
    ('shot_integrated_lufs', [-19.5, -16.6, -17.0, -16.6, -16.1, -15.1], 'UNEVEN_SHOT_LOUDNESS'),
    ('shot_integrated_lufs', [-16.7, -16.6, -17.0, -16.6, -16.1], 'UNEVEN_SHOT_LOUDNESS'),
])
def test_narration_loudness_gate(field, value, reason):
    module = film_module()
    module.check_loudness(MEASURED)
    with pytest.raises(AssertionError, match=reason):
        module.check_loudness({**MEASURED, field: value})


def test_every_shot_declares_semantic_labels_against_wrong_domains():
    from shorts_studio.factory.rumble_episode2 import (
        SEMANTIC_NEGATIVE_LABELS,
        SHOT_IDS,
        semantic_labels,
    )

    assert len(SEMANTIC_NEGATIVE_LABELS) >= 4
    for shot in SHOT_IDS:
        positive = semantic_labels(shot)
        assert len(positive) >= 2
        assert not set(positive) & set(SEMANTIC_NEGATIVE_LABELS)
        assert any(word in " ".join(positive) for word in ("tire", "wheel", "car"))
    with pytest.raises(ValueError):
        semantic_labels("title_card")


def semantic_result(status):
    return {"status": status, "margin": 0.08 if status == "PASS" else 0.01}


@pytest.mark.parametrize('statuses,expected', [
    (['PASS'] * 6, 'PASS'),
    (['PASS'] * 5 + ['NOT_EVALUATED'], 'SEMANTIC_VISUAL_QA'),
    (['FAIL'] + ['PASS'] * 5, 'SEMANTIC_VISUAL_QA'),
    (['PASS'] * 5, 'SEMANTIC_VISUAL_QA'),
])
def test_semantic_gate_fails_closed_on_any_non_pass_shot(statuses, expected):
    from shorts_studio.factory.rumble_episode2 import SHOT_IDS

    check = film_module().check_semantic
    results = [{"shot": shot, **semantic_result(s)} for shot, s in zip(SHOT_IDS, statuses)]
    if expected == 'PASS':
        assert check(results)['status'] == 'PASS'
    else:
        with pytest.raises(AssertionError, match=expected):
            check(results)


def test_fresh_film_assembler_installs_real_local_clip():
    workflow = (Path(__file__).resolve().parents[1]
                / '.github/workflows/rumble-episode2-native-film.yml').read_text()
    assemble = workflow.split('  assemble:', 1)[1]
    assert '--index-url https://download.pytorch.org/whl/cpu' in assemble
    assert "pip install -e '.[vision]'" in assemble


@pytest.mark.parametrize('failing', [None, 'visual_activity', 'black_opening', 'captions_visible'])
def test_original_final_video_checks_fail_closed(failing):
    check = film_module().check_original_video_qa
    results = {name: {"status": "FAIL" if name == failing else "PASS"}
               for name in ("visual_activity", "black_opening", "captions_visible")}
    if failing is None:
        assert check(results)["status"] == "PASS"
    else:
        with pytest.raises(AssertionError, match="ORIGINAL_VIDEO_QA"):
            check(results)
    with pytest.raises(AssertionError, match="ORIGINAL_VIDEO_QA"):
        check({"visual_activity": {"status": "PASS"}})


def test_assembler_runs_original_checks_with_unchanged_thresholds():
    source = (Path(__file__).resolve().parents[1]
              / 'benchmarks/road_safety/episode2_film.py').read_text()
    for name in ("measure_visual_activity", "verify_visual_activity",
                 "verify_no_black_opening", "verify_captions_visible"):
        assert f"{name}(" in source
    # The originals' defaults (12.0 change, 5 s hold, >=1 change in first 5 s)
    # must not be overridden for this episode.
    assert "change_threshold=" not in source
    assert "max_static_seconds=" not in source
    assert "min_first_5s_changes=" not in source
