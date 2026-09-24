from __future__ import annotations
import asyncio, json, os, shutil, subprocess, time, urllib.error, urllib.request
from pathlib import Path
from .project import load_project
from .prosody import PhraseSpec, plan_narration
from .tts import synthesize_plan
from .subtitles import segment
from .qa import subtitle_qa, write_report
from .visual_qa import asset_visual_gate, default_vision_provider, evaluate_scene_semantics, production_semantic_ok
from .final_video_qa import run_final_video_qa

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

# Bottom rows [SAFE_BOTTOM_Y, 1920) must ALWAYS stay pure black background --
# never sharp foreground -- because the burned-in caption safe area lives
# there (measured empirically: at MarginV=48 captions occupy rows ~1499-1585,
# so 1300 leaves >=199px of headroom even for a 2-line caption). This is a
# generic invariant enforced for every scene via the fg box's height, not a
# per-scene crop/position hack.
SAFE_BOTTOM_Y=1300
# Top rows [0, SAFE_TOP_Y) are reserved for the persistent top title so the
# foreground image doesn't visually crowd it.
SAFE_TOP_Y=190
_FG_BAND_WIDTH=1000
# How often a scene's picture changes when more than one asset is declared
# for it (primary + recovery_candidates) and no semantic QA gates the scene
# (see _render_scene_rotation). A scene with only one asset simply shows it
# for the whole duration, as before -- this is purely additional visual
# variety for scenes with nothing to protect via QA.
IMAGE_ROTATION_SECONDS=3.0

# ASS/libass alignment codes rendered by this ffmpeg build follow the legacy
# SSA numbering (5/6/7 = top row), NOT the ASS numpad convention (7/8/9 = top
# row) -- verified empirically: Alignment=8 rendered mid-screen, not near the
# top. Alignment=6 is the top-center value that actually works here.
_TITLE_STYLE="Alignment=6,MarginV=15,FontSize=20,Outline=3,Shadow=0,Bold=1"

def _title_clause(title_srt:Path|None)->str:
    if not title_srt:
        return ""
    return f",subtitles={title_srt.as_posix()}:force_style='{_TITLE_STYLE}'"

def _write_title_srt(path:Path, title:str, duration:float)->Path:
    path.write_text(f"1\n{_srt_time(0.0)} --> {_srt_time(duration)}\n{title}\n\n",encoding="utf-8")
    return path

def _rotation_segments(assets:list[Path], duration:float, seg_seconds:float|None=None)->list[tuple[Path,float]]:
    """Splits `duration` into consecutive (asset, length) segments cycling
    through `assets` in declared order, each seg_seconds long except the
    last (shortened to fit exactly). Zero or one asset is the common,
    QA-gated case: no image, or one segment spanning the whole duration --
    unchanged from the historical single-image-per-scene behavior.

    `seg_seconds` defaults to the CURRENT value of the module-level
    IMAGE_ROTATION_SECONDS, looked up at call time rather than bound into
    the signature -- a mutable default bound at def-time would silently
    ignore any later override of the module constant (e.g. in tests)."""
    if seg_seconds is None:
        seg_seconds=IMAGE_ROTATION_SECONDS
    if not assets:
        return []
    if len(assets)==1:
        return [(assets[0],duration)]
    segments=[]; t=0.0; i=0
    while t<duration-1e-6:
        length=min(seg_seconds,duration-t)
        segments.append((assets[i%len(assets)],length))
        t+=length; i+=1
    return segments

# Slow, centered zoom-in used ONLY for the single-image fallback (see
# _rotation_filter_complex): "moving viewpoint" for a scene that has no
# additional image to cut to, rather than a frozen frame. It is bounded
# entirely inside the fixed-size foreground box (via zoompan's own `s=`),
# so it can NEVER grow the foreground outside the caption-safe band --
# unlike the old whole-frame zoompan this replaced, which zoomed the
# composited frame itself and had no such structural guarantee.
_KEN_BURNS_ZOOM_EXPR="min(zoom+0.0007,1.15)"

def _fg_filter(fg_w:int, fg_h:int, fps:int, motion:bool)->str:
    """The per-image foreground filter placed into the fixed box. `motion`
    selects between:
      - False (2+ images declared -- see _rotation_segments): a plain
        contain-fit scale. The picture is visually still for as long as
        it's on screen; the cuts between images are what supplies visual
        change, so no extra motion is added on top.
      - True (only one image available for the whole scene): a bounded
        Ken Burns zoom-in. The image is first cover-cropped to the box's
        exact aspect ratio (so zoompan has no letterbox bars to zoom into),
        upscaled for headroom, then zoompan'd back down to EXACTLY fg_w x
        fg_h -- the rendered box's size and position never change, only
        the framing of the image inside it does."""
    if not motion:
        return f"scale={fg_w}:{fg_h}:force_original_aspect_ratio=decrease"
    # Contain-fit + pad (NOT cover-crop) before zooming in: this keeps the
    # "preserve the complete source image" guarantee at zoom=1 (the start
    # of the clip) -- a cover-crop would immediately discard whatever
    # doesn't fit the box's aspect ratio, which is exactly the content-loss
    # problem the contain-fit approach was originally chosen to avoid. The
    # padding is black, matching the surrounding background, so it reads as
    # part of the backdrop rather than a visible letterbox bar; zooming in
    # over time mostly eats into that padding first.
    return (
        f"scale={fg_w}:{fg_h}:force_original_aspect_ratio=decrease,"
        f"pad={fg_w}:{fg_h}:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"scale={fg_w*2}:{fg_h*2},"
        f"zoompan=z='{_KEN_BURNS_ZOOM_EXPR}':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':d=1:s={fg_w}x{fg_h}:fps={fps}"
    )

def _rotation_filter_complex(lengths:list[float], srt:Path, fps:int, title_srt:Path|None=None)->str:
    """Filter graph for input 0 = the black background (spanning the whole
    clip) and inputs 1..len(lengths) = each rotation image, already trimmed
    (via -t) to its own segment length and time-shifted (via -itsoffset in
    the caller) to occupy its window on input 0's shared timeline. Each
    image is placed centered in the caption-safe band and only composited
    during its own window via `enable`. A single segment (no additional
    image was available) gets the bounded Ken Burns fallback (see
    _fg_filter); 2+ segments each stay visually still -- switching between
    real images is already the visual change."""
    fg_h=SAFE_BOTTOM_Y-SAFE_TOP_Y
    style="Alignment=2,MarginV=48,FontSize=18,Outline=2,Shadow=0,Bold=1"
    n=len(lengths)
    fg_scale=_fg_filter(_FG_BAND_WIDTH,fg_h,fps,motion=(n==1))
    starts=[0.0]
    for length in lengths[:-1]:
        starts.append(starts[-1]+length)
    pos=f"(W-w)/2:{SAFE_TOP_Y}+({fg_h}-h)/2"
    parts=[]; cur="[0:v]"
    for i in range(n):
        parts.append(f"[{i+1}:v]{fg_scale}[fg{i}]")
        if n==1:
            enable_clause=""
        elif i==n-1:
            enable_clause=f":enable='gte(t,{starts[i]:.3f})'"
        else:
            enable_clause=f":enable='between(t,{starts[i]:.3f},{starts[i+1]:.3f})'"
        out=f"vmain" if i==n-1 else f"v{i}"
        parts.append(f"{cur}[fg{i}]overlay={pos}{enable_clause}[{out}]")
        cur=f"[{out}]"
    parts.append(f"{cur}fps={fps},subtitles={srt.as_posix()}:force_style='{style}'{_title_clause(title_srt)}[vout]")
    return ";".join(parts)

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

def _composite_scene_clip(scene, asset, audio:Path, srt:Path, duration:float, fps:int, build:Path, index:int, title:str|None=None)->Path:
    """`asset` is either a single Path|None (the historical, still-supported
    call shape: no image, or one image for the whole clip) or a list[Path]
    (a QA-exempt scene's rotation pool -- see _render_scene_rotation).
    Either way the background is solid black (never a blurred copy of the
    image) and the foreground is placed centered in the caption-safe band,
    at a fixed position and size that can never grow into the caption zone.
    With 2+ images, each is shown visually still for its own window (the
    cuts between them supply the visual change); with exactly one image
    (no additional image was available), it instead gets a bounded Ken
    Burns zoom -- a "moving viewpoint" rather than a frozen frame -- see
    _fg_filter."""
    assets=asset if isinstance(asset,list) else ([asset] if asset else [])
    clip=build/(f"{scene.id}.mp4" if index==0 else f"{scene.id}_r{index}.mp4")
    title_srt=_write_title_srt(build/f"{scene.id}_title.srt",title,duration) if title else None
    if assets:
        segments=_rotation_segments(assets,duration)
        lengths=[length for _,length in segments]
        cmd=["ffmpeg","-y","-f","lavfi","-i",f"color=c=black:s=1080x1920:r={fps}:d={duration}"]
        t=0.0
        for img,length in segments:
            if t>0:
                cmd+=["-itsoffset",f"{t:.3f}"]
            cmd+=["-loop","1","-framerate",str(fps),"-t",f"{length:.3f}","-i",str(img)]
            t+=length
        cmd+=["-i",str(audio)]
        audio_idx=len(segments)+1
        filt=_rotation_filter_complex(lengths,srt,fps,title_srt)
        cmd+=["-filter_complex",filt,"-map","[vout]","-map",f"{audio_idx}:a","-t",str(duration),"-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac","-shortest",str(clip)]
    else:
        vf=f"subtitles={srt.as_posix()}:force_style='Alignment=2,MarginV=48,FontSize=18,Outline=2,Bold=1'{_title_clause(title_srt)}"
        cmd=["ffmpeg","-y","-f","lavfi","-i",f"color=c=black:s=1080x1920:r={fps}:d={duration}","-i",str(audio),"-vf",vf,"-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac","-shortest",str(clip)]
    try:
        subprocess.run(cmd,check=True,capture_output=True,text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg failed compositing {scene.id}: {e.stderr[-2000:] if e.stderr else e}") from e
    return clip

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

def _render_scene_rotation(scene, candidates:list[dict], audio:Path, duration:float, srt:Path, fps:int, build:Path, title:str|None=None)->dict:
    """A scene with no visual_qa_requirements has nothing semantic QA can
    FAIL, so the sequential try-on-failure recovery loop below doesn't
    apply. Instead, every declared asset (primary + recovery_candidates) is
    resolved and shown in rotation across the scene's duration (see
    _rotation_segments) for visual variety -- a scene with only one asset
    still just shows it the whole time, unchanged from before. A secondary
    (rotation-only) candidate that fails to resolve is skipped rather than
    failing the scene; only the primary failing does."""
    assets=[]; used=None
    for index,cand in enumerate(candidates):
        try:
            asset=_resolve_asset(cand,build,scene.id,index)
        except Exception as e:
            if index==0:
                reason=f"candidate 0 failed to resolve/render: {e}"
                return {"clip":None,"source":None,"semantic":{"scene":scene.id,"status":"FAIL","reason":reason,"recovery_attempts":0,"recovery_exhausted":True}}
            continue
        if used is None:
            used={"index":index,"asset":str(asset) if asset else None,"attribution":cand.get("attribution")}
        if asset:
            assets.append(asset)
    clip=_composite_scene_clip(scene,assets,audio,srt,duration,fps,build,0,title=title)
    result={"scene":scene.id,"status":"NOT_EVALUATED","reason":"no visual_qa_requirements declared","recovery_attempts":0,"recovery_exhausted":False}
    return {"clip":clip,"source":used,"semantic":result}

def _render_scene_with_recovery(scene, audio:Path, duration:float, srt:Path, fps:int, build:Path, max_attempts:int, provider, title:str|None=None)->dict:
    """Render a scene's visual clip, running semantic visual QA and, on FAIL,
    swapping to the next declared fallback asset and re-rendering ONLY this
    scene's clip (never the whole production) until it passes or the bounded
    recovery budget is exhausted."""
    candidates=_asset_candidates(scene)
    if not scene.visual_qa_requirements:
        return _render_scene_rotation(scene,candidates,audio,duration,srt,fps,build,title=title)
    last_index_tried=-1; last_error=None; result=None; clip=None; used=None
    for index in range(min(len(candidates), max_attempts+1)):
        last_index_tried=index
        try:
            asset=_resolve_asset(candidates[index],build,scene.id,index)
            clip=_composite_scene_clip(scene,asset,audio,srt,duration,fps,build,index,title=title)
        except Exception as e:
            last_error=f"candidate {index} failed to resolve/render: {e}"
            result={"scene":scene.id,"status":"FAIL","reason":last_error}
            continue
        used={"index":index,"asset":str(asset) if asset else None,"attribution":candidates[index].get("attribution")}
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
    for scene in p.scenes:
        audio,duration,srt,q,caps=_synthesize_scene_audio(scene,build)
        subtitle_reports.append(q)
        if q["status"]!="PASS": raise RuntimeError(f"subtitle QA failed: {scene.id}: {q}")
        title=scene.overlay_title or p.overlay_title
        outcome=_render_scene_with_recovery(scene,audio,duration,srt,p.fps,build,p.max_visual_recovery_attempts,provider,title=title)
        if outcome["clip"] is None:
            raise RuntimeError(f"scene {scene.id}: no asset candidate could be rendered: {outcome['semantic'].get('reason')}")
        concat.append(outcome["clip"])
        sources.append({"scene":scene.id,"asset":outcome["source"]["asset"] if outcome["source"] else None,"attribution":outcome["source"]["attribution"] if outcome["source"] else None,"candidate_index":outcome["source"]["index"] if outcome["source"] else None,"recovery_attempts":outcome["semantic"].get("recovery_attempts",0)})
        if scene.visual_qa_requirements:
            semantic_results.append(outcome["semantic"])
        scene_windows.append({"scene":scene.id,"start":cumulative,"caption_window":(caps[0].start,caps[0].end) if caps else None})
        cumulative+=duration
    lst=build/"concat.txt"; lst.write_text("\n".join(f"file '{x.resolve()}'" for x in concat),encoding="utf-8")
    final=dist/"final.mp4"
    subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(lst),"-c","copy",str(final)],check=True,capture_output=True)
    probe=json.loads(subprocess.run(["ffprobe","-v","error","-show_entries","stream=codec_type,width,height,r_frame_rate","-show_entries","format=duration","-of","json",str(final)],capture_output=True,text=True,check=True).stdout)
    visual=asset_visual_gate(p,sources)
    if any(r["status"]=="FAIL" for r in semantic_results): semantic_status="FAIL"
    elif semantic_results and all(r["status"]=="PASS" for r in semantic_results): semantic_status="PASS"
    else: semantic_status="NOT_EVALUATED"
    semantic={"status":semantic_status,"results":semantic_results}
    require_semantic=bool(os.environ.get("SHORTS_REQUIRE_SEMANTIC_QA"))
    semantic_ok=production_semantic_ok(semantic["status"],require_semantic)
    final_video=run_final_video_qa(final,p,sources,semantic_results,probe,scene_windows,build)
    overall="PASS" if visual["structural_status"]=="PASS" and semantic_ok and all(x["status"]=="PASS" for x in subtitle_reports) and final_video["status"]=="PASS" else "FAIL"
    report={"status":overall,"subtitle_reports":subtitle_reports,"visual_qa":visual,"semantic_visual_qa":semantic,"semantic_required":require_semantic,"final_video_qa":final_video,"sources":sources,"probe":probe,"output":str(final)}
    write_report(dist/"qa_report.json",report)
    if overall!="PASS":
        raise RuntimeError(f"QA failed: {report}")
    return report
