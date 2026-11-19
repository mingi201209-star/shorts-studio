import json
from pathlib import Path

from benchmarks.speed_bump import captions as c

PLAN = json.loads((Path(__file__).resolve().parents[1] / "examples/experiments/speed-bump-speech-plan.json").read_text())


def test_every_narration_sentence_has_single_line_curated_phrases():
    for beat in PLAN["variants"][0]["beats"]:
        assert beat["narration_en"] in c.CURATED, beat["narration_en"]
        groups = c.single_line_groups(beat["narration_en"])
        tokens = beat["narration_en"].split()
        assert groups[0][0] == 0 and groups[-1][1] == len(tokens)
        assert all(len(" ".join(tokens[a:b])) <= 24 for a, b in groups)
