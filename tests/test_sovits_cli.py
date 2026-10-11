import json
import sys
from types import SimpleNamespace

import pytest

from scripts import gpt_sovits_narration as cli


def test_quota_failure_stops_retries(monkeypatch, tmp_path):
    calls = []
    class Client:
        def __init__(self, *args, **kwargs):
            pass
        def predict(self, *args, **kwargs):
            calls.append(1)
            raise RuntimeError("You have exceeded your ZeroGPU quota")
    monkeypatch.setitem(sys.modules, "gradio_client", SimpleNamespace(Client=Client, handle_file=lambda x: x))
    with pytest.raises(RuntimeError, match="quota exhausted"):
        cli.synthesize("물입니다", tmp_path / "ref.wav", "참조", [], tmp_path / "out.wav")
    assert len(calls) == 1


def test_failed_second_take_preserves_first_report(monkeypatch, tmp_path):
    reftext = tmp_path / "ref.txt"
    reftext.write_text("참조")
    out = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", ["sovits", "--marked", "물이 들어옵니다.", "--ref", str(tmp_path / "ref.wav"), "--ref-text", str(reftext), "--takes", "2", "--out", str(out)])
    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=lambda *a, **kw: object()))
    calls = []
    def synthesize(*args):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("quota exhausted")
        args[4].write_bytes(b"completed audio")
        return args[4]
    monkeypatch.setattr(cli, "synthesize", synthesize)
    monkeypatch.setattr(cli, "retime", lambda *args: {"recognised": "물이 들어옵니다."})
    with pytest.raises(RuntimeError, match="quota exhausted"):
        cli.main()
    report = json.loads((out / "report.json").read_text())
    assert report["status"] == "incomplete"
    assert report["failed_take"] == 2
    assert report["takes"][0]["recognised"] == "물이 들어옵니다."
    assert (out / "take1_raw.wav").read_bytes() == b"completed audio"
