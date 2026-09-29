"""Evidence for visual changes; pixel motion alone never establishes novelty.

Opt-in migration: old projects keep every existing gate. This contract is an
additional gate, not a replacement for cadence, semantic QA, retention or PEC.
Descriptions are author claims. Delivery checks do not prove comprehension;
the report explicitly requires review of the actual frames against narration.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path


def _normal(text):
    return re.sub(r"\W+", "", text).lower()


def audit_visual_changes(project):
    failures = []
    seen_states, seen_hashes = set(), set()
    previous = None
    for scene in project.scenes:
        for i, beat in enumerate(scene.visual_beats):
            change = beat.visual_change
            if change is None:
                failures.append(f"{scene.id}/{i}: missing visual_change evidence")
                continue
            cue = _normal(change.narration_cue)
            speech = _normal(" ".join(p.text for p in scene.narration_plan) or scene.narration)
            if not cue or speech.count(cue) != 1:
                failures.append(f"{scene.id}/{i}: cue must occur exactly once in narration")
            key = (change.concept_id, change.state_id)
            if change.kind == "framing":
                failures.append(f"{scene.id}/{i}: framing is not meaningful information")
            if key in seen_states or change.source_sha256 in seen_hashes:
                failures.append(f"{scene.id}/{i}: repeated state/content is not new information")
            if change.kind == "state" and (previous is None or change.concept_id != previous.concept_id):
                failures.append(f"{scene.id}/{i}: state requires the preceding stable concept")
            if change.kind == "concept" and previous and change.concept_id == previous.concept_id:
                failures.append(f"{scene.id}/{i}: same concept mislabeled as a new concept")
            asset = Path(beat.asset or "")
            if not asset.is_file() or hashlib.sha256(asset.read_bytes()).hexdigest() != change.source_sha256:
                failures.append(f"{scene.id}/{i}: reviewed source hash missing or mismatched")
            seen_states.add(key)
            seen_hashes.add(change.source_sha256)
            previous = change
        if not scene.visual_beats:
            failures.append(f"{scene.id}: no visual change evidence")
    return {"status": "FAIL" if failures else "PASS", "failures": failures,
            "semantic_status": "REQUIRES_VISUAL_REVIEW"}


def resolve_visual_cues(scene, words, duration):
    """Bind literal cues to measured TTS words; no fixed cut interval or text-rate estimate."""
    normalized = [_normal(w["text"]) for w in words]
    joined = "".join(normalized)
    offsets, cursor = [], 0
    for token in normalized:
        offsets.append(cursor)
        cursor += len(token)
    beats = []
    previous = -1.0
    for i, beat in enumerate(scene.visual_beats):
        cue = _normal(beat.visual_change.narration_cue)
        if joined.count(cue) != 1:
            raise ValueError(f"{scene.id}: missing/ambiguous measured narration cue {cue!r}")
        index = joined.index(cue)
        wi = max(j for j, offset in enumerate(offsets) if offset <= index)
        start = 0.0 if i == 0 else float(words[wi]["start"])
        if start <= previous or start >= duration - 0.1:
            raise ValueError(f"{scene.id}: invalid measured visual cue time {start}")
        beats.append(beat.model_copy(update={"start": start}))
        previous = start
    return scene.model_copy(update={"visual_beats": beats})


def equivalent_framing(before, after):
    """Negative evidence: exact duplicates or crop/zoom explainable by one transform.

    SIFT/RANSAC estimates geometry; residual pixels, not matching filenames or
    declared state IDs, decide whether a registered view contains new content.
    Failing to find a transform is NOT a semantic PASS.
    """
    import cv2
    import numpy as np
    def picture(image):
        # Contain-fit letterboxing stays still during an embedded crop/zoom;
        # it must not create a false registration residual at the border.
        ys, xs = np.where(image.max(axis=2) > 12)
        if len(xs):
            image = image[ys.min():ys.max()+1, xs.min():xs.max()+1]
        return cv2.resize(image, (480, 480))
    a, b = picture(before), picture(after)
    if float(np.abs(a.astype(float) - b.astype(float)).mean()) < 3:
        return True
    sift = cv2.SIFT_create(nfeatures=1200)
    ka, da = sift.detectAndCompute(cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), None)
    kb, db = sift.detectAndCompute(cv2.cvtColor(b, cv2.COLOR_BGR2GRAY), None)
    if da is None or db is None:
        return False
    pairs = cv2.BFMatcher().knnMatch(da, db, k=2)
    good = [m for pair in pairs if len(pair) == 2 for m, n in [pair] if m.distance < .7*n.distance]
    if len(good) < 10:
        return False
    src = np.float32([ka[m.queryIdx].pt for m in good])
    dst = np.float32([kb[m.trainIdx].pt for m in good])
    matrix, inliers = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=2)
    if matrix is None or inliers.sum() < 8:
        return False
    warped = cv2.warpAffine(a, matrix, (480, 480))
    mask = cv2.warpAffine(np.ones((480, 480), np.uint8), matrix, (480, 480)) > 0
    # A tight crop can be entirely contained in the other frame. Require
    # broad overlap and compare blur-tolerant residuals, excluding borders.
    if mask.mean() < .55:
        return False
    aa, bb = cv2.GaussianBlur(warped, (5, 5), 0), cv2.GaussianBlur(b, (5, 5), 0)
    residual = np.abs(aa.astype(float) - bb.astype(float)).mean(axis=2)
    return float((residual[mask] > 18).mean()) < .025


def verify_observed_changes(project, windows, video, build_dir, media_box):
    """Observe every delivered state in the real final MP4; reject crop churn.

    All legacy checks still run. This uses media-only crops so changing
    captions/title cannot manufacture an event. Source QA remains independent.
    """
    import cv2
    import numpy as np
    by_id = {s.id: s for s in project.scenes}
    events, failures, frames = [], [], []
    out = Path(build_dir) / "_meaningful"
    out.mkdir(parents=True, exist_ok=True)
    previous = None
    for window in windows:
        scene = by_id[window["scene"]]
        for i, beat in enumerate(scene.visual_beats):
            end = scene.visual_beats[i+1].start if i+1 < len(scene.visual_beats) else window["duration"]
            start = float(beat.start)
            if end <= start:
                failures.append(f"{scene.id}/{i}: undelivered state")
                continue
            timestamp = window["start"] + start + min(.25, (end-start)/2)
            path = out / f"{scene.id}_{i}.png"
            subprocess.run(["ffmpeg", "-y", "-ss", str(timestamp), "-i", str(video),
                            "-frames:v", "1", "-vf", f"crop=1080:{media_box[1]-media_box[0]}:0:{media_box[0]}",
                            str(path)], check=True, capture_output=True, timeout=90)
            frame = cv2.imread(str(path))
            if frame is None:
                failures.append(f"{scene.id}/{i}: missing actual frame")
                continue
            change = beat.visual_change
            meaningful = change is not None and change.kind != "framing"
            if not meaningful:
                failures.append(f"{scene.id}/{i}: missing meaningful declaration")
            # Compare the rendered media box against the pinned source, not
            # merely against the previous frame. A wrong but changing image
            # cannot stand in for a declared explanatory state.
            source = cv2.imread(str(beat.asset)) if beat.asset else None
            if source is None and beat.asset:
                # Moving visual beats are real evidence too. cv2.imread cannot
                # decode a video container, so sample the source at the same
                # local offset used for the rendered-state observation.
                cap = cv2.VideoCapture(str(beat.asset))
                try:
                    # Match the same semantic source offset the renderer uses.
                    # Without this, a later source_start would render (say)
                    # second 8 while QA compared it to second 0.25 and could
                    # falsely report the correct moving beat as unrelated.
                    source_start=float(getattr(beat,"source_start",0.0) or 0.0)
                    local_sample=min(.25, max(0.0, (end-start)/2))
                    cap.set(cv2.CAP_PROP_POS_MSEC, (source_start+local_sample) * 1000.0)
                    ok, frame_from_video = cap.read()
                    if ok and frame_from_video is not None:
                        source = frame_from_video
                finally:
                    cap.release()
            if source is None:
                meaningful = False
                failures.append(f"{scene.id}/{i}: source cannot be independently decoded")
            else:
                expected = np.zeros_like(frame)
                h, w = source.shape[:2]
                scale = min(980/w, 950/h)
                sw, sh = round(w*scale), round(h*scale)
                rendered_source = cv2.resize(source,(sw,sh),interpolation=cv2.INTER_LANCZOS4)
                oy, ox = (frame.shape[0]-sh)//2, (frame.shape[1]-sw)//2
                expected[oy:oy+sh,ox:ox+sw] = rendered_source
                error = float(np.abs(cv2.resize(expected,(256,256)).astype(float)-cv2.resize(frame,(256,256)).astype(float)).mean())
                if error > 8:
                    meaningful = False
                    failures.append(f"{scene.id}/{i}: rendered state differs from pinned source ({error:.2f})")
            equivalent = previous is not None and equivalent_framing(previous, frame)
            replay = any(equivalent_framing(old, frame) for old in frames[:-1])
            if equivalent or replay:
                meaningful = False
                failures.append(f"{scene.id}/{i}: equivalent crop/zoom or replay; no observed new state")
            if previous is not None and end-start < 1.2:
                failures.append(f"{scene.id}/{i}: unreadably short state ({end-start:.2f}s)")
            # A claimed state must be visible, not just an authored timestamp.
            difference = float(np.abs(cv2.resize(frame,(256,256)).astype(float)-cv2.resize(previous,(256,256)).astype(float)).mean()) if previous is not None else None
            events.append({"scene": scene.id, "beat": i, "start": window["start"]+start,
                           "duration": end-start, "kind": change.kind if change else None,
                           "concept": change.concept_id if change else None,
                           "meaningful_delivery": meaningful, "equivalent_framing": equivalent,
                           "pixel_difference": difference, "frame": str(path),
                           "declared_information": change.added_information if change else None})
            previous = frame
            frames.append(frame)
    first = [e for e in events if 0 < e["start"] < 5 and e["meaningful_delivery"]]
    if not first:
        failures.append("no observed meaningful information/state change in the first 0–5s")
    return {"status": "FAIL" if failures else "PASS", "failures": failures, "events": events,
            "first_5s_meaningful_changes": len(first), "human_review_required": True,
            "semantic_status": "REQUIRES_VISUAL_REVIEW",
            "pass_meaning": "Declared non-framing states delivered without detected crop churn; not proof of semantic novelty."}
