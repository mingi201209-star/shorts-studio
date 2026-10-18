"""Deterministic per-shot dependency fingerprints. Never claims an uncached render exists."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .contracts import FactoryManifest, TemplateRegistry


def fingerprint(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf8")).hexdigest()


def create_plan(manifest: FactoryManifest, registry: TemplateRegistry, cache_dir: str | Path) -> dict:
    """Plan all native renders; caching requires exact matching provenance sidecars.

    Only a complete artifact+matching metadata can be a cache hit. A bare file
    (or unknown rig/old SHA) can never bypass native-frame verification.
    """
    rigs = {rig.rig_id: rig for rig in registry.rigs}
    assets = {asset.asset_id: asset for asset in manifest.assets}
    shots = []
    cursor = 1
    cache_dir = Path(cache_dir)
    for shot in manifest.shots:
        rig = rigs.get(shot.rig_id)
        blockers = []
        if rig is None:
            blockers.append("unknown rig")
        elif rig.status != "ready":
            blockers.append("rig not implemented")
        # For future ready rigs, caller must resolve the entrypoint and verify
        # its source SHA before running. A plan alone is never a render job.
        elif not rig.entrypoint or not Path(rig.entrypoint).is_file():
            blockers.append("missing renderer entrypoint")
        elif hashlib.sha256(Path(rig.entrypoint).read_bytes()).hexdigest() != rig.source_sha256:
            blockers.append("renderer source checksum mismatch")
        visual_key = fingerprint({
            "profile": manifest.output.model_dump(mode="json"),
            "rig": rig.model_dump(mode="json") if rig else {"unknown": shot.rig_id},
            "visual": {"id": shot.shot_id, "frames": shot.frames,
                       "camera": shot.camera, "purpose": shot.visual_proof,
                       "change": shot.mechanism_change, "params": shot.params},
            "assets": [assets[a].model_dump(mode="json") for a in shot.assets],
        })
        # Voice and captions never invalidate visual-only renders.
        speech_key = fingerprint({"language": manifest.language, "text": shot.narration_en})
        root = cache_dir / visual_key
        artifact = root / "native.mp4"
        sidecar = root / "proof.json"
        hit = False
        if not blockers and artifact.is_file() and sidecar.is_file():
            try:
                proof = json.loads(sidecar.read_text(encoding="utf8"))
                expected = {"visual_key": visual_key, "frame_count": shot.frames,
                            "width": 1080, "height": 1920, "fps": 30,
                            "unique_decoded_frames": shot.frames, "verified": True}
                digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
                hit = (all(proof.get(k) == v for k, v in expected.items())
                       and proof.get("artifact_sha256") == digest)
            except (OSError, ValueError):
                hit = False
        shots.append({"shot_id": shot.shot_id, "frame_start": cursor,
                      "frame_end": cursor + shot.frames - 1, "visual_key": visual_key,
                      "speech_key": speech_key, "render": "blocked" if blockers else ("cache_hit" if hit else "needs_render"),
                      "blockers": blockers})
        cursor += shot.frames
    return {"topic_id": manifest.topic_id, "total_frames": manifest.total_frames,
            "fps": manifest.output.fps, "ready_to_render": all(not s["blockers"] for s in shots),
            "shots": shots,
            "disclaimer": "Planning is not a quality PASS, rendered video, or upload authorization."}
