"""Print the critical frames to --preview check for a progressive manifest,
chunked to fit render_curious_mechanics.py's 12-frame sparse --frame-list
cap. One CHUNK_<i> line per chunk, comma-separated frame numbers -- meant to
be consumed by a CI step, not a human.

Deliberately self-contained (does not add anything to
curious_mechanics_timeline.py, only reads load_episode()'s already-public
output): that module is a push-trigger path for the full 30-shard
production render workflow, so adding preflight-only logic to it would
make iterating on this checker alone re-trigger the expensive matrix. The
breakpoints below are duplicated from curious_mechanics_timeline.py's own
travel_x/lane_return_offset (90, and 75/720 respectively) -- if those ever
move, update both.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from shorts_studio.factory.curious_mechanics_timeline import load_episode

# Frames where travel_x's slope (90) or lane_return_offset's ramps (75, 720)
# change: a shot whose span crosses one of these, or whose own start/end sit
# far from its camera anchor along whichever side has the faster local rate,
# is the shot most likely to clip. Not exhaustive proof -- real Blender
# projection is -- but a cheap, no-render way to pick which frames are worth
# spending an actual (low-res/low-sample --preview) Blender check on before
# committing to a full production matrix.
KINEMATIC_BREAKPOINTS = (75, 90, 720)
RUMBLE_REVIEW_FRAMES = (616, 637)


def critical_preview_frames(episode, breakpoints=KINEMATIC_BREAKPOINTS):
    """For each shot: its own start/end (travel_x is monotonic in frame, so
    the two true extremes of forward travel from the shot's camera anchor
    are always at one of these) plus any global breakpoint (and
    breakpoint+1) that falls inside the shot, since lane_return_offset is
    only monotonic within a single regime and a shot that straddles one
    needs that interior extremum checked too."""
    frames = set()
    for shot in episode["shots"]:
        frames.add(shot["start"])
        frames.add(shot["end"])
        if shot["id"].endswith("rumble_mechanism_close"):
            for frame in RUMBLE_REVIEW_FRAMES:
                if shot["start"] <= frame <= shot["end"]:
                    frames.add(frame)
        for bp in breakpoints:
            if shot["start"] <= bp <= shot["end"]:
                frames.add(bp)
            if shot["start"] <= bp + 1 <= shot["end"]:
                frames.add(bp + 1)
    return sorted(frames)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--chunk-size", type=int, default=12)
    args = parser.parse_args()

    episode = load_episode(args.manifest)
    frames = critical_preview_frames(episode)
    chunks = [frames[i:i + args.chunk_size] for i in range(0, len(frames), args.chunk_size)]
    print("CRITICAL_FRAME_CHUNKS", len(chunks), flush=True)
    for i, chunk in enumerate(chunks):
        print(f"CHUNK_{i}", ",".join(str(f) for f in chunk), flush=True)


if __name__ == "__main__":
    main()
