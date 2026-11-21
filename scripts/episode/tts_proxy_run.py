"""Runs a speech-capture script with edge-tts going through the session's HTTPS proxy (cloud sessions cannot reach the TTS service
directly). Usage, from the repo root:
  SPEECH_RATE=+3% SPEECH_REQUEST_GAP=4 PYTHONPATH=$PWD python3 scripts/episode/tts_proxy_run.py \\
      benchmarks/road_safety/curious_mechanics_speech.py --plan examples/experiments/<ep>-speech-plan.json --target-seconds 60 --out <dir>"""
import functools
import os
import runpy
import sys

import edge_tts

if os.environ.get("HTTPS_PROXY"):
    edge_tts.Communicate = functools.partial(edge_tts.Communicate, proxy=os.environ["HTTPS_PROXY"])
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
