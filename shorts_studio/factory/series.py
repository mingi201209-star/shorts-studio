"""The launch lane is deliberately limited to seven related U.S. road-safety topics."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .contracts import FactoryManifest

ROAD_SAFETY_FIRST_SEVEN = (
    "guardrail-deflection",
    "rumble-strip-alerts",
    "breakaway-signposts",
    "crash-cushion-barrels",
    "runaway-truck-ramps",
    "retroreflective-road-paint",
    "bridge-expansion-joints",
)


class SeriesScope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: Literal[1]
    series_id: Literal["hidden-engineering-american-roads"]
    ordered_topic_ids: tuple[str, ...]

    @classmethod
    def load(cls, path: str | Path) -> SeriesScope:
        value = cls.model_validate(json.loads(Path(path).read_text(encoding="utf8")))
        if value.ordered_topic_ids != ROAD_SAFETY_FIRST_SEVEN:
            raise ValueError("road-safety first season must preserve the agreed seven topic IDs")
        return value


def require_topic_in_series(topic: FactoryManifest, series: SeriesScope) -> None:
    if topic.topic_id not in series.ordered_topic_ids:
        raise ValueError(
            f"{topic.topic_id!r} is not in the approved first-season road-safety series"
        )
