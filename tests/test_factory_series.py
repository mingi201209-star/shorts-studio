"""Guardrail series lane remains narrow until the owner explicitly expands it."""
import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from shorts_studio.factory.contracts import FactoryManifest
from shorts_studio.factory.series import (
    ROAD_SAFETY_FIRST_SEVEN,
    SeriesScope,
    require_topic_in_series,
)

ROOT = Path(__file__).resolve().parents[1]
SERIES = ROOT / "examples" / "factory" / "road-safety-series.json"


def test_series_has_exactly_the_agreed_seven_topics():
    series = SeriesScope.load(SERIES)
    assert len(series.ordered_topic_ids) == 7
    assert series.ordered_topic_ids == ROAD_SAFETY_FIRST_SEVEN
    assert len(set(series.ordered_topic_ids)) == 7


def test_guardrail_and_rumble_strip_belong():
    series = SeriesScope.load(SERIES)
    for name in ("guardrail", "rumble-strips"):
        m = FactoryManifest.load(ROOT / "examples" / "factory" / f"{name}.json")
        require_topic_in_series(m, series)


def test_unrelated_differential_topic_is_blocked():
    m = FactoryManifest.load(ROOT / "examples" / "factory" / "differential.json")
    with pytest.raises(ValueError, match="not in the approved"):
        require_topic_in_series(m, SeriesScope.load(SERIES))


def test_missing_and_added_topics_are_rejected(tmp_path):
    raw = json.loads(SERIES.read_text())
    raw["ordered_topic_ids"].append("differential-gears")
    p = tmp_path / "illegal-extra.json"
    p.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="preserve"):
        SeriesScope.load(p)
    raw["ordered_topic_ids"] = raw["ordered_topic_ids"][:-2]
    p.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="preserve"):
        SeriesScope.load(p)


def test_series_contract_fails_unknown_fields():
    raw = json.loads(SERIES.read_text())
    raw["allow_unrelated_topics"] = True
    with pytest.raises(ValidationError):
        SeriesScope.model_validate(raw)


def test_cli_rejects_out_of_series_even_if_rig_exists(tmp_path):
    cmd = [sys.executable, "-m", "shorts_studio.factory",
           str(ROOT / "examples" / "factory" / "differential.json"),
           "--registry", str(ROOT / "examples" / "factory" / "rigs.json"),
           "--cache-dir", str(tmp_path), "--series", str(SERIES)]
    out = subprocess.run(cmd, check=False, text=True, capture_output=True)
    assert out.returncode != 0
    assert "not in the approved first-season" in out.stderr
