"""Manual rehearsal of the fresh-film shard and assemble QA on synthetic frames.

Run from the repository root before dispatching the 900-frame workflow:
    PYTHONPATH=. python benchmarks/road_safety/rehearse_episode2_film.py --out /tmp/rehearsal
Synthetic stand-ins prove the pipeline, never the picture; the MP4 is not a candidate.
"""
import argparse
import json
import random
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import episode2_film as film

from shorts_studio.factory.rumble_episode2 import (
    load_episode,
    shot_for_frame,
    travel_x,
)
from shorts_studio.factory.rumble_native_shard_qa import digest

parser = argparse.ArgumentParser()
parser.add_argument("--out", type=Path, required=True)
root = parser.parse_args().out
chunks = root / "chunks"
out = root / "review"
shutil.rmtree(chunks, ignore_errors=True); shutil.rmtree(out, ignore_errors=True)
episode = load_episode(film.MANIFEST)
cameras = {s["id"]: [[1.0 + i, -4.0, 2.0], [1.1, 0.0, 0.3], 3.2]
           for i, s in enumerate(episode["shots"])}
for first in range(1, 901, 30):
    d = chunks / f"rumble-native-{first}"; d.mkdir(parents=True)
    records = []
    for n in range(first, first + 30):
        rng = random.Random(n)
        im = Image.new("RGB", (1080, 1920), (110, 112, 108))
        draw = ImageDraw.Draw(im)
        x = int(n * 1.1) % 900
        draw.rectangle((x, 600, x + 180, 900), fill=(30, 70, 160))
        draw.text((40, 40), f"frame {n}", fill=(255, 255, 255))
        im.paste(Image.frombytes("RGB", (160, 160), rng.randbytes(160 * 160 * 3)), (460, 1100))
        p = d / f"frame_{n:04d}.png"; im.save(p, compress_level=1)
        records.append({"frame": n, "shot_id": shot_for_frame(episode, n)["id"],
                        "absolute_x_m": round(travel_x(n), 7), "sha256": digest(p),
                        "render_seconds": 1.0,
                        "near_tyre_min_z_m": {"Front_tire": 0.0001, "Rear_tire": 0.0001}})
    nums = list(range(first, first + 30))
    proof = {"episode_id": episode["episode_id"], "source_sha256": episode["source_scene_sha256"],
             "renderer_source_sha256": digest(film.RENDERER), "renderer": "CYCLES",
             "preview_only": False, "frames": 30, "first_frame": first, "last_frame": nums[-1],
             "frame_numbers": nums, "fps": 30, "resolution": [1080, 1920], "cycles_samples": 32,
             "render_seconds": [1.0] * 30,
             "camera_by_shot": {r["shot_id"]: cameras[r["shot_id"]] for r in records},
             "original_frame_records": records, "car_mesh_parts": 72, "rotating_wheel_pivots": 4,
             "physically_calibrated": False, "upload_ready": False}
    (d / "episode-proof.json").write_text(json.dumps(proof))
    film.shard(d)
    for p in d.glob("frame_*.png"):
        p.unlink()   # the CI artifact carries only proof + lossless clip
out.mkdir(parents=True)
film.assemble(out, chunks)
print("REHEARSAL_DONE", json.loads((out / "film_validation.json").read_text())["technical_status"])
