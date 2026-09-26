"""Regression coverage for extra="forbid" on every manifest model (Project,
Scene, Motion, NarrationPhrase, VisualBeat, AssetCandidate).

Real bug this guards against: examples/train_wheels.json (PR #24) shipped
with a real hook_type declaration that a pre-retention-engine build of
these models silently dropped -- pydantic's own default is
extra="ignore", so an unrecognized or typo'd manifest field simply
vanishes with no error and `shorts_studio validate` still reports PASS.
Phase 0 of the retention-foundation integration proved (not assumed) that
forbidding extra fields rejects zero real fields across every production
manifest (comet.json, radium_girls.json, titanic_fourth_funnel.json,
train_wheels.json) before this was enabled repo-wide; these tests are the
permanent regression guard for that same guarantee.
"""
import json

import pytest
from pydantic import ValidationError

from shorts_studio.models import Project


def _base_manifest():
    return {
        "title": "t",
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "scenes": [
            {
                "id": "s1",
                "narration": "하나",
                "visual_description": "d",
                "narration_plan": [
                    {"role": "HOOK", "text": "하나", "hook_type": "contradiction"},
                ],
                "visual_beats": [
                    {"start": 0.0, "asset_url": "https://x/a.jpg"},
                ],
            }
        ],
    }


def test_valid_hook_type_passes():
    Project.model_validate(_base_manifest())  # must not raise


def test_unknown_project_field_fails():
    m = _base_manifest()
    m["totally_made_up_project_field"] = True
    with pytest.raises(ValidationError, match="totally_made_up_project_field"):
        Project.model_validate(m)


def test_unknown_scene_field_fails():
    m = _base_manifest()
    m["scenes"][0]["totally_made_up_scene_field"] = True
    with pytest.raises(ValidationError, match="totally_made_up_scene_field"):
        Project.model_validate(m)


def test_unknown_narration_phrase_field_fails():
    m = _base_manifest()
    m["scenes"][0]["narration_plan"][0]["totally_made_up_narration_field"] = True
    with pytest.raises(ValidationError, match="totally_made_up_narration_field"):
        Project.model_validate(m)


def test_unknown_visual_beat_field_fails():
    m = _base_manifest()
    m["scenes"][0]["visual_beats"][0]["totally_made_up_beat_field"] = True
    with pytest.raises(ValidationError, match="totally_made_up_beat_field"):
        Project.model_validate(m)


def test_hook_type_typo_fails():
    """The exact real-world shape of the bug: a manifest author means to
    write hook_type but typos the key name -- must fail loudly, not
    silently produce a NarrationPhrase with hook_type=None."""
    m = _base_manifest()
    m["scenes"][0]["narration_plan"][0] = {"role": "HOOK", "text": "하나", "hok_type": "contradiction"}
    with pytest.raises(ValidationError, match="hok_type"):
        Project.model_validate(m)


def test_invalid_hook_type_value_fails():
    m = _base_manifest()
    m["scenes"][0]["narration_plan"][0]["hook_type"] = "not_a_real_hook_type"
    with pytest.raises(ValidationError, match="hook_type must be one of"):
        Project.model_validate(m)


@pytest.mark.parametrize("path", [
    "examples/comet.json",
    "examples/radium_girls.json",
])
def test_real_manifests_have_no_unknown_fields(path):
    """The exact regression Phase 0 proved manually: every field actually
    present in these real production manifests is modeled, so extra="forbid"
    rejects none of them."""
    raw = json.loads(open(path, encoding="utf-8").read())
    Project.model_validate(raw)  # must not raise
