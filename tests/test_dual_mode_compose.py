import json

import pytest

from shorts_studio.dual_mode_compose import select_frames


def scene(cache, key, hashes):
    root = cache / "scenes" / key
    root.mkdir(parents=True)
    (root / "proof.json").write_text(
        json.dumps(
            {
                "outputs": {f"frame_{i:04}.png": value for i, value in enumerate(hashes, 1)},
                "specification": {"motion": "rolling" if key[0] == "a" else "locked"},
            }
        )
    )


def test_explicit_cut_preserves_native_provenance(tmp_path):
    key = "a" * 64
    scene(tmp_path, key, ["one", "two", "three"])
    result = select_frames(
        tmp_path, [{"key": key, "start": 2, "end": 3}], lambda root, k: {"native_frames": 3}
    )
    assert [r["source_frame"] for r in result] == [2, 3]
    assert [r["source_sha256"] for r in result] == ["two", "three"]
    assert all(r["motion"] == "rolling" for r in result)


def test_repeated_source_is_not_extended_into_a_longer_clip(tmp_path):
    key = "a" * 64
    scene(tmp_path, key, ["one", "two"])
    with pytest.raises(ValueError, match="duplicate"):
        select_frames(tmp_path, [{"key": key}, {"key": key}], lambda root, k: {"native_frames": 2})


def test_two_motion_scenes_allow_an_explicit_nonduplicate_cut(tmp_path):
    a, b = "a" * 64, "b" * 64
    scene(tmp_path, a, ["same-initial", "rolling-2"])
    scene(tmp_path, b, ["same-initial", "locked-2"])
    result = select_frames(
        tmp_path, [{"key": a}, {"key": b, "start": 2}], lambda root, k: {"native_frames": 2}
    )
    assert [r["motion"] for r in result] == ["rolling", "rolling", "locked"]
    assert len({r["source_sha256"] for r in result}) == 3


@pytest.mark.parametrize("start,end", [(0, 2), (2, 1), (1, 4), (True, 2)])
def test_invalid_cut_range_is_rejected(tmp_path, start, end):
    key = "a" * 64
    scene(tmp_path, key, ["one", "two"])
    with pytest.raises(ValueError):
        select_frames(
            tmp_path,
            [{"key": key, "start": start, "end": end}],
            lambda root, k: {"native_frames": 2},
        )


@pytest.mark.parametrize("key", ["../outside", "not-a-key", "A" * 64])
def test_scene_path_is_bound_to_content_key(tmp_path, key):
    with pytest.raises(ValueError):
        select_frames(tmp_path, [{"key": key}], lambda *a: {"native_frames": 2})


def test_failed_scene_validation_is_not_ignored(tmp_path):
    def invalid(*args):
        raise ValueError("invalid native source")

    with pytest.raises(ValueError, match="invalid native source"):
        select_frames(tmp_path, [{"key": "a" * 64}], invalid)
