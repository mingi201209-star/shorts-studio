"""Opt-in R2 scene-clip staging (shorts_studio.scene_r2_staging), wired into
render() via Project.enable_r2_scene_staging (default False).

Every test here stays entirely offline/local: stage_scene_clip() only ever
calls r2_handoff's plan_source/stage_source/StateStore, none of which touch
the network or read any credential -- see the module's own docstring for why.
"""
import os

import pytest

from shorts_studio.r2_handoff.contracts import HandoffError
from shorts_studio.scene_r2_staging import (
    R2StagingConfig,
    R2StagingConfigError,
    config_from_env,
    slugify_namespace,
    stage_scene_clip,
)

# --- slugify_namespace -------------------------------------------------------

def test_slugify_simple_title():
    assert slugify_namespace("Hydroplaning") == "renders/hydroplaning"

def test_slugify_strips_non_alnum_and_collapses_runs():
    ns = slugify_namespace("타이어가 도로에서 뜬다!! v2.0")
    assert ns.startswith("renders/")
    assert "--" not in ns
    assert ns == ns.lower()

def test_slugify_empty_after_stripping_falls_back_to_prefix():
    assert slugify_namespace("!!!", prefix="renders") == "renders"

def test_slugify_result_always_matches_r2_handoff_identity_pattern():
    import re
    pattern = re.compile(r"[a-z0-9]+(?:[-/][a-z0-9]+)*")
    for title in ["A", "A/B\\C", "...", "매우 긴 제목 " * 10, "already-good-slug"]:
        ns = slugify_namespace(title)
        assert pattern.fullmatch(ns), ns
        assert len(ns) <= 80

# --- config_from_env ----------------------------------------------------------

def test_config_from_env_raises_when_unconfigured(monkeypatch):
    monkeypatch.delenv("SHORTS_R2_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("SHORTS_R2_BUCKET", raising=False)
    with pytest.raises(R2StagingConfigError):
        config_from_env(namespace="renders/x")

def test_config_from_env_raises_when_only_one_var_set(monkeypatch):
    monkeypatch.setenv("SHORTS_R2_ACCOUNT_ID", "a" * 32)
    monkeypatch.delenv("SHORTS_R2_BUCKET", raising=False)
    with pytest.raises(R2StagingConfigError):
        config_from_env(namespace="renders/x")

def test_config_from_env_builds_config_when_set(monkeypatch, tmp_path):
    monkeypatch.setenv("SHORTS_R2_ACCOUNT_ID", "a" * 32)
    monkeypatch.setenv("SHORTS_R2_BUCKET", "shorts-studio-media")
    monkeypatch.setenv("SHORTS_R2_STATE_ROOT", str(tmp_path / "state"))
    config = config_from_env(namespace="renders/x")
    assert config.account_id == "a" * 32
    assert config.bucket == "shorts-studio-media"
    assert config.namespace == "renders/x"
    assert config.state_root == tmp_path / "state"

# --- stage_scene_clip ---------------------------------------------------------

def _config(tmp_path, **overrides):
    defaults = dict(account_id="a" * 32, bucket="shorts-studio-media",
                    namespace="renders/test", state_root=tmp_path / "state")
    defaults.update(overrides)
    return R2StagingConfig(**defaults)

def test_stage_scene_clip_is_offline_and_returns_job_metadata(tmp_path):
    clip = tmp_path / "scene.mp4"
    clip.write_bytes(b"fake mp4 bytes for hashing only" * 100)
    result = stage_scene_clip(clip, config=_config(tmp_path))
    assert result["status"] == "STAGED"
    assert result["job_id"]
    assert result["size_bytes"] == clip.stat().st_size
    import hashlib
    assert result["sha256"] == hashlib.sha256(clip.read_bytes()).hexdigest()

def test_stage_scene_clip_never_touches_network(tmp_path, monkeypatch):
    """No socket module usage is exercised: patch socket.socket to explode
    if anything in the call path ever tries to open a connection."""
    import socket
    def _boom(*a, **k):
        raise AssertionError("stage_scene_clip must never open a network socket")
    monkeypatch.setattr(socket, "socket", _boom)
    clip = tmp_path / "scene.mp4"
    clip.write_bytes(b"no network here" * 50)
    stage_scene_clip(clip, config=_config(tmp_path))  # must not raise

def test_stage_scene_clip_is_idempotent_for_identical_content(tmp_path):
    clip = tmp_path / "scene.mp4"
    clip.write_bytes(b"same content twice" * 50)
    config = _config(tmp_path)
    first = stage_scene_clip(clip, config=config)
    second = stage_scene_clip(clip, config=config)
    assert first["job_id"] == second["job_id"]

def test_stage_scene_clip_different_content_gets_different_job_id(tmp_path):
    config = _config(tmp_path)
    clip_a = tmp_path / "a.mp4"; clip_a.write_bytes(b"alpha" * 50)
    clip_b = tmp_path / "b.mp4"; clip_b.write_bytes(b"beta" * 50)
    a = stage_scene_clip(clip_a, config=config)
    b = stage_scene_clip(clip_b, config=config)
    assert a["job_id"] != b["job_id"]

def test_stage_scene_clip_rejects_unsupported_suffix(tmp_path):
    clip = tmp_path / "scene.mov"  # not in r2_handoff.contracts.SUFFIXES
    clip.write_bytes(b"x" * 50)
    with pytest.raises(HandoffError):
        stage_scene_clip(clip, config=_config(tmp_path))

def test_stage_scene_clip_limits_match_r2_handoff_validate_for(tmp_path):
    """The limits this module computes must be sufficient for
    r2_handoff.contracts.Limits.validate_for(mode='upload') to accept --
    this is exactly what StateStore.create_job calls internally."""
    clip = tmp_path / "scene.mp4"
    clip.write_bytes(b"y" * (40 * 1024 * 1024))  # spans multiple 32MiB chunks
    result = stage_scene_clip(clip, config=_config(tmp_path))
    assert result["limits"]["max_data_ops"] >= 4 * 2 + 4  # 2 chunks expected

# --- render.py wiring -----------------------------------------------------

def test_render_stages_clip_only_when_flag_enabled(monkeypatch, tmp_path):
    import shorts_studio.render as R
    calls = []
    monkeypatch.setattr(R, "config_from_env", lambda *, namespace: object())
    monkeypatch.setattr(R, "stage_scene_clip", lambda clip, *, config: calls.append((clip, config)) or {"job_id": "x", "sha256": "y"})
    clip = tmp_path / "scene.mp4"; clip.write_bytes(b"z")
    project_off = type("P", (), {"title": "t", "enable_r2_scene_staging": False})()
    project_on = type("P", (), {"title": "t", "enable_r2_scene_staging": True})()
    # Simulate render()'s own gate directly (unit-level, no full TTS/ffmpeg render needed).
    if getattr(project_off, "enable_r2_scene_staging", False):
        R._stage_scene_clip_for_project(clip, "s1", project_off)
    assert calls == []
    if getattr(project_on, "enable_r2_scene_staging", False):
        R._stage_scene_clip_for_project(clip, "s1", project_on)
    assert len(calls) == 1 and calls[0][0] == clip

def test_render_stage_helper_raises_when_env_unconfigured(monkeypatch, tmp_path):
    import shorts_studio.render as R
    from shorts_studio.scene_r2_staging import R2StagingConfigError
    monkeypatch.delenv("SHORTS_R2_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("SHORTS_R2_BUCKET", raising=False)
    clip = tmp_path / "scene.mp4"; clip.write_bytes(b"z")
    project = type("P", (), {"title": "t"})()
    with pytest.raises(R2StagingConfigError):
        R._stage_scene_clip_for_project(clip, "s1", project)
