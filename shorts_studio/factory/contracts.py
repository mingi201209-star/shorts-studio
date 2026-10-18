"""Fail-closed, topic-agnostic contracts for native 3D short production."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

SHA = re.compile(r"[a-f0-9]{64}\Z")
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class VideoProfile(StrictModel):
    width: Literal[1080] = 1080
    height: Literal[1920] = 1920
    fps: Literal[30] = 30
    frame_mode: Literal["native_unique"] = "native_unique"
    upper_text: Literal[False] = False
    caption_position: Literal["bottom_safe"] = "bottom_safe"
    renderer: Literal["cycles32"] = "cycles32"


class Evidence(StrictModel):
    claim: str = Field(min_length=12)
    source_url: HttpUrl


class Asset(StrictModel):
    asset_id: str = Field(pattern=r"^[a-z][a-z0-9_-]+$")
    source_url: HttpUrl
    license: Literal["CC0", "CC-BY-4.0", "OWNED"]
    sha256: str
    unit_scale_m: float = Field(gt=0, le=1000)

    @model_validator(mode="after")
    def check_hash(self):
        if not SHA.fullmatch(self.sha256):
            raise ValueError("asset sha256 must be lowercase 64-character hex")
        return self


class Shot(StrictModel):
    shot_id: str = Field(pattern=r"^[a-z][a-z0-9_-]+$")
    frames: int = Field(ge=1)
    rig_id: str = Field(pattern=r"^[a-z][a-z0-9_-]+$")
    camera: Literal["fixed"] = "fixed"
    visual_proof: str = Field(min_length=12)
    mechanism_change: str = Field(min_length=12)
    narration_en: str = Field(min_length=10)
    assets: tuple[str, ...] = ()
    params: dict[str, str | int | float | bool] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_visual(self):
        if len(set(self.assets)) != len(self.assets):
            raise ValueError("duplicate asset within shot")
        return self


class FactoryManifest(StrictModel):
    version: Literal[1] = 1
    topic_id: str
    language: Literal["en"] = "en"
    headline: str = Field(min_length=10)
    hook_visual: str = Field(min_length=12)
    output: VideoProfile = Field(default_factory=VideoProfile)
    evidence: tuple[Evidence, ...] = Field(min_length=1)
    assets: tuple[Asset, ...] = ()
    shots: tuple[Shot, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def check_consistency(self):
        if not SLUG.fullmatch(self.topic_id):
            raise ValueError("topic_id must be a lowercase hyphen slug")
        shot_ids = [shot.shot_id for shot in self.shots]
        if len(shot_ids) != len(set(shot_ids)):
            raise ValueError("duplicate shot_id")
        ids = [asset.asset_id for asset in self.assets]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate asset_id")
        unknown = {asset for shot in self.shots for asset in shot.assets} - set(ids)
        if unknown:
            raise ValueError(f"shots reference unknown assets: {sorted(unknown)}")
        return self

    @classmethod
    def load(cls, path: str | Path) -> "FactoryManifest":
        return cls.model_validate(json.loads(Path(path).read_text(encoding="utf8")))

    @property
    def total_frames(self) -> int:
        return sum(shot.frames for shot in self.shots)


class Rig(StrictModel):
    rig_id: str = Field(pattern=r"^[a-z][a-z0-9_-]+$")
    status: Literal["ready", "planned"]
    source_sha256: str
    entrypoint: str | None = None

    @model_validator(mode="after")
    def check_rig(self):
        if not SHA.fullmatch(self.source_sha256):
            raise ValueError("rig source_sha256 must be lowercase 64-character hex")
        if self.status == "ready" and not self.entrypoint:
            raise ValueError("ready rig requires an entrypoint")
        return self


class TemplateRegistry(StrictModel):
    version: Literal[1] = 1
    rigs: tuple[Rig, ...]

    @model_validator(mode="after")
    def check_unique(self):
        ids = [rig.rig_id for rig in self.rigs]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate rig_id")
        return self

    @classmethod
    def load(cls, path: str | Path) -> "TemplateRegistry":
        return cls.model_validate(json.loads(Path(path).read_text(encoding="utf8")))
