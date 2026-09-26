"""Viewer-facing QA that actually looks at the rendered final.mp4, rather than
trusting that "the pipeline ran without an exception" means the Short looks
right. A green render used to mean only: file exists, resolution/codecs are
valid, and the coarse semantic-asset checks passed. None of that catches a
missing top title, a caption that's clipped off-screen, or a photo bleeding
into the caption safe area -- so those defects shipped past CI. Every check
here extracts a real frame (or measures real timing data) from the actual
production artifacts and fails closed if the evidence isn't there.

IMPORTANT -- QA PASS is a minimum quality bar, not proof of a successful
video: real post-publish channel data on two videos that passed every check
in this module (Titanic: 62s runtime, 43s average view duration, 69%
average view rate, but only 23.3% "stayed to watch"; Comet: 63s runtime,
38s AVD, 60.2% average view rate, ~55% 30s-retention, with the steepest
real drop-off inside the first ~5-10 seconds) showed that a file can clear
every gate here and still lose most of its real audience in the opening
seconds. Never report "QA PASS" as "this video will perform" -- real
success can only be verified against real acquisition/retention data after
publishing, which is outside what any file-level check can see. What
belongs here is real, checkable STRUCTURE the data points at (see the
First-10s Retention Contract below) -- never a channel KPI number (e.g. a
target "stayed to watch" percentage) hardcoded as a pass/fail threshold.
"""
from __future__ import annotations
import re
import subprocess
import urllib.parse
from pathlib import Path

from .retention_rules import hook_violation, is_generic_establishing_text, token_overlap_ratio, is_near_duplicate_text, has_tension_marker

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

def _beat_family_timeline(project) -> list[dict]:
    """Every visual beat in real timeline order, tagged with its normalized
    source-family id. Shared by every source-reuse/novelty check below so
    they all agree on what counts as "the same picture" -- a crop, zoom,
    pan, resize, or re-host of the same underlying photo is one family, not
    a fresh distinct source."""
    timeline = []
    for scene in project.scenes:
        beats = getattr(scene, "visual_beats", None) or []
        for beat in beats:
            ident = getattr(beat, "asset", None) or getattr(beat, "asset_url", None) or ""
            timeline.append({"scene": scene.id, "start": float(getattr(beat, "start", 0.0)),
                              "identifier": ident, "family": _source_family(ident)})
    families: list[str] = []
    for entry in timeline:
        key = entry["family"]
        if not key:
            entry["family_id"] = -1
            continue
        matched = next((fi for fi, rep in enumerate(families) if _same_source_family(key, rep)), None)
        if matched is None:
            families.append(key)
            matched = len(families) - 1
        entry["family_id"] = matched
    return timeline

def compute_source_reuse(project) -> dict:
    """Walk every scene's visual_beats in real timeline order and measure how
    often the same underlying source repeats -- including back-to-back
    across a scene cut, which is exactly what makes a Short read as cycling
    through the same handful of pictures rather than showing real variety."""
    timeline = _beat_family_timeline(project)
    total = len(timeline)
    family_ids = [e["family_id"] for e in timeline]
    unique = len({fi for fi in family_ids if fi != -1})
    max_consecutive = 1
    run = 1
    for i in range(1, total):
        if family_ids[i] != -1 and family_ids[i] == family_ids[i - 1]:
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


# A single recycled picture must never dominate the video: even with zero
# ADJACENT repeats, one source covering too much of the runtime is exactly
# what reads as "the same couple of historical photos the whole way
# through" -- the real complaint that motivated this gate.
GLOBAL_MAX_SOURCE_FAMILY_RATIO = 0.20
# A picture reappearing within a short window of beats reads as the video
# running out of new material even when it's not literally back-to-back.
# Calibrated empirically against the real, verified source pool: an
# exhaustive backtracking search over the actual scene layout proved
# window=5 mathematically infeasible with the 6 distinct, semantically
# correct real sources currently available (some positions are pinned to
# specific narration beats and can't move), while window=4 is achievable
# and still means no picture can repeat within 4 beats of itself anywhere
# in the video. Raise this back to 5 once another genuinely distinct,
# narration-accurate source is sourced for the relevant scenes.
NOVELTY_WINDOW_BEATS = 4

def compute_global_source_reuse(project) -> dict:
    """Whole-video source-family accounting, independent of adjacency."""
    timeline = _beat_family_timeline(project)
    total = len(timeline)
    from collections import Counter
    counts = Counter(e["family_id"] for e in timeline if e["family_id"] != -1)
    unique = len(counts)
    max_occurrences = counts.most_common(1)[0][1] if counts else 0
    seen: set[int] = set()
    repeated_source_timestamps = []
    for e in timeline:
        fid = e["family_id"]
        if fid == -1:
            continue
        if fid in seen:
            repeated_source_timestamps.append({"scene": e["scene"], "start": e["start"], "family": e["family"]})
        else:
            seen.add(fid)
    return {
        "total_beats": total,
        "unique_source_family_count": unique,
        "unique_source_family_ratio": (unique / total) if total else 0.0,
        "global_source_reuse_ratio": (1 - unique / total) if total else 0.0,
        "max_source_family_occurrences": max_occurrences,
        "max_source_family_ratio": (max_occurrences / total) if total else 0.0,
        "repeated_source_timestamps": repeated_source_timestamps,
    }

def verify_global_source_reuse(metrics: dict, max_family_ratio: float = GLOBAL_MAX_SOURCE_FAMILY_RATIO) -> dict:
    """FAIL if any single source family covers more than max_family_ratio of
    every visual beat in the whole video. Logs exactly when/where each
    repeat happens, not just the aggregate number."""
    if metrics["repeated_source_timestamps"]:
        for r in metrics["repeated_source_timestamps"]:
            print(f"[source-reuse] {r['scene']}@{r['start']:.1f}s repeats source family '{r['family'][:40]}'")
    if metrics["max_source_family_ratio"] > max_family_ratio + 1e-9:
        return {"status": "FAIL", "reason": f"one source family covers {metrics['max_source_family_ratio']:.0%} of all visual beats (limit {max_family_ratio:.0%}) -- the video leans on a single recycled picture", "evidence": metrics}
    return {"status": "PASS", "evidence": metrics}

def compute_novelty_window_violations(project, window: int = NOVELTY_WINDOW_BEATS) -> list[dict]:
    """Flags every beat whose source family already appeared within the
    previous `window` beats -- catches 'factory -> ad -> ad -> factory ->
    worker photo -> other -> factory' cycling even when no two beats are
    literally adjacent."""
    timeline = _beat_family_timeline(project)
    violations = []
    for i, entry in enumerate(timeline):
        fid = entry["family_id"]
        if fid == -1:
            continue
        for j in range(max(0, i - window), i):
            if timeline[j]["family_id"] == fid:
                violations.append({
                    "scene": entry["scene"], "start": entry["start"], "family": entry["family"],
                    "previous_scene": timeline[j]["scene"], "previous_start": timeline[j]["start"],
                    "gap_beats": i - j,
                })
                break
    return violations

def verify_visual_novelty(violations: list[dict]) -> dict:
    """FAIL if any beat reuses a source family that appeared within the
    novelty window -- the pixel-diff cadence check alone can't catch this
    because each individual cut IS a real pixel change; this checks whether
    it's actually NEW information."""
    if violations:
        for v in violations:
            print(f"[novelty] {v['scene']}@{v['start']:.1f}s repeats '{v['family'][:40]}' first seen at {v['previous_scene']}@{v['previous_start']:.1f}s ({v['gap_beats']} beats earlier)")
        return {"status": "FAIL", "reason": f"{len(violations)} beat(s) repeat a source family within the last {NOVELTY_WINDOW_BEATS} beats", "evidence": violations}
    return {"status": "PASS", "evidence": violations}

def compute_first_5s_family_coverage(scene_windows: list[dict], project, horizon: float = 5.0) -> dict:
    """How many genuinely distinct source families appear in the real
    opening horizon seconds of the concatenated timeline -- a crop/zoom of
    an already-shown source does not count as a new one."""
    by_id = {scene.id: scene for scene in project.scenes}
    family_reps: list[str] = []
    families_seen = []
    for w in scene_windows:
        scene = by_id.get(w.get("scene"))
        for beat in getattr(scene, "visual_beats", None) or []:
            abs_t = float(w.get("start", 0.0)) + float(getattr(beat, "start", 0.0))
            if abs_t >= horizon:
                continue
            ident = getattr(beat, "asset", None) or getattr(beat, "asset_url", None) or ""
            key = _source_family(ident)
            if not key:
                continue
            matched = next((r for r in family_reps if _same_source_family(key, r)), None)
            if matched is None:
                family_reps.append(key)
                families_seen.append({"scene": w.get("scene"), "start": abs_t, "family": key})
    return {"first_5s_unique_sources": len(family_reps), "first_5s_families": families_seen}

def verify_first_5s_coverage(metrics: dict, min_unique: int = 3) -> dict:
    """FAIL if the real opening horizon doesn't show at least min_unique
    genuinely distinct sources -- a single crop/zoom held the whole time,
    or the same picture repeated, no longer satisfies this."""
    if metrics["first_5s_unique_sources"] < min_unique:
        return {"status": "FAIL", "reason": f"only {metrics['first_5s_unique_sources']} distinct source(s) in the first {5}s (need >= {min_unique})", "evidence": metrics}
    return {"status": "PASS", "evidence": metrics}


# A global reuse ratio under the cap can still hide a real, viewer-visible
# problem: a couple of "generic" families each sitting right at the cap,
# with the ending specifically leaning on material already shown earlier
# instead of anything about the story's actual aftermath. This gate scores
# the ending as its own segment rather than folding it into the whole-video
# ratio, since a video can pass every whole-video check and still end on
# "show the opening photo again and roll credits."
ENDING_WINDOW_SECONDS = 18.0
ENDING_FINAL_WINDOW_SECONDS = 10.0
ENDING_MIN_NEW_RATIO = 0.6
ENDING_MIN_FINAL_WINDOW_UNIQUE = 2

def compute_ending_novelty(scene_windows: list[dict], project, total_duration: float,
                            ending_seconds: float = ENDING_WINDOW_SECONDS,
                            final_window_seconds: float = ENDING_FINAL_WINDOW_SECONDS) -> dict:
    """Whether the video's real ending shows genuinely new material or just
    revisits what's already been shown earlier. Family-based throughout (a
    crop/zoom/new montage of an already-used source is not novel), and
    scoped against the actual rendered duration, not the manifest's nominal
    scene boundaries."""
    by_id = {scene.id: scene for scene in project.scenes}
    timeline = []
    for w in scene_windows:
        scene = by_id.get(w.get("scene"))
        for beat in getattr(scene, "visual_beats", None) or []:
            abs_t = float(w.get("start", 0.0)) + float(getattr(beat, "start", 0.0))
            ident = getattr(beat, "asset", None) or getattr(beat, "asset_url", None) or ""
            timeline.append({"scene": w.get("scene"), "start": abs_t, "family": _source_family(ident)})
    timeline.sort(key=lambda e: e["start"])

    def family_rep(key, reps):
        return next((r for r in reps if key and _same_source_family(key, r)), None)

    ending_cutoff = total_duration - ending_seconds
    final_cutoff = total_duration - final_window_seconds

    earlier_reps: list[str] = []
    for e in timeline:
        if e["start"] < ending_cutoff and e["family"] and family_rep(e["family"], earlier_reps) is None:
            earlier_reps.append(e["family"])

    ending_beats = [e for e in timeline if e["start"] >= ending_cutoff]
    new_ending_beats = [e for e in ending_beats if e["family"] and family_rep(e["family"], earlier_reps) is None]
    new_ratio = (len(new_ending_beats) / len(ending_beats)) if ending_beats else 1.0

    final_window_new_reps: list[str] = []
    for e in timeline:
        if e["start"] >= final_cutoff and e["family"] and family_rep(e["family"], earlier_reps) is None:
            if family_rep(e["family"], final_window_new_reps) is None:
                final_window_new_reps.append(e["family"])

    last_beat = timeline[-1] if timeline else None
    last_beat_is_reused_generic = bool(last_beat and last_beat["family"] and family_rep(last_beat["family"], earlier_reps) is not None)

    return {
        "ending_seconds": ending_seconds,
        "final_window_seconds": final_window_seconds,
        "ending_cutoff": ending_cutoff,
        "ending_beat_count": len(ending_beats),
        "ending_new_beat_count": len(new_ending_beats),
        "ending_new_ratio": new_ratio,
        "final_window_unique_new_count": len(final_window_new_reps),
        "last_beat_family": last_beat["family"] if last_beat else None,
        "last_beat_is_reused_generic": last_beat_is_reused_generic,
        "ending_beats_detail": ending_beats,
    }

def verify_ending_novelty(metrics: dict, min_new_ratio: float = ENDING_MIN_NEW_RATIO,
                           min_final_window_unique: int = ENDING_MIN_FINAL_WINDOW_UNIQUE) -> dict:
    """FAIL if the ending doesn't earn its own novelty: not enough of its
    beats are genuinely new material, not enough distinct new sources show
    up in the closing seconds, or the very last beat reuses an already-seen
    generic family."""
    for e in metrics["ending_beats_detail"]:
        print(f"[ending] {e['scene']}@{e['start']:.1f}s family='{(e['family'] or '')[:40]}'")
    reasons = []
    if metrics["ending_new_ratio"] < min_new_ratio - 1e-9:
        reasons.append(f"only {metrics['ending_new_ratio']:.0%} of the last {metrics['ending_seconds']:.0f}s beats are genuinely new material (need >= {min_new_ratio:.0%})")
    if metrics["final_window_unique_new_count"] < min_final_window_unique:
        reasons.append(f"only {metrics['final_window_unique_new_count']} new unique source(s) in the last {metrics['final_window_seconds']:.0f}s (need >= {min_final_window_unique})")
    if metrics["last_beat_is_reused_generic"]:
        reasons.append(f"the final visual beat reuses an already-shown source family ('{(metrics['last_beat_family'] or '')[:40]}')")
    if reasons:
        return {"status": "FAIL", "reason": "; ".join(reasons), "evidence": metrics}
    return {"status": "PASS", "evidence": metrics}


# Loose keyword proxies for the narration semantic categories this project's
# stories tend to move through. Purely informational (reported, not gated
# on) -- a real semantic classifier is out of scope, but this at least shows
# which of the expected story beats have SOME matching visual on file.
_NARRATION_SEMANTIC_CATEGORIES = {
    "factory_work": ["factory", "workshop", "work table", "working"],
    "technique_closeup": ["brush", "close-up", "fine brush"],
    "material_product": ["paint", "luminous", "advertisement", "vial", "poison", "watch"],
    "affected_people": ["portrait", "plaintiff", "scientist"],
    "legal_company": ["lawsuit", "newspaper", "montage", "advertisement"],
    "investigation": ["electroscope", "laboratory", "measur", "instrument"],
}

def compute_semantic_visual_coverage(project) -> dict:
    """Fraction of the narration's expected semantic categories that have at
    least one beat whose own visual_qa_labels actually describes it -- a
    proxy for 'is there real coverage per story beat, or is one generic
    label/photo doing duty for everything'."""
    all_labels = []
    for scene in project.scenes:
        for beat in getattr(scene, "visual_beats", None) or []:
            all_labels.append(" ".join(getattr(beat, "visual_qa_labels", None) or []).lower())
    covered = {cat: any(any(kw in label for kw in kws) for label in all_labels)
               for cat, kws in _NARRATION_SEMANTIC_CATEGORIES.items()}
    ratio = (sum(covered.values()) / len(covered)) if covered else 0.0
    return {"semantic_visual_coverage": ratio, "categories_covered": covered}


def verify_source_budget(project, max_family_ratio: float = GLOBAL_MAX_SOURCE_FAMILY_RATIO, min_unique_ratio: float = 0.35) -> dict:
    """Pre-render gate: if the manifest doesn't have enough genuinely
    distinct source families to cover its own visual beats without one
    family dominating, fail BEFORE spending a full render on it. The fix is
    to source more real, distinct images -- not to let a render proceed on
    a thin pool and recycle the same handful of pictures."""
    metrics = compute_global_source_reuse(project)
    if metrics["total_beats"] == 0:
        return {"status": "PASS", "evidence": metrics}
    if metrics["max_source_family_ratio"] > max_family_ratio + 1e-9:
        return {"status": "FAIL", "reason": f"source budget insufficient: one family would cover {metrics['max_source_family_ratio']:.0%} of all beats (limit {max_family_ratio:.0%}); source more distinct real images before rendering", "evidence": metrics}
    if metrics["unique_source_family_ratio"] < min_unique_ratio:
        return {"status": "FAIL", "reason": f"source budget insufficient: only {metrics['unique_source_family_ratio']:.0%} of beats have a distinct source (need >= {min_unique_ratio:.0%}); source more distinct real images before rendering", "evidence": metrics}
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

# ---------------------------------------------------------------------------
# Retention-engine contracts (opt-in via Project.strict_retention_contract):
# First-Second Hook, Information Change, Story Progression, Ending Payoff,
# and Runtime Discipline. All of these are script-level -- they only look at
# the manifest (`project`), never the rendered video -- so they can run
# BEFORE spending a real render, exactly like verify_source_budget above,
# and are re-reported in the final qa_report.json for the same reason the
# source-diversity metrics are: a human reading the report should be able to
# see the whole retention picture without re-deriving it.
# ---------------------------------------------------------------------------

def _first_narration_phrase_text(scene) -> str:
    plan = getattr(scene, "narration_plan", None) or []
    if plan:
        return plan[0].text
    return getattr(scene, "narration", "") or ""

def verify_hook_opener(project) -> dict:
    """The very first spoken phrase of the whole video must not be a
    greeting, a topic announcement, 'today we'll look at X' framing, OR a
    flat descriptive/background sentence with no real tension marker (see
    retention_rules.hook_violation / has_tension_marker) -- this last case
    is a real one: a published production's actual opener ("타이타닉에는
    거대한 굴뚝이 네 개 있었습니다") matched none of the banned patterns yet
    was pure background exposition, exactly the acquisition bottleneck real
    channel data (23.3% stayed-to-watch) pointed at. If narration_plan is
    authored, its first phrase's role must be HOOK and must declare a
    hook_type (retention_rules.HOOK_TYPES) -- an authorial commitment to
    WHICH mechanism (result/contradiction/danger/question/anomaly/reversal)
    the opener is using, not just that some banned phrase is absent."""
    if not project.scenes:
        return {"status": "FAIL", "reason": "no scenes"}
    first_scene = project.scenes[0]
    text = _first_narration_phrase_text(first_scene)
    reason = hook_violation(text)
    if reason:
        return {"status": "FAIL", "reason": f"first spoken phrase fails the hook contract ({reason}): {text!r}"}
    plan = getattr(first_scene, "narration_plan", None) or []
    if plan:
        if plan[0].role != "HOOK":
            return {"status": "FAIL", "reason": f"first narration_plan phrase's role is '{plan[0].role}', must be HOOK"}
        if not getattr(plan[0], "hook_type", None):
            return {"status": "FAIL", "reason": "first HOOK phrase does not declare a hook_type (retention_rules.HOOK_TYPES)"}
    return {"status": "PASS", "evidence": {"first_phrase": text, "hook_type": getattr(plan[0], "hook_type", None) if plan else None}}

def verify_first_beat_visual_grounding(project) -> dict:
    """The first visual beat of the first scene must commit to showing a
    concrete event/result, not a generic establishing shot."""
    if not project.scenes:
        return {"status": "FAIL", "reason": "no scenes"}
    first_scene = project.scenes[0]
    beats = getattr(first_scene, "visual_beats", None) or []
    if beats:
        reqs = beats[0].visual_qa_requirements or []
        text = " ".join(reqs) if reqs else (getattr(first_scene, "visual_description", "") or "")
    else:
        text = getattr(first_scene, "visual_description", "") or ""
    if not text.strip():
        return {"status": "FAIL", "reason": "first visual beat declares no concrete visual requirement"}
    if is_generic_establishing_text(text):
        return {"status": "FAIL", "reason": f"first visual beat reads as a generic establishing shot: {text!r}"}
    return {"status": "PASS", "evidence": {"first_beat_text": text}}

def verify_first_beat_narration_visual_sync(project) -> dict:
    """Not just 'a cut happened' -- the first spoken words and the first
    visual requirement must actually be about the same thing. A zero-overlap
    result means the opening narration and the opening picture may be
    describing unrelated content."""
    if not project.scenes:
        return {"status": "FAIL", "reason": "no scenes"}
    first_scene = project.scenes[0]
    narration_text = _first_narration_phrase_text(first_scene)
    beats = getattr(first_scene, "visual_beats", None) or []
    if beats:
        req_text = " ".join(beats[0].visual_qa_requirements or [])
    else:
        req_text = " ".join(getattr(first_scene, "visual_qa_requirements", None) or [])
    if not req_text.strip():
        return {"status": "NOT_EVALUATED", "reason": "no visual requirement text declared to compare against"}
    overlap = token_overlap_ratio(narration_text, req_text)
    if overlap <= 0.0:
        return {"status": "FAIL", "reason": "first narration and first visual requirement share no common words",
                "evidence": {"narration": narration_text, "requirement": req_text, "overlap": overlap}}
    return {"status": "PASS", "evidence": {"narration": narration_text, "requirement": req_text, "overlap": overlap}}


def compute_information_progression(project) -> dict:
    """Every beat that declares an info_role (VisualBeat.info_role,
    models.py), in timeline order, plus which ones repeat an already-used
    label -- a beat with a duplicate info_role is, by the author's own
    declaration, not delivering new information."""
    entries = []
    for scene in project.scenes:
        for beat in getattr(scene, "visual_beats", None) or []:
            role = getattr(beat, "info_role", None)
            if role and role.strip():
                entries.append({"scene": scene.id, "start": float(getattr(beat, "start", 0.0)), "info_role": role.strip()})
    total_beats = sum(len(getattr(s, "visual_beats", None) or []) for s in project.scenes)
    seen: dict[str, dict] = {}
    duplicates = []
    for e in entries:
        key = e["info_role"].lower()
        if key in seen:
            duplicates.append({**e, "first_seen": seen[key]})
        else:
            seen[key] = {"scene": e["scene"], "start": e["start"]}
    return {
        "total_beats": total_beats,
        "declared_info_role_count": len(entries),
        "declared_info_role_ratio": (len(entries) / total_beats) if total_beats else 0.0,
        "duplicate_info_roles": duplicates,
    }

MIN_DECLARED_INFO_ROLE_RATIO = 0.8

def verify_information_progression(metrics: dict, min_declared_ratio: float = MIN_DECLARED_INFO_ROLE_RATIO) -> dict:
    """FAIL if any beat repeats an already-declared info_role (no new
    information despite a real picture change), or if too few beats bother
    declaring their information role at all for a project that opted into
    this contract."""
    if metrics["duplicate_info_roles"]:
        for d in metrics["duplicate_info_roles"]:
            print(f"[info-progression] {d['scene']}@{d['start']:.1f}s repeats info_role '{d['info_role']}' first declared at {d['first_seen']['scene']}@{d['first_seen']['start']:.1f}s")
        return {"status": "FAIL", "reason": f"{len(metrics['duplicate_info_roles'])} beat(s) declare an info_role already used earlier -- no new information", "evidence": metrics}
    if metrics["total_beats"] and metrics["declared_info_role_ratio"] < min_declared_ratio - 1e-9:
        return {"status": "FAIL", "reason": f"only {metrics['declared_info_role_ratio']:.0%} of beats declare an info_role (need >= {min_declared_ratio:.0%})", "evidence": metrics}
    return {"status": "PASS", "evidence": metrics}


MIN_DISTINCT_NARRATIVE_ROLES = 4

def _all_narration_roles(project) -> list[str]:
    roles = []
    for scene in project.scenes:
        for phrase in getattr(scene, "narration_plan", None) or []:
            roles.append(phrase.role)
    return roles

def verify_story_progression(project) -> dict:
    """Reject a flat 'A and B and C' script: requires an authored
    narration_plan (role-tagged, see models.NarrationPhrase), the first
    phrase's role to be HOOK, at least MIN_DISTINCT_NARRATIVE_ROLES distinct
    roles used across the whole video, and every scene to introduce at least
    one role not already covered by an earlier scene (a real state change,
    not a scene that only repeats narrative functions already served)."""
    roles = _all_narration_roles(project)
    if not roles:
        return {"status": "FAIL", "reason": "no narration_plan roles declared -- Story Progression requires an authored role-tagged script, not a flat narration string"}
    if roles[0] != "HOOK":
        return {"status": "FAIL", "reason": f"first narration phrase's role is '{roles[0]}', must be HOOK", "evidence": {"roles": roles}}
    distinct = len(set(roles))
    if distinct < MIN_DISTINCT_NARRATIVE_ROLES:
        return {"status": "FAIL", "reason": f"only {distinct} distinct narrative role(s) used ({sorted(set(roles))}) -- reads as a flat script with no real state progression (need >= {MIN_DISTINCT_NARRATIVE_ROLES})", "evidence": {"roles": roles}}
    seen_roles: set[str] = set()
    stagnant = []
    for scene in project.scenes:
        roleset = {p.role for p in (getattr(scene, "narration_plan", None) or [])}
        if roleset and roleset.issubset(seen_roles):
            stagnant.append(scene.id)
        seen_roles |= roleset
    if stagnant:
        return {"status": "FAIL", "reason": f"scene(s) {stagnant} introduce no narrative role beyond what earlier scenes already covered -- no state change in that scene", "evidence": {"roles": roles}}
    return {"status": "PASS", "evidence": {"roles": roles, "distinct_roles": distinct}}

def verify_ending_payoff_role(project) -> dict:
    """The last spoken phrase of the video must be a PAYOFF or REVEAL, not
    an EXPLANATION/SETUP tail -- the ending must not just summarize."""
    if not project.scenes:
        return {"status": "FAIL", "reason": "no scenes"}
    last_scene = project.scenes[-1]
    plan = getattr(last_scene, "narration_plan", None) or []
    if not plan:
        return {"status": "FAIL", "reason": f"last scene {last_scene.id} has no narration_plan -- cannot confirm a PAYOFF/REVEAL closes the video"}
    last_role = plan[-1].role
    if last_role not in ("PAYOFF", "REVEAL"):
        return {"status": "FAIL", "reason": f"last narration phrase's role is '{last_role}', must be PAYOFF or REVEAL", "evidence": {"last_role": last_role}}
    return {"status": "PASS", "evidence": {"last_role": last_role}}


# ---------------------------------------------------------------------------
# First-10s Retention Contract -- added in response to REAL post-publish
# channel data, not a QA-report number: Titanic (62s, 43s AVD, 69% avg view
# rate, but only 23.3% "stayed to watch") and Comet (63s, 38s AVD, 60.2% avg
# view rate, ~55% 30s-retention) both show the steepest real drop-off inside
# the first ~5-10 seconds, not in the middle or the ending -- both videos
# already passed every existing QA gate. QA PASS is therefore a minimum
# quality bar, not proof a video will actually hold acquisition; this
# contract targets the specific bottleneck the data pointed at, using REAL
# per-role timing recovered from the actual TTS synthesis (tts.py's
# per-unit start/end, threaded through scene_windows[i]["narration_units"]
# by render.py) -- not an approximation from character counts.
#
# Deliberately NOT a hardcoded channel-performance number (e.g. "40%
# stayed-to-watch"): that is a real business goal to verify with real
# post-publish data, not something a rendered video file alone can prove.
# What IS checkable from the file is the STRUCTURE the data suggests such a
# number needs: a real claim in second 1, a visual proof shortly after, a
# new tension by mid-opening, and an early payoff before the 12s mark --
# never a stretch of pure background exposition with nothing changing.
# ---------------------------------------------------------------------------

FIRST_10S_HOOK_WINDOW = (0.0, 1.0)
FIRST_10S_VISUAL_PROOF_WINDOW = (0.2, 3.0)
FIRST_10S_STATE_CHANGE_WINDOW = (3.0, 8.0)
FIRST_10S_PAYOFF_WINDOW = (8.0, 12.0)
MIN_DISTINCT_ROLES_IN_FIRST_10S = 3

_STATE_CHANGE_ROLES = ("CRISIS", "INVESTIGATION")
_EARLY_PAYOFF_ROLES = ("REVEAL", "PAYOFF")

def compute_first_10s_narration_timeline(scene_windows: list[dict]) -> list[dict]:
    """Every narration_plan unit (see tts.py/render.py), in absolute
    final-video time, built from REAL per-unit synthesis timing -- not a
    character-count approximation."""
    timeline = []
    for w in scene_windows:
        base = float(w.get("start", 0.0) or 0.0)
        for u in (w.get("narration_units") or []):
            timeline.append({
                "scene": w.get("scene"),
                "role": u.get("role"),
                "text": u.get("text"),
                "start": base + float(u.get("start", 0.0) or 0.0),
                "end": base + float(u.get("end", 0.0) or 0.0),
            })
    timeline.sort(key=lambda e: e["start"])
    return timeline

def verify_first_10s_retention(narration_timeline: list[dict], visual_cut_timestamps: list[float]) -> dict:
    """Structural check on the real opening timeline: a HOOK claim in
    [0,1s], a real visual cut following it by [0.2,3s] (the claim gets
    immediate visual proof, not a static hold), a new
    danger/question/state-change by [3,8s], and an early REVEAL/PAYOFF by
    [8,12s] -- with at least MIN_DISTINCT_ROLES_IN_FIRST_10S distinct
    narrative roles in the first 10s so the opening can never be one long
    unbroken stretch of background exposition."""
    if not narration_timeline:
        return {"status": "FAIL", "reason": "no real narration timing data available -- cannot verify the First-10s Retention Contract"}
    reasons = []

    hook_units = [e for e in narration_timeline if e["role"] == "HOOK" and FIRST_10S_HOOK_WINDOW[0] <= e["start"] <= FIRST_10S_HOOK_WINDOW[1]]
    if not hook_units:
        reasons.append(f"no HOOK-role narration starts within {FIRST_10S_HOOK_WINDOW[0]}-{FIRST_10S_HOOK_WINDOW[1]}s")

    proof_cuts = [t for t in visual_cut_timestamps if FIRST_10S_VISUAL_PROOF_WINDOW[0] < t <= FIRST_10S_VISUAL_PROOF_WINDOW[1]]
    if not proof_cuts:
        reasons.append(f"no real visual cut lands within {FIRST_10S_VISUAL_PROOF_WINDOW[0]}-{FIRST_10S_VISUAL_PROOF_WINDOW[1]}s to prove the opening claim (picture held static instead)")

    state_change_units = [e for e in narration_timeline if FIRST_10S_STATE_CHANGE_WINDOW[0] < e["start"] <= FIRST_10S_STATE_CHANGE_WINDOW[1]
                           and (e["role"] in _STATE_CHANGE_ROLES or has_tension_marker(e["text"] or ""))]
    if not state_change_units:
        reasons.append(f"no new danger/question/state-change narration starts within {FIRST_10S_STATE_CHANGE_WINDOW[0]}-{FIRST_10S_STATE_CHANGE_WINDOW[1]}s")

    payoff_units = [e for e in narration_timeline if e["role"] in _EARLY_PAYOFF_ROLES and FIRST_10S_PAYOFF_WINDOW[0] < e["start"] <= FIRST_10S_PAYOFF_WINDOW[1]]
    if not payoff_units:
        reasons.append(f"no REVEAL/PAYOFF-role narration starts within {FIRST_10S_PAYOFF_WINDOW[0]}-{FIRST_10S_PAYOFF_WINDOW[1]}s (no early payoff)")

    early = [e for e in narration_timeline if e["start"] < 10.0]
    distinct_early_roles = len({e["role"] for e in early})
    if distinct_early_roles < MIN_DISTINCT_ROLES_IN_FIRST_10S:
        reasons.append(f"only {distinct_early_roles} distinct narrative role(s) in the first 10s -- reads as an unbroken stretch of background exposition (need >= {MIN_DISTINCT_ROLES_IN_FIRST_10S})")

    evidence = {
        "narration_timeline_first_12s": [e for e in narration_timeline if e["start"] < 12.0],
        "visual_proof_cuts": proof_cuts,
        "distinct_early_roles": distinct_early_roles,
    }
    if reasons:
        return {"status": "FAIL", "reason": "; ".join(reasons), "evidence": evidence}
    return {"status": "PASS", "evidence": evidence}


def verify_no_redundant_narration(project) -> dict:
    """Runtime Discipline: fail if any two narration phrases (or whole-scene
    narration strings, for scenes with no narration_plan) are near-duplicate
    -- restated filler instead of new content in a 40-60s video wastes
    exactly the seconds that should carry new information."""
    texts = []
    for scene in project.scenes:
        plan = getattr(scene, "narration_plan", None) or []
        if plan:
            for p in plan:
                texts.append((scene.id, p.text))
        else:
            texts.append((scene.id, getattr(scene, "narration", "") or ""))
    violations = []
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            if is_near_duplicate_text(texts[i][1], texts[j][1]):
                violations.append({"a": {"scene": texts[i][0], "text": texts[i][1]}, "b": {"scene": texts[j][0], "text": texts[j][1]}})
    if violations:
        return {"status": "FAIL", "reason": f"{len(violations)} pair(s) of near-duplicate narration sentences found", "evidence": violations}
    return {"status": "PASS"}


def verify_retention_contract(project) -> dict:
    """Aggregate pre-render gate for every opt-in retention check. Called
    both from render() (fail before spending a render) and reported inside
    run_final_video_qa's checks for the same project that already rendered,
    so a human reading qa_report.json sees the whole retention picture."""
    checks = {
        "hook_opener": verify_hook_opener(project),
        "first_beat_visual_grounding": verify_first_beat_visual_grounding(project),
        "hook_narration_visual_sync": verify_first_beat_narration_visual_sync(project),
        "story_progression": verify_story_progression(project),
        "ending_payoff_role": verify_ending_payoff_role(project),
        "no_redundant_narration": verify_no_redundant_narration(project),
        "information_progression": verify_information_progression(compute_information_progression(project)),
    }
    blocking = {k: v for k, v in checks.items() if v["status"] == "FAIL"}
    overall = "FAIL" if blocking else "PASS"
    return {"status": overall, "checks": checks}


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
    # Metrics are always computed (useful in the report either way); only
    # projects that opt in via strict_source_diversity are gated on them --
    # see the field's docstring in models.py for why this isn't universal.
    global_reuse = compute_global_source_reuse(project)
    novelty_violations = compute_novelty_window_violations(project)
    first_5s_coverage = compute_first_5s_family_coverage(scene_windows, project)
    semantic_coverage = compute_semantic_visual_coverage(project)
    ending_novelty = compute_ending_novelty(scene_windows, project, final_duration)
    if getattr(project, "strict_source_diversity", False):
        checks["global_source_reuse"] = verify_global_source_reuse(global_reuse)
        checks["visual_novelty"] = verify_visual_novelty(novelty_violations)
        checks["first_5s_coverage"] = verify_first_5s_coverage(first_5s_coverage)
        checks["ending_novelty"] = verify_ending_novelty(ending_novelty)

    # Retention-engine contract (Idea-Gate era additions): script-level, so
    # this is the same result render() already fail-closed on before
    # spending the render -- reported again here so qa_report.json carries
    # the whole retention picture in one place. Opt-in: see models.py.
    information_progression = compute_information_progression(project)
    retention_contract = None
    first_10s_retention = None
    if getattr(project, "strict_retention_contract", False):
        retention_contract = verify_retention_contract(project)
        checks["retention_contract"] = retention_contract
        # Real per-role timing + real visual cut ground truth (both already
        # computed above) -- this is the ONE post-render check in the whole
        # retention contract, because it needs the actual synthesized TTS
        # timing and the actual rendered cuts, not the nominal manifest.
        narration_timeline = compute_first_10s_narration_timeline(scene_windows)
        first_10s_retention = verify_first_10s_retention(narration_timeline, visual_activity["cut_timestamps"])
        checks["first_10s_retention"] = first_10s_retention

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
        "unique_source_family_count": global_reuse["unique_source_family_count"],
        "unique_source_family_ratio": global_reuse["unique_source_family_ratio"],
        "global_source_reuse_ratio": global_reuse["global_source_reuse_ratio"],
        "max_source_family_occurrences": global_reuse["max_source_family_occurrences"],
        "semantic_visual_coverage": semantic_coverage["semantic_visual_coverage"],
        "first_5s_unique_sources": first_5s_coverage["first_5s_unique_sources"],
        "repeated_source_timestamps": global_reuse["repeated_source_timestamps"],
        "ending_new_ratio": ending_novelty["ending_new_ratio"],
        "ending_final_window_unique_new_count": ending_novelty["final_window_unique_new_count"],
        "ending_last_beat_is_reused_generic": ending_novelty["last_beat_is_reused_generic"],
        "declared_info_role_ratio": information_progression["declared_info_role_ratio"],
        "duplicate_info_role_count": len(information_progression["duplicate_info_roles"]),
        "distinct_narrative_roles": len(set(_all_narration_roles(project))),
        "retention_contract_status": retention_contract["status"] if retention_contract else "NOT_EVALUATED",
        "first_10s_retention_status": first_10s_retention["status"] if first_10s_retention else "NOT_EVALUATED",
    }

    overall = "PASS" if all(c["status"] == "PASS" for c in checks.values()) else "FAIL"
    return {"status": overall, "checks": checks, "metrics": metrics}
