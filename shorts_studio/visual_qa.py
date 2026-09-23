from __future__ import annotations
import hashlib, json, subprocess
from pathlib import Path
from typing import Protocol

class VisionProvider(Protocol):
    def evaluate(self, image: Path, requirements: list[str], **context) -> dict: ...

class SidecarVisionProvider:
    def evaluate(self, image: Path, requirements: list[str], **context) -> dict:
        sidecar = image.with_suffix(image.suffix + ".qa.json")
        if not sidecar.exists(): return {"status":"NOT_EVALUATED","reason":"no semantic vision evidence"}
        try: data=json.loads(sidecar.read_text(encoding="utf-8"))
        except (json.JSONDecodeError,OSError): return {"status":"NOT_EVALUATED","reason":"unreadable semantic vision evidence"}
        status=data.get("status")
        if status not in {"PASS","FAIL"}: return {"status":"NOT_EVALUATED","reason":"invalid semantic vision evidence"}
        return {"status":status,"details":data.get("details",[]),"requirements":requirements}

_SQUARE_KEYWORDS=("90도","90°","네모","각진","sharp","square")
_ROUND_KEYWORDS=("둥근","라운드","round","rounded")
_DISTINGUISH_KEYWORDS=("구별","distinguish")
def _shape_expectations(requirements):
    text=" ".join(requirements).lower()
    return any(k.lower() in text for k in _SQUARE_KEYWORDS),any(k.lower() in text for k in _ROUND_KEYWORDS),any(k.lower() in text for k in _DISTINGUISH_KEYWORDS)

def classify_corner_shape(contour,image_area):
    """Classify a contour as sharp-cornered ("square") or large-rounded-corner
    ("rounded") using corner-gap-ratio: how far the contour's actual boundary
    sits from the four corners of its own bounding box, relative to the box
    diagonal. A sharp corner reaches almost all the way into the bbox corner
    (gap ~0); a large rounded corner recedes well short of it (gap large).
    This is measured directly in pixel space, so it survives JPEG/H.264
    compression artifacts that make vertex-count-based fitting (approxPolyDP)
    unreliable -- compression noise can fragment a straight edge into many
    tiny zigzag vertices at a fine tolerance without the shape actually being
    curved, which previously caused real sharp corners to be misread as
    rounded on the composited video frame (not just the raw source asset)."""
    import cv2, numpy as np
    area=cv2.contourArea(contour)
    if image_area<=0 or area/image_area<.008:return {"shape":"unknown","reason":"contour too small to classify"}
    x,y,w,h=cv2.boundingRect(contour)
    bbox_area=max(1,w*h); extent=area/bbox_area
    diag=(w**2+h**2)**0.5
    if diag<=0:return {"shape":"unknown","reason":"degenerate contour"}
    pts=contour.reshape(-1,2).astype(float)
    corners=((x,y),(x+w,y),(x,y+h),(x+w,y+h))
    corner_gaps=[float(np.min(np.hypot(pts[:,0]-cx,pts[:,1]-cy))) for cx,cy in corners]
    gap_ratio=float(np.mean(corner_gaps))/diag
    m={"extent":extent,"corner_gap_ratio":gap_ratio}
    if gap_ratio<=0.035 and extent>=0.85:return {"shape":"square",**m}
    if gap_ratio>=0.055:return {"shape":"rounded",**m}
    return {"shape":"unknown",**m}

def _window_candidates(image_path):
    import cv2
    img=cv2.imread(str(image_path))
    if img is None:return None
    gray=cv2.GaussianBlur(cv2.cvtColor(img,cv2.COLOR_BGR2GRAY),(5,5),0)
    edges=cv2.dilate(cv2.Canny(gray,40,120),None,iterations=1)
    contours,_=cv2.findContours(edges,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
    h,w=gray.shape; area=float(h*w); out=[]
    # Lower bound recalibrated for the safe-area composition fix: the
    # contain-fit foreground band is now capped to SAFE_BOTTOM_Y-SAFE_TOP_Y
    # tall (never bleeding into the bottom caption zone), so the window
    # comparison graphic renders smaller in-frame than before (measured
    # ~0.03-0.044 for the real shapes vs ~0.0016 for background noise --
    # .02 keeps a wide margin above noise while covering the new real size).
    for c in contours:
        frac=cv2.contourArea(c)/area
        if .02<=frac<=.45:
            x,y,cw,ch=cv2.boundingRect(c); out.append({"contour":c,"cx":x+cw/2,"frac":frac})
    return {"candidates":out,"frame_area":area,"width":w}

class CornerGeometryVisionProvider:
    """Real (non-ML) corner-shape geometry check. When both a square and a
    rounded corner are expected (the side-by-side comparison graphic), it
    requires the square to be found specifically in the LEFT half of the
    frame and the rounded shape specifically in the RIGHT half -- matching
    the actual left/right layout of the comparison -- so a frame where both
    sides show the same shape (all-square or all-rounded) fails."""
    def evaluate(self,image,requirements,**context):
        expects_square,expects_round,expects_distinct=_shape_expectations(requirements)
        if not expects_square and not expects_round:return {"status":"NOT_EVALUATED","reason":"no corner-shape requirement declared"}
        try:data=_window_candidates(image)
        except Exception as e:return {"status":"NOT_EVALUATED","reason":f"geometry analysis failed: {e}"}
        if data is None:return {"status":"NOT_EVALUATED","reason":"frame could not be read"}
        classified=[{"cx":c["cx"],**classify_corner_shape(c["contour"],data["frame_area"])} for c in data["candidates"]]
        confident=[c for c in classified if c["shape"]!="unknown"]
        if not confident:return {"status":"NOT_EVALUATED","reason":"no unambiguous window-shaped contour found","candidates":classified}
        mid=data["width"]/2
        left=[c for c in confident if c["cx"]<mid]; right=[c for c in confident if c["cx"]>=mid]
        if expects_distinct or (expects_square and expects_round):
            left_has_square=any(c["shape"]=="square" for c in left)
            right_has_round=any(c["shape"]=="rounded" for c in right)
            if left_has_square and right_has_round:return {"status":"PASS","shapes":[c["shape"] for c in confident]}
            return {"status":"FAIL","reason":"square (left) and rounded (right) corners were not both distinctly present","shapes":[c["shape"] for c in confident]}
        if expects_square and not any(c["shape"]=="square" for c in confident):return {"status":"FAIL","reason":"expected sharp 90-degree corners were not found","shapes":[c["shape"] for c in confident]}
        if expects_round and not any(c["shape"]=="rounded" for c in confident):return {"status":"FAIL","reason":"expected large rounded corners were not found","shapes":[c["shape"] for c in confident]}
        return {"status":"PASS","shapes":[c["shape"] for c in confident]}

class ClarityVisionProvider:
    MIN_SHARPNESS=8.;MIN_CONTRAST=6.;MIN_MEAN=8.;MAX_MEAN=248.
    def evaluate(self,image,requirements,**context):
        try:import cv2
        except ImportError:return {"status":"NOT_EVALUATED","reason":"opencv not installed"}
        img=cv2.imread(str(image))
        if img is None:return {"status":"NOT_EVALUATED","reason":"frame could not be read"}
        gray=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY); s=float(cv2.Laplacian(gray,cv2.CV_64F).var()); c=float(gray.std()); m=float(gray.mean()); metrics={"sharpness":s,"contrast":c,"mean":m}
        if s<self.MIN_SHARPNESS:return {"status":"FAIL","reason":"frame is too blurry for mobile viewing",**metrics}
        if c<self.MIN_CONTRAST:return {"status":"FAIL","reason":"frame is nearly flat/blank",**metrics}
        if not(self.MIN_MEAN<=m<=self.MAX_MEAN):return {"status":"FAIL","reason":"frame is over/under-exposed",**metrics}
        return {"status":"PASS",**metrics}

_CLIP_CACHE={}
def _load_clip(model_name="ViT-B-32",pretrained="openai"):
    key=(model_name,pretrained)
    if key in _CLIP_CACHE:return _CLIP_CACHE[key]
    try:import torch,open_clip
    except ImportError:_CLIP_CACHE[key]=None;return None
    model,_,preprocess=open_clip.create_model_and_transforms(model_name,pretrained=pretrained); tokenizer=open_clip.get_tokenizer(model_name);model.eval()
    _CLIP_CACHE[key]=(torch,model,preprocess,tokenizer);return _CLIP_CACHE[key]
def clip_zero_shot_scores(bundle,image_path,labels):
    torch,model,preprocess,tokenizer=bundle
    from PIL import Image
    image=preprocess(Image.open(image_path).convert("RGB")).unsqueeze(0);text=tokenizer(labels)
    with torch.no_grad():
        a=model.encode_image(image);b=model.encode_text(text);a=a/a.norm(dim=-1,keepdim=True);b=b/b.norm(dim=-1,keepdim=True);s=(a@b.T).squeeze(0)
    return {label:float(s[i]) for i,label in enumerate(labels)}

class ClipSemanticVisionProvider:
    """Local zero-shot CLIP semantic check.

    CLIP is used as a wrong-domain detector, not as a calibrated binary
    classifier for specialist archival photography. A strong contradiction
    (negative ensemble >= positive ensemble) is a confident FAIL. A small
    positive lead below MIN_MARGIN is explicitly INCONCLUSIVE so another
    independent semantic provider/evidence can arbitrate it; it must not be
    mislabeled as wrong-domain. Production still fails closed on an overall
    NOT_EVALUATED result.
    """
    MIN_MARGIN=.03;MIN_ABS=.18
    def __init__(self,model_name="ViT-B-32",pretrained="openai"):self.model_name=model_name;self.pretrained=pretrained
    def evaluate(self,image,requirements,**context):
        positive=list(context.get("positive_labels") or []);negative=list(context.get("negative_labels") or [])
        if not positive:return {"status":"NOT_EVALUATED","reason":"no visual_qa_labels declared for scene"}
        bundle=_load_clip(self.model_name,self.pretrained)
        if bundle is None:return {"status":"NOT_EVALUATED","reason":"local CLIP model unavailable; install the 'vision' extra (open-clip-torch, torch)"}
        try:scores=clip_zero_shot_scores(bundle,image,positive+negative)
        except Exception as e:return {"status":"NOT_EVALUATED","reason":f"CLIP inference failed: {e}"}
        pos_scores=[scores[x] for x in positive];neg_scores=[scores[x] for x in negative]
        best_pos=max(pos_scores);mean_pos=sum(pos_scores)/len(pos_scores)
        mean_neg=sum(neg_scores)/len(neg_scores) if neg_scores else -1.
        if best_pos<self.MIN_ABS:return {"status":"FAIL","reason":"no declared subject label matched the frame","scores":scores}
        if neg_scores:
            margin=mean_pos-mean_neg
            if margin<=0:return {"status":"FAIL","reason":"wrong-domain content matched at least as strongly as the expected subject","scores":scores,"mean_pos":mean_pos,"mean_neg":mean_neg,"margin":margin}
            if margin<self.MIN_MARGIN:return {"status":"NOT_EVALUATED","reason":"CLIP positive lead is too narrow for a confident archival-image verdict","scores":scores,"mean_pos":mean_pos,"mean_neg":mean_neg,"margin":margin}
        return {"status":"PASS","scores":scores,"mean_pos":mean_pos,"mean_neg":mean_neg,"margin":mean_pos-mean_neg if neg_scores else None}

class AssetProvenanceVisionProvider:
    """Deterministic, non-ML evidence: verifies the resolved source asset's
    exact byte content matches a manifest-declared expected SHA-256 for this
    scene. This proves the specific, previously-vetted historical image is
    the one actually in use, independent of any similarity-score judgment --
    it does not need CLIP to confidently arbitrate fine archival detail, and
    it fails hard (not NOT_EVALUATED) on any substitution: a bad recovery
    candidate, a hijacked URL, or a manual mistake swapping in the wrong
    file, all produce a different hash. NOT_EVALUATED only when the scene
    declares no expected hash at all."""
    def evaluate(self,image,requirements,**context):
        expected=context.get("expected_asset_sha256") or []
        if isinstance(expected,str):expected=[expected]
        if not expected:return {"status":"NOT_EVALUATED","reason":"no expected_asset_sha256 declared for this scene"}
        asset_path=context.get("asset_path")
        if not asset_path or not Path(asset_path).exists():
            return {"status":"FAIL","reason":"source asset file unavailable to verify provenance"}
        digest=hashlib.sha256(Path(asset_path).read_bytes()).hexdigest()
        if digest not in expected:
            return {"status":"FAIL","reason":f"asset content hash does not match any declared-correct hash (got {digest[:16]}...); wrong or substituted image","actual_sha256":digest}
        return {"status":"PASS","sha256":digest}

class CompositeVisionProvider:
    """Combine independent visual checks without letting provenance substitute
    for semantic evidence.

    AssetProvenanceVisionProvider answers only "is this the exact pinned
    source asset?". It must never turn a semantic mismatch into PASS. A
    confident FAIL from any applicable provider therefore fails the scene.
    This keeps provenance useful for substitution/hijack detection while
    preserving the separate scene-to-script semantic contract.
    """
    def __init__(self,providers=None):
        self.providers=providers if providers is not None else [
            SidecarVisionProvider(),
            AssetProvenanceVisionProvider(),
            ClarityVisionProvider(),
            CornerGeometryVisionProvider(),
            ClipSemanticVisionProvider(),
        ]

    def evaluate(self,image,requirements,**context):
        subs=[];app=[]
        for p in self.providers:
            r=p.evaluate(image,requirements,**context)
            if r.get("status") not in {"PASS","FAIL","NOT_EVALUATED"}:
                r={**r,"status":"NOT_EVALUATED","reason":f"malformed provider status: {r.get('status')!r}"}
            subs.append({"provider":type(p).__name__,**r})
            if r["status"]!="NOT_EVALUATED":
                app.append((p,r))
        if not app:
            return {"status":"NOT_EVALUATED","reason":"no vision provider could evaluate this scene","sub_results":subs}
        fails=[r for _,r in app if r["status"]=="FAIL"]
        if fails:
            return {"status":"FAIL","reason":fails[0].get("reason","semantic visual QA failed"),"sub_results":subs}
        return {"status":"PASS","sub_results":subs}
def default_vision_provider():return CompositeVisionProvider()
def _clip_duration(video):
    try:
        p=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","json",str(video)],capture_output=True,text=True,check=True);return float(json.loads(p.stdout)["format"]["duration"])
    except Exception:return 1.
def extract_frame(video,timestamp,output):
    output.parent.mkdir(parents=True,exist_ok=True);subprocess.run(["ffmpeg","-y","-ss",str(timestamp),"-i",str(video),"-frames:v","1",str(output)],check=True,capture_output=True);return output
def extract_representative_frame(video,output):return extract_frame(video,max(0.,_clip_duration(video)/2),output)
def asset_visual_gate(project,sources):
    by={x["scene"]:x for x in sources};fail=[]
    for s in project.scenes:
        if (s.asset or s.asset_url) and s.id not in by:fail.append({"scene":s.id,"reason":"declared asset was not used"})
        if s.visual_qa_requirements and not(s.asset or s.asset_url):fail.append({"scene":s.id,"reason":"visual QA requirements exist without an asset"})
    return {"structural_status":"PASS" if not fail else "FAIL","semantic_status":"NOT_EVALUATED","failures":fail,"requirements":{s.id:s.visual_qa_requirements for s in project.scenes if s.visual_qa_requirements}}
def evaluate_scene_semantics(scene,clip,provider,frame_path,asset_path=None):
    if not scene.visual_qa_requirements:return {"scene":scene.id,"status":"NOT_EVALUATED","reason":"no visual_qa_requirements declared"}
    extract_representative_frame(clip,frame_path)
    r=provider.evaluate(frame_path,scene.visual_qa_requirements,
        narration=getattr(scene,"narration",""),
        positive_labels=list(getattr(scene,"visual_qa_labels",[]) or []),
        negative_labels=list(getattr(scene,"visual_qa_negative_labels",[]) or []),
        expected_asset_sha256=list(getattr(scene,"visual_qa_expected_sha256",[]) or []),
        asset_path=asset_path)
    return {"scene":scene.id,"requirements":scene.visual_qa_requirements,**r}
def production_semantic_ok(status,require_semantic):return status=="PASS" if require_semantic else status!="FAIL"
def semantic_visual_gate(project,scene_clips,provider=None,build_dir=Path("build")):
    provider=provider or default_vision_provider();results=[]
    for scene,clip in zip(project.scenes,scene_clips):
        if scene.visual_qa_requirements:results.append(evaluate_scene_semantics(scene,clip,provider,build_dir/f"{scene.id}_qa.jpg"))
    status="FAIL" if any(r["status"]=="FAIL" for r in results) else ("PASS" if results and all(r["status"]=="PASS" for r in results) else "NOT_EVALUATED")
    return {"status":status,"results":results}
