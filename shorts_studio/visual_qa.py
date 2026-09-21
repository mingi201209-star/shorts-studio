from __future__ import annotations
import json, subprocess
from pathlib import Path
from typing import Protocol

class VisionProvider(Protocol):
    def evaluate(self, image: Path, requirements: list[str], **context) -> dict: ...

class SidecarVisionProvider:
    """CI/provider-neutral adapter. A trusted vision worker (human reviewer or an
    external multimodal API integration) writes <frame>.qa.json next to the frame.
    Missing/invalid evidence is NOT_EVALUATED, never PASS."""
    def evaluate(self, image: Path, requirements: list[str], **context) -> dict:
        sidecar = image.with_suffix(image.suffix + ".qa.json")
        if not sidecar.exists():
            return {"status": "NOT_EVALUATED", "reason": "no semantic vision evidence"}
        try:
            data = json.loads(sidecar.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"status": "NOT_EVALUATED", "reason": "unreadable semantic vision evidence"}
        status = data.get("status")
        if status not in {"PASS", "FAIL"}:
            return {"status": "NOT_EVALUATED", "reason": "invalid semantic vision evidence"}
        return {"status": status, "details": data.get("details", []), "requirements": requirements}

_SQUARE_KEYWORDS = ("90도", "90°", "네모", "각진", "sharp", "square")
_ROUND_KEYWORDS = ("둥근", "라운드", "round", "rounded")
_DISTINGUISH_KEYWORDS = ("구별", "distinguish")

def _shape_expectations(requirements: list[str]) -> tuple[bool, bool, bool]:
    text = " ".join(requirements).lower()
    expects_square = any(k.lower() in text for k in _SQUARE_KEYWORDS)
    expects_round = any(k.lower() in text for k in _ROUND_KEYWORDS)
    expects_distinct = any(k.lower() in text for k in _DISTINGUISH_KEYWORDS)
    return expects_square, expects_round, expects_distinct

def classify_corner_shape(contour, image_area: float) -> dict:
    """Classify one contour as a sharp-cornered ("square") or large-rounded-corner
    ("rounded") quadrilateral using real geometric measurements (no ML): the ratio of
    vertices needed to fit the contour at a fine vs. coarse tolerance (curves need many
    more fine-tolerance points than straight edges do), and how much of the bounding
    box the contour fills (rounded corners cut area out of the box corners)."""
    import cv2
    area = cv2.contourArea(contour)
    if image_area <= 0 or area / image_area < 0.008:
        return {"shape": "unknown", "reason": "contour too small to classify"}
    peri = cv2.arcLength(contour, True)
    if peri <= 0:
        return {"shape": "unknown", "reason": "degenerate contour"}
    coarse = cv2.approxPolyDP(contour, 0.02 * peri, True)
    fine = cv2.approxPolyDP(contour, 0.004 * peri, True)
    x, y, w, h = cv2.boundingRect(contour)
    bbox_area = max(1, w * h)
    extent = area / bbox_area
    roundness_ratio = len(fine) / max(1, len(coarse))
    metrics = {"extent": extent, "roundness_ratio": roundness_ratio, "coarse_vertices": len(coarse)}
    if 4 <= len(coarse) <= 6 and extent >= 0.95 and roundness_ratio < 1.6:
        return {"shape": "square", **metrics}
    if extent <= 0.94 and roundness_ratio >= 1.6:
        return {"shape": "rounded", **metrics}
    return {"shape": "unknown", **metrics}

def _window_candidates(image_path: Path):
    import cv2
    img = cv2.imread(str(image_path))
    if img is None:
        return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 40, 120)
    edges = cv2.dilate(edges, None, iterations=1)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    h, w = gray.shape
    frame_area = float(h * w)
    candidates = []
    for c in contours:
        area = cv2.contourArea(c)
        frac = area / frame_area
        if 0.08 <= frac <= 0.45:
            x, y, cw, ch = cv2.boundingRect(c)
            candidates.append({"contour": c, "cx": x + cw / 2, "frac": frac})
    return {"candidates": candidates, "frame_area": frame_area, "width": w}

class CornerGeometryVisionProvider:
    """Real (non-ML) corner-shape geometry check for the square-vs-rounded window
    requirement. Only commits to PASS/FAIL when it finds large, unambiguous
    diagram-scale shapes (as in a controlled comparison graphic); otherwise it
    steps back to NOT_EVALUATED rather than risk a false FAIL on a busy real photo,
    leaving that scene to the semantic (CLIP) provider."""
    def evaluate(self, image: Path, requirements: list[str], **context) -> dict:
        expects_square, expects_round, expects_distinct = _shape_expectations(requirements)
        if not expects_square and not expects_round:
            return {"status": "NOT_EVALUATED", "reason": "no corner-shape requirement declared"}
        try:
            data = _window_candidates(image)
        except Exception as e:
            return {"status": "NOT_EVALUATED", "reason": f"geometry analysis failed: {e}"}
        if data is None:
            return {"status": "NOT_EVALUATED", "reason": "frame could not be read"}
        classified = [
            {"cx": cand["cx"], **classify_corner_shape(cand["contour"], data["frame_area"])}
            for cand in data["candidates"]
        ]
        confident = [c for c in classified if c["shape"] != "unknown"]
        if not confident:
            return {"status": "NOT_EVALUATED", "reason": "no unambiguous window-shaped contour found", "candidates": classified}
        found_square = any(c["shape"] == "square" for c in confident)
        found_round = any(c["shape"] == "rounded" for c in confident)
        if expects_distinct or (expects_square and expects_round):
            left = [c for c in confident if c["cx"] < data["width"] / 2]
            right = [c for c in confident if c["cx"] >= data["width"] / 2]
            shapes = {c["shape"] for c in confident}
            if found_square and found_round and len(shapes) >= 2 and (left or right):
                return {"status": "PASS", "shapes": [c["shape"] for c in confident]}
            return {"status": "FAIL", "reason": "square and rounded corners were not both distinctly present", "shapes": [c["shape"] for c in confident]}
        if expects_square and not found_square:
            return {"status": "FAIL", "reason": "expected sharp 90-degree corners were not found", "shapes": [c["shape"] for c in confident]}
        if expects_round and not found_round:
            return {"status": "FAIL", "reason": "expected large rounded corners were not found", "shapes": [c["shape"] for c in confident]}
        return {"status": "PASS", "shapes": [c["shape"] for c in confident]}

class ClarityVisionProvider:
    """Real, deterministic image-quality floor: rejects blank, corrupted, flat,
    or extremely blurry frames using measured sharpness/contrast/exposure. This is
    the 'mobile clarity' / 'subject visibility' baseline; it never guesses about
    scene semantics."""
    MIN_SHARPNESS = 8.0
    MIN_CONTRAST = 6.0
    MIN_MEAN = 8.0
    MAX_MEAN = 248.0

    def evaluate(self, image: Path, requirements: list[str], **context) -> dict:
        try:
            import cv2
        except ImportError:
            return {"status": "NOT_EVALUATED", "reason": "opencv not installed"}
        img = cv2.imread(str(image))
        if img is None:
            return {"status": "NOT_EVALUATED", "reason": "frame could not be read"}
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        contrast = float(gray.std())
        mean = float(gray.mean())
        metrics = {"sharpness": sharpness, "contrast": contrast, "mean": mean}
        if sharpness < self.MIN_SHARPNESS:
            return {"status": "FAIL", "reason": "frame is too blurry for mobile viewing", **metrics}
        if contrast < self.MIN_CONTRAST:
            return {"status": "FAIL", "reason": "frame is nearly flat/blank", **metrics}
        if not (self.MIN_MEAN <= mean <= self.MAX_MEAN):
            return {"status": "FAIL", "reason": "frame is over/under-exposed", **metrics}
        return {"status": "PASS", **metrics}

_CLIP_CACHE: dict[tuple[str, str], object] = {}

def _load_clip(model_name: str = "ViT-B-32", pretrained: str = "openai"):
    key = (model_name, pretrained)
    if key in _CLIP_CACHE:
        return _CLIP_CACHE[key]
    try:
        import torch, open_clip
    except ImportError:
        _CLIP_CACHE[key] = None
        return None
    model, _, preprocess = open_clip.create_model_and_transforms(model_name, pretrained=pretrained)
    tokenizer = open_clip.get_tokenizer(model_name)
    model.eval()
    bundle = (torch, model, preprocess, tokenizer)
    _CLIP_CACHE[key] = bundle
    return bundle

def clip_zero_shot_scores(bundle, image_path: Path, labels: list[str]) -> dict[str, float]:
    """Pure scoring step, kept separate from model loading so tests can exercise
    the PASS/FAIL decision logic by monkeypatching this function without needing
    torch/open_clip installed."""
    torch, model, preprocess, tokenizer = bundle
    from PIL import Image
    image = preprocess(Image.open(image_path).convert("RGB")).unsqueeze(0)
    text = tokenizer(labels)
    with torch.no_grad():
        image_features = model.encode_image(image)
        text_features = model.encode_text(text)
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)
        sims = (image_features @ text_features.T).squeeze(0)
    return {label: float(sims[i]) for i, label in enumerate(labels)}

class ClipSemanticVisionProvider:
    """Real local zero-shot vision-language semantic check (open_clip, no API key,
    no payment, runs entirely on-device). Confirms narration-declared subjects are
    actually present and that wrong-domain content is not dominant. Degrades to
    NOT_EVALUATED (never a fake PASS) when the scene declares no labels or the
    optional 'vision' dependency group is not installed."""
    MIN_MARGIN = 0.03
    MIN_ABS = 0.18

    def __init__(self, model_name: str = "ViT-B-32", pretrained: str = "openai"):
        self.model_name = model_name
        self.pretrained = pretrained

    def evaluate(self, image: Path, requirements: list[str], **context) -> dict:
        positive = list(context.get("positive_labels") or [])
        negative = list(context.get("negative_labels") or [])
        if not positive:
            return {"status": "NOT_EVALUATED", "reason": "no visual_qa_labels declared for scene"}
        bundle = _load_clip(self.model_name, self.pretrained)
        if bundle is None:
            return {"status": "NOT_EVALUATED", "reason": "local CLIP model unavailable; install the 'vision' extra (open-clip-torch, torch)"}
        try:
            scores = clip_zero_shot_scores(bundle, image, positive + negative)
        except Exception as e:
            return {"status": "NOT_EVALUATED", "reason": f"CLIP inference failed: {e}"}
        best_pos = max(scores[label] for label in positive)
        best_neg = max((scores[label] for label in negative), default=-1.0)
        if best_pos < self.MIN_ABS:
            return {"status": "FAIL", "reason": "no declared subject label matched the frame", "scores": scores}
        if best_neg >= 0 and (best_pos - best_neg) < self.MIN_MARGIN:
            return {"status": "FAIL", "reason": "wrong-domain content scored too close to the expected subject", "scores": scores}
        return {"status": "PASS", "scores": scores}

class CompositeVisionProvider:
    """Combines several independent real checks. Any confident FAIL fails the
    scene; PASS requires at least one provider to have actually evaluated it and
    none to have failed. If every sub-provider abstains, the scene is
    NOT_EVALUATED (fail-closed), never defaulted to PASS."""
    def __init__(self, providers: list[VisionProvider] | None = None):
        self.providers = providers if providers is not None else [
            SidecarVisionProvider(), ClarityVisionProvider(), CornerGeometryVisionProvider(), ClipSemanticVisionProvider(),
        ]

    def evaluate(self, image: Path, requirements: list[str], **context) -> dict:
        sub_results = []
        applicable = []
        for provider in self.providers:
            result = provider.evaluate(image, requirements, **context)
            status = result.get("status")
            if status not in {"PASS", "FAIL", "NOT_EVALUATED"}:
                # Malformed/unrecognized evidence must never be treated as a pass signal.
                result = {**result, "status": "NOT_EVALUATED", "reason": f"malformed provider status: {status!r}"}
            sub_results.append({"provider": type(provider).__name__, **result})
            if result["status"] != "NOT_EVALUATED":
                applicable.append(result)
        if not applicable:
            return {"status": "NOT_EVALUATED", "reason": "no vision provider could evaluate this scene", "sub_results": sub_results}
        failures = [r for r in applicable if r["status"] == "FAIL"]
        if failures:
            return {"status": "FAIL", "reason": failures[0].get("reason", "semantic visual QA failed"), "sub_results": sub_results}
        return {"status": "PASS", "sub_results": sub_results}

def default_vision_provider() -> VisionProvider:
    return CompositeVisionProvider()

def _clip_duration(video: Path) -> float:
    try:
        p = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(video)],
            capture_output=True, text=True, check=True,
        )
        return float(json.loads(p.stdout)["format"]["duration"])
    except Exception:
        return 1.0

def extract_frame(video: Path, timestamp: float, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-ss", str(timestamp), "-i", str(video), "-frames:v", "1", str(output)], check=True, capture_output=True)
    return output

def extract_representative_frame(video: Path, output: Path) -> Path:
    """Extract the mid-point frame of the clip as its representative frame."""
    timestamp = max(0.0, _clip_duration(video) / 2)
    return extract_frame(video, timestamp, output)

def asset_visual_gate(project, sources: list[dict]) -> dict:
    by_scene = {x["scene"]: x for x in sources}
    failures = []
    for scene in project.scenes:
        if (scene.asset or scene.asset_url) and scene.id not in by_scene:
            failures.append({"scene": scene.id, "reason": "declared asset was not used"})
        if scene.visual_qa_requirements and not (scene.asset or scene.asset_url):
            failures.append({"scene": scene.id, "reason": "visual QA requirements exist without an asset"})
    return {
        "structural_status": "PASS" if not failures else "FAIL",
        "semantic_status": "NOT_EVALUATED",
        "failures": failures,
        "requirements": {s.id: s.visual_qa_requirements for s in project.scenes if s.visual_qa_requirements},
    }

def evaluate_scene_semantics(scene, clip: Path, provider: VisionProvider, frame_path: Path) -> dict:
    """Evaluate one scene's representative frame. Isolated from the loop in
    semantic_visual_gate so the recovery loop can re-invoke it for a single scene
    without touching any other scene's clip or QA result."""
    if not scene.visual_qa_requirements:
        return {"scene": scene.id, "status": "NOT_EVALUATED", "reason": "no visual_qa_requirements declared"}
    extract_representative_frame(clip, frame_path)
    result = provider.evaluate(
        frame_path, scene.visual_qa_requirements,
        narration=getattr(scene, "narration", ""),
        positive_labels=list(getattr(scene, "visual_qa_labels", []) or []),
        negative_labels=list(getattr(scene, "visual_qa_negative_labels", []) or []),
    )
    return {"scene": scene.id, "requirements": scene.visual_qa_requirements, **result}

def production_semantic_ok(status: str, require_semantic: bool) -> bool:
    """Fail-closed policy: in production-required mode, only an actually-executed
    PASS is acceptable -- NOT_EVALUATED is treated as a failure, never a silent
    success. Outside required mode, NOT_EVALUATED is tolerated but FAIL always
    fails, in either mode."""
    if require_semantic:
        return status == "PASS"
    return status != "FAIL"

def semantic_visual_gate(project, scene_clips: list[Path], provider: VisionProvider | None = None, build_dir: Path = Path("build")) -> dict:
    provider = provider or default_vision_provider()
    results = []
    for scene, clip in zip(project.scenes, scene_clips):
        if not scene.visual_qa_requirements:
            continue
        frame = build_dir / f"{scene.id}_qa.jpg"
        results.append(evaluate_scene_semantics(scene, clip, provider, frame))
    if any(r["status"] == "FAIL" for r in results):
        status = "FAIL"
    elif results and all(r["status"] == "PASS" for r in results):
        status = "PASS"
    else:
        status = "NOT_EVALUATED"
    return {"status": status, "results": results}
