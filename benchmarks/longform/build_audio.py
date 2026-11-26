"""Builds a long-form film's narration blocks (one per chapter) from the captured lines, with the Shorts' audio rules except the
total-silence cap: a minute of speech has more short pauses between sentences than a 35 s Short, so only the long-dead-air rule (no
gap over 0.9 s) is kept. Usage: PYTHONPATH=$PWD python3 benchmarks/longform/build_audio.py CAPTURE_DIR OUT_DIR VARIANT..."""
import re
import sys
from pathlib import Path

from benchmarks.road_safety import curious_mechanics_audio as cma
from benchmarks.road_safety.episode2_film import run


def long_form_silence(path):
    result = run(["ffmpeg", "-hide_banner", "-i", path, "-af", "silencedetect=noise=-35dB:d=0.3", "-vn", "-f", "null", "-"])
    gaps = [float(n) for n in re.findall(r"silence_duration:\s*([0-9.]+)", result.stderr)]
    assert max(gaps, default=0) <= .9, ("LONG_DEAD_AIR", gaps)
    return gaps


cma.silence = long_form_silence

if __name__ == "__main__":
    cap, out = Path(sys.argv[1]), Path(sys.argv[2])
    for v in sys.argv[3:]:
        cma.build(cap / v, out / v, 120, trim=True, gap_s=0.22)
        print("built", v, flush=True)
