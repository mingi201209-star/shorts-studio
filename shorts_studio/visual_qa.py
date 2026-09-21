from __future__ import annotations
import json, subprocess
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
    import cv2
    area=cv2.contourArea(contour)
    if image_area<=0 or area/image_area<.008:return {"shape":"unknown","reason":"contour too small to classify"}
    peri=cv2.arcLength(contour,True)
    if peri<=0:return {"shape":"unknown","reason":"degenerate contour"}
    coarse=cv2.approxPolyDP(contour,.02*peri,True); fine=cv2.approxPolyDP(contour,.004*peri,True)
    x,y,w,h=cv2.boundingRect(contour); extent=area/max(1,w*h); ratio=len(fine)/max(1,len(coarse))
    m={"extent":extent,"roundness_ratio":ratio,"coarse_vertices":len(coarse)}
    # Thick strokes create inner/outer contours. A true rectangle still has four
    # coarse vertices even when edge dilation lowers extent slightly.
    if len(coarse)==4 and ratio<1.6:return {"shape":"square",**m}
    if 4<=len(coarse)<=10 and ratio>=1.6 and extent<=.94:return {"shape":"rounded",**m}
    return {"shape":"unknown",**m}

def _window_candidates(image_path):
    import cv2
    img=cv2.imread(str(image_path))
    if img is None:return None
    gray=cv2.GaussianBlur(cv2.cvtColor(img,cv2.COLOR_BGR2GRAY),(5,5),0)
    edges=cv2.dilate(cv2.Canny(gray,40,120),None,iterations=1)
    contours,_=cv2.findContours(edges,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
    h,w=gray.shape; area=float(h*w); out=[]
    for c in contours:
        frac=cv2.contourArea(c)/area
        if .08<=frac<=.45:
            x,y,cw,ch=cv2.boundingRect(c); out.append({"contour":c,"cx":x+cw/2,"frac":frac})
    return {"candidates":out,"frame_area":area,"width":w}

class CornerGeometryVisionProvider:
    def evaluate(self,image,requirements,**context):
        sq,rnd,distinct=_shape_expectations(requirements)
        if not sq and not rnd:return {"status":"NOT_EVALUATED","reason":"no corner-shape requirement declared"}
        try:data=_window_candidates(image)
        except Exception as e:return {"status":"NOT_EVALUATED","reason":f"geometry analysis failed: {e}"}
        if data is None:return {"status":"NOT_EVALUATED","reason":"frame could not be read"}
        classified=[{"cx":c["cx"],**classify_corner_shape(c["contour"],data["frame_area"])} for c in data["candidates"]]
        confident=[c for c in classified if c["shape"]!="unknown"]
        if not confident:return {"status":"NOT_EVALUATED","reason":"no unambiguous window-shaped contour found","candidates":classified}
        left=[c for c in confident if c["cx"]<data["width"]/2]; right=[c for c in confident if c["cx"]>=data["width"]/2]
        found_sq=any(c["shape"]=="square" for c in left if sq) or (not distinct and any(c["shape"]=="square" for c in confident))
        found_rnd=any(c["shape"]=="rounded" for c in right if rnd) or (not distinct and any(c["shape"]=="rounded" for c in confident))
        if distinct or (sq and rnd):
            if found_sq and found_rnd:return {"status":"PASS","shapes":[c["shape"] for c in confident]}
            return {"status":"FAIL","reason":"square and rounded corners were not both distinctly present","shapes":[c["shape"] for c in confident]}
        if sq and not any(c["shape"]=="square" for c in confident):return {"status":"FAIL","reason":"expected sharp 90-degree corners were not found","shapes":[c["shape"] for c in confident]}
        if rnd and not any(c["shape"]=="rounded" for c in confident):return {"status":"FAIL","reason":"expected large rounded corners were not found","shapes":[c["shape"] for c in confident]}
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
    MIN_MARGIN=.03;MIN_ABS=.18
    def __init__(self,model_name="ViT-B-32",pretrained="openai"):self.model_name=model_name;self.pretrained=pretrained
    def evaluate(self,image,requirements,**context):
        positive=list(context.get("positive_labels") or []);negative=list(context.get("negative_labels") or [])
        if not positive:return {"status":"NOT_EVALUATED","reason":"no visual_qa_labels declared for scene"}
        bundle=_load_clip(self.model_name,self.pretrained)
        if bundle is None:return {"status":"NOT_EVALUATED","reason":"local CLIP model unavailable; install the 'vision' extra (open-clip-torch, torch)"}
        try:scores=clip_zero_shot_scores(bundle,image,positive+negative)
        except Exception as e:return {"status":"NOT_EVALUATED","reason":f"CLIP inference failed: {e}"}
        bp=max(scores[x] for x in positive);bn=max((scores[x] for x in negative),default=-1.)
        if bp<self.MIN_ABS:return {"status":"FAIL","reason":"no declared subject label matched the frame","scores":scores}
        if bn>=0 and bp-bn<self.MIN_MARGIN:return {"status":"FAIL","reason":"wrong-domain content scored too close to the expected subject","scores":scores}
        return {"status":"PASS","scores":scores}

class CompositeVisionProvider:
    def __init__(self,providers=None):self.providers=providers if providers is not None else [SidecarVisionProvider(),ClarityVisionProvider(),CornerGeometryVisionProvider(),ClipSemanticVisionProvider()]
    def evaluate(self,image,requirements,**context):
        subs=[];app=[]
        for p in self.providers:
            r=p.evaluate(image,requirements,**context)
            if r.get("status") not in {"PASS","FAIL","NOT_EVALUATED"}:r={**r,"status":"NOT_EVALUATED","reason":f"malformed provider status: {r.get('status')!r}"}
            subs.append({"provider":type(p).__name__,**r})
            if r["status"]!="NOT_EVALUATED":app.append(r)
        if not app:return {"status":"NOT_EVALUATED","reason":"no vision provider could evaluate this scene","sub_results":subs}
        fails=[r for r in app if r["status"]=="FAIL"]
        if fails:return {"status":"FAIL","reason":fails[0].get("reason","semantic visual QA failed"),"sub_results":subs}
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
def evaluate_scene_semantics(scene,clip,provider,frame_path):
    if not scene.visual_qa_requirements:return {"scene":scene.id,"status":"NOT_EVALUATED","reason":"no visual_qa_requirements declared"}
    extract_representative_frame(clip,frame_path)
    r=provider.evaluate(frame_path,scene.visual_qa_requirements,narration=getattr(scene,"narration",""),positive_labels=list(getattr(scene,"visual_qa_labels",[]) or []),negative_labels=list(getattr(scene,"visual_qa_negative_labels",[]) or []))
    return {"scene":scene.id,"requirements":scene.visual_qa_requirements,**r}
def production_semantic_ok(status,require_semantic):return status=="PASS" if require_semantic else status!="FAIL"
def semantic_visual_gate(project,scene_clips,provider=None,build_dir=Path("build")):
    provider=provider or default_vision_provider();results=[]
    for scene,clip in zip(project.scenes,scene_clips):
        if scene.visual_qa_requirements:results.append(evaluate_scene_semantics(scene,clip,provider,build_dir/f"{scene.id}_qa.jpg"))
    status="FAIL" if any(r["status"]=="FAIL" for r in results) else ("PASS" if results and all(r["status"]=="PASS" for r in results) else "NOT_EVALUATED")
    return {"status":status,"results":results}
