from __future__ import annotations
import asyncio, json, os, shutil, subprocess, time, urllib.error, urllib.request
from pathlib import Path
from types import SimpleNamespace
from .project import load_project
from .prosody import PhraseSpec, plan_narration
from .tts import synthesize_plan
from .subtitles import segment
from .qa import subtitle_qa, write_report
from .visual_qa import asset_visual_gate, default_vision_provider, evaluate_scene_semantics, production_semantic_ok
from .final_video_qa import run_final_video_qa
from .captions import merge_scene_srt_files

def _srt_time(x:float)->str:
    ms=round(x*1000); h,ms=divmod(ms,3600000); m,ms=divmod(ms,60000); s,ms=divmod(ms,1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

def write_srt(path:Path,caps):
    blocks=[f"{i}\n{_srt_time(c.start)} --> {_srt_time(c.end)}\n{c.text}" for i,c in enumerate(caps,1)]
    path.write_text("\n\n".join(blocks)+"\n",encoding="utf-8")

_TRANSIENT_HTTP_CODES={429,500,502,503,504}

def _download(url:str,path:Path,max_attempts:int=4)->Path:
    """Download with bounded retry+backoff for transient server-side errors
    (rate limiting, brief outages). Permanent client errors (404, 403, ...)
    fail immediately -- retrying them would never succeed and would just
    delay the recovery loop's move to the next candidate."""
    req=urllib.request.Request(url,headers={"User-Agent":"shorts-studio/0.1"})
    last_error=None
    for attempt in range(max_attempts):
        try:
            with urllib.request.urlopen(req,timeout=60) as src, path.open("wb") as dst:
                shutil.copyfileobj(src,dst)
            return path
        except urllib.error.HTTPError as e:
            last_error=e
            if e.code not in _TRANSIENT_HTTP_CODES or attempt==max_attempts-1:
                raise
        except (urllib.error.URLError, TimeoutError) as e:
            last_error=e
            if attempt==max_attempts-1:
                raise
        time.sleep(2**(attempt+1))
    raise last_error  # pragma: no cover - loop always returns or raises above

# The picture has a fixed centered box; its pixels never enter the title or subtitle regions.
# All pixels outside the picture box stay black.
SAFE_TOP_Y=190
IMAGE_TOP_Y=230
IMAGE_BOX_WIDTH=980
IMAGE_BOX_HEIGHT=1000
SAFE_BOTTOM_Y=IMAGE_TOP_Y+IMAGE_BOX_HEIGHT

# Shorts-style speech captions live in the black gutter directly below the picture.
# Keep them visually connected to the content while preserving the hard no-overlap contract.
CAPTION_FONT_SIZE=30
CAPTION_MARGIN_V=48
CAPTION_OUTLINE=2
CAPTION_STYLE=f"Alignment=2,MarginV={CAPTION_MARGIN_V},MarginL=72,MarginR=72,FontSize={CAPTION_FONT_SIZE},Outline={CAPTION_OUTLINE},Shadow=1,Bold=0,WrapStyle=0"
CAPTION_MASK_TOP=SAFE_BOTTOM_Y
CAPTION_MASK_HEIGHT=1920-SAFE_BOTTOM_Y

# ASS/libass alignment codes rendered by this ffmpeg build follow the legacy
# SSA numbering (5/6/7 = top row) -- Alignment=6 is the top-center value.
_TITLE_STYLE="Alignment=6,MarginV=18,FontSize=16,Outline=2,Shadow=0,Bold=1"

def _title_clause(title_srt:Path|None)->str:
    if not title_srt:
        return ""
    return f",subtitles={title_srt.as_posix()}:force_style='{_TITLE_STYLE}'"

def _write_title_srt(path:Path, title:str, duration:float)->Path:
    path.write_text(f"1\n{_srt_time(0.0)} --> {_srt_time(duration)}\n{title}\n\n",encoding="utf-8")
    return path

def _visual_filter(scene, srt:Path, fps:int, title_srt:Path|None=None)->str:
    style=CAPTION_STYLE
    # Contain the complete photo in the same centered box for every scene.
    # The final canvas is black, so subtitles can only appear in the separate
    # lower region; still-image motion is intentionally disabled.
    picture=(
        f"scale={IMAGE_BOX_WIDTH}:{IMAGE_BOX_HEIGHT}:force_original_aspect_ratio=decrease:flags=lanczos,"
        f"pad={IMAGE_BOX_WIDTH}:{IMAGE_BOX_HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1"
    )
    return (
        f"{picture},pad=1080:1920:(ow-iw)/2:{IMAGE_TOP_Y}:color=black,"
        f"fps={fps},format=yuv420p,split=2[base][cap];"
        f"[cap]subtitles={srt.as_posix()}:force_style='{style}',crop=1080:{CAPTION_MASK_HEIGHT}:0:{CAPTION_MASK_TOP}[capg];"
        f"[base][capg]overlay=0:{CAPTION_MASK_TOP}"
        f"{_title_clause(title_srt)}"
    )

def _rasterize_svg(svg:Path, output:Path, width:int=1080, height:int=1920)->Path:
    # ffmpeg has no built-in SVG decoder (it only demuxes "svg_pipe", it cannot
    # decode the vector content), so SVG assets must be rasterized before
    # ffmpeg ever sees them.
    if not shutil.which("rsvg-convert"):
        raise RuntimeError("rsvg-convert (apt package librsvg2-bin) is required to rasterize SVG assets")
    subprocess.run(["rsvg-convert","-w",str(width),"-h",str(height),str(svg),"-o",str(output)],check=True,capture_output=True)
    return output

def _resolve_asset(candidate:dict, build:Path, scene_id:str, index:int)->Path|None:
    asset=candidate.get("asset"); asset_url=candidate.get("asset_url")
    path=None
    if asset and Path(asset).exists():
        path=Path(asset)
    elif asset_url:
        suffix=Path(asset_url.split('?')[0]).suffix or '.jpg'
        path=_download(asset_url, build/f"{scene_id}_asset_{index}{suffix}")
    if path and path.suffix.lower()==".svg":
        path=_rasterize_svg(path, build/f"{scene_id}_asset_{index}.png")
    return path

def _resolve_cached_asset(candidate:dict, build:Path, scene_id:str, index:int, asset_cache:dict)->Path|None:
    """Resolve each source asset once per production and reuse the local file."""
    key=(candidate.get("asset"),candidate.get("asset_url"))
    cached=asset_cache.get(key)
    if cached is not None and Path(cached).exists():
        return Path(cached)
    asset=_resolve_asset(candidate,build,scene_id,index)
    if asset is not None:
        asset_cache[key]=asset
    return asset

def _composite_scene_clip(scene, asset:Path|None, audio:Path, srt:Path, duration:float, fps:int, build:Path, index:int, title:str|None=None)->Path:
    clip=build/(f"{scene.id}.mp4" if index==0 else f"{scene.id}_r{index}.mp4")
    title_srt=_write_title_srt(build/f"{scene.id}_title.srt",title,duration) if title else None
    if asset:
        cmd=["ffmpeg","-y","-loop","1","-framerate",str(fps),"-i",str(asset),"-i",str(audio),"-t",str(duration),"-vf",_visual_filter(scene,srt,fps,title_srt),"-c:v","libx264","-pix_fmt","yuv420p","-af",f"apad=whole_dur={duration}","-c:a","aac",str(clip)]
    else:
        vf=f"split=2[base][cap];[cap]subtitles={srt.as_posix()}:force_style='{CAPTION_STYLE}',crop=1080:{CAPTION_MASK_HEIGHT}:0:{CAPTION_MASK_TOP}[capg];[base][capg]overlay=0:{CAPTION_MASK_TOP}{_title_clause(title_srt)}"
        cmd=["ffmpeg","-y","-f","lavfi","-i",f"color=c=black:s=1080x1920:r={fps}:d={duration}","-i",str(audio),"-vf",vf,"-af",f"apad=whole_dur={duration}","-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac",str(clip)]
    try:
        subprocess.run(cmd,check=True,capture_output=True,text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg failed compositing {scene.id}: {e.stderr[-2000:] if e.stderr else e}") from e
    return clip

def _visual_beat_windows(scene, duration:float)->list[tuple[object,float]]:
    """Resolve timed visual beats into positive-duration windows."""
    beats=list(getattr(scene,"visual_beats",None) or [])
    if not beats:
        return []
    windows=[]
    for i,beat in enumerate(beats):
        end=beats[i+1].start if i+1<len(beats) else duration
        length=max(0.0,min(duration,end)-beat.start)
        if length>0.01:
            windows.append((beat,length))
    return windows

def _composite_visual_beats(scene, audio:Path, srt:Path, duration:float, fps:int, build:Path, index:int, title:str|None=None, asset_cache:dict|None=None)->tuple[Path,list[Path],list[float],list[Path]]:
    """Render multiple picture cuts under one untouched narration/caption track."""
    windows=_visual_beat_windows(scene,duration)
    if not windows:
        raise ValueError("visual beat renderer requires at least one positive-duration beat")
    visual_clips=[]; assets=[]
    asset_cache=asset_cache if asset_cache is not None else {}
    for beat_index,(beat,beat_duration) in enumerate(windows):
        candidate={"asset":beat.asset,"asset_url":beat.asset_url,"attribution":beat.attribution}
        asset=_resolve_cached_asset(candidate,build,f"{scene.id}_beat{beat_index}",index,asset_cache)
        if asset is None:
            raise RuntimeError(f"{scene.id}: visual beat {beat_index} asset could not be resolved")
        assets.append(asset)
        # Render only the moving picture here. Captions/title/audio are applied
        # once after the cuts are joined, so their timing remains scene-global.
        beat_scene=SimpleNamespace(motion=beat.motion)
        vf=(
            f"scale={IMAGE_BOX_WIDTH}:{IMAGE_BOX_HEIGHT}:force_original_aspect_ratio=decrease:flags=lanczos,"
            f"pad={IMAGE_BOX_WIDTH}:{IMAGE_BOX_HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,"
            f"pad=1080:1920:(ow-iw)/2:{IMAGE_TOP_Y}:color=black,fps={fps},format=yuv420p"
        )
        beat_clip=build/f"{scene.id}_beat{beat_index}_v.mp4"
        cmd=["ffmpeg","-y","-loop","1","-framerate",str(fps),"-i",str(asset),"-t",str(beat_duration),"-vf",vf,"-an","-c:v","libx264","-pix_fmt","yuv420p",str(beat_clip)]
        try:
            subprocess.run(cmd,check=True,capture_output=True,text=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"ffmpeg failed visual beat {scene.id}/{beat_index}: {e.stderr[-2000:] if e.stderr else e}") from e
        visual_clips.append(beat_clip)
    lst=build/f"{scene.id}_beats.txt"
    lst.write_text("\n".join(f"file '{x.resolve()}'" for x in visual_clips),encoding="utf-8")
    joined=build/f"{scene.id}_beats_joined.mp4"
    subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(lst),"-c","copy",str(joined)],check=True,capture_output=True,text=True)
    clip=build/(f"{scene.id}.mp4" if index==0 else f"{scene.id}_r{index}.mp4")
    title_srt=_write_title_srt(build/f"{scene.id}_title.srt",title,duration) if title else None
    vf=f"split=2[base][cap];[cap]subtitles={srt.as_posix()}:force_style='{CAPTION_STYLE}',crop=1080:{CAPTION_MASK_HEIGHT}:0:{CAPTION_MASK_TOP}[capg];[base][capg]overlay=0:{CAPTION_MASK_TOP}{_title_clause(title_srt)}"
    subprocess.run(["ffmpeg","-y","-i",str(joined),"-i",str(audio),"-t",str(duration),"-vf",vf,"-af",f"apad=whole_dur={duration}","-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac",str(clip)],check=True,capture_output=True,text=True)
    return clip,assets,[_media_duration_seconds(path) for path in visual_clips],visual_clips

def _evaluate_visual_beats(scene, beat_clips:list[Path], beat_assets:list[Path], provider, build:Path)->dict:
    """Evaluate every visual beat independently; a scene-level midpoint cannot
    prove that required earlier/later beats are present in the final sequence."""
    beats=list(getattr(scene,"visual_beats",None) or [])
    if not beats or len(beats)!=len(beat_clips) or len(beats)!=len(beat_assets):
        return {"scene":scene.id,"status":"FAIL","reason":"visual beat QA evidence count does not match manifest"}
    results=[]
    for index,(beat,clip,asset) in enumerate(zip(beats,beat_clips,beat_assets)):
        beat_scene=SimpleNamespace(
            id=f"{scene.id}_beat_{index:02d}",
            narration=getattr(scene,"narration",""),
            visual_qa_requirements=list(getattr(beat,"visual_qa_requirements",[]) or []),
            visual_qa_labels=list(getattr(beat,"visual_qa_labels",[]) or []),
            visual_qa_negative_labels=list(getattr(beat,"visual_qa_negative_labels",[]) or []),
            visual_qa_expected_sha256=list(getattr(beat,"visual_qa_expected_sha256",[]) or []),
        )
        frame=build/f"{beat_scene.id}_qa.jpg"
        results.append(evaluate_scene_semantics(beat_scene,clip,provider,frame,asset_path=asset))
    status="FAIL" if any(x.get("status")=="FAIL" for x in results) else (
        "PASS" if results and all(x.get("status")=="PASS" for x in results) else "NOT_EVALUATED"
    )
    return {"scene":scene.id,"status":status,"requirements":list(scene.visual_qa_requirements),"beat_results":results}

def _representative_visual_asset(assets:list[Path],durations:list[float],clip_duration:float)->Path:
    """Return the source image visible at the midpoint QA actually samples."""
    if not assets or len(assets)!=len(durations):
        raise ValueError("visual beat asset/duration counts do not match")
    if any(duration<=0 for duration in durations):
        raise ValueError("visual beat durations must be positive")
    target=max(0.0,min(clip_duration/2,sum(durations)))
    elapsed=0.0
    for asset,duration in zip(assets,durations):
        if target < elapsed+duration:
            return asset
        elapsed+=duration
    return assets[-1]

def _narration_plan(scene)->list[PhraseSpec]:
    """Boundary/pause placement is never authored -- it is always computed
    by the general Korean boundary planner (prosody.plan_narration ->
    korean_boundary). A scene may author WHICH TEXT belongs to which
    narrative role (a semantic/story decision); a scene with no such
    segments falls back to a single default-role segment covering the
    whole flat `narration` string, so any manifest benefits from the same
    automatic linguistic segmentation with no per-script configuration."""
    declared=getattr(scene,"narration_plan",None) or []
    if declared:
        segments=[(p.role,p.text,p.focus) for p in declared]
    else:
        segments=[("SETUP",scene.narration,False)]
    return plan_narration(segments)

def _log_narration_plan(scene, plan:list[PhraseSpec])->None:
    """Prints the planned synthesis units and boundaries for a scene so a
    future unnatural-pause report can be diagnosed from CI logs alone,
    without re-running the planner locally against a guessed input."""
    print(f"[prosody] {scene.id}: {len(plan)} synthesis unit(s)")
    for i,p in enumerate(plan):
        print(f"[prosody]   unit {i}: role={p.role} boundary={p.boundary} focus={p.focus} text={p.text!r}")

def _media_duration_seconds(path:Path)->float:
    """Return the duration of the artifact that will actually be concatenated.

    Scene planning/timing duration can be slightly longer than the encoded clip
    because ffmpeg uses -shortest. Final-video QA must therefore accumulate
    real clip durations, otherwise every later sample drifts forward and can
    eventually seek past EOF or between captions.
    """
    data=json.loads(subprocess.run(
        ["ffprobe","-v","error","-show_entries","format=duration","-of","json",str(path)],
        capture_output=True,text=True,check=True,
    ).stdout)
    return float(data["format"]["duration"])

def _synthesize_scene_audio(scene, build:Path)->tuple[Path,float,Path,dict,list]:
    audio=build/f"{scene.id}.mp3"; timing=build/f"{scene.id}.timing.json"
    plan=_narration_plan(scene)
    _log_narration_plan(scene,plan)
    words=asyncio.run(synthesize_plan(plan,audio,timing,use_role_rates=True))
    duration=max(w.end for w in words)+.25
    caps=segment(words,duration)
    q=subtitle_qa(caps,words,duration)
    srt=build/f"{scene.id}.srt"; write_srt(srt,caps)
    return audio,duration,srt,{"scene":scene.id,**q},caps

def _asset_candidates(scene)->list[dict]:
    primary={"asset":scene.asset,"asset_url":scene.asset_url,"attribution":scene.attribution}
    return [primary]+[c.model_dump() for c in scene.recovery_candidates]

def _render_scene_with_recovery(scene, audio:Path, duration:float, srt:Path, fps:int, build:Path, max_attempts:int, provider, title:str|None=None, asset_cache:dict|None=None)->dict:
    """Render a scene's visual clip, running semantic visual QA and, on FAIL,
    swapping to the next declared fallback asset and re-rendering ONLY this
    scene's clip (never the whole production) until it passes or the bounded
    recovery budget is exhausted."""
    candidates=_asset_candidates(scene)
    last_index_tried=-1; last_error=None; result=None; clip=None; used=None
    for index in range(min(len(candidates), max_attempts+1)):
        last_index_tried=index
        try:
            if getattr(scene,"visual_beats",None):
                clip,beat_assets,beat_durations,beat_clips=_composite_visual_beats(scene,audio,srt,duration,fps,build,index,title=title,asset_cache=asset_cache)
                asset=_representative_visual_asset(beat_assets,beat_durations,_media_duration_seconds(clip))
            else:
                asset=_resolve_asset(candidates[index],build,scene.id,index)
                clip=_composite_scene_clip(scene,asset,audio,srt,duration,fps,build,index,title=title)
        except Exception as e:
            last_error=f"candidate {index} failed to resolve/render: {e}"
            result={"scene":scene.id,"status":"FAIL","reason":last_error}
            continue
        used={"index":index,"asset":str(asset) if asset else None,"attribution":candidates[index].get("attribution")}
        if not scene.visual_qa_requirements:
            result={"scene":scene.id,"status":"NOT_EVALUATED","reason":"no visual_qa_requirements declared"}
            break
        if getattr(scene,"visual_beats",None):
            result=_evaluate_visual_beats(scene,beat_clips,beat_assets,provider,build)
        else:
            frame=build/f"{scene.id}_qa.jpg"
            result=evaluate_scene_semantics(scene,clip,provider,frame,asset_path=asset)
        if result["status"]!="FAIL":
            break
        last_error=result.get("reason")
    recovery_attempts=last_index_tried  # index 0 is the primary asset, not a recovery
    more_candidates_available=(last_index_tried+1)<len(candidates)
    exhausted=result["status"]=="FAIL" and (not more_candidates_available or recovery_attempts>=max_attempts)
    result={**result,"recovery_attempts":recovery_attempts,"recovery_exhausted":bool(exhausted)}
    return {"clip":clip,"source":used,"semantic":result}

def render(manifest:str,dry_run:bool=False)->dict:
    p=load_project(manifest)
    if dry_run: return {"status":"PASS","scenes":len(p.scenes),"mode":"dry-run"}
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("FFmpeg/ffprobe required")
    build=Path("build"); dist=Path("dist"); build.mkdir(exist_ok=True); dist.mkdir(exist_ok=True)
    provider=default_vision_provider()
    concat=[]; subtitle_reports=[]; sources=[]; semantic_results=[]; scene_windows=[]; cumulative=0.0
    asset_cache={}
    for scene in p.scenes:
        audio,duration,srt,q,caps=_synthesize_scene_audio(scene,build)
        subtitle_reports.append(q)
        if q["status"]!="PASS": raise RuntimeError(f"subtitle QA failed: {scene.id}: {q}")
        title=scene.overlay_title or p.overlay_title
        outcome=_render_scene_with_recovery(scene,audio,duration,srt,p.fps,build,p.max_visual_recovery_attempts,provider,title=title,asset_cache=asset_cache)
        if outcome["clip"] is None:
            raise RuntimeError(f"scene {scene.id}: no asset candidate could be rendered: {outcome['semantic'].get('reason')}")
        concat.append(outcome["clip"])
        sources.append({"scene":scene.id,"asset":outcome["source"]["asset"] if outcome["source"] else None,"attribution":outcome["source"]["attribution"] if outcome["source"] else None,"candidate_index":outcome["source"]["index"] if outcome["source"] else None,"recovery_attempts":outcome["semantic"].get("recovery_attempts",0)})
        if scene.visual_qa_requirements:
            semantic_results.append(outcome["semantic"])
        clip_duration=_media_duration_seconds(outcome["clip"])
        scene_windows.append({"scene":scene.id,"start":cumulative,"duration":clip_duration,"caption_window":(caps[0].start,caps[0].end) if caps else None})
        cumulative+=clip_duration
    lst=build/"concat.txt"; lst.write_text("\n".join(f"file '{x.resolve()}'" for x in concat),encoding="utf-8")
    final=dist/"final.mp4"
    subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(lst),"-c","copy",str(final)],check=True,capture_output=True)
    probe=json.loads(subprocess.run(["ffprobe","-v","error","-show_entries","stream=codec_type,width,height,r_frame_rate","-show_entries","format=duration","-of","json",str(final)],capture_output=True,text=True,check=True).stdout)
    caption_result=merge_scene_srt_files(scene_windows,build,float(probe["format"]["duration"]),dist/"captions.srt")
    visual=asset_visual_gate(p,sources)
    if any(r["status"]=="FAIL" for r in semantic_results): semantic_status="FAIL"
    elif semantic_results and all(r["status"]=="PASS" for r in semantic_results): semantic_status="PASS"
    else: semantic_status="NOT_EVALUATED"
    semantic={"status":semantic_status,"results":semantic_results}
    require_semantic=bool(os.environ.get("SHORTS_REQUIRE_SEMANTIC_QA"))
    semantic_ok=production_semantic_ok(semantic["status"],require_semantic)
    final_video=run_final_video_qa(final,p,sources,semantic_results,probe,scene_windows,build)
    overall="PASS" if visual["structural_status"]=="PASS" and semantic_ok and all(x["status"]=="PASS" for x in subtitle_reports) and final_video["status"]=="PASS" else "FAIL"
    report={"status":overall,"subtitle_reports":subtitle_reports,"visual_qa":visual,"semantic_visual_qa":semantic,"semantic_required":require_semantic,"final_video_qa":final_video,"sources":sources,"probe":probe,"captions":caption_result,"output":str(final)}
    write_report(dist/"qa_report.json",report)
    if overall!="PASS":
        raise RuntimeError(f"QA failed: {report}")
    return report
