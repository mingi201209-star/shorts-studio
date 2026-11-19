import ast
import re
from pathlib import Path

from benchmarks.road_safety.assemble_driver_pilot import motion_body

ROOT = Path(__file__).resolve().parents[1]


def test_renderer_change_retires_old_preserved_partial_inventory():
    """render_driver_insert.py was intentionally changed (continuous idle
    motion -- breathing + three blinks -- added inside the pre-notice,
    inter-notice/turn, and post-turn holds, to fix the confirmed
    boring-static-shot finding). The preserved partial inventory from run
    41416805484 was rendered with the old motion math, so it must now read
    as incompatible: assemble_driver_pilot.assemble()'s own safety
    assertion ("scene or motion changed; cannot reuse") is what protects
    against ever silently stitching those old-physics frames onto the
    changed renderer, and this test confirms that gate would in fact
    trip -- not that the renderer must stay frozen forever."""
    folder = ROOT / "benchmarks/road_safety"
    old = (folder / "renderer_snapshots/render_driver_insert_055db61.py").read_text()
    new = (folder / "render_driver_insert.py").read_text()
    assert motion_body(old) != motion_body(new)


def test_parallel_ranges_cover_only_missing_frames_once():
    workflow = (ROOT / ".github/workflows/studio-org-driver-pilot.yml").read_text()
    match = re.search(r"start: (\[[^\]]+\])", workflow)
    starts = ast.literal_eval(match.group(1))
    frames = [n for start in starts for n in range(start, min(start + 4, 90) + 1)]
    assert frames == list(range(38, 91))
    assert len(frames) == len(set(frames)) == 53


def test_idle_motion_fresh_render_shards_cover_all_90_frames_once():
    """The idle-motion fix changed the motion for every frame (the breathing
    term runs the whole clip), so this is a from-scratch render -- unlike
    the production workflow above, it must cover 1-90 once each, not just
    the previously-missing 53."""
    workflow = (ROOT / ".github/workflows/driver-pilot-idle-motion-render.yml").read_text()
    match = re.search(r"start: (\[[^\]]+\])", workflow)
    starts = ast.literal_eval(match.group(1))
    frames = [n for start in starts for n in range(start, min(start + 4, 90) + 1)]
    assert frames == list(range(1, 91))
    assert len(frames) == len(set(frames)) == 90
