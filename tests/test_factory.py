import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from shorts_studio.factory import FactoryManifest, TemplateRegistry, create_plan
from shorts_studio.factory.contracts import Rig

EX = Path(__file__).resolve().parents[1] / "examples" / "factory"


def load(topic="guardrail"):
    return FactoryManifest.load(EX / f"{topic}.json")


def test_two_distinct_topic_contracts_valid():
    a, b = load(), load("differential")
    assert a.topic_id != b.topic_id
    assert a.total_frames == b.total_frames == 240
    assert a.output.width == 1080 and b.output.height == 1920
    assert all(s.camera == "fixed" for s in a.shots + b.shots)


def test_incomplete_rigs_block_render_instead_of_claiming_success(tmp_path):
    result = create_plan(load(), TemplateRegistry.load(EX / "rigs.json"), tmp_path)
    assert not result["ready_to_render"]
    assert [s["render"] for s in result["shots"]] == ["blocked", "blocked"]
    assert result["shots"][0]["frame_start"] == 1
    assert result["shots"][-1]["frame_end"] == 240


def test_narration_change_does_not_invalidate_visual_cache_key(tmp_path):
    m = load()
    changed = m.model_copy(update={"shots": (m.shots[0].model_copy(
        update={"narration_en": "A very different line of English speech."}),) + m.shots[1:]})
    r = TemplateRegistry.load(EX / "rigs.json")
    before, after = create_plan(m, r, tmp_path), create_plan(changed, r, tmp_path)
    assert before["shots"][0]["visual_key"] == after["shots"][0]["visual_key"]
    assert before["shots"][0]["speech_key"] != after["shots"][0]["speech_key"]


def test_visual_params_change_invalidates_only_one_shot(tmp_path):
    m = load()
    changed = m.model_copy(update={"shots": (
        m.shots[0].model_copy(update={"params": {"contact_width": 1.5}}),) + m.shots[1:]})
    r = TemplateRegistry.load(EX / "rigs.json")
    before, after = create_plan(m, r, tmp_path), create_plan(changed, r, tmp_path)
    assert before["shots"][0]["visual_key"] != after["shots"][0]["visual_key"]
    assert before["shots"][1]["visual_key"] == after["shots"][1]["visual_key"]


@pytest.mark.parametrize("field,value", [
    ("output", {"width": 720}),
    ("output", {"upper_text": True}),
    ("output", {"frame_mode": "held_frame"}),
    ("language", "ko"),
    ("bogus", 123),
])
def test_degraded_profiles_or_unknown_fields_rejected(field, value):
    raw = json.loads((EX / "guardrail.json").read_text())
    raw[field] = value
    with pytest.raises(ValidationError):
        FactoryManifest.model_validate(raw)


def test_invalid_asset_and_duplicate_ids_rejected():
    raw = json.loads((EX / "guardrail.json").read_text())
    raw["shots"] += [raw["shots"][0]]
    with pytest.raises(ValidationError):
        FactoryManifest.model_validate(raw)
    raw = json.loads((EX / "guardrail.json").read_text())
    raw["shots"][0]["assets"] = ["untracked"]
    with pytest.raises(ValidationError):
        FactoryManifest.model_validate(raw)


def test_ready_rig_checksum_fail_closed(tmp_path):
    script = tmp_path / "rig.py"
    script.write_text("print(unverified)")
    rig = Rig(rig_id="contact_deflection", status="ready", source_sha256="0" * 64,
              entrypoint=str(script))
    registry = TemplateRegistry(rigs=(rig,))
    result = create_plan(load(), registry, tmp_path)
    assert not result["ready_to_render"]
    assert "renderer source checksum mismatch" in result["shots"][0]["blockers"]



def test_invalid_cache_proof_never_hits(tmp_path):
    m = load()
    script = tmp_path / "rig.py"
    script.write_text("print('ok')")
    import hashlib
    hashcode = hashlib.sha256(script.read_bytes()).hexdigest()
    rig = Rig(rig_id="contact_deflection", status="ready",
              source_sha256=hashcode, entrypoint=str(script))
    r = TemplateRegistry(rigs=(rig,))
    first = create_plan(m, r, tmp_path)
    folder = tmp_path / first["shots"][0]["visual_key"]
    folder.mkdir(parents=True)
    (folder / "native.mp4").write_bytes(b"not a real video")
    (folder / "proof.json").write_text(json.dumps({
        "visual_key": first["shots"][0]["visual_key"],
        "frame_count": 90, "width": 1080, "height": 1920, "fps": 30,
        "unique_decoded_frames": 90, "verified": True}))
    result = create_plan(m, r, tmp_path)
    assert result["shots"][0]["render"] == "needs_render"
