"""관리부/자원관리's view of what already exists -- backed by the real manifest.

This does not invent a separate catalogue of fake assets. It reads the same
episode manifest the render pipeline itself uses
(shorts_studio.factory.curious_mechanics_timeline.load_episode), so "no
existing clip" is a fact about the real production, not a scripted mock. A
shot id or role that is genuinely in the manifest is "found"; anything else,
including a role that would require a human/driver figure (which the asset
inventory in benchmarks/road_safety/curious_mechanics_asset_inventory.py
already established does not exist in the licensed CC0 scene), is correctly
reported as not found.
"""
from __future__ import annotations

from pathlib import Path


class AssetRegistry:
    def __init__(self, known_roles: set[str] | None = None):
        self._known_roles: set[str] = set(known_roles or ())

    @classmethod
    def from_manifest(cls, manifest_path: str | Path) -> "AssetRegistry":
        from shorts_studio.factory import curious_mechanics_timeline as timeline

        episode = timeline.load_episode(Path(manifest_path))
        roles = {shot["id"] for shot in episode["shots"]}
        roles |= set(timeline._STYLE.values())
        return cls(known_roles=roles)

    def find_clip(self, shot_requirement: str) -> dict[str, str] | None:
        if shot_requirement in self._known_roles:
            return {"shot_id": shot_requirement, "source": "existing_manifest"}
        return None
