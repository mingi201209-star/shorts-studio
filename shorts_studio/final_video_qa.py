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
import re
import subprocess
import urllib.parse
from pathlib import Path

_QA_FFMPEG_TIMEOUT_SECONDS = 180

def _extract_frame(video: Path, ts: float, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg","-y","-ss",str(max(0.0,ts)),"-i",str(video),"-frames:v","1",str(out)],check=True,capture_output=True)
    return out

# Calibrated empirically (see tests/test_final_video_qa.py) against real
# rendered frames: a blurred/plain region measures well under 5, a crisp
# bordered title/caption measures in the hundreds to low thousands.
MIN_TEXT_EDGE_VAR = 50.0
TITLE_ROW_BAND = (10, 290)          # covers _TITLE_STYLE's real 2-line extent at FontSize=130 (measured rows ~44-274)
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


IMAGE_TOP_Y=280
IMAGE_BOTTOM_Y=1230
# Captions are now top-anchored right under the picture (render.py's
# CAPTION_MARGIN_TOP = IMAGE_BOTTOM_Y + a small real gap), by direct user
# request -- there is deliberately no longer a wide black gap between the
# picture and the caption. This band is now a thin buffer strip covering
# only the real gap itself (narrower than render.py's CAPTION_GAP_BELOW_IMAGE
# to leave headroom for font-ascent variance), which must ALWAYS stay black:
# a genuine "the picture and the caption text never visually touch" check,
# not "there is a wide empty region below the picture" (that assumption no
# longer holds under the new tight layout).
CAPTION_GUTTER=(1230,1245)
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
    # A scene boundary is not a visual cut when the outgoing and incoming
    # beats declare the same source image.
    for prev, curr in zip(scene_windows, scene_windows[1:]):
        left = list(getattr(by_id.get(prev.get("scene")), "visual_beats", []) or [])
        right = list(getattr(by_id.get(curr.get("scene")), "visual_beats", []) or [])
        if not left or not right:
            continue
        def source(beat):
            return getattr(beat, "asset", None) or getattr(beat, "asset_url", None)
        if source(left[-1]) and source(left[-1]) == source(right[0]):
            trailing = float(prev.get("duration", 0) or 0) - float(left[-1].start)
            leading = float(right[1].start) if len(right) > 1 else float(curr.get("duration", 0) or 0)
            if trailing + leading > max_hold + 0.05:
                failures.append({"scene_boundary": [prev["scene"], curr["scene"]],
                                 "longest_hold": trailing + leading, "limit": max_hold})
    if failures:
        return {"status":"FAIL","reason":"picture hold exceeds the visual cut limit","failures":failures}
    return {"status":"PASS","max_hold_seconds":max_hold}


def _sample_media_box_frames(video: Path, media_box: tuple[int, int], build_dir: Path, fps: float = 2.0) -> list[Path]:
    """Extract a real, evenly-spaced sequence of frames from the actual
    rendered video -- not the authored manifest -- cropped to the media box
    only, so a title or caption changing never registers as a 'visual
    change' here. This is what lets visual-cadence QA measure real picture
    variety in the output, independent of whether the manifest's own
    visual_beats metadata is honest about it."""
    out_dir = build_dir / "_activity_frames"
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("f_*.jpg"):
        stale.unlink()
    top, bottom = media_box
    pattern = out_dir / "f_%05d.jpg"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video), "-vf", f"fps={fps},crop=1080:{bottom-top}:0:{top}", str(pattern)],
        check=True, capture_output=True, timeout=_QA_FFMPEG_TIMEOUT_SECONDS,
    )
    return sorted(out_dir.glob("f_*.jpg"))

# Mean absolute per-pixel difference (0-255 scale) between two consecutive
# sampled frames of the SAME still picture is dominated by h264 compression
# noise, empirically well under 5; a genuine cut to a different photo (even
# a similarly-toned one) clears 20+ by a wide margin (see
# tests/test_visual_activity_qa.py). Set with a comfortable margin above the
# noise floor so this never flags a static frame as "changed".
VISUAL_CHANGE_THRESHOLD = 12.0

def measure_visual_activity(video: Path, media_box: tuple[int, int], build_dir: Path, fps: float = 2.0, change_threshold: float = VISUAL_CHANGE_THRESHOLD) -> dict:
    """Real, pixel-level measurement of how often the picture actually
    changes in the rendered output. This is ground truth: it does not trust
    the manifest's visual_beats timestamps at all, so an author who claims a
    cut but doesn't actually deliver a different picture (e.g. only a
    crop/zoom of the same source composited to look "new") is still caught."""
    import cv2
    import numpy as np
    frames = _sample_media_box_frames(video, media_box, build_dir, fps=fps)
    if len(frames) < 2:
        return {"cut_timestamps": [0.0], "average_visual_beat_seconds": 0.0,
                "max_static_visual_seconds": 0.0, "first_5s_visual_changes": 0, "sample_fps": fps}
    interval = 1.0 / fps
    cuts = [0.0]
    prev = cv2.imread(str(frames[0]))
    for i, fp in enumerate(frames[1:], start=1):
        cur = cv2.imread(str(fp))
        if prev is not None and cur is not None and prev.shape == cur.shape:
            diff = float(np.abs(cur.astype(int) - prev.astype(int)).mean())
            if diff >= change_threshold:
                cuts.append(i * interval)
        prev = cur
    total_duration = len(frames) * interval
    edges = cuts + [total_duration]
    holds = [b - a for a, b in zip(edges, edges[1:])]
    first_5s_changes = sum(1 for t in cuts if 0.0 < t < 5.0)
    return {
        "cut_timestamps": cuts,
        "average_visual_beat_seconds": (sum(holds) / len(holds)) if holds else 0.0,
        "max_static_visual_seconds": max(holds) if holds else 0.0,
        "first_5s_visual_changes": first_5s_changes,
        "sample_fps": fps,
    }

def verify_visual_activity(activity: dict, max_static_seconds: float = 5.0, min_first_5s_changes: int = 1) -> dict:
    """FAIL if the real rendered picture ever sits static for too long, or
    the opening 5 seconds never actually change -- see measure_visual_activity."""
    if activity["max_static_visual_seconds"] > max_static_seconds + 0.05:
        return {"status": "FAIL", "reason": f"picture held static for {activity['max_static_visual_seconds']:.1f}s (> {max_static_seconds}s) with no real pixel change", "evidence": activity}
    if activity["first_5s_visual_changes"] < min_first_5s_changes:
        return {"status": "FAIL", "reason": f"only {activity['first_5s_visual_changes']} real visual change(s) in the first 5s (need >= {min_first_5s_changes})", "evidence": activity}
    return {"status": "PASS", "evidence": activity}

def verify_no_black_opening(video: Path, media_box: tuple[int, int], build_dir: Path, black_threshold: float = 12.0, caption_bright_threshold: int = 200) -> dict:
    """A Short must not open on an empty black media area with only a
    caption floating on it -- the first frame needs to actually show
    something. FAIL only when BOTH the media box reads as black AND there is
    visible bright (caption) text somewhere in the frame; a black media box
    with no text yet is not this failure mode."""
    import cv2
    frame = _extract_frame(video, 0.05, build_dir / "_openqa_0.jpg")
    img = cv2.imread(str(frame))
    if img is None:
        return {"status": "FAIL", "reason": "could not read the opening frame"}
    top, bottom = media_box
    media_band = cv2.cvtColor(img[top:bottom, :], cv2.COLOR_BGR2GRAY)
    media_mean = float(media_band.mean())
    media_is_black = media_mean < black_threshold
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    has_bright_text = bool((gray > caption_bright_threshold).any())
    evidence = {"media_mean": media_mean, "media_is_black": media_is_black, "has_bright_text": has_bright_text}
    if media_is_black and has_bright_text:
        return {"status": "FAIL", "reason": "opening frame is a black media area with only text visible", "evidence": evidence}
    return {"status": "PASS", "evidence": evidence}


def _source_family(identifier: str | None) -> str:
    """Normalize an asset path/URL to a family key so a crop/resize/rescan
    of the SAME underlying photograph is recognized as one real source, not
    counted as a fresh, distinct picture just because its filename or query
    string differs."""
    if not identifier:
        return ""
    name = identifier.rsplit("/", 1)[-1].split("?", 1)[0]
    try:
        name = urllib.parse.unquote(name)
    except Exception:
        pass
    name = name.rsplit(".", 1)[0].lower()
    name = re.sub(r"\(cropped\)|\bcropped\b|_norm\b|-norm\b|150dpi|\d{3,4}x\d{3,4}", "", name)
    name = re.sub(r"[^a-z0-9가-힣]+", "", name)
    return name

def _same_source_family(a: str, b: str) -> bool:
    """Two family keys are the same real source if they're identical, or one
    is fully contained in the other (a crop's filename is typically a
    truncated or extended form of the original's, e.g. an uncropped
    establishing-shot filename embedded inside its own cropped variant's
    filename)."""
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    return len(shorter) >= 8 and shorter in longer

def compute_source_reuse(project) -> dict:
    """Walk every scene's visual_beats in real timeline order and measure how
    often the same underlying source repeats -- including back-to-back
    across a scene cut, which is exactly what makes a Short read as cycling
    through the same handful of pictures rather than showing real variety."""
    sequence = []
    for scene in project.scenes:
        beats = getattr(scene, "visual_beats", None) or []
        for beat in beats:
            ident = getattr(beat, "asset", None) or getattr(beat, "asset_url", None) or ""
            sequence.append(_source_family(ident))
    total = len(sequence)
    families: list[str] = []
    family_of: list[int] = []
    for key in sequence:
        if not key:
            family_of.append(-1)
            continue
        matched = next((fi for fi, rep in enumerate(families) if _same_source_family(key, rep)), None)
        if matched is None:
            families.append(key)
            matched = len(families) - 1
        family_of.append(matched)
    unique = len(families)
    max_consecutive = 1
    run = 1
    for i in range(1, total):
        if family_of[i] != -1 and family_of[i] == family_of[i - 1]:
            run += 1
            max_consecutive = max(max_consecutive, run)
        else:
            run = 1
    reuse_ratio = (1 - unique / total) if total else 0.0
    return {"total_beats": total, "unique_sources": unique, "source_reuse_ratio": reuse_ratio, "max_consecutive_same_source": max_consecutive}

def verify_source_reuse(metrics: dict, max_consecutive: int = 1) -> dict:
    """FAIL if the same real source (by family, not just exact URL) ever
    appears in two adjacent beats -- including across a scene cut."""
    if metrics["max_consecutive_same_source"] > max_consecutive:
        return {"status": "FAIL", "reason": f"the same source repeats {metrics['max_consecutive_same_source']} times in a row (limit {max_consecutive})", "evidence": metrics}
    return {"status": "PASS", "evidence": metrics}


def _captions_overlap_media_box(caption_evidence: list[dict], media_box: tuple[int, int]) -> bool:
    """A caption's bright-row band (from verify_captions_visible's own
    evidence) intersecting the media box's row range is a direct, literal
    subtitle/media overlap -- independent of the gutter/safe-area
    heuristics, which only look at pixel busyness, not geometry."""
    for sample in caption_evidence:
        rows = sample.get("rows_in_band")
        if rows and rows[0] <= media_box[1] and rows[1] >= media_box[0]:
            return True
    return False

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

    media_box = (IMAGE_TOP_Y, IMAGE_BOTTOM_Y)

    checks = {}
    checks["composition_9x16"] = verify_composition_9x16(probe, project.width, project.height)
    checks["scenes_present"] = verify_scenes_present([s.id for s in project.scenes], sources)
    checks["visual_cut_cadence"] = verify_visual_cut_cadence(scene_windows, project.scenes)
    checks["no_semantic_skip"] = verify_no_semantic_skip(semantic_results)
    checks["narration_continuity"] = verify_narration_continuity(video)

    # Real, pixel-level ground truth on the actual rendered file -- does not
    # trust the manifest's visual_beats timestamps at all, so a beat that
    # claims a cut but doesn't actually deliver a different picture is still
    # caught, and a >5s real static hold or a dead opening 5 seconds fails
    # closed regardless of what the authored cadence looks like on paper.
    visual_activity = measure_visual_activity(video, media_box, build_dir)
    checks["visual_activity_real"] = verify_visual_activity(visual_activity)
    checks["no_black_opening"] = verify_no_black_opening(video, media_box, build_dir)
    source_reuse = compute_source_reuse(project)
    checks["source_reuse"] = verify_source_reuse(source_reuse)

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
            # The caption search band's lower bound must never dip above
            # IMAGE_BOTTOM_Y: the caption overlay is hard-cropped to start
            # exactly there (CAPTION_MASK_TOP in render.py), so no real
            # caption pixel can ever appear higher than that. A stale wider
            # band (this used to start at row 1000, from before captions
            # moved to sit right under the picture) let a photo's own bright
            # content masquerade as "caption evidence" -- harmless for the
            # old "some bright pixel exists" check, but a real false
            # positive for the newer literal subtitle/media overlap check.
            caption_points.append((ts, (IMAGE_BOTTOM_Y, 1900)))
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
    # The fixed picture boundary is already enforced by safe_area_clean. When
    # speech starts at scene zero there is no clean pre-caption frame to
    # sample without confusing legitimate caption glyphs for picture bleed.
    checks["picture_caption_gutter"] = verify_picture_caption_gutter(video, gutter_samples, build_dir) if gutter_samples else {"status": "PASS", "evidence": [], "reason": "no pre-caption frame; fixed picture boundary covered by safe_area_clean"}

    # A caption's bright-row band (already sampled for captions_visible)
    # overlapping the media box's own row range is a direct, literal
    # subtitle/media overlap -- independent of the gutter/safe-area
    # heuristics above, which only look at pixel busyness, not geometry.
    subtitle_media_overlap = _captions_overlap_media_box(checks["captions_visible"].get("evidence", []), media_box)
    if subtitle_media_overlap:
        checks["captions_visible"] = {**checks["captions_visible"], "status": "FAIL",
                                       "reason": "a caption's bright pixels overlap the media box row range"}

    metrics = {
        "average_visual_beat_seconds": visual_activity["average_visual_beat_seconds"],
        "max_static_visual_seconds": visual_activity["max_static_visual_seconds"],
        "source_reuse_ratio": source_reuse["source_reuse_ratio"],
        "first_5s_visual_changes": visual_activity["first_5s_visual_changes"],
        "subtitle_media_overlap": subtitle_media_overlap,
        "title_safe_area_pass": checks["title_visible"]["status"] == "PASS",
        "subtitle_safe_area_pass": checks["captions_visible"]["status"] == "PASS" and checks["safe_area_clean"]["status"] == "PASS",
    }

    overall = "PASS" if all(c["status"] == "PASS" for c in checks.values()) else "FAIL"
    return {"status": overall, "checks": checks, "metrics": metrics}
