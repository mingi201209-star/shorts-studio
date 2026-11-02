"""Read-only integrity check for the isolated driver pilot, not final/editorial QA."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .ledger import TaskLedger


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_pilot(root: Path, renderer: Path) -> dict:
    import cv2
    from PIL import Image, ImageStat

    proof = json.loads((root / "driver-pilot.json").read_text())
    if proof["renderer_sha256"] != digest(renderer):
        raise ValueError("pilot renderer source changed")
    assert (proof["samples"], proof["resolution"], proof["fps"], proof["frame_count"]) == (
        32, [1080, 1920], 30, 90)
    assert proof["is_final"] is False and proof["narration_alignment"] == "NOT_YET_APPLIED"
    assert set(proof["png_sha256"]) == {f"{n:04d}.png" for n in range(1, 91)}
    pixels = []
    for name, sha in sorted(proof["png_sha256"].items()):
        path = root / name
        if digest(path) != sha:
            raise ValueError(f"PNG hash mismatch: {name}")
        with Image.open(path) as im:
            assert im.size == (1080, 1920)
            rgb = im.convert("RGB")
            if sum(ImageStat.Stat(rgb.resize((30, 50))).mean) < 25:
                raise ValueError(f"black or empty visual: {name}")
            pixels.append(hashlib.md5(rgb.tobytes()).hexdigest())
    assert len(set(pixels)) == 90
    for name in ("driver-lossless.mkv", "driver-review.mp4"):
        cap = cv2.VideoCapture(str(root / name))
        try:
            assert cap.isOpened(), f"could not decode {name}"
            assert abs(cap.get(cv2.CAP_PROP_FPS) - 30) < .001
            decoded = []
            while True:
                ok, bgr = cap.read()
                if not ok:
                    break
                assert bgr.shape[:2] == (1920, 1080)
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                decoded.append(hashlib.md5(rgb.tobytes()).hexdigest())
            assert len(decoded) == len(set(decoded)) == 90, name
            if name.endswith(".mkv"):
                assert decoded == pixels, "lossless clip does not match PNG pixels"
        finally:
            cap.release()
    return {
        "technical_status": "PASS_DRIVER_PILOT_INTEGRITY",
        "video": str((root / "driver-review.mp4").resolve()),
        "sha256": digest(root / "driver-review.mp4"),
        "native_frames_verified": 90, "lossless_decoded_exact": True,
        "is_final": False, "is_mock": False, "silent": True,
        "editorial_status": "REVIEW_REQUIRED",
        "narration_alignment": "NOT_YET_APPLIED", "human_first_view": "UNVERIFIED",
        "upload_authorized": False,
    }


def record_review(root: Path, renderer: Path, ledger: TaskLedger, task_id: str) -> dict:
    task = ledger.get(task_id)
    assert task.requirements.get("kind") == "driver-action-pilot"
    assert task.output and task.output.get("github_run_id")
    result = inspect_pilot(root, renderer)
    result["github_run_id"] = task.output["github_run_id"]
    existing = ledger.find_evaluation_for(task_id)
    if existing is None:
        ledger.create(
            department="평가부", division="기술검수", predecessors=[task_id],
            requirements={"kind": "driver-pilot-integrity"},
            completion_criteria="90 actual frames, exact lossless pixels, no final/editorial claim",
            input_hash=digest(root / "driver-pilot.json"), output=result, status="completed")
    elif existing.output != result:
        raise ValueError("existing pilot review changed; explicit revision required")
    ledger.update(task_id, status="completed", output=result)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--renderer", type=Path, required=True)
    p.add_argument("--ledger", type=Path, required=True)
    p.add_argument("--task", required=True)
    args = p.parse_args()
    result = record_review(args.root, args.renderer, TaskLedger(args.ledger), args.task)
    (args.root / "pilot-integrity.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
