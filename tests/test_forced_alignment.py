import pytest

from shorts_studio.forced_alignment import strict_aligned_words


def test_strict_aligned_words_restores_authored_korean_punctuation():
    text = "빗길에선 타이어가 돌고 있어도 도로에 안 닿을 수 있습니다."
    raw = [
        {"word": "빗길에선", "start": 0.00, "end": 0.45},
        {"word": "타이어가", "start": 0.47, "end": 0.91},
        {"word": "돌고", "start": 0.93, "end": 1.15},
        {"word": "있어도", "start": 1.16, "end": 1.48},
        {"word": "도로에", "start": 1.58, "end": 1.93},
        {"word": "안", "start": 1.95, "end": 2.06},
        {"word": "닿을", "start": 2.08, "end": 2.31},
        {"word": "수", "start": 2.33, "end": 2.42},
        {"word": "있습니다", "start": 2.44, "end": 2.89},
    ]
    words = strict_aligned_words(text, raw)
    assert words[-1]["text"] == "있습니다."
    assert words[-1]["end"] == pytest.approx(2.89)


def test_strict_aligned_words_fails_closed_on_pronunciation_token_drift():
    text = "타이어 밑으로 파고드는 물입니다."
    raw = [
        {"word": "타이어", "start": 0.0, "end": 0.3},
        {"word": "밑으로", "start": 0.31, "end": 0.6},
        {"word": "파고", "start": 0.62, "end": 0.8},
        {"word": "되는", "start": 0.81, "end": 1.0},
        {"word": "물입니다", "start": 1.02, "end": 1.4},
    ]
    with pytest.raises(ValueError, match="lexical words"):
        strict_aligned_words(text, raw)


@pytest.mark.parametrize(
    "raw",
    [
        [{"word": "물이", "start": None, "end": 0.3}],
        [{"word": "물이", "start": 0.4, "end": 0.3}],
    ],
)
def test_strict_aligned_words_rejects_missing_or_invalid_time(raw):
    with pytest.raises(ValueError):
        strict_aligned_words("물이", raw)


@pytest.mark.parametrize("field,value", [("start", float("nan")), ("end", float("nan")), ("start", float("inf")), ("end", float("inf"))])
def test_strict_aligned_words_rejects_nonfinite_time(field, value):
    raw = {"word": "물이", "start": 0.0, "end": 0.3}
    raw[field] = value
    with pytest.raises(ValueError, match="invalid timing"):
        strict_aligned_words("물이", [raw])


def test_alignment_cli_disables_timestamp_interpolation(monkeypatch, tmp_path):
    import json
    import sys
    import numpy as np
    from types import SimpleNamespace
    from scripts import whisperx_align_narration as cli
    text = tmp_path / "text.txt"
    text.write_text("물이")
    output = tmp_path / "words.json"
    monkeypatch.setattr(sys, "version_info", (3, 13, 0))
    monkeypatch.setattr(sys, "argv", ["align", "--audio", str(tmp_path / "audio.wav"), "--text", str(text), "--out", str(output)])
    def align(*args, **kwargs):
        assert kwargs["interpolate_method"] == "ignore"
        return {"word_segments": [{"word": "물이", "start": 0.0, "end": 0.3}]}
    monkeypatch.setitem(sys.modules, "whisperx", SimpleNamespace(load_audio=lambda *a: np.zeros(16000), load_align_model=lambda **kw: (object(), {}), align=align))
    cli.main()
    assert json.loads(output.read_text()) == [{"text": "물이", "start": 0.0, "end": 0.3}]
