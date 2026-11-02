"""Manifest roles describe plans, never proof that a rendered clip exists."""
from __future__ import annotations

import hashlib
from pathlib import Path


class AssetRegistry:
    def __init__(self, known_roles: set[str] | None = None):
        self._known_roles: set[str] = set(known_roles or ())
        self._clips: dict[str, dict[str, str]] = {}

    @classmethod
    def from_manifest(cls, manifest_path: str | Path) -> AssetRegistry:
        from shorts_studio.factory import curious_mechanics_timeline as timeline

        episode = timeline.load_episode(Path(manifest_path))
        roles = {shot["id"] for shot in episode["shots"]}
        roles |= set(timeline._STYLE.values())
        return cls(known_roles=roles)

    def register_clip(self, shot: str, path: Path, sha256: str) -> None:
        """Register bytes by digest; this is availability, not an editorial QA pass."""
        path = path.resolve()
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != sha256:
            raise ValueError("clip missing or SHA256 mismatch")
        self._clips[shot] = {"shot_id": shot, "path": str(path), "sha256": sha256,
                             "source": "verified_file"}

    def find_clip(self, shot_requirement: str) -> dict[str, str] | None:
        clip = self._clips.get(shot_requirement)
        if clip is None:
            return None
        path = Path(clip["path"])
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != clip["sha256"]:
            return None
        return dict(clip)
