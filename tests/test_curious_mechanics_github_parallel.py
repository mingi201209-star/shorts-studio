from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "benchmarks/road_safety/curious_mechanics_github_parallel.py"
spec = importlib.util.spec_from_file_location("curious_mechanics_github_parallel", SCRIPT)
parallel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parallel)


@pytest.mark.parametrize("shard,expected", [
    (1, (1, 30)), (2, (31, 60)), (3, (61, 90)),
    (10, (271, 300)), (30, (871, 900)),
])
def test_shard_range_is_contiguous_30_frames(shard, expected):
    assert parallel.shard_range(shard) == expected


@pytest.mark.parametrize("shard", [0, 31, -1, 1.5, True])
def test_shard_range_rejects_invalid_values(shard):
    with pytest.raises(ValueError):
        parallel.shard_range(shard)


@pytest.mark.parametrize("frame,expected", [
    (1, 1), (30, 31), (31, 31), (241, 241), (270, 271), (271, 271), (900, 901),
])
def test_contact_start_aligns_to_existing_shard_boundaries(frame, expected):
    assert parallel.aligned_contact_start(frame) == expected


@pytest.mark.parametrize("frame", [0, 901, True])
def test_contact_start_rejects_invalid_frame(frame):
    with pytest.raises(ValueError):
        parallel.aligned_contact_start(frame)


@pytest.mark.parametrize("variant,shot_start,shot_end,expected", [
    ("A", 421, 450, (421, 450)),
    ("B", 241, 270, (241, 270)),
    ("C", 241, 270, (241, 270)),
])
def test_contact_range_uses_variant_timeline(monkeypatch, variant, shot_start, shot_end, expected):
    fake_timeline = SimpleNamespace(
        load_episode=lambda manifest: {"shots": [{"id": f"{variant}_contact", "start": shot_start, "end": shot_end}]},
        detail_stage=lambda shot_id: "rolling_contact",
    )
    fake_factory = ModuleType("shorts_studio.factory")
    fake_factory.__path__ = []
    fake_factory.curious_mechanics_timeline = fake_timeline
    fake_parent = ModuleType("shorts_studio")
    fake_parent.__path__ = []
    fake_parent.factory = fake_factory
    monkeypatch.setitem(sys.modules, "shorts_studio", fake_parent)
    monkeypatch.setitem(sys.modules, "shorts_studio.factory", fake_factory)
    monkeypatch.setitem(sys.modules, "shorts_studio.factory.curious_mechanics_timeline", fake_timeline)
    assert parallel.contact_range(variant) == expected


def test_contact_range_selects_first_late_contact_when_b_has_two(monkeypatch):
    fake_timeline = SimpleNamespace(
        load_episode=lambda manifest: {"shots": [
            {"id": "B_early", "start": 232, "end": 316},
            {"id": "B_later", "start": 504, "end": 606},
        ]},
        detail_stage=lambda shot_id: "rolling_contact",
    )
    fake_factory = ModuleType("shorts_studio.factory")
    fake_factory.__path__ = []
    fake_factory.curious_mechanics_timeline = fake_timeline
    fake_parent = ModuleType("shorts_studio")
    fake_parent.__path__ = []
    fake_parent.factory = fake_factory
    monkeypatch.setitem(sys.modules, "shorts_studio", fake_parent)
    monkeypatch.setitem(sys.modules, "shorts_studio.factory", fake_factory)
    monkeypatch.setitem(sys.modules, "shorts_studio.factory.curious_mechanics_timeline", fake_timeline)
    assert parallel.contact_range("B") == (241, 270)


def test_contact_range_rejects_wrong_variant():
    with pytest.raises(ValueError):
        parallel.contact_range("D")


def test_full_matrix_covers_all_900_frames_without_overlap():
    frames = [
        n for shard in range(1, 31)
        for start, end in [parallel.shard_range(shard)]
        for n in range(start, end + 1)
    ]
    assert frames == list(range(1, 901))


@pytest.mark.parametrize("variant", list("ABC"))
def test_real_contact_shard_is_inside_rolling_contact_timeline(variant):
    start, end = parallel.contact_range(variant)
    assert end - start == 29
    assert start in range(1, 901, 30)
    assert end <= 900


def test_selective_recovery_workflow_only_retries_failed_shards():
    workflow = (ROOT / ".github/workflows/curious-mechanics-selective-recovery.yml").read_text()
    assert "workflow_dispatch:" in workflow
    assert "pull_request:" in workflow and "types: [labeled]" in workflow
    assert "curious-mechanics-recover" in workflow
    assert "inputs.source_run_id || '44499589013'" in workflow
    assert "source_run_id:" in workflow
    assert "variant: C" in workflow and "shard: 2" in workflow
    assert "curious-native-C-2-recovery" in workflow
    assert "curious-contact-${{ matrix.variant }}-recovery" in workflow
    assert 'gh run download "$SOURCE_RUN_ID"' in workflow
    assert 'gh run download "$GITHUB_RUN_ID"' in workflow
    assert "curious-native-A-1" in workflow and "curious-native-B-3" in workflow
    assert "curious-native-C-3" in workflow
    assert "retention-days: 90" in workflow


def test_contact_cli_resolves_package_from_repository_root():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "contact", "--variant", "A"],
        cwd=ROOT, env=env, capture_output=True, text=True, check=True,
    )
    assert tuple(map(int, result.stdout.split())) == parallel.contact_range("A")


def test_production_workflow_is_manual_only_and_uses_free_standard_runners():
    workflow = (ROOT / ".github/workflows/curious-mechanics-production-parallel.yml").read_text()
    assert "workflow_dispatch:" in workflow
    assert "runs-on: ubuntu-24.04" in workflow
    assert "max-parallel: 18" in workflow
    assert "needs: preflight" in workflow
    assert "matrix.shard <= 3" not in workflow
    assert "fromJSON(inputs.mode == 'full'" in workflow
    assert "CM_AUDIO_EXPORT_ENABLED" in workflow
    assert "Full production requires CM_AUDIO_EXPORT_ENABLED=true" in workflow
    assert "retention-days: 1" in workflow  # transient native shards
    assert "retention-days: 90" in workflow  # review films and pilot previews
    assert workflow.count("if-no-files-found: error") == 4
    assert "options: [pilot, full]" in workflow
    assert "curious-native-" in workflow
    assert "curious-review-" in workflow
    assert 'PYTHONPATH="$PWD" python benchmarks/road_safety/curious_mechanics_github_parallel.py contact' in workflow
    assert "https://mirrors.aliyun.com/blender/release/Blender5.0/" in workflow
    assert "https://mirror.nju.edu.cn/blender/release/Blender5.0/" in workflow
    assert "https://mirror.freedif.org/blender/release/Blender5.0/" in workflow
    assert "sha256sum -c -" in workflow
    assert "push:" not in workflow and "pull_request:" not in workflow
