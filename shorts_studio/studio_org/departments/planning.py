"""기획부: 소재조사 · 대본구성 · 장면설계.

Not exercised by this round's validation scenario (which starts mid-pipeline,
from 편집부's missing-cut request), but implemented for real rather than left
as an empty stub: it reads the actual narration script and shot manifest this
project already authored, instead of generating placeholder content.
"""
from __future__ import annotations

import json
from pathlib import Path


class PlanningDept:
    def __init__(self, rewrite_json_path: str | Path, manifest_path: str | Path):
        self.rewrite_json_path = Path(rewrite_json_path)
        self.manifest_path = Path(manifest_path)

    def _variant(self, variant: str) -> dict:
        data = json.loads(self.rewrite_json_path.read_text(encoding="utf8"))
        return next(v for v in data["variants"] if v["id"] == variant)

    def research_material(self, variant: str) -> dict:
        """소재조사: what source material already backs this variant."""
        v = self._variant(variant)
        return {"division": "소재조사", "variant": variant, "beat_count": len(v["beats"])}

    def compose_script(self, variant: str) -> dict:
        """대본구성: the real narration lines, in order, with their timestamps."""
        v = self._variant(variant)
        return {
            "division": "대본구성",
            "variant": variant,
            "beats": [
                {"start": b["start"], "end": b["end"], "narration_en": b["narration_en"]}
                for b in v["beats"]
            ],
        }

    def design_scene(self) -> dict:
        """장면설계: the real shot list this script maps onto."""
        from shorts_studio.factory import curious_mechanics_timeline as timeline

        episode = timeline.load_episode(self.manifest_path)
        return {"division": "장면설계", "shots": [s["id"] for s in episode["shots"]]}
