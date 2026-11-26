"""Storyboard stills for a long-form film's 16:9 framing, before the narration exists: renders the middle frame of each listed row of
one episode with the film's camera conversion (each row given 48 frames). Environment: LF_FILM, LF_EPISODE, LF_ROWS (comma list).
Usage: LF_FILM=lf01 LF_EPISODE=rocknet LF_ROWS=A1-boulder-in-the-net,C-chain-mail-rings blender -b -P benchmarks/longform/storyboard_lf.py --
--source car.blend --res-scale 0.3 --samples 8 --out DIR"""
import importlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from benchmarks.longform import lf_timeline as lt  # noqa: E402

film = importlib.import_module(f"benchmarks.longform.{os.environ['LF_FILM']}")
key = os.environ["LF_EPISODE"]
rows = os.environ["LF_ROWS"].split(",")
shots = []
for r in rows:
    sh = {"row": r, "frames": 48}
    sh.update(getattr(film, "OVERRIDES", {}).get((key, r), {}))
    shots.append(sh)
renderer = importlib.import_module(lt.EPISODES[key][1])
renderer.tl = lt.episode_timeline(key, shots)
renderer.FRAME = lt.FRAME
sys.argv += ["--list", ",".join(str(48 * i + 24) for i in range(len(rows)))]
renderer.main()
