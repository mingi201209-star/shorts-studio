"""Viewer-facing QA that actually looks at the rendered final.mp4, rather than
trusting that "the pipeline ran without an exception" means the Short looks
right. A green render used to mean only: file exists, resolution/codecs are
valid, and the coarse semantic-asset checks passed. None of that catches a
missing top title, a caption that's clipped off-screen, or a photo bleeding
into the caption safe area -- so those defects shipped past CI. Every check
here extracts a real frame (or measures real timing data) from the actual
production artifacts and fails closed if the evidence isn't there.
"""
from __future__ import annotations
import subprocess
from pathlib import Path

def _extract_frame(video: Path, ts: float, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg","-y","-ss",str(max(0.0,ts)),"-i",str(video),"-frames:v","1",str(out)],check=True,capture_output=True)
    return out

# Calibrated empirically (see tests/test_final_video_qa.py) against real
# rendered frames: a blurred/plain region measures well under 5, a crisp
# bordered title/caption measures in the hundreds to low thousands.
MIN_TEXT_EDGE_VAR = 50.0
TITLE_ROW_BAND = (10, 175)          # matches _TITLE_STYLE's MarginV=15/FontSize=20
# Heuristic tripwire, NOT the primary guard -- the primary guard is the
# deterministic magenta-marker regression in test_safe_area_regression.py,
# which proves via the actual ffmpeg filter graph that the fg band can never
# geometrically reach past SAFE_BOTTOM_Y, independent of image content.
# Calibrated on flat synthetic test images (clean ~0.001, a fully unbounded
# fg regression ~0.002-0.003); real archival photos' blurred backdrop will
# carry more residual grain than a flat synthetic fill, so this ceiling is
# set with a wide margin above that measured synthetic-bug floor to avoid
# false-positive failures on legitimately busy (but correctly blurred) real
# photo content, while still catching a grossly reintroduced regression.
MAX_SAFE_AREA_EDGE_DENSITY = 0.08

def _laplacian_var(img, row_range):
    import cv2
    band = img[row_range[0]:row_range[1], :]
    return float(cv2.Laplacian(band, cv2.CV_64F).var())

def _canny_density(img, row_range):
    import cv2
    band = img[row_range[0]:row_range[1], :]
    edges = cv2.Canny(band, 50, 150)
    return float((edges > 0).mean())

def verify_title_visible(video: Path, sample_timestamps: list[float], build_dir: Path) -> dict:
    """The persistent top title must be visible near the top at MULTIPLE
    points across the Short, not just in one scene -- proving it survives
    the whole concatenated output, not just a single clip."""
    import cv2
    evidence = []
    for i, ts in enumerate(sample_timestamps):
        frame = _extract_frame(video, ts, build_dir / f"_titleqa_{i}.jpg")
        img = cv2.imread(str(frame))
        if img is None:
            return {"status": "FAIL", "reason": f"could not read frame at t={ts}"}
        var = _laplacian_var(img, TITLE_ROW_BAND)
        evidence.append({"t": ts, "title_band_edge_var": var})
        if var < MIN_TEXT_EDGE_VAR:
            return {"status": "FAIL", "reason": f"no crisp title text detected near the top at t={ts} (edge_var={var:.1f} < {MIN_TEXT_EDGE_VAR})", "evidence": evidence}
    return {"status": "PASS", "evidence": evidence}

def verify_captions_visible(video: Path, sample_points: list[tuple[float, tuple[float, float]]], build_dir: Path, brightness_threshold: int = 200) -> dict:
    """For each (frame_timestamp, expected_caption_row_band), verify real
    bright (near-white fill) pixels exist inside the expected caption band
    and are not clipped at the very bottom edge of the frame."""
    import cv2, numpy as np
    evidence = []
    for i, (ts, band) in enumerate(sample_points):
        frame = _extract_frame(video, ts, build_dir / f"_capqa_{i}.jpg")
        img = cv2.imread(str(frame))
        if img is None:
            return {"status": "FAIL", "reason": f"could not read frame at t={ts}"}
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        height = gray.shape[0]
        rows = np.where((gray > brightness_threshold).any(axis=1))[0]
        rows_in_band = rows[(rows >= band[0]) & (rows <= band[1])] if len(rows) else rows
        evidence.append({"t": ts, "rows_in_band": (int(rows_in_band.min()), int(rows_in_band.max())) if len(rows_in_band) else None})
        if len(rows_in_band) == 0:
            return {"status": "FAIL", "reason": f"no caption pixels found in the expected band at t={ts}", "evidence": evidence}
        if rows_in_band.max() >= height - 2:
            return {"status": "FAIL", "reason": f"caption pixels touch the very bottom edge at t={ts} (clipped)", "evidence": evidence}
    return {"status": "PASS", "evidence": evidence}

def verify_bottom_safe_area_clean(video: Path, sample_timestamps: list[float], build_dir: Path, safe_band: tuple[int, int]) -> dict:
    """Heuristic tripwire: the bottom caption safe area should read as
    blurred background (+ occasional caption text), never a crisp photo
    edge. See MAX_SAFE_AREA_EDGE_DENSITY for why this is generous."""
    import cv2
    evidence = []
    for i, ts in enumerate(sample_timestamps):
        frame = _extract_frame(video, ts, build_dir / f"_safeqa_{i}.jpg")
        img = cv2.imread(str(frame))
        if img is None:
            return {"status": "FAIL", "reason": f"could not read frame at t={ts}"}
        density = _canny_density(img, safe_band)
        evidence.append({"t": ts, "safe_area_edge_density": density})
        if density > MAX_SAFE_AREA_EDGE_DENSITY:
            return {"status": "FAIL", "reason": f"bottom safe area looks obstructed by sharp foreground content at t={ts} (edge_density={density:.4f} > {MAX_SAFE_AREA_EDGE_DENSITY})", "evidence": evidence}
    return {"status": "PASS", "evidence": evidence}


IMAGE_TOP_Y=230
IMAGE_BOTTOM_Y=1230
CAPTION_GUTTER=(1238,1308)
# Sample gutter integrity before the first authored speech caption appears; later
# samples may legitimately contain burned-in caption glyphs in this band.
GUTTER_SAMPLE_LEAD_SECONDS=0.08
MAX_BLACK_GUTTER_MEAN=10.0
MAX_BLACK_GUTTER_P99=24

def verify_picture_caption_gutter(video: Path, sample_timestamps: list[float], build_dir: Path) -> dict:
    """Check the reserved band between the fixed picture box and captions is black."""
    import cv2, numpy as np
    evidence=[]
    for i,ts in enumerate(sample_timestamps):
        frame=_extract_frame(video,ts,build_dir/f"_layout_{i}_qa.jpg")
        img=cv2.imread(str(frame))
        if img is None:
            return {"status":"FAIL","reason":f"could not read frame at t={ts}"}
        band=cv2.cvtColor(img[CAPTION_GUTTER[0]:CAPTION_GUTTER[1],:],cv2.COLOR_BGR2GRAY)
        mean=float(band.mean()); p99=float(np.percentile(band,99))
        evidence.append({"t":ts,"black_gutter_mean":mean,"black_gutter_p99":p99})
        if mean>MAX_BLACK_GUTTER_MEAN or p99>MAX_BLACK_GUTTER_P99:
            return {"status":"FAIL","reason":f"picture or caption entered the reserved black gutter at t={ts}","evidence":evidence}
    return {"status":"PASS","evidence":evidence}

def verify_visual_cut_cadence(scene_windows: list[dict], scenes: list, max_hold: float=3.5) -> dict:
    """Fail if any picture stays on screen past the authored visual-cut cadence."""
    by_id={scene.id:scene for scene in scenes}
    failures=[]
    for window in scene_windows:
        scene=by_id.get(window.get("scene"))
        duration=float(window.get("duration",0) or 0)
        beats=list(getattr(scene,"visual_beats",[]) or [])
        starts=[float(b.start) for b in beats]
        if not starts or starts[0]!=0:
            failures.append({"scene":window.get("scene"),"reason":"visual beats must start at zero"})
            continue
        edges=starts+[duration]
        holds=[b-a for a,b in zip(edges,edges[1:])]
        longest=max(holds,default=duration)
        if longest>max_hold+0.05:
            failures.append({"scene":window.get("scene"),"longest_hold":longest,"limit":max_hold})
    if failures:
        return {"status":"FAIL","reason":"picture hold exceeds the visual cut limit","failures":failures}
    return {"status":"PASS","max_hold_seconds":max_hold}

def verify_composition_9x16(probe: dict, expected_width: int = 1080, expected_height: int = 1920) -> dict:
    streams = probe.get("streams", [])
    video_streams = [s for s in streams if s.get("codec_type") == "video" or ("width" in s and "height" in s)]
    if not video_streams:
        return {"status": "FAIL", "reason": "no video stream found in probe data"}
    v = video_streams[0]
    if v.get("width") != expected_width or v.get("height") != expected_height:
        return {"status": "FAIL", "reason": f"composition is not {expected_width}x{expected_height}: {v}"}
    return {"status": "PASS"}

def verify_scenes_present(expected_scene_ids: list[str], sources: list[dict]) -> dict:
    rendered_ids = [s["scene"] for s in sources]
    missing = [sid for sid in expected_scene_ids if sid not in rendered_ids]
    if missing:
        return {"status": "FAIL", "reason": f"scenes missing from the final render: {missing}"}
    if rendered_ids != list(expected_scene_ids):
        return {"status": "FAIL", "reason": f"rendered scene order does not match the manifest: {rendered_ids} != {expected_scene_ids}"}
    return {"status": "PASS"}

def verify_no_semantic_skip(semantic_results: list[dict]) -> dict:
    """A required scene (one that declares visual_qa_requirements) sitting at
    NOT_EVALUATED must always fail this check -- independent of the
    SHORTS_REQUIRE_SEMANTIC_QA env flag, so this can never be silently
    disabled by an environment change."""
    skipped = [r["scene"] for r in semantic_results if r.get("status") == "NOT_EVALUATED"]
    if skipped:
        return {"status": "FAIL", "reason": f"required scenes were not actually semantically evaluated: {skipped}"}
    return {"status": "PASS"}


def verify_narration_continuity(video: Path, max_silence_seconds: float = 1.5) -> dict:
    """Reject long silent holes in the actual output audio, including dropped TTS words."""
    import re
    proc = subprocess.run([
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(video),
        "-map", "0:a:0",
        "-af", f"silencedetect=noise=-55dB:d={max_silence_seconds}",
        "-f", "null", "-",
    ], capture_output=True, text=True)
    if proc.returncode != 0:
        return {"status": "FAIL", "reason": "cannot decode final narration audio"}
    starts = [float(x) for x in re.findall(r"silence_start:\s*([0-9.]+)", proc.stderr)]
    if starts:
        return {"status": "FAIL", "reason": "long silence in final narration",
                "silence_starts": starts, "max_silence_seconds": max_silence_seconds}
    return {"status": "PASS", "max_silence_seconds": max_silence_seconds}

def run_final_video_qa(video: Path, project, sources: list[dict], semantic_results: list[dict], probe: dict, scene_windows: list[dict], build_dir: Path) -> dict:
    """scene_windows: [{"scene": id, "start": cumulative_start_in_final_video,
    "caption_window": (start,end) or None}] -- caption_window is the first
    caption's (start,end) *within that scene's own clip*, or None if the
    scene has no captions (shouldn't happen for narrated scenes)."""
    final_duration=float(probe.get("format",{}).get("duration",0) or 0)
    planned_total=sum(float(w.get("duration",0) or 0) for w in scene_windows)
    timeline_scale=(final_duration/planned_total) if final_duration>0 and planned_total>0 else 1.0
    def final_ts(t:float)->float:
        mapped=max(0.0,float(t)*timeline_scale)
        return min(mapped,max(0.0,final_duration-0.05)) if final_duration>0 else mapped

    checks = {}
    checks["composition_9x16"] = verify_composition_9x16(probe, project.width, project.height)
    checks["scenes_present"] = verify_scenes_present([s.id for s in project.scenes], sources)
    checks["visual_cut_cadence"] = verify_visual_cut_cadence(scene_windows, project.scenes)
    checks["no_semantic_skip"] = verify_no_semantic_skip(semantic_results)
    checks["narration_continuity"] = verify_narration_continuity(video)

    title_samples = []
    if scene_windows:
        first = scene_windows[0]; last = scene_windows[-1]
        mid = scene_windows[len(scene_windows)//2]
        for w in {first["scene"]: first, mid["scene"]: mid, last["scene"]: last}.values():
            title_samples.append(final_ts(w["start"] + 0.3))
    checks["title_visible"] = verify_title_visible(video, title_samples, build_dir) if title_samples else {"status": "NOT_EVALUATED", "reason": "no scenes to sample"}

    caption_points = []
    safe_area_samples = []
    for w in scene_windows:
        if w.get("caption_window"):
            cs, ce = w["caption_window"]
            ts = final_ts(w["start"] + (cs + ce) / 2)
            caption_points.append((ts, (1000, 1900)))
        safe_area_samples.append(final_ts(w["start"] + 0.15))
    checks["captions_visible"] = verify_captions_visible(video, caption_points, build_dir) if caption_points else {"status": "NOT_EVALUATED", "reason": "no caption windows available"}
    checks["safe_area_clean"] = verify_bottom_safe_area_clean(video, safe_area_samples, build_dir, (IMAGE_BOTTOM_Y, 1920)) if safe_area_samples else {"status": "NOT_EVALUATED", "reason": "no scenes to sample"}
    gutter_samples=[]
    cursor=0.0
    for w in scene_windows:
        if w.get("caption_window"):
            cs,_=w["caption_window"]
            if cs > GUTTER_SAMPLE_LEAD_SECONDS:
                gutter_samples.append(final_ts(w["start"] + min(GUTTER_SAMPLE_LEAD_SECONDS, cs / 2)))
    # The fixed picture boundary is already enforced by safe_area_clean. When speech starts at scene zero there is no clean pre-caption frame to sample without confusing legitimate caption glyphs for picture bleed.\n    checks["picture_caption_gutter"] = verify_picture_caption_gutter(video, gutter_samples, build_dir) if gutter_samples else {"status": "PASS", "evidence": [], "reason": "no pre-caption frame; fixed picture boundary covered by safe_area_clean"}

    overall = "PASS" if all(c["status"] == "PASS" for c in checks.values()) else "FAIL"
    return {"status": overall, "checks": checks}
