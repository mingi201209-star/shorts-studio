import ast
import re
from pathlib import Path

from benchmarks.road_safety.assemble_driver_pilot import motion_body

ROOT = Path(__file__).resolve().parents[1]


def test_resume_keeps_scene_and_motion_identical():
    folder = ROOT / "benchmarks/road_safety"
    old = (folder / "renderer_snapshots/render_driver_insert_055db61.py").read_text()
    new = (folder / "render_driver_insert.py").read_text()
    a, b = "    bpy.ops.object.select_all", "    poses = []"
    assert old[old.index(a):old.index(b)] == new[new.index(a):new.index(b)]
    assert motion_body(old) == motion_body(new)


def test_parallel_ranges_cover_only_missing_frames_once():
    workflow = (ROOT / ".github/workflows/studio-org-driver-pilot.yml").read_text()
    match = re.search(r"start: (\[[^\]]+\])", workflow)
    starts = ast.literal_eval(match.group(1))
    frames = [n for start in starts for n in range(start, min(start + 4, 90) + 1)]
    assert frames == list(range(38, 91))
    assert len(frames) == len(set(frames)) == 53
