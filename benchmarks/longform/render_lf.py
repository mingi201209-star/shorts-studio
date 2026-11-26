"""Renders one episode's shots of a long-form film inside Blender: the episode's own renderer, its timeline swapped for the film's
virtual timeline of that episode and its frame set to 16:9. Environment: LF_FILM (e.g. lf01), LF_EPISODE (a key of
lf_timeline.EPISODES). Usage: LF_FILM=lf01 LF_EPISODE=rocknet blender -b -P benchmarks/longform/render_lf.py -- --source car.blend
--frames A-B --res-scale 0.6667 --samples 16 --out DIR (frames are the episode's virtual frames)."""
import importlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from benchmarks.longform import lf_timeline as lt  # noqa: E402

film = importlib.import_module(f"benchmarks.longform.{os.environ['LF_FILM']}")
key = os.environ["LF_EPISODE"]
renderer = importlib.import_module(lt.EPISODES[key][1])
renderer.tl = film.episode_timeline(key)
renderer.FRAME = lt.FRAME
print("LF_EPISODE " + key + " virtual frames " + str(renderer.tl.frame_count()), flush=True)
renderer.main()
