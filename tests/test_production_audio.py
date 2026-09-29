import json
import shutil
import subprocess
from types import SimpleNamespace

import pytest

import shorts_studio.render as R

requires_ffmpeg = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="requires ffmpeg/ffprobe",
)


@requires_ffmpeg
def test_mix_production_audio_keeps_video_duration_and_adds_optional_layers(tmp_path):
    source = tmp_path / "source.mp4"
    subprocess.run([
        "ffmpeg","-y",
        "-f","lavfi","-i","color=c=black:s=320x240:r=30:d=2",
        "-f","lavfi","-i","sine=frequency=440:sample_rate=48000:duration=2",
        "-shortest","-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac",
        str(source),
    ],check=True,capture_output=True)

    bg = tmp_path / "bg.wav"
    sfx = tmp_path / "sfx.wav"
    subprocess.run(["ffmpeg","-y","-f","lavfi","-i","sine=frequency=220:sample_rate=48000:duration=2",str(bg)],check=True,capture_output=True)
    subprocess.run(["ffmpeg","-y","-f","lavfi","-i","sine=frequency=880:sample_rate=48000:duration=0.25",str(sfx)],check=True,capture_output=True)

    beat = SimpleNamespace(start=0.5,sfx_asset=str(sfx),sfx_gain_db=-18.0)
    scene = SimpleNamespace(id="s1",visual_beats=[beat])
    project = SimpleNamespace(
        scenes=[scene],
        background_music=str(bg),
        background_music_gain_db=-30.0,
    )
    out = tmp_path / "mixed.mp4"
    result = R._mix_production_audio(
        source,project,[{"scene":"s1","start":0.0,"duration":2.0}],out
    )
    assert result == out
    assert out.is_file() and out.stat().st_size > 0

    probe=json.loads(subprocess.run([
        "ffprobe","-v","error","-show_entries","format=duration",
        "-show_entries","stream=codec_type","-of","json",str(out)
    ],capture_output=True,text=True,check=True).stdout)
    assert 1.8 <= float(probe["format"]["duration"]) <= 2.2
    assert {s["codec_type"] for s in probe["streams"]} >= {"video","audio"}


def test_mix_production_audio_is_noop_when_no_layers_are_declared(tmp_path):
    source = tmp_path / "already.mp4"
    project = SimpleNamespace(scenes=[],background_music=None)
    result = R._mix_production_audio(source,project,[],tmp_path/"unused.mp4")
    assert result == source
